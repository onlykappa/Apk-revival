# Offline bird and egg treasure rules

This enables the original Meego 1.32 bird/egg mini-game code through the local
service. It restores the native transport and introduces a conservative **local
reward policy**. It is not a recovered copy of the discontinued server economy.
No online leaderboard, other-player visit or purchasing service is involved.

## Recovered original contracts

The privately owned original APK has SHA-256
`030613cbc63bd03786545999c3590456a264796866127898928a4d59988d29a2`;
`libverde.so` has SHA-256
`6b1000dccb517635a51656dd0439f49052a361b9a2a905b3e21453c481b3dcf3`.
Static ARM instructions and Objective-C metadata establish:

- `JMVillageClient.getTreasureMiniGame:minigameType:` at `0xa3b7a8` calls
  `game/village/get_treasure_mini_game`. The response is a direct `JMMiniGame`,
  not a game-state wrapper.
- `JFGrakBirdService` requests type 1 and requires `new_session == 1`, a nonzero
  level and enough expiry time to run the selected details. Original packaged
  `client_data/8/mini_game_details_1` specifies 60 seconds idle, 30 seconds play,
  60 seconds reward. Level 1 uses the original speed 140.
- The egg-touched method at `0x684ae8` submits its egg level as `payout_number`.
  The reward request at `0xa3b8f8` sends a `data` dictionary with exactly
  `payout_number`, `token`, `minigame_type`, plus `signature`, to
  `game/village/retrieve_treasure_mini_game_reward`.
- `JMMiniGame.getSignature:` at `0x8b6364` serializes the dictionary through
  `JSONRepresentation`, calls `hmacForKeyAndData:withData:` using the session
  token as key, and base64-encodes the result.
- That HMAC method's implementation is `0x95a3c0`. It calls
  `cStringUsingEncoding:1` for key and data (ASCII), obtains their string
  lengths, passes algorithm **2** to `CCHmac` at `0x95a47c`, and returns exactly
  **32 bytes** at `0x95a49c`: HMAC-SHA256. This is recovered signature validation,
  not an ignored signature field.
- The native reward callback binds `response.game_state`; the egg animation
  separately reads `points_reward` and the `item_rewards` item-ID/count map.

The original JSON writer's dictionary iteration order is not established.
Validation tries only the six compact JSON orders of the three exact expected
ASCII scalar keys. Every candidate must match the submitted base64 SHA256 HMAC
with a constant-time comparison. Missing/invalid signatures, duplicate JSON
keys, extra keys, non-integer numeric fields and invalid tokens are rejected.
A different native whitespace convention would fail closed; actual-device
compatibility was observed in the Deck review: valid signatures and egg
numbers 1–4 arrived; later eggs were incorrectly rejected by the earlier
single-reward policy. Per-egg receipts correct that observed mismatch.

## Explicit local policy

The original server's eligibility cadence, payout schedule, allowed egg count
and item rewards are unavailable in the APK. They must not be described as
recovered original behavior. This implementation uses these bounded rules:

- The first poll records the next opportunity one hour later and awards nothing.
- The next eligible poll issues one cryptographically random 48-character hex
  session token, with the requested original mini-game variant (1–11) and
  level 1. Its own bundled timing definition must be present and compatible. The session lasts 155 seconds: the original total
  150 seconds plus five seconds for callback/clock skew.
- Polls/restarts during that session preserve the token and do not re-trigger
  the animation. The opportunity timer persists with the session. A long
  offline interval offers one session, never a backlog of free sessions.
- A correctly signed, unexpired reward request earns **one crystal skull** and
  no item, once for each distinct egg number in the session. The submitted
  egg number is bounded to 0–5 and is an identifier, not a reward amount. This
  local policy caps a session at six skulls, without granting missed eggs.
- The exact same signed request retried before expiry returns zero additional
  reward. Different collected egg numbers can earn their own single reward.
  Legacy single-egg receipts are retained during migration. Old tokens, expired
  tokens and requests before session start are rejected.
- The helpers return copies of state and the matching native response; the
  server must atomically persist the copy under its existing state lock before
  returning it. No global balance is changed on polling or before collection.

The HMAC key is sent to the local client, as in the original protocol. It
protects transport consistency and identifies a session; it cannot prove that a
person physically tapped a bird. This is a loopback offline game, not an online
anti-cheat system. No discarded server secret or online authority is claimed.

## Validation

`apk_revival/meego/regression_tests/test_meego_treasure.py` uses synthetic game states and clocks. Fifteen
checks passed with the original APK supplied read-only, covering original timing,
direct native response fields, all six signed key orders, invalid/tampered
requests, expiry boundaries, bounded payouts, restart persistence, retry
idempotence, stale tokens and no offline catch-up. No installed app, save or
runtime was changed. Original animation and physical-device compatibility still
need a later device test; automated backend tests do not establish them.

### Deck follow-up

Variant 4 is requested by the actual native client. Original variants 1–11
use separate bundled detail records with matching duration contracts; the
responder now validates the requested record and binds claims to that same
variant and token. A variant cannot claim another variant's session. The
cadence and skull payouts above remain local policy, not recovered balances.
