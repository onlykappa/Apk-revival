# Scripted gifts: recovered scope and remaining limits

The following bundled items are **type 8 gifts**, not ordinary villager stat
potions. Their original mailbox model is `JMGift`; their activation transport
is `game/gift/open_gift/` with `gift_id` and `villager_ids`. Ordinary village
`items` inventory is a different ownership container. This implementation never
fabricates a mailbox entry from an item ID or invents incoming social gifts.

| Item | Original role | Offline handling |
| --- | --- | --- |
| 994 Thirsty Bugs | Gift type 2, JFMosquito.lua, mini-game type 2 | Explicit non-consuming error pending validated bug session/reward contract |
| 995 Hungry Bugs | Gift type 2, JFHugBug.lua, mini-game type 3 | Explicit non-consuming error pending validated bug session/reward contract |
| 997 Kick Ball | Gift type 3, nongiftable JFSoccerBall.lua | Open an existing owned single mailbox box; original client executes soccer animation |
| 1126 Mystery Box | Gift type 3, nongiftable JFFoolsPranks.lua | Open an existing owned single box; original client chooses cosmetic bug/bird/size prank |
| 1177 Deadly Plague | Gift type 3, nongiftable April Fools JFTombstoneGift.lua | Open an existing owned single box; original script temporarily hides adults behind tombstone sprites, then restores them after 12 seconds; **no saved deaths/stat changes** |

`giftable` means sending to another player; being nongiftable does not itself
mean an already-owned local box cannot be opened. Obtaining new boxes through
social delivery is excluded. There is no new mailbox-generating policy, no
invented crafting recipe endpoint, and no consumption of unsupported items.
The original resource conversion definitions remain bundled in the APK, but a
verified conversion transport is not implemented by this module.

## Native contracts

Static original artifact evidence:

* `JMVillageClient.openGift:withVillagerIds:withCallback:` at 0xa3c928:
  `gift_id`, `villager_ids`, actual `game/gift/open_gift/` endpoint.
* Its callback at 0xa3caf4 binds the response's `game_state`.
* `JMGameState.gifts` at 0xa1eb38 is a dictionary of JMGift models, distinct
  from `items`. JMGift fields include gift_id, gift_item_id, gift_type,
  gift_count and sender metadata.
* `JFGiftService` callback at 0x84d4c4 looks for response `gift_minigame`, binds
  it to JMMiniGame and adds it to JFMiniGameCacheService.
* `JFGiftboxStateOpened` at 0x74f90c resolves original script stem + `OnOpen`.
  Its mini-game branch requires `gift_minigame.token` (0x74ff14 onward).
* Original JFMosquito/JFHugBug scripts look up that token in the mini-game
  cache. JFBugs submits signed treasure-reward requests for final-generation
  bugs, with recursively derived payout numbers. Bird-only treasure sessions
  cannot substitute for this contract: item/session identity, multiple payout
  receipts, spawn/expiry rules and original reward amounts need separate work.

The original Lua remains in the user's APK; no proprietary source or tables
are copied into this repository. Mystery Box's prank bug actors have separate
prank implementations without reward sessions; these must not be mistaken for
994/995's reward-bearing bug mini-games.

## Integration and safety

Use `scripted_items.open_gift(data, params, rules, now)` only for the recovered
`game/gift/open_gift` route. It returns `(new_save, response_envelope)`. Persist
the returned copy under the server's existing transaction before responding.
Only an existing owned single box with matching original type/script is
consumed. Duplicate opens, unknown boxes, stacks whose semantics are unknown,
modified rules and unexpected individual-villager targets fail unchanged.
The original native client then executes its script; there is no fake server
animation acknowledgment or saved villager death.

This is support for **existing mailbox boxes only**, not a claim that all gift
items can be obtained in a new offline game, that ordinary inventory use works,
or that cosmetic Lua execution was tested on the physical Deck. The focused
source tests cover classification, transactional opening, missing ownership,
non-consumption on unsupported bug sessions, retries, and unchanged villagers.
