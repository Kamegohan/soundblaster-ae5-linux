#!/usr/bin/env bash
# ae5-diag – Diagnose-Protokoll für die Sound BlasterX AE-5 (Plus)
#
# Läuft im Hintergrund und schreibt mit, was mit der Karte passiert:
#   - Kernel-Meldungen zur Karte, Standby/Aufwachen, Bildschirmsperre
#   - PipeWire/WirePlumber-Meldungen
#   - alle 2 s den Zustand von Karte, PCM-Stream und PipeWire-Ausgabe
#     (nur Änderungen werden geschrieben; ein hängender Stream wird als STALL markiert)
#
# Nutzung / usage:
#   ae5-diag.sh start          Protokoll im Hintergrund starten / start logging in the background
#   ae5-diag.sh mark [text]    Markierung setzen / set a mark ("sound lost")
#   ae5-diag.sh status         Läuft es? Wo liegt die Datei? / running? where is the file?
#   ae5-diag.sh stop           Protokoll beenden / stop logging
#   ae5-diag.sh run            Im Vordergrund laufen / run in the foreground

set -u

# Sprache: Deutsch bei deutscher Systemsprache, sonst Englisch (AE5_LANG=de|en erzwingt)
case "${AE5_LANG:-${LC_ALL:-${LC_MESSAGES:-${LANG:-}}}}" in de*) AE5_DE=1 ;; *) AE5_DE=0 ;; esac
t() { if [ "$AE5_DE" = 1 ]; then printf '%s' "$1"; else printf '%s' "$2"; fi; }

UNIT="ae5-diag"
LOG_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/ae5-control/diag"
CURRENT_LINK="$LOG_DIR/current.log"
INTERVAL=2

ts() { date '+%Y-%m-%d %H:%M:%S'; }

log() {
    printf '%s %s\n' "$(ts)" "$*" >>"$CURRENT_LINK"
}

# Karte über den Namen finden – die Kartennummer ändert sich zwischen Bootvorgängen.
find_card() {
    local f
    for f in /proc/asound/card[0-9]*/id; do
        [ -r "$f" ] || continue
        if [ "$(cat "$f")" = "Creative" ]; then
            basename "$(dirname "$f")"
            return 0
        fi
    done
    return 1
}

find_pci_dev() {
    local d
    for d in /sys/bus/pci/devices/*; do
        if [ "$(cat "$d/vendor" 2>/dev/null)" = "0x1102" ] && [ "$(cat "$d/device" 2>/dev/null)" = "0x0012" ]; then
            echo "$d"
            return 0
        fi
    done
    return 1
}

# Liefert den Zustand der Karte als eine Zeile (ohne hw_ptr, damit nur echte Änderungen zählen).
snapshot() {
    local card pci drv="" rt="" pcm="-" out="" sink
    card=$(find_card) || card="MISSING"
    pci=$(find_pci_dev) || pci=""
    if [ -n "$pci" ]; then
        [ -e "$pci/driver" ] && drv=$(basename "$(readlink "$pci/driver")")
        rt=$(cat "$pci/power/runtime_status" 2>/dev/null)
    fi
    if [ "$card" != "MISSING" ]; then
        pcm=$(awk '/^state:/{print $2}' /proc/asound/"$card"/pcm0p/sub0/status 2>/dev/null)
        [ -z "$pcm" ] && pcm=$(head -1 /proc/asound/"$card"/pcm0p/sub0/status 2>/dev/null)
        out=$(amixer -c "${card#card}" sget 'Output Select' 2>/dev/null | awk -F"'" '/Item0/{print $2}')
    fi
    local addr
    addr=$(basename "$pci" 2>/dev/null)
    sink=$(pactl list sinks short 2>/dev/null | awk -v a="pci-${addr//:/_}." 'index($2, a) {print $2" "$NF; exit}')
    [ -z "$sink" ] && sink="NO_PIPEWIRE_SINK"
    printf 'card=%s driver=%s pci_power=%s pcm=%s output=%s pipewire=[%s]' \
        "$card" "${drv:-none}" "${rt:-?}" "${pcm:-?}" "${out:-?}" "$sink"
}

hw_ptr() {
    local card
    card=$(find_card) || return 1
    awk '/^hw_ptr/{print $3}' /proc/asound/"$card"/pcm0p/sub0/status 2>/dev/null
}

run() {
    mkdir -p "$LOG_DIR"
    local file
    file="$LOG_DIR/ae5-diag-$(date '+%Y%m%d-%H%M%S').log"
    : >"$file"
    ln -sfn "$file" "$CURRENT_LINK"

    log "=== ae5-diag started (kernel $(uname -r)) ==="
    log "INFO $(pipewire --version 2>/dev/null | tail -1)"
    log "INFO snd_hda_intel power_save=$(cat /sys/module/snd_hda_intel/parameters/power_save 2>/dev/null)"

    # Kernel + System: Karte, Standby, Bildschirmsperre/Energieverwaltung
    local pci_re
    pci_re=$(basename "$(find_pci_dev)" 2>/dev/null | sed 's/^0000://; s/\./\\./g')
    journalctl -f -n 0 -o short-iso --no-pager 2>/dev/null \
        | grep --line-buffered -iE "ca0132|snd_hda|hdaudio|${pci_re:-ae5-none}|azx|suspend|resum|sleep|screenlock|powerdevil|dpms" \
        | sed -u 's/^/SYS  /' >>"$CURRENT_LINK" &
    local j1=$!
    # Benutzersitzung: PipeWire / WirePlumber
    journalctl --user -f -n 0 -o short-iso --no-pager 2>/dev/null \
        | grep --line-buffered -iE 'pipewire|wireplumber|spa\.alsa' \
        | sed -u 's/^/USER /' >>"$CURRENT_LINK" &
    local j2=$!

    trap 'log "=== ae5-diag stopped ==="; pkill -P $$ 2>/dev/null; exit 0' TERM INT

    local last="" cur ptr last_ptr="" pcm stalled=0
    while true; do
        cur=$(snapshot)
        if [ "$cur" != "$last" ]; then
            log "STATE $cur"
            last="$cur"
        fi
        # Hänger erkennen: Stream läuft, aber die Position bewegt sich nicht.
        pcm=$(sed -n 's/.*pcm=\([^ ]*\).*/\1/p' <<<"$cur")
        if [ "$pcm" = "RUNNING" ]; then
            ptr=$(hw_ptr)
            if [ -n "$ptr" ] && [ "$ptr" = "$last_ptr" ]; then
                [ $stalled -eq 0 ] && log "STALL stream running but hw_ptr stuck at $ptr – card not responding"
                stalled=1
            else
                [ $stalled -eq 1 ] && log "STALL over, hw_ptr moving again"
                stalled=0
            fi
            last_ptr="$ptr"
        else
            last_ptr=""
            stalled=0
        fi
        sleep "$INTERVAL" &
        wait $!
    done
}

case "${1:-}" in
    start)
        if systemctl --user is-active --quiet "$UNIT"; then
            echo "$(t "Läuft bereits. Datei:" "Already running. File:") $(readlink -f "$CURRENT_LINK")"
            exit 0
        fi
        systemctl --user reset-failed "$UNIT" 2>/dev/null
        systemd-run --user --unit="$UNIT" --description="AE-5 Diagnose-Protokoll" \
            "$(readlink -f "$0")" run >/dev/null
        sleep 1
        echo "$(t "Gestartet. Datei:" "Started. File:") $(readlink -f "$CURRENT_LINK")"
        ;;
    stop)
        if systemctl --user stop "$UNIT" 2>/dev/null; then t "Beendet." "Stopped."; else t "Lief nicht." "Was not running."; fi
        echo
        echo "$(t "Datei:" "File:") $(readlink -f "$CURRENT_LINK" 2>/dev/null)"
        ;;
    mark)
        shift
        log "MARK ${*:-sound lost}  |  $(snapshot)"
        t "Markierung gesetzt." "Mark set."; echo
        ;;
    status)
        if systemctl --user is-active --quiet "$UNIT"; then t "Läuft." "Running."; else t "Läuft nicht." "Not running."; fi
        echo
        echo "$(t "Datei:" "File:") $(readlink -f "$CURRENT_LINK" 2>/dev/null)"
        echo "$(t "Jetzt:" "Now:") $(snapshot)"
        ;;
    run)
        run
        ;;
    *)
        sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'
        exit 1
        ;;
esac
