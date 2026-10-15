#!/bin/bash
# Private Cage client. Stop the session if its display loop has disappeared.
set -Eeuo pipefail
resources="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
randr="$HOME/.local/opt/steamos-waydroid/current/bin/wlr-randr"
outputs="$(timeout 5 "$randr")"
count=0
output=""
while IFS= read -r line; do
    if [[ "$line" =~ ^[^[:space:]] ]]; then
        ((count+=1))
        output=${line%% *}
    fi
done <<< "$outputs"
[[ $count == 1 && -n "$output" ]] || {
    echo "Android compositor did not report exactly one output." >&2; exit 1;
}
timeout 5 "$randr" --output "$output" --custom-mode 1280x800
waydroid session start &
session=$!
watcher=""
startup_ready=false
startup_state() {
    [[ -z "${APKR_STARTUP_STATE_FILE:-}" ]] || printf '%s\n' "$1" > "$APKR_STARTUP_STATE_FILE"
}
cleanup() {
    $startup_ready || startup_state failed
    [[ -z "$watcher" ]] || kill "$watcher" 2>/dev/null || true
    if kill -0 "$session" 2>/dev/null; then
        timeout 15 waydroid session stop || true
        kill "$session" 2>/dev/null || true
    fi
}
trap cleanup EXIT
trap 'exit 143' TERM HUP INT
watch_display() {
    local failures=0
    while kill -0 "$session" 2>/dev/null; do
        sleep 2
        if timeout 2 "$randr" >/dev/null 2>&1; then failures=0
        else ((failures+=1)); fi
        if (( failures >= 2 )); then
            echo "The game display closed or stopped responding; stopping its Android session." >&2
            timeout 15 waydroid session stop || true
            for ((attempt=0; attempt<25; attempt++)); do
                kill -0 "$session" 2>/dev/null || return
                sleep 0.2
            done
            kill "$session" 2>/dev/null || true
            return
        fi
    done
}
watch_display &
watcher=$!
startup_state authorizing
sudo -A /bin/bash "$resources/managed-waydroid-startup.sh"
config="$HOME/Android_Waydroid/config"
for setting in fake_wifi fake_touch; do
    if [[ -r "$config/$setting" ]]; then
        waydroid prop set "persist.waydroid.$setting" "$(cat "$config/$setting")"
    fi
done
startup_ready=true
startup_state ready
wait "$session"
