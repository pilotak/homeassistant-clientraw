"""One managed polling loop per Clientraw station."""

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator, UpdateFailed,
)

from homeassistant.util import dt as dt_util

from .client import FETCH_ERRORS, async_fetch, parse_condition
from .const import (
    CONF_DATE_FORMAT, CONF_INTERVAL, CONF_MONITORED_CONDITIONS,
    CONF_STATION_TIMEZONE, DEFAULT_INTERVAL, DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class ClientrawCoordinator(DataUpdateCoordinator[list[str]]):
    """Fetch station data once for all its sensors."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass, _LOGGER, name=DOMAIN, config_entry=entry,
            update_interval=timedelta(minutes=entry.options.get(
                CONF_INTERVAL,
                entry.data.get(CONF_INTERVAL, DEFAULT_INTERVAL))),
        )
        self.url = entry.data[CONF_URL]
        self._entry = entry
        self._timezone = dt_util.get_time_zone(
            entry.data[CONF_STATION_TIMEZONE])
        assert self._timezone is not None

    async def _async_update_data(self) -> list[str]:
        try:
            fields = await async_fetch(self.hass, self.url)
        except FETCH_ERRORS as err:
            # Do not log URLs, which may contain credentials or query secrets.
            raise UpdateFailed("Unable to fetch valid clientraw data") from err
        selected = self._entry.options.get(
            CONF_MONITORED_CONDITIONS,
            self._entry.data[CONF_MONITORED_CONDITIONS])
        issue_id = f"invalid_timestamp_{self._entry.entry_id}"
        if ("last_updated" in selected and parse_condition(
                fields, "last_updated", self._timezone,
                self._entry.data[CONF_DATE_FORMAT]) is None):
            if ir.async_get(self.hass).async_get_issue(
                    DOMAIN, issue_id) is None:
                ir.async_create_issue(
                    self.hass, DOMAIN, issue_id, is_fixable=False,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key="invalid_timestamp",
                    translation_placeholders={
                        "station": self._entry.data["name"],
                    },
                )
        else:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)
        return fields
