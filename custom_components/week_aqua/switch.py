"""Switch platform: the lamp's built-in daily schedule."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import WeekAquaConfigEntry
from .entity import WeekAquaLampEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WeekAquaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([WeekAquaScheduleSwitch(entry)])


class WeekAquaScheduleSwitch(WeekAquaLampEntity, SwitchEntity):
    """On: the lamp follows its own on/off times, even without Home Assistant.

    Off: the window is set to 00:00-24:00, so only Home Assistant switches it.
    """

    _attr_translation_key = "schedule"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_assumed_state = False

    def __init__(self, entry: WeekAquaConfigEntry) -> None:
        super().__init__(entry, "schedule")

    @property
    def is_on(self) -> bool:
        return self._lamp.settings.schedule_enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._lamp.async_set_schedule(enabled=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._lamp.async_set_schedule(enabled=False)
