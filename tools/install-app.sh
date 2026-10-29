#!/usr/bin/env bash
# Richtet die Einstellungs-App ein: Menüeintrag + Autostart im Tray. Ohne Root.
#   install-app.sh            einrichten
#   install-app.sh --remove   Menüeintrag und Autostart entfernen
set -eu

# Sprache: Deutsch bei deutscher Systemsprache, sonst Englisch (AE5_LANG=de|en erzwingt)
case "${AE5_LANG:-${LC_ALL:-${LC_MESSAGES:-${LANG:-}}}}" in de*) AE5_DE=1 ;; *) AE5_DE=0 ;; esac
t() { if [ "$AE5_DE" = 1 ]; then printf '%s' "$1"; else printf '%s' "$2"; fi; }
ROOT=$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)
APP="$HOME/.local/share/applications/ae5-control.desktop"
AUTO="$HOME/.config/autostart/ae5-control.desktop"

if [ "${1:-}" = "--remove" ]; then
    rm -f "$APP" "$AUTO"
    t "Entfernt." "Removed."; echo
    exit 0
fi

mkdir -p "$(dirname "$APP")" "$(dirname "$AUTO")"
sed "s|@ROOT@|$ROOT|g" "$ROOT/desktop/ae5-control.desktop" > "$APP"
sed -e "s|@ROOT@|$ROOT|g" -e "s|^Exec=.*|Exec=$ROOT/bin/ae5-control --tray|" \
    "$ROOT/desktop/ae5-control.desktop" > "$AUTO"
echo "X-KDE-autostart-after=panel" >> "$AUTO"
update-desktop-database "$(dirname "$APP")" 2>/dev/null || true
echo "$(t "Menüeintrag:" "Menu entry:") $APP"
echo "Autostart (Tray): $AUTO"
