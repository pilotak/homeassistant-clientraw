"""UI setup, exact YAML imports, and later editing."""

from unittest.mock import patch

import aiohttp
import pytest

from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_RECONFIGURE
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.clientraw.client import (
    InvalidClientraw, endpoint_id, import_id,
)
from custom_components.clientraw.const import CONDITIONS, DOMAIN

URL = "https://example.com/clientraw.txt"
SETTINGS = {"url": URL, "name": "clientraw", "interval": 15}


@pytest.mark.parametrize("source", ["user", SOURCE_RECONFIGURE])
async def test_timestamp_settings_and_detection(
    hass, entry, fetch, payload, source,
):
    payload[74] = "2026-11-09"
    timestamp = {"date_format": "iso", "station_timezone": "Europe/Oslo"}
    if source == "user":
        settings = {**SETTINGS, "url": URL + "?new", **timestamp}
        context = {"source": source}
    else:
        settings = {
            "url": URL, "name": "clientraw", "redetect": True, **timestamp}
        context = {"source": source, "entry_id": entry.entry_id}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context=context, data=settings)
    assert result["step_id"] == "conditions"
    assert "last_updated" in defaults(result)["monitored_conditions"]
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"monitored_conditions": ["last_updated"]})
    await hass.async_block_till_done()
    configured = result["result"] if source == "user" else entry
    assert configured.data["date_format"] == "iso"
    assert configured.data["station_timezone"] == "Europe/Oslo"
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{configured.entry_id}_last_updated")
    assert hass.states.get(entity_id).state == "2026-11-09T14:12:24+00:00"
    flow = await hass.config_entries.options.async_init(configured.entry_id)
    flow = await hass.config_entries.options.async_configure(flow["flow_id"], {
        "interval": 15, "monitored_conditions": ["last_updated"],
        "redetect": True,
    })
    assert "last_updated" in defaults(flow)["monitored_conditions"]
    assert await hass.config_entries.async_unload(configured.entry_id)


@pytest.mark.parametrize("source", ["user", SOURCE_RECONFIGURE])
async def test_invalid_timezone_preserves_settings(hass, entry, fetch, source):
    context = {"source": source}
    if source == SOURCE_RECONFIGURE:
        context["entry_id"] = entry.entry_id
    before = dict(entry.data)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context=context, data={
            **SETTINGS, "station_timezone": "Invalid/Timezone",
            "date_format": "mdy",
        })
    assert result["errors"] == {"base": "invalid_settings"}
    assert defaults(result)["station_timezone"] == "Invalid/Timezone"
    assert defaults(result)["date_format"] == "mdy"
    assert entry.data == before
    fetch[1].assert_not_awaited()


def defaults(result):
    return {
        key.schema: key.default()
        for key in result["data_schema"].schema
        if callable(key.default)
    }


@pytest.mark.parametrize("selected", [
    ["temp", "humidity_min"], [], list(CONDITIONS),
])
async def test_user_flow(hass, fetch, payload, selected):
    payload[164] = "---"
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"})
    assert result["step_id"] == "user"
    assert defaults(result)["interval"] == 15
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], SETTINGS)
    assert result["step_id"] == "conditions"
    prefilled = defaults(result)["monitored_conditions"]
    assert "temp" in prefilled
    assert "humidity_min" not in prefilled
    checklist = next(iter(result["data_schema"].schema.values()))
    assert {item["value"] for item in checklist.config["options"]} == (
        set(CONDITIONS))
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"monitored_conditions": selected})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        **SETTINGS, "monitored_conditions": selected,
        "date_format": "dmy", "station_timezone": hass.config.time_zone,
    }
    await hass.async_block_till_done()
    fetch[1].assert_awaited_once()
    assert await hass.config_entries.async_unload(result["result"].entry_id)


@pytest.mark.parametrize("error,key", [
    (TimeoutError(), "cannot_connect"),
    (aiohttp.ClientConnectionError(), "cannot_connect"),
    (InvalidClientraw(), "invalid_clientraw"),
])
async def test_setup_errors(hass, fetch, error, key):
    fetch[1].side_effect = error
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data=SETTINGS)
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": key}
    assert defaults(result)["url"] == URL
    assert not hass.config_entries.async_entries(DOMAIN)


@pytest.mark.parametrize("changes", [
    {"url": "ftp://example.com/x"}, {"name": "   "}, {"interval": 0},
    {"interval": 60},
])
async def test_invalid_settings(hass, fetch, changes):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data={**SETTINGS, **changes})
    assert result["errors"] == {"base": "invalid_settings"}
    fetch[1].assert_not_awaited()


async def test_duplicate_endpoint(hass, entry, fetch):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"},
        data={**SETTINGS, "url": "HTTPS://EXAMPLE.COM:443/clientraw.txt#x"})
    assert result["reason"] == "already_configured"
    fetch[1].assert_not_awaited()


async def test_invalid_conditions(hass, fetch):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data=SETTINGS)
    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(
            result["flow_id"], {"monitored_conditions": ["not_a_sensor"]})


async def test_import_offline_and_repeat_preserves_ui(hass, fetch):
    fetch[0].side_effect = aiohttp.ClientConnectionError()
    data = {**SETTINGS, "monitored_conditions": []}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=data)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    imported = result["result"]
    assert imported.data["monitored_conditions"] == []
    assert imported.data["yaml_import_id"] == import_id(URL, "clientraw")
    fetch[1].assert_not_awaited()
    await hass.async_block_till_done()
    updated = {**imported.data, "name": "edited", "url": URL + "?new"}
    hass.config_entries.async_update_entry(
        imported, data=updated, unique_id=endpoint_id(updated["url"]),
        options={"monitored_conditions": ["temp"], "interval": 3})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=data)
    assert result["reason"] == "already_imported"
    assert imported.data["name"] == "edited"
    assert imported.options["monitored_conditions"] == ["temp"]
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_import_endpoint_conflict(hass, entry, fetch):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT},
        data={**SETTINGS, "monitored_conditions": ["temp"]})
    assert result["reason"] == "import_conflict"
    assert ir.async_get(hass).async_get_issue(
        DOMAIN, f"import_conflict_{import_id(URL, 'clientraw')}") is not None
    assert entry.data["monitored_conditions"] == ["temp", "humidity"]


async def test_conflicting_yaml_blocks_are_not_silently_ignored(hass, fetch):
    data = {**SETTINGS, "monitored_conditions": ["temp"]}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=data)
    await hass.async_block_till_done()
    imported = result["result"]
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT},
        data={**data, "monitored_conditions": ["humidity"]})
    assert result["reason"] == "import_conflict"
    assert imported.data["monitored_conditions"] == ["temp"]
    assert await hass.config_entries.async_unload(imported.entry_id)


@pytest.mark.parametrize("selected", [[], ["humidity_min"]])
async def test_options_save_and_reload_once(hass, entry, fetch, selected):
    assert await hass.config_entries.async_setup(entry.entry_id)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert defaults(result)["monitored_conditions"] == ["temp", "humidity"]
    with patch.object(hass.config_entries, "async_reload",
                      return_value=True) as reload:
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {
                "interval": 1, "monitored_conditions": selected,
                "redetect": False,
            })
        await hass.async_block_till_done()
        reload.assert_awaited_once_with(entry.entry_id)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["monitored_conditions"] == selected
    assert entry.options["interval"] == 1
    fetch[1].assert_not_awaited()
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_options_redetect_review(hass, entry, fetch, payload):
    payload[164] = "---"
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {
            "interval": 59, "monitored_conditions": ["temp"], "redetect": True,
        })
    assert result["step_id"] == "conditions"
    assert "humidity_min" not in defaults(result)["monitored_conditions"]
    assert entry.options == {}
    with patch.object(hass.config_entries, "async_reload", return_value=True):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"monitored_conditions": ["humidity_min"]})
        await hass.async_block_till_done()
    assert entry.options == {
        "interval": 59, "monitored_conditions": ["humidity_min"]}
    fetch[1].assert_awaited_once()


async def test_options_redetect_failure(hass, entry, fetch):
    fetch[1].side_effect = TimeoutError
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {
            "interval": 3, "monitored_conditions": [], "redetect": True,
        })
    assert result["errors"] == {"base": "cannot_connect"}
    assert defaults(result)["monitored_conditions"] == []
    assert entry.options == {}


@pytest.mark.parametrize("redetect", [True, False])
async def test_reconfigure_preserves_identity(hass, entry, fetch, redetect):
    assert await hass.config_entries.async_setup(entry.entry_id)
    devices = dr.async_get(hass)
    original_device = devices.async_get_device({(DOMAIN, entry.entry_id)})
    assert original_device is not None
    before = hass.states.get("sensor.clientraw_temperature")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_RECONFIGURE,
                         "entry_id": entry.entry_id})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {
            "url": URL + "?new", "name": "New station", "redetect": redetect,
        })
    if redetect:
        assert result["step_id"] == "conditions"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"monitored_conditions": ["temp"]})
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    assert entry.data["url"] == URL + "?new"
    assert entry.title == "New station"
    after = hass.states.get(before.entity_id)
    assert after is not None
    assert after.attributes["friendly_name"] == "New station Temperature"
    device = devices.async_get_device({(DOMAIN, entry.entry_id)})
    assert device.id == original_device.id
    assert device.name == "New station"
    assert entry.options.get("monitored_conditions") == (
        ["temp"] if redetect else None)
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_reconfigure_duplicate(hass, entry, fetch):
    other_url = "https://example.com/other.txt"
    other = MockConfigEntry(
        domain=DOMAIN, unique_id=endpoint_id(other_url),
        data={**SETTINGS, "url": other_url, "monitored_conditions": []})
    other.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_RECONFIGURE,
                         "entry_id": entry.entry_id},
        data={"url": other_url, "name": "Other"})
    assert result["reason"] == "already_configured"
    assert entry.data["url"] == URL


@pytest.mark.parametrize("error,key", [
    (TimeoutError(), "cannot_connect"),
    (InvalidClientraw(), "invalid_clientraw"),
])
async def test_reconfigure_failure_does_not_change_settings(
    hass, entry, fetch, error, key,
):
    fetch[1].side_effect = error
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_RECONFIGURE,
                         "entry_id": entry.entry_id},
        data={"url": URL + "?new", "name": "Changed"})
    assert result["errors"] == {"base": key}
    assert entry.data["url"] == URL
    assert entry.data["name"] == "clientraw"


async def test_options_invalid_payload_keeps_selection(hass, entry, fetch):
    fetch[1].side_effect = InvalidClientraw()
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {
            "interval": 10, "monitored_conditions": ["temp"],
            "redetect": True,
        })
    assert result["errors"] == {"base": "invalid_clientraw"}
    assert entry.options == {}
    assert defaults(result)["monitored_conditions"] == ["temp"]


async def test_setup_conditions_race_with_existing_entry(hass, fetch):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data=SETTINGS)
    competing = MockConfigEntry(
        domain=DOMAIN, unique_id=endpoint_id(URL),
        data={**SETTINGS, "monitored_conditions": []})
    competing.add_to_hass(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"monitored_conditions": ["temp"]})
    assert result["reason"] == "already_configured"
