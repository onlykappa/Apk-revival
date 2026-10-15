#!/bin/bash
# Use the installed SteamOS main profile and its privileged lifecycle helpers.
set -Eeuo pipefail
source /usr/lib/steamos-waydroid/waydroid-profile.sh
resolve_waydroid_profile main
export XDG_DATA_HOME=$WAYDROID_XDG_DATA_HOME
sudo -A /usr/bin/waydroid-mount main --check-only
sudo -A /usr/bin/waydroid-mount main
sudo -A /usr/bin/waydroid-firewall
bundle="$HOME/.local/opt/steamos-waydroid/current"
selector="$HOME/Android_Waydroid/select-bundle"
if [[ -x "$selector" ]]; then "$selector"; fi
[[ -f "$bundle/.verified" ]] || { echo 'Cage bundle is missing or unverified.' >&2; exit 1; }
"$bundle/tools/check-bundle-target.sh" "$bundle"
resources="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# Opt-in Desktop experiment: reuse only the explicitly supplied KDE socket.
# Invalid or unavailable desktop displays keep the existing nested launch path.
if [[ "${APKR_RUNTIME_DISPLAY:-}" == desktop &&
      "${XDG_SESSION_TYPE:-}" == wayland &&
      ":${XDG_CURRENT_DESKTOP:-}:" == *:KDE:* &&
      -n "${WAYLAND_DISPLAY:-}" ]]; then
    desktop_socket=$WAYLAND_DISPLAY
    if [[ "$desktop_socket" != /* ]]; then
        desktop_socket="${XDG_RUNTIME_DIR:-}/$desktop_socket"
    fi
    if [[ -n "${XDG_RUNTIME_DIR:-}" && -d "$XDG_RUNTIME_DIR" &&
          -O "$XDG_RUNTIME_DIR" && -S "$desktop_socket" && -O "$desktop_socket" ]]; then
        export APKR_DESKTOP_WAYLAND_SOCKET=$desktop_socket
        exec /bin/bash "$resources/managed-waydroid-desktop-session.sh"
    fi
fi
# Cage owns a dedicated Android Wayland socket in Desktop and Gaming Mode.
# Use the nested X11 backend supported by this installed SteamOS bundle.
export WLR_BACKENDS=x11
export WLR_LIBINPUT_NO_DEVICES=1
exec "$bundle/bin/cage" -- /bin/bash "$resources/managed-waydroid-session.sh"
