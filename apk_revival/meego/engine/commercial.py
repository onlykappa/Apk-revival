"""Paid operator rewards reconstructed from bundled jobs; no server calls.

Call ``advance`` on the copied save BEFORE production.advance_cycles stops the
operator at expiry. Collection returns its own copy for transactional saving.
See ../COMMERCIAL_RULES.md for the explicitly local rolling policy.
"""
import copy
import hashlib
import math

from . import local_game as g, production

POLICY = 'commercial-earned-drops-v1'
STATE = 'local_commercial'


def _number(value):
    if isinstance(value, bool):
        raise g.ActionError('Invalid commercial reward accounting.')
    try:
        result = float(value)
    except (ValueError, TypeError, OverflowError):
        raise g.ActionError('Invalid commercial reward accounting.') from None
    if not math.isfinite(result) or result < 0:
        raise g.ActionError('Invalid commercial reward accounting.')
    return result


def _roll(data, source, cycle):
    uid = data.get('game_user', {}).get('user_id', 0)
    seed = f'{POLICY}:{uid}:{source["building_id"]}:{source["building_type"]}:{cycle}'
    return int.from_bytes(hashlib.sha256(seed.encode()).digest()[:8], 'big') % 1_000_000 / 1_000_000


def reward(rules, job_id, attempts, roll):
    """One categorical percentage roll using the current original attempt tier.

    Thresholds, chances and count contributions are bundled data. Choosing one
    roll per completed hour rather than the unavailable server's schedule is
    local policy. Remaining probability awards nothing, never a substitute.
    """
    tiers = rules.get('jobs', {}).get(str(job_id), {}).get('random_drop', {})
    eligible = [int(key) for key in tiers if int(key) <= attempts]
    if not eligible:
        return {}
    result = tiers[str(max(eligible))]
    total = sum(_number(entry.get('chance', 0)) for entry in result.values())
    roll *= max(100, total)
    boundary = 0
    for ident, entry in sorted(result.items(), key=lambda pair: int(pair[0])):
        chance = _number(entry.get('chance', 0))
        counts = entry.get('count_contribution', {})
        if any(_number(counts.get(stat, 0)) for stat in ('strength', 'intelligence', 'charisma')):
            raise g.ActionError('This commercial reward formula is not supported.')
        count = _number(counts.get('constant', 0))
        if count != int(count) or int(ident) <= 0 or str(ident) not in rules.get('items', {}):
            raise g.ActionError('The original commercial reward item is unavailable.')
        if boundary <= roll < boundary + chance and count:
            return {str(ident): int(count)}
        boundary += chance
    return {}


def advance(data, now, elapsed, rules):
    """Settle assigned work, then stage at most one reward for a paid cycle.

    No operator means no credit. Paid activation with an interrupted hour can
    expire but does not earn a full-hour reward. Clock/poll/restart repeats are
    bounded by the persistent cycle/last_tick/settled fields.
    """
    now, elapsed = _number(now), _number(elapsed)
    gs = data['game_state']
    for source in gs.get('buildings', {}).values():
        if not production.is_commercial(source):
            continue
        cycle = int(_number(source.get('local_production_cycle', 0)))
        if cycle <= 0 or source.get('local_production_policy') != production.POLICY:
            continue  # Legacy/free activation cannot mint a retrospective reward.
        rule = production.state_rule(source, rules)
        duration = _number(rule.get('default_length', 0))
        deadline = _number(source.get('expire_date', 0))
        if not duration or not deadline:
            continue
        job_id = int(rule.get('active_job', 0))
        record = source.get(STATE)
        if not record or record.get('cycle') != cycle:
            record = dict(cycle=cycle, worked=0, last_tick=deadline-duration, settled=False)
            source[STATE] = record
        if record.get('settled'):
            continue
        start = max(deadline-duration, now-elapsed, _number(record['last_tick']))
        stop = min(now, deadline)
        workers = [p for p in gs.get('all_villagers', {}).values()
                   if p.get('job', {}).get('source_id') == source['building_id']
                   and p['job'].get('job_id') == job_id]
        if workers:
            assigned = min(_number(p['job'].get('job_start_date', now)) for p in workers)
            record['worked'] = min(duration, _number(record['worked']) + max(0, stop-max(start, assigned)))
        record['last_tick'] = max(_number(record['last_tick']), now)
        if now < deadline:
            continue
        record['settled'] = True
        if record['worked'] + 1e-6 < duration:
            continue
        info = gs.setdefault('unlock_information', {}).setdefault('job_attempts', {})
        attempts = int(_number(info.get(str(job_id), 0)))
        awards = reward(rules, job_id, attempts, _roll(data, source, cycle))
        # A completed paid cycle advances the UI attempt tier even on a miss.
        info[str(job_id)] = attempts + 1
        inventory = source.setdefault('items', {})
        for ident, count in awards.items():
            item = inventory.setdefault(ident, dict(item_id=int(ident), count=0, layer=0, cooldown=0))
            item['count'] = int(_number(item.get('count', 0))) + count
            item['last_update'] = now


def collect(data, params, rules, now):
    """Collect native building_type_id/location once; return copied full save.

    Return new['game_state'] directly to the native route. Its `items` map is
    the complete village inventory, as required by the native delta popup.
    """
    kind = g.integer(params, 'building_type_id', low=1)
    location = g.integer(params, 'location', high=g.MAP_SIZE*g.MAP_SIZE-1)
    if kind not in production.COMMERCIAL:
        raise g.ActionError('This building has no commercial items to collect.')
    matches = [b for b in data['game_state'].get('buildings', {}).values()
               if b.get('building_type') == kind and b.get('location') == location]
    if len(matches) != 1:
        raise g.ActionError('The commercial building moved or is unavailable. Select it again.')
    source = matches[0]
    # Validate every staged item before any credit, including a corrupted save.
    for ident, item in source.get('items', {}).items():
        count = _number(item.get('count', 0))
        if str(ident) not in rules.get('items', {}) or count != int(count):
            raise g.ActionError('Invalid staged commercial item.')
    new = copy.deepcopy(data)
    source = new['game_state']['buildings'][str(source['building_id'])]
    inventory = new['game_state'].setdefault('items', {})
    for ident, staged in source.get('items', {}).items():
        item = inventory.setdefault(str(ident), dict(item_id=int(ident), count=0, layer=0, cooldown=0))
        item['count'] = int(_number(item.get('count', 0))) + int(staged['count'])
        item['last_update'] = now
    source['items'] = {}
    return new
