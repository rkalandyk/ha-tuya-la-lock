import logging

from homeassistant.components.lock import LockEntity, LockEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TuyaLockCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: TuyaLockCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        TuyaLALockEntity(coordinator, device_id)
        for device_id in coordinator.data
    )


class TuyaLALockEntity(CoordinatorEntity[TuyaLockCoordinator], LockEntity):
    _attr_has_entity_name = True
    _attr_supported_features = LockEntityFeature.OPEN

    def __init__(self, coordinator: TuyaLockCoordinator, device_id: str) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"tuya_la_{device_id}"

    @property
    def _data(self) -> dict:
        return self.coordinator.data.get(self._device_id, {})

    @property
    def _status(self) -> dict:
        return self._data.get("status", {})

    @property
    def name(self) -> str:
        return self._data.get("info", {}).get("name", self._device_id)

    @property
    def is_locked(self) -> bool | None:
        """True = zamknięty, False = otwarty.
        lock_motor_state: False = zamknięty, True = otwarty (bool z Tuya API).
        """
        motor = self._status.get("lock_motor_state")
        if motor is None:
            return True  # domyślnie zamknięty (bezpieczny default)
        if isinstance(motor, bool):
            return not motor  # False = zamknięty → True
        return motor != "open"  # dla ewentualnych wartości string

    @property
    def is_jammed(self) -> bool:
        # alarm_lock to string z typem alarmu (np. "wrong_finger"), nie bool
        # HA "jammed" = zamek mechanicznie zablokowany — nie mapujemy alarm_lock
        return False

    @property
    def available(self) -> bool:
        return self._data.get("info", {}).get("online", False)

    @property
    def extra_state_attributes(self) -> dict:
        s = self._status
        return {
            "battery_%": s.get("residual_electricity"),
            "reverse_lock": s.get("reverse_lock"),
            "manual_lock": s.get("manual_lock"),
            "auto_lock": s.get("automatic_lock"),
            "auto_lock_time": s.get("auto_lock_time"),
            "arming_switch": s.get("arming_switch"),
            "beep_volume": s.get("beep_volume"),
            "alarm_type": s.get("alarm_type"),
            "alarm_lock": s.get("alarm_lock"),
            "open_inside": s.get("open_inside"),
            "device_id": self._device_id,
        }

    @property
    def device_info(self) -> dict:
        info = self._data.get("info", {})
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": info.get("name", self._device_id),
            "manufacturer": "Tuya / JTMS Pro",
            "model": info.get("product_name", "LA-T01"),
            "sw_version": info.get("fw_ver"),
        }

    async def async_unlock(self, **kwargs) -> None:
        _LOGGER.info("Otwieranie zamka %s (%s)", self.name, self._device_id)
        success = await self.coordinator.unlock_door(self._device_id)
        if success:
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Nie udało się otworzyć zamka %s", self.name)

    async def async_open(self, **kwargs) -> None:
        """Alias — otwórz bez blokowania po zamknięciu."""
        await self.async_unlock(**kwargs)

    async def async_lock(self, **kwargs) -> None:
        """Zamek LA-T01 blokuje się automatycznie — brak komendy cloud lock."""
        _LOGGER.warning(
            "Zamek %s blokuje się automatycznie (auto-lock). "
            "Ręczne blokowanie przez cloud API nie jest obsługiwane.",
            self.name,
        )
