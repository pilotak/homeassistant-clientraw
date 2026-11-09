"""Clientraw weather station config entries."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.util import slugify

from .const import CONDITIONS, CONF_LEGACY_NAME, DOMAIN
from .coordinator import ClientrawCoordinator

PLATFORMS = [Platform.SENSOR]
type ClientrawConfigEntry = ConfigEntry[ClientrawCoordinator]


def migrate_entities(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Adopt legacy entities without changing their entity IDs."""
    if CONF_LEGACY_NAME not in entry.data:
        return
    registry = er.async_get(hass)
    migrations: list[tuple[str, str]] = []
    for key in CONDITIONS:
        old_id = slugify(f"sensor.{entry.data[CONF_LEGACY_NAME]}_{key}")
        entity_id = registry.async_get_entity_id("sensor", DOMAIN, old_id)
        if entity_id is None:
            continue
        entity = registry.async_get(entity_id)
        assert entity is not None
        new_id = f"{entry.entry_id}_{key}"
        collision = registry.async_get_entity_id("sensor", DOMAIN, new_id)
        if (entity.config_entry_id not in (None, entry.entry_id)
                or collision not in (None, entity_id)):
            ir.async_create_issue(
                hass, DOMAIN, f"migration_conflict_{entry.entry_id}",
                is_fixable=False, severity=ir.IssueSeverity.ERROR,
                translation_key="migration_conflict",
                translation_placeholders={"entity_id": entity_id},
            )
            raise ConfigEntryError(
                f"Cannot migrate {entity_id}: it belongs to another entry")
        migrations.append((entity_id, new_id))
    for entity_id, new_id in migrations:
        registry.async_update_entity(
            entity_id, new_unique_id=new_id, config_entry_id=entry.entry_id)
    ir.async_delete_issue(
        hass, DOMAIN, f"migration_conflict_{entry.entry_id}")
    data = dict(entry.data)
    del data[CONF_LEGACY_NAME]
    hass.config_entries.async_update_entry(entry, data=data)


async def async_setup_entry(
    hass: HomeAssistant, entry: ClientrawConfigEntry,
) -> bool:
    """Set up a station, retrying automatically if the endpoint is offline."""
    coordinator = ClientrawCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    migrate_entities(hass, entry)
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ClientrawConfigEntry,
) -> bool:
    """Unload entities and their coordinator subscriptions."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
