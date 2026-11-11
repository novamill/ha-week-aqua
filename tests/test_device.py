"""Tests for the BLE connection manager."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.week_aqua.device import WeekAquaDevice, WeekAquaError
from custom_components.week_aqua.protocol import WRITE_CHAR_UUID, DeviceKind


def _client() -> MagicMock:
    client = MagicMock()
    client.is_connected = True
    client.write_gatt_char = AsyncMock()
    client.disconnect = AsyncMock()
    client.services.get_characteristic = lambda uuid: object() if uuid == WRITE_CHAR_UUID else None
    return client


@pytest.fixture
def connect():
    with (
        patch("custom_components.week_aqua.device.establish_connection") as est,
        patch("custom_components.week_aqua.device.close_stale_connections_by_address"),
        patch("custom_components.week_aqua.device.FRAME_GAP", 0),
    ):
        yield est


def _writes(client: MagicMock) -> list[str]:
    return [c.args[1].hex() for c in client.write_gatt_char.call_args_list]


async def test_connect_syncs_clock_then_writes(
    hass: HomeAssistant, connect, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(datetime(2026, 3, 29, 7, 5, 9, tzinfo=dt_util.get_default_time_zone()))
    client = _client()
    connect.return_value = client
    dev = WeekAquaDevice(hass, BLEDevice("AA", "lamp", {}), DeviceKind.LIGHT_RGBUV, "lamp")

    await dev.send(b"\xfd\xf1UUUUUU", b"\xfb\xf9\xeb\x00\x00\x00UU")
    await dev.send(b"\xfb\xf9\x00\x00\x00\x00UU")

    assert connect.call_count == 1  # link reused
    assert _writes(client) == [
        "ff07050955555555",
        "fdf1555555555555",
        "fbf9eb0000005555",
        "fbf9000000005555",
    ]
    assert all(c.kwargs["response"] is False for c in client.write_gatt_char.call_args_list)


async def test_idle_disconnect(hass: HomeAssistant, connect) -> None:
    client = _client()
    connect.return_value = client
    dev = WeekAquaDevice(hass, BLEDevice("AA", "lamp", {}), DeviceKind.LIGHT_RGBUV, "lamp")
    await dev.send(b"\xfd\xf1UUUUUU")
    client.disconnect.assert_not_called()

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=30), fire_all=True)
    await hass.async_block_till_done()
    client.disconnect.assert_awaited_once()


async def test_retry_on_stale_link(hass: HomeAssistant, connect) -> None:
    stale, fresh = _client(), _client()
    stale.write_gatt_char.side_effect = [None, BleakError("gone")]  # clock ok, cmd fails
    connect.side_effect = [stale, fresh]
    dev = WeekAquaDevice(hass, BLEDevice("AA", "lamp", {}), DeviceKind.PUMP, "pump")

    await dev.send(b"\xfb\xf9\xf0UUUUU")

    assert connect.call_count == 2
    assert _writes(fresh)[1] == "fbf9f05555555555"
    await dev.async_shutdown()


async def test_gives_up_after_retry(hass: HomeAssistant, connect) -> None:
    connect.side_effect = BleakError("out of range")
    dev = WeekAquaDevice(hass, BLEDevice("AA", "lamp", {}), DeviceKind.PUMP, "pump")
    with pytest.raises(WeekAquaError):
        await dev.send(b"\xfb\xf9\xf0UUUUU")


async def test_missing_write_characteristic(hass: HomeAssistant, connect) -> None:
    client = _client()
    client.services.get_characteristic = lambda uuid: None
    connect.return_value = client
    dev = WeekAquaDevice(hass, BLEDevice("AA", "x", {}), DeviceKind.PUMP, "x")
    with pytest.raises(WeekAquaError):
        await dev.send(b"\xfb\xf9\xf0UUUUU")
    client.disconnect.assert_awaited()
