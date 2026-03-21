import hashlib
import hmac
import time

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import BASE_URL, DOMAIN


class TuyaLALockConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        errors: dict = {}

        if user_input is not None:
            try:
                await self._test_auth(
                    user_input["client_id"], user_input["client_secret"]
                )
            except Exception:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(user_input["client_id"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Tuya LA-T01 Smart Lock",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("client_id"): str,
                    vol.Required("client_secret"): str,
                }
            ),
            errors=errors,
        )

    async def _test_auth(self, client_id: str, client_secret: str) -> None:
        path = "/v1.0/token?grant_type=1"
        t = str(int(time.time() * 1000))
        content_hash = hashlib.sha256(b"").hexdigest()
        string_to_sign = "\n".join(["GET", content_hash, "", path])
        sig = hmac.new(
            client_secret.encode(),
            (client_id + t + string_to_sign).encode(),
            hashlib.sha256,
        ).hexdigest().upper()
        headers = {
            "client_id": client_id,
            "sign": sig,
            "t": t,
            "sign_method": "HMAC-SHA256",
        }
        session = async_get_clientsession(self.hass)
        async with session.get(
            BASE_URL + path, headers=headers, timeout=10
        ) as resp:
            data = await resp.json(content_type=None)

        if not data.get("success"):
            raise ValueError(f"Auth failed: {data}")
