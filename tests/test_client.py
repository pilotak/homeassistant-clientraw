"""Regression coverage for every existing field and conversion."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from custom_components.clientraw.client import (
    InvalidClientraw, async_fetch, detect_conditions, endpoint_id,
    normalize_url, parse_condition, parse_payload,
)
from custom_components.clientraw.const import CONDITIONS

FIELDS = {
    "dewpoint": 72, "heat_index": 112, "temp": 4, "temp_indoor": 12,
    "temp_day_max": 46, "temp_day_min": 47, "humidex": 44,
    "wind_degrees": 3, "wind_dir": 3, "wind_gust_hour": 133,
    "wind_gust_day": 71, "wind_speed": 2, "wind_speed_average": 1,
    "wind_speed_avg_10min": 158, "symbol": 48, "daily_rain": 7,
    "yesterday_rain": 19, "monthly_rain": 8, "yearly_rain": 9,
    "rain_rate": 10, "pressure": 6, "humidity": 5, "humidity_indoor": 13,
    "humidity_max": 163, "humidity_min": 164, "cloud_height": 73,
    "forecast": 15, "station": 32, "date": 74, "wind_chill": 44,
    "wind_chill_max": 77, "wind_chill_min": 78, "vp_solar": 127,
    "uv_index": 79, "apparent_temp": 130, "apparent_temp_min": 137,
    "apparent_temp_max": 136,
}


@pytest.mark.parametrize("key,index", FIELDS.items())
def test_mapping_and_detection(payload, key, index):
    assert set(FIELDS) == set(CONDITIONS)
    assert CONDITIONS[key].index == index
    payload[index] = "0"
    assert key in detect_conditions(payload)
    assert parse_condition(payload, key) is not None
    payload[index] = "---"
    assert key not in detect_conditions(payload)
    assert parse_condition(payload, key) is None


@pytest.mark.parametrize("key", CONDITIONS)
@pytest.mark.parametrize("raw", ["-", "--", "---", "nan", "inf", "bad"])
def test_bad_readings(payload, key, raw):
    if CONDITIONS[key].kind == "text" and raw not in ("-", "--", "---"):
        return
    payload[CONDITIONS[key].index] = raw
    assert parse_condition(payload, key) is None
    assert key not in detect_conditions(payload)


@pytest.mark.parametrize("key,raw,metric,imperial", [
    ("temp", "-5", -5, 23),
    ("dewpoint", "0", 0, 32),
    ("wind_speed", "10", 18.52, 11.51),
    ("daily_rain", "25.4", 25.4, 1),
    ("pressure", "1013.25", 1013.25, 29.92),
    ("cloud_height", "100", 100, 328.08),
    ("vp_solar", "100", 100, 31.7),
    ("humidity", "55", 55, 55),
    ("wind_dir", "270", "W", "W"),
    ("forecast", "8", "heavy rain", "heavy rain"),
    ("symbol", "2", 2, 2),
    ("station", "Test_Station", "Test_Station", "Test_Station"),
    ("date", "09/11/2026", "09/11/2026", "09/11/2026"),
    ("apparent_temp", "10.123", 10.123, 10.123),
])
def test_existing_conversions(payload, key, raw, metric, imperial):
    payload[CONDITIONS[key].index] = raw
    assert parse_condition(payload, key) == metric
    assert parse_condition(payload, key, False) == imperial


def test_short_payload_and_whitespace(payload):
    short = payload[:114] + [payload[-1]]
    parsed = parse_payload("\n\t".join(short) + "\n")
    assert parse_condition(parsed, "temp") == 10
    assert parse_condition(parsed, "humidity_min") is None
    assert "vp_solar" not in detect_conditions(parsed)


def test_optional_version_marker(payload):
    parsed = parse_payload(" ".join(payload[:-1]))
    assert parse_condition(parsed, "humidity_min") == 0
    assert "humidity_min" in detect_conditions(parsed)


@pytest.mark.parametrize("text", [
    "", "<html>error</html>", " ".join(["0"] * 166),
    "12345 1 2 !!C10!!",
])
def test_invalid_payload(text):
    with pytest.raises(InvalidClientraw):
        parse_payload(text)


def test_unknown_forecast_and_fractional_symbol(payload):
    payload[15] = "-1"
    payload[48] = "1.5"
    assert parse_condition(payload, "forecast") == "unknown"
    assert "forecast" not in detect_conditions(payload)
    assert parse_condition(payload, "symbol") is None


def test_conversion_overflow_is_unavailable(payload):
    payload[4] = "1.7e308"
    assert parse_condition(payload, "temp", False) is None


def test_url_identity():
    assert normalize_url("HTTPS://EXAMPLE.COM:443/clientraw.txt#x") == (
        "https://example.com/clientraw.txt")
    assert endpoint_id("https://example.com/clientraw.txt?a=1") != endpoint_id(
        "https://example.com/clientraw.txt?a=2")
    assert normalize_url("http://user:pass@EXAMPLE.COM/x") == (
        "http://user:pass@example.com/x")
    assert normalize_url("http://[::1]:8080/x") == "http://[::1]:8080/x"
    with pytest.raises(ValueError):
        normalize_url("ftp://example.com/clientraw.txt")


async def test_real_fetch(hass, aioclient_mock, payload):
    url = "https://example.com/clientraw.txt"
    aioclient_mock.get(url, text=" ".join(payload))
    assert await async_fetch(hass, url) == payload


@pytest.mark.parametrize("status", [404, 500])
async def test_http_errors(hass, aioclient_mock, status):
    url = "https://example.com/clientraw.txt"
    aioclient_mock.get(url, status=status)
    with pytest.raises(aiohttp.ClientResponseError):
        await async_fetch(hass, url)


async def test_timeout_covers_response_body(hass):
    response = MagicMock()
    response.text = AsyncMock(side_effect=asyncio.TimeoutError)
    request = MagicMock()
    request.__aenter__ = AsyncMock(return_value=response)
    request.__aexit__ = AsyncMock(return_value=False)
    session = MagicMock()
    session.get.return_value = request
    with patch("custom_components.clientraw.client.async_get_clientsession",
               return_value=session), pytest.raises(TimeoutError):
        await async_fetch(hass, "https://example.com/clientraw.txt")
    request.__aexit__.assert_awaited_once()
