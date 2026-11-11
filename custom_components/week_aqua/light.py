"""Light platform for Week Aqua R/G/B/UV lamps.

The lamp has four channels. They are exposed as one RGBW light where the
"white" channel drives the UV LEDs. Brightness scales the whole mix, like the
"total power" slider in the official app.
"""

from __future__ import annotations

from datetime import time
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGBW_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
import voluptuous as vol

from . import WeekAquaConfigEntry
from .const import (
    ATTR_OFF_TIME,
    ATTR_ON_TIME,
    ATTR_RAMP,
    SERVICE_CLEAR_SCHEDULE,
    SERVICE_SET_SCHEDULE,
)
from .entity import WeekAquaLampEntity
from .protocol import LIGHT_CHANNELS, RAMP_MINUTES_TO_CODE, limit_light_power

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WeekAquaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([WeekAquaLight(entry)])

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SET_SCHEDULE,
        {
            vol.Required(ATTR_ON_TIME): cv.time,
            vol.Required(ATTR_OFF_TIME): cv.time,
            vol.Optional(ATTR_RAMP, default=0): vol.All(
                vol.Coerce(int), vol.In(sorted(RAMP_MINUTES_TO_CODE))
            ),
        },
        "async_set_schedule",
    )
    platform.async_register_entity_service(
        SERVICE_CLEAR_SCHEDULE, None, "async_clear_schedule"
    )


class WeekAquaLight(WeekAquaLampEntity, LightEntity):
    """R/G/B/UV aquarium lamp.

    Brightness is the strongest channel; the RGBW colour is the channel mix
    scaled so that channel reads 255.
    """

    _attr_name = None
    _attr_color_mode = ColorMode.RGBW
    _attr_supported_color_modes = {ColorMode.RGBW}

    def __init__(self, entry: WeekAquaConfigEntry) -> None:
        super().__init__(entry, "light")

    @property
    def _levels(self) -> tuple[float, ...]:
        return tuple(self._lamp.settings.channels[ch] for ch in LIGHT_CHANNELS)

    @property
    def is_on(self) -> bool:
        return self._lamp.settings.is_on

    @property
    def brightness(self) -> int:
        return max(1, round(max(self._levels) * 255 / 100))

    @property
    def rgbw_color(self) -> tuple[int, int, int, int]:
        peak = max(self._levels) or 100
        r, g, b, w = (round(v / peak * 255) for v in self._levels)
        return (r, g, b, w)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Channel output in percent after the lamp's power budget is applied."""
        levels = limit_light_power(self._levels) if self.is_on else (0, 0, 0, 0)
        return dict(zip(LIGHT_CHANNELS, (round(v, 1) for v in levels), strict=True))

    async def async_turn_on(self, **kwargs: Any) -> None:
        if ATTR_RGBW_COLOR not in kwargs and ATTR_BRIGHTNESS not in kwargs:
            await self._lamp.async_set_light(True)
            return
        rgbw = kwargs.get(ATTR_RGBW_COLOR, self.rgbw_color)
        brightness = kwargs.get(ATTR_BRIGHTNESS, self.brightness)
        if not any(rgbw):
            rgbw = (255, 255, 255, 255)
        scale = brightness / 255 * 100 / 255
        await self._lamp.async_set_light(
            True, {ch: c * scale for ch, c in zip(LIGHT_CHANNELS, rgbw, strict=True)}
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._lamp.async_set_light(False)

    async def async_set_schedule(self, on_time: time, off_time: time, ramp: int = 0) -> None:
        """Program and enable the lamp's own daily on/off window."""
        await self._lamp.async_set_schedule(
            enabled=True, on_time=on_time, off_time=off_time, ramp=ramp
        )

    async def async_clear_schedule(self) -> None:
        """Disable the built-in window so only Home Assistant switches the lamp."""
        await self._lamp.async_set_schedule(enabled=False)
