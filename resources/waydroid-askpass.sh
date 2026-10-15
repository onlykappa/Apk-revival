#!/bin/sh
# sudo consumes this password through a pipe; never log or store it.
. "$(dirname -- "$0")/waydroid-auth-display.sh"
exec /usr/bin/kdialog --title 'APK Revival — Start game runtime' --password 'Authorize starting the existing game runtime. Your games and saves are preserved.'
