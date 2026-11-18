"""Native configuration, YAML import, and editable Clientraw settings."""

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow,
)
from homeassistant.const import CONF_NAME, CONF_URL
from homeassistant.core import callback
from homeassistant.helpers import (
    config_validation as cv, issue_registry as ir, selector,
)
from homeassistant.util import dt as dt_util

from .client import (
    FETCH_ERRORS, InvalidClientraw, async_fetch, detect_conditions,
    endpoint_id, import_id, import_signature, normalize_url,
)
from .const import (
    CONDITIONS, CONF_DATE_FORMAT, CONF_IMPORT_ID, CONF_IMPORT_SIGNATURE,
    CONF_INTERVAL, CONF_LEGACY_NAME, CONF_MONITORED_CONDITIONS,
    CONF_STATION_TIMEZONE, DATE_FORMATS, DEFAULT_DATE_FORMAT, DEFAULT_INTERVAL,
    DEFAULT_NAME, DOMAIN,
)

CONF_REDETECT = "redetect"
INTERVAL = vol.All(vol.Coerce(int), vol.Range(min=1, max=59))
CONDITION_LIST = vol.All([vol.In(CONDITIONS)])


def conditions_schema(selected: list[str]) -> vol.Schema:
    """Use a native checkbox list with all supported conditions."""
    return vol.Schema({
        vol.Required(CONF_MONITORED_CONDITIONS, default=selected):
            selector.SelectSelector(selector.SelectSelectorConfig(
                options=[
                    selector.SelectOptionDict(
                        value=key, label=f"{condition.name} ({key})")
                    for key, condition in CONDITIONS.items()
                ],
                multiple=True, mode=selector.SelectSelectorMode.LIST,
            )),
    })


def current_conditions(entry: ConfigEntry) -> list[str]:
    """Respect explicit empty selections and saved overrides."""
    return list(entry.options.get(
        CONF_MONITORED_CONDITIONS, entry.data[CONF_MONITORED_CONDITIONS]))


def timestamp_settings(settings: dict[str, Any],
                       default_timezone: str) -> dict[str, str]:
    """Validate explicit date order and station timezone."""
    return {
        CONF_DATE_FORMAT: vol.In(DATE_FORMATS)(
            settings.get(CONF_DATE_FORMAT, DEFAULT_DATE_FORMAT)),
        CONF_STATION_TIMEZONE: cv.time_zone(
            settings.get(CONF_STATION_TIMEZONE, default_timezone)),
    }


def timestamp_schema(settings: dict[str, Any],
                     default_timezone: str) -> vol.Schema:
    """Offer unambiguous date formats and an IANA timezone."""
    date_format = vol.Required(
        CONF_DATE_FORMAT, default=settings.get(
            CONF_DATE_FORMAT, DEFAULT_DATE_FORMAT))
    return vol.Schema({
        date_format: selector.SelectSelector(selector.SelectSelectorConfig(
            options=[
                selector.SelectOptionDict(value="dmy", label="DD/MM/YYYY"),
                selector.SelectOptionDict(value="mdy", label="MM/DD/YYYY"),
                selector.SelectOptionDict(value="iso", label="YYYY-MM-DD"),
            ],
            mode=selector.SelectSelectorMode.DROPDOWN,
        )),
        vol.Required(CONF_STATION_TIMEZONE, default=settings.get(
            CONF_STATION_TIMEZONE, default_timezone)): str,
    })


def detect_with_settings(fields: list[str],
                         settings: dict[str, Any]) -> list[str]:
    """Use the station's settings for both detection and runtime."""
    timezone = dt_util.get_time_zone(settings[CONF_STATION_TIMEZONE])
    assert timezone is not None
    return detect_conditions(fields, timezone, settings[CONF_DATE_FORMAT])


class ClientrawConfigFlow(ConfigFlow, domain=DOMAIN):
    """Configure a Clientraw station without YAML."""

    VERSION = 1
    MINOR_VERSION = 2

    def __init__(self) -> None:
        self._settings: dict[str, Any] = {}
        self._selected: list[str] = []
        self._reconfiguring = False

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return ClientrawOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Validate the endpoint before suggesting monitored conditions."""
        errors = {}
        if user_input is not None:
            try:
                url = normalize_url(user_input[CONF_URL])
                interval = INTERVAL(user_input[CONF_INTERVAL])
                name = str(user_input[CONF_NAME]).strip()
                if not name:
                    raise ValueError("Station name must not be empty")
                timestamp = timestamp_settings(
                    user_input, self.hass.config.time_zone)
            except (ValueError, vol.Invalid):
                errors["base"] = "invalid_settings"
            else:
                await self.async_set_unique_id(endpoint_id(url))
                self._abort_if_unique_id_configured()
                try:
                    fields = await async_fetch(self.hass, url)
                except InvalidClientraw:
                    errors["base"] = "invalid_clientraw"
                except FETCH_ERRORS:
                    errors["base"] = "cannot_connect"
                else:
                    self._settings = {
                        CONF_URL: url, CONF_NAME: name,
                        CONF_INTERVAL: interval,
                        **timestamp,
                    }
                    self._selected = detect_with_settings(
                        fields, self._settings)
                    return await self.async_step_conditions()
        defaults = user_input or {}
        return self.async_show_form(
            step_id="user", errors=errors,
            data_schema=vol.Schema({
                vol.Required(
                    CONF_URL, default=defaults.get(CONF_URL, "")): str,
                vol.Required(CONF_NAME, default=defaults.get(
                    CONF_NAME, DEFAULT_NAME)): str,
                vol.Required(CONF_INTERVAL, default=defaults.get(
                    CONF_INTERVAL, DEFAULT_INTERVAL)): INTERVAL,
            }).extend(timestamp_schema(
                defaults, self.hass.config.time_zone).schema),
        )

    async def async_step_conditions(
        self, user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Save the user's checklist, not an ongoing detection rule."""
        errors = {}
        if user_input is not None:
            try:
                selected = CONDITION_LIST(
                    user_input[CONF_MONITORED_CONDITIONS])
            except vol.Invalid:
                errors["base"] = "invalid_conditions"
            else:
                if self._reconfiguring:
                    return self._finish_reconfigure(selected)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=self._settings[CONF_NAME],
                    data={
                        **self._settings, CONF_MONITORED_CONDITIONS: selected},
                )
        return self.async_show_form(
            step_id="conditions",
            data_schema=conditions_schema(self._selected),
            errors=errors,
        )

    async def async_step_import(
        self, user_input: dict[str, Any],
    ) -> ConfigFlowResult:
        """Import exact YAML settings without requiring an online station."""
        url = normalize_url(user_input[CONF_URL])
        token = import_id(url, user_input[CONF_NAME])
        signature = import_signature(
            url, user_input[CONF_NAME], user_input[CONF_INTERVAL],
            user_input[CONF_MONITORED_CONDITIONS])
        for entry in self._async_current_entries():
            if entry.data.get(CONF_IMPORT_ID) == token:
                if entry.data[CONF_IMPORT_SIGNATURE] == signature:
                    return self.async_abort(reason="already_imported")
                return self._import_conflict(token)
        unique_id = endpoint_id(url)
        if any(entry.unique_id == unique_id
               for entry in self._async_current_entries()):
            return self._import_conflict(token)
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()
        ir.async_delete_issue(self.hass, DOMAIN, f"import_conflict_{token}")
        return self.async_create_entry(
            title=user_input[CONF_NAME],
            data={
                CONF_URL: url, CONF_NAME: user_input[CONF_NAME],
                CONF_INTERVAL: user_input[CONF_INTERVAL],
                CONF_MONITORED_CONDITIONS:
                    user_input[CONF_MONITORED_CONDITIONS],
                CONF_IMPORT_ID: token,
                CONF_IMPORT_SIGNATURE: signature,
                CONF_LEGACY_NAME: user_input[CONF_NAME],
                **timestamp_settings({}, self.hass.config.time_zone),
            },
        )

    def _import_conflict(self, token: str) -> ConfigFlowResult:
        ir.async_create_issue(
            self.hass, DOMAIN, f"import_conflict_{token}",
            is_fixable=False, severity=ir.IssueSeverity.ERROR,
            translation_key="import_conflict",
        )
        return self.async_abort(reason="import_conflict")

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Edit connection settings, optionally detecting fresh suggestions."""
        entry = self._get_reconfigure_entry()
        errors = {}
        if user_input is not None:
            try:
                url = normalize_url(user_input[CONF_URL])
                name = str(user_input[CONF_NAME]).strip()
                if not name:
                    raise ValueError("Station name must not be empty")
                timestamp = timestamp_settings(
                    {**entry.data, **user_input}, self.hass.config.time_zone)
            except (ValueError, vol.Invalid):
                errors["base"] = "invalid_settings"
            else:
                unique_id = endpoint_id(url)
                if any(other.entry_id != entry.entry_id
                       and other.unique_id == unique_id
                       for other in self._async_current_entries()):
                    return self.async_abort(reason="already_configured")
                try:
                    fields = await async_fetch(self.hass, url)
                except InvalidClientraw:
                    errors["base"] = "invalid_clientraw"
                except FETCH_ERRORS:
                    errors["base"] = "cannot_connect"
                else:
                    self._settings = {
                        CONF_URL: url, CONF_NAME: name, **timestamp}
                    self._reconfiguring = True
                    if user_input.get(CONF_REDETECT, False):
                        self._selected = detect_with_settings(
                            fields, self._settings)
                        return await self.async_step_conditions()
                    return self._finish_reconfigure()
        defaults = {**entry.data, **(user_input or {})}
        return self.async_show_form(
            step_id="reconfigure", errors=errors,
            data_schema=vol.Schema({
                vol.Required(CONF_URL, default=defaults[CONF_URL]): str,
                vol.Required(CONF_NAME, default=defaults[CONF_NAME]): str,
                vol.Optional(CONF_REDETECT, default=defaults.get(
                    CONF_REDETECT, False)): bool,
            }).extend(timestamp_schema(
                defaults, self.hass.config.time_zone).schema),
        )

    def _finish_reconfigure(
        self, selected: list[str] | None = None,
    ) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        unique_id = endpoint_id(self._settings[CONF_URL])
        if any(other.entry_id != entry.entry_id
               and other.unique_id == unique_id
               for other in self._async_current_entries()):
            return self.async_abort(reason="already_configured")
        options = dict(entry.options)
        if selected is not None:
            options[CONF_MONITORED_CONDITIONS] = selected
        return self.async_update_reload_and_abort(
            entry, title=self._settings[CONF_NAME],
            unique_id=unique_id,
            data_updates=self._settings, options=options,
        )


class ClientrawOptionsFlow(OptionsFlow):
    """Edit polling and the selection without discarding manual choices."""

    def __init__(self) -> None:
        self._interval = DEFAULT_INTERVAL
        self._selected: list[str] = []

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        entry = self.config_entry
        errors = {}
        if user_input is not None:
            try:
                self._interval = INTERVAL(user_input[CONF_INTERVAL])
                selected = CONDITION_LIST(
                    user_input[CONF_MONITORED_CONDITIONS])
            except vol.Invalid:
                errors["base"] = "invalid_settings"
            else:
                if not user_input.get(CONF_REDETECT, False):
                    return self._save(selected)
                try:
                    fields = await async_fetch(self.hass, entry.data[CONF_URL])
                except InvalidClientraw:
                    errors["base"] = "invalid_clientraw"
                except FETCH_ERRORS:
                    errors["base"] = "cannot_connect"
                else:
                    self._selected = detect_with_settings(
                        fields, timestamp_settings(
                            entry.data, self.hass.config.time_zone))
                    return await self.async_step_conditions()
        defaults = user_input or {
            CONF_INTERVAL: entry.options.get(
                CONF_INTERVAL, entry.data[CONF_INTERVAL]),
            CONF_MONITORED_CONDITIONS: current_conditions(entry),
        }
        schema = conditions_schema(
            defaults[CONF_MONITORED_CONDITIONS]).extend({
                vol.Required(
                    CONF_INTERVAL, default=defaults[CONF_INTERVAL]): INTERVAL,
                vol.Optional(CONF_REDETECT, default=defaults.get(
                    CONF_REDETECT, False)): bool,
            })
        return self.async_show_form(
            step_id="init", data_schema=schema, errors=errors)

    async def async_step_conditions(
        self, user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        errors = {}
        if user_input is not None:
            try:
                selected = CONDITION_LIST(
                    user_input[CONF_MONITORED_CONDITIONS])
            except vol.Invalid:
                errors["base"] = "invalid_conditions"
            else:
                return self._save(selected)
        return self.async_show_form(
            step_id="conditions",
            data_schema=conditions_schema(self._selected),
            errors=errors,
        )

    def _save(self, selected: list[str]) -> ConfigFlowResult:
        options = {
            CONF_INTERVAL: self._interval,
            CONF_MONITORED_CONDITIONS: selected,
        }
        # Save before scheduling, without newer OptionsFlowWithReload APIs or
        # an update listener that would also reload reconfiguration flows.
        if self.hass.config_entries.async_update_entry(
                self.config_entry, options=options):
            self.hass.config_entries.async_schedule_reload(
                self.config_entry.entry_id)
        return self.async_create_entry(title="", data=options)
