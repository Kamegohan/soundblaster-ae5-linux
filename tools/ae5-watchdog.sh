#!/usr/bin/env bash
# ae5-watchdog – erkennt, wenn die AE-5 hängt, und startet sie automatisch neu.
#
# "Hängt" heißt: Der Audio-Stream läuft, aber die Hardware-Position der Karte
# bewegt sich mehrere Sekunden lang nicht mehr (so sieht der Absturz nach einer
# statischen Entladung aus). Dann ruft der Wächter ae5-recover.sh --auto auf und
# zeigt eine Desktop-Meldung.
#
# Schutz vor Endlosschleifen: Nach 3 erfolglosen Versuchen innerhalb von
# 10 Minuten gibt der Wächter auf und meldet das.

set -u

# Sprache: Deutsch bei deutscher Systemsprache, sonst Englisch (AE5_LANG=de|en erzwingt)
case "${AE5_LANG:-${LC_ALL:-${LC_MESSAGES:-${LANG:-}}}}" in de*) AE5_DE=1 ;; *) AE5_DE=0 ;; esac
t() { if [ "$AE5_DE" = 1 ]; then printf '%s' "$1"; else printf '%s' "$2"; fi; }

SELF_DIR=$(cd "$(dirname "$(readlink -f "$0")")" && pwd)
RECOVER="$SELF_DIR/ae5-recover.sh"
LOG="${XDG_STATE_HOME:-$HOME/.local/state}/ae5-control/diag/current.log"
INTERVAL=2          # Sekunden zwischen zwei Messungen
STALL_LIMIT=3       # so viele Messungen ohne Bewegung = Hänger (~6 s)
COOLDOWN=30         # Sekunden Pause nach einem Neustart
FAIL_WINDOW=600     # Zeitfenster für Fehlversuche
FAIL_LIMIT=3

log() {
    echo "$*"
    [ -e "$LOG" ] && printf '%s WATCHDOG %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >>"$LOG"
}

notify() {
    notify-send --app-name="AE-5" --icon=audio-card "$1" "${2:-}" 2>/dev/null || true
}

find_card() {
    local f
    for f in /proc/asound/card[0-9]*/id; do
        [ "$(cat "$f" 2>/dev/null)" = "Creative" ] && { basename "$(dirname "$f")"; return 0; }
    done
    return 1
}

# Gibt "STATE HW_PTR" des Wiedergabe-Streams aus
read_pcm() {
    local card st
    card=$(find_card) || return 1
    st=/proc/asound/"$card"/pcm0p/sub0/status
    awk '/^state:/{s=$2} /^hw_ptr/{p=$3} END{print s, p}' "$st" 2>/dev/null
}

log "$(t "Wächter gestartet." "Watchdog started.")"
fails=()
stall=0
last_ptr=""

while true; do
    sleep "$INTERVAL"
    read -r state ptr <<<"$(read_pcm)" || { stall=0; last_ptr=""; continue; }

    if [ "$state" != "RUNNING" ] || [ -z "$ptr" ]; then
        stall=0; last_ptr=""; continue
    fi
    if [ "$ptr" != "$last_ptr" ]; then
        stall=0; last_ptr="$ptr"; continue
    fi

    stall=$((stall + 1))
    [ $stall -lt $STALL_LIMIT ] && continue

    # Hänger erkannt
    now=$(date +%s)
    recent=()
    for t in "${fails[@]}"; do
        [ $((now - t)) -lt $FAIL_WINDOW ] && recent+=("$t")
    done
    fails=("${recent[@]}")
    if [ ${#fails[@]} -ge $FAIL_LIMIT ]; then
        log "$(t "Zu viele Fehlversuche – automatischer Neustart pausiert." "Too many failed attempts – automatic restart paused.")"
        notify "$(t "AE-5 kommt nicht zurück" "AE-5 does not come back")" "$(t "Automatischer Neustart hat mehrfach nicht geholfen. Bitte PC neu starten." "Automatic restart failed repeatedly. Please reboot.")"
        sleep $FAIL_WINDOW
        stall=0; last_ptr=""; continue
    fi

    log "$(t "Hänger erkannt (hw_ptr steht bei $ptr) – starte AE-5 neu." "Hang detected (hw_ptr stuck at $ptr) – restarting AE-5.")"
    notify "$(t "AE-5 hängt" "AE-5 hung")" "$(t "Soundkarte wird automatisch neu gestartet …" "Restarting the sound card automatically …")"
    if "$RECOVER" --auto --hang; then
        notify "$(t "AE-5 läuft wieder" "AE-5 is back")" "$(t "Falls ein Programm pausiert hat (z. B. Spotify): einmal auf Play drücken." "If an app paused (e.g. Spotify): press play once.")"
    else
        fails+=("$now")
        notify "$(t "AE-5-Neustart fehlgeschlagen" "AE-5 restart failed")" "Details: ~/.local/state/ae5-control/diag/current.log"
    fi
    stall=0; last_ptr=""
    sleep $COOLDOWN
done
