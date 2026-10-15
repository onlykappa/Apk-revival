"""One bounded reconnect of an already-owned game and local backend.

This helper never starts a container, session, activity or service. It neither
installs packages nor replaces a backend. The caller decides when repeated
failed monitor checks warrant normal session cleanup.
"""
import ipaddress
import json
import re

from ..util import RevivalError


def _alive(backend):
    thread = getattr(backend, 'thread', None)
    return thread is not None and thread.is_alive()


def _port(value):
    return isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 65535


def _probe(runtime, backend):
    # probe_backend already performs the guest-to-host request using the
    # current backend's fresh nonce. Require the actual JSON token as well,
    # rather than accepting its occurrence in a header or unrelated field.
    response = runtime.probe_backend(timeout=5)
    if not isinstance(response, str) or len(response) > 65536:
        raise RevivalError('The backend health response was invalid.')
    normalized = response.replace('\r\n', '\n')
    headers, separator, body = normalized.partition('\n\n')
    if not separator or not re.match(r'^HTTP/1\.[01] 200(?:\s|$)', headers):
        raise RevivalError('The backend health request did not succeed.')
    try:
        health = json.loads(body)
    except (TypeError, ValueError):
        raise RevivalError('The backend health response was not JSON.') from None
    token = getattr(backend, 'token', None)
    if (not isinstance(token, str) or not token or not isinstance(health, dict)
            or health.get('token') != token):
        raise RevivalError('The backend health response belongs to a different service.')


def recover(manager, runtime, active):
    """Return recovered/paused/failed while retaining caller-owned objects.

    Discovery uses exactly ``discover(connect=True, probe_timeout=3)``. Only
    its reported current managed IP and matching connected ADB device qualify.
    A verified guest becomes the current runtime/active serial even if its game
    or service probe subsequently fails. Unverified devices never change them.

    When a live backend owns its matching ``forward_port``, probe it first. If
    needed, rebind that one TCP reverse and verify the same fresh service nonce.
    No port-wide removals, new backend instances, or lifecycle methods occur.
    Each health probe uses a five-second timeout; pid and the single reverse
    operation use three seconds. A known failed managed display check returns
    failure without restarting the compositor or Android.
    """
    try:
        info = manager.discover(connect=True, probe_timeout=3)
        if not isinstance(info, dict) or not info.get('waydroid'):
            return {'state': 'failed', 'detail': 'The managed Android runtime could not be verified.'}
        session = str(info.get('session', '')).upper()
        container = str(info.get('container', '')).upper()
        if 'FROZEN' in (session, container) and session in {'RUNNING', 'FROZEN'} and container in {'RUNNING', 'FROZEN'}:
            return {'state': 'paused', 'detail': 'Android is frozen or paused; the game and local service remain owned.'}
        if session != 'RUNNING' or container != 'RUNNING':
            return {'state': 'failed', 'detail': 'The managed Android session or container is stopped.'}
        try:
            address = ipaddress.ip_address(info.get('ip'))
        except (ValueError, TypeError):
            return {'state': 'failed', 'detail': 'The managed Android guest has no verified current address.'}
        serial = str(address) + ':5555'
        devices = info.get('devices', [])
        if not info.get('ready') or not any(isinstance(device, dict) and
                device.get('serial') == serial and device.get('state') == 'device'
                for device in devices):
            return {'state': 'failed', 'detail': 'The current managed guest is not connected; unrelated ADB devices were ignored.'}
        display_check = getattr(manager, 'check_managed_display', None)
        if callable(display_check) and display_check(info) is False:
            return {'state': 'failed', 'detail': 'The managed game display is unavailable; recovery did not restart Android or its compositor.'}
        package = getattr(runtime, 'package', None)
        if not isinstance(package, str) or not re.fullmatch(r'[A-Za-z0-9_.]+', package):
            return {'state': 'failed', 'detail': 'The owned game package could not be verified.'}
        runtime.serial = serial
        active['serial'] = serial
        pid = runtime.shell('pidof', package, timeout=3).strip()
        if not re.fullmatch(r'\d+(?:\s+\d+)*', pid):
            return {'state': 'failed', 'detail': 'Android reconnected, but the owned game process is not running.'}
        backend = getattr(runtime, 'backend', None)
        if backend is not None:
            if not _alive(backend):
                return {'state': 'failed', 'detail': 'The owned local service has stopped; it was preserved for normal cleanup.'}
            port = getattr(backend, 'port', None)
            if not _port(port) or getattr(runtime, 'forward_port', None) != port:
                return {'state': 'failed', 'detail': 'The local reverse port is not owned by this game; recovery did not rebind it.'}
            try:
                _probe(runtime, backend)
            except (RevivalError, OSError, ValueError):
                if runtime.backend is not backend or not _alive(backend) or runtime.forward_port != port:
                    return {'state': 'failed', 'detail': 'The owned service changed during recovery; its connections were preserved.'}
                runtime.adb('reverse', f'tcp:{port}', f'tcp:{port}', timeout=3)
                _probe(runtime, backend)
        return {'state': 'recovered', 'detail': 'Reconnected the current Android guest and verified the owned game and service.'}
    except Exception as error:
        return {'state': 'failed', 'detail': 'The single connection recovery check failed: ' + str(error)[:2000]}
