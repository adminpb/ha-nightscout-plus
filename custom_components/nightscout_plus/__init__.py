"""Nightscout Plus — розширена інтеграція Nightscout для Home Assistant.

Форк оригінальної інтеграції nightscout з підтримкою:
- Treatments (ліки, їжа, болюси, замітки, тренування)
- Notes (нотатки користувача)
- IOB / COB (з devicestatus)
- Blood Glucose (SGV) з підтримкою mmol/L
"""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant

from .api import NightscoutClient
from .const import (
    DOMAIN,
    CONF_API_SECRET,
    CONF_TREATMENTS_COUNT,
    DEFAULT_TREATMENTS_COUNT,
    PLATFORMS,
)
from .coordinator import NightscoutPlusCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Nightscout Plus from a config entry."""
    url = entry.data[CONF_URL]
    api_secret = entry.data.get(CONF_API_SECRET)
    treatments_count = entry.data.get(CONF_TREATMENTS_COUNT, DEFAULT_TREATMENTS_COUNT)

    client = NightscoutClient(url, api_secret=api_secret)

    # Перевірка підключення
    try:
        status = await client.test_connection()
        _LOGGER.info(
            "Connected to Nightscout '%s' v%s",
            status.get("name", "?"),
            status.get("version", "?"),
        )
    except Exception as exc:
        _LOGGER.error("Failed to connect to Nightscout at %s: %s", url, exc)
        await client.close()
        return False

    coordinator = NightscoutPlusCoordinator(
        hass,
        client,
        treatments_count=treatments_count,
    )

    # Перше завантаження даних
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "client": client,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        await data["client"].close()

    return unload_ok
