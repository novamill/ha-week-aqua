"""Fan platform: the Week Aqua filter / wave pump.

Percentage maps to the app's flow slider; preset modes are the flow patterns.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import WeekAquaConfigEntry
from .device import WeekAquaError
from .entity import WeekAquaEntity
from .protocol import PumpMode, cmd_manual_mode, cmd_pump

PARALLEL_UPDATES = 1

PRESET_TO_MODE = {mode.name.lower(): mode for mode in PumpMode}
DEFAULT_PRESET = "constant"
DEFAULT_PERCENTAGE = 100


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WeekAquaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([WeekAquaPump(entry)])


class WeekAquaPump(WeekAquaEntity, FanEntity, RestoreEntity):
    """Filter pump with flow control and wave patterns."""

    _attr_name = None
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.PRESET_MODE
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )
    _attr_preset_modes = list(PRESET_TO_MODE)
    _attr_speed_count = 100

    def __init__(self, entry: WeekAquaConfigEntry) -> None:
        super().__init__(entry, "pump")
        self._attr_percentage = DEFAULT_PERCENTAGE
        self._attr_preset_mode = DEFAULT_PRESET
        # Last non-zero flow, restored when turning back on.
        self._last_percentage = DEFAULT_PERCENTAGE

    @property
    def is_on(self) -> bool:
        return bool(self._attr_percentage)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) is None:
            return
        if (preset := last.attributes.get("preset_mode")) in PRESET_TO_MODE:
            self._attr_preset_mode = preset
        if (pct := last.attributes.get("percentage")) is not None:
            self._attr_percentage = int(pct)
            if pct:
                self._last_percentage = int(pct)
        if last.state == "off":
            self._attr_percentage = 0

    async def async_set_percentage(self, percentage: int) -> None:
        await self._apply(self._attr_preset_mode or DEFAULT_PRESET, percentage)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        await self._apply(preset_mode, self._attr_percentage or self._last_percentage)

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        await self._apply(
            preset_mode or self._attr_preset_mode or DEFAULT_PRESET,
            percentage if percentage is not None else self._last_percentage,
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._apply(self._attr_preset_mode or DEFAULT_PRESET, 0)

    async def _apply(self, preset: str, percentage: int) -> None:
        try:
            await self._device.send(
                cmd_manual_mode(), cmd_pump(PRESET_TO_MODE[preset], percentage)
            )
        except WeekAquaError as err:
            raise HomeAssistantError(str(err)) from err
        self._attr_preset_mode = preset
        self._attr_percentage = percentage
        if percentage:
            self._last_percentage = percentage
        self.async_write_ha_state()
