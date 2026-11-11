"""BLE connection manager for a single Week Aqua device."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import logging
from typing import TYPE_CHECKING

from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from bleak_retry_connector import (
    BleakClientWithServiceCache,
    close_stale_connections_by_address,
    establish_connection,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.util import dt as dt_util

from .const import DISCONNECT_DELAY, FRAME_GAP
from .protocol import (
    FALLBACK_WRITE_CHAR_UUIDS,
    WRITE_CHAR_UUID,
    DeviceKind,
    cmd_set_name,
    cmd_sync_clock,
)

if TYPE_CHECKING:
    from .lamp import LampController

_LOGGER = logging.getLogger(__name__)


class WeekAquaError(Exception):
    """Raised when a command could not be delivered."""


class WeekAquaDevice:
    """Owns the BLE link to one device.

    The devices are write-only, so the connection is opened on demand, the
    clock is synced on every fresh connection, and the link is dropped after a
    short idle period to free up proxy / adapter connection slots.
    """

    def __init__(
        self, hass: HomeAssistant, ble_device: BLEDevice, kind: DeviceKind, name: str
    ) -> None:
        self.hass = hass
        self.kind = kind
        self.name = name
        self._ble_device = ble_device
        # Name the device currently advertises (the app's device name).
        self.advertised_name: str | None = ble_device.name
        self._client: BleakClientWithServiceCache | None = None
        self._write_char: str | None = None
        self._lock = asyncio.Lock()
        self._disconnect_timer: asyncio.TimerHandle | None = None
        self._available = True
        self._listeners: list[Callable[[], None]] = []
        # Pump only: minutes used by the Feed button (set by the number entity).
        self.feed_minutes = 10
        # Lamps only: shared settings, attached during setup.
        self.lamp: LampController | None = None

    # -- availability -------------------------------------------------------

    @property
    def address(self) -> str:
        return self._ble_device.address

    @property
    def available(self) -> bool:
        return self._available

    @callback
    def set_ble_device(self, ble_device: BLEDevice, name: str | None = None) -> None:
        self._ble_device = ble_device
        if name and name != self.advertised_name:
            self.advertised_name = name
            self._notify()

    @callback
    def set_available(self, available: bool) -> None:
        if available != self._available:
            self._available = available
            self._notify()

    @callback
    def _notify(self) -> None:
        for listener in list(self._listeners):
            listener()

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> CALLBACK_TYPE:
        self._listeners.append(listener)

        @callback
        def _remove() -> None:
            self._listeners.remove(listener)

        return _remove

    # -- commands -----------------------------------------------------------

    async def send(self, *frames: bytes) -> None:
        """Write frames in order, connecting first if needed."""
        async with self._lock:
            try:
                await self._send_locked(frames)
            except (BleakError, TimeoutError, OSError) as err:
                # One retry on a fresh connection: proxies occasionally drop
                # idle links without us noticing.
                _LOGGER.debug("%s: write failed (%s), retrying", self.name, err)
                await self._disconnect_locked()
                try:
                    await self._send_locked(frames)
                except (BleakError, TimeoutError, OSError) as err2:
                    await self._disconnect_locked()
                    raise WeekAquaError(f"{self.name}: {err2}") from err2
            self._schedule_disconnect()

    async def set_name(self, name: str) -> None:
        """Rename the device; it advertises the new name from then on."""
        await self.send(cmd_set_name(name))
        self.advertised_name = name
        self._notify()

    async def sync_clock(self) -> None:
        await self.send(cmd_sync_clock(dt_util.now()))

    async def _send_locked(self, frames: tuple[bytes, ...]) -> None:
        client = await self._ensure_connected_locked()
        assert self._write_char is not None
        for frame in frames:
            _LOGGER.debug("%s: write %s", self.name, frame.hex())
            await client.write_gatt_char(self._write_char, frame, response=False)
            await asyncio.sleep(FRAME_GAP)

    async def _ensure_connected_locked(self) -> BleakClientWithServiceCache:
        if self._client is not None and self._client.is_connected:
            return self._client
        _LOGGER.debug("%s: connecting", self.name)
        await close_stale_connections_by_address(self.address)
        client = await establish_connection(
            BleakClientWithServiceCache,
            self._ble_device,
            self.name,
            disconnected_callback=self._on_disconnected,
            ble_device_callback=lambda: self._ble_device,
        )
        char = None
        for uuid in (WRITE_CHAR_UUID, *FALLBACK_WRITE_CHAR_UUIDS):
            if client.services.get_characteristic(uuid) is not None:
                char = uuid
                break
        if char is None:
            await client.disconnect()
            raise BleakError("no Week Aqua write characteristic found")
        self._client = client
        self._write_char = char
        # Every fresh connection re-syncs the clock so the built-in schedule
        # stays correct across drift and DST changes.
        frame = cmd_sync_clock(dt_util.now())
        _LOGGER.debug("%s: write %s (clock sync)", self.name, frame.hex())
        await client.write_gatt_char(char, frame, response=False)
        await asyncio.sleep(FRAME_GAP)
        return client

    # -- connection lifecycle ----------------------------------------------

    def _on_disconnected(self, _client: BleakClientWithServiceCache) -> None:
        _LOGGER.debug("%s: disconnected", self.name)
        self._client = None

    def _schedule_disconnect(self) -> None:
        if self._disconnect_timer:
            self._disconnect_timer.cancel()
        self._disconnect_timer = self.hass.loop.call_later(
            DISCONNECT_DELAY, lambda: self.hass.async_create_task(self._idle_disconnect())
        )

    async def _idle_disconnect(self) -> None:
        async with self._lock:
            await self._disconnect_locked()

    async def _disconnect_locked(self) -> None:
        if self._disconnect_timer:
            self._disconnect_timer.cancel()
            self._disconnect_timer = None
        client, self._client = self._client, None
        if client is not None and client.is_connected:
            try:
                await client.disconnect()
            except BleakError:
                _LOGGER.debug("%s: error while disconnecting", self.name, exc_info=True)

    async def async_shutdown(self) -> None:
        async with self._lock:
            await self._disconnect_locked()
