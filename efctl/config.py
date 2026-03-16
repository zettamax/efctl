"""User configuration stored in ~/.efctl/config.json"""

import json
import re
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

CONFIG_DIR = Path.home() / ".efctl"
CONFIG_FILE = CONFIG_DIR / "config.json"
MAX_NAME_LEN = 10


def sanitize_name(name: str) -> str:
    clean = re.sub(r'[^a-zA-Z0-9_\-]', '_', name)
    # Collapse multiple underscores
    clean = re.sub(r'_+', '_', clean).strip('_')
    return clean[:MAX_NAME_LEN]


def default_name_from_model(model: str) -> str:
    """EcoFlow RIVER 2 Pro → RIVER_2_Pro"""
    short = model.replace("EcoFlow ", "")
    return sanitize_name(short)


@dataclass
class DeviceEntry:
    address: str
    serial_number: str
    model: str
    name: Optional[str] = None
    last_seen: float = 0.0

    @property
    def display_name(self) -> str:
        return self.name or default_name_from_model(self.model)


@dataclass
class Config:
    user_id: str = ""
    devices: list[DeviceEntry] = field(default_factory=list)

    def find_device(self, identifier: str) -> Optional[DeviceEntry]:
        ident = identifier.upper()
        for dev in self.devices:
            if (dev.address.upper() == ident
                    or dev.serial_number.upper() == ident
                    or (dev.name and dev.name.upper() == ident)
                    or dev.display_name.upper() == ident):
                return dev
        for dev in self.devices:
            if dev.address.upper().endswith(ident):
                return dev
        return None

    def add_device(self, address: str, serial_number: str, model: str,
                   name: Optional[str] = None) -> DeviceEntry:
        clean_name = sanitize_name(name) if name else None
        for dev in self.devices:
            if dev.address.upper() == address.upper():
                dev.serial_number = serial_number
                dev.model = model
                if clean_name:
                    dev.name = clean_name
                dev.last_seen = time.time()
                return dev
        entry = DeviceEntry(address=address, serial_number=serial_number,
                            model=model, name=clean_name, last_seen=time.time())
        self.devices.append(entry)
        return entry

    def remove_device(self, address: str) -> bool:
        before = len(self.devices)
        self.devices = [d for d in self.devices if d.address.upper() != address.upper()]
        return len(self.devices) < before

    def device_names(self) -> list[str]:
        names = []
        for d in self.devices:
            names.append(d.display_name)
            if d.name and d.name != d.display_name:
                names.append(d.name)
        return names


def load_config() -> Config:
    if not CONFIG_FILE.exists():
        return Config()
    try:
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)
        devices = []
        for d in data.get("devices", []):
            devices.append(DeviceEntry(
                address=d["address"], serial_number=d["serial_number"],
                model=d["model"], name=d.get("name"),
                last_seen=d.get("last_seen", 0.0),
            ))
        return Config(user_id=data.get("user_id", ""), devices=devices)
    except (json.JSONDecodeError, TypeError, KeyError):
        return Config()


def save_config(config: Config) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "user_id": config.user_id,
        "devices": [asdict(d) for d in config.devices],
    }
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)
