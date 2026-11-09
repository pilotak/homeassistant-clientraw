"""Registry migration, polling, error recovery, and lifecycle coverage."""

from datetime import timedelta
import aiohttp
import pytest

from homeassistant.config_entries import ConfigEntryState
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
        assert hass.states.get(entity.entity_id).state != "unavailable"
        assert entity.device_id == device.id
    temperature = hass.states.get("sensor.clientraw_temperature")
    assert float(temperature.state) == (50 if imperial else 10)
    assert temperature.attributes["unit_of_measurement"] == (
        "°F" if imperial else "°C")
    pressure = hass.states.get("sensor.clientraw_pressure")
    assert float(pressure.state) == (29.92 if imperial else 1013.25)
    assert pressure.attributes["unit_of_measurement"] == (
        "inHg" if imperial else "hPa")
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
