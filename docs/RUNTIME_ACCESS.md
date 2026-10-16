# Optional password-free runtime startup

APK Revival still needs the installed Waydroid Android runtime. The Deck
candidate merges upstream v0.3.8's launcher with the tested local Meego engine;
this setup does not replace Android or change any game save or APK.

The repeated password prompt came from running the user-owned
`managed-waydroid-startup.sh` as root. It preserves the shared folder and
controller discovery. Granting password-free access to a user-writable shell
script would also grant arbitrary administrator commands, so this candidate
does not do that. The installed bundle's general startup script also changes
system/Android settings and is deliberately not used as a shortcut.

Setup -> Enable password-free startup requests ONE administrator authorization
to install `/etc/apk-revival/runtime-helper` (root-owned0755) and
`/etc/sudoers.d/zzzzzzzzzz-apk-revival-runtime` (root-owned0440). The rule names the invoking
account, root as the only target account, NOSETENV, and exactly five commands:
probe, preflight, mount, start-container and post-start. There are no wildcard
arguments, password-free shells, user-selected paths or other runtime profiles.
The helper uses existing system runtime libraries and a fixed main profile.
It preserves shared storage and existing controller integration. It changes no
kernel settings, Android security settings or file permissions in game storage.

The installer validates account identity, dependency ownership, protected target
directories, shell and sudoers syntax. It refuses symlinks/unrelated files and
restores its previous files if validation fails. It migrates only its own old
`apk-revival-runtime` rule. The late filename prevents earlier general SteamOS
wheel rules from overriding the narrow NOPASSWD exceptions. After syntax
validation, it drops to the invoking account with runuser and tests
`sudo -k -n -- /etc/apk-revival/runtime-helper probe`; ignoring cached
credentials proves that noninteractive access actually works. It does not start, stop, reset
or reinstall Android. It does not store your password or change global sudo
timeout/security policy. Root dependencies must already exist.

Once configured, Play uses `sudo -n` for those exact helper actions. An installed
helper failure is reported rather than retried via another password prompt.
Without setup, the existing graphical authorization path remains available.
The helper is system configuration and stays across application replacements.
Removal requires an administrator to remove only these two dedicated files;
the old graphical startup path then applies again.

The development sandbox cannot elevate privileges (`no new privileges` is set),
so it cannot install this system configuration. Tests cover policy parsing with
real visudo, account/argument rejection, rollback, and launcher command routing.
Actual installation and a stopped-runtime password-free launch must be verified
on the host after the user completes the one-time setup. Do not claim that
passing these tests has removed the password prompt on this Deck.
