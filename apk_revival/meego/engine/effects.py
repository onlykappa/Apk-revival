"""Owned temporary boosters and appearance/age consumables, entirely offline.

Coefficients, eligible jobs/groups, duration and reusable-item lifetime come
from the selected original APK. Composition is an explicit LOCAL overlay:
add modifiers, multiply multipliers, match explicit job IDs OR boost groups;
reusable lifetime is a cooldown measured from activation. The former server's
stacking/cooldown-start policy is not recovered. Production modifiers are
published only in final per-job values; native effect records identify the
visible icon/expiry and are not added to backend modifiers a second time. The
recovered child-play script uses native effect_id/expire_date records; its
once-per-activation child stat award is explicitly a local policy.

Settle harvesting through ``now`` BEFORE advance removes expired receipts or
use_item changes active modifiers. change_times supplies boundaries for offline
catch-up. Unsupported scripts/quests/infections fail before consuming anything.
"""
import copy
import hashlib
import math

from . import local_game as g

POLICY = 'local-item-effects-v1'
STATE_KEY = 'local_item_effects'
FIELDS = ('production_rate_modifier', 'production_rate_multiplier',
          'production_time_modifier', 'production_time_multiplier')
DEFAULTS = (0.0, 1.0, 0.0, 1.0)
CHILD_PLAY_ITEMS = (1663, 2210, 2211)
CHILD_PLAY_SCRIPT = 'JFSoccerBall.lua'
DUNGEON_BOOST_ITEMS = (1186, 1511)


def _number(value, label, minimum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise g.ActionError(f'Invalid {label}.')
    if minimum is not None and value < minimum:
        raise g.ActionError(f'Invalid {label}.')
    return float(value)


def _state(data):
    state = data.get(STATE_KEY, {'policy': POLICY, 'original_server_policy_verified': False,
                               'active': [], 'cooldowns': {}})
    if (not isinstance(state, dict) or state.get('policy') != POLICY
            or not isinstance(state.get('active'), list)
            or not isinstance(state.get('cooldowns'), dict)):
        raise g.ActionError('Unsupported local item-effect policy.')
    return state


def _inventory(data, person, item_id):
    for inventory, owner in ((person.get('items', {}), str(person['villager_id'])),
                             (data['game_state'].get('items', {}), 'village')):
        item = inventory.get(str(item_id))
        if item and int(item.get('count', 0)) > 0:
            return item, owner
    raise g.ActionError('You do not own this item.')


def _values(rule):
    values = tuple(_number(rule.get(key, default), key, 0 if 'multiplier' in key else None)
                   for key, default in zip(FIELDS, DEFAULTS))
    if values[1] <= 0 or values[3] <= 0:
        raise g.ActionError('This item has invalid production multipliers.')
    return values


def _matches(rule, job_id, rules):
    ids, groups = rule.get('job_ids', []), rule.get('job_boost_groups', [])
    job_groups = rules.get('jobs', {}).get(str(job_id), {}).get('boost_groups', [])
    return job_id in ids or bool(set(groups).intersection(job_groups))


def production_modifiers(data, person, job_id, now, rules):
    """Active production overlay; equipment and global/native boosts excluded."""
    now = _number(now, 'effect clock')
    values = list(DEFAULTS)
    for effect in (_state(data)['active'] if STATE_KEY in data else []):
        if not effect['started_at'] <= now < effect['expires_at']:
            continue
        if effect['target'] == 'self' and effect['villager_id'] != person['villager_id']:
            continue
        rule = rules.get('items', {}).get(str(effect['item_id']), {})
        if not _matches(rule, job_id, rules):
            continue
        current = _values(rule)
        values[0] += current[0]
        values[1] *= current[1]
        values[2] += current[2]
        values[3] *= current[3]
    return dict(zip(('rate_modifier', 'rate_multiplier', 'time_modifier', 'time_multiplier'), values))


def change_times(data, start, end):
    """Absolute modifier/cooldown boundaries for deterministic offline catch-up."""
    return sorted({value for entry in (_state(data)['active'] if STATE_KEY in data else [])
                   for value in (entry['started_at'], entry['expires_at']) if start < value < end})


def adventure_bonus(data, person_id, now):
    """Original active owned bonus coefficient; LOCAL non-stacking maximum.

    The adventure engine documents how it interprets this coefficient. This
    helper never grants a reward or reconstructs a missing server payout.
    """
    now = _number(now, 'adventure effect clock')
    owner = data['game_user']['user_id']
    person = data['game_state'].get('all_villagers', {}).get(str(person_id))
    if not person or person.get('user_id') != owner:
        return 0
    return max([0] + [int(entry.get('dungeon_bonus', 0))
                      for entry in (_state(data)['active'] if STATE_KEY in data else [])
                      if entry.get('villager_id') == person_id
                      and entry.get('item_id') in DUNGEON_BOOST_ITEMS
                      and entry['started_at'] <= now < entry['expires_at']])


def publish_production_effect(data, entry, rules):
    """Publish the native effect indicator; backend math still uses receipts."""
    rule=rules.get('items',{}).get(str(entry['item_id']),{})
    if entry.get('wire_effect') is not None or _values(rule)==DEFAULTS:
        return
    if entry.get('target')=='self':
        entry['wire_owner']=entry['villager_id']
        target=data['game_state']['all_villagers'][str(entry['villager_id'])]
    else:
        target=data['game_state'].setdefault('global_state',{})
    entry['wire_effect']=dict(effect_id=entry['item_id'],expire_date=math.ceil(entry['expires_at']))
    target.setdefault('effects',[]).append(copy.deepcopy(entry['wire_effect']))


def advance(data, now, rules):
    """Expire owned receipts/cooldowns AFTER prior harvesting has been settled."""
    now = _number(now, 'effect clock')
    if STATE_KEY not in data:
        return False
    state = _state(data)
    before = copy.deepcopy(state)
    # JMEffect's recovered native shape is effect_id + Unix expire_date. Remove
    # only a record created by our own receipt; retain unrelated village effects.
    for entry in state['active']:
        if entry['expires_at']>now:
            publish_production_effect(data,entry,rules)
        owned_wire = entry.get('wire_effect')
        if owned_wire is not None and entry['expires_at'] <= now:
            if entry.get('wire_owner') is not None:
                person = data['game_state'].get('all_villagers', {}).get(str(entry['wire_owner']), {})
                wire = person.get('effects', [])
            else:
                wire = data['game_state'].get('global_state', {}).get('effects', [])
            wire[:] = [record for record in wire if record != owned_wire]
    state['active'] = [entry for entry in state['active'] if entry['expires_at'] > now]
    for key, entry in list(state['cooldowns'].items()):
        owner, ident = entry['owner'], str(entry['item_id'])
        person = data['game_state'].get('all_villagers', {}).get(owner)
        inventory = data['game_state'].get('items', {}) if owner == 'village' else (person or {}).get('items', {})
        item = inventory.get(ident)
        if item is not None:
            item.update(cooldown=max(0, entry['ready_at'] - now), last_update=now)
        if entry['ready_at'] <= now:
            del state['cooldowns'][key]
    return state != before


def _new_hair(person, rule, rules, item, now):
    indices = [i for i, owned in enumerate(person.get('appearance_items', []))
               if rules.get('items', {}).get(str(owned.get('item_id')), {}).get('collection') == 'hair']
    if len(indices) != 1:
        raise g.ActionError('This Meego needs one valid birth hairstyle before a hair potion can be used.')
    index = indices[0]
    current = person['appearance_items'][index]
    old = rules['items'][str(current['item_id'])]
    candidates = []
    for key, value in rules.get('items', {}).items():
        if (not str(key).isdigit() or value.get('type') != 1 or value.get('active') is not True
                or value.get('collection') != 'hair' or value.get('gender') != person['gender']
                or value.get('given_on_birth') is not True or int(key) == current['item_id']
                or not any(r.get('layer') == 1 for r in value.get('restrictions', []))):
            continue
        same_style = value.get('base_id', value.get('image_id')) == old.get('base_id', old.get('image_id'))
        if rule.get('change_hair_colour') and not same_style:
            continue
        if rule.get('change_hair') and same_style:
            continue
        candidates.append(int(key))
    if not candidates:
        raise g.ActionError('The bundled catalog has no alternate hair for this potion.')
    # Stable within a retried transaction, different after a consumed item.
    seed = f'{person["villager_id"]}:{rule["techtree_id"]}:{current["item_id"]}:{item["count"]}:{item.get("last_update", 0)}'
    choice = sorted(candidates)[int.from_bytes(hashlib.sha256(seed.encode()).digest(), 'big') % len(candidates)]
    appearance = copy.deepcopy(person['appearance_items'])
    appearance[index] = dict(item_id=choice, count=1, layer=1, cooldown=0, last_update=now)
    return appearance


def use_item(data, person_id, item_id, rules, now, *, hours_per_age=1, child_age=2, adult_age=10):
    """Handle recoverable effects; return False for the existing stat handler.

    This operates on the caller's transaction copy. All validation precedes any
    mutation. A reusable hat keeps its owned count; a one-use booster/potion
    consumes exactly activate_count. No script-only item is silently consumed.
    """
    now = _number(now, 'effect clock')
    person_id = g.integer({'id': person_id}, 'id', low=1)
    item_id = g.integer({'id': item_id}, 'id', low=1)
    person = data['game_state'].get('all_villagers', {}).get(str(person_id))
    if person is None or person.get('user_id') != data['game_user']['user_id']:
        raise g.ActionError('Choose one of your Meegos.')
    if person.get('job', {}).get('job_id') == 6:
        raise g.ActionError('Choose a living Meego.')
    if person.get('location_type', 0) != 0:
        raise g.ActionError('This Meego is away on an adventure. Finish the adventure first.')
    rule = rules.get('items', {}).get(str(item_id))
    if not rule or int(rule.get('type', -1)) != 4:
        return False
    child_play = (item_id in CHILD_PLAY_ITEMS and rule.get('script') == CHILD_PLAY_SCRIPT
                  and rule.get('target') == 'village' and rule.get('cosmetic_effect') is True)
    if rule.get('script') and not child_play:
        raise g.ActionError('This scripted village item is not implemented offline; it was not consumed.')
    if rule.get('target') not in ('self', 'village'):
        raise g.ActionError('This infection or subset effect is not implemented offline; it was not consumed.')
    dungeon_boost = item_id in DUNGEON_BOOST_ITEMS and bool(rule.get('bonus_dungeon_reward'))
    if rule.get('bonus_questing_reward') or (rule.get('bonus_dungeon_reward') and not dungeon_boost):
        raise g.ActionError('This social-travel or unknown quest booster is not supported offline; it was not consumed.')
    affluence = _number(rule.get('affluence', 0), 'item Mojo')
    duration = _number(rule.get('duration', 0), 'item duration', 0)
    hair = bool(rule.get('change_hair') or rule.get('change_hair_colour'))
    age = bool(rule.get('add_lifetime') or 'set_age' in rule)
    if not duration and not hair and not age and not affluence:
        return False  # Preserve existing permanent self-stat semantics.
    if (hair or age) and rule.get('target') != 'self':
        raise g.ActionError('This appearance or age item must target one Meego.')
    values = _values(rule)
    if duration and values == DEFAULTS and not child_play and not dungeon_boost:
        raise g.ActionError('This item has no supported temporary production effect; it was not consumed.')
    dungeon_bonus = 0
    if dungeon_boost:
        dungeon_bonus = _number(rule['bonus_dungeon_reward'], 'dungeon bonus', 0)
        if (rule.get('target') != 'self' or duration <= 0 or not dungeon_bonus.is_integer()
                or dungeon_bonus > 100 or not isinstance(person.get('effects', []), list)):
            raise g.ActionError('This adventure booster has unsupported bundled effect fields.')
    mojo_delta = _number(data.get('local_affluence_delta', 0), 'saved item Mojo')
    additions = {stat: _number(rule.get('add_' + stat, 0), f'item {stat}')
                 for stat in ('strength', 'intelligence', 'charisma')}
    if any(not value.is_integer() for value in additions.values()):
        raise g.ActionError('Invalid item stat amount.')
    children = []
    if child_play:
        if duration <= 0 or values != DEFAULTS or rule.get('stats_target') not in (None, 'children'):
            raise g.ActionError('This child-play item has unsupported bundled effect fields.')
        if any(additions.values()) and rule.get('stats_target') != 'children':
            raise g.ActionError('This child-play item does not identify its stat recipients.')
        scale = _number(hours_per_age, 'age scale', 0) * 3600
        lower = _number(child_age, 'child age', 0)
        upper = _number(adult_age, 'adult age', 0)
        if scale <= 0 or lower >= upper:
            raise g.ActionError('Invalid child-play age configuration.')
        global_state = data['game_state'].get('global_state', {})
        if not isinstance(global_state, dict) or not isinstance(global_state.get('effects', []), list):
            raise g.ActionError('Saved village effects must be a list.')
        if any(isinstance(record, dict) and record.get('effect_id') in CHILD_PLAY_ITEMS
               and float(record.get('expire_date', 0)) > now
               for record in global_state.get('effects', [])):
            raise g.ActionError('A child-play ball is already active.')
        for child in data['game_state'].get('all_villagers', {}).values():
            if (child.get('user_id') == data['game_user']['user_id']
                    and child.get('job', {}).get('job_id') != 6
                    and lower <= (now - _number(child.get('birthday'), 'child birthday')) / scale < upper):
                children.append(child)
    item, owner = _inventory(data, person, item_id)
    state = _state(data)
    cooldown_key = f'{owner}:{item_id}'
    cooldown = state['cooldowns'].get(cooldown_key, {})
    if cooldown.get('ready_at', 0) > now:
        raise g.ActionError('This item is still cooling down.')
    # Legacy native cooldown values are remaining seconds as of last_update.
    if max(0, float(item.get('cooldown', 0)) - max(0, now - float(item.get('last_update', now)))) > 0:
        raise g.ActionError('This item is still cooling down.')
    if any(e['item_id'] == item_id and e['expires_at'] > now
           and (e['target'] == 'village' or e['villager_id'] == person_id) for e in state['active']):
        raise g.ActionError('This item is already active.')
    if child_play and any(e.get('script') == CHILD_PLAY_SCRIPT and e['expires_at'] > now
                          for e in state['active']):
        raise g.ActionError('A child-play ball is already active.')
    consume = g.integer({'count': rule.get('activate_count', 1)}, 'count')
    if consume > int(item['count']):
        raise g.ActionError('You do not own enough of this item.')
    if not consume and not duration:
        raise g.ActionError('This reusable item has no supported timed activation.')
    lifetime = _number(rule.get('lifetime', 0), 'reusable-item cooldown', 0) if not consume else 0
    if duration and not consume and lifetime < duration:
        raise g.ActionError('This reusable item has an invalid cooldown.')
    appearance = _new_hair(person, rule, rules, item, now) if hair else None
    dates = None
    if age:
        scale = _number(hours_per_age, 'age scale', 0) * 3600
        if scale <= 0:
            raise g.ActionError('Invalid age scale.')
        birthday = _number(person['birthday'], 'birthday')
        deathday = _number(person['deathday'], 'deathday')
        if 'set_age' in rule:
            new_birthday = now - _number(rule['set_age'], 'target age', 0) * scale
            delta = new_birthday - birthday
        else:
            delta = _number(rule['add_lifetime'], 'lifetime change') * scale
        # add_lifetime>0 means younger; shift both dates to preserve lifespan.
        delta = min(delta, now - birthday)
        dates = (birthday + delta, deathday + delta)
    # Validation complete: caller will persist this transaction atomically.
    if appearance is not None:
        person['appearance_items'] = appearance
    if dates is not None:
        person.update(birthday=int(dates[0]), deathday=int(dates[1]))
    if affluence:
        # Recalculation must add this receipt to original building affluence;
        # altering only the native-facing sum would disappear on next refresh.
        data['local_affluence_delta'] = mojo_delta + affluence
        from . import skills
        for stat, amount in additions.items():
            if amount:
                skills._gain(person, stat, int(amount))
    item.update(count=int(item['count']) - consume, last_update=now, cooldown=lifetime)
    person['last_update'] = now
    if duration:
        entry = dict(item_id=item_id, villager_id=person_id, target=rule['target'],
                     started_at=now, expires_at=now + duration)
        if dungeon_boost:
            entry.update(dungeon_bonus=int(dungeon_bonus), wire_owner=person_id,
                         wire_effect=dict(effect_id=item_id, expire_date=now + duration))
            person.setdefault('effects', []).append(copy.deepcopy(entry['wire_effect']))
        if child_play:
            # The bundled Lua owns animation/selection and has no payout call.
            # LOCAL reward policy: apply its explicit add_* to children present
            # at activation once, capped by the existing consumable helper.
            # duration expires the visible ball; it does not subtract earned
            # base stats later or grant stats to future newborns/reopens.
            from . import skills
            for child in children:
                for stat, amount in additions.items():
                    if amount:
                        skills._gain(child, stat, int(amount))
                if any(additions.values()):
                    child['last_update'] = now
            entry.update(script=CHILD_PLAY_SCRIPT,
                         local_reward_policy='existing-owned-children-once-at-activation',
                         rewarded_villager_ids=[child['villager_id'] for child in children]
                         if any(additions.values()) else [])
            entry['wire_effect'] = dict(effect_id=item_id, expire_date=now + duration)
            data['game_state'].setdefault('global_state', {}).setdefault('effects', []).append(
                copy.deepcopy(entry['wire_effect']))
        publish_production_effect(data,entry,rules)
        state['active'].append(entry)
    if lifetime:
        state['cooldowns'][cooldown_key] = dict(owner=owner, item_id=item_id, ready_at=now + lifetime)
    data[STATE_KEY] = state
    return True
