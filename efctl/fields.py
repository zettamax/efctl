"""Field introspection, humanization, and formatting for device watch mode."""

from __future__ import annotations

import re
from dataclasses import fields as dc_fields
from typing import Any, TYPE_CHECKING

from .eflib.devicebase import DeviceBase

from .field_defs import (
    MAX_DISPLAY_MINUTES, SENTINEL_THRESHOLD,
    _GROUP_NAMES, _GROUP_ORDER,
    _PORT_FIELDS, _USB_POWER_FIELDS, _OUTPUT_FIELDS,
    _SETTINGS_FIELDS, _DC_SETTINGS_FIELDS, _INPUT_FIELDS,
    _SYSTEM_FIELDS, _BATTERY_SLOT_1_FIELDS, _BATTERY_SLOT_2_FIELDS,
    _BATTERY_FIELDS,
    _WORD_UPPER, _WORD_MAP, _FIELD_OVERRIDES, _SKIP_FIELDS,
    _SKIP_DEVICE_FIELDS, _FIELD_IMPORTANCE,
    _RAW_VALUE_MAP, _INTERESTING_RAW_FIELDS, _CAPACITY_FIELDS,
)

if TYPE_CHECKING:
    from .ble import ManagedDevice

# Type aliases for the nested tuples used throughout
FieldEntry = tuple[str, str]                        # (human_label, formatted_value)
FieldGroup = tuple[str, list[FieldEntry]]           # (group_name, fields)


def _reclassify_field(field_name: str) -> str | None:
    """Return target group name if field should be moved, else None."""
    if field_name in _PORT_FIELDS or field_name in _USB_POWER_FIELDS or field_name in _OUTPUT_FIELDS:
        return "Output"
    if field_name in _INPUT_FIELDS:
        return "Input"
    if field_name in _SETTINGS_FIELDS:
        return "Settings"
    if field_name in _DC_SETTINGS_FIELDS:
        return "DC Settings"
    if field_name in _SYSTEM_FIELDS:
        return "System"
    if field_name in _BATTERY_SLOT_1_FIELDS:
        return "Battery (Slot 1)"
    if field_name in _BATTERY_SLOT_2_FIELDS:
        return "Battery (Slot 2)"
    if field_name in _BATTERY_FIELDS:
        return "Battery"
    # Pattern-based fallback
    n = field_name.lower()
    if n.startswith("cfg_") and n not in _PORT_FIELDS and n not in _DC_SETTINGS_FIELDS:
        return "Settings"
    if n.endswith("_used_time"):
        return None
    return None


# --- Field naming ---

def _humanize_group(name: str) -> str:
    if name in _GROUP_NAMES:
        return _GROUP_NAMES[name]
    return re.sub(r'(?<!^)(?=[A-Z])', ' ', name).strip('_ ')


def _humanize_field(name: str) -> str:
    if name in _FIELD_OVERRIDES:
        return _FIELD_OVERRIDES[name]
    parts = name.split('_')
    result = []
    for p in parts:
        low = p.lower()
        if low in _WORD_MAP:
            mapped = _WORD_MAP[low]
            if mapped:
                result.append(mapped)
        elif low in _WORD_UPPER:
            result.append(low.upper())
        else:
            m = re.match(r'^([a-z]+?)(\d+)$', low)
            if m:
                base, num = m.groups()
                if base in _WORD_MAP and _WORD_MAP[base]:
                    result.append(f"{_WORD_MAP[base]} {num}")
                elif base in _WORD_UPPER:
                    result.append(f"{base.upper()} {num}")
                else:
                    result.append(p.capitalize())
            else:
                result.append(p.capitalize())
    return ' '.join(result)


# --- Units & conversion ---

def _get_unit(field_name: str) -> str:
    n = field_name.lower()
    if any(x in n for x in ("remain_time", "remaining_time")):
        return ""
    if any(x in n for x in ("used_time", "standby_min", "lcd_off")):
        return ""
    # Power
    if n.endswith("_watts") or n.endswith("_watt") or n.endswith("_power"):
        return " W"
    if n in ("input_watts", "output_watts", "in_watts", "out_watts"):
        return " W"
    if n.endswith("_output_power") or n.endswith("_input_power"):
        return " W"
    if "power" in n and "limit" not in n and "flag" not in n:
        return " W"
    if "watts" in n:
        return " W"
    if n in ("ac_charging_speed", "max_ac_charging_power", "min_ac_charging_power"):
        return " W"
    # Voltage (displayed as V after conversion)
    if n.endswith("_vol") or n == "vol" or "voltage" in n:
        return " V"
    if n.endswith("_output_voltage"):
        return " V"
    # Current (displayed as A after conversion)
    if n.endswith("_amp") or n == "amp" or n.endswith("_amps") or n.endswith("_current"):
        return " A"
    if n.endswith("_output_current") or n.endswith("_max_amps"):
        return " A"
    if n in ("dc_charging_current_max",):
        return " A"
    # Temperature
    if "temperature" in n or n.endswith("_temp") or n == "temp":
        return " °C"
    # Percentage
    if "battery_level" in n or "show_soc" in n or n == "soc":
        return " %"
    if "charge_limit" in n or "charge_soc" in n or n == "soh":
        return " %"
    if n.endswith("_soc"):
        return " %"
    if n in ("energy_backup_battery_level", "bp_power_soc"):
        return " %"
    # Capacity
    if n.endswith("_cap"):
        return " Ah"
    # Charging config
    if "chg_watts" in n or "charging_speed" in n:
        return " W"
    if "chg_rated_power" in n:
        return " W"
    # Frequency
    if n.endswith("_freq"):
        return " Hz"
    if n == "wifi_rssi":
        return " dBm"
    return ""


def _convert_raw(name: str, value: Any) -> Any:
    """Convert raw data values to display-friendly units.

    Only for abbreviation-style field names (vol, amp, cap) from raw dataclasses.
    Device-level fields using full words (voltage, current) are already converted.
    Returns None for sentinel values (uint32 0xFFFFFFFF).
    """
    if not isinstance(value, (int, float)):
        return value
    n = name.lower()
    # mV -> V
    if n.endswith("_vol") or n == "vol" or n.endswith("cell_vol"):
        converted = round(value / 1000, 2)
        return None if converted > SENTINEL_THRESHOLD else converted
    # mA -> A
    if n.endswith("_amp") or n == "amp" or n.endswith("_current"):
        converted = round(value / 1000, 2)
        return None if converted > SENTINEL_THRESHOLD else converted
    # mAh -> Ah (applies to both raw fields and device-level _cap fields)
    if n.endswith("_cap") and value > 0:
        converted = round(value / 1000, 1)
        return None if converted > SENTINEL_THRESHOLD else converted
    return value


def _fmt_value(value: Any, field_name: str = "") -> str:
    if value is None:
        return "—"
    if isinstance(value, (bytes, bytearray)):
        return value.hex() if len(value) <= 8 else f"{value[:4].hex()}..."
    if isinstance(value, bool):
        return "ON" if value else "OFF"
    n = field_name.lower()
    # Time: format as h/m
    if any(x in n for x in ("remain_time", "remaining_time")):
        if isinstance(value, (int, float)):
            mins = int(value)
            if mins <= 0 or mins > MAX_DISPLAY_MINUTES:
                return "—"
            if mins < 60:
                return f"{mins}m"
            h, m = divmod(mins, 60)
            return f"{h}h {m}m" if m else f"{h}h"
    # Enum check before int (IntEnum is a subclass of int)
    if hasattr(value, 'name') and hasattr(value, 'value'):
        return value.name.replace('_', ' ').title()
    if isinstance(value, float):
        return f"{value:.2f}"
    if isinstance(value, int):
        return str(value)
    return str(value)


# --- Field extraction ---

def _format_field(field_name: str, value: Any, convert: bool = False) -> FieldEntry:
    """Format a single field into (human_label, formatted_value)."""
    if convert:
        value = _convert_raw(field_name, value)
    # Map raw int values for known config fields
    if field_name in _RAW_VALUE_MAP and isinstance(value, int):
        mapped = _RAW_VALUE_MAP[field_name].get(value)
        if mapped:
            return (_humanize_field(field_name), mapped)
    human = _humanize_field(field_name)
    formatted = _fmt_value(value, field_name)
    if value is not None and formatted != "—":
        formatted += _get_unit(field_name)
    return (human, formatted)


# Tagged = (raw_name, FieldEntry) — preserves raw name for sorting
TaggedField = tuple[str, FieldEntry]
TaggedGroup = tuple[str, list[TaggedField]]


def _field_sort_key(field_name: str) -> int:
    """Return sort priority for a field. Lower = more important."""
    if field_name in _FIELD_IMPORTANCE:
        return _FIELD_IMPORTANCE[field_name]
    n = field_name.lower()
    if "battery_level" in n or "soc" in n:
        return 15
    if n.endswith("_watts") or n.endswith("_watt") or "power" in n:
        return 100
    if n.endswith("_vol") or "voltage" in n:
        return 110
    if n.endswith("_amp") or "current" in n:
        return 120
    if n.endswith("_temp") or "temperature" in n:
        return 130
    if n.startswith("cfg_"):
        return 250
    if "standby" in n:
        return 320
    if "_ver" in n or "version" in n:
        return 450
    return 500


def _sort_and_finalize(groups: list[TaggedGroup]) -> list[FieldGroup]:
    """Sort tagged fields by importance, drop raw names, return final groups."""
    result = []
    for name, tagged_fields in groups:
        tagged_fields.sort(key=lambda x: _field_sort_key(x[0]))
        result.append((name, [entry for _, entry in tagged_fields]))
    return result


def _port_display(state: Any, power: int | None, has_switch: bool = True) -> str:
    """Format port display: OFF when disabled, ON when enabled idle, X W when power flows."""
    if has_switch:
        if state is None or state is False or state == 0:
            return "OFF"
        if power and power > 0:
            return f"{power} W"
        return "ON"
    else:
        # No switch (e.g. River USB) — just show watts
        return f"{power or 0} W"


def _build_output_group(ef_device: DeviceBase) -> list[FieldEntry]:
    """Build Output group: AC, USB, DC 12V — each shows OFF / ON / X W."""
    entries = []

    # AC output
    ac_state = getattr(ef_device, 'ac_ports', None)
    ac_power = getattr(ef_device, 'ac_output_power', None)
    ac_power_int = int(ac_power) if isinstance(ac_power, (int, float)) and ac_power > 0 else None
    entries.append(("AC", _port_display(ac_state, ac_power_int)))

    # USB (aggregated) — has_switch only if device has usb_ports field
    has_usb_switch = hasattr(ef_device, 'usb_ports') and 'usb_ports' in {
        f.public_name for f in ef_device._fields
    }
    usb_state = getattr(ef_device, 'usb_ports', None) if has_usb_switch else None
    usb_total = 0
    for attr in _USB_POWER_FIELDS:
        val = getattr(ef_device, attr, None)
        if isinstance(val, (int, float)) and val > 0:
            usb_total += int(val)
    entries.append(("USB", _port_display(usb_state, usb_total if usb_total > 0 else None, has_switch=has_usb_switch)))

    # DC 12V — derive power from total if no direct reading
    dc_state = getattr(ef_device, 'dc_12v_port', None)
    if dc_state is not None:
        dc_power = (
            getattr(ef_device, 'dc12v_output_power', None)
            or getattr(ef_device, 'dc_output_power', None)
        )
        dc_power_int = int(dc_power) if isinstance(dc_power, (int, float)) and dc_power > 0 else None
        # If port is ON but no direct power reading, derive from total
        if dc_power_int is None and dc_state:
            total_out = getattr(ef_device, 'output_power', None) or 0
            ac_out = getattr(ef_device, 'ac_output_power', None) or 0
            derived = int(total_out) - int(ac_out) - usb_total
            if derived > 0:
                dc_power_int = derived
        entries.append(("DC 12V", _port_display(dc_state, dc_power_int)))

    # Total output
    total_out = getattr(ef_device, 'output_power', None)
    if total_out is not None:
        entries.append(("Total", f"{int(total_out)} W"))

    return entries


def _groups_from_fields(ef_device: DeviceBase) -> list[TaggedGroup]:
    """Extract device-level fields into tagged groups (raw names preserved for sorting)."""
    from .eflib.props.protobuf_field import ProtobufField
    from .eflib.props.raw_data_field import RawDataField

    groups: dict[str, list[TaggedField]] = {}
    group_order: list[str] = []

    for f in ef_device._fields:
        raw_name = f.public_name
        if raw_name in _SKIP_DEVICE_FIELDS:
            continue
        if raw_name in _PORT_FIELDS or raw_name in _USB_POWER_FIELDS or raw_name in _OUTPUT_FIELDS:
            continue

        value = getattr(ef_device, raw_name)

        # Input power fields: show "0 W" instead of "—" for None
        if raw_name in _INPUT_FIELDS and value is None:
            value = 0

        entry = _format_field(raw_name, value, convert=True)

        # Determine initial group from source message type
        if isinstance(f, ProtobufField):
            key = _humanize_group(f.pb_field.message_type.__name__)
        elif isinstance(f, RawDataField):
            key = _humanize_group(f.data_attr.message_type.__name__)
        else:
            key = "System"

        # Reclassify to semantic group
        new_group = _reclassify_field(raw_name)
        if new_group:
            key = new_group

        if key not in groups:
            groups[key] = []
            group_order.append(key)
        groups[key].append((raw_name, entry))

    return [(name, groups[name]) for name in group_order]


def _collapse_empty_slots(groups: list[FieldGroup]) -> list[FieldGroup]:
    """Replace empty battery slot groups with a single 'Not installed' line."""
    collapsed = []
    for name, fields in groups:
        if name.startswith("Battery (Slot"):
            non_dash = [
                (label, val) for label, val in fields
                if val not in ("—", "OFF")
            ]
            if not non_dash:
                collapsed.append((name, [("Status", "Not installed")]))
                continue
        collapsed.append((name, fields))
    return collapsed


def _hide_empty_groups(groups: list[FieldGroup]) -> list[FieldGroup]:
    """Remove groups where all values are '—', and strip individual '—' entries."""
    result = []
    for name, fields in groups:
        # Keep Battery Slot groups as-is (handled by _collapse_empty_slots)
        if name.startswith("Battery (Slot"):
            result.append((name, fields))
            continue
        # Keep Output as-is (built manually)
        if name == "Output":
            result.append((name, fields))
            continue
        # Filter out individual "—" entries
        filtered = [(label, val) for label, val in fields if val != "—"]
        if filtered:
            result.append((name, filtered))
    return result


def _get_exposed_raw_fields(ef_device: DeviceBase) -> set[tuple[str, str]]:
    """Return set of (message_type_name, raw_attr_name) covered by device fields."""
    from .eflib.props.raw_data_field import RawDataField
    exposed = set()
    for f in ef_device._fields:
        if isinstance(f, RawDataField):
            exposed.add((
                f.data_attr.message_type.__name__,
                f.data_attr.attr,
            ))
    return exposed


def _supplement_hidden_fields(
    tagged_groups: list[TaggedGroup],
    ef_device: DeviceBase,
    parsed_messages: dict[str, Any],
) -> list[TaggedGroup]:
    """Add raw fields not exposed at device level (cycles, soh, etc.)."""
    exposed = _get_exposed_raw_fields(ef_device)
    # Pre-populate added with exposed field names to prevent duplicates
    # across different message types (e.g. cfg_ac_xboost in both MPPT and INV)
    added: set[str] = {attr for _, attr in exposed}

    groups: dict[str, list[TaggedField]] = {}
    for name, fields_list in tagged_groups:
        groups[name] = list(fields_list)

    for class_name, msg in parsed_messages.items():
        default_group = _humanize_group(class_name)

        for f in dc_fields(msg):
            if f.name in _SKIP_FIELDS:
                continue
            if f.name not in _INTERESTING_RAW_FIELDS:
                continue
            if f.name in added:
                continue
            already_exposed = any(
                (base.__name__, f.name) in exposed
                for base in type(msg).__mro__
            )
            if already_exposed:
                continue

            value = getattr(msg, f.name)
            if isinstance(value, (bytes, bytearray)):
                continue
            entry = _format_field(f.name, value, convert=True)
            if entry[1] == "—":
                continue

            # Apply same reclassification as device-level fields
            group_name = _reclassify_field(f.name) or default_group

            if group_name not in groups:
                groups[group_name] = []
            groups[group_name].append((f.name, entry))
            added.add(f.name)

    return [(name, fields) for name, fields in groups.items()]


def _get_pack_voltage(parsed_messages: dict[str, Any]) -> float | None:
    """Get pack voltage from BMS raw data for Ah->Wh conversion."""
    for cls_name, msg in parsed_messages.items():
        if not hasattr(msg, 'vol'):
            continue
        vol = getattr(msg, 'vol', None)
        if vol is None or vol <= 0:
            continue
        # Auto-detect unit: >1000 = mV, <=1000 = V
        return vol / 1000 if vol > 1000 else float(vol)
    return None


def _convert_capacity_to_wh(
    tagged_groups: list[TaggedGroup], voltage: float,
) -> list[TaggedGroup]:
    """Convert capacity fields from Ah to Wh using pack voltage.

    This operates on string-formatted values (e.g. "12.3 Ah") because fields
    are already formatted as FieldEntry tuples by this point in the pipeline.
    A numeric approach would require carrying raw values alongside formatted
    strings, which is a larger pipeline change.
    """
    result = []
    for name, fields in tagged_groups:
        new_fields = []
        for raw_name, (label, val_str) in fields:
            if raw_name in _CAPACITY_FIELDS and val_str.endswith(" Ah"):
                try:
                    ah = float(val_str.replace(" Ah", ""))
                    wh = round(ah * voltage)
                    new_fields.append((raw_name, (label, f"{wh} Wh")))
                    continue
                except ValueError:
                    pass
            new_fields.append((raw_name, (label, val_str)))
        result.append((name, new_fields))
    return result


def _hide_backup_reserve_when_off(groups: list[FieldGroup]) -> list[FieldGroup]:
    """Hide Backup Reserve value when Energy Backup is OFF."""
    result = []
    for name, fields in groups:
        if name == "Settings":
            # Check if Energy Backup is OFF
            backup_on = any(
                label in ("Energy Backup",) and val not in ("OFF", "—")
                for label, val in fields
            )
            if not backup_on:
                fields = [(l, v) for l, v in fields
                          if l not in ("Backup Reserve",)]
        result.append((name, fields))
    return result


def get_device_fields_grouped(managed: ManagedDevice) -> list[FieldGroup]:
    """Return [(group_name, [(human_label, formatted_value), ...]), ...]

    Always uses device-level fields (with semantic reclassification).
    Supplements with hidden raw fields (cycles, soh) when available.
    """
    ef_device = managed.ef_device
    if not ef_device:
        return []

    # Phase 1: extract tagged groups (raw names preserved)
    tagged = _groups_from_fields(ef_device)

    # Phase 2: supplement with hidden raw fields
    if managed.parsed_messages:
        tagged = _supplement_hidden_fields(tagged, ef_device, managed.parsed_messages)

    # Phase 3: convert capacity Ah → Wh using BMS voltage
    pack_voltage = _get_pack_voltage(managed.parsed_messages)
    if pack_voltage:
        tagged = _convert_capacity_to_wh(tagged, pack_voltage)

    # Phase 4: sort within groups and finalize
    result = _sort_and_finalize(tagged)

    # Phase 5: add Output group (built separately, already ordered)
    output_entries = _build_output_group(ef_device)
    if output_entries:
        result.append(("Output", output_entries))

    # Phase 6: post-processing
    result = _collapse_empty_slots(result)
    result = _hide_backup_reserve_when_off(result)
    result = _hide_empty_groups(result)
    result.sort(key=lambda x: _GROUP_ORDER.get(x[0], 100))

    return result
