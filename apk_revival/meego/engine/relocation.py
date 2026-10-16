"""Native move lifecycle: remove old model and create the destination model."""
REMOVED_KEY = 'local_relocated_buildings'


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
        return
    old=int(ident);new=int(destination)
    # Preserve stable local reward/progression identity through native rekeys.
    node.setdefault('local_instance_id',old)
    node.update(building_id=new,location=location,orientation=orientation,last_update=now)
    del buildings[ident]
    buildings[destination]=node
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
    removed=data.setdefault(REMOVED_KEY,{})
    removed[ident]=now
    for key in sorted(removed,key=removed.get)[:-512]:del removed[key]


def removed_nodes(data):
    from .ecology import REMOVED_KEY as DEPLETED
    return set(data.get(DEPLETED,{})) | set(data.get(REMOVED_KEY,{}))
