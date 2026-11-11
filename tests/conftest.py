"""Fixtures for Week Aqua tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from bleak.backends.device import BLEDevice
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo
import pytest

LIGHT_ADDRESS = "C8:47:80:00:00:30"
PUMP_ADDRESS = "C8:47:80:00:01:30"


def make_service_info(name: str, address: str, mfr_id: int, payload: str) -> BluetoothServiceInfoBleak:
    from bleak.backends.scanner import AdvertisementData

    device = BLEDevice(address, name, {})
    adv = AdvertisementData(
        local_name=name,
        manufacturer_data={mfr_id: bytes.fromhex(payload)},
        service_data={},
        service_uuids=["0000fff0-0000-1000-8000-00805f9b34fb"],
        tx_power=None,
        rssi=-60,
        platform_data=(),
    )
    return BluetoothServiceInfoBleak(
        name=name,
        address=address,
        rssi=-60,
        manufacturer_data=adv.manufacturer_data,
        service_data={},
        service_uuids=adv.service_uuids,
        source="local",
        device=device,
        advertisement=adv,
        connectable=True,
        time=0,
        tx_power=None,
    )


LIGHT_INFO = make_service_info("B3.0-Mini9Pro-30", LIGHT_ADDRESS, 0x4657, "0001c84780000030")
PUMP_INFO = make_service_info("B8.0-ES350-130", PUMP_ADDRESS, 0x5157, "0001c84780000130")
UNSUPPORTED_INFO = make_service_info("strip", "C8:47:80:00:09:99", 0x5057, "0001c84780000999")


@pytest.fixture(autouse=True)
def auto_enable(enable_custom_integrations, mock_bluetooth) -> None:
    """Enable custom integrations and mock the Bluetooth stack."""


@pytest.fixture
def mock_send() -> Generator[AsyncMock]:
    """Capture every frame the integration writes, without touching BLE."""
    with (
        patch(
            "custom_components.week_aqua.device.WeekAquaDevice.send", autospec=True
        ) as send,
        patch(
            "custom_components.week_aqua.bluetooth.async_ble_device_from_address",
            side_effect=lambda hass, address, connectable: BLEDevice(address, "x", {}),
        ),
        patch(
            "custom_components.week_aqua.bluetooth.async_register_callback",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.week_aqua.bluetooth.async_track_unavailable",
            return_value=MagicMock(),
        ),
    ):
        yield send


def sent_frames(send: AsyncMock) -> list[str]:
    """Flatten all frames passed to WeekAquaDevice.send into hex strings."""
    return [frame.hex() for call in send.call_args_list for frame in call.args[1:]]


__all__ = ["BluetoothServiceInfo", "sent_frames"]
