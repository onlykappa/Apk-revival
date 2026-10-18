"""Half-speed closed-session aging, preserving the native absolute date model."""
import math

OFFLINE_RATE = 0.5


def _date(value):
    return type(value) in (int, float) and math.isfinite(value)


def slow_offline(data, previous, now):
    """Shift living owned villagers' age dates by the unaged half of the gap.

    Call once before simulation splits effect boundaries or clips work catch-up.
    last_simulated_at remains the authoritative replay/rollback guard. No dates
    already settled before this update are rewritten. Real task deadlines and
    food balances are independent of aging.
    """
    if not _date(previous) or not _date(now):
        raise ValueError('Invalid aging clock.')
    if now <= previous:
        return
    people = data['game_state']['all_villagers']
    owner = data['game_user']['user_id']
    for person in people.values():
        birthday = person.get('birthday')
        deathday = person.get('deathday')
        if (person.get('user_id') != owner or not _date(birthday)
                or person.get('job', {}).get('job_id') == 6
                or (_date(deathday) and deathday <= previous)):
            continue
        shift = max(0, now - max(previous, birthday)) * (1 - OFFLINE_RATE)
        person['birthday'] = birthday + shift
        person['local_offline_age_seconds'] = person.get('local_offline_age_seconds', 0) + shift
        if _date(deathday):
            person['deathday'] = deathday + shift
        if shift:
            person['last_update'] = now
    # Adventures keep a separate render/work snapshot of the same owned people.
    for session in data.get('local_adventures_v1', {}).get('sessions', {}).values():
        for ident, person in session.get('game_state', {}).get('all_villagers', {}).items():
            home = people.get(ident)
            if home:
                for key in ('birthday', 'deathday', 'local_offline_age_seconds'):
                    if key in home:
                        person[key] = home[key]
