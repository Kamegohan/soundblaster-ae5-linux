#!/usr/bin/env bash
# Umstieg von der Handinstallation (install-*.sh) auf das pacman-Paket.
#
#   1. Paket bauen (vorher, damit nichts entfernt wird, wenn der Bau scheitert)
#   2. Handinstallierte Dateien entfernen (sonst Dateikonflikte bzw. überdeckte Paketdateien)
#   3. Paket installieren – schlägt das fehl, wird die Handinstallation wiederhergestellt
#   4. Benutzerdienste aktivieren, PipeWire neu laden, App neu starten
#
# Profile in ~/.config/ae5-control bleiben unverändert.
set -u

# Sprache: Deutsch bei deutscher Systemsprache, sonst Englisch (AE5_LANG=de|en erzwingt)
case "${AE5_LANG:-${LC_ALL:-${LC_MESSAGES:-${LANG:-}}}}" in de*) AE5_DE=1 ;; *) AE5_DE=0 ;; esac
t() { if [ "$AE5_DE" = 1 ]; then printf '%s' "$1"; else printf '%s' "$2"; fi; }
ROOT=$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)
cd "$ROOT/packaging" || exit 1

echo "==> 1/4 $(t "Paket bauen" "Building package")"
makepkg -f || { t "Bau fehlgeschlagen – nichts geändert." "Build failed – nothing changed."; echo; exit 1; }
PKG=$(ls -t ae5-control-*-any.pkg.tar.* | head -1)

echo "==> 2/4 $(t "Handinstallation entfernen" "Removing manual installation")"
sudo -v || exit 1
systemctl --user disable --now ae5-watchdog.service ae5-amp-guard.service 2>/dev/null
rm -f ~/.config/systemd/user/ae5-watchdog.service ~/.config/systemd/user/ae5-amp-guard.service \
      ~/.config/autostart/ae5-control.desktop ~/.local/share/applications/ae5-control.desktop \
      ~/.config/wireplumber/wireplumber.conf.d/51-ae5-no-suspend.conf
systemctl --user daemon-reload
sudo rm -f /etc/modprobe.d/ae5-control.conf \
           /etc/udev/rules.d/91-ae5-control.rules \
           /usr/lib/firmware/ae5-control/ae5-model.fw \
           /usr/share/alsa-card-profile/mixer/paths/ae5-output-headphones.conf \
           /usr/share/alsa-card-profile/mixer/paths/ae5-output-speakers.conf \
           /usr/share/alsa-card-profile/mixer/profile-sets/ae5-control.conf \
           /usr/share/polkit-1/actions/org.ae5control.reset.policy \
           /usr/local/libexec/ae5-control/ae5-reset-helper
sudo rmdir --ignore-fail-on-non-empty /usr/local/libexec/ae5-control /usr/lib/firmware/ae5-control 2>/dev/null

echo "==> 3/4 $(t "Paket installieren" "Installing package")"
if ! sudo pacman -U --noconfirm "$PKG"; then
    t "Installation fehlgeschlagen – stelle Handinstallation wieder her ..." "Installation failed – restoring the manual installation ..."; echo
    "$ROOT/tools/install-model-fix.sh"
    "$ROOT/tools/install-pipewire-profile.sh"
    "$ROOT/tools/install-recovery.sh"
    "$ROOT/tools/install-app.sh"
    exit 1
fi

echo "==> 4/4 $(t "Dienste aktivieren und neu laden" "Enabling services and reloading")"
systemctl --user daemon-reload
systemctl --user enable --now ae5-watchdog.service ae5-amp-guard.service
systemctl --user restart wireplumber pipewire pipewire-pulse
pkill -f '[p]ython3 -m ae5control.gui'
sleep 2
setsid /usr/bin/ae5-control --tray >/dev/null 2>&1 < /dev/null &
echo
echo "$(t "Fertig. Installiert:" "Done. Installed:") $(pacman -Q ae5-control)"
echo "$(t "Wächter" "Watchdog"): $(systemctl --user is-active ae5-watchdog) / $(t "Verstärker-Wächter" "Amplifier guard"): $(systemctl --user is-active ae5-amp-guard)"
