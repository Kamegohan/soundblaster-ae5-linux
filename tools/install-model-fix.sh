#!/usr/bin/env bash
# Installiert die Treiber-Vorgabe, damit die AE-5 auch nach einem harten Reset
# als AE-5 erkannt wird. Wirkt ab dem nächsten Start (oder Neu-Einbinden der Karte).
#   install-model-fix.sh            installieren
#   install-model-fix.sh --remove   wieder entfernen
set -eu

# Sprache: Deutsch bei deutscher Systemsprache, sonst Englisch (AE5_LANG=de|en erzwingt)
case "${AE5_LANG:-${LC_ALL:-${LC_MESSAGES:-${LANG:-}}}}" in de*) AE5_DE=1 ;; *) AE5_DE=0 ;; esac
t() { if [ "$AE5_DE" = 1 ]; then printf '%s' "$1"; else printf '%s' "$2"; fi; }
DIR=$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)
FW_DST=/usr/lib/firmware/ae5-control/ae5-model.fw
CONF_DST=/etc/modprobe.d/ae5-control.conf

if [ "${1:-}" = "--remove" ]; then
    # Zuerst die Option entfernen, dann die Datei – sonst findet der Treiber sie nicht
    sudo rm -f "$CONF_DST"
    sudo rm -f "$FW_DST"
    sudo rmdir --ignore-fail-on-non-empty "$(dirname "$FW_DST")"
    t "Entfernt." "Removed."; echo
    exit 0
fi

# Reihenfolge wichtig: erst die Datei, dann die Option, die auf sie verweist
sudo install -Dm644 "$DIR/config/ae5-model.fw" "$FW_DST"
sudo install -Dm644 "$DIR/config/ae5-control.conf" "$CONF_DST"
t "Installiert:" "Installed:"; echo
echo "  $FW_DST"
echo "  $CONF_DST"
t "Wirkt ab dem nächsten Start." "Takes effect after the next boot."; echo
