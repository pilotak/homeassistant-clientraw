"""Fetching and parsing shared by configuration and runtime."""

import asyncio
from datetime import datetime, timezone, tzinfo
from hashlib import sha256
import logging
import math
import re
from urllib.parse import urlsplit, urlunsplit

import aiohttp

from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .const import (
    CONDITIONS, DATE_FORMATS, DEFAULT_DATE_FORMAT, DIRECTIONS, FORECASTS,
    MISSING_VALUES,
)

_LOGGER = logging.getLogger(__name__)
STATION_TIME = re.compile(
    r"(?P<name>.+)-(?P<time>[0-9]{2}:[0-9]{2}:[0-9]{2})")


def split_station(raw: str) -> tuple[str, str | None]:
    """Split only a trailing valid clock, preserving hyphens in names."""
    if match := STATION_TIME.fullmatch(raw):
        try:
            datetime.strptime(match["time"], "%H:%M:%S")
        except ValueError:
            _LOGGER.debug("Invalid clock in Clientraw station field")
        else:
            return match["name"], match["time"]
    return raw, None


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
                    station_timezone: tzinfo = timezone.utc,
                    date_format: str = DEFAULT_DATE_FORMAT,
                    ) -> str | float | int | datetime | None:
    """Return a reading, or None for a missing/invalid individual field."""
    condition = CONDITIONS[key]
    if condition.index >= len(fields):
        return None
    raw = fields[condition.index]
    if raw in MISSING_VALUES or (raw.startswith("!!") and raw.endswith("!!")):
        return None
    if condition.kind == "text":
        return raw
    if condition.kind == "station":
        return split_station(raw)[0]
    if condition.kind == "timestamp":
        date_index = CONDITIONS["date"].index
        if date_index >= len(fields):
            _LOGGER.debug("Missing date or time for Clientraw last updated")
            return None
        try:
            clock_fields = fields[29:32]
            if len(clock_fields) != 3 or not all(
                    re.fullmatch(r"[0-9]{1,2}", part)
                    for part in clock_fields):
                raise ValueError("Invalid station clock fields")
            hour, minute, second = map(int, clock_fields)
            updated = datetime.strptime(
                fields[date_index], DATE_FORMATS[date_format]).replace(
                    hour=hour, minute=minute, second=second)
        except ValueError:
            _LOGGER.debug("Invalid date or clock for Clientraw last updated")
            return None
        candidates = {
            aware.astimezone(timezone.utc)
            for fold in (0, 1)
            if (aware := updated.replace(
                tzinfo=station_timezone, fold=fold)).astimezone(
                    timezone.utc).astimezone(
                        station_timezone).replace(tzinfo=None) == updated
        }
        if len(candidates) != 1:
            _LOGGER.debug("Ambiguous or nonexistent Clientraw station time")
            return None
        return candidates.pop()
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
        case "rain_rate":
            value *= 60
            if not math.isfinite(value):
                _LOGGER.debug("Invalid normalized Clientraw rain rate")
                return None
            return value
        case ("number" | "humidity" | "temperature" | "wind" | "rain"
              | "pressure" | "height" | "solar"):
            return value
        case _:
            raise ValueError(f"Unknown condition conversion: {condition.kind}")


def detect_conditions(fields: list[str],
                      station_timezone: tzinfo = timezone.utc,
                      date_format: str = DEFAULT_DATE_FORMAT) -> list[str]:
    """Suggest conditions without claiming to detect hardware capabilities."""
    return [key for key in CONDITIONS
            if parse_condition(fields, key, station_timezone, date_format)
            not in (None, STATE_UNKNOWN)]


FETCH_ERRORS = (
    aiohttp.ClientError, TimeoutError, UnicodeError, InvalidClientraw,
)
