"""Explicit LOCAL loot balance, using only original themed item identities.

The client preserves items and their descriptions, not the discontinued server's
drop table. These weights and work requirement are restoration choices. Native
results accept one item-ID/count mapping per participant; no premium currency
or random client-supplied item is accepted.
"""
import hashlib

POLICY = 'local-earned-themed-loot-v1'
MINIMUM_WORK_SECONDS = 60
# Membership inferred from original Turtle/ice imagery and descriptions. The
# weights below are LOCAL, never attributed to original server rarity.
POOLS = {
    3: ((1185, 25), (1186, 20), (1187, 35), (1188, 5),
        (1505, 2), (1506, 2), (1507, 4), (1508, 4), (1509, 3)),
    2: ((1510, 35), (1511, 30), (1512, 25), (1513, 3), (1514, 4), (1515, 3)),
}


def reward(data, session, ident, record, rules):
    """One deterministic earned item for a new-policy completed session.

    Pure selection; the caller credits inventory and saves its immutable claim
    receipt atomically. Existing pre-policy sessions never gain retroactive loot.
    """
    if (session.get('loot_policy') != POLICY
            or float(record.get('time_worked', 0)) < MINIMUM_WORK_SECONDS
            or int(record.get('job_activations', 0)) < 1
            or int(record.get('gold_count', 0)) <= 0):
        return {}
    pool = POOLS.get(session['type_id'], ())
    catalog = rules.get('items', {})
    # Partial/synthetic rule sets must not produce an unknown item identity.
    if not pool or any(not catalog.get(str(item), {}).get('active') for item, _ in pool):
        return {}
    seed = f'{POLICY}:{data["game_user"]["user_id"]}:{session["id"]}:{ident}'
    roll = int.from_bytes(hashlib.sha256(seed.encode()).digest()[:8], 'big') % sum(weight for _, weight in pool)
    for item_id, weight in pool:
        if roll < weight:
            limit = int(catalog[str(item_id)].get('max_count', 0))
            owned = int(data['game_state'].get('items', {}).get(str(item_id), {}).get('count', 0))
            owned += sum(int(p.get('items', {}).get(str(item_id), {}).get('count', 0))
                         for p in data['game_state'].get('all_villagers', {}).values())
            # A full owned cap does not reroll into a different/free reward.
            return {} if limit and owned >= limit else {str(item_id): 1}
        roll -= weight
    return {}
