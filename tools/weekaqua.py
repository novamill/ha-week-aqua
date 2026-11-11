#!/usr/bin/env python3
"""Bench CLI for Week Aqua devices (no Home Assistant needed).

    pip install bleak
    python tools/weekaqua.py scan
    python tools/weekaqua.py light  <name-or-address> 80 60 70 40     # R G B UV %
    python tools/weekaqua.py off    <name-or-address>
    python tools/weekaqua.py schedule <name-or-address> 08:00 20:00 --ramp 60
    python tools/weekaqua.py pump   <name-or-address> constant 70
    python tools/weekaqua.py feed   <name-or-address> 10
    python tools/weekaqua.py sync   <name-or-address>
    python tools/weekaqua.py rename <name-or-address> "B3.0-Left"

Uses the same protocol module as the integration. Close the phone app first:
the devices accept a single connection.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
from datetime import datetime, time
import importlib.util
from pathlib import Path
import sys

from bleak import BleakClient, BleakScanner

_spec = importlib.util.spec_from_file_location(
    "week_aqua_protocol",
    Path(__file__).resolve().parent.parent / "custom_components/week_aqua/protocol.py",
)
p = importlib.util.module_from_spec(_spec)
sys.modules["week_aqua_protocol"] = p
_spec.loader.exec_module(p)


def _matches(target: str, address: str, name: str) -> bool:
    t = target.lower()
    return t == address.lower() or t in name.lower()


# Week Aqua devices of a type the integration doesn't support yet, seen by scan().
_unsupported: dict[str, tuple[str, str]] = {}


async def scan(
    duration: float = 15.0, target: str | None = None
) -> dict[str, tuple[str, p.AdvertisementInfo]]:
    """Scan for devices. With a target, stop as soon as it is seen.

    Some devices (e.g. the ES350 pump) advertise only every few seconds, so
    short scans can miss them.
    """
    found: dict[str, tuple[str, p.AdvertisementInfo]] = {}
    hit = asyncio.Event()

    def cb(dev, adv):
        for mfr_id in adv.manufacturer_data:
            if mfr_id in p.TYPE_CODE_BY_MANUFACTURER_ID and mfr_id not in p.KIND_BY_MANUFACTURER_ID:
                code = p.TYPE_CODE_BY_MANUFACTURER_ID[mfr_id]
                _unsupported[dev.address] = (adv.local_name or dev.name or "?", code)
        if info := p.parse_advertisement(adv.manufacturer_data):
            name = adv.local_name or dev.name or "?"
            found[dev.address] = (name, info)
            if target and _matches(target, dev.address, name):
                hit.set()

    async with BleakScanner(cb):
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(hit.wait(), duration)
    return found


async def resolve(target: str) -> str:
    found = await scan(30.0, target)
    for address, (name, _info) in found.items():
        if _matches(target, address, name):
            return address
    sys.exit(f"{target!r} not found within 30 s; is the phone app connected to it?")


async def send(target: str, *frames: bytes) -> None:
    address = await resolve(target)
    async with BleakClient(address) as client:
        candidates = (p.WRITE_CHAR_UUID, *p.FALLBACK_WRITE_CHAR_UUIDS)
        char = next((u for u in candidates if client.services.get_characteristic(u)), None)
        if char is None:
            sys.exit("write characteristic not found")
        print(f"MTU {client.mtu_size}")
        for frame in (p.cmd_sync_clock(datetime.now()), *frames):
            print(f"-> {frame.hex()}")
            await client.write_gatt_char(char, frame, response=False)
            await asyncio.sleep(0.25)


def hhmm(s: str) -> time:
    return time.fromisoformat(s)


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("scan")

    def device_cmd(name: str) -> argparse.ArgumentParser:
        parser = sub.add_parser(name)
        parser.add_argument("target", help="name (or part of it) or address")
        return parser

    s = device_cmd("light")
    for channel in p.LIGHT_CHANNELS:
        s.add_argument(channel, type=float, help=f"{channel} percent")
    device_cmd("off")
    device_cmd("always-on")
    device_cmd("sync")
    s = device_cmd("schedule")
    s.add_argument("on", type=hhmm)
    s.add_argument("off", type=hhmm)
    s.add_argument("--ramp", type=int, default=0, choices=sorted(p.RAMP_MINUTES_TO_CODE))
    s = device_cmd("pump")
    s.add_argument("mode", choices=[m.name.lower() for m in p.PumpMode])
    s.add_argument("percent", type=int)
    s = device_cmd("rename")
    s.add_argument("name", help=f"new Bluetooth name, max {p.NAME_MAX_LEN} ASCII characters")
    s = device_cmd("feed")
    s.add_argument("minutes", type=int, choices=p.PUMP_FEED_MINUTES)
    a = ap.parse_args()

    if a.cmd == "scan":
        for address, (name, info) in asyncio.run(scan()).items():
            print(f"{address}  {name:24} type={info.type_code} kind={info.kind} mac={info.mac}")
        for address, (name, code) in _unsupported.items():
            print(f"{address}  {name:24} type={code} (not supported yet)")
        return
    frames: tuple[bytes, ...] = {
        "light": lambda: (
            p.cmd_manual_mode(),
            p.cmd_light_levels(a.red, a.green, a.blue, a.uv),
        ),
        "off": lambda: (p.cmd_manual_mode(), p.cmd_light_off()),
        "schedule": lambda: (
            p.cmd_manual_mode(),
            p.cmd_light_schedule(a.on, a.off, a.ramp),
        ),
        "always-on": lambda: (p.cmd_manual_mode(), p.cmd_light_always_on()),
        "pump": lambda: (
            p.cmd_manual_mode(),
            p.cmd_pump(p.PumpMode[a.mode.upper()], a.percent),
        ),
        "feed": lambda: (p.cmd_pump_feed(a.minutes),),
        "sync": lambda: (),
        "rename": lambda: (p.cmd_set_name(a.name),),
    }[a.cmd]()
    asyncio.run(send(a.target, *frames))


if __name__ == "__main__":
    main()
