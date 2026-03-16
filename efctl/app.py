"""Textual TUI for efctl."""

import asyncio
import re as _re
import signal
import time
from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Static, Input, Label, RichLog
from textual.binding import Binding
from textual.suggester import Suggester
from textual import work

from .config import Config, save_config, MAX_NAME_LEN
from .ble import (
    ScannedDevice, ManagedDevice, scan_devices, connect_device,
    get_device_summary,
)
from .fields import get_device_fields_grouped
from .eflib.props.raw_data_props import RawDataProps


# --- Constants ---

W = 34
IW = W - 2
LOADER = "◉"
LOADER_DURATION = 1.0
STALE_DATA_TIMEOUT = 60
UI_TICK_INTERVAL = 5
AUTO_CONNECT_INTERVAL = 15

COMMANDS = ["scan", "list", "add", "on", "off", "set", "show", "remove", "help", "exit"]
PORTS = ["ac", "dc", "usb"]
SETTINGS = ["xboost", "charge-level", "discharge-level", "charge-power"]

# Setting definitions: (display_name, value_type, method_names, hint)
SETTING_DEFS = {
    "xboost": {
        "display": "X-Boost",
        "type": "bool",
        "methods": ["enable_ac_xboost", "enable_xboost"],
        "hint": "on/off",
    },
    "charge-level": {
        "display": "Charge Level",
        "type": "percent",
        "methods": ["set_battery_charge_limit_max"],
        "hint": "50-100",
        "attr": "battery_charge_limit_max",
        "min": 50, "max": 100,
    },
    "discharge-level": {
        "display": "Discharge Level",
        "type": "percent",
        "methods": ["set_battery_charge_limit_min"],
        "hint": "0-30",
        "attr": "battery_charge_limit_min",
        "min": 0, "max": 30,
    },
    "charge-power": {
        "display": "Charge Power",
        "type": "watts",
        "methods": ["set_ac_charging_speed"],
        "hint": "W",
        "min_attr": "min_ac_charging_power",
        "max_attr": "max_ac_charging_power",
        "attr": "ac_charging_speed",
        "hard_min": 100,
    },
}


def _fmt_time(minutes):
    if minutes <= 0:
        return ""
    if minutes < 60:
        return f"{minutes}m"
    h, m = divmod(minutes, 60)
    return f"{h}h{m}m" if m else f"{h}h"


def _fmt_ago(ts):
    if ts <= 0:
        return ""
    elapsed = time.time() - ts
    if elapsed < 10:
        return ""
    if elapsed < 60:
        return f"{int(elapsed)}s ago"
    if elapsed < 3600:
        return f"{int(elapsed / 60)}m ago"
    return f"{int(elapsed / 3600)}h ago"


def _plain(s):
    return _re.sub(r'\[/?[^\]]*\]', '', s)


# --- Device block ---

class DeviceBlock(Static):

    def __init__(self, entry, managed=None, **kwargs):
        super().__init__(**kwargs, markup=True)
        self.entry = entry
        self.managed = managed

    def render_block(self):
        entry = self.entry
        managed = self.managed
        name = entry.display_name[:MAX_NAME_LEN]
        connected = managed is not None and managed.connected
        reconnecting = managed is not None and managed.state == "reconnecting"

        h = "─" * IW
        lines = [f"┌{h}┐"]

        # Header
        if reconnecting:
            dot = "[yellow]↻[/]"
        elif connected:
            dot = "[green]●[/]"
        else:
            dot = "[dim]○[/]"

        time_str = ""
        summary = managed.messages.get("_summary") if managed else None
        if summary:
            ct = summary.get("charge_time")
            dt = summary.get("discharge_time")
            if ct and ct > 0:
                time_str = f" ↑{_fmt_time(ct)}"
            elif dt and dt > 0:
                time_str = f" ↓{_fmt_time(dt)}"

        show_loader = (connected and managed and managed.last_update_ts > 0
                       and (time.time() - managed.last_update_ts) < LOADER_DURATION)
        loader = f"{LOADER} " if show_loader else ""

        left = f" {dot} [bold]{name}[/]{time_str}"
        if reconnecting:
            loader = "…reconnect "  # right-aligned reconnect indicator
        avail = IW - len(loader)
        pad = avail - len(_plain(left))
        if pad < 1:
            pad = 1
        lines.append(f"│{left}{' ' * pad}{loader}│")

        # Address + ago
        last_ts = 0
        if managed and managed.last_packet_ts > 0:
            last_ts = managed.last_packet_ts
        elif entry.last_seen > 0:
            last_ts = entry.last_seen
        ago = _fmt_ago(last_ts)
        addr_plain = f" {entry.address}"
        if ago:
            gap = IW - len(addr_plain) - len(ago) - 1
            if gap < 1:
                gap = 1
            lines.append(f"│ [dim]{entry.address}[/]{' ' * gap}[dim]{ago}[/] │")
        else:
            lines.append(f"│ [dim]{entry.address}[/]{' ' * (IW - len(addr_plain))}│")

        lines.append(f"├{h}┤")

        # Metrics
        if summary and isinstance(summary, dict):
            m = summary.get("metrics", {})
            for label, val_tuple in m.items():
                if val_tuple is not None:
                    value, unit = val_tuple
                    val_str = f"{value:.1f}" if isinstance(value, float) else str(value)
                    line = f" {label + ':':<12s} {val_str}{unit}"
                else:
                    line = f" {label + ':':<12s} —"
                lines.append(f"│{line[:IW].ljust(IW)}│")

            cycles = summary.get("cycles")
            xboost = summary.get("xboost")
            if cycles is not None:
                line = f" {'Cycles:':<12s} {cycles}"
                lines.append(f"│{line[:IW].ljust(IW)}│")
            if xboost is not None:
                line = f" {'X-Boost:':<12s} {'ON' if xboost else 'OFF'}"
                lines.append(f"│{line[:IW].ljust(IW)}│")

            ports = summary.get("ports", {})
            if ports:
                lines.append(f"├{h}┤")
                badges = []
                plain_badges = []
                for plabel, pval in ports.items():
                    badge_text = f" {plabel} "
                    plain_badges.append(badge_text)
                    if pval is True:
                        badges.append(f"[black on green]{badge_text}[/]")
                    else:
                        badges.append(f"[dim]{badge_text}[/]")
                badge_line = "  ".join(badges)
                plain_total = len("  ".join(plain_badges))
                lpad = (IW - plain_total) // 2
                rpad = IW - lpad - plain_total
                lines.append(f"│{' ' * lpad}{badge_line}{' ' * rpad}│")
        else:
            line = " waiting for data..."
            lines.append(f"│[dim]{line.ljust(IW)}[/]│")

        lines.append(f"└{h}┘")
        return "\n".join(lines)

    def refresh_data(self, managed):
        self.managed = managed
        self.update(self.render_block())

    def on_mount(self):
        self.update(self.render_block())


# --- Detail view ---

class DeviceDetail(VerticalScroll):

    def __init__(self, entry, managed, **kwargs):
        super().__init__(**kwargs)
        self.entry = entry
        self.managed = managed

    def compose(self) -> ComposeResult:
        connected = self.managed.connected if self.managed else False
        dot = "[green]●[/]" if connected else "[dim]○[/]"
        yield Label(
            f"{dot} [bold]{self.entry.display_name}[/]  "
            f"[dim]{self.entry.model}  {self.entry.address}[/]",
        )
        yield Static("[dim]─────────────────────────────────────────[/]")
        yield Static("", id="detail-body")

    def refresh_data(self, managed):
        self.managed = managed
        groups = get_device_fields_grouped(managed) if managed else []
        lines = []
        for group_name, fields in groups:
            lines.append(f"\n[bold yellow] {group_name}[/]")
            for label, value in fields:
                lines.append(f"   {label:<30s} {value}")
        body = self.query_one("#detail-body", Static)
        body.update("\n".join(lines) if lines else "[dim]Waiting for data...[/]")


# --- Autocomplete ---

class CommandSuggester(Suggester):

    def __init__(self, config: Config):
        super().__init__(use_cache=False)
        self.config = config

    async def get_suggestion(self, value: str) -> str | None:
        if not value:
            return None
        parts = value.split()
        if len(parts) <= 1 and not value.endswith(" "):
            prefix = value.lower()
            matches = [c for c in COMMANDS if c.startswith(prefix) and c != prefix]
            if len(matches) == 1:
                return matches[0]
            return None

        verb = parts[0].lower()

        # Device name completion (2nd arg for most commands)
        if verb in ("show", "remove", "rm", "add", "on", "off", "set"):
            if len(parts) == 1 and value.endswith(" "):
                names = self.config.device_names()
                return f"{verb} {names[0]}" if names else None
            elif len(parts) == 2 and not value.endswith(" "):
                prefix = parts[1].upper()
                for n in self.config.device_names():
                    if n.upper().startswith(prefix) and n.upper() != prefix:
                        return f"{verb} {n}"

        # Port completion for on/off (3rd arg)
        if verb in ("on", "off"):
            if len(parts) == 3 and not value.endswith(" "):
                prefix = parts[2].lower()
                for p in PORTS:
                    if p.startswith(prefix) and p != prefix:
                        return f"{parts[0]} {parts[1]} {p}"

        # Setting name completion for set (3rd arg)
        if verb == "set":
            if len(parts) == 3 and not value.endswith(" "):
                prefix = parts[2].lower()
                matches = [s for s in SETTINGS if s.startswith(prefix) and s != prefix]
                if len(matches) == 1:
                    return f"{parts[0]} {parts[1]} {matches[0]}"
                elif len(matches) > 1:
                    common = matches[0]
                    for m in matches[1:]:
                        while not m.startswith(common):
                            common = common[:-1]
                    if common and common != prefix:
                        return f"{parts[0]} {parts[1]} {common}"
            # Value completion for set (4th arg)
            if len(parts) == 4 and not value.endswith(" "):
                sdef = SETTING_DEFS.get(parts[2].lower())
                if sdef and sdef["type"] == "bool":
                    prefix = parts[3].lower()
                    for v in ("on", "off"):
                        if v.startswith(prefix) and v != prefix:
                            return f"{parts[0]} {parts[1]} {parts[2]} {v}"

        return None


# --- Main app ---

class EfctlTextual(App):
    CSS = """
    Screen { layout: vertical; }
    #dashboard { height: auto; max-height: 50%; padding: 1; }
    .device-block { width: auto; height: auto; margin: 0 1 0 0; }
    #no-devices { padding: 1; }
    #command-input {
        margin: 0;
        border-top: solid $surface-darken-1;
        border-bottom: solid $surface-darken-1;
    }
    #output { height: 1fr; scrollbar-size: 1 1; }
    #detail-view { height: 1fr; padding: 0 1; }
    """

    BINDINGS = [
        Binding("escape", "exit_detail", "Back", show=False),
        Binding("ctrl+c", "safe_quit", "Quit"),
    ]

    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self.managed: dict[str, ManagedDevice] = {}
        self.scanned: dict[str, ScannedDevice] = {}
        self.device_blocks: dict[str, DeviceBlock] = {}
        self._detail_view = None
        self._detail_address = None
        self._history: list[str] = []
        self._history_pos: int = -1

    def compose(self) -> ComposeResult:
        with Horizontal(id="dashboard"):
            if not self.config.devices:
                h = "─" * IW
                empty = (
                    f"┌{h}┐\n"
                    f"│{' No devices'.ljust(IW)}│\n"
                    f"│{' Use scan / add'.ljust(IW)}│\n"
                    f"│{''.ljust(IW)}│\n"
                    f"│{''.ljust(IW)}│\n"
                    f"│{''.ljust(IW)}│\n"
                    f"│{''.ljust(IW)}│\n"
                    f"│{''.ljust(IW)}│\n"
                    f"└{h}┘"
                )
                yield Static(f"[dim]{empty}[/]", classes="device-block", id="no-devices")
            for entry in self.config.devices:
                block = DeviceBlock(entry, classes="device-block",
                                    id=f"dev-{entry.address.replace(':', '')}")
                self.device_blocks[entry.address.upper()] = block
                yield block
        yield Input(placeholder="efctl> ", id="command-input",
                    suggester=CommandSuggester(self.config))
        output = VerticalScroll(id="output")
        output.can_focus = False
        yield output

    def on_mount(self):
        self.query_one("#command-input", Input).focus()
        self._start_timers()
        self.start_background()

    def _start_timers(self):
        """Periodic UI refresh for ago counters, loader cleanup, stale pings."""
        self.set_interval(UI_TICK_INTERVAL, self._ui_tick)

    def _ui_tick(self):
        """Refresh all blocks (ago, loader) and check stale connections."""
        now = time.time()
        for addr, managed in self.managed.items():
            # Stale data ping
            if (managed.connected and managed.last_update_ts > 0
                    and (now - managed.last_update_ts) > STALE_DATA_TIMEOUT
                    and managed.ef_device):
                try:
                    conn = getattr(managed.ef_device, '_conn', None)
                    if conn and getattr(conn, 'is_connected', False):
                        asyncio.ensure_future(conn.send_auth_status_packet())
                except Exception:
                    pass
            # Refresh block display
            if addr in self.device_blocks:
                self.device_blocks[addr].refresh_data(managed)
        # Refresh detail view if open
        if self._detail_view and self._detail_address:
            managed = self.managed.get(self._detail_address)
            if managed:
                self._detail_view.refresh_data(managed)

    def action_safe_quit(self):
        save_config(self.config)
        self.exit()

    # --- Output (reverse order: newest command block on top) ---

    def log_message(self, msg: str):
        """Add a message. Prepends at top of output (newest first)."""
        try:
            output = self.query_one("#output", VerticalScroll)
            widget = Static(msg, markup=True)
            widget.can_focus = False
            output.mount(widget, before=0)
            # Trim
            children = list(output.children)
            if len(children) > 500:
                for child in children[500:]:
                    child.remove()
        except Exception:
            pass

    def _begin_busy(self, label: str = "Operation in progress..."):
        """Disable input, show progress indicator at top of output."""
        inp = self.query_one("#command-input", Input)
        inp.disabled = True
        inp.placeholder = label
        try:
            output = self.query_one("#output", VerticalScroll)
            indicator = Static(f"[bold yellow]⏳ {label}[/]", id="busy-indicator", markup=True)
            indicator.can_focus = False
            output.mount(indicator, before=0)
        except Exception:
            pass

    def _end_busy(self):
        """Remove progress indicator, re-enable input."""
        inp = self.query_one("#command-input", Input)
        inp.disabled = False
        inp.placeholder = "efctl> "
        try:
            self.query_one("#busy-indicator").remove()
        except Exception:
            pass
        inp.focus()

    def log_block(self, *messages: str):
        """Log a command block with separator on top. Messages appear top-to-bottom."""
        ts = time.strftime("%H:%M:%S")
        # Prepend in reverse so they read top-to-bottom
        # Last mounted at before=0 ends up on top
        all_lines = [f"[dim]{ts} {'─' * 30}[/]"] + list(messages)
        try:
            output = self.query_one("#output", VerticalScroll)
            for msg in reversed(all_lines):
                widget = Static(msg, markup=True)
                widget.can_focus = False
                output.mount(widget, before=0)
            children = list(output.children)
            if len(children) > 500:
                for child in children[500:]:
                    child.remove()
        except Exception:
            pass

    # --- Input handling ---

    def on_key(self, event) -> None:
        inp = self.query_one("#command-input", Input)
        if event.key == "tab":
            event.prevent_default()
            event.stop()
            if not inp.has_focus:
                inp.focus()
                return
            # Accept suggestion (Textual uses Right arrow, we remap Tab)
            inp.action_cursor_right()
            return
        if not inp.has_focus:
            # Any keypress returns focus to input
            inp.focus()
            return
        if event.key == "up":
            if self._history:
                if self._history_pos == -1:
                    self._history_pos = len(self._history) - 1
                elif self._history_pos > 0:
                    self._history_pos -= 1
                inp.value = self._history[self._history_pos]
                inp.cursor_position = len(inp.value)
            event.prevent_default()
        elif event.key == "down":
            if self._history and self._history_pos != -1:
                self._history_pos += 1
                if self._history_pos >= len(self._history):
                    self._history_pos = -1
                    inp.value = ""
                else:
                    inp.value = self._history[self._history_pos]
                    inp.cursor_position = len(inp.value)
            event.prevent_default()

    def on_input_submitted(self, event: Input.Submitted):
        cmd = event.value.strip()
        event.input.value = ""
        self._history_pos = -1
        if not cmd:
            return
        self._history.append(cmd)
        self._handle_command(cmd)

    # --- Commands ---

    def _handle_command(self, cmd: str):
        parts = cmd.split()
        verb = parts[0].lower()
        args = parts[1:]

        if verb in ("quit", "exit", "q"):
            self.action_safe_quit()
            return

        if verb == "help":
            self.log_block(
                "Commands:\n"
                "  [bold]scan[/]                    Scan for BLE devices\n"
                "  [bold]list[/]                    List saved devices\n"
                "  [bold]add[/] DEV \\[NAME]          Add device\n"
                "  [bold]on[/] DEV PORT             Turn port on (ac/dc/usb)\n"
                "  [bold]off[/] DEV PORT            Turn port off\n"
                "  [bold]set[/] DEV SETTING VALUE   Change setting\n"
                "  [bold]show[/] DEV                Detailed device view\n"
                "  [bold]remove[/] DEV              Remove & disconnect\n"
                "  [bold]help[/]                    Show this help\n"
                "  [bold]exit[/]                    Exit\n"
                "\n"
                "Settings: xboost (on/off), charge-level (0-100),\n"
                "  discharge-level (0-100), charge-power (W)"
            )
        elif verb == "scan":
            self._do_scan()
        elif verb == "add":
            if not args:
                self.log_block("Usage: add DEV \\[NAME]")
            else:
                self._do_add(args[0], args[1] if len(args) > 1 else None)
        elif verb in ("list", "ls"):
            self._do_list()
        elif verb == "show":
            if not args:
                self.log_block("Usage: show DEV")
            else:
                self._do_show(args[0])
        elif verb == "set":
            if not args:
                self.log_block("Usage: set DEV SETTING VALUE\nSettings: xboost, charge-level, discharge-level, charge-power")
            elif len(args) == 1:
                self._do_set_show(args[0])
            elif len(args) == 2:
                # Show hint for the setting
                sdef = SETTING_DEFS.get(args[1].lower())
                if sdef:
                    self.log_block(f"Usage: set {args[0]} {args[1]} ({sdef['hint']})")
                else:
                    self.log_block(f"Unknown setting '{args[1]}'. Available: {', '.join(SETTINGS)}")
            else:
                self._do_set(args[0], args[1], args[2])
        elif verb == "on":
            if len(args) < 2:
                self.log_block("Usage: on DEV ac|dc|usb")
            else:
                self._do_port(args[0], args[1], True)
        elif verb == "off":
            if len(args) < 2:
                self.log_block("Usage: off DEV ac|dc|usb")
            else:
                self._do_port(args[0], args[1], False)
        elif verb in ("remove", "rm"):
            if not args:
                self.log_block("Usage: remove DEV")
            else:
                self._do_remove(args[0])
        else:
            self.log_block(f"Unknown: '{verb}'. Type 'help'.")

    def _do_list(self):
        if not self.config.devices:
            self.log_block("No saved devices. Run 'scan' then 'add'.")
            return
        lines = ["Saved devices:"]
        for entry in self.config.devices:
            managed = self.managed.get(entry.address.upper())
            if managed and managed.connected:
                dot = "[green]●[/]"
            elif managed and managed.state == "reconnecting":
                dot = "[yellow]↻[/]"
            else:
                dot = "[dim]○[/]"
            name = entry.display_name[:MAX_NAME_LEN].ljust(MAX_NAME_LEN)
            lines.append(f" {dot} {name}  {entry.address}  {entry.serial_number}")
        self.log_block(*lines)

    def _do_set_show(self, identifier: str):
        """Show current settings for a device."""
        entry = self.config.find_device(identifier)
        if not entry:
            self.log_block(f"[red]ERROR: '{identifier}' not found.[/]")
            return
        managed = self.managed.get(entry.address.upper())
        ef = managed.ef_device if managed and managed.connected else None
        if not ef:
            self.log_block(f"[red]ERROR: '{entry.display_name}' not connected.[/]")
            return

        lines = [f"Settings for {entry.display_name}:"]
        for sname, sdef in SETTING_DEFS.items():
            # Check if device supports this setting (xboost always available via raw packet)
            method = None
            for m in sdef["methods"]:
                if hasattr(ef, m):
                    method = m
                    break
            is_available = method is not None or sname == "xboost"
            available = "  " if is_available else "  [dim]"
            suffix = "[/]" if not is_available else ""

            # Get current value
            attr = sdef.get("attr")
            if sdef["type"] == "bool":
                val = getattr(ef, "ac_xboost", None)
                if val is None:
                    # Check raw MPPT
                    for msg in (managed.parsed_messages or {}).values():
                        if hasattr(msg, 'cfg_ac_xboost'):
                            val = getattr(msg, 'cfg_ac_xboost') == 1
                            break
                val_str = "ON" if val else "OFF" if val is not None else "—"
            elif attr:
                val = getattr(ef, attr, None)
                if val is not None:
                    if sdef["type"] == "percent":
                        val_str = f"{int(val)}%"
                    elif sdef["type"] == "watts":
                        val_str = f"{int(val)} W"
                    else:
                        val_str = str(val)
                else:
                    val_str = "—"
            else:
                val_str = "—"

            hint = sdef["hint"]
            if sdef["type"] == "percent":
                hint = f"{sdef.get('min', 0)}-{sdef.get('max', 100)}%"
            elif sdef["type"] == "watts":
                hard_min = sdef.get("hard_min", 100)
                mn = getattr(ef, sdef.get("min_attr", ""), None)
                mx = getattr(ef, sdef.get("max_attr", ""), None)
                mn = max(int(mn or hard_min), hard_min)
                mx = int(mx) if mx else 9999
                hint = f"{mn}-{mx} W"

            lines.append(f"{available}{sdef['display']:<20s} {val_str:<10s} ({hint}){suffix}")
            if not is_available:
                lines[-1] = lines[-1].rstrip("[/]") + " — not available[/]"

        self.log_block(*lines)

    async def _set_xboost(self, ef_device, enabled: bool):
        """Set X-Boost on any device — uses raw packet if no method available."""
        if hasattr(ef_device, 'enable_ac_xboost'):
            await ef_device.enable_ac_xboost(enabled)
        elif hasattr(ef_device, 'enable_xboost'):
            await ef_device.enable_xboost(enabled)
        else:
            # Delta2 variants: same cmd 0x42 as enable_ac_ports, byte[1] is xboost
            from .eflib.packet import Packet
            payload = bytes([0xFF, 0x01 if enabled else 0x00, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF])
            dst = getattr(ef_device, 'ac_commands_dst', 0x05)
            packet = Packet(0x21, dst, 0x20, 0x42, payload, version=0x02)
            await ef_device._conn.sendPacket(packet)

    @work(thread=False)
    async def _do_set(self, identifier: str, setting: str, value: str):
        """Change a device setting."""
        entry = self.config.find_device(identifier)
        if not entry:
            self.log_block(f"[red]ERROR: '{identifier}' not found.[/]")
            return
        managed = self.managed.get(entry.address.upper())
        ef = managed.ef_device if managed and managed.connected else None
        if not ef:
            self.log_block(f"[red]ERROR: '{entry.display_name}' not connected.[/]")
            return

        sdef = SETTING_DEFS.get(setting.lower())
        if not sdef:
            self.log_block(f"[red]ERROR: Unknown setting '{setting}'.[/]\nAvailable: {', '.join(SETTINGS)}")
            return

        # Find method (xboost always available via raw packet fallback)
        is_xboost = setting.lower() == "xboost"
        method = None
        for m in sdef["methods"]:
            if hasattr(ef, m):
                method = m
                break
        if not method and not is_xboost:
            self.log_block(f"[red]ERROR: {sdef['display']} not available on {entry.display_name}.[/]")
            return

        # Parse and validate value
        if sdef["type"] == "bool":
            if value.lower() in ("on", "1", "true", "yes"):
                parsed = True
            elif value.lower() in ("off", "0", "false", "no"):
                parsed = False
            else:
                self.log_block(f"[red]ERROR: Invalid value '{value}'. Use: on/off[/]")
                return
        elif sdef["type"] == "percent":
            try:
                parsed = int(value)
            except ValueError:
                self.log_block(f"[red]ERROR: Invalid value '{value}'. Use: 0-100[/]")
                return
            lo = sdef.get("min", 0)
            hi = sdef.get("max", 100)
            if parsed < lo or parsed > hi:
                self.log_block(f"[red]ERROR: {sdef['display']} must be {lo}-{hi}%, got {parsed}[/]")
                return
            # Cross-validate charge vs discharge levels
            if setting.lower() == "charge-level":
                discharge = getattr(ef, "battery_charge_limit_min", 0) or 0
                if parsed <= int(discharge):
                    self.log_block(f"[red]ERROR: Charge level ({parsed}%) must be > discharge level ({int(discharge)}%)[/]")
                    return
            elif setting.lower() == "discharge-level":
                charge = getattr(ef, "battery_charge_limit_max", 100) or 100
                if parsed >= int(charge):
                    self.log_block(f"[red]ERROR: Discharge level ({parsed}%) must be < charge level ({int(charge)}%)[/]")
                    return
        elif sdef["type"] == "watts":
            try:
                parsed = int(value)
            except ValueError:
                self.log_block(f"[red]ERROR: Invalid value '{value}'. Use a number in watts.[/]")
                return
            hard_min = sdef.get("hard_min", 1)
            mn = getattr(ef, sdef.get("min_attr", ""), None)
            mx = getattr(ef, sdef.get("max_attr", ""), None)
            mn = max(int(mn or hard_min), hard_min)
            mx = int(mx) if mx else 9999
            if parsed < mn or parsed > mx:
                self.log_block(f"[red]ERROR: Value must be {mn}-{mx} W, got {parsed}[/]")
                return

        # Execute
        self._begin_busy(f"Setting {sdef['display']}...")
        try:
            if is_xboost:
                result = await self._set_xboost(ef, parsed)
            else:
                result = await getattr(ef, method)(parsed)
            if result is False:
                self._end_busy()
                self.log_block(f"[red]ERROR: Device rejected the value.[/]")
                return
            self._end_busy()
            if sdef["type"] == "bool":
                val_str = "ON" if parsed else "OFF"
            elif sdef["type"] == "percent":
                val_str = f"{parsed}%"
            else:
                val_str = f"{parsed} W"
            self.log_block(f"[green]{entry.display_name}: {sdef['display']} → {val_str}[/]")
        except Exception as e:
            self._end_busy()
            self.log_block(f"[red]ERROR: Failed to set {sdef['display']}: {e}[/]")

    def _do_show(self, identifier: str):
        entry = self.config.find_device(identifier)
        if not entry:
            self.log_block(f"[red]ERROR: '{identifier}' not found.[/]")
            return
        self.log_block(f"Opened detail view: {entry.display_name}")
        addr = entry.address.upper()
        managed = self.managed.get(addr)

        self._detail_address = addr
        detail = DeviceDetail(entry, managed, id="detail-view")
        self._detail_view = detail
        self.query_one("#dashboard").display = False
        self.query_one("#output").display = False
        self.query_one("#command-input").display = False
        self.mount(detail, before=self.query_one("#command-input"))
        if managed:
            detail.refresh_data(managed)

    def action_exit_detail(self):
        if self._detail_view:
            self._detail_view.remove()
            self._detail_view = None
            self._detail_address = None
            self.query_one("#dashboard").display = True
            self.query_one("#output").display = True
            self.query_one("#command-input").display = True
            self.query_one("#command-input", Input).focus()

    @work(thread=False)
    async def _do_scan(self):
        self._begin_busy("Scanning...")
        self.scanned.clear()
        try:
            results = await scan_devices(duration=5.0)
        except RuntimeError as e:
            self._end_busy()
            self.log_block(f"[red]ERROR: {e}[/]")
            return
        lines = []
        for sd in results:
            self.scanned[sd.address] = sd
            lines.append(f"  [green]{sd.display}[/]")
        header = f"Scan: {len(results)} device(s) found" if results else "Scan: no devices found"
        self._end_busy()
        self.log_block(header, *lines)

    @work(thread=False)
    async def _do_add(self, identifier: str, name=None):
        if not self.config.user_id:
            self.log_block("[red]ERROR: user_id not set.[/]")
            return
        ident = identifier.upper()
        sd = None
        for addr, s in self.scanned.items():
            if (addr.upper() == ident or s.serial_number.upper() == ident
                    or addr.upper().endswith(ident)):
                sd = s
                break
        if not sd:
            self.log_block(f"[red]ERROR: '{identifier}' not in scan results.[/]")
            return

        self._begin_busy(f"Connecting to {sd.model}...")
        ef_dev = await connect_device(sd, self.config.user_id)
        if not ef_dev:
            self._end_busy()
            self.log_block(f"[red]ERROR: Auth failed for {sd.address}[/]")
            return

        entry = self.config.add_device(sd.address, sd.serial_number, sd.model, name)
        save_config(self.config)

        managed = ManagedDevice(entry=entry, ef_device=ef_dev, connected=True, state="online")
        self.managed[sd.address.upper()] = managed
        self._setup_device(managed)

        block = DeviceBlock(entry, managed, classes="device-block",
                            id=f"dev-{entry.address.replace(':', '')}")
        self.device_blocks[entry.address.upper()] = block
        self.query_one("#dashboard").mount(block)

        self._end_busy()
        # Remove "no devices" placeholder if present
        try:
            self.query_one("#no-devices").remove()
        except Exception:
            pass
        self.log_block(f"[green]Added: {entry.display_name} \\[{sd.address}][/]")

    @work(thread=False)
    async def _do_port(self, device_id: str, port: str, enable: bool):
        entry = self.config.find_device(device_id)
        if not entry:
            self.log_block(f"[red]ERROR: '{device_id}' not found.[/]")
            return
        managed = self.managed.get(entry.address.upper())
        if not managed or not managed.connected or not managed.ef_device:
            self.log_block(f"[red]ERROR: '{entry.display_name}' not connected.[/]")
            return

        method_map = {"ac": "enable_ac_ports", "dc": "enable_dc_12v_port", "usb": "enable_usb_ports"}
        method = method_map.get(port.lower())
        if not method:
            self.log_block(f"[red]ERROR: Unknown port '{port}'[/]")
            return
        if not hasattr(managed.ef_device, method):
            self.log_block(f"[red]ERROR: {entry.display_name} has no {port.upper()} control.[/]")
            return

        action = "ON" if enable else "OFF"
        self._begin_busy(f"Switching {port.upper()} {action}...")
        try:
            await getattr(managed.ef_device, method)(enable)
            self._end_busy()
            self.log_block(f"[green]{entry.display_name}: {port.upper()} turned {action}[/]")
        except Exception as e:
            self._end_busy()
            self.log_block(f"[red]ERROR: {port.upper()} {action} failed: {e}[/]")

    @work(thread=False)
    async def _do_remove(self, identifier: str):
        entry = self.config.find_device(identifier)
        if not entry:
            self.log_block(f"[red]ERROR: '{identifier}' not found.[/]")
            return
        addr = entry.address.upper()
        name = entry.display_name

        self._begin_busy(f"Removing {name}...")
        managed = self.managed.pop(addr, None)
        if managed and managed.ef_device:
            try:
                ef = managed.ef_device
                ef.with_disabled_reconnect(True)
                conn = getattr(ef, '_conn', None)
                client = getattr(conn, '_client', None) if conn else None
                if client and getattr(client, 'is_connected', False):
                    for char_uuid in ("6e400003-b5a3-f393-e0a9-e50e24dcca9e",
                                      "00000003-0000-1000-8000-00805f9b34fb"):
                        try:
                            await client.stop_notify(char_uuid)
                        except Exception:
                            pass
                    try:
                        await client.disconnect()
                    except Exception:
                        pass
                await ef.disconnect()
            except Exception:
                pass
            await asyncio.sleep(5)

        self.config.remove_device(addr)
        save_config(self.config)
        block = self.device_blocks.pop(addr, None)
        if block:
            block.remove()
        # Show "no devices" placeholder if last device removed
        if not self.config.devices:
            h = "─" * IW
            empty = (
                f"┌{h}┐\n"
                f"│{' No devices'.ljust(IW)}│\n"
                f"│{' Use scan / add'.ljust(IW)}│\n"
                f"│{''.ljust(IW)}│\n"
                f"│{''.ljust(IW)}│\n"
                f"│{''.ljust(IW)}│\n"
                f"│{''.ljust(IW)}│\n"
                f"│{''.ljust(IW)}│\n"
                f"└{h}┘"
            )
            placeholder = Static(f"[dim]{empty}[/]", classes="device-block", id="no-devices")
            self.query_one("#dashboard").mount(placeholder)
        self._end_busy()
        self.log_block(f"[green]Removed {name}[/]")

    # --- Device setup ---

    def _setup_device(self, managed: ManagedDevice):
        ef_dev = managed.ef_device
        if not ef_dev:
            return

        original = ef_dev.update_callback

        def _refresh_now():
            addr = managed.entry.address.upper()
            if addr in self.device_blocks:
                self.device_blocks[addr].refresh_data(managed)
            if self._detail_view and self._detail_address == addr:
                self._detail_view.refresh_data(managed)

        def patched(propname):
            original(propname)
            summary = get_device_summary(ef_dev)
            if summary:
                for msg in managed.parsed_messages.values():
                    if hasattr(msg, 'cycles'):
                        summary["cycles"] = msg.cycles
                        break
                if summary["xboost"] is None:
                    for msg in managed.parsed_messages.values():
                        if hasattr(msg, 'cfg_ac_xboost'):
                            summary["xboost"] = msg.cfg_ac_xboost == 1
                            break
                managed.messages["_summary"] = summary
                managed.last_update_ts = time.time()
                # Immediate refresh (shows loader)
                _refresh_now()
                # Delayed refresh (clears loader after duration)
                self.set_timer(LOADER_DURATION + 0.1, _refresh_now)

        ef_dev.update_callback = patched

        def on_packet(packet):
            managed.last_packet_ts = time.time()
            if managed.entry:
                managed.entry.last_seen = time.time()

        ef_dev.on_packet_parsed(on_packet)

        if isinstance(ef_dev, RawDataProps):
            ef_dev.on_message_processed(
                lambda msg: managed.parsed_messages.__setitem__(type(msg).__name__, msg)
            )

        from .eflib.connection import ConnectionState

        def on_state(state):
            if state == ConnectionState.AUTHENTICATED:
                managed.connected = True
                managed.state = "online"
            elif state == ConnectionState.RECONNECTING:
                managed.connected = False
                managed.state = "reconnecting"
            elif state == ConnectionState.DISCONNECTED:
                managed.connected = False
                managed.state = "disconnected"
            elif state.is_error:
                managed.connected = False
                managed.state = "error"
            # UI refresh happens via _ui_tick timer

        ef_dev.on_connection_state_change(on_state)

        def on_disconnect(exc):
            managed.connected = False
            if managed.state != "reconnecting":
                managed.state = "disconnected"

        ef_dev.on_disconnect(on_disconnect)

    @work(thread=False)
    async def start_background(self):
        """Auto-connect to saved devices."""
        await asyncio.sleep(2)
        while True:
            for entry in self.config.devices:
                addr = entry.address.upper()
                managed = self.managed.get(addr)
                if managed and managed.connected:
                    continue
                try:
                    sd_found = None

                    def on_found(sd, a=addr):
                        nonlocal sd_found
                        if sd.address.upper() == a:
                            sd_found = sd

                    await scan_devices(duration=4.0, callback=on_found)
                    if not sd_found or not self.config.user_id:
                        continue

                    ef_dev = await connect_device(sd_found, self.config.user_id)
                    if not ef_dev:
                        continue

                    managed = ManagedDevice(
                        entry=entry, ef_device=ef_dev,
                        connected=True, state="online",
                    )
                    self.managed[addr] = managed
                    self._setup_device(managed)
                    entry.last_seen = time.time()
                    save_config(self.config)
                except Exception:
                    pass
            await asyncio.sleep(AUTO_CONNECT_INTERVAL)


def run_app_textual(config: Config):
    app = EfctlTextual(config)
    app.run()
