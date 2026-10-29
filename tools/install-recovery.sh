#!/usr/bin/env bash
# Installiert den passwortlosen Notfall-Neustart und den Wächter.
#   - Root-Helfer:   /usr/local/libexec/ae5-control/ae5-reset-helper
#   - polkit-Regel:  /usr/share/polkit-1/actions/org.ae5control.reset.policy
#   - Wächter:       ~/.config/systemd/user/ae5-watchdog.service (aktiviert)
#   - Verstärker-Wächter: ~/.config/systemd/user/ae5-amp-guard.service (aktiviert)
#   install-recovery.sh            installieren
#   install-recovery.sh --remove   wieder entfernen
set -eu

# Sprache: Deutsch bei deutscher Systemsprache, sonst Englisch (AE5_LANG=de|en erzwingt)
case "${AE5_LANG:-${LC_ALL:-${LC_MESSAGES:-${LANG:-}}}}" in de*) AE5_DE=1 ;; *) AE5_DE=0 ;; esac
t() { if [ "$AE5_DE" = 1 ]; then printf '%s' "$1"; else printf '%s' "$2"; fi; }
DIR=$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)
HELPER_DST=/usr/local/libexec/ae5-control/ae5-reset-helper
POLICY_DST=/usr/share/polkit-1/actions/org.ae5control.reset.policy
UNIT_DST="$HOME/.config/systemd/user/ae5-watchdog.service"
AMP_DST="$HOME/.config/systemd/user/ae5-amp-guard.service"

if [ "${1:-}" = "--remove" ]; then
    systemctl --user disable --now ae5-watchdog.service ae5-amp-guard.service 2>/dev/null || true
    rm -f "$UNIT_DST" "$AMP_DST"
    systemctl --user daemon-reload
    sudo rm -f "$POLICY_DST" "$HELPER_DST"
    sudo rmdir --ignore-fail-on-non-empty "$(dirname "$HELPER_DST")"
    t "Entfernt." "Removed."; echo
    exit 0
fi

sudo install -Dm755 -o root -g root "$DIR/system/ae5-reset-helper" "$HELPER_DST"
sudo install -Dm644 -o root -g root "$DIR/system/org.ae5control.reset.policy" "$POLICY_DST"
mkdir -p "$(dirname "$UNIT_DST")"
sed "s|@LIBDIR@|$DIR|" "$DIR/systemd/ae5-watchdog.service" > "$UNIT_DST"
sed "s|@LIBDIR@|$DIR|" "$DIR/systemd/ae5-amp-guard.service" > "$AMP_DST"
systemctl --user daemon-reload
systemctl --user enable --now ae5-watchdog.service ae5-amp-guard.service
echo "$(t "Installiert. Wächter:" "Installed. Watchdog:") $(systemctl --user is-active ae5-watchdog.service)"
