"""Local newcomer policy, using the original client's owned-villager model.

The six-hour schedule is a restoration choice: the original server's arrival
schedule and stat distribution have not been recovered. This module neither
simulates another user's guests nor claims original-server balance.
"""
import math

from . import local_game as g, population

INTERVAL_SECONDS = 6 * 3600
POLICY = 'local-newcomers-6h-v1'
STATE_KEY = 'local_community'
MAX_VILLAGERS = 25  # TechTree client_data/0/max_villager_count in Meego 1.32.
MAX_ID = 2147483647
APPEARANCE = {
    1: (313, 317, 322, 329, 339),
    0: (335, 343, 347, 351, 355),
}


def _number(value, label):
    if isinstance(value, bool):
        raise ValueError(f'Invalid newcomer {label}.')
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError(f'Invalid newcomer {label}.') from None
    if not math.isfinite(result):
        raise ValueError(f'Invalid newcomer {label}.')
    return result


def _ident(value):
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value if value > 0 else 0
    if isinstance(value, str) and value.isascii() and value.isdigit():
        return int(value)
    return 0


def _next_id(people, cursor=1):
    # Check dictionary keys AND native model IDs. Reserve a persisted cursor so
    # removal of a dead villager cannot reuse a previous newcomer's identifier.
    largest = max((_ident(v) for k, p in people.items()
                   for v in (k, p.get('villager_id'))), default=0)
    result = max(_ident(cursor), largest + 1, 1)
    if result > MAX_ID:
        raise ValueError('No free newcomer villager identifier remains.')
    return result


def _limit(rules):
    bundled = (rules or {}).get('client_data', {}).get('0', {}).get(
        'max_villager_count', MAX_VILLAGERS)
    value = _ident(bundled)
    return min(MAX_VILLAGERS, value or MAX_VILLAGERS)


def _name(rules, gender, count):
    names = (rules or {}).get('client_data', {}).get('7', {}).get(
        'villager_names', {}).get('male' if gender == 1 else 'female', [])
    names = [n for n in names if isinstance(n, str) and n.strip()]
    # These fallback names also occur in the original bundled name pools.
    return names[(count // 2) % len(names)] if names else ('Mert' if gender else 'Nooni')


def advance(data, now, *, housing_capacity, rules=None, hours_per_age=1):
    """Mutate an already-copied save; return the new owned villager ID or None.

    The caller must hold its save lock and persist the result, including the
    first call that initializes a deadline without adding anyone. Call after
    aging/deaths have advanced, then expose the usual full game-state response.
    All scheduling metadata lives at the save root under ``local_community``;
    none of it enters the native game-state payload.

    Migration starts a fresh six-hour clock. An overdue check adds at most one
    adult and schedules six hours from this check. A full island also discards
    its overdue opportunity; it cannot accumulate queued arrivals. Living owned
    travellers reserve their home beds. Guests and dead job-6 models use no
    permanent slots, and every existing model and unrelated save field remains.
    Clock rollback never produces an arrival.
    """
    now = _number(now, 'clock')
    age_scale = _number(hours_per_age, 'age scale')
    capacity = _number(housing_capacity, 'capacity')
    if age_scale <= 0 or capacity < 0 or not capacity.is_integer():
        raise ValueError('Invalid newcomer age scale or capacity.')
    rules = g.RULES if rules is None else rules
    uid = _ident(data['game_user']['user_id'])
    if not uid:
        raise ValueError('Invalid newcomer village owner.')
    people = data['game_state']['all_villagers']
    state = data.get(STATE_KEY)
    if state is None:
        data[STATE_KEY] = dict(policy=POLICY, original_server_policy_verified=False,
                               next_due=now + INTERVAL_SECONDS,
                               last_checked_at=now, next_villager_id=_next_id(people),
                               arrival_count=0)
        return None
    if not isinstance(state, dict) or state.get('policy') != POLICY:
        raise ValueError('Unsupported local newcomer policy. Save was not changed.')
    due = _number(state.get('next_due'), 'deadline')
    checked = _number(state.get('last_checked_at'), 'previous clock')
    if now <= checked:
        return None
    if now < due:
        state['last_checked_at'] = now
        return None
    owned = sum(_ident(p.get('user_id')) == uid and
                _ident(p.get('job', {}).get('job_id')) != 6
                for p in people.values())
    if owned >= min(int(capacity), _limit(rules)):
        state.update(next_due=now + INTERVAL_SECONDS, last_checked_at=now)
        return None
    ident = _next_id(people, state.get('next_villager_id'))
    count = state.get('arrival_count')
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise ValueError('Invalid newcomer arrival count. Save was not changed.')
    gender = 1 if count % 2 == 0 else 0
    person = g.villager(ident, _name(rules, gender, count), gender,
                        APPEARANCE[gender], uid, now)
    person.update(birthday=int(now - 20 * age_scale * 3600),
                  deathday=int(now + 80 * age_scale * 3600))
    person = population.decorate_new(data, person, rules)
    people[str(ident)] = person
    state.update(next_due=now + INTERVAL_SECONDS, last_checked_at=now,
                 next_villager_id=ident + 1, arrival_count=count + 1,
                 last_arrival_at=now)
    return ident
