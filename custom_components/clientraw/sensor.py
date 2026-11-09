"""Clientraw sensors and the temporary YAML import bridge."""

import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_NAME, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.unit_system import METRIC_SYSTEM

from . import ClientrawConfigEntry
from .client import import_id, normalize_url, parse_condition
from .const import (
    CONDITIONS, CONF_IMPORT_ID, CONF_INTERVAL, CONF_MONITORED_CONDITIONS,
    DEFAULT_INTERVAL, DEFAULT_NAME, DOMAIN,
)
from .coordinator import ClientrawCoordinator

_LOGGER = logging.getLogger(__name__)

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
    async_add_entities(
        ClientrawSensor(entry.runtime_data, entry, key) for key in selected)


class ClientrawSensor(CoordinatorEntity[ClientrawCoordinator], SensorEntity):
    """A stable sensor backed by the station's shared data."""

    def __init__(self, coordinator: ClientrawCoordinator,
                 entry: ClientrawConfigEntry, key: str) -> None:
        super().__init__(coordinator)
        self.key = key
        self.condition = CONDITIONS[key]
        self._metric = coordinator.hass.config.units is METRIC_SYSTEM
        self._attr_name = f"{entry.data[CONF_NAME]} {self.condition.name}"
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_icon = self.condition.icon
        self._attr_native_unit_of_measurement = (
            self.condition.metric if self._metric else self.condition.imperial)

    @property
    def native_value(self) -> str | float | int | None:
        return parse_condition(self.coordinator.data, self.key, self._metric)

    @property
    def available(self) -> bool:
        return super().available and self.native_value is not None
