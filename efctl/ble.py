"""BLE scanning, connection, and device summary extraction."""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional, Callable, Any

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from .eflib import NewDevice, sn_from_advertisement
from .eflib.devicebase import DeviceBase
from .eflib.device_mappings import ECOFLOW_DEVICE_LIST
from .eflib.connection import ConnectionState

log = logging.getLogger(__name__)


@dataclass
class ScannedDevice:
    ble_device: BLEDevice
    adv_data: AdvertisementData
    serial_number: str
    model: str
    address: str

    @property
    def display(self) -> str:
        return f"{self.model}  SN:{self.serial_number}  [{self.address}]"


@dataclass
class ManagedDevice:
    entry: Any
    ef_device: Optional[DeviceBase] = None
    connected: bool = False
    state: str = "idle"
    messages: dict[str, Any] = field(default_factory=dict)
    last_update_ts: float = 0.0
    last_packet_ts: float = 0.0
    parsed_messages: dict[str, Any] = field(default_factory=dict)
    reconnect_attempt: int = 0
    reconnect_max: int = 0


def model_from_sn(sn: str) -> str:
    for prefix_len in (4, 3, 2):
        prefix = sn[:prefix_len]
        if prefix in ECOFLOW_DEVICE_LIST:
            return ECOFLOW_DEVICE_LIST[prefix]["name"]
    return f"Unknown ({sn[:4]})"


async def scan_devices(duration: float = 5.0,
                       callback: Optional[Callable[[ScannedDevice], None]] = None
                       ) -> list[ScannedDevice]:
    found: dict[str, ScannedDevice] = {}

    def on_discovery(device: BLEDevice, adv_data: AdvertisementData):
        if device.address in found:
            return
        sn_bytes = sn_from_advertisement(adv_data)
        if sn_bytes is None:
            return
        sn = sn_bytes.decode("ASCII").rstrip("\x00")
        model = model_from_sn(sn)
        sd = ScannedDevice(
            ble_device=device, adv_data=adv_data,
            serial_number=sn, model=model, address=device.address,
        )
        found[device.address] = sd
        if callback:
            callback(sd)

    scanner = BleakScanner(detection_callback=on_discovery)
    try:
        async with scanner:
            await asyncio.sleep(duration)
    except FileNotFoundError:
        raise RuntimeError(
            "BLE adapter not found. Ensure your system's Bluetooth stack is "
            "installed and the Bluetooth service is running."
        )
    except Exception as e:
        raise RuntimeError(f"BLE scan failed: {e}")

    return list(found.values())


async def connect_device(scanned: ScannedDevice, user_id: str,
                         ) -> Optional[DeviceBase]:
    ef_dev = NewDevice(scanned.ble_device, scanned.adv_data)
    if ef_dev is None:
        log.error("Cannot create device for %s", scanned.address)
        return None

    await ef_dev.connect(user_id=user_id, timeout=30)
    state = await ef_dev.wait_until_authenticated_or_error(raise_on_error=False)

    if state != ConnectionState.AUTHENTICATED:
        log.error("Auth failed for %s: state=%s", scanned.address, state)
        return None

    return ef_dev


# --- Device summary for dashboard ---

STANDARD_METRICS = [
    ("Battery",    "battery_level",     "%"),
    ("Input",      "input_power",       "W"),
    ("Output",     "output_power",      "W"),
    ("Cell Temp",  "cell_temperature",  "°C"),
]

TIME_METRICS = [
    ("charge_time",    "remaining_time_charging"),
    ("charge_time",    "remain_time_charging"),
    ("discharge_time", "remaining_time_discharging"),
    ("discharge_time", "remain_time_discharging"),
]

MAX_DISPLAY_MINUTES = 2880

# (label, bool attribute for on/off state)
PORT_ATTRS = [
    ("AC",  "ac_ports"),
    ("USB", "usb_ports"),
    ("DC",  "dc_12v_port"),
]


def get_device_summary(ef_device: DeviceBase) -> dict[str, Any]:
    """Returns {metrics, charge_time, discharge_time, ports}.

    ports: only includes entries where the device class actually declares
    the control attribute. If declared but value is None → included as None.
    If not declared at all → NOT included (port row won't show it).
    """
    result = {
        "metrics": {},
        "charge_time": None,
        "discharge_time": None,
        "ports": {},
        "xboost": None,
        "cycles": None,
    }

    for label, attr, unit in STANDARD_METRICS:
        val = getattr(ef_device, attr, None)
        result["metrics"][label] = (val, unit) if val is not None else None

    for key, attr in TIME_METRICS:
        val = getattr(ef_device, attr, None)
        if val is not None and 0 < int(val) <= MAX_DISPLAY_MINUTES:
            result[key] = int(val)

    # Only include ports that the device CLASS declares as a field/property
    dev_class = type(ef_device)
    for label, attr in PORT_ATTRS:
        # Walk MRO to check if any class in the hierarchy defines this
        declared = any(
            attr in cls.__dict__ for cls in dev_class.__mro__
            if cls is not object
        )
        if declared:
            val = getattr(ef_device, attr, None)
            result["ports"][label] = bool(val) if val is not None else None

    # X-Boost
    xboost = getattr(ef_device, 'ac_xboost', None)
    if xboost is not None:
        result["xboost"] = bool(xboost)

    return result
