# Remaining solo mini-game and adventure contracts

This is a bounded, read-only static investigation of the user's original
Meego 1.32 APK and the current local service. No game launches, APK installs,
live save mutations, provider setup, or speculative reward implementations
were performed. It supplements the island-core audit; it does not establish
complete game parity.

Original APK SHA-256:
`030613cbc63bd03786545999c3590456a264796866127898928a4d59988d29a2`.
Original `libverde.so` SHA-256:
`6b1000dccb517635a51656dd0439f49052a361b9a2a905b3e21453c481b3dcf3`.
Addresses below are native ARM virtual addresses/file offsets in that library.
Method identities were read from its Objective-C metadata; instructions were
decoded with the already available LLVM library. This describes shipped code,
not observed execution. Raw disassembly remains in the private analysis tree.

## Treasure mini-game: existing play code, suppressed by the local stub

The original client already implements the Grak bird, tapping, egg drop,
egg collection and reward animation. Its local server currently replies to
`game/village/get_treasure_mini_game` with `new_session=False` and a deferred
token. This is deliberate non-implementation, rather than missing game art or
a need to write a replacement mini-game UI.

Recovered request and callback sequence:

1. `JMVillageClient.getTreasureMiniGame:minigameType:` (`0xa3b7a8`)
   sends `game/village/get_treasure_mini_game/`, with `minigame_type`.
   The actual request call is `0xa3b8a8`. A model callback binds the direct
   response as `JMMiniGame`, whose fields include `new_session`, `token`,
   `minigame_type`, `level`, `start_date`, `next_poll_date`, `expire_date`
   and `last_update`.
2. `JFGrakBirdService.performMiniGamePoll` requests type 1 (`0x96b770`).
   Its success callback checks `new_session == 1` (`0x96b8cc`), type 1
   (`0x96b8ec`), nonzero level (`0x96b90c`) and sufficient remaining expiry
   time against the selected details' total duration (`0x96b944`–`0x96b9a0`).
   It then calls `startMiniGame:` (`0x96b9c0`) and updates the next poll date.
   The current false flag prevents entering this original native play path.
3. `JFGrakBirdService.startMiniGame:` (`0x96bb68`) instantiates
   `JFGrakBird.initWithMiniGame:` (`0x96bd24`–`0x96bd28`).
   `JFGrakBirdTap.onEnter:withMessage:` (`0x8dedec`) reads mini-game level
   details and runs the original egg-drop animation (`0x8df0c4`).
4. `JFGrakEggStateTouched.onEnter:withMessage:` (`0x684ae8`) reads the
   egg's `level` (`0x684ce4`) and passes it to the reward request as
   `payout_number` (`0x684d24`–`0x684d38`). This number is an index supplied
   by the client, **not a recovered skull amount**.
5. `getRetrieveTreasureMiniGameReward:withMiniGame:withCallback:`
   (`0xa3b8f8`) builds a payload with `payout_number`, `token` and
   `minigame_type` (`0xa3b9cc`–`0xa3b9f8`). It sends an envelope containing
   `data` and `signature` to
   `game/village/retrieve_treasure_mini_game_reward/` (`0xa3bb18`).
   Exact HTTP parameter encoding was not traced in this pass.
6. `JMMiniGame.getSignature:` (`0x8b6364`) serializes the data with
   `JSONRepresentation`, calls `hmacForKeyAndData:withData:` using the
   mini-game token property, then base64-encodes the result. The token ivar
   reference resolves to `OBJC_IVAR_$_JMMiniGame.token` at `0xcf17ec`.
   HMAC digest choice and JSON canonicalization remain to be verified before
   implementing signature validation; no security checks were disabled.
7. The reward callback chain reads response `game_state` (`0xa3bbd0`) and
   binds it into the native local game state (`0xa3bc24`).
   `JFGrakEggStateTouched.deliverReward:` (`0x684ed4`) additionally reads
   `points_reward` (`0x684f3c`) and `item_rewards` (`0x68504c`) to animate
   what was earned. `item_rewards` is enumerated as an item-ID/count mapping
   (`0x685088`–`0x685158`). A real implementation must atomically persist the
   matching balances/inventory and return both the full game state and the
   matching display reward, with replay protection for each allowed payout.

The retained `client_data/8` has 11 mini-game detail records, containing
30-second game, 60-second idle and 60-second reward durations, colours and
level speeds. `JMMiniGame.details` tries a type/level-specific details key and
then a type-only fallback. These records do not specify reward amounts,
eligibility cadence, payout multiplicity or the authoritative reward schedule.
The service path traced here specifically selects type 1; the presence of
other details does not prove every variant was available to this client.

**Remaining blockers:** recover the payout schedule and allowed payout count
per session, eligibility/poll policy, signature digest/encoding and restart
semantics. Enabling `new_session=True` with empty or guessed rewards would
produce an incomplete mini-game and is not an honest restoration. No such
change was made.

## Solo-adaptable adventures: routes are present, complete contracts are not

The original client can display and run adventure sessions. Retained dungeon
rules describe active Ice Bear Cave (type 2, two stages) and Turtle's Grotto
(type 3, one stage), plus an inactive older Turtle definition. There are four
stage records in total. These include maps, session classes, durations,
participant limits, entry costs and time-worked progress breakpoints.

Recovered `JMVillageClient` dungeon calls include:

| Native method | Address | Request route |
| --- | --- | --- |
| `startDungeonWithTypeId:villagerId:withCallback:` | `0xa3cfd0` | `game/dungeon/start_dungeon/` (`0xa3d21c`) |
| `getActiveDungeonWithCallback:` | `0xa3d410` | `game/dungeon/get_active_dungeon/` (`0xa3d4d0`) |
| `getDungeonById:withCallback:` | `0xa3d61c` | `game/dungeon/get_dungeon/` (`0xa3d744`) |
| `sendVillager:toDungeon:withCallback:` | `0xa3d798` | `game/dungeon/send_villager_to_dungeon/` (`0xa3d93c`) |
| `completeDungeonQuest:withCallback:` | `0xa3de2c` | `game/dungeon/complete_dungeon_quest/` (`0xa3df74`) |
| `getDungeons:` | `0xa3dfd8` | `game/dungeon/get_dungeons_list/` (`0xa3e094`) |

The start callback reads `user_dungeon` (`0xa3d2d0`) and `game_state`
(`0xa3d338`). Other callback/model identities establish additional required
data, but do not constitute a complete usable packet schema:

- `JMDungeonPacket` has `user_dungeon` and `dungeon_game_state`.
- `JMDungeonResultsPacket` has `game_state`, `dungeon_results`, `user_dungeon`
  and typed `dungeon_summary` entries.
- `JMDungeonQuestResult` has `resources`, `bonus_resources`, `items`, `points`
  and `additional_bonus_rewards_key`.
- `JMDungeonVillagerSummary` includes participant identity, time worked,
  activations, gold and quest results.

The local engine does not implement these adventure sessions or their save,
rating, resource accounting and payout lifecycle. Original commercial
buildings' `quest_rewards` tables belong to their own drops; they are **not**
evidence of dungeon rewards and must not be repurposed as those rewards.
Offline single-player adaptation could reuse the native adventure UI, but
still needs a complete local session model and verified response shapes.
Original multiplayer, chat, tribes and other players remain excluded.

The separate village quest client sends `game/village/get_quests/`
(`0xa3aa54`) and `game/village/attempt_quest/` (`0xa3ac08`). The original
TechTree has no generic `quests` or task-instance table, and the local service
returns empty lists. A concrete quest/objective catalogue and original
completion/reward rules have not been recovered by this work.

## Scope and next implementation step

Bundled files being preserved establishes content preservation, not complete
offline gameplay. Treasure, solo-adapted adventures and original server-fed
quest/task catalogues remain additional gaps beyond island collection,
production, tools, breeding and achievements. Restoring the latter systems
does not close these separate gaps.

The next bounded Treasure task is to finish the signature helper analysis and
recover an authoritative reward/session rule source. If no original reward
schedule can be recovered, any playable replacement needs an explicitly
labelled local balancing policy; it cannot be presented as the original full
game. No skull payouts should be invented silently to make a test pass.

Private supporting files: `treasure-contract-annotated.txt` and
`solo-contract-annotated.txt` under `private-analysis/meego/`. No native code,
proprietary assets or private tokens are included in this public audit note.
