"""Native move lifecycle: remove old model and create the destination model."""
REMOVED_KEY = 'local_relocated_buildings'


def remember_removal(data, ident, now):
    """Persist a bounded native removal marker for moved or deleted models."""
    removed = data.setdefault(REMOVED_KEY, {})
    removed[str(ident)] = now
    for key in sorted(removed, key=removed.get)[:-512]:
        del removed[key]


def stop_removed_workers(data, ident, now):
    from .local_game import idle_job
    for person in data['game_state']['all_villagers'].values():
        job = person.get('job', {})
        if ident in (job.get('source_id'), job.get('destination_id')):
            person.update(job=idle_job(now), last_update=now)


def move(data, ident, location, orientation, now):
    from .local_game import ActionError
    state=data['game_state'];buildings=state['buildings'];node=buildings[ident]
    destination=str(location)
    if destination!=ident and destination in buildings:
        raise ActionError('That position conflicts with an existing building identity. Choose another position.')
    for key in ('school_sessions','school_reports'):
        records=data.get(key,{})
        if destination!=ident and ident in records and destination in records:
            raise ActionError('Collect the existing school reports before moving here.')
    if destination==ident:
        node.update(location=location,orientation=orientation,last_update=now)
        _move_capacity(data, ident, destination, node)
        return
    old=int(ident);new=int(destination)
    # Preserve stable local reward/progression identity through native rekeys.
    node.setdefault('local_instance_id',old)
    node.update(building_id=new,location=location,orientation=orientation,last_update=now)
    del buildings[ident]
    buildings[destination]=node
    _move_capacity(data, ident, destination, node)
    for person in state['all_villagers'].values():
        job=person.get('job',{})
        if job.get('source_id')==old:
            job['source_id']=new
            if job.get('target_id')==old:job['target_id']=new
        if job.get('destination_id')==old:job['destination_id']=new
    for trip in data.get('local_islands', {}).get('trips', {}).values():
        if trip.get('dock_id')==old:trip['dock_id']=new
    for other in buildings.values():
        if other.get('destination')==old:other['destination']=new
    for key in ('school_sessions','school_reports'):
        records=data.get(key,{})
        if ident in records:records[destination]=records.pop(ident)
    remember_removal(data, ident, now)


def _move_capacity(data, old, new, node):
    from .ecology import CAPACITY_KEY
    records = data.get(CAPACITY_KEY, {})
    record = records.pop(old, None)
    if record is not None:
        record['location'] = node['location']
        records[new] = record


def removed_nodes(data):
    from .ecology import REMOVED_KEY as DEPLETED
    return set(data.get(DEPLETED,{})) | set(data.get(REMOVED_KEY,{}))
