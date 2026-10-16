# Data and execution boundaries

APK/OBB/game inputs and saves belong in the private data root, outside Git. Import preserves originals, copies all bytes into private storage and hashes each input. Analysis does not run APKs or contact embedded endpoints. Launching explicitly installs/runs code in the user's configured Android guest.

Archive inspection rejects traversal, absolute names, duplicate entries, encrypted entries and symbolic links, and bounds declared uncompressed sizes. It does not execute supporting archives. XAPK/APKS/AAB/IPA containers are unsupported base inputs. Text parsing is bounded; tools can still encounter hostile files, so inspect untrusted APKs in an appropriately isolated environment.

Imported JSON and XML are evidence unless explicitly marked assets. DAT/BIN files default to private saves. CLI roles (`--assets`, `--saves`, `--logs`) disambiguate them. Save and log contents are excluded from portable export by default. Source packaging includes only trusted project files and the self-authored demo, never private workbench data.

Patch plans are data, not shell scripts. Operations require safe relative text paths, exact input hashes, known operation types and the exact original APK hash/version. Shell arguments sent through ADB are separately quoted because ADB joins its shell command arguments. Uploaded files cannot auto-register plugins or execute backend code in the host.

The fixture backend binds host loopback, supports only its documented progression protocol, rejects unknown actions, limits request bodies, and atomically saves progression under its configured local path. It does not proxy requests, implement arbitrary accounts or fetch missing assets.

Local signing keys/passwords stay under the private data root with restrictive file modes. Passwords reach signing tools through an environment variable rather than command arguments. Export excludes keys and passwords. Back up this identity yourself if you need future APK updates signed with the same certificate.

Portable `hashes.json` detects corruption and accidental changes; it is **not a cryptographic authenticity signature**. Treat unknown bundles as executable code. The supplied standalone exports contain only this project and its fixture.

The offline verifier changes guest firewall chains temporarily, not the host firewall. It fails rather than certify partial blocking. Abrupt termination may leave guest chains; recovery is documented in VERIFICATION.md. Multiple concurrent workbench processes sharing one private store are not supported.

This project cannot recover missing proprietary server code, authorize redistribution, or guarantee original gameplay. Evidence and testing scope accompany every claim.

