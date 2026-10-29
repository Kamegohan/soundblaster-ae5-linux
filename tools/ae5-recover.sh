#!/usr/bin/env bash
# ae5-recover – startet nur die Sound BlasterX AE-5 neu, ohne den PC neu zu starten.
#
# Stufen (es geht erst weiter, wenn die vorige nicht geholfen hat):
#   1  AE-5 vom Treiber snd_hda_intel trennen und wieder verbinden
#   2  AE-5 vom PCI-Bus entfernen und neu suchen
#   3  Soundchip neu initialisieren (Codec-reconfig) – nur als letzter Ausweg,
#      weil dafür PipeWire angehalten werden muss: Programme wie Spotify oder
#      Spiele verlieren dabei ihre Verbindung und müssen neu gestartet werden.
# Stufe 1 und 2 laufen bei laufendem PipeWire: Für Programme sieht das aus wie
# kurz aus- und wieder eingesteckt, ihr Ton wird danach wieder an die AE-5 gehängt.
# Nach jeder Stufe wird kurz Stille auf die AE-5 gespielt und geprüft, ob die
# Karte die Daten wirklich annimmt. Die Mixer-Einstellungen (Verstärkung, EQ,
# Effekte) werden vorher gesichert und danach wiederhergestellt.
#
# Root-Rechte: über den installierten Helfer + polkit ohne Passwort
# (tools/install-recovery.sh), sonst über sudo.
# Damit die Karte nach Stufe 1/2 als AE-5 erkannt wird, muss die Treiber-Vorgabe
# installiert sein (tools/install-model-fix.sh).
#
# Nutzung:  ae5-recover.sh            alle Stufen der Reihe nach
#           ae5-recover.sh --auto     wie oben, aber nie nach einem Passwort fragen (Wächter)
#           ae5-recover.sh --hang     bei erkanntem Hänger: Stufe 1 überspringen und direkt mit
#                                     Stufe 2 beginnen (Stufe 1 hat bei echten Hängern nie gereicht)
#           ae5-recover.sh --check    nur prüfen, ob die Karte Daten annimmt

set -u

# Sprache: Deutsch bei deutscher Systemsprache, sonst Englisch (AE5_LANG=de|en erzwingt)
case "${AE5_LANG:-${LC_ALL:-${LC_MESSAGES:-${LANG:-}}}}" in de*) AE5_DE=1 ;; *) AE5_DE=0 ;; esac
t() { if [ "$AE5_DE" = 1 ]; then printf '%s' "$1"; else printf '%s' "$2"; fi; }

SELF_DIR=$(cd "$(dirname "$(readlink -f "$0")")" && pwd)
STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/ae5-control"
LOG="$STATE_DIR/diag/current.log"
MIXER_STATE="$STATE_DIR/mixer.state"
# Root-Helfer: aus dem Paket (/usr/lib) oder von install-recovery.sh (/usr/local)
HELPER=""
for candidate in /usr/lib/ae5-control/ae5-reset-helper /usr/local/libexec/ae5-control/ae5-reset-helper; do
    [ -x "$candidate" ] && { HELPER=$candidate; break; }
done
PW_UNITS_STOP="pipewire-pulse.socket pipewire.socket pipewire-pulse pipewire wireplumber"
PW_UNITS_START="pipewire.socket pipewire-pulse.socket pipewire wireplumber pipewire-pulse"
AUTO=0

say() {
    echo "$*"
    [ -e "$LOG" ] && printf '%s RECOVER %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >>"$LOG"
}

find_pci_addr() {
    local d
    for d in /sys/bus/pci/devices/*; do
        if [ "$(cat "$d/vendor" 2>/dev/null)" = "0x1102" ] && [ "$(cat "$d/device" 2>/dev/null)" = "0x0012" ]; then
            basename "$d"
            return 0
        fi
    done
    return 1
}

find_card() {
    local f
    for f in /proc/asound/card[0-9]*/id; do
        [ "$(cat "$f" 2>/dev/null)" = "Creative" ] && { basename "$(dirname "$f")"; return 0; }
    done
    return 1
}

# sysfs-Pfad des CA0132-Codecs (z. B. /sys/class/sound/hwC0D1)
find_codec_sysfs() {
    local card d
    card=$(find_card) || return 1
    for d in /sys/class/sound/hwC"${card#card}"D*; do
        [ "$(cat "$d/vendor_id" 2>/dev/null)" = "0x11020011" ] && { echo "$d"; return 0; }
    done
    return 1
}

chip_name() {
    local codec
    codec=$(find_codec_sysfs) && cat "$codec/chip_name" 2>/dev/null
}

sink_name() {
    local addr
    addr=$(find_pci_addr) || return 1
    # PipeWire-Name: alsa_output.pci-<adresse>.<profil> (in der Adresse wird nur ":" zu "_")
    pactl list sinks short 2>/dev/null | awk -v a="pci-${addr//:/_}." 'index($2, a) {print $2; exit}'
}

wait_for_card() {
    local i card
    for ((i = 0; i < $1; i++)); do
        card=$(find_card) && [ -e /proc/asound/"$card"/pcm0p ] && return 0
        sleep 1
    done
    return 1
}

wait_for_sink() {
    local i
    for ((i = 0; i < $1; i++)); do
        [ -n "$(sink_name)" ] && return 0
        sleep 1
    done
    return 1
}

# Spielt kurz Stille auf die AE-5 und prüft, ob die Hardware-Position weiterläuft.
# 0 = Karte nimmt Daten an, 1 = hängt
check_card() {
    local card sink st p1 p2 pid rc=1
    card=$(find_card) || return 1
    sink=$(sink_name)
    [ -z "$sink" ] && return 1
    st=/proc/asound/"$card"/pcm0p/sub0/status
    pacat --playback --device="$sink" --format=s16le --rate=48000 --channels=2 \
        --property=media.role=test </dev/zero >/dev/null 2>&1 &
    pid=$!
    sleep 1.5
    p1=$(awk '/^hw_ptr/{print $3}' "$st" 2>/dev/null)
    sleep 1
    p2=$(awk '/^hw_ptr/{print $3}' "$st" 2>/dev/null)
    kill "$pid" 2>/dev/null
    wait "$pid" 2>/dev/null
    [ -n "$p1" ] && [ -n "$p2" ] && [ "$p1" != "$p2" ] && rc=0
    return $rc
}

# Führt eine Aktion des Root-Helfers aus (reconfig|rebind|rescan).
root_do() {
    if [ -n "$HELPER" ]; then
        pkexec "$HELPER" "$1"
    elif [ $AUTO -eq 1 ]; then
        say "$(t "  Helfer nicht installiert – automatischer Neustart nicht möglich (tools/install-recovery.sh)." "  Helper not installed – automatic restart not possible (tools/install-recovery.sh).")"
        return 1
    elif [ -f "$SELF_DIR/../system/ae5-reset-helper" ]; then
        sudo bash "$SELF_DIR/../system/ae5-reset-helper" "$1"
    else
        say "$(t "  Root-Helfer fehlt." "  Root helper missing.")"
        return 1
    fi
}

SAVED_VOLUME=""
SAVED_MUTE=""

mixer_save() {
    mkdir -p "$STATE_DIR"
    alsactl --file "$MIXER_STATE" store Creative 2>/dev/null
    # PipeWire-Lautstärke merken – nach einem PipeWire-Neustart lädt WirePlumber
    # sonst evtl. einen älteren (lauteren) gespeicherten Wert
    local sink
    sink=$(sink_name)
    if [ -n "$sink" ]; then
        SAVED_VOLUME=$(pactl get-sink-volume "$sink" 2>/dev/null | grep -o '[0-9]*%' | head -1)
        SAVED_MUTE=$(pactl get-sink-mute "$sink" 2>/dev/null | awk '{print $2}')
    fi
}

mixer_restore() {
    # Steuerelemente, die es nach dem Neustart nicht gibt, sind kein Fehler
    [ -s "$MIXER_STATE" ] && { alsactl --file "$MIXER_STATE" restore Creative >/dev/null 2>&1 || true; }
    local sink
    sink=$(sink_name)
    [ -z "$sink" ] && return 0
    if [ -n "$SAVED_VOLUME" ]; then
        # WirePlumber setzt nach dem Start verzögert einen eigenen Wert –
        # deshalb einige Sekunden lang aufpassen und ggf. erneut zurücksetzen.
        local i cur
        for ((i = 0; i < 16; i++)); do
            cur=$(pactl get-sink-volume "$sink" 2>/dev/null | grep -o '[0-9]*%' | head -1)
            [ "$cur" != "$SAVED_VOLUME" ] && pactl set-sink-volume "$sink" "$SAVED_VOLUME"
            sleep 0.5
        done
    fi
    case "$SAVED_MUTE" in
        yes|ja) pactl set-sink-mute "$sink" 1 ;;
        no|nein) pactl set-sink-mute "$sink" 0 ;;
    esac
}

# Kopfhörerverstärker/Ausgang neu ansteuern: Output Select kurz umschalten und zurück.
# Nach einem Neustart der Karte kommt sonst evtl. kein Ton, obwohl sie Daten annimmt.
amp_reinit() {
    local card cur other
    card=$(find_card) || return 0
    cur=$(amixer -c "${card#card}" sget 'Output Select' 2>/dev/null | awk -F"'" '/Item0/{print $2}')
    [ -z "$cur" ] && return 0
    if [ "$cur" = "Headphone" ]; then other=Speakers; else other=Headphone; fi
    amixer -c "${card#card}" sset 'Output Select' "$other" >/dev/null 2>&1
    sleep 0.3
    amixer -c "${card#card}" sset 'Output Select' "$cur" >/dev/null 2>&1
}

# Ergebnis einer Stufe prüfen. 0 = fertig, 1 = hängt weiter, 2 = falsches Modell
verify() {
    wait_for_sink 15 || { say "$(t "  PipeWire-Ausgabe der AE-5 fehlt." "  PipeWire output of the AE-5 missing.")"; return 1; }
    mixer_restore
    sleep 1
    if ! check_card; then
        say "$(t "  Karte nimmt weiterhin keine Daten an." "  Card still does not accept data.")"
        return 1
    fi
    local chip
    chip=$(chip_name)
    if [[ "$chip" != *AE-5* ]]; then
        say "$(t "  Karte läuft, wird aber als \"$chip\" erkannt – kein Ton an den AE-5-Ausgängen." "  Card runs but is detected as \"$chip\" – no sound on the AE-5 outputs.")"
        say "$(t "  Abhilfe: Treiber-Vorgabe installieren (Paket oder tools/install-model-fix.sh), danach Neustart." "  Fix: install the driver model override (package or tools/install-model-fix.sh), then reboot.")"
        return 2
    fi
    # Aktives Klangprofil der App erneut einspielen (falls die App eingerichtet ist)
    "$SELF_DIR/../bin/ae5ctl" apply-active >/dev/null 2>&1 || true
    amp_reinit
    say "$(t "Fertig – AE-5 läuft wieder ($chip)." "Done – AE-5 is running again ($chip).")"
    return 0
}

stage3_reconfig() {
    find_codec_sysfs >/dev/null || return 1
    say "$(t "Stufe 3: Soundchip neu initialisieren (PipeWire wird neu gestartet – Programme ggf. neu starten) ..." "Stage 3: re-initializing the sound chip (PipeWire restarts – apps may need a restart) ...")"
    # reconfig geht nur, wenn niemand die Karte geöffnet hat
    systemctl --user stop $PW_UNITS_STOP
    root_do reconfig
    local rc=$?
    systemctl --user start $PW_UNITS_START
    return $rc
}

stage1_rebind() {
    say "$(t "Stufe 1: AE-5 vom Treiber trennen und neu verbinden ..." "Stage 1: unbinding and rebinding the AE-5 driver ...")"
    root_do rebind || return 1
    wait_for_card 20
}

stage2_rescan() {
    say "$(t "Stufe 2: AE-5 vom PCI-Bus entfernen und neu suchen ..." "Stage 2: removing the AE-5 from the PCI bus and rescanning ...")"
    root_do rescan || return 1
    wait_for_card 20
}

STAGES="stage1_rebind stage2_rescan stage3_reconfig"
for arg in "$@"; do
    case "$arg" in
        --check)
            find_pci_addr >/dev/null || { echo "AE-5 nicht gefunden."; exit 1; }
            if check_card; then echo "$(t "OK – AE-5 nimmt Daten an" "OK – AE-5 accepts data") ($(chip_name))."; exit 0; fi
            echo "$(t "HÄNGT – AE-5 nimmt keine Daten an" "HUNG – AE-5 does not accept data") ($(chip_name))."
            exit 1
            ;;
        --auto) AUTO=1 ;;
        --hang) STAGES="stage2_rescan stage3_reconfig" ;;
    esac
done

ADDR=$(find_pci_addr) || { say "$(t "FEHLER: AE-5 nicht auf dem PCI-Bus gefunden." "ERROR: AE-5 not found on the PCI bus.")"; exit 1; }
say "$(t "Starte AE-5 neu" "Restarting AE-5") ($ADDR, $(t "erkannt als" "detected as") \"$(chip_name)\") ..."

# Ohne Helfer: Passwort vorab abfragen, damit PipeWire nicht während der Abfrage aus ist
if [ -z "$HELPER" ] && [ $AUTO -eq 0 ]; then
    sudo -v || { say "$(t "Abgebrochen (kein sudo)." "Aborted (no sudo).")"; exit 1; }
fi

mixer_save

for stage in $STAGES; do
    if $stage; then
        verify
        case $? in
            0) exit 0 ;;
            2) exit 2 ;;
        esac
    fi
    [ -z "$HELPER" ] && [ $AUTO -eq 0 ] && sudo -v
done

say "$(t "FEHLER: Karte kommt nicht zurück. Hier hilft leider nur ein Neustart." "ERROR: card does not come back. Only a reboot helps now.")"
exit 3
