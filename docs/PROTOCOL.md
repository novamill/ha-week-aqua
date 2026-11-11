# Week Aqua Bluetooth protocol

This document describes what this integration knows about the protocol. It
was worked out from the official Android app and from Bluetooth captures. It
is not official documentation and may be incomplete.

Status markers:

* ✅ **verified on hardware:** tested on a real device.
* 🔍 **from the app:** decoded from the app; not yet tested.

## Hardware

The lamps opened so far (Mini9 Pro V3.0 and one other model) have a generic
**Beken BK3432** Bluetooth Low Energy module and a separate **STC 8051**
microcontroller that drives the LEDs. An RTC chip with a coin cell keeps the
time when the lamp is unplugged.

The Bluetooth module reports these Device Information values:

* manufacturer `BEKEN SAS`
* model `BK-BLE-1.0`
* firmware `6.1.2`
* software `6.3.0`

The module appears to pass data through to the microcontroller, except for
its own configuration commands (see [Renaming](#renaming)).

## Discovery

Devices advertise manufacturer-specific data. The 16-bit company ID encodes
the device type as two ASCII digits in little-endian order. The payload is
`00 01` followed by the device's 6-byte MAC address.

| Company ID | Type | App name | Device | Integration |
|---|---|---|---|---|
| `0x4557` | `5745` | HJ | Multi-mode light | — |
| `0x4657` | `5746` | WEK | R/G/B/UV light | ✅ supported |
| `0x4757` | `5747` | FOUR | 7-channel light | — |
| `0x4857` | `5748` | FIVE | 10-channel light | — |
| `0x4957` | `5749` | SIX | Warm/cool white light | — |
| `0x5057` | `5750` | SEVEN | 6-socket power strip | — |
| `0x5157` | `5751` | EIGHT | Filter / wave pump | ✅ supported |
| `0x5257` | `5752` | NINE | 7-channel light | — |

Advertised names follow `B<hardware>.<rev>-<model>-<n>`, for example
`B3.0-Mini9Pro-30` or `B8.0-ES350-130`. Users can change them (see
[Renaming](#renaming)).

## GATT

| UUID | Properties | Use |
|---|---|---|
| `0000fff0-…` service | | Vendor service |
| `0000fff2-…` | write without response | **Command channel** |
| `0000fff1-…` | read, notify | Module → app. The lamps tested never send anything here. |
| `0000ffe1-…`, `0000ffe3-…` | write | Command channel on some other hardware (used if `fff2` is missing) |
| `0000180a-…` | read | Device Information |
| `f000ffc0-…` service (`ffc1` "Img Identify", `ffc2` "Img Block") | write, notify | **Firmware update (OAD).** Never write to it. |

There is no way to read a device's settings back. The integration keeps the
last values it sent and stores them across restarts.

## Command frames

Commands are **8 bytes**, padded with `0x55`, written without response to
`fff2`. The app waits 500 ms between frames; 150 ms works fine.

**Times are BCD:** 07:29 is sent as `07 29`, not `07 1D`.

### Common

| Frame | Meaning | |
|---|---|---|
| `FF hh mm ss 55 55 55 55` | Set the device clock (BCD, local time) | ✅ |
| `FD F1 55 55 55 55 55 55` | Manual mode (fixed levels and a daily window) | ✅ |
| `FD F2 55 55 55 55 55 55` | Auto mode (the app's multi-point program) | 🔍 |

The app sends `FD F1` before every manual-mode command, and so does this
integration.

### R/G/B/UV light (`5746`)

| Frame | Meaning | |
|---|---|---|
| `FB F9 rr gg bb uu 55 55` | Channel levels red, green, blue, UV. `0x00`–`0xEB` = 0–100 % | ✅ |
| `FE F9 h1 m1 h2 m2 00 rr` | Daily window: on at `h1:m1`, off at `h2:m2` (BCD). `rr` = ramp code | ✅ |
| `FE F9 00 00 24 00 00 00` | Window 00:00–24:00, i.e. always on (schedule disabled) | ✅ |

The level byte is `round(percent × 235 / 100)`.

The ramp code sets the sunrise and sunset fade length (one value for both):

| `rr` | 0 | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|---|
| minutes | 0 | 30 | 60 | 90 | 120 | 150 |

An off time of `24 00` means midnight. The byte before `rr` is a flag the app
can toggle; it always sends `00` for this model.

The lamp runs its window at the channel levels last sent with `FB F9`.

**Power budget.** The app never sends a mix where

```
0.39·R + 0.41·G + 0.53·B + 0.11·UV > 100      (R, G, B, UV in percent)
```

The board takes 9 W at 5 V. When a requested mix exceeds the budget, the
integration scales all four channels down by the same factor.

### Pump (`5751`)

| Frame | Meaning | |
|---|---|---|
| `FB mm pp 55 55 55 55 55` | Set pattern `mm` and power `pp` | ✅ |
| `FB FC tt 55 55 55 55 55` | Feed pause for `tt` minutes (BCD, 05–60). The pump resumes by itself. | ✅ |

The pattern byte `mm`:

| `mm` | Pattern | |
|---|---|---|
| `F9` | Constant | ✅ |
| `FA` | Wavy | 🔍 |
| `FB` | Surge | ✅ |
| `FD` | Tide | 🔍 |
| `FE` | Cycle | 🔍 |

Power byte `pp`:

* `00` stops the pump.
* Otherwise `pp = 0x30 + 192 × percent // 100`, giving `0x31`–`0xF0`.
* Example: 38 % → `0x78`.

## Renaming

| Payload | Meaning | |
|---|---|---|
| ASCII `!%!%:ADV_NAME:<name>` | Set the advertised name; takes effect immediately | ✅ (light) |

The Bluetooth module handles this command itself and stores the name. It is
longer than 20 bytes, so it needs an ATT MTU above the 23-byte default. The
app requests an MTU of 128 first. The integration limits names to 20
printable ASCII characters.

Other app device families use `AT+NAME=<name>` instead.

## Capturing traffic for other models

To add a model, capture what the official app sends:

1. On Android, enable **Developer options → Enable Bluetooth HCI snoop log**.
   Toggle Bluetooth off and on.
2. In the Week Aqua app, use each control once. Note the time and value of
   each action.
3. Create a bug report (`adb bugreport`) and extract `btsnoop_hci.log`.
4. Open it in Wireshark with the filter `btatt.opcode == 0x52`
   (write command) and match the frames to your notes.

Then open a *New device support* issue with the log and your notes.
