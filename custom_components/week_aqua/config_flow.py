"""Config flow for Week Aqua."""

from __future__ import annotations

from typing import Any

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS
import voluptuous as vol

from .const import CONF_KIND, CONF_RISK_ACCEPTED, DOMAIN
from .protocol import AdvertisementInfo, DeviceKind, parse_advertisement

KIND_LABEL = {DeviceKind.LIGHT_RGBUV: "RGB+UV light", DeviceKind.PUMP: "Pump"}


def _title(service_info: BluetoothServiceInfoBleak) -> str:
    return service_info.name or service_info.address


class WeekAquaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Week Aqua."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovery: BluetoothServiceInfoBleak | None = None
        self._discovery_info: AdvertisementInfo | None = None
        self._candidates: dict[str, tuple[BluetoothServiceInfoBleak, AdvertisementInfo]] = {}
        self._pending: tuple[BluetoothServiceInfoBleak, AdvertisementInfo] | None = None

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle a device found by Bluetooth discovery."""
        info = parse_advertisement(discovery_info.manufacturer_data)
        if info is None:
            return self.async_abort(reason="not_supported")
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovery = discovery_info
        self._discovery_info = info
        self.context["title_placeholders"] = {"name": _title(discovery_info)}
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a discovered device."""
        assert self._discovery is not None and self._discovery_info is not None
        if user_input is not None:
            return await self._create(self._discovery, self._discovery_info)
        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={
                "name": _title(self._discovery),
                "kind": KIND_LABEL[self._discovery_info.kind],
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick from devices currently in range."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            service_info, info = self._candidates[address]
            return await self._create(service_info, info)

        configured = self._async_current_ids(include_ignore=False)
        for service_info in async_discovered_service_info(self.hass, connectable=True):
            if service_info.address in configured:
                continue
            if info := parse_advertisement(service_info.manufacturer_data):
                self._candidates[service_info.address] = (service_info, info)

        if not self._candidates:
            return self.async_abort(reason="no_devices_found")

        options = {
            address: f"{_title(si)} — {KIND_LABEL[info.kind]}"
            for address, (si, info) in self._candidates.items()
        }
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): vol.In(options)}),
        )

    def _risk_accepted(self) -> bool:
        """The disclaimer is accepted once, with the first device."""
        return any(
            entry.data.get(CONF_RISK_ACCEPTED)
            for entry in self._async_current_entries(include_ignore=False)
        )

    async def async_step_disclaimer(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the use-at-your-own-risk disclaimer; setup continues only if accepted."""
        assert self._pending is not None
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input.get(CONF_RISK_ACCEPTED):
                return self._create_entry(*self._pending)
            errors["base"] = "must_accept"
        return self.async_show_form(
            step_id="disclaimer",
            data_schema=vol.Schema({vol.Required(CONF_RISK_ACCEPTED, default=False): bool}),
            errors=errors,
        )

    async def _create(
        self, service_info: BluetoothServiceInfoBleak, info: AdvertisementInfo
    ) -> ConfigFlowResult:
        if self._risk_accepted():
            return self._create_entry(service_info, info)
        self._pending = (service_info, info)
        return await self.async_step_disclaimer()

    def _create_entry(
        self, service_info: BluetoothServiceInfoBleak, info: AdvertisementInfo
    ) -> ConfigFlowResult:
        return self.async_create_entry(
            title=_title(service_info),
            data={
                CONF_ADDRESS: service_info.address,
                CONF_KIND: info.kind.value,
                CONF_RISK_ACCEPTED: True,
            },
        )
