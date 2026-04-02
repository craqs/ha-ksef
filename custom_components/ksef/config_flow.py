"""Config flow for KSeF integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import CONF_NIP, CONF_TOKEN, CONF_USE_PROD, DOMAIN
from .ksef_api.client import KSEFAuthError, KSEFClient, KSEFError, PROD_BASE_URL, TEST_BASE_URL

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NIP): str,
        vol.Required(CONF_TOKEN): str,
        vol.Optional(CONF_USE_PROD, default=True): bool,
    }
)


async def _validate_credentials(
    hass: HomeAssistant, nip: str, token: str, use_prod: bool
) -> dict:
    """Attempt authentication and return tokens on success."""
    client = KSEFClient(
        nip=nip,
        ksef_token=token,
        base_url=PROD_BASE_URL if use_prod else TEST_BASE_URL,
    )
    try:
        await hass.async_add_executor_job(client.authenticate)
    except KSEFAuthError as err:
        raise InvalidAuth(str(err)) from err
    except KSEFError as err:
        raise CannotConnect(str(err)) from err
    return client.tokens


class KSEFConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial configuration."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            nip = user_input[CONF_NIP].strip()
            token = user_input[CONF_TOKEN].strip()
            use_prod = user_input.get(CONF_USE_PROD, True)

            # Prevent duplicate entries for the same NIP + environment
            await self.async_set_unique_id(f"{nip}_{'prod' if use_prod else 'test'}")
            self._abort_if_unique_id_configured()

            try:
                tokens = await _validate_credentials(
                    self.hass, nip, token, use_prod
                )
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during KSeF authentication")
                errors["base"] = "unknown"
            else:
                env_label = "Production" if use_prod else "Test"
                return self.async_create_entry(
                    title=f"KSeF {nip} ({env_label})",
                    data={
                        CONF_NIP: nip,
                        CONF_TOKEN: token,
                        CONF_USE_PROD: use_prod,
                        **tokens,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate a connection problem."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate invalid credentials."""
