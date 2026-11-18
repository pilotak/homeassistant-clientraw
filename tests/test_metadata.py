"""Verify the shipped flow labels and metadata using Home Assistant."""

import json
from pathlib import Path

from homeassistant.helpers.translation import async_get_translations

from custom_components.clientraw.const import CONDITIONS, DOMAIN

INTEGRATION = (
    Path(__file__).parent.parent / "custom_components" / DOMAIN)


async def test_shipped_translations(hass):
    strings = json.loads((INTEGRATION / "strings.json").read_text())
    english = json.loads(
        (INTEGRATION / "translations" / "en.json").read_text())
    assert strings == english
    for category, expected in (
        ("config", "step.user.title"),
        ("options", "step.init.title"),
        ("issues", "remove_yaml.title"),
    ):
        translations = await async_get_translations(
            hass, "en", category, {DOMAIN})
        assert f"component.{DOMAIN}.{category}.{expected}" in translations


def test_manifest_enables_native_setup():
    manifest = json.loads((INTEGRATION / "manifest.json").read_text())
    assert manifest["domain"] == DOMAIN
    assert manifest["config_flow"] is True
    assert manifest["iot_class"] == "cloud_polling"
    assert CONDITIONS["dewpoint"].icon == "mdi:weather-fog"
