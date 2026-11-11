"""Select platform: sunrise/sunset length of the lamp's built-in schedule."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import WeekAquaConfigEntry
from .entity import WeekAquaLampEntity
from .protocol import RAMP_MINUTES_TO_CODE

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WeekAquaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([WeekAquaRampSelect(entry)])


class WeekAquaRampSelect(WeekAquaLampEntity, SelectEntity):
    """Fade length after the on time and before the off time.

    The lamp has one setting for both sunrise and sunset, 0-150 minutes.
    """

    _attr_translation_key = "schedule_ramp"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_assumed_state = False
    _attr_options = [str(m) for m in sorted(RAMP_MINUTES_TO_CODE)]

    def __init__(self, entry: WeekAquaConfigEntry) -> None:
        super().__init__(entry, "schedule_ramp")

    @property
    def current_option(self) -> str:
        return str(self._lamp.settings.ramp)

    async def async_select_option(self, option: str) -> None:
        await self._lamp.async_set_schedule(ramp=int(option))
