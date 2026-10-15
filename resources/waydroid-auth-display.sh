#!/bin/sh
# Cage changes the child's display. Authorization belongs on the launcher's
# parent desktop, including when sudo calls askpass after Android has booted.
if [ "${APKR_AUTH_CONTEXT-}" = 1 ]; then
    if [ -n "${APKR_AUTH_WAYLAND_DISPLAY-}" ]; then
        WAYLAND_DISPLAY=$APKR_AUTH_WAYLAND_DISPLAY; export WAYLAND_DISPLAY
    else unset WAYLAND_DISPLAY; fi
    if [ -n "${APKR_AUTH_DISPLAY-}" ]; then
        DISPLAY=$APKR_AUTH_DISPLAY; export DISPLAY
    else unset DISPLAY; fi
    if [ -n "${APKR_AUTH_XAUTHORITY-}" ]; then
        XAUTHORITY=$APKR_AUTH_XAUTHORITY; export XAUTHORITY
    else unset XAUTHORITY; fi
fi
