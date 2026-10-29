#!/usr/bin/env bash
# ae5-amp-guard – weckt den Kopfhörerverstärker der AE-5, sobald nach einer Pause
# wieder Ton startet.
#
# Hintergrund: Stoppt ein Stream und startet neu, nimmt die AE-5 zwar Daten an,
# ihr Ausgang bleibt aber stumm (Zustand im DSP, von Linux aus nicht sichtbar).
# Kurzes Umschalten von "Output Select" auf den anderen Ausgang und zurück holt
# den Ton zurück. Dieses Skript lauscht auf PipeWire-Ereignisse und tut das
# genau dann, wenn die AE-5-Ausgabe von "nicht spielend" auf RUNNING wechselt.

set -u

# Sprache: Deutsch bei deutscher Systemsprache, sonst Englisch (AE5_LANG=de|en erzwingt)
case "${AE5_LANG:-${LC_ALL:-${LC_MESSAGES:-${LANG:-}}}}" in de*) AE5_DE=1 ;; *) AE5_DE=0 ;; esac
t() { if [ "$AE5_DE" = 1 ]; then printf '%s' "$1"; else printf '%s' "$2"; fi; }
export LC_ALL=C

LOG="${XDG_STATE_HOME:-$HOME/.local/state}/ae5-control/diag/current.log"

log() {
    echo "$*"
    [ -e "$LOG" ] && printf '%s AMPGUARD %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >>"$LOG"
}

find_card() {
    local f
    for f in /proc/asound/card[0-9]*/id; do
        [ "$(cat "$f" 2>/dev/null)" = "Creative" ] && { basename "$(dirname "$f")"; return 0; }
    done
    return 1
}

# PCI-Adresse der AE-5 (Creative 1102:0012)
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

# PipeWire-Ausgabe der AE-5 (alsa_output.pci-<adresse>.<profil>) und ihr Zustand
ae5_sink() {
    local addr
    addr=$(find_pci_addr) || return 1
    pactl list sinks short 2>/dev/null | awk -v a="pci-${addr//:/_}." 'index($2, a) {print $2" "$NF; exit}'
}

# Zustand der AE-5-Ausgabe in PipeWire: RUNNING, IDLE, SUSPENDED oder leer
sink_state() {
    ae5_sink | awk '{print $2}'
}

amp_reinit() {
    local card n cur other
    card=$(find_card) || return 0
    n=${card#card}
    cur=$(amixer -c "$n" sget 'Output Select' 2>/dev/null | awk -F"'" '/Item0/{print $2}')
    [ -z "$cur" ] && return 0
    if [ "$cur" = "Headphone" ]; then other=Speakers; else other=Headphone; fi
    amixer -c "$n" sset 'Output Select' "$other" >/dev/null 2>&1
    sleep 0.15
    amixer -c "$n" sset 'Output Select' "$cur" >/dev/null 2>&1
    log "$(t "Ton startet – Verstärker neu angesteuert ($cur)." "Sound starting – amplifier re-initialized ($cur).")"
}

log "$(t "Verstärker-Wächter gestartet." "Amplifier guard started.")"
last=$(sink_state)
[ "$last" = "RUNNING" ] && amp_reinit

# Bei jedem Ereignis zu Ausgaben/Streams den Zustand prüfen
pactl subscribe 2>/dev/null | while read -r line; do
    case "$line" in
        *" on sink #"* | *" on sink-input #"*) ;;
        *) continue ;;
    esac
    state=$(sink_state)
    if [ "$state" = "RUNNING" ] && [ "$last" != "RUNNING" ]; then
        amp_reinit
    fi
    last=$state
done

log "$(t "Verbindung zu PipeWire verloren – Dienst startet neu." "Lost connection to PipeWire – service restarts.")"
exit 1
