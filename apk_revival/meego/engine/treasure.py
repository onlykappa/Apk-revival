"""Original bird/egg transport with explicitly local, bounded reward policy.

Pure helpers: callers persist the returned copy atomically before replying.
See ../TREASURE_RULES.md for static evidence and limits.
"""
import base64
import copy
import hmac
import itertools
import json
import math
import secrets

from . import local_game as g

STATE_KEY = 'local_treasure_v1'
OPPORTUNITY_SECONDS = 3600
# Original details total 150 seconds; five seconds cover callback/clock skew.
SESSION_SECONDS = 155
KEYS = ('payout_number', 'token', 'minigame_type')


def _clock(now):
    if isinstance(now, bool) or not isinstance(now, (int, float)) or not math.isfinite(now) or now < 0:
        raise g.ActionError('Invalid treasure clock.')
    return float(now)


def _details(rules):
    details = rules.get('client_data', {}).get('8', {}).get('mini_game_details_1', {})
    if not details or any(details.get(k) != v for k, v in
                          (('idle_duration', 60), ('game_duration', 30), ('reward_duration', 60))):
        raise g.ActionError('The original bird mini-game timing data is unavailable.')
    return details


def poll(data, params, rules, now):
    """Return (new save, direct JMMiniGame); polling itself awards nothing."""
    now = _clock(now)
    kind = g.integer(params, 'minigame_type', default=1, low=1, high=11)
    if kind != 1:
        raise g.ActionError('Only the original island bird mini-game is supported offline.')
    _details(rules)
    new = copy.deepcopy(data)
    state = new.setdefault(STATE_KEY, {'next_opportunity': now + OPPORTUNITY_SECONDS})
    session = state.get('session')
    # Do not re-trigger the bird animation or generate new tokens on polls/restarts.
    launch = False
    if now >= float(state['next_opportunity']) and (not session or now >= session['expire_date']):
        session = dict(token=secrets.token_hex(24), minigame_type=1, level=1,
                       start_date=now, expire_date=now + SESSION_SECONDS,
                       claimed_payout=None)
        state['session'] = session
        # No backlog/catch-up sessions after a long offline interval.
        state['next_opportunity'] = now + OPPORTUNITY_SECONDS
        launch = True
    if session:
        model = {k: session[k] for k in ('token', 'minigame_type', 'level', 'start_date', 'expire_date')}
    else:
        model = dict(token='', minigame_type=1, level=1, start_date=now,
                     expire_date=now)
    model.update(new_session=launch, next_poll_date=state['next_opportunity'], last_update=now)
    return new, model


def _payload(params):
    raw = params.get('data')
    if isinstance(raw, list):
        if len(raw) != 1:
            raise g.ActionError('Invalid treasure reward data.')
        raw = raw[0]
    if isinstance(raw, str):
        if len(raw) > 2048:
            raise g.ActionError('Invalid treasure reward data.')
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError('duplicate key')
                result[key] = value
            return result
        try:
            raw = json.loads(raw, object_pairs_hook=unique)
        except (ValueError, TypeError):
            raise g.ActionError('Invalid treasure reward JSON.')
    if not isinstance(raw, dict) or set(raw) != set(KEYS):
        raise g.ActionError('Treasure reward data must contain exactly payout_number, token and minigame_type.')
    if type(raw['payout_number']) is not int or not 0 <= raw['payout_number'] <= 5:
        raise g.ActionError('Invalid treasure payout number.')
    if type(raw['minigame_type']) is not int or raw['minigame_type'] != 1:
        raise g.ActionError('Invalid treasure mini-game type.')
    token = raw['token']
    if not isinstance(token, str) or len(token) != 48 or any(c not in '0123456789abcdef' for c in token):
        raise g.ActionError('Invalid treasure token.')
    return raw


def valid_signature(payload, signature):
    """Check recovered ASCII HMAC-SHA256/base64, tolerating dictionary order.

    The native JSON writer's hash-table order is unspecified. There are exactly
    six compact encodings of the three whitelisted ASCII scalar fields. Testing
    those preserves validation without trusting arbitrary client canonicalization.
    """
    if not isinstance(signature, str) or len(signature) != 44:
        return False
    try:
        digest = base64.b64decode(signature, validate=True)
    except (ValueError, TypeError):
        return False
    if len(digest) != 32:
        return False
    for order in itertools.permutations(KEYS):
        encoded = json.dumps({key: payload[key] for key in order}, separators=(',', ':'), ensure_ascii=True).encode('ascii')
        expected = hmac.digest(payload['token'].encode('ascii'), encoded, 'sha256')
        if hmac.compare_digest(expected, digest):
            return True
    return False


def retrieve(data, params, rules, now):
    """Return (new save, native reward envelope), rejecting invalid signatures."""
    now = _clock(now)
    _details(rules)
    payload = _payload(params)
    signature = params.get('signature', '')
    if isinstance(signature, list):
        signature = signature[0] if len(signature) == 1 else ''
    if not valid_signature(payload, signature):
        raise g.ActionError('Treasure reward signature is invalid.')
    session = data.get(STATE_KEY, {}).get('session')
    if not session or not hmac.compare_digest(payload['token'], session['token']):
        raise g.ActionError('This treasure session is no longer available.')
    if now < session['start_date'] or now >= session['expire_date']:
        raise g.ActionError('This treasure session has expired or has not started.')
    previous = session.get('claimed_payout')
    if previous is not None and previous != payload['payout_number']:
        raise g.ActionError('This treasure session reward was already collected.')
    new = copy.deepcopy(data)
    points = 0 if previous is not None else 1
    if points:
        new['game_state']['points'] = int(new['game_state'].get('points', 0)) + points
        new[STATE_KEY]['session']['claimed_payout'] = payload['payout_number']
    return new, dict(game_state=copy.deepcopy(new['game_state']), points_reward=points, item_rewards={})
