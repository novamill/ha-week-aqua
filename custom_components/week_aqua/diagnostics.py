"""Diagnostics for Week Aqua."""

from __future__ import annotations

from typing import Any

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant

from . import WeekAquaConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: WeekAquaConfigEntry
) -> dict[str, Any]:
    device = entry.runtime_data
    service_info = bluetooth.async_last_service_info(hass, device.address, connectable=True)
    return {
        "entry": dict(entry.data),
        "kind": device.kind,
        "available": device.available,
        "advertisement": None
        if service_info is None
        else {
            "name": service_info.name,
            "rssi": service_info.rssi,
            "source": service_info.source,
            "manufacturer_data": {k: v.hex() for k, v in service_info.manufacturer_data.items()},
            "service_uuids": service_info.service_uuids,
        },
    }
