"""One managed polling loop per Clientraw station."""

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator, UpdateFailed,
)

from .client import FETCH_ERRORS, async_fetch
from .const import CONF_INTERVAL, DEFAULT_INTERVAL, DOMAIN

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

    async def _async_update_data(self) -> list[str]:
        try:
            return await async_fetch(self.hass, self.url)
        except FETCH_ERRORS as err:
            # Do not log URLs, which may contain credentials or query secrets.
            raise UpdateFailed("Unable to fetch valid clientraw data") from err
