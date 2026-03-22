import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
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
    entities = []
    for device_id in coordinator.data:
        entities.append(TuyaLockBatterySensor(coordinator, device_id))
        entities.append(TuyaLockStatusSensor(coordinator, device_id))
    async_add_entities(entities)


class TuyaLockBaseSensor(CoordinatorEntity[TuyaLockCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: TuyaLockCoordinator, device_id: str) -> None:
        super().__init__(coordinator)
        self._device_id = device_id

    @property
    def _data(self) -> dict:
        return self.coordinator.data.get(self._device_id, {})

    @property
    def _status(self) -> dict:
        return self._data.get("status", {})

    @property
    def available(self) -> bool:
        return self._data.get("info", {}).get("online", False)

    @property
    def device_info(self) -> dict:
        info = self._data.get("info", {})
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": info.get("name", self._device_id),
            "manufacturer": "Tuya / JTMS Pro",
            "model": info.get("product_name", "LA-T01"),
        }


class TuyaLockBatterySensor(TuyaLockBaseSensor):
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: TuyaLockCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"tuya_la_{device_id}_battery"

    @property
    def name(self) -> str:
        return "Bateria"

    @property
    def native_value(self) -> int | None:
        return self._status.get("residual_electricity")

    @property
    def icon(self) -> str:
        val = self.native_value
        if val is None:
            return "mdi:battery-unknown"
        if val <= 10:
            return "mdi:battery-10"
        if val <= 20:
            return "mdi:battery-20"
        if val <= 50:
            return "mdi:battery-50"
        if val <= 80:
            return "mdi:battery-80"
        return "mdi:battery"


class TuyaLockStatusSensor(TuyaLockBaseSensor):
    _attr_device_class = None

    def __init__(self, coordinator: TuyaLockCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"tuya_la_{device_id}_status"

    @property
    def name(self) -> str:
        return "Status"

    @property
    def native_value(self) -> str:
        s = self._status
        if s.get("reverse_lock"):
            return "zaryglowany od wewnątrz"
        if s.get("manual_lock"):
            return "zamknięty ręcznie"
        motor = s.get("lock_motor_state")
        if motor is True:
            return "otwarty"
        if motor is False:
            return "zamknięty"
        return "nieznany"

    @property
    def icon(self) -> str:
        val = self.native_value
        if val == "otwarty":
            return "mdi:lock-open"
        if "zaryglowany" in (val or ""):
            return "mdi:lock-plus"
        return "mdi:lock"

    @property
    def extra_state_attributes(self) -> dict:
        s = self._status
        return {
            "alarm_lock": s.get("alarm_lock"),
            "open_inside": s.get("open_inside"),
            "closed_opened": s.get("closed_opened"),
            "unlock_fingerprint": s.get("unlock_fingerprint"),
            "unlock_password": s.get("unlock_password"),
            "unlock_card": s.get("unlock_card"),
            "unlock_ble": s.get("unlock_ble"),
            "unlock_phone_remote": s.get("unlock_phone_remote"),
        }
