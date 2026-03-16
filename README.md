# efctl

Terminal tool for EcoFlow power stations over Bluetooth LE. Monitor battery, power flow, port states, and control settings — all from the command line, no cloud needed.

Built with [Textual](https://textual.textualize.io/) and [ha-ef-ble](https://github.com/rabits/ha-ef-ble) protocol library.

```
┌────────────────────────────────┐  ┌────────────────────────────────┐
│ ● DELTA_3    ↓5h52m         ◉ │  │ ● RIVER_2_Pro  ↑1h3m          │
│ AA:BB:CC:DD:EE:F1              │  │ AA:BB:CC:DD:EE:F2              │
├────────────────────────────────┤  ├────────────────────────────────┤
│ Battery:     80%               │  │ Battery:     79%               │
│ Input:       0W                │  │ Input:       96W               │
│ Output:      156W              │  │ Output:      3W                │
│ Cell Temp:   23°C              │  │ Cell Temp:   24°C              │
│ Cycles:      22                │  │ Cycles:      72                │
│ X-Boost:     ON                │  │ X-Boost:     ON                │
├────────────────────────────────┤  ├────────────────────────────────┤
│    AC     USB    DC 12V       │  │    AC     USB    DC 12V       │
└────────────────────────────────┘  └────────────────────────────────┘
```

## Setup

```bash
git clone https://github.com/user/efctl.git && cd efctl
make setup
make run
```

On first launch you'll be asked for your EcoFlow User ID — grab it from the EcoFlow app or at https://gnox.github.io/user_id.

## What it does

- **Dashboard** — live device blocks with battery, power, ports, cycles
- **Detail view** (`show`) — full breakdown: input/output, battery health, settings, DC config
- **Port control** (`on`/`off`) — toggle AC, DC, USB ports
- **Settings** (`set`) — change charge/discharge levels, charge power, X-Boost
- **Auto-connect** — reconnects to saved devices automatically
- Tab autocomplete, command history, busy indicators

## Tested on

- **EcoFlow DELTA 3 (1500)** and **RIVER 2 Pro** on Linux
- Other ha-ef-ble supported devices (Delta 2/Pro, River 3, PowerStream, etc.) should work but are untested
- **Linux only** for now — depends on `bleak-retry-connector` which requires BlueZ. Cross-platform support (macOS/Windows) is planned.

Requires Python 3.12+, Linux with BlueZ, and a BLE adapter.

## Notes

- EcoFlow devices support **one BLE connection at a time** — disconnect the EcoFlow app first
- Config is stored in `~/.efctl/config.json`
- `efctl/eflib/` is the BLE protocol library vendored from [ha-ef-ble](https://github.com/rabits/ha-ef-ble) by [@rabits](https://github.com/rabits) (Apache-2.0)

## License

Apache-2.0
