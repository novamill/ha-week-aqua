# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [0.4.0] - 2026-11-25

### Added

- Dashboard cards for lights and pumps, installed with the integration:
  - light card: brightness slider that keeps the colour proportions, one
    slider per channel, the built-in schedule and sunrise/sunset buttons
  - pump card: strength slider, one button per wave pattern, and feed pause
    with a countdown
  - English and Hungarian text

### Changed

- Changing only the light's brightness now scales the stored channel mix
  exactly, so the proportions don't drift.

## [0.3.2] - 2026-11-14

### Added

- Hungarian translation.
- Translated names for the pump's wave patterns.

### Changed

- Pump flow is rounded to the nearest step, matching the official app exactly
  (e.g. 30 % now sends `0x6A` instead of `0x69`).
- Light colour mixes are kept within both known versions of the app's LED
  power limit. Very bright mixes may be scaled down slightly more than before.

## [0.3.1] - 2026-11-13

### Added

- Screenshots of the light and pump in the README.

### Changed

- The project moved to [novamill/ha-week-aqua](https://github.com/novamill/ha-week-aqua).
  If you added the old repository to HACS, remove it and add the new one.

## [0.3.0] - 2026-11-11

First public release.

### Added

- R/G/B/UV lights (type `5746`):
  - light entity with RGBW colour (W = UV) and brightness
  - per-channel sliders
  - built-in schedule switch, on/off times and sunrise/sunset length
  - `set_schedule` and `clear_schedule` actions
- Filter and wave pumps (type `5751`): flow and pattern as a fan entity, plus a
  feed pause button and duration.
- **Bluetooth name** entity on every device. It shows the advertised name and
  renames the device.
- Bluetooth discovery. Connects on demand through local adapters or ESPHome
  proxies and disconnects after 15 s idle.
- Clock sync on every connection and daily at 03:07.
- The app's LED power budget is enforced.
- Lamp settings persist across restarts.
- Diagnostics download.
- A use-at-your-own-risk disclaimer that must be accepted when the first
  device is added.
- `tools/weekaqua.py`, a command-line tool for testing without Home Assistant.

[0.4.0]: https://github.com/novamill/ha-week-aqua/releases/tag/v0.4.0
[0.3.2]: https://github.com/novamill/ha-week-aqua/releases/tag/v0.3.2
[0.3.1]: https://github.com/novamill/ha-week-aqua/releases/tag/v0.3.1
[0.3.0]: https://github.com/novamill/ha-week-aqua/releases/tag/v0.3.0
