"""Protocol tests. Expected frames come from HCI captures of the official app."""

from datetime import time

import pytest

from custom_components.week_aqua import protocol as p


def h(s: str) -> bytes:
    return bytes.fromhex(s)


@pytest.mark.parametrize(
    ("clock", "frame"),
    [
        (time(13, 53, 1), "ff13530155555555"),
        (time(22, 28, 18), "ff22281855555555"),
        (time(22, 57, 51), "ff22575155555555"),
    ],
)
def test_sync_clock_matches_capture(clock, frame):
    assert p.cmd_sync_clock(clock) == h(frame)


def test_mode_frames_match_capture():
    assert p.cmd_manual_mode() == h("fdf1555555555555")
    assert p.cmd_auto_mode() == h("fdf2555555555555")


@pytest.mark.parametrize(
    ("on", "off", "ramp", "frame"),
    [
        (time(7, 29), time(20, 20), 0, "fef9072920200000"),
        (time(7, 20), time(20, 33), 60, "fef9072020330002"),
        (time(7, 20), time(20, 33), 90, "fef9072020330003"),
        (time(7, 15), time(20, 30), 60, "fef9071520300002"),
        (time(0, 0), None, 0, "fef9000024000000"),
    ],
)
def test_light_schedule_matches_capture(on, off, ramp, frame):
    assert p.cmd_light_schedule(on, off, ramp) == h(frame)


def test_light_schedule_rejects_unknown_ramp():
    with pytest.raises(ValueError):
        p.cmd_light_schedule(time(8), time(20), 45)


def test_light_levels():
    assert p.cmd_light_levels(100, 0, 0, 0) == h("fbf9eb0000005555")
    assert p.cmd_light_off() == h("fbf9000000005555")
    # App preset "FBF96CE373EB5555" sits inside the power budget, so it must
    # round-trip unchanged.
    preset = (0x6C / 2.35, 0xE3 / 2.35, 0x73 / 2.35, 0xEB / 2.35)
    assert p.cmd_light_levels(*preset) == h("fbf96ce373eb5555")


def test_light_power_budget_is_enforced():
    frame = p.cmd_light_levels(100, 100, 100, 100)
    levels = [b / p.LIGHT_LEVEL_MAX * 100 for b in frame[2:6]]
    assert p.light_power_load(tuple(levels)) == pytest.approx(100, abs=0.5)
    # Ratios are preserved.
    assert frame[2] == frame[3] == frame[4] == frame[5]


def test_pump_frames():
    assert p.cmd_pump(p.PumpMode.CONSTANT, 0) == h("fbf9005555555555")
    assert p.cmd_pump(p.PumpMode.CONSTANT, 100) == h("fbf9f05555555555")
    assert p.cmd_pump(p.PumpMode.SURGE, 50) == h("fbfb905555555555")
    assert p.cmd_pump(p.PumpMode.TIDE, 1) == h("fbfd315555555555")
    assert p.cmd_pump(p.PumpMode.CYCLE, 100) == h("fbfef05555555555")
    assert p.cmd_pump(p.PumpMode.WAVY, 100) == h("fbfaf05555555555")


def test_pump_feed_is_bcd():
    # App sends the minutes as decimal digits: "FBFC" + "10" + "5555555555".
    assert p.cmd_pump_feed(5) == h("fbfc055555555555")
    assert p.cmd_pump_feed(10) == h("fbfc105555555555")
    assert p.cmd_pump_feed(60) == h("fbfc605555555555")
    with pytest.raises(ValueError):
        p.cmd_pump_feed(7)


def test_parse_advertisement():
    light = p.parse_advertisement({0x4657: h("0001c84780000030")})
    assert light == p.AdvertisementInfo(p.DeviceKind.LIGHT_RGBUV, "5746", "C8:47:80:00:00:30")
    pump = p.parse_advertisement({0x5157: h("0001c84780000130")})
    assert pump is not None and pump.kind is p.DeviceKind.PUMP
    assert p.parse_advertisement({0x5057: h("0001c84780000130")}) is None
    assert p.parse_advertisement({0x004C: h("0215")}) is None


def test_set_name() -> None:
    from custom_components.week_aqua.protocol import cmd_set_name

    assert cmd_set_name("B3.0-Tank") == b"!%!%:ADV_NAME:B3.0-Tank"
    for bad in ("", "x" * 21, "Akvárium"):
        with pytest.raises(ValueError):
            cmd_set_name(bad)
