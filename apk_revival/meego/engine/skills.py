"""Recovered Meego stat/item wire contract with explicitly local growth policy.

Helpers mutate a caller-owned transaction copy, never persist or touch Android.
Pass actual credited resource units to credit_work, not trips or elapsed seconds.
Work gains (one point per 60 units) and school rewards (+1 INT) are local choices;
the original server's coefficients and grade odds were not recovered. Equipment
bonuses remain in native item properties and must not be added to base stats.
Backend-only progress lives outside game_state/all_villagers to preserve the
native model. Use the returned collect_reports wrapper directly on the wire.
"""
import copy
import hashlib
import json

from . import local_game as g

STATS = ('strength', 'intelligence', 'charisma')
ITEM_STAT_CAP = 1799  # Explicit original consumable item descriptions.
WORK_UNITS_PER_POINT = 60  # Local policy, not an original server threshold.
WORK_PROGRESS_MIGRATION = 'credited-work-units-1'
SCHOOL_SECONDS = 3600  # Original jobs 46/47 and building active-state rules.


def _person(data, ident):
    ident = g.integer({'id': ident}, 'id', low=1)
    person = data['game_state']['all_villagers'].get(str(ident))
    if person is None:
        raise g.ActionError('That Meego does not exist.')
    return person


def _gain(person, stat, amount):
    old = int(person['stats'].get(stat, 0))
    # Above-cap saves are preserved; positive items cannot lower their stats.
    new = max(old, min(ITEM_STAT_CAP, old + amount)) if amount >= 0 else max(0, old + amount)
    person['stats'][stat] = new
    return new - old


def migrate_work_progress(data):
    """Keep earned stats and unfinished progress when switching trips to units.

    Old saves do not record each trip's actual resource delivery. Preserve the
    old remainder numerically as a minimum earned credit instead of resetting
    it or inventing retroactive yields. No immediate stat reward is fabricated.
    This marker and progress are saved in the caller's normal transaction.
    """
    migrations = data.setdefault('local_migrations', [])
    if WORK_PROGRESS_MIGRATION in migrations:
        return False
    migrations.append(WORK_PROGRESS_MIGRATION)
    return True


def credit_work(data, person_id, job_id, credited_units, now):
    """Award local work gains only for resource units the economy delivered.

    Harvesting -> STR; Thinking Rock -> INT. Construction, commercial jobs,
    idle, and unsupported travel do not receive invented harvest rewards.
    Persist data.skill_progress with the same transaction as resource credit.
    """
    person = _person(data, person_id)
    units = g.integer({'units': credited_units}, 'units')
    stat = ('intelligence' if job_id == 20 else
            'strength' if job_id in (16, 17, 18, 19, 23, 25, 29, 32, 33, 34, 35, 39) else None)
    if not stat or not units:
        return 0
    migrate_work_progress(data)
    progress = data.setdefault('skill_progress', {}).setdefault(str(person['villager_id']), {})
    gained, remainder = divmod(int(progress.get(stat, 0)) + units, WORK_UNITS_PER_POINT)
    progress[stat] = remainder
    changed = _gain(person, stat, gained)
    if changed:
        person['last_update'] = now
    return changed


def use_item(data, person_id, item_id, rules, now):
    """Consume one owned permanent self stat item; success wire value is full GS.

    Reject temporary boosters, village gifts, equipment, cooldowns and scripts
    whose original activation semantics are not implemented here. They must not
    silently become permanent stats. Repeating a depleted-item request fails.
    """
    person = _person(data, person_id)
    ident = str(g.integer({'item_id': item_id}, 'item_id', low=1))
    rule = rules.get('items', {}).get(ident)
    if not rule:
        raise g.ActionError('Unknown item.')
    additions = {stat: int(rule.get('add_' + stat, 0)) for stat in STATS}
    random_amount = int(rule.get('add_random_stat', 0))
    if (int(rule.get('type', -1)) != 4 or rule.get('target') != 'self' or
            int(rule.get('duration', 0)) != 0 or rule.get('script') or
            not (any(additions.values()) or random_amount)):
        raise g.ActionError('This item is a temporary boost, equipment, or unsupported gift; it cannot be used as a permanent stat item.')
    if person.get('job', {}).get('job_id') == 6:
        raise g.ActionError('Choose a living Meego.')
    # A consumable may already have moved into this villager's inventory through
    # assign_item_to_villager. Equipment is excluded by the rule check above.
    item = person.get('items', {}).get(ident)
    if not item or int(item.get('count', 0)) < 1:
        item = data['game_state'].get('items', {}).get(ident)
    if not item or int(item.get('count', 0)) < 1:
        raise g.ActionError('You do not own this consumable item.')
    if float(item.get('cooldown', 0)) > 0:
        raise g.ActionError('This item is still cooling down.')
    if random_amount:
        # Stable selection across a retried/restarted transaction; inventory
        # changes after consumption, allowing subsequent items another choice.
        key = f'{person_id}:{ident}:{item["count"]}:{person.get("last_update", 0)}'
        selected = STATS[int.from_bytes(hashlib.sha256(key.encode()).digest()[:4], 'little') % len(STATS)]
        additions[selected] += random_amount
    for stat, amount in additions.items():
        if amount:
            _gain(person, stat, amount)
    item['count'] -= 1
    item['last_update'] = now
    person['last_update'] = now


def _age(person, now, hours_per_age):
    return max(0, (now - float(person['birthday'])) / (3600 * hours_per_age))


def start_school(data, teacher_id, job_data, rules, now, *, child_age=2, adult_age=10, hours_per_age=1):
    """Validate native teacher job_data and start persisted one-hour training.

    Invoke before ordinary set_job age restrictions. No changes occur until
    teacher, school, requested transition and every student are validated.
    """
    teacher = _person(data, teacher_id)
    school_id = str(g.integer(job_data, 'source_id', low=1))
    school = data['game_state']['buildings'].get(school_id)
    if school is None or int(school['building_type']) != 30:
        raise g.ActionError('Choose a completed Skool.')
    if g.integer(job_data, 'building_type_id', low=1) != 30:
        raise g.ActionError('That school type does not match.')
    states = rules['buildings']['30']['state_data']
    current = states.get(str(school['state']), {})
    requested = g.integer(job_data, 'state')
    active = states.get(str(requested), {})
    if requested not in current.get('valid_transitions', []) or int(active.get('active_job', -1)) != 46:
        raise g.ActionError('Skool must be complete and ready for a class.')
    if school_id in data.get('school_sessions', {}) or data.get('school_reports', {}).get(school_id):
        raise g.ActionError('Finish this class and collect its report cards first.')
    if _age(teacher, now, hours_per_age) < adult_age or teacher['job']['job_id'] in (1, 2, 3, 6, 46, 47, 48):
        raise g.ActionError('Choose an available adult teacher.')
    ids = job_data.get('child_villager_ids', [])
    if isinstance(ids, str):
        try:
            ids = json.loads(ids)
        except (ValueError, TypeError):
            raise g.ActionError('Invalid student list.') from None
    if not isinstance(ids, list):
        raise g.ActionError('Invalid student list.')
    capacity = int(active.get('max_workers', 0)) - 1
    if not ids or len(ids) > capacity:
        raise g.ActionError('Choose students within this Skool capacity.')
    students = [_person(data, ident) for ident in ids]
    canonical = [int(p['villager_id']) for p in students]
    if len(set(canonical)) != len(canonical) or int(teacher_id) in canonical:
        raise g.ActionError('Each student must be a different child.')
    for person in students:
        age = _age(person, now, hours_per_age)
        remaining = (adult_age - age) * 3600 * hours_per_age
        if not child_age <= age < adult_age or remaining < SCHOOL_SECONDS or person['job']['job_id'] not in (0, 2):
            raise g.ActionError('Choose available children with at least one hour before adulthood.')
    # Everything is validated before this transaction copy is changed.
    for person, job_id in [(teacher, 46)] + [(p, 47) for p in students]:
        person['job'] = g.idle_job(now)
        person['job'].update(job_id=job_id, source_id=int(school_id), target_id=int(school_id),
                             update_interval=60)
        person['last_update'] = now
    school.update(state=requested, progress=0, last_update=now, expire_date=now + SCHOOL_SECONDS)
    data.setdefault('school_sessions', {})[school_id] = {
        'teacher_id': int(teacher_id), 'student_ids': canonical,
        'started_at': now, 'ends_at': now + SCHOOL_SECONDS,
        'active_state': requested, 'idle_state': int(active['auto_transition']),
        'local_reward_policy': 'one-intelligence-per-completed-class',
    }


def advance_school(data, now, *, adult_age=10, hours_per_age=1):
    """Complete each saved class once; cancel a class missing its teacher.

    Cancellation releases matching student jobs without changing a teacher's
    new job or inventing grades/rewards. Completed students still wait in the
    original post-class job48 until their report cards have been collected.
    """
    completed = 0
    sessions = data.get('school_sessions', {})
    for ident, session in list(sessions.items()):
        school = data['game_state']['buildings'].get(ident)
        people = data['game_state']['all_villagers']
        teacher = people.get(str(session['teacher_id']))
        def enrolled(person, expected_job):
            return (person is not None and person['job'].get('source_id') == int(ident)
                    and person['job']['job_id'] == expected_job)
        valid = (school is not None and school['building_type'] == 30
                 and school['state'] == session['active_state']
                 and enrolled(teacher, 46)
                 and any(enrolled(people.get(str(i)), 47) for i in session['student_ids']))
        if valid and now < session['ends_at']:
            continue
        reports = {}
        for person_id in [session['teacher_id']] + session['student_ids']:
            student = person_id in session['student_ids']
            person = people.get(str(person_id))
            if not enrolled(person, 47 if student else 46):
                continue
            if valid and student:
                gained = _gain(person, 'intelligence', 1)
                reports[str(person_id)] = {'success': 1, 'stat_count': gained, 'stat': 'INT'}
            person['job'] = g.idle_job(now)
            if valid and student:
                person['job'].update(job_id=48, source_id=int(ident), target_id=int(ident))
            elif student and _age(person, now, hours_per_age) < adult_age:
                person['job']['job_id'] = 2
            person['last_update'] = now
        if school is not None and school['building_type'] == 30 and school['state'] == session['active_state']:
            school.update(state=session['idle_state'], progress=0, expire_date=0, last_update=now)
        if valid:
            data.setdefault('school_reports', {})[ident] = reports
            completed += 1
        del sessions[ident]
    return completed


def collect_reports(data, building_id, now, *, adult_age=10, hours_per_age=1):
    """Return original {game_state, report_cards} wrapper and consume reports.

    advance_school should precede this call in the same saved transaction.
    Repeated collection returns empty reports and never awards points again.
    """
    ident = str(g.integer({'building_id': building_id}, 'building_id', low=1))
    building = data['game_state']['buildings'].get(ident)
    if building is None or int(building['building_type']) != 30:
        raise g.ActionError('That Skool does not exist.')
    reports = data.get('school_reports', {}).pop(ident, {})
    for person_id in reports:
        person = data['game_state']['all_villagers'].get(person_id)
        if person and person['job']['job_id'] == 48 and person['job']['source_id'] == int(ident):
            person['job'] = g.idle_job(now)
            if _age(person, now, hours_per_age) < adult_age:
                person['job']['job_id'] = 2
            person['last_update'] = now
    return {'game_state': copy.deepcopy(data['game_state']), 'report_cards': copy.deepcopy(reports)}
