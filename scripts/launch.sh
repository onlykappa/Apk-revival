#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
if [ -f "$HOME/.cache/apk-revival/tools/env.sh" ]; then
    . "$HOME/.cache/apk-revival/tools/env.sh"
fi
exec python3 -m apk_revival gui

