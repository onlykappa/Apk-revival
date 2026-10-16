#!/bin/bash
# Opt-in client of the existing KDE compositor. Never manage the compositor.
set -Eeuo pipefail
resources="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$resources/managed-waydroid-privilege.sh"
session=""
startup_ready=false
startup_state() {
    [[ -z "${APKR_STARTUP_STATE_FILE:-}" ]] || printf '%s\n' "$1" > "$APKR_STARTUP_STATE_FILE"
}
cleanup() {
    $startup_ready || startup_state failed || true
    if [[ -n "$session" ]] && kill -0 "$session" 2>/dev/null; then
        timeout 15 waydroid session stop || true
        kill "$session" 2>/dev/null || true
        for ((attempt=0; attempt<25; attempt++)); do
            kill -0 "$session" 2>/dev/null || break
            sleep 0.2
        done
        if kill -0 "$session" 2>/dev/null; then
            kill -KILL "$session" 2>/dev/null || true
        fi
        wait "$session" 2>/dev/null || true
    fi
}
trap cleanup EXIT
trap 'exit 143' TERM HUP INT
[[ "${APKR_RUNTIME_DISPLAY:-}" == desktop &&
   "${XDG_SESSION_TYPE:-}" == wayland &&
   ":${XDG_CURRENT_DESKTOP:-}:" == *:KDE:* &&
   -n "${WAYLAND_DISPLAY:-}" &&
   -n "${APKR_DESKTOP_WAYLAND_SOCKET:-}" &&
   -S "$APKR_DESKTOP_WAYLAND_SOCKET" && -O "$APKR_DESKTOP_WAYLAND_SOCKET" ]] || {
    echo 'The declared KDE Wayland display is unavailable or not owned by this user.' >&2
    exit 1
}
waydroid session start &
session=$!
startup_state authorizing
apkr_runtime_privileged post-start
kill -0 "$session" 2>/dev/null || {
    echo 'The Android session ended during runtime startup.' >&2
    exit 1
}
config="$HOME/Android_Waydroid/config"
for setting in fake_wifi fake_touch; do
    if [[ -r "$config/$setting" ]]; then
        waydroid prop set "persist.waydroid.$setting" "$(cat "$config/$setting")"
    fi
done
startup_ready=true
startup_state ready
wait "$session"
