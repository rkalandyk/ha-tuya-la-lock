import hashlib
import hmac
import json
import logging
import time
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import BASE_URL, DOMAIN, POLL_INTERVAL

_LOGGER = logging.getLogger(__name__)


class TuyaLockCoordinator(DataUpdateCoordinator):
    """Pobiera status wszystkich zamków LA-T01 z Tuya Cloud."""

    def __init__(self, hass: HomeAssistant, client_id: str, client_secret: str) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=POLL_INTERVAL),
        )
        self.client_id = client_id
        self.client_secret = client_secret
        self._access_token: str = ""
        self._token_expires: float = 0

    def _sign(self, method: str, path: str, body: str = "", token: str = "") -> tuple[str, str]:
        t = str(int(time.time() * 1000))
        content_hash = hashlib.sha256(body.encode()).hexdigest()
        string_to_sign = "\n".join([method, content_hash, "", path])
        base = (self.client_id + token + t) if token else (self.client_id + t)
        sig = hmac.new(
            self.client_secret.encode(),
            (base + string_to_sign).encode(),
            hashlib.sha256,
        ).hexdigest().upper()
        return t, sig

    async def _get_token(self) -> str:
        if self._access_token and self._token_expires > time.time() + 60:
            return self._access_token

        path = "/v1.0/token?grant_type=1"
        t, sig = self._sign("GET", path)
        headers = {
            "client_id": self.client_id,
            "sign": sig,
            "t": t,
            "sign_method": "HMAC-SHA256",
        }
        session = async_get_clientsession(self.hass)
        async with session.get(
            BASE_URL + path, headers=headers, timeout=15
        ) as resp:
            data = await resp.json(content_type=None)

        if not data.get("success"):
            raise UpdateFailed(f"Tuya token error: {data}")

        result = data["result"]
        self._access_token = result["access_token"]
        self._token_expires = time.time() + result.get("expire_time", 7200) - 300
        return self._access_token

    async def api(self, method: str, path: str, data: dict | None = None) -> dict:
        """Wywołaj Tuya Cloud API."""
        token = await self._get_token()
        body = json.dumps(data) if data is not None else ""
        t, sig = self._sign(method, path, body, token)
        headers = {
            "client_id": self.client_id,
            "access_token": token,
            "sign": sig,
            "t": t,
            "sign_method": "HMAC-SHA256",
        }
        if body:
            headers["Content-Type"] = "application/json"

        session = async_get_clientsession(self.hass)
        async with session.request(
            method,
            BASE_URL + path,
            data=body.encode() if body else None,
            headers=headers,
            timeout=15,
        ) as resp:
            return await resp.json(content_type=None)

    async def _async_update_data(self) -> dict:
        try:
            r = await self.api(
                "GET",
                "/v1.0/iot-01/associated-users/devices?last_row_key=&page_size=50",
            )
            devices = r.get("result", {}).get("devices", [])
            locks = {d["id"]: d for d in devices if d.get("category") == "jtmspro"}

            result: dict = {}
            for device_id, info in locks.items():
                status_r = await self.api("GET", f"/v1.0/devices/{device_id}/status")
                status = {
                    s["code"]: s["value"] for s in status_r.get("result", [])
                }
                result[device_id] = {"info": info, "status": status}

            _LOGGER.debug("Pobrano %d zamków z Tuya Cloud", len(result))
            return result

        except Exception as err:
            raise UpdateFailed(f"Błąd komunikacji z Tuya Cloud: {err}") from err

    async def unlock_door(self, device_id: str) -> bool:
        """Otwórz zamek przez Smart Lock API (ticket-based)."""
        ticket_r = await self.api(
            "POST",
            f"/v1.0/devices/{device_id}/door-lock/password-ticket",
            {},
        )
        if not ticket_r.get("success"):
            _LOGGER.error(
                "Błąd pobierania ticketu dla %s: %s", device_id, ticket_r
            )
            return False

        ticket = ticket_r["result"]
        open_r = await self.api(
            "POST",
            f"/v1.0/devices/{device_id}/door-lock/password-free/open-door",
            {
                "ticket_key": ticket["ticket_key"],
                "ticket_id": ticket["ticket_id"],
            },
        )
        success = open_r.get("success", False)
        if not success:
            _LOGGER.error("Błąd otwierania %s: %s", device_id, open_r)
        return success
