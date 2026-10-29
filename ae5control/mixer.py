"""Zugriff auf die ALSA-Regler der AE-5 über `amixer`.

Die Karte wird über ihren Namen ("Creative") gefunden, weil sich die
Kartennummer zwischen Neustarts ändert. Werte sind immer Listen von Rohwerten
(ein Eintrag pro Kanal), Auswahllisten als Index.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .i18n import tr

CARD_ID = "Creative"
ASOUND = Path("/proc/asound")


class MixerError(RuntimeError):
    """Die AE-5 ist nicht da oder ein Regler ließ sich nicht lesen/setzen."""


@dataclass
class Control:
    numid: int
    name: str
    type: str  # BOOLEAN, INTEGER, ENUMERATED, ...
    writable: bool
    count: int = 1
    minimum: int = 0
    maximum: int = 1
    items: list[str] = field(default_factory=list)
    values: list[int] = field(default_factory=list)


_HEAD = re.compile(r"^numid=(\d+),iface=(\w+),name='(.*)'(?:,index=\d+)?$")
_TYPE = re.compile(r"^\s+; type=(\w+),access=([\w-]+),values=(\d+)(.*)$")
_ITEM = re.compile(r"^\s+; Item #(\d+) '(.*)'$")
_VALUES = re.compile(r"^\s+: values=(.*)$")


def _to_int(raw: str) -> int:
    raw = raw.strip()
    if raw == "on":
        return 1
    if raw == "off":
        return 0
    return int(raw)


def parse_contents(text: str) -> dict[str, Control]:
    """Wertet die Ausgabe von `amixer -c N contents` aus (nur MIXER-Regler)."""
    controls: dict[str, Control] = {}
    current: Control | None = None
    for line in text.splitlines():
        head = _HEAD.match(line)
        if head:
            numid, iface, name = head.groups()
            current = Control(int(numid), name, "", False) if iface == "MIXER" else None
            if current:
                controls.setdefault(name, current)
            continue
        if current is None:
            continue
        typ = _TYPE.match(line)
        if typ:
            current.type = typ.group(1)
            current.writable = "w" in typ.group(2)
            current.count = int(typ.group(3))
            extra = dict(re.findall(r"(\w+)=(-?\d+)", typ.group(4)))
            if "min" in extra:
                current.minimum = int(extra["min"])
            if "max" in extra:
                current.maximum = int(extra["max"])
            continue
        item = _ITEM.match(line)
        if item:
            current.items.append(item.group(2))
            continue
        vals = _VALUES.match(line)
        if vals and current.type in ("BOOLEAN", "INTEGER", "ENUMERATED"):
            current.values = [_to_int(v) for v in vals.group(1).split(",")]
            if current.type == "ENUMERATED":
                current.minimum, current.maximum = 0, max(len(current.items) - 1, 0)
    return controls


def find_card(asound: Path = ASOUND) -> int:
    for id_file in sorted(asound.glob("card[0-9]*/id")):
        try:
            if id_file.read_text().strip() == CARD_ID:
                return int(id_file.parent.name[4:])
        except OSError:
            continue
    raise MixerError(tr("AE-5 nicht gefunden – Karte gerade nicht verfügbar.", "AE-5 not found – card currently unavailable."))


def _quote(name: str) -> str:
    return "'" + name.replace("'", "\\'") + "'"


class Mixer:
    """Liest und setzt Regler der AE-5."""

    def __init__(self, runner=subprocess.run):
        self._run = runner

    def _amixer(self, args: list[str], stdin: str | None = None) -> str:
        card = find_card()
        result = self._run(
            ["amixer", "-c", str(card), *args],
            input=stdin, capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            raise MixerError(result.stderr.strip() or tr("amixer fehlgeschlagen", "amixer failed"))
        return result.stdout

    def read_all(self) -> dict[str, Control]:
        return parse_contents(self._amixer(["contents"]))

    def write(self, values: dict[str, list[int]], known: dict[str, Control] | None = None) -> list[str]:
        """Setzt mehrere Regler in einem amixer-Aufruf.

        Unbekannte oder schreibgeschützte Regler werden übersprungen;
        zurückgegeben wird die Liste der übersprungenen Namen.
        """
        known = known if known is not None else self.read_all()
        lines, skipped = [], []
        for name, vals in values.items():
            ctl = known.get(name)
            if ctl is None or not ctl.writable or not vals:
                skipped.append(name)
                continue
            clamped = [min(max(int(v), ctl.minimum), ctl.maximum) for v in vals]
            lines.append(f"cset name={_quote(name)} {','.join(map(str, clamped))}")
        if lines:
            self._amixer(["-q", "-s"], stdin="\n".join(lines) + "\n")
        return skipped
