# Contributing

Thanks for helping! Contributions of every size are welcome: bug reports,
captures from models that aren't supported yet, documentation and code.

## Reporting a bug

Open a [bug report](https://github.com/novamill/ha-week-aqua/issues/new?template=bug_report.yml)
and include:

- the diagnostics download (**device page → ⋮ → Download diagnostics**)
- a debug log (`custom_components.week_aqua: debug`)

## Adding a device type

The integration supports the R/G/B/UV lights (`5746`) and pumps (`5751`).
Other models need captures of what the official app sends. See
[Capturing traffic](docs/PROTOCOL.md#capturing-traffic-for-other-models),
then open a [new device issue](https://github.com/novamill/ha-week-aqua/issues/new?template=new_device.yml).

**Never write to the `f000ffc0` service while experimenting.** It is the
firmware-update channel and can brick the device.

## Development setup

You need Python 3.13 and [uv](https://docs.astral.sh/uv/) (or plain `pip`):

```sh
git clone https://github.com/novamill/ha-week-aqua
cd ha-week-aqua
uv venv -p 3.13
uv pip install -r requirements_test.txt
.venv/bin/pytest
.venv/bin/ruff check .
```

The code is organised in layers:

| File | Responsibility |
|---|---|
| `protocol.py` | Pure frame encoders and advertisement parsing; no Home Assistant imports. Shared with `tools/weekaqua.py`. |
| `device.py` | BLE connection handling: connect on demand, one retry, idle disconnect, clock sync. |
| `lamp.py` | Shared, persisted state of a lamp, used by all its entities. |
| `light.py`, `fan.py`, … | Thin entity platforms. |

To try changes on real hardware without Home Assistant, use
`python tools/weekaqua.py`.

## Pull requests

- Keep each change focused, and add or update tests.
  `tests/test_integration.py` checks the exact bytes sent for each action.
- `pytest` and `ruff check .` must pass. CI also runs hassfest and the HACS
  validation.
- Add an entry under *Unreleased* in `CHANGELOG.md` for user-visible changes.
- Say what you tested on real hardware and which model.

## Releasing (maintainers)

1. Update the `version` in `custom_components/week_aqua/manifest.json` and
   in `CHANGELOG.md`.
2. Tag `vX.Y.Z` and publish a GitHub release. A workflow checks that the tag
   matches the manifest.
