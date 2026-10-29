# Sound BlasterX AE-5 unter Linux – stabiler Ton + Einstellungs-App

[![Tests](https://github.com/Kamegohan/soundblaster-ae5-linux/actions/workflows/tests.yml/badge.svg)](https://github.com/Kamegohan/soundblaster-ae5-linux/actions/workflows/tests.yml) [![License: GPL v2+](https://img.shields.io/badge/license-GPL--2.0--or--later-blue.svg)](LICENSE)

**[English version → README.md](README.md)**

Die Creative Sound BlasterX **AE-5 / AE-5 Plus** ist eine tolle Karte, hat unter Linux aber zwei Probleme:

1. **Der Ton fällt aus und kommt nur nach einem Neustart zurück.** Typischer Auslöser: Headset aufnehmen, Kabel bewegt sich oder eine kleine statische Entladung – der DSP der Karte hängt. Andere Geräte (USB-Mikrofon, HDMI) laufen weiter, die AE-5 bleibt stumm.
2. **Es gibt keine Einstellungs-App** wie Creatives Windows-Software, obwohl der Linux-Treiber fast alle Regler anbietet (Effekte, Equalizer, Kopfhörer-Verstärkung, DAC-Filter, Mikrofon-Effekte).

Dieses Projekt löst beides – ohne Kernel-Patch:

- Ein **Wächter** erkennt den Hänger nach ~6 Sekunden und startet *nur die AE-5* neu (kein PC-Neustart, kein PipeWire-Neustart). Nach ~20 Sekunden ist der Ton zurück; laufende Programme und Spiele bleiben verbunden (manche wie Spotify pausieren – einmal Play drücken).
- Eine **Einstellungs-App** (Qt) mit Profilen, Effekten, 10-Band-Equalizer, Mikrofon-Effekten und Tray-Symbol. Deutsch und Englisch.
- Korrekturen für mehrere Fallen, in denen die AE-5 unter PipeWire stumm bleibt (siehe [Was gelöst wird](#was-gelöst-wird)).

![Equalizer](docs/screenshot-equalizer.png)

## Unterstützte Hardware

- Creative Sound BlasterX **AE-5** und **AE-5 Plus** (PCI `1102:0012`, Subsystem `1102:0191`, CA0132-Codec, Treiber `snd_hda_codec_ca0132`).
- Getestet mit einer AE-5 Plus unter CachyOS (Arch), Kernel 7.2/7.3, PipeWire 1.6 + WirePlumber, KDE Plasma 6 (Wayland).
- Andere CA0132-Karten (Sound Blaster Z, ZxR, AE-7, Recon3D) werden (noch) **nicht** unterstützt. Pull Requests willkommen.

Karte prüfen:

```bash
lspci -nn | grep -i 1102:0012
```

## Was gelöst wird

| Problem | Ursache | Lösung |
|---|---|---|
| Ton weg nach Aufnehmen des Headsets, nur Neustart hilft | Statische Entladung / Kabelbewegung → DMA der Karte hängt (`pcm RUNNING`, `hw_ptr` steht) | Wächter startet nur die AE-5 neu (PCI entfernen + neu suchen), PipeWire läuft weiter |
| Nach so einem Reset stumm, Karte heißt „Sound Blaster Z“ | Nach hartem Reset meldet die Karte eine falsche PCI-Kennung (`1102:0010`) | Treiber-Vorgabe: Modell `ae5`, erkannt über die Codec-Kennung (Patch-Firmware + modprobe-Option) |
| Kopfhörer stumm / „nicht angeschlossen“ | PipeWires Kopfhörer-Vorlage schaltet `Front` stumm – darüber speist die AE-5 aber ihren Kopfhörerverstärker | Eigenes PipeWire-(ACP-)Profil nur für die AE-5, per udev zugewiesen |
| Nach einer Pause stumm, obwohl die Karte Daten annimmt | Der DSP schaltet den Ausgang beim Neustart eines Streams stumm; PipeWires Ruhezustand verschärft das | Kein Ruhezustand für die AE-5 + Verstärker-Wächter, der beim Tonstart den Kopfhörerverstärker neu ansteuert |

## Installation

### Arch Linux / CachyOS / Manjaro (Paket)

```bash
git clone https://github.com/Kamegohan/soundblaster-ae5-linux.git
cd soundblaster-ae5-linux/packaging
makepkg -si
systemctl --user daemon-reload
systemctl --user enable --now ae5-watchdog.service ae5-amp-guard.service
systemctl --user restart wireplumber pipewire pipewire-pulse
```

Danach einmal neu starten, damit die Treiber-Vorgabe (Modell `ae5`) aktiv ist. Entfernen: `sudo pacman -R ae5-control`.

### Andere Distributionen (von Hand)

Voraussetzungen: Python ≥ 3.10, PySide6, `alsa-utils` (`amixer`, `alsactl`), `pactl` (PulseAudio-Utils / pipewire-pulse), PipeWire + WirePlumber, polkit, systemd, `notify-send` (libnotify).

```bash
git clone https://github.com/Kamegohan/soundblaster-ae5-linux.git
cd soundblaster-ae5-linux
tools/install-model-fix.sh          # Treiber-Vorgabe (wirkt ab dem nächsten Start)
tools/install-pipewire-profile.sh   # AE-5-PipeWire-Profil + kein Ruhezustand
tools/install-recovery.sh           # Root-Helfer, polkit-Regel, Wächter, Verstärker-Wächter
tools/install-app.sh                # Menüeintrag + Autostart im Tray (ohne Root)
```

Jedes Skript kennt `--remove`. Die Handinstallation läuft aus dem geklonten Ordner – danach nicht mehr verschieben.
Umstieg von der Handinstallation auf das Paket: `tools/migrate-to-package.sh`.

## Benutzung

- **App:** „AE-5 Control“ im Startmenü oder `ae5-control` (`--tray` startet nur im Tray).
  - **Profile** enthalten Effekte, Equalizer und Mikrofon-Effekte – nie die Lautstärke, ein Wechsel kann also nicht plötzlich laut werden. Standard: Neutral, Gaming, Musik, Film. „Zurücksetzen“ verwirft Änderungen oder stellt die Standardprofile wieder her.
  - **Ausgabe:** Kopfhörer/Lautsprecher, Kopfhörer-Verstärkung (fragt vor dem Erhöhen), DAC-Filter, Lautsprecher-Kanäle.
  - Jedes Bedienelement erklärt sich per Tooltip.
- **Tray:** Linksklick öffnet/schließt das Fenster, Rechtsklick wechselt Profile oder startet die Karte neu.
- **Kommandozeile:**
  - `ae5ctl list | apply NAME | apply-active | save NAME | status`
  - `ae5-recover` startet die Karte von Hand neu (`--check` prüft nur)
  - `ae5-diag start | mark | status | stop` schreibt ein Diagnose-Protokoll
- **Sprache:** Deutsch bei deutscher Systemsprache, sonst Englisch. Erzwingen mit `AE5_LANG=de` oder `AE5_LANG=en`.

## Sicherheit

Der Kopfhörerverstärker der AE-5 ist kräftig. Die App fragt vor dem Erhöhen der Verstärkung und bietet an, die Lautstärke vorher zu senken. Beim Testen Kopfhörer absetzen oder leise anfangen.

## Fehlersuche und Fehlerberichte

1. Diagnose-Protokoll starten: `ae5-diag start`
2. Wenn der Fehler auftritt: `ae5-diag mark "was passiert ist"`
3. Ein [Issue](https://github.com/Kamegohan/soundblaster-ae5-linux/issues) öffnen und das Protokoll aus `~/.local/state/ae5-control/diag/current.log` anhängen, dazu die Ausgabe von `lspci -nnk | grep -A3 -i creative` und `cat /proc/asound/cards`.

## Wie es funktioniert

Eine Übersicht aller Bestandteile steht in der [englischen README](README.md#how-it-works).
Einstellungen liegen in `~/.config/ae5-control/` (`profiles/*.json`, `device.json`, `state.json`).
Tests: `python3 -m unittest discover -s tests -t .`

## Einschränkungen

- Die RGB-Beleuchtung der AE-5 steuert der Linux-Treiber nicht.
- Manche Programme pausieren, wenn die Karte beim Neustart kurz verschwindet – einmal Play drücken.
- Die Unterschiede der DAC-Filter sind sehr klein (oberhalb von ~18 kHz).

## Danksagung und Lizenz

- Die Werte der Equalizer-Voreinstellungen und das DSP-Wissen stammen aus dem Linux-Kernel-Treiber `sound/hda/codecs/ca0132.c` (Creative Technology Ltd. und Mitwirkende, GPL-2.0-or-later).
- Dieses Projekt steht unter der **GNU General Public License v2.0 oder später** – siehe [LICENSE](LICENSE).
- Nicht mit Creative Technology verbunden. „Sound BlasterX“ ist eine Marke von Creative Technology Ltd.
