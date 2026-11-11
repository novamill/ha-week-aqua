"""Base entity for Week Aqua."""

from __future__ import annotations

from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity import Entity

from . import WeekAquaConfigEntry
from .const import DOMAIN
from .device import WeekAquaDevice
from .lamp import LampController
from .protocol import DeviceKind

MODEL = {DeviceKind.LIGHT_RGBUV: "RGB+UV LED (5746)", DeviceKind.PUMP: "Filter pump (5751)"}


class WeekAquaEntity(Entity):
    """Common device info, availability and naming."""

    _attr_has_entity_name = True
    # No read-back exists: state reflects the last command sent.
    _attr_assumed_state = True

    def __init__(self, entry: WeekAquaConfigEntry, key: str) -> None:
        self._device: WeekAquaDevice = entry.runtime_data
        self._attr_unique_id = f"{entry.unique_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id or self._device.address)},
            connections={(CONNECTION_BLUETOOTH, self._device.address)},
            name=entry.title,
            manufacturer="Week Aqua",
            model=MODEL[self._device.kind],
        )

    @property
    def available(self) -> bool:
        return self._device.available

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self._device.async_add_listener(self.async_write_ha_state))


class WeekAquaLampEntity(WeekAquaEntity):
    """Entity that shows and edits the shared settings of a lamp."""

    def __init__(self, entry: WeekAquaConfigEntry, key: str) -> None:
        super().__init__(entry, key)
        assert self._device.lamp is not None
        self._lamp: LampController = self._device.lamp

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self._lamp.async_add_listener(self.async_write_ha_state))
