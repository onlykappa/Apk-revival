# Offline gameplay verification

The `Verified Offline` label requires **actual Android gameplay under an enforced guest network guard**, with an exact artifact hash and recorded results. A successful APK signature, install, activity launch or server health request is insufficient.

## Fixture checks

1. Stop the game and install the prepared signed client.
2. Require guest root and create unique temporary IPv4 and IPv6 OUTPUT chains. Allow guest loopback. Preserve only TCP 5555 ADB replies from root/shell UID, then reject all remaining guest egress. The host firewall is not modified.
3. Record the actual chain and OUTPUT rules and guest routes; an external TCP negative probe must fail. No silent IPv4-only fallback is allowed.
4. Cold-launch the game. For the backend path, start the host server, reverse-forward the configured port, and prove guest-to-host reachability with a fresh backend health nonce.
5. Observe a `ready` event from the fixture containing rendered coin/level state.
6. Use UIAutomator to find and tap the visible **Collect coin** control. Check that `saved` reports exactly one additional coin.
7. Force-stop and relaunch. Check rendered loaded progress equals the saved state.
8. For the backend path, actually stop the backend and its forwarding, relaunch to a backend error, start a fresh instance, confirm guest reachability, tap **Retry**, and confirm preserved progress.
9. Confirm the artifact hash did not change, save exact observations/logs and clean up firewall rules, game, forwarding and backend.

V1's automated verifier only understands the self-authored fixture. Unknown games must supply an adapter-specific verifier. Fixture log markers are intentionally instrumented test evidence; they are not proof of gameplay in an unrelated game. A commercial adapter should use appropriate UI assertions, screenshots, state changes, and save evidence.

Requirements: a specific connected Android ADB serial; `su 0` guest root; working `iptables`, `ip6tables`, owner matching, `toybox nc`, UIAutomator and Android shell utilities. Failure records the exact error and does not certify the game. A test changes a fixture save by one coin, without clearing it.

## Scope of a passing result

The defined cold activity launch, one meaningful collect action, save/relaunch and backend recovery have passed under the recorded rules. It does not establish all levels, purchases, multiplayer, runtime reboot, long-session stability, every ABI or every Waydroid/Steam Deck configuration. Fixture verification is separate from a real game's restoration.

`passes()` requires all checks plus the Android gameplay kind and explicit external-network-blocked flag. Host protocol tests and rebuild tests cannot pass that gate. Exports remain **Exported but Unverified** until actual guest verification passes.

## Recovery after abrupt termination

Normal completion/error cleanup removes only this run's unique `APKR_*` chains. If the process is killed or the guest connection disappears during testing, reconnect to the **same test guest** and inspect:

```bash
adb -s GUEST_IP:5555 shell su 0 iptables -S OUTPUT
adb -s GUEST_IP:5555 shell su 0 ip6tables -S OUTPUT
```

For each exact `APKR_RUN_ID` left by a crashed verification, remove only that chain:

```bash
adb -s GUEST_IP:5555 shell su 0 iptables -D OUTPUT -j APKR_RUN_ID
adb -s GUEST_IP:5555 shell su 0 iptables -F APKR_RUN_ID
adb -s GUEST_IP:5555 shell su 0 iptables -X APKR_RUN_ID
adb -s GUEST_IP:5555 shell su 0 ip6tables -D OUTPUT -j APKR_RUN_ID
adb -s GUEST_IP:5555 shell su 0 ip6tables -F APKR_RUN_ID
adb -s GUEST_IP:5555 shell su 0 ip6tables -X APKR_RUN_ID
```

Do not flush all rules. Runtime reboot also removes these nonpersistent chains. The verifier deliberately does not persist firewall changes.

## Save restore

Fixture SharedPreferences backups use `run-as` on the debuggable fixture. Unknown private save paths and arbitrary root overwrites are unsupported. Local backend/rebuild saves use atomic JSON. Restore checks original APK hash and selected path and preserves an earlier backup when present. Stop active launchers before restoring through the CLI; the GUI does this automatically.
