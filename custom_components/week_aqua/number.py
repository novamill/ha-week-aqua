"""Number platform: colour channel sliders (lamps), feed-pause duration (pump)."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode, RestoreNumber
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import WeekAquaConfigEntry
from .entity import WeekAquaEntity, WeekAquaLampEntity
from .protocol import LIGHT_CHANNELS, PUMP_FEED_MINUTES, DeviceKind

DEFAULT_FEED_MINUTES = 10


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WeekAquaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    if entry.runtime_data.kind is DeviceKind.PUMP:
        async_add_entities([WeekAquaFeedDuration(entry)])
    else:
        async_add_entities(WeekAquaChannel(entry, channel) for channel in LIGHT_CHANNELS)


class WeekAquaChannel(WeekAquaLampEntity, NumberEntity):
    """One colour channel of a lamp, 0-100 % like the app's sliders.

    The value is the requested level. If the mix exceeds the lamp's power
    budget, all channels are scaled down together when sent (see the light's
    attributes for the actual output).
    """

    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER

    def __init__(self, entry: WeekAquaConfigEntry, channel: str) -> None:
        super().__init__(entry, f"channel_{channel}")
        self._channel = channel
        self._attr_translation_key = f"channel_{channel}"

    @property
    def native_value(self) -> float:
        return round(self._lamp.settings.channels[self._channel])

    async def async_set_native_value(self, value: float) -> None:
        await self._lamp.async_set_channel(self._channel, value)


class WeekAquaFeedDuration(WeekAquaEntity, RestoreNumber):
    """How long the "Feed" button pauses the pump.

    Local setting only: the duration is sent when the button is pressed.
    """

    _attr_translation_key = "feed_duration"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = PUMP_FEED_MINUTES[0]
    _attr_native_max_value = PUMP_FEED_MINUTES[-1]
    _attr_native_step = 5
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_mode = NumberMode.SLIDER
    # This is a local setting, never out of sync with the device.
    _attr_assumed_state = False

    def __init__(self, entry: WeekAquaConfigEntry) -> None:
        super().__init__(entry, "feed_duration")
        self._attr_native_value = DEFAULT_FEED_MINUTES

    @property
    def available(self) -> bool:
        return True

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_number_data()) and last.native_value:
            self._attr_native_value = last.native_value
        self._device.feed_minutes = int(self._attr_native_value)

    async def async_set_native_value(self, value: float) -> None:
        self._attr_native_value = value
        self._device.feed_minutes = int(value)
        self.async_write_ha_state()
