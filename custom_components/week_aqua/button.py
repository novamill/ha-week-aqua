"""Button platform: clock sync (all devices) and feed pause (pump)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import WeekAquaConfigEntry
from .device import WeekAquaDevice, WeekAquaError
from .entity import WeekAquaEntity
from .protocol import DeviceKind, cmd_pump_feed

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class WeekAquaButtonDescription(ButtonEntityDescription):
    press_fn: Callable[[WeekAquaDevice], Awaitable[None]]
    kinds: frozenset[DeviceKind]


BUTTONS: tuple[WeekAquaButtonDescription, ...] = (
    WeekAquaButtonDescription(
        key="sync_clock",
        translation_key="sync_clock",
        entity_category=EntityCategory.DIAGNOSTIC,
        press_fn=lambda device: device.sync_clock(),
        kinds=frozenset(DeviceKind),
    ),
    WeekAquaButtonDescription(
        key="feed",
        translation_key="feed",
        press_fn=lambda device: device.send(cmd_pump_feed(device.feed_minutes)),
        kinds=frozenset({DeviceKind.PUMP}),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WeekAquaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    kind = entry.runtime_data.kind
    async_add_entities(
        WeekAquaButton(entry, description) for description in BUTTONS if kind in description.kinds
    )


class WeekAquaButton(WeekAquaEntity, ButtonEntity):
    entity_description: WeekAquaButtonDescription
    _attr_assumed_state = False

    def __init__(self, entry: WeekAquaConfigEntry, description: WeekAquaButtonDescription) -> None:
        super().__init__(entry, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        try:
            await self.entity_description.press_fn(self._device)
        except WeekAquaError as err:
            raise HomeAssistantError(str(err)) from err
