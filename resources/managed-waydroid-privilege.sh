#!/bin/bash
# Never authorize a user-writable shell script password-free. The optional
# installed helper is root-owned and sudoers permits only its fixed actions.
apkr_runtime_privileged() {
    local action=$1
    local helper=/etc/apk-revival/runtime-helper
    if [[ -x "$helper" ]]; then
        /usr/bin/sudo -n "$helper" "$action"
        return $?
    fi
    case "$action" in
        preflight) /usr/bin/sudo -A /usr/bin/waydroid-mount main --check-only ;;
        mount) /usr/bin/sudo -A /usr/bin/waydroid-mount main ;;
        start-container) /usr/bin/sudo -A /usr/bin/waydroid-firewall ;;
        post-start) /usr/bin/sudo -A /bin/bash "$resources/managed-waydroid-startup.sh" ;;
        *) return 64 ;;
    esac
}
