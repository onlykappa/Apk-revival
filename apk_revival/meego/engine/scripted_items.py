"""Open existing owned cosmetic gift boxes using the recovered native route.

No mailbox generation, social transport, inventory-to-gift conversion or server
stat effect is invented. Native JFGiftboxStateOpened executes the original Lua
on successful response; scripts and client assets remain in the user's APK.
"""
import copy
import json

from . import local_game as g

# These original type-8/gift-type-3 scripts are client-only animations.
COSMETIC_GIFTS = {
    997: 'JFSoccerBall.lua',
    1126: 'JFFoolsPranks.lua',
    1177: 'JFTombstoneGift.lua',
}
BUG_GIFTS = {994: 2, 995: 3}


def _no_villager_targets(params):
    raw = params.get('villager_ids', ['[]'])
    if isinstance(raw, list):
        if len(raw) != 1:
            raise g.ActionError('Invalid scripted gift targets.')
        raw = raw[0]
    try:
        value = json.loads(raw) if isinstance(raw, str) else raw
    except (ValueError, TypeError):
        raise g.ActionError('Invalid scripted gift targets.') from None
    if value != []:
        raise g.ActionError('This cosmetic gift does not change individual Meego.')


def open_gift(data, params, rules, now):
    """Return (copied save, native envelope), consuming one existing gift box.

    Integrate only at ``game/gift/open_gift``. Do not treat an arbitrary item ID
    as an owned gift_id: native JMGift ownership lives in game_state.gifts.
    Unknown, missing, depleted, stacked, mismatched and bug gifts fail before
    consumption. A repeated open of an already removed box fails without changes.
    """
    ident = g.integer(params, 'gift_id', low=1)
    gift = data['game_state'].get('gifts', {}).get(str(ident))
    if not isinstance(gift, dict) or gift.get('gift_id') != ident:
        raise g.ActionError('That owned gift box is unavailable or was already opened.')
    item_id = g.integer(gift, 'gift_item_id', low=1)
    if item_id in BUG_GIFTS:
        raise g.ActionError('Bug gifts need an original type-2/3 mini-game session; this gift was not consumed.')
    script = COSMETIC_GIFTS.get(item_id)
    rule = rules.get('items', {}).get(str(item_id), {})
    if (script is None or rule.get('type') != 8 or rule.get('gift_type') != 3
            or rule.get('script') != script or gift.get('gift_type') != 3):
        raise g.ActionError('This scripted gift is not supported offline; it was not consumed.')
    if type(gift.get('gift_count')) is not int or gift['gift_count'] != 1:
        raise g.ActionError('This gift quantity cannot be opened safely; it was not consumed.')
    _no_villager_targets(params)
    # The script owns the transient visual effect. In particular, the April
    # Fools tombstone script never changes birthdays, deathdays, jobs or saves.
    new = copy.deepcopy(data)
    del new['game_state']['gifts'][str(ident)]
    return new, {'game_state': copy.deepcopy(new['game_state'])}
