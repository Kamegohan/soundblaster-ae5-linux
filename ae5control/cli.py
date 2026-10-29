"""ae5ctl – Kommandozeile für Profile der AE-5 / command line for AE-5 profiles."""

from __future__ import annotations

import sys

from . import core
from .mixer import Mixer, MixerError
from .profiles import Store
from .i18n import tr

USAGE = tr("""ae5ctl – Profile der Sound BlasterX AE-5

  ae5ctl list               Profile anzeigen (* = aktiv)
  ae5ctl apply NAME         Profil einspielen und als aktiv merken
  ae5ctl apply-active       aktives Profil + Geräteeinstellungen erneut einspielen
  ae5ctl save NAME          aktuelle Klangeinstellungen als Profil speichern
  ae5ctl status             Karte und aktives Profil anzeigen""",
"""ae5ctl – profiles for the Sound BlasterX AE-5

  ae5ctl list               list profiles (* = active)
  ae5ctl apply NAME         apply a profile and remember it as active
  ae5ctl apply-active       re-apply the active profile + device settings
  ae5ctl save NAME          save the current sound settings as a profile
  ae5ctl status             show card and active profile""")


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help", "help"):
        print(USAGE)
        return 0
    store = Store()
    store.ensure_defaults()
    cmd, rest = args[0], args[1:]
    try:
        if cmd == "list":
            active = store.active_profile()
            for name in store.list_profiles():
                print(("* " if name == active else "  ") + name)
        elif cmd == "apply" and rest:
            skipped = core.apply_profile(" ".join(rest), Mixer(), store)
            name = " ".join(rest)
            print(tr(f"Profil „{name}“ eingespielt.", f"Profile “{name}” applied."))
            if skipped:
                print(tr("Übersprungen: ", "Skipped: ") + ", ".join(skipped), file=sys.stderr)
        elif cmd == "apply-active":
            name = core.apply_active(Mixer(), store)
            print(tr(f"Profil „{name}“ erneut eingespielt.", f"Profile “{name}” re-applied.") if name
                  else tr("Kein aktives Profil – nur Geräteeinstellungen.", "No active profile – device settings only."))
        elif cmd == "save" and rest:
            name = " ".join(rest)
            store.save_profile(name, core.current_profile_values(Mixer()))
            store.set_active_profile(name)
            print(tr(f"Profil „{name}“ gespeichert.", f"Profile “{name}” saved."))
        elif cmd == "status":
            mixer = Mixer()
            ctls = mixer.read_all()
            print(tr(f"Karte: gefunden ({len(ctls)} Regler)", f"Card: found ({len(ctls)} controls)"))
            print(tr("Aktives Profil: ", "Active profile: ") + (store.active_profile() or "–"))
        else:
            print(USAGE, file=sys.stderr)
            return 2
    except (MixerError, KeyError, ValueError) as exc:
        print(tr("Fehler: ", "Error: ") + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
