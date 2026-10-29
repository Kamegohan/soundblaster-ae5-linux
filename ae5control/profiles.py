"""Klangprofile und Geräteeinstellungen als JSON in ~/.config/ae5-control/."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from .catalog import DEVICE_CONTROLS, EQ_CENTER, PROFILE_CONTROLS
from .i18n import tr
from .mixer import Control

def _profile(**overrides) -> dict[str, list[int]]:
    """Vollständiges Klangprofil: neutrale Grundwerte + Abweichungen.

    Mikrofon-Effekte gehören absichtlich nicht dazu – ein Wechsel des
    Klangprofils soll das Mikrofon nicht verändern.
    """
    base = {
        "Enable OutFX Playback Switch": [1],
        "FX: Surround Playback Switch": [0], "FX: Surround Playback Volume": [50],
        "FX: Crystalizer Playback Switch": [0], "FX: Crystalizer Playback Volume": [50],
        "FX: X-Bass Playback Switch": [0], "FX: X-Bass Playback Volume": [50],
        "FX: X-Bass Crossover Playback Volume": [8],
        "FX: Smart Volume Playback Switch": [0], "FX: Smart Volume Playback Volume": [50],
        "FX: Smart Volume Setting": [0],
        "FX: Dialog Plus Playback Switch": [0], "FX: Dialog Plus Playback Volume": [50],
        "FX: Equalizer Playback Switch": [0], "FX: Equalizer Preset Switch": [0],
        **{f"EQ Band{i} Playback Volume": [EQ_CENTER] for i in range(10)},
    }
    for key, value in overrides.items():
        base[_KEYS[key]] = [value]
    return base


_KEYS = {
    "outfx": "Enable OutFX Playback Switch",
    "surround": "FX: Surround Playback Switch", "surround_lvl": "FX: Surround Playback Volume",
    "crystal": "FX: Crystalizer Playback Switch", "crystal_lvl": "FX: Crystalizer Playback Volume",
    "bass": "FX: X-Bass Playback Switch", "bass_lvl": "FX: X-Bass Playback Volume",
    "smart": "FX: Smart Volume Playback Switch", "smart_lvl": "FX: Smart Volume Playback Volume",
    "dialog": "FX: Dialog Plus Playback Switch", "dialog_lvl": "FX: Dialog Plus Playback Volume",
}

# Standardprofile: (deutscher Name, englischer Name, Einstellungen)
_BUILTINS = [
    ("Neutral", "Neutral", _profile(outfx=0)),
    ("Gaming", "Gaming", _profile(surround=1, surround_lvl=60, crystal=1, crystal_lvl=40, dialog=1, dialog_lvl=40)),
    ("Musik", "Music", _profile(crystal=1, crystal_lvl=50, bass=1, bass_lvl=35)),
    ("Film", "Movie", _profile(surround=1, surround_lvl=70, bass=1, bass_lvl=40, smart=1, smart_lvl=50,
                               dialog=1, dialog_lvl=60)),
]

# Unter den Namen der aktiven Sprache angelegt; beide Namensformen gelten als Standardprofil
DEFAULT_PROFILES = {tr(de, en): controls for de, en, controls in _BUILTINS}
_BUILTIN_BY_NAME = {name: controls for de, en, controls in _BUILTINS for name in (de, en)}


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "ae5-control"


def _safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^\w\- ]", "_", name).strip()
    if not cleaned:
        raise ValueError(tr("Profilname ist leer.", "Profile name is empty."))
    return cleaned


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    tmp.replace(path)


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def snapshot(controls: dict[str, Control], names: list[str]) -> dict[str, list[int]]:
    return {n: list(controls[n].values) for n in names if n in controls and controls[n].values}


class Store:
    def __init__(self, root: Path | None = None):
        self.root = root or config_dir()
        self.profile_dir = self.root / "profiles"

    # --- Profile -------------------------------------------------------------
    def ensure_defaults(self) -> None:
        if not (self.profile_dir.exists() and any(self.profile_dir.glob("*.json"))):
            self.restore_all_builtins()
            return
        # Ältere Versionen legten unvollständige Standardprofile an (ohne Equalizer) – auffrischen
        for name in DEFAULT_PROFILES:
            path = self.profile_dir / f"{_safe_filename(name)}.json"
            if path.exists() and "EQ Band0 Playback Volume" not in _read_json(path).get("controls", {}):
                self.restore_builtin(name)

    def list_profiles(self) -> list[str]:
        names = []
        for f in sorted(self.profile_dir.glob("*.json")):
            names.append(_read_json(f).get("name") or f.stem)
        return names

    def load_profile(self, name: str) -> dict[str, list[int]]:
        data = _read_json(self.profile_dir / f"{_safe_filename(name)}.json")
        if not data:
            raise KeyError(tr(f"Profil „{name}“ nicht gefunden.", f"Profile “{name}” not found."))
        return {k: v for k, v in data.get("controls", {}).items() if k in PROFILE_CONTROLS}

    def save_profile(self, name: str, controls: dict[str, list[int]]) -> None:
        clean = {k: v for k, v in controls.items() if k in PROFILE_CONTROLS}
        _write_json(self.profile_dir / f"{_safe_filename(name)}.json", {"name": name, "controls": clean})

    @staticmethod
    def is_builtin(name: str) -> bool:
        return name in _BUILTIN_BY_NAME

    def restore_builtin(self, name: str) -> None:
        """Setzt ein Standardprofil auf Werkseinstellung zurück (legt es ggf. neu an)."""
        self.save_profile(name, _BUILTIN_BY_NAME[name])

    def restore_all_builtins(self) -> None:
        for name in DEFAULT_PROFILES:
            self.restore_builtin(name)

    def delete_profile(self, name: str) -> None:
        (self.profile_dir / f"{_safe_filename(name)}.json").unlink(missing_ok=True)
        if self.active_profile() == name:
            self.set_active_profile(None)

    # --- Zustand -------------------------------------------------------------
    def active_profile(self) -> str | None:
        return _read_json(self.root / "state.json").get("active_profile")

    def set_active_profile(self, name: str | None) -> None:
        state = _read_json(self.root / "state.json")
        state["active_profile"] = name
        _write_json(self.root / "state.json", state)

    def load_device(self) -> dict[str, list[int]]:
        data = _read_json(self.root / "device.json").get("controls", {})
        return {k: v for k, v in data.items() if k in DEVICE_CONTROLS}

    def save_device(self, controls: dict[str, list[int]]) -> None:
        clean = {k: v for k, v in controls.items() if k in DEVICE_CONTROLS}
        _write_json(self.root / "device.json", {"controls": clean})
