"""KSeF sensor entities."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_NIP, DOMAIN, SENSOR_TYPES
from .coordinator import KSEFCoordinator

_LOGGER = logging.getLogger(__name__)

MAX_INVOICES_IN_ATTRS = 50  # HA attribute size limit


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: KSEFCoordinator = hass.data[DOMAIN][entry.entry_id]
    nip = entry.data[CONF_NIP]
    async_add_entities(
        KSEFInvoiceSensor(coordinator, entry, key, name, nip)
        for key, name, _subject, _period in SENSOR_TYPES
    )


class KSEFInvoiceSensor(CoordinatorEntity[KSEFCoordinator], SensorEntity):
    """A sensor representing a group of KSeF invoices."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "invoices"
    _attr_icon = "mdi:file-document-outline"

    def __init__(
        self,
        coordinator: KSEFCoordinator,
        entry: ConfigEntry,
        key: str,
        name: str,
        nip: str,
    ) -> None:
        super().__init__(coordinator)
        self._key = key
        self._nip = nip
        self._attr_name = f"KSeF {name}"
        self._attr_unique_id = f"ksef_{nip}_{key}"

    @property
    def native_value(self) -> int | None:
        if self.coordinator.data is None:
            return None
        return len(self.coordinator.data.get(self._key, []))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if self.coordinator.data is None:
            return {}

        invoices = self.coordinator.data.get(self._key, [])
        total_net = round(sum(i.net_amount for i in invoices), 2)
        total_gross = round(sum(i.gross_amount for i in invoices), 2)
        total_vat = round(sum(i.vat_amount for i in invoices), 2)
        # Use the most common currency; fall back to PLN
        currencies = [i.currency for i in invoices if i.currency]
        currency = max(set(currencies), key=currencies.count) if currencies else "PLN"

        # Limit list size to avoid exceeding HA's 16 KB attribute cap
        invoice_list = [
            i.as_attr_dict() for i in invoices[:MAX_INVOICES_IN_ATTRS]
        ]

        attrs: dict[str, Any] = {
            "total_net": total_net,
            "total_gross": total_gross,
            "total_vat": total_vat,
            "currency": currency,
            "invoices": invoice_list,
        }
        if len(invoices) > MAX_INVOICES_IN_ATTRS:
            attrs["invoices_truncated"] = True
            attrs["total_count"] = len(invoices)

        return attrs

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success
