"""Explicit local cheats. Never fast-forward the island clock or expose HTTP routes."""
import copy
import hashlib
import json
import math

from . import ecology, effects, local_game as g, production, simulation, skills

NATIVE_ROUTES = frozenset(('game/points/speed_up_parenting',
                          'game/points/speed_up_child_aging', 'game/points/finish_building'))


def skip_native(data, route, params, now):
    """Adapt existing countdown callbacks only for a verified modded client."""
    gs = data['game_state']
    if g.text(params, 'partial').lower() == 'true':
        raise g.ActionError('Use Skip timer to finish the selected task.')
    if route.endswith('/finish_building'):
        ident = str(g.integer(params, 'building_id', low=1))
        kind = 'building'
    else:
        ident = str(g.integer(params, 'villager_id', low=1))
        person = gs['all_villagers'].get(ident)
        if route.endswith('/speed_up_parenting'):
            baby_id = str(g.integer(params, 'baby_id', low=1))
            baby = gs['all_villagers'].get(baby_id)
            if (person is None or baby is None or person['job']['job_id'] != 3
                    or str(person['job'].get('target_id')) != baby_id or baby['job']['job_id'] != 1):
                raise g.ActionError('This nursing timer finished or changed. Reopen the baby panel.')
            ident = baby_id
        elif person is None or person['job']['job_id'] != 2:
            raise g.ActionError('This childhood timer finished or changed. Reopen the child panel.')
        kind = 'growth'
    choice = next((t for t in timers(data, now) if t['kind'] == kind and t['ident'] == ident), None)
    if choice is None:
        raise g.ActionError('This timer is no longer active. Reopen its panel.')
    return skip(data, choice['token'], now)


def timers(data, now):
    """Read-only choices; tokens identify a task generation, not a moving countdown."""
    result = []
    gs = data['game_state']

    def add(kind, ident, title, seconds, generation):
        if not math.isfinite(seconds) or seconds <= 0:
            return
        token = hashlib.sha256(json.dumps([kind, str(ident), generation], sort_keys=True).encode()).hexdigest()
        result.append(dict(kind=kind, ident=str(ident), title=title,
                           seconds=math.ceil(seconds), token=token))

    for ident, node in gs['buildings'].items():
        rule = production.state_rule(node, g.RULES)
        name = g.RULES['buildings'].get(str(node['building_type']), {}).get('name', 'Building')
        if ident in data.get('school_sessions', {}):
            session = data['school_sessions'][ident]
            add('school', ident, f'{name} #{ident}: class', session['ends_at'] - now,
                [session['started_at'], session['active_state']])
        elif rule.get('buildable') or production.is_stocking(node, g.RULES):
            remaining = float(rule.get('default_length', 0)) - float(node.get('progress', 0))
            workers = [p['job'] for p in gs['all_villagers'].values()
                       if p.get('location_type', 0) == 0 and p['job'].get('source_id') == node['building_id']]
            if rule.get('buildable'):
                rate = sum(float(j.get('build_rate', 0)) for j in workers if j['job_id'] == 5)
                phase = 'construction / upgrade'
            else:
                rate = (float(rule.get('default_increment', 1)) / float(rule.get('default_interval', 1))
                        if any(j['job_id'] == rule.get('active_job') for j in workers) else 0)
                phase = 'production preparation'
            if rate > 0:
                add('building', ident, f'{name} #{ident}: {phase}', remaining / rate,
                    [node['building_type'], node['state'], node.get('local_production_cycle', 0),
                     sorted((j['job_id'], j.get('job_start_date')) for j in workers)])
    for ident, person in gs['all_villagers'].items():
        jid = person['job']['job_id']
        if person.get('location_type', 0) != 0 or jid not in (1, 2):
            continue
        age = simulation.SETTINGS['baby_age' if jid == 1 else 'adult_age']
        deadline = person['birthday'] + age * 3600 * simulation.SETTINGS['hours_per_age']
        add('growth', ident, f"{person['name']}: {'baby to child' if jid == 1 else 'child to adult'}",
            deadline - now, [round(float(person['birthday'] - person.get('local_offline_age_seconds', 0)), 6), jid])
    for key, entry in data.get(effects.STATE_KEY, {}).get('cooldowns', {}).items():
        name = g.RULES.get('items', {}).get(str(entry['item_id']), {}).get('name', str(entry['item_id']))
        add('cooldown', key, f'{name}: cooldown (owner {entry["owner"]})',
            entry['ready_at'] - now, entry['ready_at'])
    eco = data.get(ecology.STATE_KEY)
    if eco and any(sum(b['building_type'] == kind for b in gs['buildings'].values()) < cap
                   and any(s['kind'] == kind and ecology._available(s, gs['buildings'], g.RULES)
                           for s in eco.get('sites', [])) for kind, cap in ecology.RESOURCE_LIMITS.items()):
        add('respawn', 'resources', 'Next resource respawn (five-per-kind cap applies)',
            eco['next_due'] - now, [eco['next_due'], eco['replenishment_count']])
    return result


def skip(data, token, now):
    """Copy-on-write, one selected completion, no costs or extra reward rolls."""
    selected = next((t for t in timers(data, now) if t['token'] == token), None)
    if selected is None:
        raise g.ActionError('This timer finished or changed. Refresh Mods and select it again.')
    new = copy.deepcopy(data)
    gs = new['game_state']
    kind, ident = selected['kind'], selected['ident']
    if kind == 'building':
        node = gs['buildings'][ident]
        rule = production.state_rule(node, g.RULES)
        if production.is_stocking(node, g.RULES):
            node['progress'] = rule['default_length']
            production.advance_cycles(new, now, 0, g.RULES)
        else:
            target = rule.get('auto_transition')
            if target is None or str(target) not in g.RULES['buildings'][str(node['building_type'])]['state_data']:
                raise g.ActionError('This building has no supported completion state.')
            node.update(state=int(target), progress=0, expire_date=0, last_update=now)
            for person in gs['all_villagers'].values():
                if person['job'].get('source_id') == node['building_id'] and person['job']['job_id'] == 5:
                    person['job'] = g.idle_job(now)
                    person['last_update'] = now
    elif kind == 'school':
        new['school_sessions'][ident]['ends_at'] = now
        skills.advance_school(new, now)
    elif kind == 'growth':
        person = gs['all_villagers'][ident]
        baby = person['job']['job_id'] == 1
        age = simulation.SETTINGS['baby_age' if baby else 'adult_age']
        birthday = int(now - age * 3600 * simulation.SETTINGS['hours_per_age'])
        # Keep the remaining adult lifespan, rather than creating an early death.
        person['birthday'] = birthday
        person.update(last_update=now, job=g.idle_job(now))
        person['job']['job_id'] = 2 if baby else 0
        simulation.refresh_aging_jobs(new, now)
    elif kind == 'cooldown':
        new[effects.STATE_KEY]['cooldowns'][ident]['ready_at'] = now
        effects.advance(new, now, g.RULES)
    elif kind == 'respawn':
        new[ecology.STATE_KEY].update(next_due=now, last_checked_at=now - 0.001)
        ecology.advance(new, now, rules=g.RULES, stocks=ecology.resource_stocks(new, g.RULES))
    g.synchronize(new, now)
    history = new.setdefault('local_mod_history', [])
    history.append(dict(mod='skip_timer', target=selected['title'], token=token, time=now))
    del history[:-100]
    return new, selected['title']
