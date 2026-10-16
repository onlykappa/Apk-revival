# Meego birthstone metadata and discovery repair — 2026-10-14

Scope: read-only inspection of the selected original APK, prepared private
starter/rules, current save's collection fields and retained original native
library. Existing LLVM ARM disassembly was reused. No Android launch, production
save write, APK change, asset publication or original-server parity claim.

## Original records and assets

The original `assets/TechTree.plist` version is **2.94**. It contains **35**
active birthsign records: **20 Common, 10 Uncommon, 5 Rare**. Each includes an
ID, tier, name, description and image path. Rabbit is ID **4** and has its
original complete text and `birthstone_rabbit@2x.png`. All 35 referenced image
files are present in the selected original APK. Records/images were not copied
into repository source or release assets.

The earlier four-section private extraction omits the birthsign section. Its
starter login packet sends `techtree: {}` and `techtree_version: 2.94`. Current
`birthsign_collections` is empty even though all four owned villagers observed
at this audit carry birthsign ID 1. These are backend omissions; they do not
prove the native loaded catalog was empty, since the native client normally
loads the bundled full table from disk.

## Native response and display contract

`JFUIBirthstoneDataSource.init` (`0x94add8`) reads
`JMTechTree.instance.birthsigns.allValues`. It groups records by tiers 1, 2 and
3 and reads `JMGameState.unlock_information.birthsign_collections` using
stringified tier keys. Each value is converted to a set; membership checks use
numeric `techtree_id` values (`0x94b3dc–0x94b428`). Thus discovered state uses
`{"1": [numeric_common_ids], "2": [numeric_uncommon_ids], "3": [numeric_rare_ids]}`.
Each discovered row displays the original birthstone image; undiscovered rows
use the shipped missing-stone placeholder (`0x94ab88`).

`JFUIBirthstoneItem.displayDetails` (`0x94acb8`) pushes a popup for its current
birthsign. `JFUIBirthsignDetailPopup.initWithBirthsign` (`0x712590`) reads that
model's name, description and texture directly (`0x71261c`, `0x712668`,
`0x71269c`). There is no separate detail endpoint in this path. Therefore a
blank Rabbit detail requires checking the native model/display; adding a
fabricated detail API would not repair this path.

`JMTechTree.shouldUpdate` (`0xa01a70`) accepts only a strictly newer version.
Another version-2.94 payload would be ignored. `patchWithUpdate:toVersion`
(`0xa01ad0`) merges the incoming dictionary into the retained patch and then
the original bundled tree (`0xa01c18`, `0xa01c2c`) before model binding.
`mergeTechTree:withUpgrade` includes the `birthsigns` key (`0xa019b8`);
`updateDictionary:withUpgrade:withKey` enumerates incoming dictionary keys.
The versioned partial patch therefore preserves the original other catalogs.

Private annotated disassembly is retained in
`private-analysis/meego/birthstones-*-annotated.txt`, outside releases. Original
APK SHA-256: `030613cbc63bd03786545999c3590456a264796866127898928a4d59988d29a2`.
Original native-library SHA-256:
`6b1000dccb517635a51656dd0439f49052a361b9a2a905b3e21453c481b3dcf3`.
Disassembly annotations are heuristic; the assertions above also follow the
explicit native dictionary/call/branch sequences.

## Small correction and integration

`engine/birthstones.py` reads the original table once from the already selected
user APK. `populate_packet` supplies its 35 original records as the birthsign
section and local metadata revision **2.9401** for login/resume. Existing
private prepared-file hashes, original APKs, Android installation and game
saves do not need replacement or re-signing.

`discover_owned` additively records only stones carried by the owner's current
villagers, grouped by their original tier. It ensures the three expected array
fields exist, normalizes prior numeric strings, retains earlier discoveries
when a villager dies/leaves, excludes guests, and preserves unrelated fields.
It does not grant all 35 stones or change villagers' birthsigns/stats. The
observed village receives only `{"1": [1], "2": [], "3": []}`.

Call collection discovery on the cloned save at startup and during normal
advance before persisting. Future births/arrivals carrying different valid
stones then appear once, and discoveries survive restart. Newcomer/birthstone
distribution and collection reward formulas are separate, unrecovered server
mechanics and are not invented by this metadata repair.

## Verification actually performed

`APKR_MEEGO_APK=<selected original> python3 -m unittest discover -s tests
-p test_meego_birthstones.py -v`: **9 tests passed**, zero failures/skips,
**0.142 seconds**. The actual original-APK test verifies all 35 records, every
referenced image, Rabbit name/description/image and tier counts. Other tests
cover read-only loading, preserved packet sections, the newer-version gate,
owned discovery versus guests, new-child discovery, JSON restart, historical
retention, duplicate/string IDs and missing metadata errors.

These are source/helper and original-file checks. A native visual check of the
Birthstones menu and Rabbit popup after login refresh is still required before
claiming the reported blank screen is resolved.

## Villager card follow-up — 0.3.27 / 2026-10-16

The earlier metadata and collections fix did not address IDs used by individual
villager cards. Read-only live Nooni has sign11 (OWL); no owned villager in that
snapshot has Rabbit/sign4. The default Rabbit visual is not authoritative for
saved genetics. Original name/description/image records are complete.

JFUIVillagerDetailMenu.setBirthstoneDisplay0x759a84 uses objectForKey: to index
the string-keyed birthsign table with elements taken directly from the raw
stats.birthsigns array (calls0x759bd4/0x759c10). onBirthstoneOne0x75e8a8 does the
same at0x75e974, passing the result to menuWithBirthsign:. Travel character
onBirthstoneOne0x80b4f8 follows the same contract. Native stats model declares
NSArray birthsigns with no per-element conversion. Numeric JSON IDs become
NSNumber; dictionary keys from JSON are NSString. Equal numeric value does not
make those objects equal keys. Nil model leaves default imagery and blank text.

Project only villager stats.birthsigns integer values to decimal strings at
Handler.reply/native_payload. Keep persistent genetics/IDs untouched; keep
unlock_information.birthsign_collections numeric because its native membership
contract is different. This also avoids a native patch/re-sign or Android reset.
Original ELF hash and offline-analysis caveats above still apply. Automated tests
resolve every original card through actual JSON serialization and the same
string-key dictionary lookup; they do not execute the Objective-C renderer.
Visual acceptance after a clean launch remains necessary.
