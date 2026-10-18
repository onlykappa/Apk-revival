"""Bounded local replenishment of the original client's resource node pools.

The original 1.32 client recovers missing resource nodes on startup. The local
requested cap is five of each type (original caps were4/3/3). Its server's timing
is unavailable. One-minute replenishment is a requested local policy, not
an original timer. Only previously observed resource sites are reused: guessing
free coordinates without the client's terrain mask can place nodes off-island.
"""
import math

from . import local_game as g

INTERVAL_SECONDS = 60
STATE_KEY = 'local_ecology'
LEGACY_POLICY = 'local-resource-replenishment-15m-v1'
PREVIOUS_POLICY = 'local-resource-replenishment-per-kind-15m-v2'
FIVE_MINUTE_POLICY = 'local-resource-replenishment-per-kind-5m-v3'
POLICY = 'local-resource-replenishment-per-kind-1m-v4'
RESOURCE_LIMITS = {2: 5, 3: 5, 4: 5}
LEGACY_STOCKS = {2: 40, 3: 30, 4: 75}
DEFAULT_STOCKS = {2: 250, 3: 250, 4: 250}
CAPACITY_KEY = "local_resource_capacities"
MAX_ID = 2147483647
MAX_SITES = 64
BUSH_STOCK_MIGRATION = 'bush-stock-75-v1'
REMOVED_KEY = 'local_depleted_nodes'


def remember_depletion(data, node, now):
    """Retain bounded native deletion markers, never resource stock or rewards."""
    if node.get('building_type') not in RESOURCE_LIMITS:
        return
    removed = data.setdefault(REMOVED_KEY, {})
    removed[str(node['building_id'])] = now
    # A long-running village must not grow every HTTP response indefinitely.
    # IDs currently in use are filtered again on the wire (IDs can be reused).
    if len(removed) > 512:
        for ident in sorted(removed, key=removed.get)[:-512]:
            del removed[ident]


def upgrade_bush_stock(data):
    """Raise standing old 20-unit bushes prospectively, once per save.

    Preserve food already harvested: 5 remaining becomes 60, not a refill to75.
    Exhausted/unknown/above-old-limit nodes and rock/tree stocks are untouched.
    No bank balance or worker progress changes. Fresh nodes use75 directly.
    """
    migrations=data.setdefault('local_migrations',[])
    if BUSH_STOCK_MIGRATION in migrations:return False
    for node in data['game_state'].get('buildings',{}).values():
        count=node.get('count')
        if (node.get('building_type')==4 and type(count) is int and 0<count<=20):
            node['count']=count+55
    migrations.append(BUSH_STOCK_MIGRATION)
    return True


def resource_stocks(data, rules=None):
    """250 at completed burg level one, then 50 per completed upgrade."""
    rules = g.RULES if rules is None else rules
    level = 1
    for node in data['game_state']['buildings'].values():
        if node.get('building_type') == 1:
            rule = rules.get('buildings', {}).get('1', {}).get('state_data', {}).get(str(node.get('state')), {})
            # Construction states must not grant the next level early.
            if not rule.get('buildable'):
                level = max(level, int(rule.get('temple_level', 1)))
    # Preserve the last completed level while an upgrade is in progress.
    previous = data.get('local_resource_burg_level', 1)
    level = max(level, previous)
    data['local_resource_burg_level'] = level
    return {kind: base + 50 * (level - 1) for kind, base in DEFAULT_STOCKS.items()}


def register_stock(data, node, capacity):
    data.setdefault(CAPACITY_KEY, {})[str(node['building_id'])] = dict(
        kind=node['building_type'], location=node['location'], capacity=capacity)


def upgrade_resource_stocks(data, rules=None):
    """Add only newly earned capacity; never refill spent stock or balances."""
    upgrade_bush_stock(data)
    stocks = resource_stocks(data, rules)
    records = data.setdefault(CAPACITY_KEY, {})
    buildings = data['game_state']['buildings']
    live = {str(n['building_id']) for n in buildings.values() if n.get('building_type') in RESOURCE_LIMITS}
    for key in list(records):
        if key not in live:
            del records[key]
    for node in buildings.values():
        kind = node.get('building_type')
        if kind not in RESOURCE_LIMITS:
            continue
        old = records.get(str(node['building_id']), {})
        capacity = (old['capacity'] if old.get('kind') == kind and
                    old.get('location') == node['location'] else LEGACY_STOCKS[kind])
        count = node.get('count', 0)
        if type(count) is int and count > 0:
            node['count'] = count + max(0, stocks[kind] - capacity)
        register_stock(data, node, stocks[kind])
    return stocks


def _clock(value):
    if isinstance(value, bool):
        raise ValueError('Invalid ecology clock.')
    try:
        value = float(value)
    except (ValueError, TypeError, OverflowError):
        raise ValueError('Invalid ecology clock.') from None
    if not math.isfinite(value):
        raise ValueError('Invalid ecology clock.')
    return value


def _ident(value):
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value if value > 0 else 0
    if isinstance(value, str) and value.isascii() and value.isdigit():
        return int(value)
    return 0


def _next_id(buildings, cursor=1):
    largest = max((_ident(v) for key, b in buildings.items()
                   for v in (key, b.get('building_id'))), default=0)
    ident = max(_ident(cursor), largest + 1, 1)
    if ident > MAX_ID:
        raise ValueError('No free resource building identifier remains.')
    return ident


def _footprint(kind, location, rules):
    if isinstance(location, bool) or not isinstance(location, int):
        return None
    size = _ident(rules.get('buildings', {}).get(str(kind), {}).get('size'))
    x, y = divmod(location, g.MAP_SIZE)
    if not size or min(x, y) < 0 or max(x + size, y + size) > g.MAP_SIZE:
        return None
    return x, y, x + size, y + size


def _available(site, buildings, rules):
    a = _footprint(site['kind'], site['location'], rules)
    if a is None:
        return False
    for b in buildings.values():
        q = _footprint(b.get('building_type'), b.get('location'), rules)
        # Unknown/malformed occupied buildings cannot establish a safe tile.
        if q is None or (a[0] < q[2] and a[2] > q[0] and
                         a[1] < q[3] and a[3] > q[1]):
            return False
    return True


def _sites(buildings, existing, rules):
    sites = []
    for site in existing:
        if (isinstance(site, dict) and site.get('kind') in RESOURCE_LIMITS and
                site.get('orientation') in (0, 1, 2) and
                _footprint(site['kind'], site.get('location'), rules)):
            clean = {key: site[key] for key in ('kind', 'location', 'orientation')}
            if clean not in sites:
                sites.append(clean)
    for b in buildings.values():
        kind = b.get('building_type')
        if kind not in RESOURCE_LIMITS:
            continue
        site = dict(kind=kind, location=b.get('location'),
                    orientation=b.get('orientation', 0))
        if (site['orientation'] in (0, 1, 2) and
                _footprint(kind, site['location'], rules) and site not in sites):
            sites.append(site)
    return sites[-MAX_SITES:]


def advance(data, now, *, rules=None, stocks=None):
    """Update a copied save and return the first spawned node ID, or None.

    Call before worker depletion, under the save lock, then persist the returned
    save normally. That remembers the native client's valid resource positions
    before depleted nodes disappear. Metadata stays outside ``game_state``.

    Migration observes existing nodes and waits a full interval. Each overdue
    check creates at most one missing node PER TYPE and schedules from the
    current time. Migrate older policies to one minute from the same cycle start,
    so frequent polling cannot postpone the shortened deadline.
    No stored backlog, rollback reward, resource bank refill,
    or alteration to existing nodes occurs. Occupied sites are skipped; unknown
    terrain is never guessed. The native startup recovery path remains intact.
    """
    now = _clock(now)
    rules = g.RULES if rules is None else rules
    stocks = resource_stocks(data, rules) if stocks is None else stocks
    if any(isinstance(stocks.get(kind), bool) or
           not isinstance(stocks.get(kind), int) or stocks[kind] <= 0
           for kind in RESOURCE_LIMITS):
        raise ValueError('Invalid resource replenishment stocks.')
    buildings = data['game_state']['buildings']
    state = data.get(STATE_KEY)
    if state is None:
        data[STATE_KEY] = dict(policy=POLICY,
                              original_server_timing_verified=False,
                              next_due=now + INTERVAL_SECONDS,
                              last_checked_at=now,
                              next_building_id=_next_id(buildings),
                              next_kind=2, replenishment_count=0,
                              sites=_sites(buildings, [], rules))
        return None
    if (not isinstance(state, dict) or state.get('policy') not in (POLICY, LEGACY_POLICY, PREVIOUS_POLICY, FIVE_MINUTE_POLICY) or
            not isinstance(state.get('sites'), list) or
            state.get('next_kind') not in RESOURCE_LIMITS or
            isinstance(state.get('replenishment_count'), bool) or
            not isinstance(state.get('replenishment_count'), int) or
            state['replenishment_count'] < 0):
        raise ValueError('Invalid local ecology policy. Save was not changed.')
    due = _clock(state.get('next_due'))
    checked = _clock(state.get('last_checked_at'))
    if now <= checked:
        return None
    if state['policy'] != POLICY:
        due -= (300 if state['policy'] == FIVE_MINUTE_POLICY else 900) - INTERVAL_SECONDS
        state['next_due'] = due
    state['policy'] = POLICY
    sites = _sites(buildings, state['sites'], rules)
    if now < due:
        state.update(sites=sites, last_checked_at=now)
        return None
    kinds = tuple(RESOURCE_LIMITS)
    start = kinds.index(state['next_kind'])
    first_ident = None
    for offset in range(len(kinds)):
        kind = kinds[(start + offset) % len(kinds)]
        limit = RESOURCE_LIMITS[kind]
        if sum(b.get('building_type') == kind for b in buildings.values()) >= limit:
            continue
        candidate = next((s for s in sites if s['kind'] == kind and
                          _available(s, buildings, rules)), None)
        if not candidate:
            continue
        ident = _next_id(buildings, state.get('next_building_id'))
        kind = candidate['kind']
        default_state = rules['buildings'][str(kind)].get('default_state', 1)
        node = g.building(ident, kind, default_state, candidate['location'],
                          now, candidate['orientation'])
        node['count'] = stocks[kind]
        register_stock(data, node, stocks[kind])
        buildings[str(ident)] = node
        state.update(next_building_id=ident + 1,
                     next_kind=kinds[(kinds.index(kind) + 1) % len(kinds)],
                     replenishment_count=state['replenishment_count'] + 1,
                     last_replenished_at=now)
        if first_ident is None:
            first_ident = ident
    state.update(sites=sites, last_checked_at=now,
                 next_due=now + INTERVAL_SECONDS)
    return first_ident

