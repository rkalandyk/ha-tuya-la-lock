# Tuya LA-T01 Smart Lock — Home Assistant Integration

Custom component for Home Assistant that integrates **Tuya LA-T01 smart locks** (JTMS Pro / `jtmspro` category) via the Tuya Cloud Smart Lock API.

## Features

- Auto-discovers all LA-T01 locks from your Tuya account
- Native HA `lock` entities with **unlock** support
- Uses the official **Smart Lock API** (ticket-based, password-free unlock)
- Polls lock status every 60 seconds (battery, alarm, auto-lock state, etc.)
- No local network required — works fully via Tuya Cloud

## Requirements

1. Tuya Cloud project with **Smart Lock API** subscribed
   - Go to [iot.tuya.com](https://iot.tuya.com) → your project → Cloud Services → subscribe **Smart Lock**
2. Client ID and Client Secret from your Tuya Cloud project

## Installation

### Manual (HACS not yet supported)

1. Copy `custom_components/tuya_la_lock/` to your HA `/config/custom_components/`
2. Restart Home Assistant
3. Go to **Settings → Integrations → Add Integration** → search **Tuya LA-T01 Smart Lock**
4. Enter your **Client ID** and **Client Secret**

## Entities created

Each discovered lock gets:

| Entity | Type | Description |
|--------|------|-------------|
| `lock.<name>` | Lock | Open/Unlock via Smart Lock API |

### Extra attributes on lock entity

- `battery_%` — remaining battery
- `reverse_lock` — bolted from inside (guests present)
- `manual_lock` — manually deadbolted
- `auto_lock` — auto-lock enabled
- `auto_lock_time` — auto-lock delay (seconds)
- `arming_switch` — alarm armed
- `beep_volume` — audible feedback level
- `alarm_type` — last alarm type
- `device_id` — Tuya device ID

## How unlock works

The LA-T01 uses a **ticket-based password-free unlock** flow:

```
POST /v1.0/devices/{id}/door-lock/password-free/ticket
→ { ticket_key, ticket_id }

POST /v1.0/devices/{id}/door-lock/password-free/open-door
body: { ticket_key, ticket_id }
→ { success: true }
```

The lock receives the command via Tuya Cloud → BLE Gateway → lock motor.

## Supported hardware

| Device | Product ID | Category |
|--------|-----------|----------|
| LA-T01 | `8gza4o8a` | `jtmspro` |
| LA-T01 (variant) | `99gv5nmz` | `jtmspro` |

Any `jtmspro` category device on Tuya Cloud should work.

## Automations example

```yaml
automation:
  - alias: "Unlock front door for guest"
    trigger:
      - platform: state
        entity_id: input_boolean.guest_arriving
        to: "on"
    action:
      - service: lock.unlock
        target:
          entity_id: lock.norte
```

## Home Assistant Automation with time window

```yaml
automation:
  - alias: "Auto-unlock at check-in time"
    trigger:
      - platform: time
        at: "15:00:00"
    condition:
      - condition: state
        entity_id: calendar.reservations
        state: "on"
    action:
      - service: lock.unlock
        target:
          entity_id: lock.norte
```

## License

MIT
