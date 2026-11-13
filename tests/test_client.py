"""Regression coverage for every existing field and conversion."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import aiohttp
import pytest

from custom_components.clientraw.client import (
    InvalidClientraw, async_fetch, detect_conditions, endpoint_id,
    normalize_url, parse_condition, parse_payload,
)
from custom_components.clientraw.const import CONDITIONS

FIELDS = {
    "dewpoint": 72, "heat_index": 112, "temp": 4, "temp_indoor": 12,
    "temp_day_max": 46, "temp_day_min": 47, "humidex": 45,
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
    "last_updated": 29,
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
    if (CONDITIONS[key].kind in ("text", "station")
            and raw not in ("-", "--", "---")):
        return
    payload[CONDITIONS[key].index] = raw
    assert parse_condition(payload, key) is None
    assert key not in detect_conditions(payload)


@pytest.mark.parametrize("key,raw,expected", [
    ("temp", "-5", -5),
    ("dewpoint", "0", 0),
    ("wind_speed", "10", 10),
    ("daily_rain", "25.4", 25.4),
    ("rain_rate", "0.1", 6),
    ("pressure", "1013.25", 1013.25),
    ("cloud_height", "100", 100),
    ("vp_solar", "100", 100),
    ("humidity", "55", 55),
    ("wind_dir", "270", "W"),
    ("forecast", "8", "heavy rain"),
    ("symbol", "2", 2),
    ("station", "Test_Station", "Test_Station"),
    ("station", "TILSKI-15:12:24", "TILSKI"),
    ("station", "My-Station-15:12:24", "My-Station"),
    ("date", "09/11/2026", "09/11/2026"),
    ("apparent_temp", "10.123", 10.123),
    ("apparent_temp_min", "-5", -5),
    ("apparent_temp_max", "0", 0),
])
def test_native_readings(payload, key, raw, expected):
    payload[CONDITIONS[key].index] = raw
    assert parse_condition(payload, key) == expected


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


def test_large_finite_reading_is_not_converted_in_parser(payload):
    payload[4] = "1.7e308"
    assert parse_condition(payload, "temp") == 1.7e308


@pytest.mark.parametrize("date,expected", [
    ("9/11/2026", datetime(2026, 11, 9, 14, 12, 24, tzinfo=timezone.utc)),
    ("9/7/2026", datetime(2026, 7, 9, 13, 12, 24, tzinfo=timezone.utc)),
])
def test_last_updated_uses_feed_date_and_local_timezone(
    payload, date, expected,
):
    payload[32] = "My-Station-15:12:24"
    payload[74] = date
    assert parse_condition(
        payload, "last_updated",
        station_timezone=ZoneInfo("Europe/Oslo")) == expected


@pytest.mark.parametrize("clock,date", [
    (["24", "12", "24"], "9/11/2026"),
    (["15", "60", "24"], "9/11/2026"),
    (["15", "12", "60"], "9/11/2026"),
    (["15.5", "12", "24"], "9/11/2026"),
    (["15junk", "12", "24"], "9/11/2026"),
    (["-", "12", "24"], "9/11/2026"),
    (["15", "12", "24"], "31/2/2026"),
    (["15", "12", "24"], "---"),
])
def test_invalid_last_updated(payload, clock, date):
    payload[29:32], payload[74] = clock, date
    assert parse_condition(payload, "last_updated") is None
    assert "last_updated" not in detect_conditions(payload)


def test_last_updated_midnight_and_missing_date(payload):
    payload[29:32] = ["0", "0", "0"]
    payload[32] = "TILSKI-00:00:00"
    payload[74] = "1/1/2026"
    assert parse_condition(
        payload, "last_updated", station_timezone=ZoneInfo("Europe/Oslo")
    ) == datetime(2025, 12, 31, 23, tzinfo=timezone.utc)
    assert parse_condition(payload[:40], "last_updated") is None


@pytest.mark.parametrize("station", [
    "TILSKI", "TILSKI-01:02:03", "TILSKI-25:12:24", "---",
])
def test_timestamp_is_independent_of_station_label(payload, station):
    payload[32] = station
    assert parse_condition(payload, "last_updated") == datetime(
        2026, 11, 9, 15, 12, 24, tzinfo=timezone.utc)


@pytest.mark.parametrize("format,date,month,day", [
    ("dmy", "9/11/2026", 11, 9),
    ("mdy", "9/11/2026", 9, 11),
    ("iso", "2026-11-09", 11, 9),
    ("mdy", "7/9/2026", 7, 9),
])
def test_explicit_date_format(payload, format, date, month, day):
    payload[74] = date
    assert parse_condition(
        payload, "last_updated", date_format=format) == datetime(
            2026, month, day, 15, 12, 24, tzinfo=timezone.utc)
    assert "last_updated" in detect_conditions(payload, date_format=format)


def test_wrong_date_format_is_not_guessed(payload):
    payload[74] = "11/30/2026"
    assert parse_condition(
        payload, "last_updated", date_format="dmy") is None
    assert parse_condition(
        payload, "last_updated", date_format="mdy") == datetime(
            2026, 11, 30, 15, 12, 24, tzinfo=timezone.utc)


@pytest.mark.parametrize("date,clock", [
    ("29/3/2026", ["2", "30", "0"]),
    ("25/10/2026", ["2", "30", "0"]),
])
def test_dst_transition_is_not_guessed(payload, date, clock):
    payload[74], payload[29:32] = date, clock
    assert parse_condition(
        payload, "last_updated", ZoneInfo("Europe/Oslo")) is None


def test_source_corrections_are_independent(payload):
    payload[44], payload[45] = "-5", "15"
    assert parse_condition(payload, "wind_chill") == -5
    assert parse_condition(payload, "humidex") == 15
    payload[10] = "1.7e308"
    assert parse_condition(payload, "rain_rate") is None


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
