"""Private, bounded requests to the existing library window.

Only library actions and legacy Dolphin APK imports are accepted. Requests do
not carry commands or choose result paths. The live window owns all runtime
operations, authorization prompts, workers, and shutdown behavior.
"""
import hashlib
import itertools
import json
import math
import os
import pathlib
import re
import stat
import time
import uuid

from ..util import RevivalError, atomic_json

ACTIONS = frozenset({'play', 'stop', 'restart-runtime', 'quit'})
LIFETIME = 300
MAX_PENDING = 64
MAX_PER_POLL = 32
MAX_BYTES = 16 * 1024
ID_PATTERN = re.compile(r'[0-9a-f]{32}')
GAME_PATTERN = re.compile(r'[0-9a-f]{24}')
RESULT_STATES = frozenset({'queued', 'running', 'succeeded', 'failed', 'cancelled', 'accepted'})


def _private_directory(root, name):
    path = pathlib.Path(root) / name
    if path.is_symlink():
        raise RevivalError(f'Launcher {name} must be a private directory, not a symlink.')
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)
    return path


def _action(store, action, game):
    if not isinstance(action, str) or action not in ACTIONS:
        raise RevivalError('Unknown library request action.')
    if action == 'play':
        if not isinstance(game, str) or not GAME_PATTERN.fullmatch(game):
            raise RevivalError('Play requires a valid 24-character library game ID.')
        try:
            profile = store.load(game, check=False)
        except (OSError, ValueError, KeyError, RevivalError) as error:
            raise RevivalError('The requested game is not available in this library.') from error
        if not isinstance(profile, dict) or profile.get('id') != game:
            raise RevivalError('The requested game profile is inconsistent.')
    elif game is not None:
        raise RevivalError('Only Play accepts a game ID.')


def enqueue(store, action, game=None):
    """Queue a validated library action; return its ID and local file paths.

    Poll ``result_file`` for state/error/job_id. Queuing does not start another
    runtime or application instance. The normal launcher must be running.
    """
    _action(store, action, game)
    requests = _private_directory(store.root, 'open-requests')
    results = _private_directory(store.root, 'open-results')
    if sum(1 for _ in itertools.islice(requests.glob('*.json'), MAX_PENDING)) >= MAX_PENDING:
        raise RevivalError('The library request queue is full. Wait for APK Revival to finish its current task.')
    ident = uuid.uuid4().hex
    request_file = requests / (ident + '.json')
    result_file = results / (ident + '.json')
    now = time.time()
    value = dict(id=ident, action=action, created_at=now, expires_at=now + LIFETIME)
    if game is not None:
        value['game'] = game
    atomic_json(result_file, dict(id=ident, action=action, state='queued', error=None, job_id=None))
    try:
        atomic_json(request_file, value)
    except Exception:
        result_file.unlink(missing_ok=True)
        raise
    return dict(id=ident, request_file=str(request_file), result_file=str(result_file))


def _request_id(path):
    if ID_PATTERN.fullmatch(path.stem):
        return path.stem
    # Invalid filenames still get a deterministic safe failure report. Never
    # use an untrusted embedded ID, absolute path, or traversal as a target.
    return hashlib.sha256(path.name.encode()).hexdigest()[:32]


def _read_request(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES:
            raise RevivalError('Invalid or oversized library request file.')
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise RevivalError('Library request exceeds its size limit.')
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise RevivalError('Library request must be a JSON object.')
    return value, info.st_mtime


def _clock(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise RevivalError('Invalid library request timestamp.')
    return float(value)


def _validate(store, path, value, modified, now):
    if not ID_PATTERN.fullmatch(path.stem):
        raise RevivalError('Invalid library request filename.')
    if set(value) == {'apk'}:
        if modified > now + 5:
            raise RevivalError('Invalid APK import request timestamp.')
        if now >= modified + LIFETIME:
            raise RevivalError('APK import request expired. Open the APK again.')
        if not isinstance(value['apk'], str):
            raise RevivalError('Invalid APK import path.')
        apk = pathlib.Path(value['apk']).expanduser()
        if not apk.is_file() or apk.suffix.lower() != '.apk':
            raise RevivalError('APK import requires an existing APK file.')
        return str(apk)
    if set(value) - {'id', 'action', 'game', 'created_at', 'expires_at'}:
        raise RevivalError('Unsupported fields in library request.')
    if value.get('id') != path.stem:
        raise RevivalError('Library request ID does not match its filename.')
    created = _clock(value.get('created_at'))
    expires = _clock(value.get('expires_at'))
    if expires <= created or expires > created + LIFETIME or created > now + 5:
        raise RevivalError('Invalid library request lifetime.')
    if now >= expires:
        raise RevivalError('Library request expired. Try the action again.')
    _action(store, value.get('action'), value.get('game'))
    return None


def _busy(window):
    # Even a finished QThread stays owned until its finished signal is handled.
    return bool(getattr(window, 'worker', None) or getattr(window, 'monitor_worker', None))


def _order(path):
    try:
        return path.lstat().st_mtime_ns, path.name
    except OSError:
        return 0, path.name


def process_requests(window):
    """Dispatch bounded queued requests; return the number consumed this poll.

    ``window.run_library_request(value, reply)`` returns True when it owns the
    action, False when it must wait. False keeps the request on disk. ``reply``
    accepts either a dict or state/error/job_id keyword arguments and may be
    called later by normal worker callbacks. Accepted requests are removed,
    preventing a second dispatch. Legacy APK imports use ``window.open_apk``.
    """
    store = window.service.store
    requests = _private_directory(store.root, 'open-requests')
    results = _private_directory(store.root, 'open-results')
    consumed = 0
    now = time.time()
    # Bound directory inventory too. Creation order prevents an arbitrarily
    # sorted UUID from dispatching a queued Stop or Quit before its prior Play.
    pending = itertools.islice(requests.glob('*.json'), MAX_PENDING)
    for path in sorted(pending, key=_order)[:MAX_PER_POLL]:
        ident = _request_id(path)
        destination = results / (ident + '.json')
        replied = [False]

        def reply(value=None, *, state=None, error=None, job_id=None,
                  _destination=destination, _ident=ident, _replied=replied):
            if value is not None:
                if not isinstance(value, dict):
                    raise RevivalError('Library result must be an object.')
                state, error, job_id = value.get('state'), value.get('error'), value.get('job_id')
            if state not in RESULT_STATES:
                raise RevivalError('Invalid library result state.')
            if job_id is not None and (not isinstance(job_id, str) or not ID_PATTERN.fullmatch(job_id)):
                raise RevivalError('Invalid library result job identity.')
            atomic_json(_destination, dict(id=_ident, state=state,
                                          error=str(error)[:4000] if error is not None else None,
                                          job_id=job_id))
            _replied[0] = True

        try:
            value, modified = _read_request(path)
            apk = _validate(store, path, value, modified, now)
            if _busy(window):
                break
            if apk is not None:
                window.raise_()
                window.activateWindow()
                window.open_apk(apk)
                reply(state='accepted')  # Import completion belongs to its normal UI job.
                accepted = True
            else:
                accepted = window.run_library_request(value, reply)
                if accepted is not True and accepted is not False:
                    raise RevivalError('Library handler did not acknowledge its request.')
                if accepted and not replied[0]:
                    reply(state='running')
            if not accepted:
                break
        except Exception as error:
            reply(state='failed', error=str(error))
        else:
            if not accepted:
                continue
        path.unlink(missing_ok=True)
        consumed += 1
    return consumed
