#!/usr/bin/env python3
"""Experimental local responder for the original Meego client.
Response fields are recovered where noted, defaults are provisional.
No claim of complete gameplay compatibility. No upstream network requests.
"""
import argparse, copy, datetime, ipaddress, json, math, os, tempfile, threading, time, signal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from .local_game import migrate, synchronize, ActionError, integer
from .simulation import advance, mutate, migrate_economy, housing, refresh_aging_jobs, SETTINGS
from . import community, catalog, ecology, skills, food, birthstones, treasure, scripted_items, adventures, local_game as g

HERE = Path(__file__).resolve().parent
PACKAGE = 'ata.apkrv.meego'
SENSITIVE = ('token', 'secret', 'authorization', 'mac_key', 'password', 'facebook', 'signature')

def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.save-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(value, f, indent=2); f.flush(); os.fsync(f.fileno())
        os.replace(tmp, path)
        directory = os.open(path.parent, os.O_DIRECTORY)
        try: os.fsync(directory)
        finally: os.close(directory)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def redact(params):
    if isinstance(params,list):return [redact(value) for value in params]
    if not isinstance(params,dict):return params
    result={}
    for key,value in params.items():
        if any(s in key.lower() for s in SENSITIVE):result[key]='[redacted]'
        elif key=='data':
            if isinstance(value,list) and len(value)!=1:
                result[key]='[redacted]'
                continue
            raw=value[0] if isinstance(value,list) and len(value)==1 else value
            if isinstance(raw,str):
                try:raw=json.loads(raw)
                except ValueError:raw='[redacted]'
            result[key]=redact(raw)
        else:result[key]=redact(value)
    return result

def native_payload(value, game_state=None):
    """Project saved building timers onto the native no-expiry wire contract.

    JMBuilding treats a missing expire_date as NSDate.distantFuture. Sending
    our internal zero instead means Unix epoch and causes endless overdue
    building updates/loading spinners. Keep saves and real deadlines intact;
    job timers and resource balances have different contracts.
    """
    if isinstance(value, dict):
        if {'all_villagers', 'buildings'} <= value.keys():game_state=value
        elif isinstance(value.get('game_state'), dict):game_state=value['game_state']
        result = {key: native_payload(item, game_state) for key, item in value.items()}
        if {'building_id', 'building_type', 'state'} <= value.keys() and value.get('expire_date') == 0:
            result.pop('expire_date', None)
        if 'villager_id' in value and isinstance(value.get('job'), dict) and game_state:
            job=result['job'];source=game_state.get('buildings',{}).get(str(job.get('source_id')))
            if source:
                rule=g.RULES.get('buildings',{}).get(str(source.get('building_type')),{}).get('state_data',{}).get(str(source.get('state')), {})
                finite=source.get('building_type') in (2,3,4) or rule.get('stocked_phase')
                count=source.get('count');rate=job.get('gather_rate')
                if (finite and isinstance(count,(int,float)) and not isinstance(count,bool)
                        and isinstance(rate,(int,float)) and not isinstance(rate,bool)
                        and math.isfinite(count) and math.isfinite(rate) and count>0 and rate>count):
                    # The final pickup can be smaller than a full normal trip.
                    # Keep authoritative rates/fractions in the save unchanged.
                    job['gather_rate']=count
        return result
    if isinstance(value, list):
        return [native_payload(item, game_state) for item in value]
    return value

def initial_village(seed, when=None, rules=None):
    """A fresh local village without the earlier test economy bonuses.

    Exact original server starting balances have not been recovered. Keep this
    provenance explicit rather than presenting local defaults as vanilla parity.
    """
    when = time.time() if when is None else when
    data = {'format_version': 1, 'created_at': when, 'last_simulated_at': when,
            'game_user': copy.deepcopy(seed['game_user']),
            'game_state': copy.deepcopy(seed['game_state']),
            'local_migrations': ['starter-economy-1', 'completed-trips-2'],
            'start_profile': {'name': 'no-bonus-local-village',
                              'original_server_defaults_verified': False}}
    state = data['game_state']
    for resource in state['resources'].values():resource.update(count=0, last_update=when)
    state['points'] = 0
    for person in state['all_villagers'].values():
        person.update(birthday=int(when-20*3600), deathday=int(when+80*3600), last_update=when)
        person['job'].update(job_start_date=int(when), last_update=when)
    synchronize(data, when, rules=rules)
    community.advance(data, when, housing_capacity=housing(state, rules), rules=rules)
    return data

class State:
    def __init__(self, directory, seed=None):
        self.directory = Path(directory).expanduser()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.save = self.directory / 'saves' / 'village.json'
        self.lock = threading.RLock()
        self.action_notice = None
        self.logfile = self.directory / 'logs' / 'requests.jsonl'
        self.logfile.parent.mkdir(parents=True, exist_ok=True)
        # Preserve the old retry storm without adding it to every diagnostic ZIP.
        if self.logfile.exists() and self.logfile.stat().st_size > 5 * 1024 * 1024:
            self.logfile.rename(self.logfile.with_name(f'requests-before-{time.time_ns()}.jsonl.bak'))
        self.seed = copy.deepcopy(seed) if seed is not None else json.loads((HERE / 'starter-packet.json').read_text())
        if self.save.exists():
            # A malformed save is reported, never silently replaced.
            self.data = json.loads(self.save.read_text())
            if self.data.get('format_version') != 1:
                raise ValueError('Unsupported save format. Existing save was not changed.')
        else:
            self.data = initial_village(self.seed)
            atomic_json(self.save, self.data)
        if self.data['game_user'].get('avatar_type')==0:
            new = copy.deepcopy(self.data)
            new['game_user']['avatar_type']=self.seed['game_user']['avatar_type']
            self.persist(new)
        buildings = self.data['game_state'].get('buildings', {})
        if not any(isinstance(b,dict) and b.get('building_type')==1 for b in buildings.values()):
            new = copy.deepcopy(self.data)
            next_id = max([int(k) for k in buildings if str(k).isdigit()]+[0])+1
            temple = copy.deepcopy(self.seed['game_state']['buildings']['1'])
            temple['building_id'] = next_id
            new['game_state'].setdefault('buildings', {})[str(next_id)] = temple
            self.persist(new)
            print('Backed up and repaired the test scaffold: added required level-one temple.', flush=True)
        migrated = migrate(self.data)
        if migrated is not None:
            self.persist(migrated)
            print('Backed up and added starter population, balances and temple unlocks.', flush=True)
        new = copy.deepcopy(self.data)
        migrate_economy(new, time.time())
        ecology.upgrade_bush_stock(new)
        skills.migrate_work_progress(new)
        catalog.normalize_research_cursors(new['game_state'], g.RULES)
        refresh_aging_jobs(new, time.time())
        if ecology.STATE_KEY not in new:
            ecology.advance(new, time.time(), rules=g.RULES, stocks=SETTINGS['resource_stocks'])
        if community.STATE_KEY not in new:
            community.advance(new, time.time(), housing_capacity=housing(new['game_state']))
        if food.STATE_KEY not in new:
            food.advance(new, time.time(), time.time())
        birthstones.discover_owned(new, g.RULES.get('birthsigns', {}))
        if new != self.data:self.persist(new)
    def record(self, route, params, status, error=None):
        record = {'time': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  'route': route, 'parameters': redact(params), 'status': status}
        if error:
            # Record only our own action description, never request credentials.
            record['error'] = {key: error[key] for key in ('title','message','reason') if key in error}
        with self.lock, self.logfile.open('a') as f:
            f.write(json.dumps(record) + '\n')
            if error:self.action_notice = str(error.get('message','Game action rejected.'))
        print(route, status, flush=True)
    def take_action_notice(self):
        with self.lock:
            message = self.action_notice
            self.action_notice = None
            return message
    def persist(self, new):
        if self.save.exists():
            backups = self.directory / 'backups'; backups.mkdir(exist_ok=True)
            old = json.loads(self.save.read_text())
            atomic_json(backups / f'village-{time.time_ns()}.json', old)
            for p in sorted(backups.glob('village-*.json'))[:-20]: p.unlink()
        atomic_json(self.save, new)
        self.data = new
    def packet(self):
        with self.lock:
            result = copy.deepcopy(self.seed)
            result.update(game_user=copy.deepcopy(self.data['game_user']),
                          game_state=copy.deepcopy(self.data['game_state']),
                          server_time=time.time(), host_ip_address='127.0.0.1')
            return result
    def handle(self, route, params):
        route = route.strip('/')
        with self.lock:
            now = time.time()
            current = advance(self.data, now)
            if current != self.data:
                self.persist(current)
            try:
                if route in adventures.ROUTES:
                    new,response=adventures.handle(self.data,route,params,g.RULES,now)
                    g.synchronize(new,now)
                    food.advance(new,now,now)
                    # Refresh the returned island snapshot after synchronization;
                    # preserve the separate original dungeon stage snapshot.
                    if isinstance(response,dict) and 'game_state' in response:
                        response['game_state']=copy.deepcopy(new['game_state'])
                    if new!=self.data:self.persist(new)
                    return response,'local-solo-adventure'
                if route == 'game/gift/open_gift':
                    new,response=scripted_items.open_gift(self.data,params,g.RULES,now)
                    if new!=self.data:self.persist(new)
                    return response,'local-owned-scripted-gift'
                if route in ('game/village/get_treasure_mini_game','game/village/retrieve_treasure_mini_game_reward'):
                    helper=treasure.poll if route.endswith('/get_treasure_mini_game') else treasure.retrieve
                    new,response=helper(self.data,params,g.RULES,now)
                    if new!=self.data:self.persist(new)
                    return response,'local-treasure-session'
                new = mutate(self.data, route, params, now)
                if new is not None:
                    birthstones.discover_owned(new, g.RULES.get('birthsigns', {}))
                    g.synchronize(new,now)
                    food.advance(new, now, now)
                    if new != self.data:
                        self.persist(new)
                    if route == 'game/village/check_breeding_compatibility':
                        return {'token': self.data['response_token'], 'game_state': copy.deepcopy(self.data['game_state'])}, 'local-breeding-token'
                    if route == 'game/village/collect_report_cards':
                        return {'game_state': copy.deepcopy(self.data['game_state']), 'report_cards': copy.deepcopy(self.data.get('response_report_cards', {}))}, 'local-report-cards'
                    if route == 'game/village/change_villager_name':
                        ident = str(integer(params, 'villager_id', low=1))
                        return copy.deepcopy(self.data['game_state']['all_villagers'][ident]), 'saved-local-action'
                    return copy.deepcopy(self.data['game_state']), 'saved-local-action'
            except ActionError as e:
                return {'exception': {'type': 6, 'title': 'Local Village', 'message': str(e), 'reason': 'local_action_rejected', 'endpoint': route}}, 'rejected-local-action'
            if route == 'game/village/consume_food':
                # Native callback extracts game_state and rate separately.
                return {'game_state': copy.deepcopy(self.data['game_state']),
                        'rate': self.data['game_state']['global_state'].get('food_consumption_rate', 0)}, 'local-food-rate'
            if route in ('game/relationship/get_friends', 'game/relationship/get_followers',
                         'game/relationship/get_followed', 'game/privacy/get_blocked_users',
                         'game/village/get_neighbour_list', 'game/message/get_comments',
                         'game/message/get_private_message_preview', 'game/task_list/get_tasks',
                         'game/village/get_quests'):
                return [], 'empty-offline-list'
            if route == 'game/message/get_private_message_unread_count':
                return {'count': 0}, 'no-private-messages'
            if route in ('game/gcm/enable_gcm','game/gcm/disable_gcm'):
                return {}, 'no-push-notifications'
            if route == 'game/user/get_user':
                return copy.deepcopy(self.data['game_user']), 'local-profile'
            if route == 'game/village/get_villager':
                try:
                    ident = str(integer(params, 'villager_id', low=1))
                    person = self.data['game_state']['all_villagers'].get(ident)
                    if person is None: raise ActionError('Villager does not exist.')
                    return copy.deepcopy(person), 'local-villager'
                except ActionError as e:
                    return {'exception': {'type': 6, 'title': 'Local Village', 'message': str(e), 'reason': 'local_action_rejected'}}, 'rejected-local-action'
            if route in ('game/login/oauth', 'game/login/resume_connection'):
                return self.packet(), 'experimental-login'
            if route == 'game/registration/oauth/create_game_user':
                new = copy.deepcopy(self.data)
                username = params.get('username', ['Local Village'])[0]
                new['game_user']['username'] = username[:40]
                self.persist(new)
                return self.packet(), 'saved-local-profile'
            if route == 'game/village/get_village':
                return copy.deepcopy(self.data['game_state']), 'local-village'
            if route == 'game/village/get_resources':
                return copy.deepcopy(self.data['game_state']), 'local-state'
            if route == 'game/poll/notices':
                return {'game_state': self.packet()['game_state'], 'notices': []}, 'empty-local-notices'
            if route == 'game/gplay/get_products':
                # The native callback binds the entire JSON root to an array.
                # A dictionary creates bogus products and enters StoreKit initialization.
                return [], 'empty-local-product-list'
            if route == 'game/poll/chat':
                return {'global_messages': [], 'global_topics': [], 'group_chat': []}, 'no-online-chat'
            if route in ('game/registration/report_install', 'game/metrics/android/event',
                         'game/message/set_notices_last_viewed_id', 'game/logout'):
                return {}, 'local-noop'
            if route == 'game/registration/get_username_recommendation':
                return {'valid': True, 'username': 'Local Village', 'suggestions': ['Local Village']}, 'experimental-registration'
            # Do not pretend an unsupported gameplay action succeeded.
            return {'exception': {'type': 6, 'title': 'Local Village', 'message': 'Local prototype: this action is not implemented.',
                                  'reason': 'offline_prototype_unimplemented', 'endpoint': route}}, 'unsupported'

class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def log_message(self, *_): pass
    def reply(self, code, value):
        state=getattr(getattr(self,'server',None),'state',None)
        if state is not None:
            with state.lock:projected=native_payload(value,state.data['game_state'])
        else:projected=native_payload(value)
        body = json.dumps(projected, separators=(',', ':')).encode()
        self.send_response(code); self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body))); self.send_header('Connection', 'close')
        self.end_headers(); self.wfile.write(body); self.close_connection = True
    def dispatch(self):
        peer = ipaddress.ip_address(self.client_address[0])
        if not (peer.is_loopback or peer in ipaddress.ip_network('192.168.240.0/24')):
            self.reply(403, {'error': 'Only local Waydroid clients are accepted.'}); return
        parsed = urlsplit(self.path)
        if parsed.path == '/health':
            self.reply(200, {'status': 'experimental', 'package': PACKAGE,
                             'save_exists': self.server.state.save.exists(), 'pid': os.getpid(), 'version': '0.2.0-rc1'}); return
        params = parse_qs(parsed.query, keep_blank_values=True)
        try:length = int(self.headers.get('Content-Length', '0'))
        except (ValueError, TypeError):self.reply(400, {'error': 'Invalid Content-Length'});return
        if length < 0 or length > 1024 * 1024:
            self.reply(413, {'error': 'Request too large'}); return
        if length:
            body = self.rfile.read(length)
            if 'application/json' in self.headers.get('Content-Type', ''):
                def unique(pairs):
                    result={}
                    for key,value in pairs:
                        if key in result:raise ValueError('Duplicate JSON key')
                        result[key]=value
                    return result
                try: values = json.loads(body, object_pairs_hook=unique)
                except (ValueError, UnicodeError): self.reply(400, {'error': 'Invalid JSON'}); return
                if not isinstance(values, dict): self.reply(400, {'error': 'Expected JSON object'}); return
                params.update({k: v if isinstance(v, list) else [v] if isinstance(v,dict) else [str(v)] for k, v in values.items()})
            else: params.update(parse_qs(body.decode('utf-8', 'replace'), keep_blank_values=True))
        value, status = self.server.state.handle(parsed.path, params)
        error = value.get('exception') if isinstance(value, dict) else None
        self.server.state.record(parsed.path, params, status, error=error)
        if error:
            # JMRemoteCallback onFailure: calls JSONValue on exception: the
            # wire field is a JSON-encoded string, not a nested dictionary.
            value = dict(value, exception=json.dumps(error, separators=(',', ':')))
        # SNServerConnection selects the success callback only for HTTP 200.
        # A JSON exception with 200 enters the breeding success callback with
        # no token/game_state, leaving the native sequence in an invalid state.
        # Avoid 403: that code triggers the client's upstream IP fallback.
        code = 501 if status == 'unsupported' else 409 if error else 200
        self.reply(code, value)
    do_GET = dispatch
    do_POST = dispatch

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bind', default='192.168.240.1')
    parser.add_argument('--port', type=int, default=8770)
    parser.add_argument('--data-dir', default=str(Path.home() / 'MeegoOfflineRelease'))
    args = parser.parse_args()
    if args.bind not in ('192.168.240.1', '127.0.0.1'):
        parser.error('Bind only to the Waydroid bridge or loopback.')
    def stop_requested(_signum, _frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop_requested)
    state = State(args.data_dir)
    server = ThreadingHTTPServer((args.bind, args.port), Handler); server.state = state
    print(f'EXPERIMENTAL local Meego responder: http://{args.bind}:{args.port}', flush=True)
    print(f'Save: {state.save}\nRequest log: {state.logfile}', flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()

if __name__ == '__main__': main()

