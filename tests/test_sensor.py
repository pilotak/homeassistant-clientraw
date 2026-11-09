"""Registry migration, polling, error recovery, and lifecycle coverage."""

from datetime import timedelta
import aiohttp
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import UnitOfSpeed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util, slugify
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry, async_fire_time_changed,
)

from custom_components.clientraw.client import endpoint_id, import_id
from custom_components.clientraw.const import CONDITIONS, DOMAIN

DEVICE_CLASSES = {
    "temp": "temperature", "temp_indoor": "temperature",
    "temp_day_max": "temperature", "temp_day_min": "temperature",
    "dewpoint": "temperature", "heat_index": "temperature",
    "humidex": "temperature", "wind_chill": "temperature",
    "wind_chill_min": "temperature", "wind_chill_max": "temperature",
    "apparent_temp": "temperature", "apparent_temp_min": "temperature",
    "apparent_temp_max": "temperature", "humidity": "humidity",
    "humidity_indoor": "humidity", "humidity_min": "humidity",
    "humidity_max": "humidity", "pressure": "atmospheric_pressure",
    "daily_rain": "precipitation", "yesterday_rain": "precipitation",
    "monthly_rain": "precipitation", "yearly_rain": "precipitation",
    "rain_rate": "precipitation_intensity", "cloud_height": "distance",
    "vp_solar": "irradiance", "wind_speed": "wind_speed",
    "wind_speed_average": "wind_speed", "wind_speed_avg_10min": "wind_speed",
    "wind_gust_hour": "wind_speed", "wind_gust_day": "wind_speed",
    "last_updated": "timestamp",
}


@pytest.mark.parametrize("imperial", [False, True])
async def test_every_sensor_and_unit_system(hass, entry, fetch, imperial):
    if imperial:
        hass.config.units = US_CUSTOMARY_SYSTEM
    hass.config_entries.async_update_entry(
        entry, options={"monitored_conditions": list(CONDITIONS)})
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(registry, entry.entry_id)
    assert len(entities) == len(CONDITIONS)
    device = dr.async_get(hass).async_get_device({(DOMAIN, entry.entry_id)})
    assert device is not None
    assert device.name == entry.data["name"]
    assert device.config_entries == {entry.entry_id}
    for entity in entities:
        state = hass.states.get(entity.entity_id)
        assert state.state != "unavailable"
        assert entity.device_id == device.id
        key = entity.unique_id.removeprefix(f"{entry.entry_id}_")
        assert state.attributes.get("device_class") == DEVICE_CLASSES.get(key)
        if CONDITIONS[key].metric is not None:
            assert state.attributes["unit_of_measurement"] == (
                CONDITIONS[key].imperial if imperial else
                CONDITIONS[key].metric)
    temperature = hass.states.get("sensor.clientraw_temperature")
    assert float(temperature.state) == (50 if imperial else 10)
    assert temperature.attributes["unit_of_measurement"] == (
        "°F" if imperial else "°C")
    pressure = hass.states.get("sensor.clientraw_pressure")
    assert float(pressure.state) == (29.92 if imperial else 1013.25)
    assert pressure.attributes["unit_of_measurement"] == (
        "inHg" if imperial else "hPa")
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize("imperial", [False, True])
async def test_corrected_apparent_temperature_and_rain_rate(
    hass, entry, fetch, payload, imperial,
):
    if imperial:
        hass.config.units = US_CUSTOMARY_SYSTEM
    for key in ("apparent_temp", "apparent_temp_min", "apparent_temp_max"):
        payload[CONDITIONS[key].index] = "-5"
    payload[10] = "25.4"
    selected = ["apparent_temp", "apparent_temp_min", "apparent_temp_max",
                "rain_rate"]
    hass.config_entries.async_update_entry(
        entry, options={"monitored_conditions": selected})
    registry = er.async_get(hass)
    old_rate = registry.async_get_or_create(
        "sensor", DOMAIN, f"{entry.entry_id}_rain_rate", config_entry=entry,
        suggested_object_id="garden_rain_rate",
    )
    registry.async_update_entity(
        old_rate.entity_id, unit_of_measurement="in" if imperial else "mm")
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    for key in selected[:3]:
        entity_id = registry.async_get_entity_id(
            "sensor", DOMAIN, f"{entry.entry_id}_{key}")
        state = hass.states.get(entity_id)
        assert state.attributes["device_class"] == "temperature"
        assert float(state.state) == (23 if imperial else -5)
        assert state.attributes["unit_of_measurement"] == (
            "°F" if imperial else "°C")
    state = hass.states.get(old_rate.entity_id)
    assert state.attributes["device_class"] == "precipitation_intensity"
    assert state.attributes["unit_of_measurement"] == (
        "in/h" if imperial else "mm/h")
    assert float(state.state) == (1 if imperial else 25.4)
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize("key,raw,unit,expected", [
    ("temp", "20", "°F", 68),
    ("apparent_temp", "-5", "°F", 23),
    ("pressure", "1013.25", "inHg", 29.92),
    ("daily_rain", "25.4", "in", 1),
    ("rain_rate", "25.4", "in/h", 1),
    ("cloud_height", "100", "ft", 328.08),
])
async def test_sensor_unit_override(
    hass, entry, fetch, payload, key, raw, unit, expected,
):
    payload[CONDITIONS[key].index] = raw
    hass.config_entries.async_update_entry(
        entry, options={"monitored_conditions": [key]})
    assert await hass.config_entries.async_setup(entry.entry_id)
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_{key}")
    registry.async_update_entity_options(
        entity_id, "sensor", {"unit_of_measurement": unit})
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.attributes["unit_of_measurement"] == unit
    assert float(state.state) == pytest.approx(expected, abs=0.03)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).attributes["unit_of_measurement"] == unit
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_station_and_last_updated(hass, entry, fetch, payload):
    await hass.config.async_set_time_zone("Europe/Oslo")
    payload[32] = "TILSKI-15:12:24"
    payload[74] = "9/11/2026"
    hass.config_entries.async_update_entry(entry, options={
        "monitored_conditions": ["station", "date", "last_updated"],
    })
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.clientraw_station").state == "TILSKI"
    assert hass.states.get("sensor.clientraw_date").state == "9/11/2026"
    updated = hass.states.get("sensor.clientraw_last_updated")
    assert updated.state == "2026-11-09T14:12:24+00:00"
    assert updated.attributes["device_class"] == "timestamp"
    payload[74] = "---"
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("sensor.clientraw_last_updated").state == (
        "unavailable")
    assert hass.states.get("sensor.clientraw_station").state == "TILSKI"
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize("imperial", [False, True])
async def test_wind_sensor_units_are_configurable(
    hass, entry, fetch, payload, imperial,
):
    if imperial:
        hass.config.units = US_CUSTOMARY_SYSTEM
    wind_keys = [key for key, condition in CONDITIONS.items()
                 if condition.kind == "wind"]
    assert len(wind_keys) == 5
    for key in wind_keys:
        payload[CONDITIONS[key].index] = "10"
    hass.config_entries.async_update_entry(
        entry, options={"monitored_conditions": wind_keys})
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    for key in wind_keys:
        entity_id = registry.async_get_entity_id(
            "sensor", DOMAIN, f"{entry.entry_id}_{key}")
        state = hass.states.get(entity_id)
        assert state.attributes["device_class"] == "wind_speed"
        assert state.attributes["unit_of_measurement"] == (
            UnitOfSpeed.MILES_PER_HOUR if imperial
            else UnitOfSpeed.KILOMETERS_PER_HOUR)
        assert float(state.state) == (11.51 if imperial else 18.52)
        registry.async_update_entity_options(
            entity_id, "sensor", {"unit_of_measurement": "m/s"})
    await hass.async_block_till_done()
    for key in wind_keys:
        entity_id = registry.async_get_entity_id(
            "sensor", DOMAIN, f"{entry.entry_id}_{key}")
        state = hass.states.get(entity_id)
        assert state.attributes["unit_of_measurement"] == "m/s"
        assert float(state.state) == (5.15 if imperial else 5.14)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    for key in wind_keys:
        entity_id = registry.async_get_entity_id(
            "sensor", DOMAIN, f"{entry.entry_id}_{key}")
        assert hass.states.get(
            entity_id).attributes["unit_of_measurement"] == "m/s"
    for unit, expected in (("kn", 10), ("mph", 11.51), ("km/h", 18.52)):
        for key in wind_keys:
            entity_id = registry.async_get_entity_id(
                "sensor", DOMAIN, f"{entry.entry_id}_{key}")
            registry.async_update_entity_options(
                entity_id, "sensor", {"unit_of_measurement": unit})
        await hass.async_block_till_done()
        for key in wind_keys:
            entity_id = registry.async_get_entity_id(
                "sensor", DOMAIN, f"{entry.entry_id}_{key}")
            state = hass.states.get(entity_id)
            assert state.attributes["unit_of_measurement"] == unit
            assert float(state.state) == pytest.approx(expected, abs=0.02)
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_existing_wind_sensor_preserves_id_and_unit(hass, entry, fetch):
    registry = er.async_get(hass)
    existing = registry.async_get_or_create(
        "sensor", DOMAIN, f"{entry.entry_id}_wind_speed", config_entry=entry,
        suggested_object_id="garden_wind")
    hass.config_entries.async_update_entry(
        entry, options={"monitored_conditions": ["wind_speed"]})
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get(existing.entity_id)
    assert state.attributes["unit_of_measurement"] == "km/h"
    assert state.attributes["device_class"] == "wind_speed"
    assert registry.async_get(existing.entity_id).unique_id == (
        f"{entry.entry_id}_wind_speed")
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_sensors_and_forced_missing(hass, entry, fetch, payload):
    payload[164] = "---"
    hass.config_entries.async_update_entry(
        entry, options={"monitored_conditions": ["temp", "humidity_min"]})
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.clientraw_temperature").state == "10.0"
    assert hass.states.get("sensor.clientraw_min_humidity").state == (
        "unavailable")
    registry = er.async_get(hass)
    sensor = registry.async_get("sensor.clientraw_temperature")
    assert sensor.unique_id == f"{entry.entry_id}_temp"
    assert sensor.config_entry_id == entry.entry_id
    payload[164] = "30"
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("sensor.clientraw_min_humidity").state == "30.0"
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_existing_ui_entity_joins_device(hass, entry, fetch):
    registry = er.async_get(hass)
    existing = registry.async_get_or_create(
        "sensor", DOMAIN, f"{entry.entry_id}_temp", config_entry=entry,
        suggested_object_id="my_temperature")
    assert existing.device_id is None
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    updated = registry.async_get(existing.entity_id)
    device = dr.async_get(hass).async_get_device({(DOMAIN, entry.entry_id)})
    assert updated.device_id == device.id
    assert updated.unique_id == existing.unique_id
    assert hass.states.get(existing.entity_id).state == "10.0"
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_runtime_failure_and_recovery(hass, entry, fetch):
    assert await hass.config_entries.async_setup(entry.entry_id)
    fetch[0].side_effect = aiohttp.ClientConnectionError
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("sensor.clientraw_temperature").state == (
        "unavailable")
    fetch[0].side_effect = None
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("sensor.clientraw_temperature").state == "10.0"
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_initial_failure_retries(hass, entry, fetch):
    fetch[0].side_effect = aiohttp.ClientConnectionError
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    fetch[0].side_effect = None
    assert await hass.config_entries.async_reload(entry.entry_id)
    assert entry.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_single_polling_loop_and_unload(hass, entry, fetch, freezer):
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_start()
    await hass.async_block_till_done()
    assert fetch[0].await_count == 1
    coordinator = entry.runtime_data
    freezer.tick(timedelta(minutes=15, seconds=1))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert fetch[0].await_count == 2
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert not coordinator.async_update_listeners()
    freezer.tick(timedelta(minutes=30))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert fetch[0].await_count == 2


async def test_options_real_reload_changes_interval(hass, entry, fetch):
    assert await hass.config_entries.async_setup(entry.entry_id)
    old = entry.runtime_data
    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"interval": 3, "monitored_conditions": ["temp"]})
    await hass.async_block_till_done()
    assert not old.async_update_listeners()
    assert entry.runtime_data is not old
    assert entry.runtime_data.update_interval == timedelta(minutes=3)
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_legacy_entity_id_migration(hass, entry, fetch):
    registry = er.async_get(hass)
    legacy = registry.async_get_or_create(
        "sensor", DOMAIN, slugify("sensor.clientraw_temp"),
        suggested_object_id="my_custom_temperature")
    registry.async_update_entity(
        legacy.entity_id, name="My custom label", icon="mdi:star")
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, "legacy_name": "clientraw"})
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    migrated = registry.async_get(legacy.entity_id)
    assert migrated.unique_id == f"{entry.entry_id}_temp"
    assert migrated.config_entry_id == entry.entry_id
    assert migrated.name == "My custom label"
    assert migrated.icon == "mdi:star"
    device = dr.async_get(hass).async_get_device({(DOMAIN, entry.entry_id)})
    assert migrated.device_id == device.id
    assert "legacy_name" not in entry.data
    assert hass.states.get(legacy.entity_id).state == "10.0"
    assert await hass.config_entries.async_reload(entry.entry_id)
    assert registry.async_get(legacy.entity_id).unique_id == migrated.unique_id
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_migration_does_not_steal_entities(hass, entry, fetch):
    owner = MockConfigEntry(domain=DOMAIN, data={})
    owner.add_to_hass(hass)
    registry = er.async_get(hass)
    legacy = registry.async_get_or_create(
        "sensor", DOMAIN, slugify("sensor.clientraw_temp"),
        config_entry=owner)
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, "legacy_name": "clientraw"})
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert registry.async_get(
        legacy.entity_id).config_entry_id == owner.entry_id
    assert ir.async_get(hass).async_get_issue(
        DOMAIN, f"migration_conflict_{entry.entry_id}") is not None


async def test_multiple_stations_same_name(hass, entry, fetch):
    other_url = entry.data["url"] + "?station=2"
    other = MockConfigEntry(
        domain=DOMAIN, unique_id=endpoint_id(other_url),
        data={**entry.data, "url": other_url})
    other.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert other.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.clientraw_temperature") is not None
    assert hass.states.get("sensor.clientraw_temperature_2") is not None
    assert entry.runtime_data is not other.runtime_data
    assert fetch[0].await_count == 2
    devices = dr.async_get(hass)
    first = devices.async_get_device({(DOMAIN, entry.entry_id)})
    second = devices.async_get_device({(DOMAIN, other.entry_id)})
    assert first is not None and second is not None
    assert first.id != second.id
    registry = er.async_get(hass)
    assert registry.async_get(
        "sensor.clientraw_temperature").device_id == first.id
    assert registry.async_get(
        "sensor.clientraw_temperature_2").device_id == second.id
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert await hass.config_entries.async_unload(other.entry_id)


async def test_yaml_bridge_end_to_end(hass, fetch):
    config = {
        "sensor": [{
            "platform": DOMAIN, "url": "https://example.com/clientraw.txt",
            "name": "Imported", "interval": 10,
            "monitored_conditions": ["temp", "wind_dir"],
        }],
    }
    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.data["interval"] == 10
    assert entry.data["monitored_conditions"] == ["temp", "wind_dir"]
    assert hass.states.get("sensor.imported_temperature") is not None
    token = import_id(entry.data["url"], "Imported")
    assert ir.async_get(hass).async_get_issue(
        DOMAIN, f"remove_yaml_{token}") is not None
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_empty_selection_creates_no_entities(hass, entry, fetch):
    hass.config_entries.async_update_entry(
        entry, options={"monitored_conditions": []})
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    assert not er.async_entries_for_config_entry(registry, entry.entry_id)
    assert await hass.config_entries.async_unload(entry.entry_id)
