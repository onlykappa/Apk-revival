"""Persistent offline simulation for the recovered Meego client protocol."""
import copy
import json
import math
import time
import uuid
from pathlib import Path
from . import local_game as g

SETTINGS = {'construction_seconds': 45, 'gather_update_seconds': 10, 'resource_stock': 500, 'maximum_offline_seconds': 86400, 'hours_per_age': 1, 'baby_age': 2, 'adult_age': 10, 'elder_age': 65, 'death_age': 100, 'food_per_villager_per_hour': 1}
ActionError = g.ActionError


def state_rule(b):
    return g.RULES['buildings'][str(b['building_type'])]['state_data'][str(b['state'])]


def hours_age(v, now):
    return max(0, (now - v['birthday']) / (3600 * SETTINGS['hours_per_age']))


def housing(gs):
    return sum(int(state_rule(b).get('villager_slots', 0)) for b in gs['buildings'].values()
               if b['building_type'] == 5 and not state_rule(b).get('buildable'))


def advance(data, now=None):
    now = time.time() if now is None else now
    new = copy.deepcopy(data)
    gs = new['game_state']
    if 'last_simulated_at' not in new:
        new['last_simulated_at'] = now
        return new
    previous = float(new['last_simulated_at'])
    if now <= previous:
        return new
    elapsed = min(now - previous, SETTINGS['maximum_offline_seconds'])
    limits = g.caps(gs)
    people = gs['all_villagers']
    buildings = gs['buildings']
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
        if age >= SETTINGS['death_age'] and job_id != 6:
            person['job'] = g.idle_job(now); person['job']['job_id'] = 6
            continue
        source = buildings.get(str(job.get('source_id', 0)))
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
                rate = float(job.get('gather_rate', 1))
                fractional = elapsed * rate + float(job.get('local_fraction', 0))
                credit = int(fractional)
                job['local_fraction'] = fractional - credit
                available = int(source.get('count', SETTINGS['resource_stock'])) if source['building_type'] in (2, 3, 4) else credit
                balance = gs['resources'][str(resource)]
                credit = min(credit, max(0, limits[resource] - balance['count']), available)
                balance['count'] += credit
                balance['last_update'] = now
                if source['building_type'] in (2, 3, 4):
                    source['count'] = max(0, available - credit)
                    source['last_update'] = now
                    if source['count'] == 0:
                        del buildings[str(source['building_id'])]
                        person['job'] = g.idle_job(now)
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
                    # Commercial operators grant a small permanent stat boost.
                    stat = {11: 'charisma', 12: 'strength', 14: 'intelligence'}.get(source['building_type'], 'strength')
                    person['stats'][stat] += 1
                person['job'] = g.idle_job(now)
        person['job']['last_update'] = now
        person['job']['update_interval'] = SETTINGS['gather_update_seconds']
        person['last_update'] = now
    for b in list(buildings.values()):
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
    food_accumulated = new.get('food_fraction', 0) + elapsed * len([p for p in people.values() if p['job']['job_id'] != 6]) * SETTINGS['food_per_villager_per_hour'] / 3600
    consumed = int(food_accumulated)
    new['food_fraction'] = food_accumulated - consumed
    gs['resources']['3']['count'] = max(0, gs['resources']['3']['count'] - consumed)
    gs['global_state']['food_consumption_rate'] = len(people) * SETTINGS['food_per_villager_per_hour']
    new['last_simulated_at'] = now
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
    if len(gs['all_villagers']) >= 25 or housing(gs) <= len(gs['all_villagers']):
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
            if job_id == 5:
                length = max(1, int(sr.get('default_length', 1)))
                job['build_rate'] = max(1, math.ceil(length / SETTINGS['construction_seconds']))
                source['expire_date'] = now + max(0, length-source['progress']) / job['build_rate']
            elif rule.get('type') == 3 or job_id == 20:
                destination = buildings.get(str(job['destination_id']))
                if rule.get('type') == 3 and rule.get('product_type') and destination is None:
                    raise ActionError('Choose a valid depot.')
                job.update(resource_id=g.RESOURCE_IDS.get(int(rule.get('product_type') or 0), 0),
                           gather_rate=1.0 + person['stats']['strength'] / 20.0,
                           gather_time=8, trip_time=4)
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
            if str(dest) not in buildings:
                raise ActionError('Depot does not exist.')
            person['job']['destination_id'] = dest
        person['job'].update(last_update=now, update_interval=SETTINGS['gather_update_seconds'])
        person['last_update'] = now
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
            people[str(ident)] = baby
            mother['job'] = g.idle_job(now)
            mother['job'].update(job_id=3, target_id=ident, update_interval=60)
            father['job'] = g.idle_job(now)
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
        rule = g.RULES['items'].get(str(ident))
        if not rule or not rule.get('research_points'):
            raise ActionError('This item has no research unlock.')
        cursors = gs['unlock_information']['unlocked_item_cursors']
        if any(a <= ident <= b for a,b in cursors):
            return new
        if gs['achievements']['102']['level'] < rule.get('research_temple_level', 1):
            raise ActionError('Upgrade the temple before researching this item.')
        g.charge(gs, {'372':int(rule['research_points'])})
        cursors.append([ident,ident])
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
                    b['count'] = SETTINGS['resource_stock']
        return result
    return None
