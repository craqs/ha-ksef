"""KSeF data coordinator."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_NIP,
    CONF_REFRESH_TOKEN,
    CONF_TOKEN,
    CONF_USE_PROD,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SENSOR_TYPES,
)
from .ksef_api.client import (
    KSEFAuthError,
    KSEFClient,
    KSEFError,
    KSEFRateLimitError,
    PROD_BASE_URL,
    TEST_BASE_URL,
)
from .ksef_api.models import DateRange
from .ksef_api.utils import parse_month_option

_LOGGER = logging.getLogger(__name__)


class KSEFCoordinator(DataUpdateCoordinator):
    """Fetches invoice data for all four sensor groups."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=DEFAULT_SCAN_INTERVAL),
        )
        self._entry = entry
        self._client: KSEFClient | None = None

    def _build_client(self) -> KSEFClient:
        data = self._entry.data
        return KSEFClient(
            nip=data[CONF_NIP],
            ksef_token=data[CONF_TOKEN],
            base_url=PROD_BASE_URL if data.get(CONF_USE_PROD, True) else TEST_BASE_URL,
            access_token=data.get(CONF_ACCESS_TOKEN),
            refresh_token=data.get(CONF_REFRESH_TOKEN),
        )

    def _save_tokens(self) -> None:
        if self._client is None:
            return
        tokens = self._client.tokens
        if tokens.get("access_token"):
            self.hass.config_entries.async_update_entry(
                self._entry,
                data={
                    **self._entry.data,
                    CONF_ACCESS_TOKEN: tokens["access_token"],
                    CONF_REFRESH_TOKEN: tokens.get("refresh_token"),
                },
            )

    async def _async_update_data(self) -> dict[str, Any]:
        if self._client is None:
            self._client = self._build_client()

        try:
            data = await self.hass.async_add_executor_job(self._fetch_all)
            self._save_tokens()
            return data
        except KSEFAuthError as err:
            self._client = None  # force re-auth next time
            raise ConfigEntryAuthFailed(str(err)) from err
        except KSEFRateLimitError as err:
            raise UpdateFailed(str(err)) from err
        except KSEFError as err:
            raise UpdateFailed(str(err)) from err

    def _fetch_all(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, _name, subject_type, period in SENSOR_TYPES:
            from_str, to_str = parse_month_option(period)
            date_range = DateRange(from_date=from_str, to_date=to_str, date_type="Issue")
            invoices = self._client.list_invoices(subject_type, date_range)
            result[key] = invoices
            _LOGGER.debug("Fetched %d invoices for %s", len(invoices), key)
        return result
