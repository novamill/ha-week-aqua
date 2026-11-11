"""Time platform: on and off time of the lamp's built-in schedule."""

from __future__ import annotations

from datetime import time

from homeassistant.components.time import TimeEntity
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
    async_add_entities([WeekAquaScheduleTime(entry, "on_time"), WeekAquaScheduleTime(entry, "off_time")])


class WeekAquaScheduleTime(WeekAquaLampEntity, TimeEntity):
    """Daily on or off time of the lamp's built-in schedule.

    Sent to the lamp only while the built-in schedule switch is on. An off
    time of 00:00 means midnight.
    """

    _attr_entity_category = EntityCategory.CONFIG
    _attr_assumed_state = False

    def __init__(self, entry: WeekAquaConfigEntry, key: str) -> None:
        super().__init__(entry, f"schedule_{key}")
        self._key = key
        self._attr_translation_key = f"schedule_{key}"

    @property
    def native_value(self) -> time:
        return getattr(self._lamp.settings, self._key)

    async def async_set_value(self, value: time) -> None:
        await self._lamp.async_set_schedule(**{self._key: value})
