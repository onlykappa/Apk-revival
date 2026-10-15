"""Earned offline objectives from the original APK, without fabricated payouts.

The APK contains achievement captions/thresholds and production transition
unlocks, but no achievement/tutorial payout amounts. Completing an objective
therefore unlocks its original achievement, never grants arbitrary skulls/XP.

Local policies (not recovered original server formulas): elapsed village age
stands in for "Time Played"; a production use is counted per building instance;
the affluence meter brackets the sum using completed-temple affluence milestones.
Temple level and all purchase/research unlock rules remain independent of that
meter. Social, event, moderator, tourism and tribe objectives are excluded.
"""
import math
import re

STATE_KEY = 'local_progression'
PRODUCTION_TYPES = (10, 13, 16)
COLLECTION_ACHIEVEMENTS = {'1': '160', '2': '173', '3': '174'}


def _integer(value, default=0):
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (ValueError, TypeError, OverflowError):
        return default


def _state(data):
    state = data.setdefault(STATE_KEY, {})
    if not isinstance(state, dict):
        raise ValueError('Saved local progression must be a dictionary.')
    state.setdefault('birth_events', {})
    state.setdefault('production', {})
    if not isinstance(state['birth_events'], dict) or not isinstance(state['production'], dict):
        raise ValueError('Saved local progression counters must be dictionaries.')
    return state


def _award(data, ident, level, now, rules):
    """Monotonic native achievement update; preserve unknown/legacy fields."""
    rule = rules.get('achievements', {}).get(str(ident), {})
    if not rule.get('active'):
        return False
    level = min(_integer(level), _integer(rule.get('max_level')))
    if level <= 0:
        return False
    achievements = data['game_state'].setdefault('achievements', {})
    old = achievements.get(str(ident), {})
    if _integer(old.get('level')) >= level:
        return False
    record = dict(old)
    record.update(achievement_id=int(ident), level=level, last_updated=now)
    achievements[str(ident)] = record
    return True


def _description_level(rule, amount, *, detail=False):
    """Read explicit leading numbers only from reviewed numeric objectives."""
    source = rule.get('level_client_data' if detail else 'level_descriptions', {})
    result = 0
    for key, value in source.items():
        level = _integer(key)
        if not 0 < level <= _integer(rule.get('max_level')):
            continue
        text = value.get('detail_description', '') if detail and isinstance(value, dict) else value
        if not isinstance(text, str):
            continue
        match = re.fullmatch(r'(?:Played\s+)?(\d+)\s+.+', text.strip())
        if match and amount >= int(match.group(1)):
            result = max(result, level)
    return result


def record_birth(data, event_id):
    """Record a successful breeding token once, before its retry cache expires.

    The caller must invoke this only after validating and creating the child.
    Counting historical completed tokens recovers known births on migration;
    older already-evicted births cannot be reconstructed from current people.
    """
    if not isinstance(event_id, str) or not event_id or len(event_id) > 200:
        raise ValueError('A completed birth needs its stable event identifier.')
    events = _state(data)['birth_events']
    if event_id in events:
        return False
    events[event_id] = True
    return True


def record_production_cycle(data, building_type, building_id, event_id, now, rules):
    """Count one accepted production start, never a poll or retry.

    Call after its cost/transition succeeds, passing the persisted cycle ID.
    Original unlocks occur at 9/18 uses. Counts stop at the last bundled unlock;
    this bounds saved bookkeeping and prevents unlimited event history growth.
    """
    kind = _integer(building_type)
    if kind not in PRODUCTION_TYPES:
        return False
    if not isinstance(event_id, str) or not event_id or len(event_id) > 200:
        raise ValueError('A production cycle needs its stable event identifier.')
    transitions = rules.get('buildings', {}).get(str(kind), {}).get(
        'state_data', {}).get('1', {}).get('transition_achievements', {})
    thresholds = {int(key): value for key, value in transitions.items()
                  if str(key).isdigit() and int(key) > 0 and isinstance(value, dict)}
    if not thresholds:
        return False
    key = f'{kind}:{building_id}'
    production = _state(data)['production'].setdefault(key, {'count': 0, 'events': []})
    if event_id in production['events'] or production['count'] >= max(thresholds):
        return False
    production['events'].append(event_id)
    production['count'] += 1
    for threshold, achievement in sorted(thresholds.items()):
        if production['count'] >= threshold:
            _award(data, achievement.get('achievement_id'),
                   achievement.get('achievement_level'), now, rules)
    return True


def _tutorial_rules(rules):
    result = {}
    for key, record in rules.get('client_data', {}).get('1', {}).items():
        if key.startswith('tutorial_task_') and isinstance(record, dict) and 'task_id' in record:
            result[key.removeprefix('tutorial_task_')] = record
    return result


def complete_tutorial_task(data, task, rules):
    """Acknowledge a bundled task name/numeric ID once, with no unknown reward."""
    if not isinstance(task, str) or len(task) > 100:
        raise ValueError('Invalid tutorial task.')
    task = task.removeprefix('tutorial_task_')
    records = _tutorial_rules(rules)
    canonical = next((name for name, rule in records.items()
                      if task in (name, str(rule['task_id']))), None)
    if canonical is None:
        raise ValueError('This tutorial task is not in the original game rules.')
    tasks = data.setdefault('local_tutorial_tasks', [])
    # Preserve the earlier local ID encoding and arbitrary existing fields.
    aliases = (canonical, str(records[canonical]['task_id']), records[canonical]['task_id'])
    if any(value in tasks for value in aliases):
        return False
    tasks.append(canonical)
    return True


def affluence_bounds(affluence, rules):
    """Stable local UI milestones; not an invented original XP/level formula."""
    states = rules.get('buildings', {}).get('1', {}).get('state_data', {})
    milestones = sorted({_integer(state['affluence']) for state in states.values()
                         if isinstance(state, dict) and 'affluence' in state
                         and state.get('temple_level') and not state.get('buildable')
                         and _integer(state['affluence']) >= 0})
    if len(milestones) < 2:
        return None
    value = max(0, _integer(affluence))
    current = milestones[0]
    for milestone in milestones[1:]:
        if value < milestone:
            return current, milestone
        current = milestone
    # Keep the native meter's denominator positive above the final milestone.
    # Continuing the last interval here is explicitly a local display policy.
    step = max(1, milestones[-1] - milestones[-2])
    current += ((value - current) // step) * step
    return current, current + step


def synchronize(data, now, rules):
    """Update recovered solo objectives; returns whether the save changed.

    The caller should run this after simulation/birth/production completion and
    during save migration, then persist atomically with the rest of that action.
    Existing achievement levels, unrelated fields, currency and items survive.
    """
    if not rules.get('achievements'):
        return False
    metadata = data.get(STATE_KEY, {})
    changed = (STATE_KEY not in data or not isinstance(metadata, dict)
               or 'birth_events' not in metadata or 'production' not in metadata)
    state = data['game_state']
    for event in data.get('completed_births', {}):
        changed = record_birth(data, event) or changed
    births = len(_state(data)['birth_events'])
    achievement_rules = rules['achievements']
    changed = _award(data, '105', _description_level(
        achievement_rules.get('105', {}), births, detail=True), now, rules) or changed
    collections = state.get('unlock_information', {}).get('birthsign_collections', {})
    for tier, ident in COLLECTION_ACHIEVEMENTS.items():
        valid = {str(value) for value in collections.get(tier, [])
                 if not isinstance(value, bool) and str(value).isdigit()
                 and rules.get('birthsigns', {}).get(str(value), {}).get('tier') == int(tier)}
        changed = _award(data, ident, _description_level(
            achievement_rules.get(ident, {}), len(valid), detail=True), now, rules) or changed
    created = data.get('created_at')
    if isinstance(created, (int, float)) and not isinstance(created, bool) and math.isfinite(created):
        days = max(0, now - created) / 86400
        for ident, amount in [('107', days), ('338', days / 365)]:
            changed = _award(data, ident, _description_level(
                achievement_rules.get(ident, {}), amount, detail=True), now, rules) or changed
    bounds = affluence_bounds(state.get('village_information', {}).get('affluence', 0), rules)
    if bounds is not None:
        info = state.setdefault('village_information', {})
        for key, value in zip(('current_level_affluence', 'next_level_affluence'), bounds):
            if info.get(key) != value:
                info[key] = value
                changed = True
    tutorials = _tutorial_rules(rules)
    for building in state.get('buildings', {}).values():
        rule = rules.get('buildings', {}).get(str(building.get('building_type')), {}).get(
            'state_data', {}).get(str(building.get('state')), {})
        for task in rule.get('client_data', {}).get('completes_tutorial_tasks', []):
            if task in tutorials:
                changed = complete_tutorial_task(data, task, rules) or changed
    return changed
