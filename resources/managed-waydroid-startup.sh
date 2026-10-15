#!/bin/bash
# Only preserve shared storage and existing controller device discovery.
# Do not run the bundle's broad chmod/sysctl/setup-wizard/privileged-app tweaks.
set -Eeuo pipefail
source /usr/lib/steamos-waydroid/shared-folder.sh
resolve_waydroid_profile main
export XDG_DATA_HOME=$WAYDROID_XDG_DATA_HOME
user_home="$(waydroid_user_home)"
mount_waydroid_share_when_ready "$user_home" 90 2 main
for event in /sys/devices/virtual/input/input*/event*/uevent; do
    [[ ! -w "$event" ]] || printf 'add\n' > "$event"
done
# Preserve the installed controller hotplug integration where Android 16 needs it.
if [[ "$(waydroid shell -- getprop ro.build.version.sdk)" == 36 && -x /usr/bin/waydroid-controller-hotplug ]]; then
    /usr/bin/waydroid-controller-hotplug --stop main || true
    /usr/bin/waydroid-controller-hotplug main &
fi
