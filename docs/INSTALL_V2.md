APK REVIVAL V2: START HERE

1. Download from GitHub Releases, then extract APK-Revival-0.3.1-linux-x86_64.tar.gz in Steam Deck Desktop Mode.
2. Open the extracted APK-Revival folder and double-click APK-Revival.
3. Select Setup > Install desktop shortcut to install it in your home folder.
4. Open APK Revival from the application menu. Add an APK, Prepare, then Play.

No terminal, Python installation or administrator password is needed for the
launcher installation. Linux x86_64 with glibc 2.39 or newer is required for
this build. Application-menu launch enables fullscreen; use the Fullscreen
button to return to a window. Older Linux distributions need a build produced
on a compatible older base system.

TRY IT NOW
Select Try desktop demo, then Play. Collect coins, return to the library and
Play again. The included Tap Quest desktop game persists progress and works
without Android. It is an independent rebuild of our self-authored fixture,
not verification of the original Android APK.

PREPARATION TOOLS
Setup > Install preparation tools downloads verified Android SDK tools,
apktool, and a private Java runtime if Java is missing. These stay in your
user cache and require no administrator access. Read the upstream licenses
presented in the project documentation. Internet is required for tool setup;
core analysis and gameplay workflows remain local after setup.

ANDROID / WAYDROID
Waydroid must be installed and configured for your SteamOS version separately.
The launcher checks its status, discovers its Android IP where available,
connects, and offers a device picker. Setup provides Start Android, a reviewed
administrator-authorized Start container action, Check again and a guided
installation link. It never disables SteamOS protections or installs system
packages automatically. ARM-only games may require separately configured
translation. SteamOS Gaming Mode requires an appropriate Wayland setup.

ADD TO STEAM
After installing the desktop shortcut, open Steam in Desktop Mode.
Choose Games > Add a Non-Steam Game. Select APK Revival and add it.
If it is missing from the list, browse to:
/home/deck/.local/share/apk-revival-app/APK-Revival
The application-menu shortcut includes fullscreen. If you manually browse to
the executable, set --fullscreen in Steam's launch options. This is a Steam
setting, not a terminal command.

GAME OPTIONS
Backup Save, Restore Save, supporting files and Export are under Game options.
Technical reports, profiles, backend details, verification and job logs are
under Advanced. Unknown games need a game-specific restoration adapter; Add
Game does not promise universal conversion.

PORTABLE EXPORTS
The packaged app exports a native Play-Game launcher alongside the selected
game and required assets. Extract the entire ZIP and open Play-Game. If your
archive tool removes executable permission, use Properties > Permissions to
allow it to run. Android exports still need Waydroid and connection tools.

PRIVATE DATA
Games and saves are under ~/.local/share/apk-revival, outside the application.
Updating the app preserves them. The user-local installer also preserves the
previous application folder. Signing keys remain private and are not exported.

VERIFICATION
Prepared and Launch tested are separate from Verified Offline. The latter
requires recorded Android gameplay/persistence checks under network blocking.
Our original V1 Android attempt timed out; this release does not inherit a
passing gameplay claim. See the V2 test report for exactly what was exercised.

This package is unsigned. Source: https://github.com/onlykappa/Apk-revival


UPDATES
Setup > Check for updates checks the official GitHub releases. Accept an update
to download, validate SHA-256, stage, check compatibility, install and restart.
The previous app is retained; games and saves remain in the separate data folder.
Private releases require Setup > GitHub access: provide a read-only repository
token for this session only. It is never persisted or included in diagnostics.
Alternatively choose Open releases, download the official Linux tar.gz while
signed in to GitHub, then Install downloaded update. No manual extraction.
This first certificate-fix release must be installed once from the release
download because older versions do not yet contain the updater.

HTTPS CERTIFICATES
Portable CA certificates are included. HTTPS verification stays enabled. If
verification still fails, check your Deck clock and captive network sign-in.
