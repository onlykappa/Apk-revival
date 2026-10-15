"""Conserved local food consumption in the native client's per-minute units.

The client displays an integer consumption rate per minute; its original
server's per-villager coefficient and guest/traveller policy are unrecovered.
One food per owned, present, living resident per minute is the local policy.
"""
import math

STATE_KEY = 'local_food'
POLICY = 'local-resident-food-per-minute-v1'
FOOD_PER_RESIDENT_PER_MINUTE = 1
TIME_UNITS = 1_000_000
UNITS_PER_FOOD = 60 * TIME_UNITS


def _clock(value):
    if isinstance(value, bool):
        raise ValueError('Invalid food simulation clock.')
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError('Invalid food simulation clock.') from None
    if not math.isfinite(value):
        raise ValueError('Invalid food simulation clock.')
    return value


def _integer(value, label):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'Invalid food simulation {label}.')
    return value


def _owner(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str) and value.isascii() and value.isdigit():
        return int(value) or None
    return None


def consumption_rate(data, *, food_per_resident_per_minute=FOOD_PER_RESIDENT_PER_MINUTE):
    """Return the native integer per-minute rate for owned residents at home."""
    coefficient = _integer(food_per_resident_per_minute, 'rate')
    uid = _owner(data['game_user']['user_id'])
    if uid is None:
        raise ValueError('Invalid food simulation village owner.')
    residents = sum(_owner(p.get('user_id')) == uid and
                    p.get('location_type') == 0 and
                    _owner(p.get('location_id')) == uid and
                    p.get('job', {}).get('job_id') != 6
                    for p in data['game_state']['all_villagers'].values())
    return residents * coefficient


def advance(data, previous, now, *, maximum_elapsed=86400,
            food_per_resident_per_minute=FOOD_PER_RESIDENT_PER_MINUTE):
    """Charge a copied save once; return the whole units actually consumed.

    Call after aging/deaths and before newcomers, under the existing save lock.
    ``previous`` is the existing last_simulated_at before it is updated.
    Absolute clock endpoints in integer microseconds conserve fractional food
    across repeated polling and JSON restarts. Migration starts at this check,
    retaining the old food_fraction and balance without charging any elapsed
    interval under the former hourly policy. Clock rollback and repeated
    intervals never charge twice.

    Offline elapsed is bounded, empty stores accumulate no debt, and the native
    global_state rate always uses the same per-minute units as actual charging.
    All bookkeeping stays outside the native game-state payload.
    """
    previous, now = _clock(previous), _clock(now)
    maximum_elapsed = _clock(maximum_elapsed)
    if maximum_elapsed < 0:
        raise ValueError('Invalid food simulation offline limit.')
    rate = consumption_rate(data, food_per_resident_per_minute=food_per_resident_per_minute)
    resource = data['game_state']['resources']['3']
    balance = _integer(resource.get('count'), 'balance')
    state = data.get(STATE_KEY)
    if state is None:
        fraction = _clock(data.get('food_fraction', 0))
        if not 0 <= fraction < 1:
            raise ValueError('Invalid legacy food fraction.')
        state = dict(policy=POLICY, original_server_policy_verified=False,
                     last_charged_at=max(previous, now),
                     fraction_units=round(fraction * UNITS_PER_FOOD))
    elif not isinstance(state, dict) or state.get('policy') != POLICY:
        raise ValueError('Invalid local food policy. Save was not changed.')
    charged = _clock(state.get('last_charged_at'))
    fraction_units = _integer(state.get('fraction_units'), 'fraction')
    if fraction_units > UNITS_PER_FOOD:
        raise ValueError('Invalid local food fraction. Save was not changed.')
    baseline = max(previous, charged)
    elapsed_units = min(max(0, round(now * TIME_UNITS) - round(baseline * TIME_UNITS)),
                        round(maximum_elapsed * TIME_UNITS))
    if elapsed_units:
        whole, remainder = divmod(fraction_units + elapsed_units * rate, UNITS_PER_FOOD)
        consumed = min(whole, balance)
        balance -= consumed
        # A hungry village cannot retain debt against newly harvested food.
        fraction_units = remainder if balance else 0
        if consumed:
            resource.update(count=balance, last_update=now)
    else:
        consumed = 0
    state.update(last_charged_at=max(charged, now), fraction_units=fraction_units)
    data[STATE_KEY] = state
    data['food_fraction'] = fraction_units / UNITS_PER_FOOD
    data['game_state'].setdefault('global_state', {})['food_consumption_rate'] = rate
    return consumed
