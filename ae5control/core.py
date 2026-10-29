"""Profile anwenden und den aktuellen Zustand erfassen."""

from __future__ import annotations

from .catalog import DEVICE_CONTROLS, PROFILE_CONTROLS
from .mixer import Mixer
from .profiles import Store, snapshot


def apply_profile(name: str, mixer: Mixer | None = None, store: Store | None = None) -> list[str]:
    """Spielt Geräteeinstellungen + Klangprofil ein und merkt es als aktiv."""
    mixer = mixer or Mixer()
    store = store or Store()
    values = dict(store.load_device())
    values.update(store.load_profile(name))
    skipped = mixer.write(values)
    store.set_active_profile(name)
    return skipped


def apply_active(mixer: Mixer | None = None, store: Store | None = None) -> str | None:
    """Aktives Profil (falls vorhanden) und Geräteeinstellungen erneut einspielen."""
    mixer = mixer or Mixer()
    store = store or Store()
    name = store.active_profile()
    if name and name in store.list_profiles():
        apply_profile(name, mixer, store)
        return name
    device = store.load_device()
    if device:
        mixer.write(device)
    return None


def current_profile_values(mixer: Mixer) -> dict[str, list[int]]:
    return snapshot(mixer.read_all(), PROFILE_CONTROLS)


def current_device_values(mixer: Mixer) -> dict[str, list[int]]:
    return snapshot(mixer.read_all(), DEVICE_CONTROLS)
