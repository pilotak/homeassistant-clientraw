"""Fetching and parsing shared by configuration and runtime."""

import asyncio
from hashlib import sha256
import logging
import math
from urllib.parse import urlsplit, urlunsplit

import aiohttp

from homeassistant.const import (
    STATE_UNKNOWN, UnitOfLength, UnitOfPressure, UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util.unit_conversion import (
    DistanceConverter, PressureConverter, TemperatureConverter,
)

from .const import CONDITIONS, DIRECTIONS, FORECASTS, MISSING_VALUES

_LOGGER = logging.getLogger(__name__)


class InvalidClientraw(ValueError):
    """The endpoint did not return a clientraw payload."""


def normalize_url(url: str) -> str:
    """Normalize endpoint identity without changing paths or query strings."""
    parts = urlsplit(url.strip())
    if parts.scheme.lower() not in ("http", "https") or not parts.hostname:
        raise ValueError("Enter an HTTP(S) URL")
    port = parts.port
    host = parts.hostname.lower()
    if ":" in host:
        host = f"[{host}]"
    if port and (parts.scheme.lower(), port) not in (
            ("http", 80), ("https", 443)):
        host = f"{host}:{port}"
    if "@" in parts.netloc:
        host = f"{parts.netloc.rsplit('@', 1)[0]}@{host}"
    return urlunsplit((parts.scheme.lower(), host, parts.path or "/",
                       parts.query, ""))


def endpoint_id(url: str) -> str:
    """Return a non-sensitive endpoint identity."""
    return sha256(normalize_url(url).encode()).hexdigest()


def import_id(url: str, name: str) -> str:
    """Identify the original YAML block even after UI reconfiguration."""
    return sha256(f"{normalize_url(url)}\0{name}".encode()).hexdigest()


def import_signature(url: str, name: str, interval: int,
                     selected: list[str]) -> str:
    """Distinguish conflicting YAML blocks from unchanged import retries."""
    settings = "\0".join([
        import_id(url, name), str(interval), *sorted(selected)])
    return sha256(settings.encode()).hexdigest()


def parse_payload(text: str) -> list[str]:
    """Validate framing without requiring newer fields or version markers."""
    fields = text.split()
    if len(fields) < 115 or fields[0] != "12345":
        raise InvalidClientraw("The response is not a valid clientraw file")
    return fields


async def async_fetch(hass: HomeAssistant, url: str) -> list[str]:
    """Fetch a clientraw file, including its body, within one timeout."""
    session = async_get_clientsession(hass)
    async with asyncio.timeout(10):
        async with session.get(url) as response:
            response.raise_for_status()
            return parse_payload(await response.text())


def parse_condition(fields: list[str], key: str,
                    metric: bool = True) -> str | float | int | None:
    """Return a reading, or None for a missing/invalid individual field."""
    condition = CONDITIONS[key]
    if condition.index >= len(fields):
        return None
    raw = fields[condition.index]
    if raw in MISSING_VALUES or (raw.startswith("!!") and raw.endswith("!!")):
        return None
    if condition.kind == "text":
        return raw
    try:
        value = float(raw)
        if not math.isfinite(value):
            _LOGGER.debug("Invalid numeric reading for Clientraw %s", key)
            return None
        if (condition.kind in ("integer", "forecast")
                and not value.is_integer()):
            _LOGGER.debug("Invalid integer reading for Clientraw %s", key)
            return None
    except ValueError:
        _LOGGER.debug("Invalid numeric reading for Clientraw %s", key)
        return None
    match condition.kind:
        case "integer":
            return int(value)
        case "forecast":
            return (FORECASTS[int(value)] if 0 <= value < len(FORECASTS)
                    else STATE_UNKNOWN)
        case "direction":
            return DIRECTIONS[int(value / 22.5 + .5) % 16]
        case "number":
            return value
        case "temperature":
            value = value if metric else TemperatureConverter.convert(
                value, UnitOfTemperature.CELSIUS,
                UnitOfTemperature.FAHRENHEIT)
        case "wind":
            value *= 1.85166 if metric else 1.1507794
        case "rain":
            value = value if metric else value * 0.0393700787
        case "pressure":
            value = value if metric else PressureConverter.convert(
                value, UnitOfPressure.HPA, UnitOfPressure.INHG)
        case "height":
            value = value if metric else DistanceConverter.convert(
                value, UnitOfLength.METERS, UnitOfLength.FEET)
        case "solar":
            value = value if metric else value * 0.3169983306
        case _:
            raise ValueError(f"Unknown condition conversion: {condition.kind}")
    if not math.isfinite(value):
        _LOGGER.debug("Invalid converted reading for Clientraw %s", key)
        return None
    return round(value, 2)


def detect_conditions(fields: list[str]) -> list[str]:
    """Suggest conditions without claiming to detect hardware capabilities."""
    return [key for key in CONDITIONS
            if parse_condition(fields, key) not in (None, STATE_UNKNOWN)]


FETCH_ERRORS = (
    aiohttp.ClientError, TimeoutError, UnicodeError, InvalidClientraw,
)
