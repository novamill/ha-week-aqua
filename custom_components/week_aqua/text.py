"""Text platform: the device's Bluetooth name (as shown in the Week Aqua app)."""

from __future__ import annotations

from homeassistant.components.text import TextEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import WeekAquaConfigEntry
from .device import WeekAquaError
from .entity import WeekAquaEntity
from .protocol import NAME_MAX_LEN, NAME_PATTERN

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WeekAquaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([WeekAquaBluetoothName(entry)])


class WeekAquaBluetoothName(WeekAquaEntity, TextEntity):
    """Name stored in the device. Read from its advertisements, so it is real state.

    Renaming here changes what the Week Aqua app and Bluetooth scanners show.
    The Home Assistant device name is separate and can be changed in the UI.
    """

    _attr_translation_key = "bluetooth_name"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_assumed_state = False
    _attr_native_min = 1
    _attr_native_max = NAME_MAX_LEN
    _attr_pattern = NAME_PATTERN

    def __init__(self, entry: WeekAquaConfigEntry) -> None:
        super().__init__(entry, "bluetooth_name")

    @property
    def native_value(self) -> str | None:
        return self._device.advertised_name

    async def async_set_value(self, value: str) -> None:
        try:
            await self._device.set_name(value)
        except WeekAquaError as err:
            raise HomeAssistantError(str(err)) from err
