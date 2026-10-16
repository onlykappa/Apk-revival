"""Three deterministic offline neighbours, using the native Launch Dock protocol.

Layouts and rewards are local restoration choices, not original-server parity.
Home villagers remain owned records while travelling; remote snapshots never
enter the home state. Trips and one-time rewards persist with the normal save.
"""
import copy
import json

from . import local_game as g, skills

POLICY = 'three-local-islands-v1'
KEY = 'local_islands'
ISLANDS = (
    (1900000001, 'Pebble Bay (Local)', 1, 2),
    (1900000002, 'Timber Cove (Local)', 2, 3),
    (1900000003, 'Berry Haven (Local)', 3, 4),
)
ROUTES = frozenset('game/village/' + name for name in (
    'get_neighbour_list', 'get_remote_village', 'send_villager',
    'update_villager_quest', 'complete_quest'))
MIN_DURATION = 60
MAX_DURATION = 86400


def traveller_limits(rules):
    """Native Dock menu indexes login config by questing_level, not state ID."""
    limits = {}
    for state in rules.get('buildings', {}).get('9', {}).get('state_data', {}).values():
        if state.get('active_job') != 7:
            continue
        level, capacity = state.get('questing_level'), state.get('quest_villagers')
        if type(level) is int and level > 0 and type(capacity) is int and capacity > 0:
            limits[str(level)] = max(limits.get(str(level), 0), capacity)
    return limits


def definition(ident):
    for entry in ISLANDS:
        if entry[0] == ident:
            return entry
    raise g.ActionError('Unknown offline island. Choose one of the three local islands.')


def _state(data):
    state = data.setdefault(KEY, dict(policy=POLICY, next_trip=1, trips={}))
    if not isinstance(state, dict) or state.get('policy') != POLICY:
        raise g.ActionError('Unsupported offline-island save policy. Existing data was preserved.')
    return state


def profile(data, ident):
    ident, name, _, _ = definition(ident)
    occupied = sum(t['island_id'] == ident and t['status'] == 'travelling'
                   for t in data.get(KEY, {}).get('trips', {}).values())
    return dict(game_id=5, user_id=ident, username=name, avatar_id=1,
                avatar_type=1, facebook_id='', guest_slots=3,
                guest_count=occupied, village_level=1, affluence=0,
                commercial_buildings=[], status_message='Offline local island',
                group_id=0, group_name='', is_online=1, is_followed=False,
                bidirectional=False, can_friend=False, is_blocked=False)


def remote(data, ident, seed, rules, now):
    ident, _, _, kind = definition(ident)
    # Authored layouts use the starter temple and well-separated resource sites;
    # never clone the player's island or transfer their inventory to a bot.
    gs = copy.deepcopy(seed['game_state'])
    gs.update(name='remote', all_villagers={}, buildings={}, items={}, gifts={}, points=0)
    gs['buildings']['1'] = g.building(1, 1, 1, 0, now)
    for i, (x, y) in enumerate(((20, 20), (30, 20), (40, 20)), 2):
        node = g.building(i, kind, 1, y * g.MAP_SIZE + x, now)
        node['count'] = {2: 40, 3: 30, 4: 75}[kind]
        gs['buildings'][str(i)] = node
    for i, name in enumerate(('Pip', 'Tala'), 1):
        pid = ident - 100 + i
        gs['all_villagers'][str(pid)] = g.villager(pid, name, i % 2,
            [313, 317, 322, 329, 339] if i % 2 else [335, 343, 347, 351, 355], ident, now)
    for pid, trip in data.get(KEY, {}).get('trips', {}).items():
        if trip['island_id'] == ident and trip['status'] == 'travelling':
            person = copy.deepcopy(data['game_state']['all_villagers'][pid])
            person['job'] = g.idle_job(now)
            gs['all_villagers'][pid] = person
    for resource in gs['resources'].values():
        resource.update(count=0, last_update=now)
    return dict(profile=profile(data, ident), game_state=gs)


def _dock(data, person, rules):
    candidates = [b for b in data['game_state']['buildings'].values()
                  if b['building_type'] == 9 and rules.get('buildings', {}).get('9', {})
                  .get('state_data', {}).get(str(b['state']), {}).get('active_job') == 7]
    source = person['job'].get('source_id')
    if source:
        candidates = [b for b in candidates if b['building_id'] == source]
    if not candidates:
        raise g.ActionError('Build a Launch Dock and assign this Meego before travelling.')
    return min(candidates, key=lambda b: b['building_id'])


def send(data, params, rules, now):
    pid = str(g.integer(params, 'villager_id', low=1))
    dest = g.integer(params, 'to_user_id', low=1)
    definition(dest)
    if dest==int(data['game_user']['user_id']):
        raise g.ActionError('Choose a different island from your home village.')
    duration = g.integer(params, 'duration', low=MIN_DURATION, high=MAX_DURATION)
    new = copy.deepcopy(data)
    state = _state(new)
    previous = state['trips'].get(pid)
    # A lost response may retry the same departure. Never reset its timer.
    if previous and previous['status'] in ('travelling','ready'):
        if previous['island_id'] == dest and previous['duration'] == duration:
            return new
        raise g.ActionError('This Meego already has an active or uncollected Launch Dock trip.')
    person = new['game_state']['all_villagers'].get(pid)
    if (not person or person.get('user_id') != new['game_user']['user_id']
            or not g.at_home(person) or person['job']['job_id'] not in (0, 7)
            or now >= person['deathday'] or now - person['birthday'] < 10 * 3600):
        raise g.ActionError('Choose a living adult at home, idle or waiting at the Launch Dock.')
    dock = _dock(new, person, rules)
    rule = rules['buildings']['9']['state_data'][str(dock['state'])]
    busy = sum(t['status'] in ('travelling', 'ready') and t['dock_id'] == dock['building_id']
               for t in state['trips'].values())
    if busy >= int(rule.get('quest_villagers', 0)):
        raise g.ActionError('The Launch Dock is full. Collect a returning traveller first.')
    if profile(new, dest)['guest_count'] >= 3:
        raise g.ActionError('This local island already has three visitors. Choose another island.')
    seq = state['next_trip']; state['next_trip'] += 1
    state['trips'][pid] = dict(id=seq, island_id=dest, dock_id=dock['building_id'],
        started_at=now, ends_at=now + duration, duration=duration, status='travelling')
    person.update(location_type=0, location_id=dest, last_update=now,
        quest=dict(start_date=float(now), end_date=float(now + duration),
                   from_user_id=dest, from_username=profile(new, dest)['username'],
                   from_avatar_id=1, from_avatar_type=1))
    person['job'] = g.idle_job(now)
    person['job'].update(job_id=7, source_id=dock['building_id'], target_id=dock['building_id'])
    return new


def advance(data, now):
    """Return overdue people without granting or consuming their pending rewards."""
    state = data.get(KEY)
    if state is None:
        return
    if state.get('policy') != POLICY:
        raise g.ActionError('Unsupported offline-island save policy.')
    for pid, trip in state['trips'].items():
        if trip['status'] != 'travelling' or now < trip['ends_at']:
            continue
        person = data['game_state']['all_villagers'].get(pid)
        if person is None:
            raise g.ActionError('A saved traveller is missing. Save was preserved for recovery.')
        person.update(location_type=0, location_id=data['game_user']['user_id'], last_update=now)
        person['job'] = g.idle_job(now)
        person['job'].update(job_id=8, source_id=trip['dock_id'], target_id=trip['dock_id'])
        trip['status'] = 'ready'


def _reward_ids(params):
    raw = params.get('reward_villager_ids', [])
    # Native form encoding sends a JSON array; accept repeated form IDs too.
    if isinstance(raw, list) and len(raw) == 1 and isinstance(raw[0], str) and raw[0].startswith('['):
        try: raw = json.loads(raw[0])
        except ValueError: raise g.ActionError('Invalid reward villager list.') from None
    if not isinstance(raw, list) or not raw or len(raw) > 25:
        raise g.ActionError('Select returning Launch Dock villagers to collect rewards.')
    ids = [str(g.integer({'id': v}, 'id', low=1)) for v in raw]
    if len(ids) != len(set(ids)):
        raise g.ActionError('Each returning villager can only be selected once.')
    return ids


def collect(data, params, rules, now):
    ids = _reward_ids(params)
    new = copy.deepcopy(data)
    advance(new, now)
    state = _state(new)
    for pid in ids:
        trip = state['trips'].get(pid)
        if not trip or trip['status'] not in ('ready', 'claimed'):
            raise g.ActionError('This Launch Dock trip has not returned yet.')
    results = {}
    limits = g.caps(new['game_state'])
    for pid in ids:
        trip = state['trips'][pid]
        if trip['status'] == 'claimed':
            results[pid] = copy.deepcopy(trip['receipt'])
            continue
        _, _, resource, _ = definition(trip['island_id'])
        bank = new['game_state']['resources'][str(resource)]
        # Explicit modest local reward: five resources per started minute,
        # maximum100 per trip; no cash currency, random loot or remote service.
        reward = min(100, 5 * max(1, (trip['duration'] + 59) // 60))
        granted = min(reward, max(0, int(limits.get(resource, 0)) - int(bank['count'])))
        bank.update(count=int(bank['count']) + granted, last_update=now)
        result = dict(resource_rewards={str(resource): granted}, bonus_resource_rewards={},
                      additional_bonus_rewards={}, item_rewards={}, points_reward=0)
        person = new['game_state']['all_villagers'][pid]
        skills._gain(person, 'charisma', 1)
        person['job'] = g.idle_job(now)
        if now >= person['deathday']:person['job']['job_id'] = 6
        person['quest'] = None
        person['last_update'] = now
        trip.update(status='claimed', receipt=result, claimed_at=now)
        results[pid] = copy.deepcopy(result)
    return new, dict(game_state=copy.deepcopy(new['game_state']), quest_results=results)


def handle(data, route, params, rules, seed, now):
    if route.endswith('/get_neighbour_list'):
        size = g.integer(params, 'size', default=40, high=40)
        return data, [profile(data, i[0]) for i in ISLANDS][:size]
    if route.endswith('/get_remote_village'):
        ident = g.integer(params, 'village_id', low=1)
        return data, remote(data, ident, seed, rules, now)
    if route.endswith('/send_villager'):
        new = send(data, params, rules, now)
        return new, copy.deepcopy(new['game_state'])
    if route.endswith('/complete_quest'):
        return collect(data, params, rules, now)
    pid = str(g.integer(params, 'villager_id', low=1))
    if pid not in data.get(KEY, {}).get('trips', {}):
        raise g.ActionError('This Meego has no saved Launch Dock trip.')
    new = copy.deepcopy(data)
    advance(new, now)
    return new, copy.deepcopy(new['game_state'])
