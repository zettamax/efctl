"""Configuration data for field display: names, groups, overrides, skip lists."""

from __future__ import annotations

MAX_DISPLAY_MINUTES = 2880  # 48h — values above this are sentinel "not charging"
SENTINEL_THRESHOLD = 1_000_000  # uint32 0xFFFFFFFF / 1000 ≈ 4.3M — anything above this is N/A


# --- Group naming & ordering ---

_GROUP_NAMES = {
    # PD variants
    "BasePdHeart": "Input",
    "Mr330PdHeartDelta2": "Input",
    "Mr330PdHeartRiver2": "Input",
    "DirectPdDeltaProHeartbeatPack": "Input",
    # MPPT variants
    "BaseMpptHeart": "DC Settings",
    "Mr330MpptHeart": "DC Settings",
    # EMS
    "DirectEmsDeltaHeartbeatPack": "Energy Management",
    # BMS variants — Main merges into "Battery" (slots stay separate)
    "DirectBmsMDeltaHeartbeatPack": "Battery",
    "_BmsHeartbeatBatteryMain": "Battery",
    "_BmsHeartbeatBattery1": "Battery (Slot 1)",
    "_BmsHeartbeatBattery2": "Battery (Slot 2)",
    # Inverter variants
    "DirectInvDeltaHeartbeatPack": "Inverter",
    "DirectInvRiverHeartbeatPack": "Inverter",
    "DirectInvRiverMiniHeartbeatPack": "Inverter",
    "DirectInvHeartbeatPack": "Inverter",
    # Protobuf devices (Delta 3, etc.)
    "DisplayPropertyUpload": "System Status",
    "BMSHeartBeatReport": "BMS Report",
    # Kit
    "AllKitDetailData": "Kit Details",
}

_GROUP_ORDER = {
    "Overview": 1,
    "System Status": 5,
    "Input": 10,
    "Output": 15,
    "Battery": 30,
    "Settings": 40,
    "DC Settings": 50,
    "Battery (Slot 1)": 62,
    "Battery (Slot 2)": 63,
    "BMS Report": 75,
    "Kit Details": 85,
    "System": 90,
}


# --- Semantic reclassification ---
# After extracting fields from protocol-based groups, move certain fields
# to semantic groups so ports/settings/etc. are always grouped consistently.

_PORT_FIELDS = {
    # Port states
    "ac_ports", "usb_ports", "dc_12v_port", "dc_out_state", "car_state",
    # DC output
    "dc_output_power", "dc12v_output_power", "dc12v_output_voltage", "dc12v_output_current",
    "wireless_watts",
    # Raw PD DC fields
    "car_watts", "car_out_watts", "car_out_vol", "car_out_amp",
}

# Individual USB port fields — skipped in favor of aggregated "USB" summary
_USB_POWER_FIELDS = {
    "usbc_output_power", "usbc2_output_power",
    "usba_output_power", "usba2_output_power",
    "qc_usb1_output_power", "qc_usb2_output_power",
    # Raw PD
    "typec1_watts", "typec2_watts", "usb1_watt", "usb2_watt",
    "qc_usb1_watt", "qc_usb2_watt",
}

_SETTINGS_FIELDS = {
    # AC charge config
    "ac_xboost", "cfg_ac_xboost", "cfg_ac_out_voltage", "cfg_ac_out_freq",
    "ac_charging_speed", "cfg_chg_watts", "cfg_fast_chg_watts", "cfg_slow_chg_watts",
    "max_ac_charging_power", "ac_chg_rated_power",
    # Charge limits
    "battery_charge_limit_min", "battery_charge_limit_max",
    "max_charge_soc", "min_dsg_soc",
    # Energy backup
    "energy_backup", "energy_backup_enabled", "energy_backup_battery_level",
    "watthis_config", "bp_power_soc",
    # Standby / UI
    "standby_min", "standby_mins", "cfg_standby_min",
    "ac_standby_mins", "car_standby_mins",
    "power_standby_mins", "screen_standby_mins",
    "beep_mode", "beep_state",
    "lcd_brightness", "lcd_off_sec", "lcd_show_soc",
    # UPS
    "open_ups_flag",
}

# DC-related settings → "DC Settings" section
_DC_SETTINGS_FIELDS = {
    "dc_mode", "cfg_chg_type",
    "dc_charging_max_amps", "cfg_dc_chg_current",
}

# Fields reclassified to Input (from various protocol groups)
_INPUT_FIELDS = {
    "dc_port_input_power",  # DC/solar input power (device-level, from MPPT)
    "ac_input_power",       # AC wall input power (device-level, from Inverter)
    "in_watts",             # DC input power (raw MPPT supplement for Delta)
}

_SYSTEM_FIELDS = {
    "err_code", "error_code", "sys_ver", "wifi_ver", "sw_ver",
    "wifi_rssi", "wifi_auto_recovery", "wifi_auto_rcvy",
    "relay_switch_count", "reply_switchcnt",
}

# Fields that should go to their battery slot group, not System
_BATTERY_SLOT_1_FIELDS = {
    "battery_1_battery_level", "battery_1_cell_temperature",
    "battery_1_sn", "battery_1_enabled",
}
_BATTERY_SLOT_2_FIELDS = {
    "battery_2_battery_level", "battery_2_cell_temperature",
    "battery_2_sn", "battery_2_enabled",
}

# Fields that should move to Battery group (from Energy Management/System Status)
_BATTERY_FIELDS = {
    "battery_level", "cell_temperature",
}

# Inverter fields handled by _build_output_group, skip from normal processing
_OUTPUT_FIELDS = {
    "ac_output_power",
}


# --- Field naming ---

_WORD_UPPER = {
    "ac", "dc", "usb", "qc", "sn", "soc", "id",
    "bms", "ems", "mppt", "pd", "ups", "gfci",
}

_WORD_MAP = {
    "usbc": "USB-C", "usba": "USB-A",
    "dc12v": "DC 12V", "12v": "12V", "24v": "24V",
    "cap": "Capacity", "vol": "Voltage", "amp": "Current",
    "temp": "Temperature", "cfg": "", "chg": "Charge", "dsg": "Discharge",
    "soh": "SOH", "xboost": "X-Boost", "dcdc": "DC-DC",
}

_FIELD_OVERRIDES = {
    # Time
    "remaining_time_charging": "Time to Full",
    "remain_time_charging": "Time to Full",
    "remaining_time_discharging": "Time to Empty",
    "remain_time_discharging": "Time to Empty",
    "chg_remain_time": "Time to Full",
    "dsg_remain_time": "Time to Empty",
    "remain_time": "Remaining Time",
    # SOC
    "f32_show_soc": "Battery Level",
    "f32_lcd_show_soc": "Battery Level",
    "lcd_show_soc": "LCD SOC",
    # Per-slot battery (strip redundant prefix)
    "battery_1_battery_level": "Battery Level",
    "battery_2_battery_level": "Battery Level",
    "battery_1_cell_temperature": "Cell Temperature",
    "battery_2_cell_temperature": "Cell Temperature",
    "battery_1_sn": "Serial Number",
    "battery_2_sn": "Serial Number",
    "battery_1_enabled": "Enabled",
    "battery_2_enabled": "Enabled",
    # Device-level battery fields
    "battery_level": "Battery Level",
    "cell_temperature": "Cell Temperature",
    "cycles": "Cycles",
    "soh": "SOH",
    "design_cap": "Design Capacity",
    "remain_cap": "Remaining Capacity",
    "full_cap": "Full Capacity",
    # Capacity (device-level fields with master/slave prefix)
    "master_design_cap": "Design Capacity",
    "master_remain_cap": "Remaining Capacity",
    "master_full_cap": "Full Capacity",
    "slave_design_cap": "Design Capacity",
    "slave_remain_cap": "Remaining Capacity",
    "slave_full_cap": "Full Capacity",
    # Charge limits
    "battery_charge_limit_min": "Discharge Level",
    "battery_charge_limit_max": "Charge Level",
    "max_charge_soc": "Charge Level",
    "min_dsg_soc": "Discharge Level",
    # Power summary
    "watts_in_sum": "Total Input",
    "watts_out_sum": "Total Output",
    "input_watts": "Input Power",
    "output_watts": "Output Power",
    "input_power": "Total",
    "output_power": "Total",
    # Device-level power fields
    "ac_input_power": "AC",
    "ac_output_power": "AC",
    "dc_port_input_power": "DC",
    # BMS
    "max_cell_vol": "Max Cell Voltage",
    "min_cell_vol": "Min Cell Voltage",
    "max_cell_temp": "Max Cell Temperature",
    "min_cell_temp": "Min Cell Temperature",
    "max_mos_temp": "Max MOSFET Temperature",
    "min_mos_temp": "Min MOSFET Temperature",
    "bq_sys_stat_reg": "BQ Status Register",
    "tag_chg_amp": "Target Charge Current",
    # 12V / car
    "car_out_vol": "12V Output Voltage",
    "car_out_amp": "12V Output Current",
    "car_out_watts": "12V Output",
    "car_watts": "12V Output",
    "car_state": "12V Port",
    "car_temp": "12V Temperature",
    "car_standby_mins": "12V Standby Timeout",
    # DC-DC
    "dcdc_12v_vol": "DC 12V Voltage",
    "dcdc_12v_amp": "DC 12V Current",
    "dcdc_12v_watts": "DC 12V Power",
    # MPPT I/O
    "in_vol": "Input Voltage",
    "in_amp": "Input Current",
    "in_watts": "DC",
    "out_val": "Output Voltage",
    "out_amp": "Output Current",
    "out_watts": "Output Power",
    "mppt_temp": "MPPT Temperature",
    # Inverter (kept for _supplement_hidden_fields which may still encounter these)
    "inv_out_vol": "Output Voltage",
    "inv_out_amp": "Output Current",
    "inv_out_freq": "Output Frequency",
    "inv_in_vol": "Input Voltage",
    "inv_in_amp": "Input Current",
    "inv_in_freq": "Input Frequency",
    "ac_in_vol": "AC Input Voltage",
    "ac_in_amp": "AC Input Current",
    "ac_in_freq": "AC Input Frequency",
    "out_temp": "Output Temperature",
    "in_temp": "Input Temperature",
    "dc_in_vol": "DC Input Voltage",
    "dc_in_amp": "DC Input Current",
    "dc_in_temp": "DC Input Temperature",
    "fan_state": "Fan",
    "fan_level": "Fan Level",
    # Port states
    "ac_ports": "AC",
    "usb_ports": "USB",
    "dc_12v_port": "DC 12V",
    "dc_out_state": "DC Output",
    "cfg_ac_enabled": "AC",
    # Settings
    "ac_xboost": "X-Boost",
    "cfg_ac_xboost": "X-Boost",
    "cfg_ac_out_voltage": "AC Output Voltage",
    "cfg_ac_out_freq": "AC Output Frequency",
    "cfg_chg_type": "DC Mode",
    "cfg_chg_watts": "Charge Power",
    "dc_mode": "DC Mode",
    "dc_charging_max_amps": "DC Charge Current Limit",
    "ac_charging_speed": "Charge Power",
    "max_ac_charging_power": "Max AC Charge Power",
    "cfg_dc_chg_current": "DC Charge Current Limit",
    "cfg_fast_chg_watts": "Fast Charge Limit",
    "cfg_slow_chg_watts": "Slow Charge Limit",
    "ac_chg_rated_power": "AC Charge Rated Power",
    # Energy backup
    "energy_backup": "Energy Backup",
    "energy_backup_enabled": "Energy Backup",
    "energy_backup_battery_level": "Backup Reserve",
    "watthis_config": "Energy Backup",
    "bp_power_soc": "Backup Reserve",
    # USB
    "typec1_watts": "USB-C 1",
    "typec2_watts": "USB-C 2",
    "typec1_temp": "USB-C 1 Temperature",
    "typec2_temp": "USB-C 2 Temperature",
    "usb1_watt": "USB-A 1",
    "usb2_watt": "USB-A 2",
    "qc_usb1_watt": "QC USB 1",
    "qc_usb2_watt": "QC USB 2",
    # Charge/discharge power breakdown
    "chg_power_dc": "DC Charge Power",
    "chg_sun_power": "Solar Charge Power",
    "chg_power_ac": "AC Charge Power",
    "dsg_power_dc": "DC Discharge Power",
    "dsg_power_ac": "AC Discharge Power",
    "dc_chg_power": "DC Charge Power",
    "sun_chg_power": "Solar Charge Power",
    "ac_chg_power": "AC Charge Power",
    "dc_dsg_power": "DC Discharge Power",
    "ac_dsg_power": "AC Discharge Power",
    # EMS
    "open_ups_flag": "UPS Mode",
    "ems_is_normal_flag": "EMS Normal",
    "max_available_num": "Max Batteries",
    # PD misc
    "sys_chg_dsg_state": "System State",
    "syc_chg_dsg_state": "System State",
    "relay_switch_count": "Relay Switches",
    "reply_switchcnt": "Relay Switches",
    "wifi_rssi": "WiFi RSSI",
    "beep_mode": "Beep Mode",
    "beep_state": "Beep",
    "lcd_off_sec": "LCD Off Timeout",
    "lcd_brightness": "LCD Brightness",
    "standby_min": "Standby Timeout",
    "standby_mins": "Standby Timeout",
    "cfg_standby_min": "Standby Timeout",
    "ac_standby_mins": "AC Standby Timeout",
    "power_standby_mins": "Power Standby Timeout",
    "screen_standby_mins": "Screen Standby Timeout",
    # Version/error
    "err_code": "Error Code",
    "error_code": "Error Code",
    "sys_ver": "System Version",
    "wifi_ver": "WiFi Version",
    "sw_ver": "Software Version",
}

_SKIP_FIELDS = {
    "reserved", "res", "screen_state", "bms_is_connt",
    "num", "type_", "cell_id", "model",
}

# Fields to skip entirely in the device-level view (usage counters, internal,
# inverter detail fields moved here from _PORT_FIELDS)
_SKIP_DEVICE_FIELDS = {
    "usb_used_time", "usb_qc_used_time", "type_c_used_time",
    "car_used_time", "inv_used_time", "dc_in_used_time", "mppt_used_time",
    "usbqc_used_time", "typec_used_time",
    "wifi_auto_recovery", "wifi_auto_rcvy",
    "quiet_mode", "reverser",
    "solar_input_power", "car_input_power",  # stale Plain Fields, duplicate Solar section
    "dc_charging_current_max",  # duplicate of dc_charging_max_amps
    "output_power",  # redundant with Output section per-port breakdown
    "min_ac_charging_power",  # not useful on display (future setter)
    "battery_level_main",  # duplicate of battery_level
    "battery_input_power", "battery_output_power",  # protobuf devices, duplicates Power
    "plugged_in_ac",  # internal flag
    "dc_port_state",  # internal enum, not useful as display
    "disable_grid_bypass",  # advanced feature
    "energy_strategy_self_powered", "energy_strategy_scheduled", "energy_strategy_tou",
    "ext_rj45_port", "ext_3p8_port", "ext_4p8_port",
    "pv_priority", "ac_auto_on", "ac_auto_out_config", "ac_auto_out_pause",
    "ac_auto_config", "ac_out_pause", "min_auto_soc", "min_ac_out_soc",
    "hysteresis_soc", "hysteresis_add", "schedule_id", "heartbeat_duration",
    "input_power_limit_flag", "ac_charge_flag", "cloud_ctrl_en",
    "redun_charge_flag", "pay_flag", "bkw_watts_in_power",
    "charge_type", "charger_type", "chg_type", "xt60_chg_type",
    "chg_state", "chg_cmd", "dsg_cmd", "chg_pause_flag",
    "inv_type", "cfg_ac_work_mode", "cfg_pause_flag", "ac_dip_switch",
    "ac_passby_auto_en", "pr_balance_mode", "cfg_gfci_enable",
    "cfg_fan_mode", "cfg_ac_chg_mode_flg", "discharge_type",
    "dc24v_temp", "dc24v_state",
    "bms_model", "bms_warning_state", "bms_fault",
    "open_bms_idx", "para_vol_min", "para_vol_max",
    "open_oil_eb_soc", "close_oil_eb_soc",
    "watth_is_config", "backup_soc",
    "ac_auto_config",
    # Inverter detail / temperature fields (not useful at device level)
    "ac_input_voltage", "ac_input_current",
    "inv_out_vol", "inv_out_amp", "inv_out_freq",
    "inv_in_vol", "inv_in_amp", "inv_in_freq",
    "ac_in_vol", "ac_in_amp", "ac_in_freq",
    "out_temp", "in_temp", "dc_in_vol", "dc_in_amp", "dc_in_temp",
    "fan_state", "fan_level",
}


# --- Field importance ordering within groups ---
# Lower number = shown first. Fields not listed get default 500.

_FIELD_IMPORTANCE = {
    # Battery / SOC — most important
    "battery_level": 10, "f32_show_soc": 10, "f32_lcd_show_soc": 11,
    "lcd_show_soc": 12, "soc": 13,
    "battery_1_battery_level": 15, "battery_2_battery_level": 16,
    # Power totals
    "ac_input_power": 10,  # AC first in Input section
    "dc_port_input_power": 20, "in_watts": 20,  # DC second
    "input_power": 30, "output_power": 31,  # Total last
    "input_watts": 20, "output_watts": 21,
    "watts_in_sum": 22, "watts_out_sum": 23,
    "in_watts": 24, "out_watts": 25,
    # Charge/discharge time
    "remaining_time_charging": 30, "remaining_time_discharging": 31,
    "remain_time_charging": 30, "remain_time_discharging": 31,
    "chg_remain_time": 30, "dsg_remain_time": 31,
    "remain_time": 32,
    # Port states (in Ports group)
    "ac_ports": 10, "cfg_ac_enabled": 10,
    "usb_ports": 11, "dc_out_state": 11,
    "usb_total": 12,  # aggregated USB power
    "dc_12v_port": 15, "car_state": 15,
    # Port power
    "ac_output_power": 20,
    # Temperature
    "cell_temperature": 60,
    "battery_1_cell_temperature": 61, "battery_2_cell_temperature": 62,
    "max_cell_temp": 63, "min_cell_temp": 64,
    "max_cell_vol": 55, "min_cell_vol": 56,
    "mppt_temp": 65,
    "max_mos_temp": 68, "min_mos_temp": 69,
    # Battery health (most important in Battery group)
    "cycles": 50, "soh": 51,
    # Capacity
    "master_design_cap": 70, "master_remain_cap": 71, "master_full_cap": 72,
    "slave_design_cap": 73, "slave_remain_cap": 74, "slave_full_cap": 75,
    "design_cap": 70, "remain_cap": 71, "full_cap": 72,
    "vol": 75, "amp": 76,
    # Settings importance
    "energy_backup": 500, "energy_backup_enabled": 500,
    "energy_backup_battery_level": 501, "bp_power_soc": 501,
    "battery_charge_limit_max": 20, "battery_charge_limit_min": 21,
    "max_charge_soc": 20, "min_dsg_soc": 21,
    "ac_xboost": 30, "cfg_ac_xboost": 30,
    "open_ups_flag": 35,
    "ac_charging_speed": 40, "cfg_chg_watts": 40,
    "max_ac_charging_power": 41,
    "dc_charging_max_amps": 50,
    "cfg_dc_chg_current": 50,
    "dc_mode": 55,
    "standby_min": 100, "standby_mins": 100, "cfg_standby_min": 100,
    "ac_standby_mins": 101, "car_standby_mins": 102,
    "power_standby_mins": 103, "screen_standby_mins": 104,
    "lcd_brightness": 110, "lcd_off_sec": 111,
    "beep_mode": 120, "beep_state": 121,
    # System
    "err_code": 10, "error_code": 10,
    "sys_chg_dsg_state": 20, "syc_chg_dsg_state": 20,
    "relay_switch_count": 30, "reply_switchcnt": 30,
    "wifi_rssi": 40,
    "sys_ver": 90, "wifi_ver": 91, "sw_ver": 92,
    "battery_1_sn": 95, "battery_2_sn": 96,
    # MPPT I/O
    "in_vol": 50, "in_amp": 51,
    "out_val": 52, "out_amp": 53,
}


# Raw int → display string for known config enums
_RAW_VALUE_MAP = {
    "cfg_chg_type": {0: "Auto", 1: "Solar", 2: "Car"},
    "cfg_ac_xboost": {0: "OFF", 1: "ON"},
    "cfg_ac_enabled": {0: "OFF", 1: "ON"},
}

# Raw fields worth showing that aren't exposed at device level
_INTERESTING_RAW_FIELDS = {
    "cycles", "soh",                        # battery health
    "design_cap", "remain_cap", "full_cap", # capacity (devices that don't expose these)
    "in_watts",                             # MPPT/DC input power
    "cfg_ac_xboost",                        # X-Boost (devices that don't expose it)
    "cfg_chg_type",                         # DC mode (devices that don't expose dc_mode)
    "cfg_dc_chg_current",                   # DC charge current limit
}

_CAPACITY_FIELDS = {"design_cap", "remain_cap", "full_cap",
                     "master_design_cap", "master_remain_cap", "master_full_cap",
                     "slave_design_cap", "slave_remain_cap", "slave_full_cap"}
