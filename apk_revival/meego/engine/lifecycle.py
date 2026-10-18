"""Owned Meego death resolution and stat-preserving return to age twenty."""
import copy
import math

from . import local_game as g

REMOVED_KEY = 'local_removed_villagers'
RESTORE_RECEIPTS = 'local_villager_restores'


def _boolean(params, key, default):
    value = params.get(key, [default])
    if isinstance(value, list):
        if len(value) != 1:
            raise g.ActionError('Choose one death resolution.')
        value = value[0]
    if isinstance(value,str):
        value=value.lower()
    if value is True or value == 'true':
        return True
    if value is False or value == 'false':
        return False
    raise g.ActionError('Invalid death resolution.')


def resolve(data, params, now, *, hours_per_age=1, death_age=100):
    """Handle original alive=true revival / alive=false burial parameters.

    The new native stats control reuses the same reviewed alive=true callback
    for a living adult. Existing identity, stats, equipment, skill progress and
    partial work remain intact. Short retry receipts cannot reset age repeatedly.
    """
    ident = str(g.integer(params, 'villager_id', low=1))
    restore = _boolean(params, 'alive', True)  # Preserve the old local API.
    _boolean(params, 'use_points', False)  # Free local policy for both buttons.
    new = copy.deepcopy(data)
    state = new['game_state']
    person = state['all_villagers'].get(ident)
    if person is None:
        if not restore and ident in new.get(REMOVED_KEY, {}):
            return new
        raise g.ActionError('This Meego is unavailable.')
    if person.get('user_id') != new['game_user']['user_id'] or not g.at_home(person):
        raise g.ActionError('Return this owned Meego home before changing their age.')
    scale = 3600 * hours_per_age
    if not math.isfinite(scale) or scale <= 0 or not math.isfinite(now):
        raise g.ActionError('Invalid villager age clock.')
    dead = person['job']['job_id'] == 6 or now >= person['deathday']
    if not restore:
        if not dead:
            raise g.ActionError('Only a tombstone can be cleared. Living Meego are kept.')
        # Persist an explicit removal for the native merge-only villager cache.
        del state['all_villagers'][ident]
        removed = new.setdefault(REMOVED_KEY, {})
        removed[ident] = now
        for key in sorted(removed, key=removed.get)[:-512]:
            del removed[key]
        new.get(RESTORE_RECEIPTS, {}).pop(ident, None)
        new.get('skill_progress', {}).pop(ident, None)
        _release_parent(new, int(ident), now)
        return new
    receipts = new.setdefault(RESTORE_RECEIPTS, {})
    receipt = receipts.get(ident)
    if not dead and receipt and 0 <= now - receipt['time'] < 60:
        return new
    if not dead and (now - person['birthday']) / scale < 20:
        raise g.ActionError('Return to 20 is available for Meego aged 20 or older.')
    span = max(death_age * scale, person['deathday'] - person['birthday'])
    person.update(birthday=int(now - 20 * scale), deathday=int(now - 20 * scale + span),
                  last_update=float(now))
    # Age-date offsets belong to the previous life/age generation.
    person.pop('local_offline_age_seconds', None)
    if dead:
        person.update(job=g.idle_job(now), quest=None, dungeon_quest=None)
        _release_parent(new, int(ident), now)
    receipts[ident] = {'time': now, 'revived': dead}
    live = state['all_villagers']
    for key in list(receipts):
        if key not in live:
            del receipts[key]
    return new


def _release_parent(data, ident, now):
    for person in data['game_state']['all_villagers'].values():
        if person.get('job', {}).get('job_id') == 3 and person['job'].get('target_id') == ident:
            person.update(job=g.idle_job(now), last_update=now)
