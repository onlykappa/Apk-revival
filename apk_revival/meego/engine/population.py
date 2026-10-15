"""Deterministic variety for future owned villagers, using the selected APK.

The APK supplies birthstone IDs/tiers and birth-eligible appearance groups, not
the former server's genetics or roll probabilities. The explicit LOCAL policy
below uses unseen-first stones, completing one tier before the next; it never
adds a stone to the collection until its carrier actually joins the village.
Newcomers start with 8..12 base stats. Children inherit the rounded mean of
their parents' base stats, with -2..2 variation and a 1..100 newborn bound.
Appearance slots have a one-half preference for valid same-gender parental
birth appearances. These formulas are restoration choices, not recovered odds.
Existing villagers, parents, jobs, ages and earned collections are untouched.
"""
import copy
import hashlib
import math

POLICY = 'local-population-variety-v1'
STATE_KEY = 'local_population'
SLOTS = ('mask', 'beak', 'eye', 'mouth', 'hair')
STATS = ('strength', 'intelligence', 'charisma')


def _roll(seed, label, size):
    return int.from_bytes(hashlib.sha256(f'{seed}:{label}'.encode()).digest(), 'big') % size


def _positive(value):
    return (isinstance(value, (int, str)) and not isinstance(value, bool)
            and str(value).isascii() and str(value).isdigit() and int(value) > 0)


def _stones(rules):
    return {int(key): record for key, record in rules.get('birthsigns', {}).items()
            if _positive(key) and isinstance(record, dict)
            and record.get('techtree_id') == int(key)
            and record.get('active', True) is True
            and record.get('tier') in (1, 2, 3)}


def _seen(data, stones):
    """Include existing carriers even before additive collection discovery runs."""
    owner = data['game_user']['user_id']
    info = data['game_state'].get('unlock_information', {})
    found = [value for values in info.get('birthsign_collections', {}).values()
             if isinstance(values, list) for value in values]
    for person in data['game_state'].get('all_villagers', {}).values():
        if person.get('user_id') == owner:
            found.extend(person.get('stats', {}).get('birthsigns', []))
    return {int(value) for value in found if _positive(value) and int(value) in stones}


def _stone(data, rules, parents, seed):
    stones = _stones(rules)
    if not stones:
        return None
    seen = _seen(data, stones)
    for tier in (1, 2, 3):
        available = sorted(key for key, record in stones.items() if record['tier'] == tier)
        unseen = [key for key in available if key not in seen]
        if unseen:
            return unseen[_roll(seed, 'stone', len(unseen))]
    # Once every original stone has been discovered, favour inheritance when
    # available; a newcomer can still carry any original active birthstone.
    inherited = sorted({int(value) for parent in parents
                        for value in parent.get('stats', {}).get('birthsigns', [])
                        if _positive(value) and int(value) in stones})
    options = inherited or sorted(stones)
    return options[_roll(seed, 'stone-inherit', len(options))]


def _appearance(person, rules, parents, seed):
    items = rules.get('items', {})
    chosen = []
    for slot in SLOTS:
        valid = sorted(int(key) for key, record in items.items()
                       if _positive(key) and isinstance(record, dict)
                       and record.get('techtree_id') == int(key)
                       and record.get('active') is True
                       and record.get('type') == 1
                       and record.get('given_on_birth') is True
                       and record.get('gender') == person['gender']
                       and record.get('collection') == slot
                       and any(r.get('layer') == 1 for r in record.get('restrictions', [])
                               if isinstance(r, dict)))
        if not valid:
            # Incomplete old prepared metadata must not create partial masks.
            return copy.deepcopy(person.get('appearance_items', []))
        inherited = sorted({item['item_id'] for parent in parents
                            for item in parent.get('appearance_items', [])
                            if isinstance(item, dict) and item.get('item_id') in valid})
        options = inherited if inherited and _roll(seed, f'{slot}-inherit', 2) == 0 else valid
        chosen.append(dict(item_id=options[_roll(seed, slot, len(options))], count=1,
                           layer=1, cooldown=0, last_update=person['last_update']))
    return chosen


def decorate_new(data, person, rules, *, parents=()):
    """Return a varied copy of a caller-created model, before inserting it.

    Caller owns the copied-save lock and persists the returned person together
    with ``data``. Repeating the same pre-insertion call reuses its assignment.
    Root-only assignment receipts make JSON restart deterministic. Never pass a
    villager already in all_villagers: this is generation, not save migration.
    Birth callers retain their chosen age/job/name; arrival callers retain their
    existing scheduling/housing checks. No collection reward is granted here.
    """
    ident = person.get('villager_id')
    if not _positive(ident) or person.get('user_id') != data['game_user']['user_id']:
        raise ValueError('Population variety requires a new owned villager.')
    people = data['game_state'].get('all_villagers', {})
    if any(str(key) == str(ident) or str(value.get('villager_id')) == str(ident)
           for key, value in people.items()):
        raise ValueError('Population variety cannot replace an existing villager.')
    result = copy.deepcopy(person)
    state = data.get(STATE_KEY, {'policy': POLICY, 'original_server_policy_verified': False,
                               'assignments': {}})
    if (not isinstance(state, dict) or state.get('policy') != POLICY
            or not isinstance(state.get('assignments'), dict)):
        raise ValueError('Unsupported local population policy.')
    receipt = state['assignments'].get(str(ident))
    if receipt is not None:
        result.update(copy.deepcopy(receipt))
        return result
    seed = f'{POLICY}:{data["game_user"]["user_id"]}:{int(ident)}'
    if type(result.get('gender')) is not int or result['gender'] not in (0, 1):
        result['gender'] = _roll(seed, 'gender', 2)
    parents = tuple(parents)
    if _stones(rules):
        for stat in STATS:
            values = [parent.get('stats', {}).get(stat) for parent in parents]
            values = [value for value in values if isinstance(value, (int, float))
                      and not isinstance(value, bool) and math.isfinite(value) and value > 0]
            base = math.floor(sum(values) / len(values) + 0.5) if values else 10
            result['stats'][stat] = max(1, min(100, base + _roll(seed, stat, 5) - 2))
        result['stats']['birthsigns'] = [_stone(data, rules, parents, seed)]
    result['appearance_items'] = _appearance(result, rules, parents, seed)
    receipt = {key: copy.deepcopy(result[key]) for key in ('gender', 'stats', 'appearance_items')}
    state['assignments'][str(ident)] = receipt
    data[STATE_KEY] = state
    return result
