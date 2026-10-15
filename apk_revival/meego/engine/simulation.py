"""Persistent offline simulation for the recovered Meego client protocol."""
import copy
import json
import math
import time
import uuid
from pathlib import Path
from . import local_game as g
from . import community, skills, catalog, ecology, food, birthstones, production, population, progression, effects, harvesting

SETTINGS = {'construction_seconds': 45, 'gather_update_seconds': 10, 'gather_seconds': 8, 'travel_seconds': 4, 'resource_stocks': {2: 40, 3: 30, 4: 75}, 'maximum_offline_seconds': 86400, 'hours_per_age': 1, 'baby_age': 2, 'adult_age': 10, 'elder_age': 65, 'death_age': 100}
ActionError = g.ActionError


def state_rule(b):
    return g.RULES['buildings'][str(b['building_type'])]['state_data'][str(b['state'])]


def hours_age(v, now):
    return max(0, (now - v['birthday']) / (3600 * SETTINGS['hours_per_age']))


def refresh_aging_jobs(data, now):
    """Keep native job expiry (last_update + update_interval) on a fixed date.

    JMJob.expire_date is computed, not a writable JSON field. Nursing and
    childhood must count toward birthdays rather than each resource poll.
    """
    people = data['game_state']['all_villagers']
    scale = 3600 * SETTINGS['hours_per_age']
    for person in people.values():
        job = person['job'];kind = int(job['job_id'])
        if kind in (1, 2):
            age = SETTINGS['baby_age'] if kind == 1 else SETTINGS['adult_age']
            deadline = person['birthday'] + age * scale
        elif kind == 3:
            child = people.get(str(job.get('target_id')))
            if not child or int(child['job']['job_id']) != 1:
                person['job'] = g.idle_job(now)
                continue
            deadline = child['birthday'] + SETTINGS['baby_age'] * scale
        else:
            continue
        job.update(last_update=int(now),
                   update_interval=max(1, math.ceil(deadline) - int(now)))


def death_date(person):
    # Native JMVillager.ageCategory uses the individual's deathday. Preserve
    # that lifespan; fallback only for old saves lacking a valid deathday.
    date = person.get('deathday')
    if isinstance(date, (int, float)) and math.isfinite(date) and date > person['birthday']:
        return date
    return person['birthday'] + SETTINGS['death_age'] * 3600 * SETTINGS['hours_per_age']


def housing(gs, rules=None):
    # Capacity belongs to each building's current rule state. In particular,
    # the starter temple houses five villagers and upgrades retain slots.
    rules = g.RULES if rules is None else rules
    return sum(int(rules['buildings'][str(b['building_type'])]['state_data'][str(b['state'])].get('villager_slots', 0)) for b in gs['buildings'].values())


def gather_parameters(person,job_id,data=None,now=0):
    return harvesting.parameters(person,job_id,g.RULES,data,now,
                                 gather_seconds=SETTINGS['gather_seconds'],travel_seconds=SETTINGS['travel_seconds'])


def gather_amount(person, job_id, data=None, now=0):
    return gather_parameters(person,job_id,data,now)['gather_rate']


def refresh_gather_jobs(data, now):
    """Publish changed equipment/effects with the same action response."""
    for person in data['game_state']['all_villagers'].values():
        job = person['job']
        rule = g.RULES.get('jobs', {}).get(str(job['job_id']), {})
        if (rule.get('type') == 3 and rule.get('product_type')) or job['job_id'] == 20:
            job.update(gather_parameters(person, job['job_id'], data, now))


def migrate_economy(data, now):
    """Normalize only the old local node/job defaults; keep earned balances."""
    if 'completed-trips-2' in data.get('local_migrations', []):return
    gs = data['game_state']
    for source in gs['buildings'].values():
        stock = SETTINGS['resource_stocks'].get(source['building_type'])
        if stock is not None:
            source['count'] = max(0, min(int(source.get('count', stock)), stock))
            source['expire_date'] = 0
    for person in gs['all_villagers'].values():
        job = person['job'];job_id = int(job['job_id'])
        rule = g.RULES['jobs'].get(str(job_id), {})
        if rule.get('type') == 3 or job_id == 20:
            job.update(gather_rate=gather_amount(person, job_id),
                       gather_time=SETTINGS['gather_seconds'],
                       trip_time=SETTINGS['gather_seconds'] + SETTINGS['travel_seconds'],
                       local_trip_seconds=0, local_fraction=0, last_update=now)
    data.setdefault('local_migrations', []).append('completed-trips-2')


def advance(data,now=None):
    """Settle modifier expiry boundaries without applying boosts retroactively."""
    now=time.time() if now is None else now
    working=copy.deepcopy(data)
    previous=float(working.get('last_simulated_at',now))
    if now>previous:
        previous=max(previous,now-SETTINGS['maximum_offline_seconds'])
        working['last_simulated_at']=previous
        for boundary in effects.change_times(working,previous,now)+[now]:
            working=_advance_segment(working,boundary)
        return working
    return _advance_segment(working,now)


def _advance_segment(data, now=None):
    now = time.time() if now is None else now
    new = copy.deepcopy(data)
    gs = new['game_state']
    migrate_economy(new, now)
    ecology.upgrade_bush_stock(new)
    skills.migrate_work_progress(new)
    catalog.normalize_research_cursors(gs, g.RULES)
    birthstones.discover_owned(new, g.RULES.get('birthsigns', {}))
    ecology.advance(new, now, rules=g.RULES, stocks=SETTINGS['resource_stocks'])
    if 'last_simulated_at' not in new:
        new['last_simulated_at'] = now
        community.advance(new, now, housing_capacity=housing(gs), rules=g.RULES, hours_per_age=SETTINGS['hours_per_age'])
        refresh_aging_jobs(new, now)
        food.advance(new, now, now)
        return new
    previous = float(new['last_simulated_at'])
    if now <= previous:
        refresh_aging_jobs(new, now)
        food.advance(new, previous, now)
        return new
    elapsed = min(now - previous, SETTINGS['maximum_offline_seconds'])
    limits = g.caps(gs)
    people = gs['all_villagers']
    buildings = gs['buildings']
    handled_cycles=production.advance_cycles(new,now,elapsed,g.RULES)
    effect_clock=previous+elapsed/2
    for person in list(people.values()):
        job = person['job']
        job_id = int(job['job_id'])
        rule = g.RULES['jobs'].get(str(job_id), {})
        age = hours_age(person, now)
        if job_id == 1 and age >= SETTINGS['baby_age']:
            person['job'] = g.idle_job(now)
            person['job']['job_id'] = 2 if age < SETTINGS['adult_age'] else 0
            for parent in people.values():
                if parent['job']['job_id'] == 3 and parent['job']['target_id'] == person['villager_id']:
                    parent['job'] = g.idle_job(now)
            job = person['job']; job_id = job['job_id']
        if job_id == 2 and age >= SETTINGS['adult_age']:
            person['job'] = g.idle_job(now); job = person['job']; job_id = 0
        if now >= death_date(person) and job_id != 6:
            person['job'] = g.idle_job(now); person['job']['job_id'] = 6
            continue
        source = buildings.get(str(job.get('source_id', 0)))
        if source and source['building_id'] in handled_cycles:
            production.configure_job(source,job,g.RULES,now)
            person['last_update']=now
            continue
        if job_id == 5:
            if source is None or not state_rule(source).get('buildable'):
                person['job'] = g.idle_job(now)
                continue
            length = max(1, int(state_rule(source).get('default_length', 1)))
            source['progress'] = min(length, float(source.get('progress', 0)) + elapsed * job['build_rate'])
            source['last_update'] = now
        elif (rule.get('type') == 3 or job_id == 20) and source is None:
            person['job'] = g.idle_job(now)
        elif (rule.get('type') == 3 or job_id == 20) and source is not None:
            resource = g.RESOURCE_IDS.get(int(rule.get('product_type') or 0))
            if resource:
                if rule.get('type')==3 and rule.get('product_type'):
                    try:production.validate_depot(gs,int(job.get('destination_id',0)),job_id,g.RULES)
                    except ActionError:
                        person['job']=g.idle_job(now)
                        continue
                parameters=gather_parameters(person,job_id,new,effect_clock)
                job.update(parameters)
                period = max(1, float(job.get('trip_time', SETTINGS['gather_seconds'] + SETTINGS['travel_seconds'])))
                trips, remainder = divmod(elapsed + float(job.get('local_trip_seconds', 0)), period)
                trips = int(trips);job['local_trip_seconds'] = remainder
                balance = gs['resources'][str(resource)]
                industrial=production.is_stocked(source,g.RULES)
                finite = source['building_type'] in (2, 3, 4) or industrial
                # Resolve trips in their actual order: a stat gained after 60
                # delivered units affects the next trip regardless of polling. The
                # offline elapsed limit bounds this loop; blocked trips are
                # discarded together and cannot form a future credit backlog.
                fraction_units = round(float(job.get('local_fraction', 0)) * 1_000_000)
                for _ in range(trips):
                    rate = gather_amount(person, job_id,new,effect_clock)
                    job['gather_rate'] = rate
                    # Integer micro-units preserve fractional yield across
                    # repeated polls without losing 0.999999... whole units.
                    credit, remainder_units = divmod(round(rate * 1_000_000) + fraction_units, 1_000_000)
                    available = max(0, int(source.get('count', SETTINGS['resource_stocks'].get(source['building_type'],0)))) if finite else credit
                    credited = min(credit, max(0, limits[resource] - balance['count']), available)
                    if not credited:
                        fraction_units = 0
                        break
                    balance['count'] += credited
                    balance['last_update'] = now
                    # A clipped delivery loses its uncredited remainder rather
                    # than saving work that a full store could not receive.
                    fraction_units = remainder_units if credited == credit else 0
                    skills.credit_work(new, person['villager_id'], job_id, credited, now)
                    job['gather_rate'] = gather_amount(person, job_id,new,effect_clock)
                    if finite:
                        if industrial:
                            if production.consume_stock(gs,source,credited,g.RULES,now)==0:break
                            continue
                        source['count'] = available - credited
                        source['last_update'] = now
                        if source['count'] == 0:
                            del buildings[str(source['building_id'])]
                            person['job'] = g.idle_job(now)
                            break
                job['local_fraction'] = fraction_units / 1_000_000
            # Stocking jobs have no product: complete the source's timed state.
            elif state_rule(source).get('auto_transition') is not None:
                source['progress'] = min(int(state_rule(source).get('default_length', 1)),
                                         float(source.get('progress', 0)) + elapsed)
        elif rule.get('type') == 11 and source is not None:
            if source.get('expire_date', 0) and now >= source['expire_date']:
                target = state_rule(source).get('auto_transition')
                if target is not None:
                    source['state'] = int(target)
                    source['progress'] = 0; source['expire_date'] = 0
                person['job'] = g.idle_job(now)
        person['job']['last_update'] = now
        person['job']['update_interval'] = SETTINGS['gather_update_seconds']
        person['last_update'] = now
    skills.advance_school(new, now)
    for person in people.values():
        if person['job'].get('source_id') and str(person['job']['source_id']) not in buildings:
            person['job'] = g.idle_job(now)
    refresh_aging_jobs(new, now)
    for b in list(buildings.values()):
        if str(b['building_id']) in new.get('school_sessions', {}):continue
        rule = state_rule(b)
        length = max(1, int(rule.get('default_length', 1)))
        if (rule.get('buildable') or rule.get('active_job') == 5) and b.get('progress', 0) >= length:
            b['state'] = int(rule.get('auto_transition', b['state']))
            b['progress'] = 0; b['expire_date'] = 0; b['last_update'] = now
            for person in people.values():
                if person['job']['source_id'] == b['building_id'] and person['job']['job_id'] == 5:
                    person['job'] = g.idle_job(now)
        elif not rule.get('buildable') and rule.get('auto_transition') is not None and b.get('progress', 0) >= length:
            b.update(state=int(rule['auto_transition']), progress=0, expire_date=0, last_update=now)
            for person in people.values():
                if person['job']['source_id'] == b['building_id']:
                    person['job'] = g.idle_job(now)
        elif rule.get('buildable'):
            rate = sum(p['job'].get('build_rate', 0) for p in people.values()
                       if p['job']['job_id'] == 5 and p['job']['source_id'] == b['building_id'])
            b['expire_date'] = now + max(0, length - b.get('progress', 0)) / rate if rate else 0
    food.advance(new, previous, now, maximum_elapsed=SETTINGS['maximum_offline_seconds'])
    new['last_simulated_at'] = now
    community.advance(new, now, housing_capacity=housing(gs), rules=g.RULES, hours_per_age=SETTINGS['hours_per_age'])
    birthstones.discover_owned(new, g.RULES.get('birthsigns', {}))
    effects.advance(new,now,g.RULES)
    refresh_gather_jobs(new, now)
    g.synchronize(new, now)
    return new


def object_param(params, key):
    raw = params.get(key, ['{}'])
    raw = raw[0] if isinstance(raw, list) else raw
    try:
        value = json.loads(raw) if isinstance(raw, str) else raw
    except (ValueError, TypeError):
        raise ActionError(f'Invalid {key}.')
    if not isinstance(value, dict):
        raise ActionError(f'Invalid {key}.')
    return value


def get_person(gs, params, key='villager_id'):
    ident = str(g.integer(params, key, low=1))
    if ident not in gs['all_villagers']:
        raise ActionError('Villager does not exist.')
    return gs['all_villagers'][ident]


def compatible(gs, father, mother, now):
    if father['villager_id'] == mother['villager_id'] or father['gender'] != 1 or mother['gender'] != 0:
        raise ActionError('Choose an adult male and female Meego.')
    if any(hours_age(p, now) < SETTINGS['adult_age'] or p['job']['job_id'] in (1, 2, 3, 6) for p in (father, mother)):
        raise ActionError('Both parents must be available adults.')
    uid = father['user_id']
    residents = sum(p.get('user_id') == uid and p['job']['job_id'] != 6 for p in gs['all_villagers'].values())
    if residents >= community.MAX_VILLAGERS or housing(gs) <= residents:
        raise ActionError('Build or upgrade huts to make room for a baby.')


def mutate(data, route, params, now=None):
    now = time.time() if now is None else now
    new = copy.deepcopy(data)
    gs = new['game_state']
    people = gs['all_villagers']
    buildings = gs['buildings']
    if route == 'game/village/set_job':
        person = get_person(gs, params)
        job_id = g.integer(params, 'job_id')
        rule = g.RULES['jobs'].get(str(job_id))
        if not rule or not rule.get('active'):
            raise ActionError('Unknown job.')
        if job_id == 46:
            skills.start_school(new, person['villager_id'], object_param(params, 'job_data'), g.RULES, now,
                                child_age=SETTINGS['baby_age'], adult_age=SETTINGS['adult_age'], hours_per_age=SETTINGS['hours_per_age'])
            return new
        if job_id == 0:
            person['job'] = g.idle_job(now)
        else:
            if hours_age(person, now) < SETTINGS['adult_age'] or person['job']['job_id'] in (1, 2, 3, 6):
                raise ActionError('This Meego cannot take a worker job.')
            extra = object_param(params, 'job_data')
            source_id = g.integer(extra, 'source_id', low=1)
            source = buildings.get(str(source_id))
            if source is None:
                raise ActionError('Job building does not exist.')
            previous_cycle=int(source.get('local_production_cycle',0))
            production.activate_for_job(gs,job_id,source_id,extra,g.RULES,now)
            if int(source.get('local_production_cycle',0))!=previous_cycle:
                progression.record_production_cycle(new,source['building_type'],source_id,
                    f"{source_id}:{source['local_production_cycle']}",now,g.RULES)
            sr = state_rule(source)
            if int(sr.get('active_job', -1)) != job_id:
                raise ActionError('That job does not match this building state.')
            workers = [p for p in people.values() if p['villager_id'] != person['villager_id'] and p['job'].get('source_id') == source_id and p['job']['job_id'] != 0]
            if len(workers) >= int(sr.get('max_workers', sr.get('villager_slots', 5))):
                raise ActionError('This building already has enough workers.')
            job = g.idle_job(now)
            job.update(job_id=job_id, source_id=source_id, target_id=source_id,
                       destination_id=g.integer(extra, 'destination_id', default=1),
                       job_start_date=int(now), update_interval=SETTINGS['gather_update_seconds'])
            if production.configure_job(source,job,g.RULES,now):
                pass
            elif job_id == 5:
                length = max(1, int(sr.get('default_length', 1)))
                job['build_rate'] = max(1, math.ceil(length / SETTINGS['construction_seconds']))
                source['expire_date'] = now + max(0, length-source['progress']) / job['build_rate']
            elif rule.get('type') == 3 or job_id == 20:
                if rule.get('type')==3 and rule.get('product_type'):
                    production.validate_depot(gs,job['destination_id'],job_id,g.RULES)
                job.update(resource_id=g.RESOURCE_IDS.get(int(rule.get('product_type') or 0), 0),
                           local_trip_seconds=0, local_fraction=0)
                job.update(gather_parameters(person,job_id,new,now))
            elif rule.get('type') == 11:
                requested_state = g.integer(extra, 'state', default=source['state'])
                if requested_state != source['state']:
                    raise ActionError('Commercial state changed. Select the building again.')
                source['expire_date'] = now + SETTINGS['construction_seconds']
            else:
                raise ActionError('This quest or school job is not available in this release candidate.')
            person['job'] = job
        person['last_update'] = now
        return new
    if route in ('game/village/update_villager_job', 'game/village/update_villager_job_destination'):
        person = get_person(gs, params)
        if route.endswith('destination'):
            dest = g.integer(params, 'destination_id', low=1)
            production.validate_depot(gs,dest,person['job']['job_id'],g.RULES)
            person['job']['destination_id'] = dest
        person['job'].update(last_update=now, update_interval=SETTINGS['gather_update_seconds'])
        person['last_update'] = now
        refresh_aging_jobs(new, now)
        source=buildings.get(str(person['job'].get('source_id',0)))
        if source:production.configure_job(source,person['job'],g.RULES,now)
        return new
    if route in ('game/village/check_breeding_compatibility', 'game/village/breed'):
        father = get_person(gs, params, 'father_id')
        mother = get_person(gs, params, 'mother_id')
        completed = new.setdefault('completed_births', {})
        supplied_token = g.text(params, 'token')
        done = completed.get(supplied_token)
        if route.endswith('/breed') and done and done['father_id']==father['villager_id'] and done['mother_id']==mother['villager_id']:
            return new
        compatible(gs, father, mother, now)
        tokens = new.setdefault('breeding_tokens', {})
        if route.endswith('check_breeding_compatibility'):
            token = uuid.uuid4().hex
            tokens[token] = dict(father_id=father['villager_id'], mother_id=mother['villager_id'], expires=now+600)
            new['response_token'] = token
        else:
            token = g.text(params, 'token')
            match = tokens.get(token)
            if not match or match['expires'] < now or match['father_id'] != father['villager_id'] or match['mother_id'] != mother['villager_id']:
                raise ActionError('Breeding request expired. Try pairing the parents again.')
            ident = g.next_id(people)
            gender = ident % 2
            appearance = [313,317,322,329,339] if gender else [335,343,347,351,355]
            baby = g.villager(ident, f'Baby {ident}', gender, appearance, int(new['game_user']['user_id']), now)
            baby.update(birthday=int(now), deathday=int(now + SETTINGS['death_age'] * 3600 * SETTINGS['hours_per_age']))
            baby['job'].update(job_id=1, target_id=mother['villager_id'], update_interval=60)
            baby=population.decorate_new(new,baby,g.RULES,parents=(father,mother))
            people[str(ident)] = baby
            progression.record_birth(new,token)
            mother['job'] = g.idle_job(now)
            mother['job'].update(job_id=3, target_id=ident, update_interval=60)
            father['job'] = g.idle_job(now)
            refresh_aging_jobs(new, now)
            completed[token] = dict(baby_id=ident, father_id=father['villager_id'], mother_id=mother['villager_id'])
            if len(completed)>64:
                del completed[next(iter(completed))]
            del tokens[token]
        return new
    if route in ('game/points/finish_building', 'game/village/update_building'):
        ident = str(g.integer(params, 'building_id', low=1))
        b = buildings.get(ident)
        if b is None:
            raise ActionError('Building does not exist.')
        sr = state_rule(b)
        if route.startswith('game/points') and sr.get('buildable'):
            remaining = max(1, SETTINGS['construction_seconds'] * (1 - b.get('progress', 0) / max(1, sr.get('default_length', 1))))
            g.charge(gs, {}, max(1, math.ceil(remaining / 60)))
            b.update(state=int(sr.get('auto_transition', b['state'])), progress=0, expire_date=0, last_update=now)
            for person in people.values():
                if person['job']['job_id'] == 5 and person['job']['source_id'] == int(ident):
                    person['job'] = g.idle_job(now)
        return new
    if route in ('game/points/speed_up_child_aging', 'game/points/speed_up_parenting'):
        person = get_person(gs, params)
        if person['job']['job_id'] == 3:
            person = people.get(str(person['job']['target_id']))
        if person is None or hours_age(person, now) >= SETTINGS['adult_age']:
            raise ActionError('Choose a baby or child.')
        age_target = SETTINGS['baby_age'] if person['job']['job_id'] == 1 else SETTINGS['adult_age']
        remaining = max(1, age_target * 3600 * SETTINGS['hours_per_age'] - (now-person['birthday']))
        g.charge(gs, {}, max(1, math.ceil(remaining / 600)))
        person['birthday'] = int(now - age_target * 3600 * SETTINGS['hours_per_age'] - 1)
        new['last_simulated_at'] = now-0.001
        return advance(new, now)
    if route == 'game/purchase/unlock_item':
        ident = g.integer(params, 'item_id', low=1)
        catalog.research_item(gs, ident, g.RULES, now)
        return new
    if route in ('game/village/assign_item_to_villager', 'game/village/remove_item_from_villager'):
        person = get_person(gs, params)
        ident = str(g.integer(params, 'item_id', low=1))
        rule = g.RULES['items'].get(ident)
        if not rule:
            raise ActionError('Unknown item.')
        if route.endswith('assign_item_to_villager'):
            item = gs['items'].get(ident)
            if not item or item['count'] <= 0:
                raise ActionError('Buy this item before equipping it.')
            if 'gender' in rule and rule['gender'] != person['gender']:
                raise ActionError('This item is for a different villager gender.')
            if ident in person['items']:
                return new
            item['count'] -= 1
            person['items'][ident] = dict(item_id=int(ident), count=1, layer=g.integer(params,'layer',default=1), cooldown=0, last_update=now)
        else:
            if ident not in person['items']:
                raise ActionError('This item is not equipped.')
            del person['items'][ident]
            item = gs['items'].setdefault(ident,dict(item_id=int(ident),count=0,last_update=now))
            item['count'] += 1
        refresh_gather_jobs(new, now)
        return new
    if route == 'game/village/use_villager_item':
        person_id=g.integer(params,'villager_id',low=1);item_id=g.integer(params,'item_id',low=1)
        if not effects.use_item(new,person_id,item_id,g.RULES,now,hours_per_age=SETTINGS['hours_per_age'],
                                child_age=SETTINGS['baby_age'],adult_age=SETTINGS['adult_age']):
            skills.use_item(new,person_id,item_id,g.RULES,now)
        refresh_aging_jobs(new,now)
        refresh_gather_jobs(new,now)
        g.synchronize(new,now)
        return new
    if route=='game/village/update_village_effect':
        g.integer(params,'effect_id',low=1)
        effects.advance(new,now,g.RULES)
        return new
    if route=='game/village/change_building':
        result=production.change_building(data,params,g.RULES,now)
        if result is not None:
            ident=str(g.integer(params,'building_id',low=1));source=result['game_state']['buildings'][ident]
            if source.get('local_production_cycle',0)!=data['game_state']['buildings'][ident].get('local_production_cycle',0):
                progression.record_production_cycle(result,source['building_type'],int(ident),
                    f"{ident}:{source['local_production_cycle']}",now,g.RULES)
            g.synchronize(result,now)
            return result
    if route == 'game/village/collect_report_cards':
        new['response_report_cards'] = skills.collect_reports(new, g.integer(params, 'building_id', low=1), now,
                                                             adult_age=SETTINGS['adult_age'], hours_per_age=SETTINGS['hours_per_age'])['report_cards']
        return new
    if route == 'game/village/confirm_dead_villager':
        person = get_person(gs, params)
        if person['job']['job_id'] != 6:
            raise ActionError('This villager is alive.')
        # The configured local game allows free resurrection.
        person['birthday'] = int(now - 20 * 3600 * SETTINGS['hours_per_age'])
        person['deathday'] = int(now + 80 * 3600 * SETTINGS['hours_per_age'])
        person['job'] = g.idle_job(now)
        return new
    result = g.mutate(data, route, params, now)
    if result is not None:
        # Replace diagnostic instant construction with real worker construction.
        if route in ('game/village/place_building','game/village/change_building'):
            old = data['game_state']['buildings']
            for key,b in result['game_state']['buildings'].items():
                if key not in old or b['state'] != old[key]['state']:
                    target = g.integer(params,'state') if route.endswith('change_building') else g.RULES['buildings'][str(b['building_type'])]['default_state']
                    if g.RULES['buildings'][str(b['building_type'])]['state_data'][str(target)].get('buildable'):
                        b.update(state=target,progress=0,expire_date=0,last_update=now)
            g.synchronize(result,now)
        if route == 'game/village/place_resource':
            for key,b in result['game_state']['buildings'].items():
                if key not in data['game_state']['buildings']:
                    b['count'] = SETTINGS['resource_stocks'][b['building_type']]
        return result
    return None

