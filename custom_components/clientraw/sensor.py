"""Clientraw sensors and the temporary YAML import bridge."""

import logging
from datetime import datetime

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA, SensorDeviceClass, SensorEntity,
)
from homeassistant.const import CONF_NAME, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    config_validation as cv, entity_registry as er, issue_registry as ir,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_system import METRIC_SYSTEM

from . import ClientrawConfigEntry
from .client import import_id, normalize_url, parse_condition
from .const import (
    CONDITIONS, CONF_DATE_FORMAT, CONF_IMPORT_ID, CONF_INTERVAL,
    CONF_MONITORED_CONDITIONS, CONF_STATION_TIMEZONE, DEFAULT_INTERVAL,
    DEFAULT_NAME, DOMAIN,
)
from .coordinator import ClientrawCoordinator

_LOGGER = logging.getLogger(__name__)

DEVICE_CLASSES = {
    "timestamp": SensorDeviceClass.TIMESTAMP,
    "temperature": SensorDeviceClass.TEMPERATURE,
    "wind": SensorDeviceClass.WIND_SPEED,
    "humidity": SensorDeviceClass.HUMIDITY,
    "pressure": SensorDeviceClass.ATMOSPHERIC_PRESSURE,
    "rain": SensorDeviceClass.PRECIPITATION,
    "rain_rate": SensorDeviceClass.PRECIPITATION_INTENSITY,
    "height": SensorDeviceClass.DISTANCE,
    "solar": SensorDeviceClass.IRRADIANCE,
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_URL): vol.All(cv.url, normalize_url),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_INTERVAL, default=DEFAULT_INTERVAL):
        vol.All(vol.Coerce(int), vol.Range(min=1, max=59)),
    vol.Optional(CONF_MONITORED_CONDITIONS, default=[]):
        vol.All(cv.ensure_list, [vol.In(CONDITIONS)]),
})


async def async_setup_platform(
    hass, config, async_add_entities, discovery_info=None,
):
    """Import YAML once; never create a second YAML-managed set of sensors."""
    data = {key: config[key] for key in (
        CONF_URL, CONF_NAME, CONF_INTERVAL, CONF_MONITORED_CONDITIONS)}
    data[CONF_IMPORT_ID] = import_id(data[CONF_URL], data[CONF_NAME])
    ir.async_create_issue(
        hass, DOMAIN, f"remove_yaml_{data[CONF_IMPORT_ID]}",
        is_fixable=False, severity=ir.IssueSeverity.WARNING,
        translation_key="remove_yaml",
    )
    _LOGGER.warning(
        "Clientraw YAML configuration is deprecated. After the imported "
        "entry is set up successfully, remove its sensor platform YAML block")
    hass.async_create_task(hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "import"}, data=data))


async def async_setup_entry(
    hass: HomeAssistant, entry: ClientrawConfigEntry, async_add_entities,
) -> None:
    """Create the user's saved selection, including unavailable fields."""
    selected = entry.options.get(
        CONF_MONITORED_CONDITIONS, entry.data[CONF_MONITORED_CONDITIONS])
    deselected_ids = {
        f"{entry.entry_id}_{key}" for key in CONDITIONS if key not in selected}
    registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if (entity.domain == "sensor" and entity.platform == DOMAIN
                and entity.unique_id in deselected_ids):
            registry.async_remove(entity.entity_id)
        elif (entity.domain == "sensor" and entity.platform == DOMAIN
              and entity.unique_id == f"{entry.entry_id}_rain_rate"
              and entity.unit_of_measurement in ("mm", "in")
              and "unit_of_measurement" not in entity.options.get(
                  "sensor", {})):
            registry.async_update_entity_options(
                entity.entity_id, "sensor.private", {
                    "suggested_unit_of_measurement":
                        f"{entity.unit_of_measurement}/h",
                })
    async_add_entities(
        ClientrawSensor(entry.runtime_data, entry, key) for key in selected)


class ClientrawSensor(CoordinatorEntity[ClientrawCoordinator], SensorEntity):
    """A stable sensor backed by the station's shared data."""

    def __init__(self, coordinator: ClientrawCoordinator,
                 entry: ClientrawConfigEntry, key: str) -> None:
        super().__init__(coordinator)
        self.key = key
        self.condition = CONDITIONS[key]
        self._station_timezone = dt_util.get_time_zone(
            entry.data[CONF_STATION_TIMEZONE])
        self._date_format = entry.data[CONF_DATE_FORMAT]
        assert self._station_timezone is not None
        self._attr_name = f"{entry.data[CONF_NAME]} {self.condition.name}"
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data[CONF_NAME],
        )
        self._attr_icon = self.condition.icon
        self._attr_state_class = self.condition.state_class
        if self.condition.kind in DEVICE_CLASSES:
            self._attr_device_class = DEVICE_CLASSES[self.condition.kind]
        if self.condition.kind == "wind":
            self._attr_suggested_unit_of_measurement = (
                self.condition.metric
                if coordinator.hass.config.units is METRIC_SYSTEM
                else self.condition.imperial)
        elif (self.condition.kind == "rain_rate"
              and coordinator.hass.config.units is not METRIC_SYSTEM):
            self._attr_suggested_unit_of_measurement = self.condition.imperial
        self._attr_native_unit_of_measurement = self.condition.native_unit
        if self.condition.native_unit is not None:
            self._attr_suggested_display_precision = 2

    @property
    def native_value(self) -> str | float | int | datetime | None:
        return parse_condition(
            self.coordinator.data, self.key, self._station_timezone,
            self._date_format)

    @property
    def available(self) -> bool:
        return super().available and self.native_value is not None
