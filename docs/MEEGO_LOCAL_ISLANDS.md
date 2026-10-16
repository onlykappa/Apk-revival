# Three offline Launch Dock islands — 0.3.25 pilot

Pebble Bay (stone), Timber Cove (wood) and Berry Haven (food) are local NPC
islands. No cloud model, accounts, internet or former server is used. Layouts,
names, rewards and charisma gains are authored restoration policies. This is
not a claim that original server travel has been fully recovered or reproduced.

Use the original Launch Dock Send menu to choose a local neighbour. Drag an
available adult onto the Dock first. The Dock menu requires the login config
questing_villager_limit keyed by questing_level;0.3.26 derives4/8/12/16 from
the original completed building states, repairing old empty prepared seeds
without editing private configuration or APKs. Restart the game after updating
to clear the previously cached0/0 limit. A completed
Launch Dock is required; available living adults can travel. The original
character-send screen requests7200 seconds (two hours). Backend accepts60–86400
seconds for supported callers; the pilot preserves the screen's original timer.
Each island permits three simultaneous guests. Dock capacity uses the original
quest_villagers value (4/8/12/16 at the completed upgrade levels).

The home save retains the owned villager, birthday, deathday, equipment, base
stats and housing reservation. Native travellers have location_type0 and a
foreign location_id; this differs from dungeon travellers (location_type1).
Home work, breeding, item activation and food use exclude absent travellers.
The remote screen receives a separate profile/game_state packet named remote;
unknown village identities fail instead of accidentally showing the home save.
Remote NPCs use stable separate IDs; no player inventory is cloned into them.

After the deadline, ordinary polling or next launch returns the traveller home
with native post-quest job8. Collect at the Launch Dock to settle the saved
reward. A new job cannot discard an uncollected reward. Current local reward is
five destination resources per started trip-minute, maximum100, limited to free
home storage space; the displayed receipt reports the amount actually credited.
No skulls, premium currency, random drops or Facebook bonus are invented.
Each newly collected trip grants+1 CHR using the existing1799 positive stat cap.
A claimed trip stores its receipt; retrying the same collection cannot grant it
again. Current receipts are bounded to one per villager, replaced only by a new
explicit trip. The original protocol identifies rewards by villager IDs, not an
immutable request token; it cannot distinguish an arbitrarily delayed old claim
from a later ready trip for that same villager. Normal retries within the same
trip are covered. No old home-state snapshots are replayed.

Moving the Launch Dock updates active trip references along with worker jobs.
Missing villagers fail rather than being recreated. Very late return does not
resurrect a villager: pending reward is retained and death is applied on claim.
Leaving the game preserves deadlines and receipts; closing food still freezes
under the existing food policy. No island reset, APK rewrite or save migration
is required to enable this feature. The new state is created on first departure.

## Native evidence and limits

Original user-owned libverde.so SHA256:
6b1000dccb517635a51656dd0439f49052a361b9a2a905b3e21453c481b3dcf3.
REA provider access was already unavailable in this session; existing offline
ELF Objective-C metadata and focused ARM instruction inspection were reused.
No new REA runtime execution or retained provider Evidence ID is claimed.

- JMVillageClient.getNeighbourList:0xa39774 binds an array keyed by user_id.
- sendVillager:toUser:withDuration:withResourceBonus:0xa38efc sends villager_id,
  to_user_id, duration, give_resource_bonus; completion binds the local state.
- getVillage:0xa3ad6c / getRemoteVillage:0xa3ae74 send village_id.
- JFVillageService remote success block0x8f93a0 reads profile and game_state,
  creates JMGameState.remoteInstanceWithData:withUserId:, then sets viewed state.
- JMVillager.isTravelling0xa51c84 tests foreign location_id with location_type0.
- JMVillageClient.updateVillagerQuest:0xa3a328 sends villager_id and binds home.
- completeQuest:0xa39400 sends reward_villager_ids; callback reads game_state.
  JFVillageService collection callback0x8fa200 reads quest_results keyed by
  villager ID and uses the original JMQuestResult reward panel.
- JFUICharacterQuestMenu.onSend0x80a1a4 loads7200 as the duration argument at
  0x80a498–0x80a4a0. Original completed Dock states use job7 and quest_villagers;
  original post-quest job8 has type9, as used by native collection selection.

Remote views are read-only local demonstrations. Social gifting, real players,
chat, friends, visits from bots, NPC economy simulation and additional islands
are not implemented by this pilot. No launcher redesign or new native controls.
Physical Deck menu/rendering/Send acceptance remains to be tested before calling
this native travel flow verified. Automated fixed-clock tests cover completion;
they do not constitute a two-hour real-time hardware trial.
