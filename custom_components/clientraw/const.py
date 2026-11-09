"""Shared Clientraw settings and field definitions."""

from dataclasses import dataclass

from homeassistant.const import (
    DEGREE, PERCENTAGE, UV_INDEX, UnitOfIrradiance, UnitOfLength,
    UnitOfPressure, UnitOfSpeed, UnitOfTemperature,
)

DOMAIN = "clientraw"
CONF_INTERVAL = "interval"
CONF_MONITORED_CONDITIONS = "monitored_conditions"
CONF_IMPORT_ID = "yaml_import_id"
CONF_IMPORT_SIGNATURE = "yaml_import_signature"
CONF_LEGACY_NAME = "legacy_name"
DEFAULT_NAME = "clientraw"
DEFAULT_INTERVAL = 15
MISSING_VALUES = {"-", "--", "---"}


@dataclass(frozen=True)
class Condition:
    """A condition's existing label, field, units, and value conversion."""

    name: str
    index: int
    kind: str
    metric: str | None = None
    imperial: str | None = None
    icon: str = "mdi:thermometer"


def temperature(name: str, index: int,
                icon: str = "mdi:thermometer") -> Condition:
    """Describe a temperature field."""
    return Condition(name, index, "temperature", UnitOfTemperature.CELSIUS,
                     UnitOfTemperature.FAHRENHEIT, icon)


def wind(name: str, index: int, icon: str) -> Condition:
    """Describe a wind speed field."""
    return Condition(name, index, "wind", UnitOfSpeed.KILOMETERS_PER_HOUR,
                     UnitOfSpeed.MILES_PER_HOUR, icon)


def rain(name: str, index: int) -> Condition:
    """Describe a rain field."""
    return Condition(name, index, "rain", UnitOfLength.MILLIMETERS,
                     UnitOfLength.INCHES, "mdi:weather-rainy")


def humidity(name: str, index: int) -> Condition:
    """Describe a humidity field."""
    return Condition(name, index, "number", PERCENTAGE, PERCENTAGE,
                     "mdi:water-percent")


CONDITIONS = {
    "dewpoint": temperature("Dewpoint", 72, "mdi:weather-fog"),
    "heat_index": temperature("Heat index", 112),
    "temp": temperature("Temperature", 4),
    "temp_indoor": temperature("Indoor Temperature", 12),
    "temp_day_max": temperature("Today MAX temperature", 46),
    "temp_day_min": temperature("Today MIN temperature", 47),
    "humidex": temperature("Humidex", 44),
    "wind_degrees": Condition("Wind Degrees", 3, "number", DEGREE, DEGREE,
                              "mdi:subdirectory-arrow-right"),
    "wind_dir": Condition("Wind Direction", 3, "direction",
                          icon="mdi:subdirectory-arrow-right"),
    "wind_gust_hour": wind("Wind Gust last hour", 133, "mdi:weather-windy"),
    "wind_gust_day": wind("Wind Gust last day", 71, "mdi:weather-windy"),
    "wind_speed": wind("Wind Speed", 2, "mdi:weather-windy-variant"),
    "wind_speed_average": wind("60s Avg Wind Speed", 1,
                               "mdi:weather-windy-variant"),
    "wind_speed_avg_10min": wind("10 Min Avg Wind Speed", 158,
                                 "mdi:weather-windy-variant"),
    "symbol": Condition("Symbol", 48, "integer", icon="mdi:triangle-outline"),
    "daily_rain": rain("Daily Rain", 7),
    "yesterday_rain": rain("Yesterday Rain", 19),
    "monthly_rain": rain("Monthly Rain", 8),
    "yearly_rain": rain("Yearly Rain", 9),
    "rain_rate": rain("Rain Rate", 10),
    "pressure": Condition("Pressure", 6, "pressure", UnitOfPressure.HPA,
                          UnitOfPressure.INHG, "mdi:trending-up"),
    "humidity": humidity("Humidity", 5),
    "humidity_indoor": humidity("Indoor Humidity", 13),
    "humidity_max": humidity("Max Humidity", 163),
    "humidity_min": humidity("Min Humidity", 164),
    "cloud_height": Condition(
        "Cloud Height", 73, "height", UnitOfLength.METERS,
        UnitOfLength.FEET, "mdi:cloud-outline"),
    "forecast": Condition("Forecast", 15, "forecast",
                          icon="mdi:card-text-outline"),
    "station": Condition("Station", 32, "text",
                         icon="mdi:home-thermometer-outline"),
    "date": Condition("Date", 74, "text", icon="mdi:calendar"),
    "wind_chill": temperature("Wind Chill", 44),
    "wind_chill_max": temperature("Today MAX Wind Chill", 77),
    "wind_chill_min": temperature("Today MIN Wind Chill", 78),
    "vp_solar": Condition("VP solar", 127, "solar",
                          UnitOfIrradiance.WATTS_PER_SQUARE_METER,
                          UnitOfIrradiance.BTUS_PER_HOUR_SQUARE_FOOT,
                          "mdi:solar-power"),
    "uv_index": Condition("UV index", 79, "number", UV_INDEX, UV_INDEX,
                          "mdi:white-balance-sunny"),
    # These fields historically expose the raw numeric values in either system.
    "apparent_temp": Condition("Apparent temperature", 130, "number",
                               UnitOfTemperature.CELSIUS,
                               UnitOfTemperature.FAHRENHEIT),
    "apparent_temp_min": Condition("Apparent temperature", 137, "number",
                                   UnitOfTemperature.CELSIUS,
                                   UnitOfTemperature.FAHRENHEIT),
    "apparent_temp_max": Condition("Apparent temperature", 136, "number",
                                   UnitOfTemperature.CELSIUS,
                                   UnitOfTemperature.FAHRENHEIT),
}

FORECASTS = (
    "sunny", "clear night", "cloudy", "cloudy2", "night cloudy", "dry",
    "fog", "haze", "heavy rain", "mainly fine", "mist", "night fog",
    "night heavy rain", "night overcast", "night rain", "night showers",
    "night snow", "night thunder", "overcast", "partly cloudy", "rain",
    "rain2", "showers", "sleet", "sleet showers", "snow", "snow melt",
    "snow showers2", "sunny", "thunder showers", "thunder showers2",
    "thunder storms", "tornado", "windy", "stopped raining", "windy rain",
    "sunrise", "sunset",
)
DIRECTIONS = (
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
)
