"""Local starter village and validated, persistent economy actions.

These are foundation economy helpers. The simulation module adds worker jobs,
construction timing and provisional breeding. Quests and real-money purchases
remain unsupported.
"""
import copy
import json
import time
from pathlib import Path

RULES = {}  # Per-game rules are extracted from the user-owned APK at preparation.
RESOURCE_IDS = {359: 1, 360: 2, 361: 3, 372: 4, 373: 5}
MAP_SIZE = 74


class ActionError(ValueError):
    pass


def integer(params, key, default=None, low=0, high=2147483647):
    raw = params.get(key, [default])
    if isinstance(raw, list):
        raw = raw[0] if raw else default
    try:
        if isinstance(raw, bool) or isinstance(raw, float):
            raise ValueError()
        result = int(raw)
    except (TypeError, ValueError, OverflowError):
        raise ActionError(f'Invalid {key}.')
    if not low <= result <= high:
        raise ActionError(f'Invalid {key}.')
    return result


def text(params, key, default=''):
    value = params.get(key, [default])
    return str(value[0] if isinstance(value, list) and value else value).strip()


def idle_job(now):
    return dict(job_id=0, job_state=0, target_id=0, source_id=0,
                destination_id=0, resource_id=0, build_rate=0,
                gather_rate=0, gather_time=0, trip_time=0,
                update_interval=60, job_start_date=int(now), last_update=now)


def villager(ident, name, gender, appearance, user_id, now):
    return dict(villager_id=ident, name=name, gender=gender, user_id=user_id,
                location_type=0, location_id=user_id,
                birthday=int(now - 20 * 3600), deathday=int(now + 80 * 3600),
                last_update=now, job=idle_job(now), items={}, effects=[],
                appearance_items=[dict(item_id=i, count=1, layer=1,
                                       cooldown=0, last_update=now) for i in appearance],
                available_actions={},
                stats=dict(strength=10, intelligence=10, charisma=10,
                           birthsigns=[1]))


def building(ident, kind, state, location, now, orientation=0):
    return dict(building_id=ident, building_type=kind, state=state,
                location=location, orientation=orientation, progress=0,
                count=1, items={}, destination=0, expire_date=0,
                last_update=now)


def next_id(collection):
    return max([int(k) for k in collection if str(k).isdigit()] + [0]) + 1


def synchronize(data, now, rules=None):
    rules = RULES if rules is None else rules
    gs = data['game_state']
    level = 1
    affluence = 0
    for b in gs['buildings'].values():
        rule = rules['buildings'].get(str(b['building_type']), {})
        state = rule.get('state_data', {}).get(str(b['state']), {})
        affluence += int(state.get('affluence', 0))
        if b['building_type'] == 1:
            level = int(state.get('temple_level', 1))
    gs.setdefault('achievements', {})['102'] = dict(
        achievement_id=102, level=level, last_updated=now)
    affluence+=int(data.get('local_affluence_delta',0))
    info = gs.setdefault('village_information', {})
    # Fallback for incomplete rule sets; progression then derives the village
    # display level from affluence without changing Temple achievement102.
    info.update(village_level=level, affluence=affluence,
                current_level_affluence=0, next_level_affluence=max(100, affluence + 100))
    data['game_user'].update(village_level=level, affluence=affluence)
    from . import progression
    progression.synchronize(data,now,rules)


def migrate(data, now=None):
    """One-time additive migration; preserve an already populated village."""
    now = time.time() if now is None else now
    if 'starter-economy-1' in data.get('local_migrations', []):
        return None
    new = copy.deepcopy(data)
    gs = new['game_state']
    resources = gs.setdefault('resources', {})
    legacy_empty = not gs.get('all_villagers') and len(resources) == 1
    if legacy_empty and resources.get('1', {}).get('count') == 1000:
        resources['1']['count'] = 500
    for ident, amount in [(1, 500), (2, 500), (3, 500), (4, 0), (5, 50)]:
        resources.setdefault(str(ident), dict(resource_id=ident, count=amount, last_update=now))
    if int(gs.get('points', 0)) == 0:
        gs['points'] = 25
    people = gs.setdefault('all_villagers', {})
    if not people:
        uid = int(new['game_user']['user_id'])
        entries = [('Miko', 1, [313, 317, 322, 329, 339]),
                   ('Luma', 0, [335, 343, 347, 351, 355]),
                   ('Piko', 1, [315, 319, 324, 331, 341])]
        for ident, (name, gender, appearance) in enumerate(entries, 1):
            people[str(ident)] = villager(ident, name, gender, appearance, uid, now)
    synchronize(new, now)
    new.setdefault('local_migrations', []).append('starter-economy-1')
    return new


def caps(gs):
    result = {i: 0 for i in range(1, 6)}
    for b in gs['buildings'].values():
        state = RULES['buildings'].get(str(b['building_type']), {}).get(
            'state_data', {}).get(str(b['state']), {})
        for ident, amount in state.get('resource_caps', {}).items():
            result[int(ident)] += int(amount)
    return result


def charge(gs, costs, skulls=0):
    required = {}
    for item, amount in costs.items():
        ident = RESOURCE_IDS.get(int(item))
        if ident is None or not isinstance(amount, int) or amount < 0:
            raise ActionError('This cost type is not supported locally yet.')
        required[ident] = required.get(ident, 0) + amount
    if skulls < 0 or gs.get('points', 0) < skulls:
        raise ActionError('Not enough local crystal skulls.')
    for ident, amount in required.items():
        if gs['resources'][str(ident)]['count'] < amount:
            raise ActionError('Not enough resources.')
    for ident, amount in required.items():
        gs['resources'][str(ident)]['count'] -= amount
        gs['resources'][str(ident)]['last_update'] = time.time()
    gs['points'] -= skulls


def footprint(kind, location):
    size = int(RULES['buildings'][str(kind)]['size'])
    # The native map encodes x * mapHeight + y.
    x, y = divmod(location, MAP_SIZE)
    if x < 0 or y < 0 or x + size > MAP_SIZE or y + size > MAP_SIZE:
        raise ActionError('Building is outside the village map.')
    return x, y, x + size, y + size


def check_placement(gs, kind, location, ignore=None):
    a = footprint(kind, location)
    for key, b in gs['buildings'].items():
        if key == ignore:
            continue
        q = footprint(b['building_type'], b['location'])
        if a[0] < q[2] and a[2] > q[0] and a[1] < q[3] and a[3] > q[1]:
            raise ActionError('That position overlaps another building.')


def require_unlocked(gs, rule):
    ident = rule.get('unlock_achievement_id')
    if ident and gs['achievements'].get(str(ident), {}).get('level', 0) < rule.get('unlock_achievement_level', 1):
        raise ActionError('Upgrade your temple to unlock this building.')


def mutate(data, route, params, now=None):
    """Return a new save only after validation, or None for unhandled routes."""
    supported = {
        'game/village/place_building', 'game/village/move_building',
        'game/village/change_building', 'game/village/delete_building',
        'game/village/change_villager_name', 'game/village/set_job',
        'game/points/buy_points_store_item', 'game/purchase/buy_item',
        'game/village/place_resource', 'game/village/delete_resource_building',
        'game/village/update_villager_job', 'game/village/complete_tutorial_task',
    }
    if route not in supported:
        return None
    now = time.time() if now is None else now
    new = copy.deepcopy(data)
    gs = new['game_state']
    houses = gs['buildings']
    if route == 'game/village/place_resource':
        kind = integer(params, 'building_type_id', low=2, high=4)
        location = integer(params, 'location', high=MAP_SIZE * MAP_SIZE - 1)
        orientation = integer(params, 'orientation', default=0, high=1)
        # Resource spawns are retried by the original client. Repeated requests
        # for the same node must return the saved node, not allocate another ID.
        if any(b['building_type'] == kind and b['location'] == location for b in houses.values()):
            return new
        from .ecology import RESOURCE_LIMITS as limits
        if sum(b['building_type'] == kind for b in houses.values()) >= limits[kind]:
            return new
        check_placement(gs, kind, location)
        ident = next_id(houses)
        houses[str(ident)] = building(ident, kind, 1, location, now, orientation)
    elif route == 'game/village/delete_resource_building':
        location = integer(params, 'location', high=MAP_SIZE * MAP_SIZE - 1)
        for ident, b in list(houses.items()):
            if b['location'] == location and b['building_type'] in (2, 3, 4):
                del houses[ident]
                break
    elif route == 'game/village/update_villager_job':
        ident = str(integer(params, 'villager_id', low=1))
        person = gs['all_villagers'].get(ident)
        if person is None:
            raise ActionError('Villager does not exist.')
        if person['job']['job_id'] != 0:
            raise ActionError('Updating this worker job is not implemented yet.')
        person['job'].update(last_update=now, update_interval=60)
        person['last_update'] = now
    elif route == 'game/village/complete_tutorial_task':
        # Preserve task acknowledgements locally without awarding unknown rewards.
        task = text(params, 'task_id') or text(params, 'task_name') or text(params, 'task')
        if not task or len(task) > 100:
            raise ActionError('Invalid tutorial task.')
        from . import progression
        try:progression.complete_tutorial_task(new,task,RULES)
        except ValueError as error:raise ActionError(str(error)) from error
    elif route == 'game/village/place_building':
        kind = integer(params, 'building_type_id', low=1)
        rule = RULES['buildings'].get(str(kind))
        if not rule or not rule.get('active') or kind in (1, 2, 3, 4):
            raise ActionError('This building cannot be bought locally.')
        location = integer(params, 'location', high=MAP_SIZE * MAP_SIZE - 1)
        orientation = integer(params, 'orientation', default=0, high=1)
        state = rule['state_data'][str(rule['default_state'])]
        require_unlocked(gs, state)
        level = gs['achievements']['102']['level']
        limit = rule.get('max_count_by_state_meter_unit', {}).get(f'[1, {1 + (level-1)*10}]')
        if limit is not None and sum(b['building_type'] == kind for b in houses.values()) >= limit:
            raise ActionError('This temple level has reached the building limit.')
        check_placement(gs, kind, location)
        charge(gs, state.get('counter_unit_cost', {}), int(state.get('points_cost', 0)))
        ident = next_id(houses)
        completed = int(state.get('auto_transition', rule['default_state']))
        houses[str(ident)] = building(ident, kind, completed, location, now, orientation)
    elif route in ('game/village/move_building', 'game/village/change_building', 'game/village/delete_building'):
        ident = str(integer(params, 'building_id', low=0 if route.endswith('/move_building') else 1))
        if route == 'game/village/move_building':
            # Native moveBuilding:from:to: sends its FROM POSITION under
            # building_id (unlike upgrade/delete). Resolve that exact occupied
            # position first; retain ID lookup for existing local API clients.
            matches=[key for key,node in houses.items() if node.get('location')==int(ident)]
            if len(matches)>1:raise ActionError('More than one building occupies the source position.')
            if matches:ident=matches[0]
        b = houses.get(ident)
        if b is None:
            raise ActionError('Building does not exist.')
        if route == 'game/village/move_building':
            location = integer(params, 'to_position', high=MAP_SIZE * MAP_SIZE - 1)
            check_placement(gs, b['building_type'], location, ident)
            b.update(location=location, orientation=integer(params, 'orientation', default=b['orientation'], high=1), last_update=now)
        elif route == 'game/village/delete_building':
            state = RULES['buildings'][str(b['building_type'])]['state_data'][str(b['state'])]
            if b['building_type'] == 1 or not state.get('can_user_delete'):
                raise ActionError('This building cannot be deleted.')
            del houses[ident]
        else:
            kind = integer(params, 'building_type_id', low=1)
            target = integer(params, 'state')
            old = RULES['buildings'][str(b['building_type'])]['state_data'][str(b['state'])]
            if kind != b['building_type'] or target not in old.get('valid_transitions', []):
                raise ActionError('This building transition is not supported locally.')
            rule = RULES['buildings'][str(kind)]
            state = rule['state_data'].get(str(target))
            if state is None or not state.get('buildable'):
                raise ActionError('Only building upgrades are supported by this action.')
            require_unlocked(gs, state)
            charge(gs, state.get('counter_unit_cost', {}), int(state.get('points_cost', 0)))
            b.update(state=int(state.get('auto_transition', target)), progress=0, last_update=now)
    elif route in ('game/village/change_villager_name', 'game/village/set_job'):
        ident = str(integer(params, 'villager_id', low=1))
        person = gs['all_villagers'].get(ident)
        if person is None:
            raise ActionError('Villager does not exist.')
        if route.endswith('change_villager_name'):
            name = text(params, 'villager_name')
            if not name or len(name) > 30:
                raise ActionError('Use a name between 1 and 30 characters.')
            person['name'] = name
        else:
            if integer(params, 'job_id') != 0:
                raise ActionError('Worker jobs are coming in the next local update. You can build from the shop now.')
            person['job'] = idle_job(now)
        person['last_update'] = now
    elif route == 'game/points/buy_points_store_item':
        ident = str(integer(params, 'points_store_id', low=1))
        product = RULES['points_store'].get(ident)
        if not product or not product.get('active') or product.get('type') != 1:
            raise ActionError('This local resource pack is not available.')
        level = gs['achievements']['102']['level']
        if not product.get('minimum_temple_level', 1) <= level <= product.get('maximum_temple_level', 100):
            raise ActionError('This resource pack is for a different temple level.')
        additions = {RESOURCE_IDS.get(int(k)): int(v) for k, v in product['contents'].items()}
        if None in additions:
            raise ActionError('This pack type is not supported locally.')
        limits = caps(gs)
        amounts = {i: min(v, max(0, limits[i] - gs['resources'][str(i)]['count'])) for i, v in additions.items()}
        if not any(amounts.values()):
            raise ActionError('Your storage is full. No skulls were spent.')
        charge(gs, {}, int(product['points_cost']))
        for i, amount in amounts.items():
            gs['resources'][str(i)]['count'] += amount
            gs['resources'][str(i)]['last_update'] = now
    elif route == 'game/purchase/buy_item':
        from . import catalog
        ident = str(integer(params, 'item_id', low=1))
        count = integer(params, 'count', default=1, low=1, high=100)
        catalog.purchase_item(gs, ident, count,
                              text(params, 'use_points', 'false').lower() in ('true', '1'), RULES, now)
    synchronize(new, now)
    return new

