"""Shared state for an R/G/B/UV lamp.

The lamp is write-only, so Home Assistant is the source of truth for its
settings. Several entities edit the same settings: the light, one slider per
colour channel, and the built-in schedule controls (switch, on/off time,
ramp). This controller holds those settings, keeps them on disk across
restarts, sends the matching frames and notifies the entities.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass, field, replace
from datetime import time
from typing import Any

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store

from .const import DOMAIN
from .device import WeekAquaDevice, WeekAquaError
from .protocol import (
    LIGHT_CHANNELS,
    RAMP_MINUTES_TO_CODE,
    cmd_light_always_on,
    cmd_light_levels,
    cmd_light_off,
    cmd_light_schedule,
    cmd_manual_mode,
)

STORAGE_VERSION = 1
SAVE_DELAY = 5.0

DEFAULT_CHANNELS = {"red": 100.0, "green": 100.0, "blue": 100.0, "uv": 100.0}


def _store(hass: HomeAssistant, entry_id: str) -> Store[dict[str, Any]]:
    return Store(hass, STORAGE_VERSION, f"{DOMAIN}.lamp.{entry_id}")


async def async_remove_settings(hass: HomeAssistant, entry_id: str) -> None:
    """Delete a lamp's stored settings (device removed)."""
    await _store(hass, entry_id).async_remove()


@dataclass
class LampSettings:
    """Everything the lamp has been told, in app units."""

    is_on: bool = False
    # Requested channel levels in percent, before the power budget is applied.
    channels: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_CHANNELS))
    schedule_enabled: bool = False
    on_time: time = time(8, 0)
    # 00:00 as off time means midnight (24:00).
    off_time: time = time(20, 0)
    ramp: int = 30

    def to_json(self) -> dict[str, Any]:
        data = asdict(self)
        data["on_time"] = self.on_time.isoformat("minutes")
        data["off_time"] = self.off_time.isoformat("minutes")
        return data

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> LampSettings:
        settings = cls()
        settings.is_on = bool(data.get("is_on", settings.is_on))
        channels = data.get("channels") or {}
        settings.channels = {
            ch: float(channels.get(ch, DEFAULT_CHANNELS[ch])) for ch in LIGHT_CHANNELS
        }
        settings.schedule_enabled = bool(data.get("schedule_enabled", False))
        for key in ("on_time", "off_time"):
            if value := data.get(key):
                setattr(settings, key, time.fromisoformat(value))
        if (ramp := data.get("ramp")) in RAMP_MINUTES_TO_CODE:
            settings.ramp = ramp
        return settings


class LampController:
    """Single owner of a lamp's settings."""

    def __init__(self, hass: HomeAssistant, device: WeekAquaDevice, entry_id: str) -> None:
        self._device = device
        self._store = _store(hass, entry_id)
        self.settings = LampSettings()
        self._listeners: list[Callable[[], None]] = []

    async def async_load(self) -> None:
        if data := await self._store.async_load():
            self.settings = LampSettings.from_json(data)

    async def async_flush(self) -> None:
        """Write pending settings now (unload/reload)."""
        await self._store.async_save(self.settings.to_json())

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> CALLBACK_TYPE:
        self._listeners.append(listener)

        @callback
        def _remove() -> None:
            self._listeners.remove(listener)

        return _remove

    # -- commands --------------------------------------------------------

    async def async_set_light(self, is_on: bool, channels: dict[str, float] | None = None) -> None:
        """Switch the lamp on with the given (or stored) channels, or off."""
        new = replace(self.settings, is_on=is_on)
        if channels is not None:
            new.channels = {ch: max(0.0, min(100.0, float(channels[ch]))) for ch in LIGHT_CHANNELS}
        if is_on and not any(new.channels.values()):
            new.channels = dict(DEFAULT_CHANNELS)
        frame = (
            cmd_light_levels(*(new.channels[ch] for ch in LIGHT_CHANNELS))
            if is_on
            else cmd_light_off()
        )
        await self._send(cmd_manual_mode(), frame)
        self._commit(new)

    async def async_set_channel(self, channel: str, percent: float) -> None:
        """Change one channel. Like the app's sliders, this lights the lamp."""
        channels = {**self.settings.channels, channel: percent}
        if any(channels.values()):
            await self.async_set_light(True, channels)
        else:
            await self.async_set_light(False, channels)

    async def async_set_schedule(
        self,
        *,
        enabled: bool | None = None,
        on_time: time | None = None,
        off_time: time | None = None,
        ramp: int | None = None,
    ) -> None:
        """Update the built-in schedule. Sent only while it is enabled."""
        new = replace(self.settings)
        if enabled is not None:
            new.schedule_enabled = enabled
        if on_time is not None:
            new.on_time = on_time.replace(second=0, microsecond=0)
        if off_time is not None:
            new.off_time = off_time.replace(second=0, microsecond=0)
        if ramp is not None:
            if ramp not in RAMP_MINUTES_TO_CODE:
                raise HomeAssistantError(f"Ramp must be one of {sorted(RAMP_MINUTES_TO_CODE)} minutes")
            new.ramp = ramp

        if new.schedule_enabled:
            off = None if new.off_time == time(0, 0) else new.off_time
            await self._send(cmd_manual_mode(), cmd_light_schedule(new.on_time, off, new.ramp))
        elif self.settings.schedule_enabled:
            await self._send(cmd_manual_mode(), cmd_light_always_on())
        self._commit(new)

    # -- internals -------------------------------------------------------

    async def _send(self, *frames: bytes) -> None:
        try:
            await self._device.send(*frames)
        except WeekAquaError as err:
            raise HomeAssistantError(str(err)) from err

    @callback
    def _commit(self, new: LampSettings) -> None:
        self.settings = new
        self._store.async_delay_save(self.settings.to_json, SAVE_DELAY)
        for listener in list(self._listeners):
            listener()
