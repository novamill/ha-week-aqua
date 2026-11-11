"""The Week Aqua integration."""

from __future__ import annotations

from datetime import datetime
import logging

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.event import async_track_time_change

from .const import CLOCK_SYNC_HOUR, CLOCK_SYNC_MINUTE, CONF_KIND
from .device import WeekAquaDevice, WeekAquaError
from .lamp import LampController, async_remove_settings
from .protocol import DeviceKind

_LOGGER = logging.getLogger(__name__)

PLATFORMS_BY_KIND: dict[DeviceKind, list[Platform]] = {
    DeviceKind.LIGHT_RGBUV: [
        Platform.BUTTON,
        Platform.LIGHT,
        Platform.NUMBER,
        Platform.SELECT,
        Platform.SWITCH,
        Platform.TEXT,
        Platform.TIME,
    ],
    DeviceKind.PUMP: [Platform.BUTTON, Platform.FAN, Platform.NUMBER, Platform.TEXT],
}

type WeekAquaConfigEntry = ConfigEntry[WeekAquaDevice]


async def async_setup_entry(hass: HomeAssistant, entry: WeekAquaConfigEntry) -> bool:
    """Set up a Week Aqua device from a config entry."""
    address: str = entry.data[CONF_ADDRESS]
    kind = DeviceKind(entry.data[CONF_KIND])

    ble_device = bluetooth.async_ble_device_from_address(hass, address, connectable=True)
    if ble_device is None:
        raise ConfigEntryNotReady(
            f"{entry.title} ({address}) is not in range of any connectable Bluetooth adapter or proxy"
        )

    device = WeekAquaDevice(hass, ble_device, kind, entry.title)
    if kind is DeviceKind.LIGHT_RGBUV:
        device.lamp = LampController(hass, device, entry.entry_id)
        await device.lamp.async_load()
    entry.runtime_data = device

    @callback
    def _on_advertisement(
        service_info: bluetooth.BluetoothServiceInfoBleak,
        _change: bluetooth.BluetoothChange,
    ) -> None:
        device.set_ble_device(service_info.device, service_info.name)
        device.set_available(True)

    @callback
    def _on_unavailable(_service_info: bluetooth.BluetoothServiceInfoBleak) -> None:
        device.set_available(False)

    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            _on_advertisement,
            bluetooth.BluetoothCallbackMatcher(address=address, connectable=True),
            bluetooth.BluetoothScanningMode.PASSIVE,
        )
    )
    entry.async_on_unload(
        bluetooth.async_track_unavailable(hass, _on_unavailable, address, connectable=True)
    )

    # Keep the device clock right (drift + DST) so its built-in schedule,
    # if used, fires at the correct local time. Stagger by address so not all
    # devices compete for the radio at once.
    second = sum(address.encode()) % 60

    async def _daily_sync(_now: datetime) -> None:
        try:
            await device.sync_clock()
        except WeekAquaError as err:
            _LOGGER.warning("Daily clock sync failed for %s: %s", entry.title, err)

    entry.async_on_unload(
        async_track_time_change(
            hass, _daily_sync, hour=CLOCK_SYNC_HOUR, minute=CLOCK_SYNC_MINUTE, second=second
        )
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS_BY_KIND[kind])
    return True


async def async_unload_entry(hass: HomeAssistant, entry: WeekAquaConfigEntry) -> bool:
    """Unload a config entry."""
    kind = DeviceKind(entry.data[CONF_KIND])
    if unload_ok := await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS_BY_KIND[kind]
    ):
        if (lamp := entry.runtime_data.lamp) is not None:
            await lamp.async_flush()
        await entry.runtime_data.async_shutdown()
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: WeekAquaConfigEntry) -> None:
    """Delete stored lamp settings when the device is removed."""
    if DeviceKind(entry.data[CONF_KIND]) is DeviceKind.LIGHT_RGBUV:
        await async_remove_settings(hass, entry.entry_id)
