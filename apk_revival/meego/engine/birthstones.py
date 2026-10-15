"""Original birthstone metadata and additive, owned-villager discoveries.

Metadata remains private in the user's APK. The local patch revision ensures
the native client's strict version gate actually merges the restored table.
"""
import copy
import math
import plistlib
import zipfile

LOCAL_CATALOG_VERSION = 2.9401
MAX_TECHTREE_BYTES = 5 * 1024 * 1024


def load_catalog(apk):
    """Read the already selected Meego APK without changing its bytes or files."""
    with zipfile.ZipFile(apk) as archive:
        member = archive.getinfo('assets/TechTree.plist')
        if member.file_size > MAX_TECHTREE_BYTES:
            raise ValueError('Meego TechTree exceeds the supported metadata size.')
        tree = plistlib.loads(archive.read(member))
    catalog = tree.get('techtree', {}).get('birthsigns')
    if not isinstance(catalog, dict) or not catalog:
        raise ValueError('Meego birthstone metadata is missing from this APK.')
    for key, record in catalog.items():
        if not isinstance(record, dict) or not str(key).isdigit() or int(key) <= 0:
            raise ValueError('Meego birthstone metadata has an invalid record.')
        if record.get('techtree_id') != int(key) or record.get('tier') not in (1, 2, 3):
            raise ValueError('Meego birthstone metadata has an invalid ID or tier.')
        if any(not isinstance(record.get(field), str) or not record[field] for field in ('name', 'description', 'image')):
            raise ValueError('Meego birthstone metadata lacks its name, description or image.')
    return copy.deepcopy(catalog)


def populate_packet(packet, catalog):
    """Add original records to a login/resume packet without replacing its tree.

    Original JMTechTree.patchWithUpdate merges a partial table over the bundled
    tree. Version 2.94 would be ignored by the client's strict newer-only gate.
    """
    if not catalog:
        return
    tree = packet.setdefault('techtree', {})
    if not isinstance(tree, dict):
        raise ValueError('Meego login TechTree must be a dictionary.')
    tree['birthsigns'] = copy.deepcopy(catalog)
    version = packet.get('techtree_version', 0)
    if isinstance(version, bool) or not isinstance(version, (int, float)) or not math.isfinite(version):
        raise ValueError('Meego login TechTree version is invalid.')
    packet['techtree_version'] = max(version, LOCAL_CATALOG_VERSION)


def discover_owned(data, catalog):
    """Persist earned discoveries by tier; never grant unseen birthstones.

    Collections are historical numeric IDs, so deaths/travel/other removals do
    not erase discoveries. Unknown save fields and pre-existing discoveries
    remain preserved. Guests do not populate the owner's collection.
    """
    if not catalog:
        return False
    state = data['game_state']
    info = state.setdefault('unlock_information', {})
    collections = info.setdefault('birthsign_collections', {})
    if not isinstance(collections, dict):
        raise ValueError('Saved Meego birthstone collections must be a dictionary.')
    before = copy.deepcopy(collections)
    for tier in ('1', '2', '3'):
        collection = collections.setdefault(tier, [])
        if not isinstance(collection, list):
            raise ValueError('Saved Meego birthstone tier must contain an ID list.')
        # Native membership checks use NSNumber IDs, not string IDs.
        normalized = []
        for value in collection:
            if isinstance(value, str) and value.isdigit():
                value = int(value)
            if value not in normalized:
                normalized.append(value)
        collections[tier] = normalized
    owner = int(data['game_user']['user_id'])
    for person in state.get('all_villagers', {}).values():
        if person.get('user_id') != owner:
            continue
        for ident in person.get('stats', {}).get('birthsigns', []):
            if isinstance(ident, bool) or not isinstance(ident, (int, str)) or not str(ident).isdigit():
                continue
            record = catalog.get(str(ident))
            if not record or record.get('tier') not in (1, 2, 3):
                continue
            collection = collections[str(record['tier'])]
            ident = int(ident)
            if ident not in collection:
                collection.append(ident)
    return collections != before
