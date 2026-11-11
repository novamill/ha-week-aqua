"""Week Aqua BLE protocol.

Pure Python (no Home Assistant imports) so it can be unit tested and reused by
the bench CLI. Reverse engineered from the WEEKAQUA Android app v3.0.25 and
verified against HCI captures of a 5746-type lamp.

Wire format notes
-----------------
* All commands are written (without response) to characteristic FFF2.
* Frames are 8 bytes; unused bytes are padded with 0x55.
* Times are BCD encoded: 07:29 is sent as 0x07 0x29, not 0x07 0x1D.
* The devices are write-only: there is no state read-back. The TI OAD service
  (f000ffc0-...) exposed by the lamps is the firmware-update service and must
  never be written to.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from enum import IntEnum, StrEnum

WRITE_CHAR_UUID = "0000fff2-0000-1000-8000-00805f9b34fb"
# Some hardware revisions expose the write endpoint on FFE1/FFE3 instead.
FALLBACK_WRITE_CHAR_UUIDS = (
    "0000ffe1-0000-1000-8000-00805f9b34fb",
    "0000ffe3-0000-1000-8000-00805f9b34fb",
)

PAD = 0x55
FRAME_LEN = 8


class DeviceKind(StrEnum):
    """Supported product families."""

    LIGHT_RGBUV = "light_rgbuv"
    PUMP = "pump"


# The app reads two bytes from the advertisement (the BLE company ID field) and
# compares them as a hex string: "5746", "5751", ... As a little-endian company
# ID these are 0x4657, 0x5157, ...
TYPE_CODE_BY_MANUFACTURER_ID: dict[int, str] = {
    0x4557: "5745",  # HJ   - multi-mode light (not supported yet)
    0x4657: "5746",  # WEK  - 4 channel R/G/B/UV light
    0x4757: "5747",  # FOUR - 7 channel light (not supported yet)
    0x4857: "5748",  # FIVE - 10 channel light (not supported yet)
    0x4957: "5749",  # SIX  - WW/CW light (not supported yet)
    0x5057: "5750",  # SEVEN - 6 socket power strip (not supported yet)
    0x5157: "5751",  # EIGHT - filter / wave pump
    0x5257: "5752",  # NINE - 7 channel light (not supported yet)
}

KIND_BY_MANUFACTURER_ID: dict[int, DeviceKind] = {
    0x4657: DeviceKind.LIGHT_RGBUV,
    0x5157: DeviceKind.PUMP,
}


@dataclass(frozen=True, slots=True)
class AdvertisementInfo:
    """Information decoded from a Week Aqua advertisement."""

    kind: DeviceKind
    type_code: str
    mac: str | None


def parse_advertisement(manufacturer_data: dict[int, bytes]) -> AdvertisementInfo | None:
    """Decode manufacturer data. Returns None for unsupported devices.

    Payload layout after the company ID: ``00 01 <6 byte MAC>``.
    """
    for manufacturer_id, payload in manufacturer_data.items():
        kind = KIND_BY_MANUFACTURER_ID.get(manufacturer_id)
        if kind is None:
            continue
        mac = None
        if len(payload) >= 8:
            mac = ":".join(f"{b:02X}" for b in payload[2:8])
        return AdvertisementInfo(kind, TYPE_CODE_BY_MANUFACTURER_ID[manufacturer_id], mac)
    return None


def _frame(*body: int) -> bytes:
    if len(body) > FRAME_LEN:
        raise ValueError("frame too long")
    if any(not 0 <= b <= 0xFF for b in body):
        raise ValueError(f"byte out of range in {body}")
    return bytes(body) + bytes([PAD] * (FRAME_LEN - len(body)))


def _bcd(value: int) -> int:
    if not 0 <= value <= 99:
        raise ValueError(f"cannot BCD encode {value}")
    return (value // 10) << 4 | (value % 10)


# --------------------------------------------------------------------------
# Commands shared by all device types
# --------------------------------------------------------------------------


def cmd_sync_clock(now: datetime | time) -> bytes:
    """Set the device's internal clock (used by its built-in schedule)."""
    return _frame(0xFF, _bcd(now.hour), _bcd(now.minute), _bcd(now.second))


def cmd_manual_mode() -> bytes:
    """Switch to manual mode (fixed output + optional daily on/off window)."""
    return _frame(0xFD, 0xF1)


def cmd_auto_mode() -> bytes:
    """Switch to the multi-point program stored in the device."""
    return _frame(0xFD, 0xF2)


# --------------------------------------------------------------------------
# 5746 R/G/B/UV light
# --------------------------------------------------------------------------

LIGHT_CHANNELS = ("red", "green", "blue", "uv")
LIGHT_LEVEL_MAX = 0xEB  # 100 %
# Relative power draw of each channel, used by the app to cap total load.
LIGHT_POWER_WEIGHTS = (0.39, 0.41, 0.53, 0.11)
LIGHT_POWER_BUDGET = 100.0

RAMP_MINUTES_TO_CODE = {0: 0, 30: 1, 60: 2, 90: 3, 120: 4, 150: 5}


def light_power_load(levels: tuple[float, float, float, float]) -> float:
    """Return the weighted power load (app limit is 100)."""
    return sum(level * weight for level, weight in zip(levels, LIGHT_POWER_WEIGHTS, strict=True))


def limit_light_power(
    levels: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    """Scale channel percentages down proportionally to stay within budget."""
    clamped = tuple(min(100.0, max(0.0, level)) for level in levels)
    load = light_power_load(clamped)  # type: ignore[arg-type]
    if load <= LIGHT_POWER_BUDGET:
        return clamped  # type: ignore[return-value]
    factor = LIGHT_POWER_BUDGET / load
    return tuple(level * factor for level in clamped)  # type: ignore[return-value]


def _pct_to_level(pct: float) -> int:
    level = round(pct / 100.0 * LIGHT_LEVEL_MAX)
    return max(0, min(LIGHT_LEVEL_MAX, level))


def cmd_light_levels(red: float, green: float, blue: float, uv: float) -> bytes:
    """Set the four channels (percent, 0-100). Power budget is enforced."""
    levels = limit_light_power((red, green, blue, uv))
    return _frame(0xFB, 0xF9, *(_pct_to_level(level) for level in levels))


def cmd_light_off() -> bytes:
    return _frame(0xFB, 0xF9, 0, 0, 0, 0)


def cmd_light_schedule(on: time, off: time | None, ramp_minutes: int = 0) -> bytes:
    """Daily on/off window used in manual mode.

    ``off=None`` encodes 24:00. ``on=00:00, off=None`` means always on, which is
    what the integration uses when Home Assistant is in charge of scheduling.
    """
    if ramp_minutes not in RAMP_MINUTES_TO_CODE:
        raise ValueError(f"ramp must be one of {sorted(RAMP_MINUTES_TO_CODE)}")
    off_h, off_m = (24, 0) if off is None else (off.hour, off.minute)
    return bytes(
        [
            0xFE,
            0xF9,
            _bcd(on.hour),
            _bcd(on.minute),
            _bcd(off_h),
            _bcd(off_m),
            0x00,
            RAMP_MINUTES_TO_CODE[ramp_minutes],
        ]
    )


def cmd_light_always_on() -> bytes:
    return cmd_light_schedule(time(0, 0), None, 0)


# --------------------------------------------------------------------------
# 5751 pump
# --------------------------------------------------------------------------


class PumpMode(IntEnum):
    """Pump flow patterns (second byte of the FB frame)."""

    CONSTANT = 0xF9
    WAVY = 0xFA
    SURGE = 0xFB
    TIDE = 0xFD
    CYCLE = 0xFE


PUMP_FEED = 0xFC
PUMP_POWER_MIN = 0x30
PUMP_POWER_MAX = 0xF0
PUMP_FEED_MINUTES = tuple(range(5, 61, 5))


def pump_power_byte(percent: int) -> int:
    """Map 0-100 % to the pump's power byte (0 = stopped, 1-100 -> 0x30..0xF0)."""
    if not 0 <= percent <= 100:
        raise ValueError("percent must be 0-100")
    if percent == 0:
        return 0
    return PUMP_POWER_MIN + (PUMP_POWER_MAX - PUMP_POWER_MIN) * percent // 100


def cmd_pump(mode: PumpMode, percent: int) -> bytes:
    return _frame(0xFB, PumpMode(mode), pump_power_byte(percent))


def cmd_pump_feed(minutes: int) -> bytes:
    """Pause the pump for feeding. Device resumes on its own afterwards."""
    if minutes not in PUMP_FEED_MINUTES:
        raise ValueError(f"feed minutes must be one of {PUMP_FEED_MINUTES}")
    return _frame(0xFB, PUMP_FEED, _bcd(minutes))


# --------------------------------------------------------------------------
# Bluetooth name (handled by the BLE module itself, not the lamp controller)
# --------------------------------------------------------------------------

NAME_COMMAND_PREFIX = b"!%!%:ADV_NAME:"
# The app does not limit the length. 20 printable ASCII characters keep the
# name well inside an advertising packet.
NAME_MAX_LEN = 20
NAME_PATTERN = r"^[ -~]{1,20}$"


def cmd_set_name(name: str) -> bytes:
    """Change the advertised Bluetooth name. Stored by the module.

    Unlike the 8-byte frames this is variable length ASCII, so it needs an
    ATT MTU above the 23-byte default; the app requests 128 before sending.
    """
    if not 1 <= len(name) <= NAME_MAX_LEN or not all(" " <= c <= "~" for c in name):
        raise ValueError(f"name must be 1-{NAME_MAX_LEN} printable ASCII characters")
    return NAME_COMMAND_PREFIX + name.encode("ascii")
