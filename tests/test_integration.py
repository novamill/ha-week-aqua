"""End-to-end tests: HA service calls -> exact frames on the wire."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.const import ATTR_ENTITY_ID, CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.week_aqua.const import CONF_KIND, CONF_RISK_ACCEPTED, DOMAIN

from .conftest import (
    LIGHT_ADDRESS,
    LIGHT_INFO,
    PUMP_ADDRESS,
    PUMP_INFO,
    UNSUPPORTED_INFO,
    sent_frames,
)


async def _setup(hass: HomeAssistant, address: str, kind: str, title: str) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=address,
        title=title,
        data={CONF_ADDRESS: address, CONF_KIND: kind},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


# -- config flow ------------------------------------------------------------


async def test_bluetooth_discovery_creates_entry(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_BLUETOOTH}, data=PUMP_INFO
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["step_id"] == "disclaimer"

    # Setup can't continue without accepting the disclaimer.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_RISK_ACCEPTED: False}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "must_accept"}

    with patch("custom_components.week_aqua.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_RISK_ACCEPTED: True}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "B8.0-ES350-130"
    assert result["data"] == {CONF_ADDRESS: PUMP_ADDRESS, CONF_KIND: "pump", CONF_RISK_ACCEPTED: True}


async def test_disclaimer_asked_only_once(hass: HomeAssistant) -> None:
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=PUMP_ADDRESS,
        data={CONF_ADDRESS: PUMP_ADDRESS, CONF_KIND: "pump", CONF_RISK_ACCEPTED: True},
    ).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_BLUETOOTH}, data=LIGHT_INFO
    )
    with patch("custom_components.week_aqua.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_discovery_of_unsupported_model_aborts(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_BLUETOOTH}, data=UNSUPPORTED_INFO
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_supported"


async def test_user_flow_lists_devices_in_range(hass: HomeAssistant) -> None:
    with patch(
        "custom_components.week_aqua.config_flow.async_discovered_service_info",
        return_value=[LIGHT_INFO, PUMP_INFO, UNSUPPORTED_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: LIGHT_ADDRESS}
    )
    assert result["step_id"] == "disclaimer"
    with patch("custom_components.week_aqua.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_RISK_ACCEPTED: True}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_KIND] == "light_rgbuv"


async def test_user_flow_without_devices_aborts(hass: HomeAssistant) -> None:
    with patch(
        "custom_components.week_aqua.config_flow.async_discovered_service_info",
        return_value=[UNSUPPORTED_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


# -- light ------------------------------------------------------------------


async def test_light(hass: HomeAssistant, mock_send, entity_registry: er.EntityRegistry) -> None:
    await _setup(hass, LIGHT_ADDRESS, "light_rgbuv", "Mini9Pro 30")
    entity_id = "light.mini9pro_30"
    assert hass.states.get(entity_id).state == "off"
    assert hass.states.get("button.mini9pro_30_sync_clock") is not None

    await hass.services.async_call(
        "light",
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, "rgbw_color": (255, 0, 0, 0), "brightness": 255},
        blocking=True,
    )
    assert sent_frames(mock_send) == ["fdf1555555555555", "fbf9eb0000005555"]
    state = hass.states.get(entity_id)
    assert state.state == "on"
    assert state.attributes["assumed_state"] is True
    assert state.attributes["red"] == 100

    # Full white on all four channels exceeds the power budget -> scaled.
    mock_send.reset_mock()
    await hass.services.async_call(
        "light",
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, "rgbw_color": (255, 255, 255, 255)},
        blocking=True,
    )
    frame = bytes.fromhex(sent_frames(mock_send)[1])
    assert frame[2] == frame[3] == frame[4] == frame[5] < 0xEB

    mock_send.reset_mock()
    await hass.services.async_call("light", "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True)
    assert sent_frames(mock_send) == ["fdf1555555555555", "fbf9000000005555"]
    assert hass.states.get(entity_id).state == "off"

    # Turning back on restores the previous mix.
    mock_send.reset_mock()
    await hass.services.async_call("light", "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True)
    assert sent_frames(mock_send)[1] == frame.hex()


async def test_light_schedule_services(hass: HomeAssistant, mock_send) -> None:
    await _setup(hass, LIGHT_ADDRESS, "light_rgbuv", "Mini9Pro 30")
    await hass.services.async_call(
        DOMAIN,
        "set_schedule",
        {ATTR_ENTITY_ID: "light.mini9pro_30", "on_time": "07:29", "off_time": "20:20", "ramp": 60},
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN, "clear_schedule", {ATTR_ENTITY_ID: "light.mini9pro_30"}, blocking=True
    )
    assert sent_frames(mock_send) == [
        "fdf1555555555555",
        "fef9072920200002",
        "fdf1555555555555",
        "fef9000024000000",
    ]


# -- pump -------------------------------------------------------------------


async def test_pump(hass: HomeAssistant, mock_send) -> None:
    await _setup(hass, PUMP_ADDRESS, "pump", "ES350")
    fan = "fan.es350"
    assert hass.states.get(fan).attributes["preset_modes"] == [
        "constant",
        "wavy",
        "surge",
        "tide",
        "cycle",
    ]

    await hass.services.async_call(
        "fan", "turn_on", {ATTR_ENTITY_ID: fan, "percentage": 50, "preset_mode": "surge"}, blocking=True
    )
    assert sent_frames(mock_send) == ["fdf1555555555555", "fbfb905555555555"]
    state = hass.states.get(fan)
    assert state.state == "on" and state.attributes["percentage"] == 50

    mock_send.reset_mock()
    await hass.services.async_call("fan", "turn_off", {ATTR_ENTITY_ID: fan}, blocking=True)
    assert sent_frames(mock_send) == ["fdf1555555555555", "fbfb005555555555"]
    assert hass.states.get(fan).state == "off"

    # Back on: last flow and pattern are restored.
    mock_send.reset_mock()
    await hass.services.async_call("fan", "turn_on", {ATTR_ENTITY_ID: fan}, blocking=True)
    assert sent_frames(mock_send)[1] == "fbfb905555555555"

    mock_send.reset_mock()
    await hass.services.async_call(
        "fan", "set_preset_mode", {ATTR_ENTITY_ID: fan, "preset_mode": "constant"}, blocking=True
    )
    assert sent_frames(mock_send)[1] == "fbf9905555555555"


async def test_pump_feed(hass: HomeAssistant, mock_send) -> None:
    await _setup(hass, PUMP_ADDRESS, "pump", "ES350")
    await hass.services.async_call(
        "number",
        "set_value",
        {ATTR_ENTITY_ID: "number.es350_feed_pause_duration", "value": 20},
        blocking=True,
    )
    await hass.services.async_call(
        "button", "press", {ATTR_ENTITY_ID: "button.es350_feed_pause"}, blocking=True
    )
    assert sent_frames(mock_send) == ["fbfc205555555555"]


async def test_unload(hass: HomeAssistant, mock_send) -> None:
    entry = await _setup(hass, PUMP_ADDRESS, "pump", "ES350")
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_light_channel_sliders(hass: HomeAssistant, mock_send) -> None:
    entry = await _setup(hass, LIGHT_ADDRESS, "light_rgbuv", "Mini9Pro 30")
    for channel, value in (("red", 50), ("green", 0), ("blue", 100), ("uv", 0)):
        await hass.services.async_call(
            "number",
            "set_value",
            {ATTR_ENTITY_ID: f"number.mini9pro_30_{channel}", "value": value},
            blocking=True,
        )
    # Each slider move lights the lamp with the whole mix, like the app.
    last = bytes.fromhex(sent_frames(mock_send)[-1])
    assert last[:2] == b"\xfb\xf9" and last[3] == 0 and last[5] == 0 and last[4] > last[2] > 0

    light = hass.states.get("light.mini9pro_30")
    assert light.state == "on"
    assert light.attributes["rgbw_color"] == (128, 0, 255, 0)
    assert light.attributes["brightness"] == 255
    assert hass.states.get("number.mini9pro_30_red").state == "50"

    # The light's brightness scales the sliders.
    await hass.services.async_call(
        "light", "turn_on", {ATTR_ENTITY_ID: "light.mini9pro_30", "brightness": 128}, blocking=True
    )
    assert hass.states.get("number.mini9pro_30_blue").state == "50"

    # Settings survive a restart of the integration.
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("number.mini9pro_30_blue").state == "50"
    assert hass.states.get("light.mini9pro_30").state == "on"


async def test_light_schedule_entities(hass: HomeAssistant, mock_send) -> None:
    await _setup(hass, LIGHT_ADDRESS, "light_rgbuv", "Mini9Pro 30")
    switch = "switch.mini9pro_30_built_in_schedule"
    assert hass.states.get(switch).state == "off"

    # Editing while the schedule is off only stores the value.
    await hass.services.async_call(
        "time", "set_value", {ATTR_ENTITY_ID: "time.mini9pro_30_schedule_on_time", "time": "07:29"},
        blocking=True,
    )
    await hass.services.async_call(
        "select",
        "select_option",
        {ATTR_ENTITY_ID: "select.mini9pro_30_sunrise_sunset_length", "option": "60"},
        blocking=True,
    )
    assert sent_frames(mock_send) == []

    await hass.services.async_call("switch", "turn_on", {ATTR_ENTITY_ID: switch}, blocking=True)
    assert sent_frames(mock_send) == ["fdf1555555555555", "fef9072920000002"]

    mock_send.reset_mock()
    await hass.services.async_call(
        "time", "set_value", {ATTR_ENTITY_ID: "time.mini9pro_30_schedule_off_time", "time": "00:00"},
        blocking=True,
    )
    assert sent_frames(mock_send)[1] == "fef9072924000002"  # 00:00 off = midnight

    mock_send.reset_mock()
    await hass.services.async_call("switch", "turn_off", {ATTR_ENTITY_ID: switch}, blocking=True)
    assert sent_frames(mock_send) == ["fdf1555555555555", "fef9000024000000"]

    # The service updates the same settings.
    await hass.services.async_call(
        DOMAIN,
        "set_schedule",
        {ATTR_ENTITY_ID: "light.mini9pro_30", "on_time": "09:00", "off_time": "21:30", "ramp": 90},
        blocking=True,
    )
    assert hass.states.get(switch).state == "on"
    assert hass.states.get("time.mini9pro_30_schedule_off_time").state == "21:30:00"
    assert hass.states.get("select.mini9pro_30_sunrise_sunset_length").state == "90"


async def test_bluetooth_name(hass: HomeAssistant, mock_send) -> None:
    await _setup(hass, PUMP_ADDRESS, "pump", "ES350")
    entity_id = "text.es350_bluetooth_name"
    assert hass.states.get(entity_id).state == "x"  # name of the mocked BLEDevice

    await hass.services.async_call(
        "text", "set_value", {ATTR_ENTITY_ID: entity_id, "value": "B8.0-Filter"}, blocking=True
    )
    assert mock_send.call_args.args[1] == b"!%!%:ADV_NAME:B8.0-Filter"
    assert hass.states.get(entity_id).state == "B8.0-Filter"
