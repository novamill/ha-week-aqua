# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

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

[0.3.0]: https://github.com/imretomori/ha-week-aqua/releases/tag/v0.3.0
