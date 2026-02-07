"""Config flow for Nightscout Plus integration."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_URL
from homeassistant.data_entry_flow import FlowResult

from .api import NightscoutClient, NightscoutAPIError, NightscoutAuthError
from .const import (
    DOMAIN,
    CONF_API_SECRET,
    CONF_TREATMENTS_COUNT,
    DEFAULT_TREATMENTS_COUNT,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Optional(CONF_API_SECRET, default=""): str,
        vol.Optional(
            CONF_TREATMENTS_COUNT, default=DEFAULT_TREATMENTS_COUNT
        ): vol.All(int, vol.Range(min=1, max=100)),
    }
)


class NightscoutPlusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nightscout Plus."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            url = user_input[CONF_URL].rstrip("/")
            api_secret = user_input.get(CONF_API_SECRET, "").strip() or None

            # Перевірка на дублікат
            await self.async_set_unique_id(url)
            self._abort_if_unique_id_configured()

            # Перевірка підключення
            client = NightscoutClient(url, api_secret=api_secret)
            try:
                status = await client.test_connection()
                title = status.get("name", "Nightscout")
            except NightscoutAuthError:
                errors["base"] = "invalid_auth"
            except NightscoutAPIError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Зберігаємо дані
                data = {
                    CONF_URL: url,
                    CONF_TREATMENTS_COUNT: user_input.get(
                        CONF_TREATMENTS_COUNT, DEFAULT_TREATMENTS_COUNT
                    ),
                }
                if api_secret:
                    data[CONF_API_SECRET] = api_secret

                return self.async_create_entry(
                    title=f"Nightscout Plus ({title})",
                    data=data,
                )
            finally:
                await client.close()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reconfiguration."""
        if user_input is not None:
            url = user_input[CONF_URL].rstrip("/")
            api_secret = user_input.get(CONF_API_SECRET, "").strip() or None

            client = NightscoutClient(url, api_secret=api_secret)
            try:
                await client.test_connection()
            except NightscoutAuthError:
                return self.async_show_form(
                    step_id="reconfigure",
                    data_schema=STEP_USER_DATA_SCHEMA,
                    errors={"base": "invalid_auth"},
                )
            except NightscoutAPIError:
                return self.async_show_form(
                    step_id="reconfigure",
                    data_schema=STEP_USER_DATA_SCHEMA,
                    errors={"base": "cannot_connect"},
                )
            finally:
                await client.close()

            data = {
                CONF_URL: url,
                CONF_TREATMENTS_COUNT: user_input.get(
                    CONF_TREATMENTS_COUNT, DEFAULT_TREATMENTS_COUNT
                ),
            }
            if api_secret:
                data[CONF_API_SECRET] = api_secret

            return self.async_update_reload_and_abort(
                self._get_reconfigure_entry(),
                data=data,
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=STEP_USER_DATA_SCHEMA,
        )
