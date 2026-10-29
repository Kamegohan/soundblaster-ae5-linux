"""Kopfhörer/Lautsprecher über den PipeWire-Port der AE-5 umschalten.

Die App setzt den Port statt "Output Select" direkt, damit PipeWire und die
App sich nicht gegenseitig überschreiben (das AE-5-Profil schaltet Output
Select passend zum Port).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

PORT_HEADPHONES = "ae5-output-headphones"
PORT_SPEAKERS = "ae5-output-speakers"
PCI_DEVICES = Path("/sys/bus/pci/devices")


def pci_address(root: Path = PCI_DEVICES) -> str | None:
    """PCI-Adresse der AE-5 (Creative 1102:0012), z. B. "0000:03:00.0"."""
    for dev in sorted(root.glob("*")):
        try:
            if (dev / "vendor").read_text().strip() == "0x1102" and (dev / "device").read_text().strip() == "0x0012":
                return dev.name
        except OSError:
            continue
    return None


def sink_marker() -> str | None:
    addr = pci_address()
    return f"pci-{addr.replace(':', '_')}." if addr else None


def _pactl(*args: str) -> str:
    result = subprocess.run(["pactl", *args], capture_output=True, text=True, timeout=5)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "pactl failed")
    return result.stdout


def sink_name() -> str | None:
    marker = sink_marker()
    if not marker:
        return None
    try:
        for line in _pactl("list", "sinks", "short").splitlines():
            parts = line.split("\t")
            if len(parts) > 1 and marker in parts[1]:
                return parts[1]
    except (RuntimeError, OSError, subprocess.TimeoutExpired):
        pass
    return None


def active_port(sink: str) -> str | None:
    try:
        out = _pactl("list", "sinks")
    except (RuntimeError, OSError, subprocess.TimeoutExpired):
        return None
    in_sink = False
    for line in out.splitlines():
        stripped = line.strip()
        if stripped.startswith(("Name:", "Name :")):
            in_sink = stripped.split(":", 1)[1].strip() == sink
        elif in_sink and stripped.startswith(("Active Port:", "Aktiver Port:")):
            return stripped.split(":", 1)[1].strip()
    return None


def set_port(sink: str, port: str) -> None:
    _pactl("set-sink-port", sink, port)


def volume_percent(sink: str) -> int | None:
    try:
        out = _pactl("get-sink-volume", sink)
    except (RuntimeError, OSError, subprocess.TimeoutExpired):
        return None
    for token in out.split():
        if token.endswith("%"):
            return int(token[:-1])
    return None


def set_volume_percent(sink: str, percent: int) -> None:
    _pactl("set-sink-volume", sink, f"{max(0, min(percent, 150))}%")
