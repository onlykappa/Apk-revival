"""Original bundled industrial cycles and paid commercial activation.

These helpers operate on an *already copied*, locked save, except
``change_building`` which returns its own copy. Stocking durations, finite stock
budgets, costs, unlocks, jobs and transitions come from the user's TechTree.
Using a stocked state's default_length as its initial count is the local
reconstruction of the unavailable server's initialization, not a recovered
server formula. Native resource UI reads count as remaining stock.

No drop rolls, commercial multiplier or accelerated production rate is invented
here. Effects must be applied separately using recovered effect data.
"""
import copy
import math

from . import local_game as g

INDUSTRIAL = frozenset((10, 13, 16))
COMMERCIAL = frozenset((11, 12, 14, 18, 19, 20, 21))
POLICY = 'bundled-production-cycles-1'


def _number(value, label, *, positive=False):
    if isinstance(value, bool):
        raise g.ActionError(f'Invalid production {label}.')
    try:
        value = float(value)
    except (ValueError, TypeError, OverflowError):
        raise g.ActionError(f'Invalid production {label}.') from None
    if not math.isfinite(value) or value < 0 or (positive and value == 0):
        raise g.ActionError(f'Invalid production {label}.')
    return value


def state_rule(source, rules):
    return rules.get('buildings', {}).get(str(source['building_type']), {}).get(
        'state_data', {}).get(str(source['state']), {})


def is_stocking(source, rules):
    return source.get('building_type') in INDUSTRIAL and bool(state_rule(source, rules).get('stocking_phase'))


def is_stocked(source, rules):
    return source.get('building_type') in INDUSTRIAL and bool(state_rule(source, rules).get('stocked_phase'))


def is_commercial(source):
    return source.get('building_type') in COMMERCIAL and source.get('state') == 11


def _stop_workers(gs, source_id, now):
    for person in gs.get('all_villagers', {}).values():
        if person.get('job', {}).get('source_id') == source_id:
            person['job'] = g.idle_job(now)
            person['last_update'] = now


def _enter(gs, source, target, rules, now):
    """Validate a normal activation, then charge once and enter its state."""
    old = state_rule(source, rules)
    building = rules['buildings'][str(source['building_type'])]
    rule = building['state_data'].get(str(target))
    if target == source['state']:
        return False  # Immediate HTTP retries never refill or restart a timer.
    if (target not in old.get('valid_transitions', []) or rule is None or
            rule.get('buildable') or source['state'] != 1 or
            not (rule.get('stocking_phase') or
                 (source['building_type'] in COMMERCIAL and target == 11))):
        raise g.ActionError('Complete the current production cycle before starting another.')
    g.require_unlocked(gs, rule)
    # Check rule values before the first debit. Original rules have integer costs.
    duration = _number(rule.get('default_length'), 'duration', positive=True)
    _number(rule.get('default_interval', 1), 'interval', positive=True)
    if rule.get('stocking_phase'):
        _number(rule.get('default_increment', 1), 'increment', positive=True)
        output = building['state_data'].get(str(rule.get('auto_transition')), {})
        if not output.get('stocked_phase'):
            raise g.ActionError('The bundled production output state is unavailable.')
        _number(output.get('default_length'), 'stock amount', positive=True)
    g.charge(gs, rule.get('counter_unit_cost', {}), int(rule.get('points_cost', 0)))
    source.update(state=target, progress=0, count=0, last_update=now,
                  expire_date=now + duration if source['building_type'] in COMMERCIAL else 0,
                  local_production_cycle=int(source.get('local_production_cycle', 0)) + 1,
                  local_production_policy=POLICY)
    _stop_workers(gs, source['building_id'], now)
    return True


def change_building(data, params, rules, now):
    """Return a copied activation, or None to let construction handle the route.

    Direct client requests to turn a working/stocked building back into an idle
    state are rejected: harvesting or expiry must finish it, preventing refills.
    """
    gs = data['game_state']
    ident = str(g.integer(params, 'building_id', low=1))
    source = gs['buildings'].get(ident)
    if source is None or source.get('building_type') not in INDUSTRIAL | COMMERCIAL:
        return None
    kind = g.integer(params, 'building_type_id', low=1)
    target = g.integer(params, 'state')
    if kind != source['building_type']:
        raise g.ActionError('The production building type does not match.')
    rule = rules['buildings'][str(kind)]['state_data'].get(str(target))
    if rule and rule.get('buildable'):
        return None
    new = copy.deepcopy(data)
    _enter(new['game_state'], new['game_state']['buildings'][ident], target, rules, now)
    return new


def activate_for_job(gs, job_id, source_id, extra, rules, now):
    """Support original stocking/operator jobs sent against idle state 1.

    Call after adult/source validation and before checking active_job. Returns
    whether this belongs to a supported cycle; caller still validates worker
    count and sets the job. Exceptions discard the caller's copied save.
    """
    source = gs['buildings'][str(source_id)]
    kind = source.get('building_type')
    if kind not in INDUSTRIAL | COMMERCIAL:
        return False
    states = rules['buildings'][str(kind)]['state_data']
    if source['state'] == 1:
        candidates = [int(key) for key, rule in states.items()
                      if int(rule.get('active_job', -1)) == job_id and
                      (rule.get('stocking_phase') or kind in COMMERCIAL)]
        if len(candidates) != 1:
            return False
        _enter(gs, source, candidates[0], rules, now)
    sr = state_rule(source, rules)
    if int(sr.get('active_job', -1)) != job_id:
        return False
    if kind in COMMERCIAL:
        requested = g.integer(extra, 'state', default=source['state'])
        if requested not in (1, source['state']):
            raise g.ActionError('Commercial state changed. Select the building again.')
        requested_kind = g.integer(extra, 'building_type_id', default=kind, low=1)
        if requested_kind != kind:
            raise g.ActionError('The operator building type does not match.')
    return True


def configure_job(source, job, rules, now):
    """Populate native worker timing from original rule duration (no 45s hack)."""
    if is_stocking(source, rules):
        rule = state_rule(source, rules)
        rate = (_number(rule.get('default_increment', 1), 'increment', positive=True) /
                _number(rule.get('default_interval', 1), 'interval', positive=True))
        remaining = max(0, _number(rule['default_length'], 'duration') -
                        _number(source.get('progress', 0), 'progress'))
        source['expire_date'] = now + remaining / rate
        source['last_update'] = now
        job.update(build_rate=rate, gather_rate=0, gather_time=0,
                   trip_time=0, update_interval=max(1, math.ceil(remaining / rate)),
                   last_update=now)
        return True
    if is_commercial(source):
        job.update(build_rate=0, gather_rate=0, gather_time=0, trip_time=0,
                   update_interval=max(1, math.ceil(source['expire_date'] - now)),
                   last_update=now)
        return True
    return False


def advance_cycles(data, now, elapsed, rules):
    """Advance each stocking source once, and expire paid commercial service.

    Call before the generic per-person simulation loop. Elapsed is the caller's
    bounded offline interval. A stopped or absent worker produces no progress;
    multiple workers cannot multiply a one-worker stocking rule.
    """
    now = _number(now, 'clock')
    elapsed = _number(elapsed, 'elapsed')
    gs = data['game_state']
    handled = set()
    for source in gs['buildings'].values():
        if is_commercial(source):
            handled.add(source['building_id'])
            deadline = _number(source.get('expire_date', 0), 'deadline')
            # A legacy 45-second operator interval is not silently replaced by
            # a free hour. Existing valid deadlines are preserved.
            if deadline and now >= deadline:
                source.update(state=1, progress=0, count=0, expire_date=0, last_update=now)
                _stop_workers(gs, source['building_id'], now)
            continue
        if not is_stocking(source, rules):
            continue
        handled.add(source['building_id'])
        rule = state_rule(source, rules)
        workers = [p for p in gs.get('all_villagers', {}).values()
                   if p.get('job', {}).get('source_id') == source['building_id'] and
                   p['job'].get('job_id') == rule.get('active_job')]
        length = _number(rule['default_length'], 'duration', positive=True)
        rate = (_number(rule.get('default_increment', 1), 'increment', positive=True) /
                _number(rule.get('default_interval', 1), 'interval', positive=True))
        progress = min(length, _number(source.get('progress', 0), 'progress'))
        if workers:
            # Original Farm/Quarry/Sawmill stocking states all allow one worker.
            # Restrict accumulation to their actually assigned interval.
            started = min(_number(p['job'].get('job_start_date', now), 'job start') for p in workers)
            interval = min(elapsed, max(0, now - started),
                           max(0, now - _number(source.get('last_update', now), 'last update')))
            progress = min(length, progress + interval * rate)
        source.update(progress=progress, last_update=now,
                      expire_date=now + (length - progress) / rate if workers else 0)
        if progress >= length:
            target = int(rule['auto_transition'])
            output = rules['buildings'][str(source['building_type'])]['state_data'][str(target)]
            amount = int(_number(output['default_length'], 'stock amount', positive=True))
            source.update(state=target, progress=0, count=amount, expire_date=0,
                          local_production_policy=POLICY)
            _stop_workers(gs, source['building_id'], now)
    return handled


def remaining_stock(source, rules):
    if not is_stocked(source, rules):
        raise g.ActionError('This building is not ready for harvesting.')
    return int(_number(source.get('count', 0), 'stock amount'))


def validate_depot(gs, destination_id, job_id, rules):
    """Require a real, resource-bearing destination in an allowed rule state.

    A merely existing hut or resource node is not a depot. Original Temple and
    Storage states expose resource_caps; incomplete states do not. Use original
    destination restrictions as well, rather than guessing valid state IDs.
    """
    if isinstance(destination_id, bool) or not isinstance(destination_id, int) or destination_id <= 0:
        raise g.ActionError('Choose a valid depot.')
    destination = gs.get('buildings', {}).get(str(destination_id))
    job = rules.get('jobs', {}).get(str(job_id), {})
    resource = g.RESOURCE_IDS.get(int(job.get('product_type') or 0))
    if destination is None or resource is None:
        raise g.ActionError('Choose a valid depot for this resource.')
    restrictions = job.get('parameter_restrictions', {}).get('destination_id', [])
    for restriction in restrictions:
        if (not isinstance(restriction, (list, tuple)) or len(restriction) != 3 or
                restriction[1] != 'in' or not isinstance(restriction[2], list) or
                destination.get(restriction[0]) not in restriction[2]):
            raise g.ActionError('This depot is not in a valid receiving state.')
    capacity = state_rule(destination, rules).get('resource_caps', {}).get(str(resource), 0)
    if _number(capacity, 'depot capacity') <= 0:
        raise g.ActionError('That building cannot receive this resource. Choose a depot.')
    return destination


def consume_stock(gs, source, delivered, rules, now):
    """Consume only credited output; stop all harvesters at exact exhaustion.

    The caller first clips delivery against destination capacity and this stock.
    No full-store work is deducted and no stock is replenished by a retry.
    """
    if isinstance(delivered, bool) or not isinstance(delivered, int) or delivered < 0:
        raise g.ActionError('Invalid production delivery.')
    count = remaining_stock(source, rules)
    if delivered > count:
        raise g.ActionError('Production delivery exceeds remaining stock.')
    if not delivered:
        return count
    source.update(count=count-delivered, last_update=now)
    if source['count'] == 0:
        target = int(state_rule(source, rules)['auto_transition'])
        source.update(state=target, progress=0, expire_date=0)
        _stop_workers(gs, source['building_id'], now)
    return source['count']
