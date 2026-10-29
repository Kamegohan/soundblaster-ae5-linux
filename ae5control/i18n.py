"""Einfache Zweisprachigkeit: Deutsch bei deutscher Systemsprache, sonst Englisch.

Simple bilingual support: German if the system language is German, English otherwise.
Override with AE5_LANG=de or AE5_LANG=en.
"""

from __future__ import annotations

import os


def _detect() -> str:
    forced = os.environ.get("AE5_LANG", "").lower()
    if forced in ("de", "en"):
        return forced
    for var in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
        value = os.environ.get(var)
        if value:
            return "de" if value.lower().startswith("de") else "en"
    return "en"


LANG = _detect()
GERMAN = LANG == "de"


def tr(de: str, en: str) -> str:
    """Gibt den Text in der aktiven Sprache zurück / returns the text in the active language."""
    return de if GERMAN else en
