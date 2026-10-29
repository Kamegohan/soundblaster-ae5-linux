#!/usr/bin/env bash
# Installiert das eigene PipeWire-Profil für die AE-5 (Kopfhörer-Port ohne
# stummgeschalteten Front-Kanal) und weist es per udev nur der AE-5 zu.
#   install-pipewire-profile.sh            installieren
#   install-pipewire-profile.sh --remove   wieder entfernen
set -eu

# Sprache: Deutsch bei deutscher Systemsprache, sonst Englisch (AE5_LANG=de|en erzwingt)
case "${AE5_LANG:-${LC_ALL:-${LC_MESSAGES:-${LANG:-}}}}" in de*) AE5_DE=1 ;; *) AE5_DE=0 ;; esac
t() { if [ "$AE5_DE" = 1 ]; then printf '%s' "$1"; else printf '%s' "$2"; fi; }
DIR=$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)
ACP=/usr/share/alsa-card-profile/mixer
RULE=/etc/udev/rules.d/91-ae5-control.rules
NOSUSPEND="$HOME/.config/wireplumber/wireplumber.conf.d/51-ae5-no-suspend.conf"
SAFE_VOLUME=15%

# PCI-Adresse der AE-5 (Creative 1102:0012)
ADDR=""
for d in /sys/bus/pci/devices/*; do
    if [ "$(cat "$d/vendor" 2>/dev/null)" = "0x1102" ] && [ "$(cat "$d/device" 2>/dev/null)" = "0x0012" ]; then
        ADDR=$(basename "$d")
    fi
done

reload() {
    sudo udevadm control --reload
    sudo udevadm trigger --action=change --subsystem-match=sound
    sleep 1
    systemctl --user restart wireplumber pipewire pipewire-pulse
    # Neue Ports haben keine gespeicherte Lautstärke – zur Sicherheit leise starten
    local i sink=""
    for ((i = 0; i < 15; i++)); do
        sink=$(pactl list sinks short 2>/dev/null | awk -v a="pci-${ADDR//:/_}." 'index($2, a) {print $2; exit}')
        [ -n "$sink" ] && break
        sleep 1
    done
    if [ -n "$sink" ]; then
        for ((i = 0; i < 8; i++)); do pactl set-sink-volume "$sink" "$SAFE_VOLUME"; sleep 0.5; done
        echo "$(t "AE-5-Ausgabe:" "AE-5 output:") $sink ($(t "Lautstärke" "volume") $SAFE_VOLUME)"
    fi
}

if [ "${1:-}" = "--remove" ]; then
    sudo rm -f "$RULE"
    rm -f "$NOSUSPEND"
    sudo rm -f "$ACP/profile-sets/ae5-control.conf" "$ACP/paths/ae5-output-headphones.conf" "$ACP/paths/ae5-output-speakers.conf"
    reload
    t "Entfernt – AE-5 nutzt wieder das Standard-Profil." "Removed – the AE-5 uses the default profile again."; echo
    exit 0
fi

# Erst die Vorlagen, dann die Regel, die auf sie verweist
sudo install -Dm644 "$DIR/pipewire/ae5-output-headphones.conf" "$ACP/paths/ae5-output-headphones.conf"
sudo install -Dm644 "$DIR/pipewire/ae5-output-speakers.conf" "$ACP/paths/ae5-output-speakers.conf"
sudo install -Dm644 "$DIR/pipewire/ae5-control.conf" "$ACP/profile-sets/ae5-control.conf"
sudo install -Dm644 "$DIR/system/91-ae5-control.rules" "$RULE"
# AE-5 nie in den Ruhezustand schicken (danach bliebe der Kopfhörer stumm)
install -Dm644 "$DIR/pipewire/51-ae5-no-suspend.conf" "$NOSUSPEND"
reload
t "Installiert." "Installed."; echo
