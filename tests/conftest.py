"""Clientraw fixtures using the real Home Assistant test harness."""

from unittest.mock import patch

import pytest

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.clientraw.client import endpoint_id
from custom_components.clientraw.const import DOMAIN

URL = "https://example.com/clientraw.txt"


@pytest.fixture(autouse=True)
def custom_integrations(enable_custom_integrations):
    """Enable loading this repository's integration."""


@pytest.fixture
def payload():
    """A full frame with valid readings and version framing."""
    fields = ["0"] * 165
    fields[0] = "12345"
    fields[4] = "10"
    fields[5] = "55"
    fields[6] = "1013.25"
    fields[32] = "Test_Station-15:12:24"
    fields[74] = "09/11/2026"
    return fields + ["!!C10.37S!!"]


@pytest.fixture
def entry(hass):
    config = MockConfigEntry(
        domain=DOMAIN, title="clientraw", unique_id=endpoint_id(URL),
        data={
            "url": URL, "name": "clientraw", "interval": 15,
            "monitored_conditions": ["temp", "humidity"],
        },
    )
    config.add_to_hass(hass)
    return config


@pytest.fixture
def fetch(payload):
    with patch(
        "custom_components.clientraw.coordinator.async_fetch",
        return_value=payload,
    ) as runtime, patch(
        "custom_components.clientraw.config_flow.async_fetch",
        return_value=payload,
    ) as flow:
        yield runtime, flow
