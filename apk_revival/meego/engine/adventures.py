"""Persistent solo adaptation of the original dungeon packets and stage rules.

See ADVENTURE_RULES.md for the boundary between recovered client rules and
local policies. No downloaded stage, remote player or client-supplied payout is
trusted. All public mutations operate on copies so validation errors roll back.
"""
import copy
import json
import math

from . import local_game as g
from . import adventure_loot

KEY = 'local_adventures_v1'
DUNGEON_LOCATION = 1
JOBS = {51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62}
ROUTES = {
    'game/dungeon/start_dungeon', 'game/dungeon/get_active_dungeon',
    'game/dungeon/get_dungeon', 'game/dungeon/send_villager_to_dungeon',
    'game/dungeon/get_dungeons_list', 'game/dungeon/update_dungeon',
    'game/dungeon/complete_dungeon_quest', 'game/dungeon/set_job',
    'game/dungeon/update_villager_job', 'game/dungeon/update_building',
    'game/dungeon/get_dungeon_notices', 'game/dungeon/get_last_viewed_id',
}


def _state(data):
    return data.setdefault(KEY, {'next_id': 1, 'active_id': 0, 'sessions': {}})


def is_away(data, person_id):
    person = data.get('game_state', {}).get('all_villagers', {}).get(str(person_id), {})
    return int(person.get('location_type', 0)) == DUNGEON_LOCATION


def _stages(rules, kind):
    return sorted((v for v in rules.get('dungeon_stages', {}).values()
                   if int(v.get('dungeon_type_id', 0)) == kind and v.get('active')),
                  key=lambda v: int(v['stage_level']))


def _type(rules, kind):
    rule = rules.get('dungeon_types', {}).get(str(kind), {})
    stages = _stages(rules, kind)
    if not rule.get('active') or not stages or rule.get('required_keys'):
        raise g.ActionError('This solo adventure is unavailable in the original rules.')
    if len(stages) != int(rule.get('stages_count', len(stages))):
        raise g.ActionError('Original adventure stages are missing; nothing was charged.')
    return rule


def _session(data, params, allow_inactive=False):
    state = _state(data)
    ident = g.integer(params, 'dungeon_id', state['active_id'], low=1)
    session = state['sessions'].get(str(ident))
    if session is None or (not allow_inactive and session['status'] == 'claimed'):
        raise g.ActionError('This local adventure is no longer active.')
    return session


def _person(data, ident, now):
    p = data['game_state'].get('all_villagers', {}).get(str(ident))
    if not p or int(p.get('user_id', 0)) != int(data['game_user']['user_id']):
        raise g.ActionError('Choose one of your own villagers.')
    if int(p.get('deathday', 0)) <= now or p.get('job', {}).get('job_id') in (1, 2, 3, 6):
        raise g.ActionError('This villager cannot go on an adventure.')
    if now - float(p.get('birthday', now)) < 10 * 3600:
        raise g.ActionError('Only adult villagers can go on adventures.')
    return p


def _view(data, session, rules):
    uid = int(data['game_user']['user_id'])
    return dict(dungeon_id=session['id'], dungeon_type_id=session['type_id'],
                stage_level=session['stage_level'], user_id=uid,
                username=str(data['game_user'].get('username', 'Player')),
                user_avatar_id=int(data['game_user'].get('avatar_id', 0)),
                slots_filled=len(session['participants']),
                dungeon_expire_date=session['expire_date'], stars=_stars(session, rules))


def _stars(session, rules):
    thresholds = rules['dungeon_types'][str(session['type_id'])].get('progress', {}).get('breakpoints', {})
    work = sum(float(v.get('time_worked', 0)) for v in session['participants'].values())
    return max([int(k) for k, value in thresholds.items() if work >= float(value)] + [0])


def _publish(data, rules):
    state = _state(data)
    active = state['sessions'].get(str(state['active_id']))
    entries = {}
    if active and active['status'] == 'active':
        view = _view(data, active, rules)
        entries[str(view['user_id'])] = view
    data['game_state'].setdefault('dungeon_info', {})['active_dungeons'] = entries


def _load_stage(data, session, rules, now):
    stage = _stages(rules, session['type_id'])[session['stage_level']]
    buildings = {}
    for i, (location, definition) in enumerate(stage['buildings'].items(), 1):
        obj = g.building(i, int(definition['id']), int(definition['state']), int(location), now,
                         int(definition.get('orientation', 0)))
        state_rule = rules['buildings'][str(obj['building_type'])]['state_data'][str(obj['state'])]
        obj['count'] = max(0, int(state_rule.get('default_length', 0))) if state_rule.get('stocked_phase') else 0
        obj['local_stage_links'] = copy.deepcopy(definition)
        buildings[str(i)] = obj
    # These dictionaries use the same JMGameState shapes as the island, with
    # stage buildings and participants isolated from the island's identities.
    session['game_state'] = dict(
        name='dungeon', buildings=buildings, all_villagers={},
        resources={str(i): dict(resource_id=i, count=0, last_update=now) for i in range(1, 6)},
        items={}, achievements={}, gifts={}, points=0,
        global_state=dict(food_consumption_rate=0, mood_state=0, effects=[], productivity_boost={}),
        village_information=copy.deepcopy(data['game_state'].get('village_information', {})),
        unlock_information=copy.deepcopy(data['game_state'].get('unlock_information', {})),
        dungeon_info={'active_dungeons': {}},
    )
    for ident in session['participants']:
        person = copy.deepcopy(data['game_state']['all_villagers'][ident])
        person['job'] = g.idle_job(now)
        # Original stage idle classes: fisher/driller. In this local adaptation
        # the first participant is a fisher; later ones alternate roles.
        defaults = stage.get('default_jobs', [])
        if defaults:
            person['job']['job_id'] = int(defaults[len(session['game_state']['all_villagers']) % len(defaults)])
        session['game_state']['all_villagers'][ident] = person
    session['stage_last_update'] = float(now)


def _join(data, session, ident, rules, now):
    key = str(ident)
    if key in session['participants']:
        return
    rule = _type(rules, session['type_id'])
    if session['status'] != 'active' or now >= session['expire_date']:
        raise g.ActionError('This adventure has finished.')
    if len(session['participants']) >= int(rule['user_slots']):
        raise g.ActionError('This adventure has no open slots.')
    person = _person(data, ident, now)
    if is_away(data, ident):
        raise g.ActionError('This villager is already away.')
    # Refuse to interrupt nursing, construction or other uninterruptible jobs.
    old_id = int(person.get('job', {}).get('job_id', 0))
    old_rule = rules.get('jobs', {}).get(str(old_id), {})
    if old_id not in (0, 49) and not old_rule.get('interruptible'):
        raise g.ActionError('Finish this villager’s current job first.')
    person.update(location_type=DUNGEON_LOCATION, location_id=session['id'], last_update=now)
    person['job'] = g.idle_job(now)
    person['dungeon_quest'] = dict(dungeon_id=session['id'], start_date=now,
                                  end_date=session['expire_date'], from_username=data['game_user'].get('username', ''),
                                  time_worked=0, gold_count=0, job_activations=0, chat_blocked=True)
    session['participants'][key] = dict(time_worked=0.0, gold_count=0, bonus_gold_units=0, job_activations=0, claimed=False)
    if 'game_state' in session:
        session['game_state']['all_villagers'][key] = copy.deepcopy(person)
        defaults = _stages(rules, session['type_id'])[session['stage_level']].get('default_jobs', [])
        if defaults:
            session['game_state']['all_villagers'][key]['job']['job_id'] = int(defaults[(len(session['participants']) - 1) % len(defaults)])


def _packet(data, session, rules):
    # A finished trip must unload the native dungeon session. Keeping a past-
    # deadline view alive makes the client poll update_dungeon indefinitely.
    # Participant results remain saved until explicitly collected at the portal.
    finished = session['status'] in ('finished', 'claimed')
    return dict(game_state=copy.deepcopy(data['game_state']),
                user_dungeon=None if finished else _view(data, session, rules),
                dungeon_game_state=None if finished else copy.deepcopy(session['game_state']))


def _building_rule(source, rules):
    return rules.get('buildings', {}).get(str(source['building_type']), {}).get('state_data', {}).get(str(source['state']), {})


def _idle(person, now, job_id=0):
    person['job'] = g.idle_job(now)
    person['job']['job_id'] = job_id


def _links(session, source, active, now):
    by_location = {str(b['location']): b for b in session['game_state']['buildings'].values()}
    for location, link in source.get('local_stage_links', {}).get('children', {}).items():
        child = by_location.get(str(location))
        if child:
            child.update(state=int(link['active_state' if active else 'inactive_state']), last_update=now)
            if not active:
                for person in session['game_state']['all_villagers'].values():
                    if int(person['job'].get('source_id', 0)) == int(child['building_id']):
                        _idle(person, now)


def _gold(job_id, rules):
    drop = rules.get('jobs', {}).get(str(job_id), {}).get('random_drop', {}).get('0', {}).get('373', {})
    contribution = drop.get('count_contribution', {})
    if float(drop.get('chance', 0)) != 100 or any(float(contribution.get(k, 0)) for k in ('strength', 'intelligence', 'charisma')):
        return 0
    return max(0, int(contribution.get('constant', 0)))


def _refresh_fishing_deadlines(session):
    """A stocked hole expires at its final catch, not its first pickup.

    Clear timers on abandoned stocked holes as well: without a worker, stock
    cannot deplete, so an old countdown must not trigger repeated native polls.
    """
    workers = {int(p.get('job', {}).get('source_id', 0)): p['job']
               for p in session['game_state']['all_villagers'].values()
               if int(p.get('job', {}).get('job_id', 0)) in (58, 61)}
    for source in session['game_state']['buildings'].values():
        if source['building_type'] not in (38, 41) or int(source['state']) not in (21, 31):
            continue
        job = workers.get(int(source['building_id']))
        if not job:
            source['expire_date'] = 0
            continue
        duration = max(1, float(job.get('gather_time', 10)))
        remaining = max(0, int(source.get('count', 0)) * duration - float(job.get('local_cycle_work', 0)))
        source['expire_date'] = float(job['last_update']) + remaining if remaining else 0


def _settle(data, session, now, rules):
    """Settle only assigned work, bounded by stage deadlines and source cycles."""
    stages = _stages(rules, session['type_id'])
    start = float(session['start_date'])
    end = min(float(now), float(session['expire_date']))
    while session['stage_level'] < len(stages):
        level = session['stage_level']
        stage_end = start + sum(float(s['duration']) for s in stages[:level + 1])
        stop = min(end, stage_end)
        previous = float(session['stage_last_update'])
        # Split on finite job completion so a heater's children stop exactly
        # when it does, independently of polling frequency or offline time.
        for person in session['game_state']['all_villagers'].values():
            job = person.get('job', {})
            jid = int(job.get('job_id', 0))
            if jid in JOBS - {54, 55, 57, 58, 59, 61}:
                due = float(job.get('last_update', previous)) + max(0, float(job.get('gather_time', 1)) - float(job.get('local_cycle_work', 0)))
                if due > previous:
                    stop = min(stop, due)
        if stop > previous:
            gs = session['game_state']
            completed_links = []
            for ident, person in gs['all_villagers'].items():
                job = person.get('job', {})
                jid = int(job.get('job_id', 0))
                source = gs['buildings'].get(str(job.get('source_id', 0)))
                if jid not in JOBS or jid in (55, 57) or source is None:
                    continue
                since = max(previous, float(job.get('last_update', previous)))
                worked = max(0, stop - since)
                if worked <= 0:
                    continue
                rule = _building_rule(source, rules)
                duration = max(1, int(job['gather_time']))
                carry = float(job.get('local_cycle_work', 0))
                # Cycle jobs finish once; ice chipping repeats while its heater
                # is operating. Fish holes have finite original stock counts.
                cap = math.inf if jid in (54, 59, 58, 61) else 1
                if jid in (58, 61):
                    cap = max(0, int(source.get('count', 0)))
                usable = min(worked, max(0, duration * cap - carry))
                total = carry + usable
                cycles = int(total // duration)
                job['local_cycle_work'] = total - cycles * duration
                job['last_update'] = stop
                person['last_update'] = stop
                record = session['participants'][ident]
                record['time_worked'] += usable
                earned = cycles * _gold(jid, rules)
                record['gold_count'] += earned
                from . import effects
                if earned and hasattr(effects, 'adventure_bonus'):
                    # The engine splits on effect boundaries. Credit work just
                    # before the segment boundary, not a later reward claim.
                    coefficient = max(0, int(effects.adventure_bonus(data, int(ident), max(since, stop - 0.000001))))
                    record['bonus_gold_units'] = int(record.get('bonus_gold_units', 0)) + earned * coefficient
                source['progress'] = total if cap == 1 else job['local_cycle_work']
                quest = data['game_state']['all_villagers'][ident]['dungeon_quest']
                quest.update(time_worked=int(record['time_worked']), gold_count=record['gold_count'],
                             job_activations=record['job_activations'])
                person['dungeon_quest'] = copy.deepcopy(quest)
                if cycles and jid in (58, 61):
                    source['count'] -= cycles
                    if source['count'] <= 0:
                        source.update(state=1, count=0, progress=0, expire_date=0)
                        _idle(person, stop, 57)
                elif cycles and cap == 1:
                    source.update(state=int(rule.get('auto_transition', 1)), progress=0, expire_date=0)
                    if jid in (56, 60):
                        source['count'] = max(0, int(_building_rule(source, rules).get('default_length', 0)))
                    completed_links.append(source)
                    _idle(person, stop, int(rules['jobs'][str(jid)].get('default_idle_job_id', 0)))
            for source in completed_links:
                _links(session, source, False, stop)
            session['stage_last_update'] = stop
            if stop < min(end, stage_end):
                continue
        if end < stage_end or level == len(stages) - 1:
            break
        session['stage_level'] += 1
        _load_stage(data, session, rules, stage_end)
    _refresh_fishing_deadlines(session)
    if now >= session['expire_date']:
        session['status'] = 'finished'
        # Original job 50 is the noninterruptible "post dungeon" / postquest
        # state. Return the real participant home to wait at its portal;
        # keep the quest and earned results until the explicit claim request.
        portals = [b['building_id'] for b in data['game_state'].get('buildings', {}).values()
                   if int(b.get('building_type', 0)) == 34 and int(b.get('state', 0)) == 1]
        portal = min(portals) if portals else 0
        for ident, record in session['participants'].items():
            person = data['game_state']['all_villagers'].get(ident)
            if not record.get('claimed') and person and int(person.get('location_type', 0)) == DUNGEON_LOCATION:
                person.update(location_type=0, location_id=int(data['game_user']['user_id']), last_update=now)
                person['job'] = g.idle_job(now)
                person['job'].update(job_id=50, source_id=portal, target_id=portal)
    _publish(data, rules)


def advance(data, now, rules):
    """In-place clock settlement; call on the engine's existing save copy."""
    if KEY not in data:
        return
    session = data[KEY]['sessions'].get(str(data[KEY]['active_id']))
    if session and session['status'] != 'claimed':
        _settle(data, session, now, rules)


def _set_job(data, session, params, rules, now):
    ident = g.integer(params, 'villager_id', low=1)
    person = session['game_state']['all_villagers'].get(str(ident))
    if person is None or session['participants'][str(ident)]['claimed']:
        raise g.ActionError('This villager is not in this adventure.')
    jid = g.integer(params, 'job_id')
    if jid not in JOBS | {0}:
        raise g.ActionError('This job does not belong to the current adventure.')
    if session['status'] != 'active':
        raise g.ActionError('This adventure has finished. Collect its results at the portal.')
    if jid in (0, 55, 57):
        if jid in (55, 57) and not _stages(rules, session['type_id'])[session['stage_level']].get('default_jobs'):
            raise g.ActionError('That role is unavailable on this stage.')
        _idle(person, now, jid)
        _refresh_fishing_deadlines(session)
        return
    # The native drag/drop client sends source_id inside JSON job_data,
    # just like island assignments. Keep direct fields for older callers.
    raw = params.get('job_data', [{}])
    raw = raw[0] if isinstance(raw, list) and len(raw) == 1 else raw
    if isinstance(raw, str):
        if len(raw) > 8192:
            raise g.ActionError('Adventure job data is too large.')
        try:raw = json.loads(raw)
        except (ValueError, TypeError):
            raise g.ActionError('Invalid adventure job data.') from None
    if not isinstance(raw, dict):
        raise g.ActionError('Adventure job data must be an object.')
    source_id = g.integer(raw if 'source_id' in raw else params, 'source_id', low=1)
    if 'source_id' in raw and 'source_id' in params and source_id != g.integer(params, 'source_id', low=1):
        raise g.ActionError('Conflicting adventure source identifiers.')
    source = session['game_state']['buildings'].get(str(source_id))
    if source is None:
        raise g.ActionError('Adventure source is missing.')
    if 'building_type_id' in raw and g.integer(raw,'building_type_id',low=1) != source['building_type']:
        raise g.ActionError('The adventure building type does not match.')
    if int(person['job'].get('job_id', 0)) == jid and int(person['job'].get('source_id', 0)) == source_id:
        return  # A retried activation neither charges again nor resets progress.
    job_rule = rules.get('jobs', {}).get(str(jid), {})
    # Stage role transitions prevent switching a fisher into a driller without
    # choosing its original idle role, and reject wrong sources/states.
    old = int(person['job'].get('job_id', 0))
    valid = rules.get('jobs', {}).get(str(old), {}).get('valid_transitions', [])
    if old and jid not in valid:
        raise g.ActionError('This worker has a different adventure role.')
    for field, checks in job_rule.get('parameter_restrictions', {}).items():
        if field != 'source_id':
            continue
        for key, comparison, values in checks:
            if comparison != 'in' or source.get(key) not in values:
                raise g.ActionError('This adventure job cannot use that building or state.')
    if any(p['villager_id'] != ident and int(p['job'].get('source_id', 0)) == source_id
           and int(p['job'].get('job_id', 0)) not in (0, 55, 57)
           for p in session['game_state']['all_villagers'].values()):
        raise g.ActionError('This adventure building already has a worker.')
    brule = rules['buildings'][str(source['building_type'])]
    current = _building_rule(source, rules)
    target = current
    if int(current.get('active_job', 0)) != jid:
        target = brule['state_data'].get('11', {})
        if current.get('cannot_be_actived') or int(target.get('active_job', 0)) != jid or 11 not in current.get('valid_transitions', []):
            raise g.ActionError('This building cannot perform that adventure job.')
        g.charge(data['game_state'], target.get('counter_unit_cost', {}), int(target.get('points_cost', 0)))
        source['state'] = 11
    if jid in (58, 61) and int(source.get('count', 0)) <= 0:
        raise g.ActionError('This fishing hole has no fish remaining. Drill another hole.')
    duration = int(job_rule.get('gather_time', target.get('default_length', 1)))
    if jid in (58, 61):
        duration = int(job_rule.get('gather_time', 10))
    # Fishing stock is multiple catches. A single-catch expiry makes the
    # original time-left popup flash overdue while valid stock remains.
    cycles_left = max(1, int(source.get('count', 0))) if jid in (58, 61) else 1
    source.update(progress=0, expire_date=now + max(1, duration) * cycles_left, last_update=now)
    _links(session, source, True, now)
    job = g.idle_job(now)
    job.update(job_id=jid, source_id=source_id, target_id=source_id,
               resource_id=5, gather_rate=_gold(jid, rules),
               gather_time=max(1, duration), trip_time=max(1, duration), update_interval=10)
    person['job'] = job
    session['participants'][str(ident)]['job_activations'] += 1
    _refresh_fishing_deadlines(session)


def _results(data, session, rules, now):
    summary = {}
    for ident, record in session['participants'].items():
        person = data['game_state']['all_villagers'][ident]
        gold = int(record['gold_count'])
        result = dict(resources={'5': gold}, bonus_resources={'5': int(record.get('bonus_gold_units', 0)) // 100},
                      items=adventure_loot.reward(data,session,int(ident),record,rules),
                      points=0, additional_bonus_rewards_key={})
        summary[ident] = dict(villager_id=int(ident), user_id=int(person['user_id']),
                             username=data['game_user'].get('username', ''), villager_name=person['name'],
                             gender=int(person.get('gender', 0)),
                             appearance_item_ids=[i['item_id'] for i in person.get('appearance_items', [])],
                             time_worked=int(record['time_worked']), job_activations=record['job_activations'],
                             gold_count=gold, quest_results=result)
    return summary


def handle(data, route, params, rules, now):
    """Return ``(new_save, native_response)`` or None for another subsystem.

    The caller must persist new_save atomically before returning native_response.
    Never call this against a live save outside the server's existing lock.
    """
    route = route.strip('/')
    if route not in ROUTES:
        return None
    new = copy.deepcopy(data)
    state = _state(new)
    advance(new, now, rules)
    if route.endswith('/get_dungeons_list'):
        # This native packet contains other users' lists only. Offline solo
        # starts use the original dungeon_types catalog, not fabricated friends.
        return new, dict(friend_dungeons=[], tribe_dungeons=[], neighbour_dungeons=[])
    if route.endswith('/start_dungeon'):
        kind = g.integer(params, 'dungeon_type_id', low=1)
        ident = g.integer(params, 'villager_id', low=1)
        rule = _type(rules, kind)
        session = state['sessions'].get(str(state['active_id']))
        if session and session['status'] != 'claimed':
            if session['type_id'] == kind and str(ident) in session['participants']:
                return new, _packet(new, session, rules)
            raise g.ActionError('Finish or collect your existing solo adventure first.')
        if not any(int(b.get('building_type', 0)) == 34 and int(b.get('state', 0)) == 1
                   for b in new['game_state'].get('buildings', {}).values()):
            raise g.ActionError('Build and finish the Quest Portal first.')
        session = dict(id=state['next_id'], type_id=kind, stage_level=0, status='active',
                       start_date=now, expire_date=now + int(rule['duration']), participants={},
                       loot_policy=adventure_loot.POLICY)
        _join(new, session, ident, rules, now)
        g.charge(new['game_state'], {}, int(rule.get('points_cost', 0)))
        state['next_id'] += 1
        state['active_id'] = session['id']
        state['sessions'][str(session['id'])] = session
        # A bounded archive keeps recent replay receipts. Older IDs are never
        # reused; an expired request is rejected rather than paid again.
        history = sorted((int(k) for k, old in state['sessions'].items() if old['status'] == 'claimed'))
        for old_id in history[:-31]:
            del state['sessions'][str(old_id)]
        _load_stage(new, session, rules, now)
        _publish(new, rules)
        return new, _packet(new, session, rules)
    if route.endswith('/get_active_dungeon') and not state['active_id']:
        return new, {'user_dungeon': None}
    if route.endswith('/complete_dungeon_quest') and 'dungeon_id' not in params:
        ident = str(g.integer(params, 'villager_id', low=1))
        candidates = [s for s in state['sessions'].values() if ident in s['participants']]
        if not candidates:
            raise g.ActionError('This villager has no local adventure results.')
        params = dict(params, dungeon_id=[str(max(candidates, key=lambda s: s['id'])['id'])])
    # Native stage timers can already be queued when the player collects
    # rewards. Reading that completed trip should close its old view cleanly,
    # never turn a successful claim into repeated error dialogs.
    completed_reads = ('/get_dungeon', '/update_dungeon', '/get_dungeon_notices', '/get_last_viewed_id')
    session = _session(new, params, allow_inactive=route.endswith(('/complete_dungeon_quest',) + completed_reads))
    if route.endswith('/get_last_viewed_id'):
        # JFDungeonSession.initializeNotices success block (0x91c33c) calls
        # intValue on the response itself. Empty offline notices have ID zero.
        return new, 0
    if route.endswith('/get_dungeon_notices'):
        # Original callback binds dungeon_packet, then dungeon_notices to a
        # strong array (0x6f8c70–0x6f8d50). No online notices are fabricated.
        return new, dict(dungeon_packet=_packet(new, session, rules), dungeon_notices=[])
    if route.endswith('/send_villager_to_dungeon'):
        _join(new, session, g.integer(params, 'villager_id', low=1), rules, now)
        _publish(new, rules)
    elif route.endswith('/set_job'):
        _set_job(new, session, params, rules, now)
    elif route.endswith('/update_building'):
        # Native timer completion polls supply building_id/type, without a
        # desired state. advance() already settled authoritative completion.
        # Retain explicit-state activation for the existing supported caller.
        source_id = g.integer(params, 'building_id', low=1)
        source = session['game_state']['buildings'].get(str(source_id))
        if not source:
            raise g.ActionError('Adventure building is missing.')
        if 'building_type_id' in params and g.integer(params, 'building_type_id', low=1) != source['building_type']:
            raise g.ActionError('The adventure building type does not match.')
        target = g.integer(params, 'state', default=int(source['state']), low=1)
        current = _building_rule(source, rules)
        if target == int(source['state']):
            pass
        elif target == 11 and 11 in current.get('valid_transitions', []) and not current.get('cannot_be_actived'):
            next_rule = rules['buildings'][str(source['building_type'])]['state_data'].get('11', {})
            if not next_rule.get('active_job'):
                raise g.ActionError('This building has no supported adventure activation.')
            g.charge(new['game_state'], next_rule.get('counter_unit_cost', {}), int(next_rule.get('points_cost', 0)))
            source.update(state=11, expire_date=0, progress=0, last_update=now)
        elif target == 1 and 1 in current.get('valid_transitions', []):
            source.update(state=1, expire_date=0, progress=0)
            _links(session, source, False, now)
            for person in session['game_state']['all_villagers'].values():
                if int(person['job'].get('source_id', 0)) == source_id:
                    _idle(person, now)
        else:
            raise g.ActionError('Assign a villager to activate this adventure building.')
    elif route.endswith('/update_dungeon'):
        requested = g.integer(params, 'current_stage_level', session['stage_level'])
        if requested > session['stage_level']:
            raise g.ActionError('The current adventure stage has not finished yet.')
    elif route.endswith('/complete_dungeon_quest'):
        ident = str(g.integer(params, 'villager_id', low=1))
        record = session['participants'].get(ident)
        if record is None:
            raise g.ActionError('This villager did not participate in this adventure.')
        if record.get('receipt'):
            # Return a current island snapshot with the original immutable
            # result; old snapshots must never overwrite subsequent progress.
            receipt = copy.deepcopy(record['receipt'])
            receipt['game_state'] = copy.deepcopy(new['game_state'])
            return new, receipt
        if now < session['expire_date']:
            raise g.ActionError('This adventure has not finished yet; no rewards were credited.')
        summary = _results(new, session, rules, now)
        result = summary[ident]['quest_results']
        earned = int(result['resources']['5']) + int(result['bonus_resources']['5'])
        resource = new['game_state'].setdefault('resources', {}).setdefault('5', dict(resource_id=5, count=0))
        resource.update(count=int(resource['count']) + earned, last_update=now)
        inventory = new['game_state'].setdefault('items', {})
        for item_id, count in result['items'].items():
            item = inventory.setdefault(item_id, dict(item_id=int(item_id), count=0, layer=0, cooldown=0))
            item.update(count=int(item['count'])+count, last_update=now)
        person = new['game_state']['all_villagers'][ident]
        person.update(location_type=0, location_id=int(new['game_user']['user_id']), last_update=now)
        person.pop('dungeon_quest', None)
        _idle(person, now)
        record['claimed'] = True
        if all(v['claimed'] for v in session['participants'].values()):
            session['status'] = 'claimed'
            state['active_id'] = 0
        _publish(new, rules)
        receipt = dict(game_state=copy.deepcopy(new['game_state']), user_dungeon=_view(new, session, rules),
                       dungeon_results={ident: dict(resource_rewards=copy.deepcopy(result['resources']),
                                                   bonus_resource_rewards=copy.deepcopy(result['bonus_resources']),
                                                   item_rewards=copy.deepcopy(result['items']),
                                                   points_reward=int(result['points']),
                                                   additional_bonus_rewards=copy.deepcopy(result['additional_bonus_rewards_key']))},
                       dungeon_summary=summary)
        record['receipt'] = {k: copy.deepcopy(v) for k, v in receipt.items() if k != 'game_state'}
        return new, receipt
    return new, _packet(new, session, rules)
