"""Reviewed native countdown controls; no automatic completion or clock patch."""
import copy
import hashlib

from ..util import RevivalError
from . import ccb, frame_pacing

REVISION = 1
ASSET = 'assets/CrystalSkullPopUp.ccbi'
ASSET_SHA = '37fdf14e6234ad72e7122243616d3cf57a68e953a043ad4f888484e9dae37153'


def native_patches(library):
    if hashlib.sha256(library).hexdigest() != frame_pacing.LIBRARY_SHA256:
        raise RevivalError('In-game timer mod requires the reviewed original Meego library.')
    patches = []
    # These three original price methods are used only by the reviewed
    # countdown subclasses. Their completion callbacks still run normally.
    for offset, old in ((0x7B5548, 'f04d2de924119fe5'),
                        (0x7CAA88, 'f04d2de928119fe5'),
                        (0x9EA264, 'f04d2de92c119fe5')):
        patches.append(dict(offset=offset, old=old, new='0000a0e31eff2fe1',
                            reason='Explicit in-game Skip timer mod reports zero skull cost'))
    # The relocated completion button sits outside this hidden paid panel.
    # init already hides that panel; do not show the original store controls.
    patches.append(dict(offset=0x68BE68, old='f04d2de9', new='1eff2fe1',
                        reason='Keep paid skull panel hidden while using the in-game timer mod'))
    for offset in (0x7B4E34, 0x7CA4DC, 0x9E9E28):
        patches.append(dict(offset=offset, old='0130a0e3', new='0030a0e3',
                            reason='Skip is an explicit free mod action; suppress the skull-purchase confirmation'))
    for p in patches:
        if library[p['offset']:p['offset'] + len(bytes.fromhex(p['old']))] != bytes.fromhex(p['old']):
            raise RevivalError('In-game timer patch precondition failed.')
    return patches


def patched_panel(raw):
    if hashlib.sha256(raw).hexdigest() != ASSET_SHA:
        raise RevivalError('In-game timer mod requires the reviewed countdown panel.')
    reader = ccb.Reader(raw)
    root = reader.read()
    if reader.dump(root) != raw:
        raise RevivalError('Countdown panel did not round-trip exactly.')

    def walk(node):
        yield node
        for child in node['children']:
            yield from walk(child)

    def prop(node, name):
        return next(p for p in node['props'] if p['name'] == name)

    def change(node, name, value):
        p = prop(node, name)
        p.update(value=value, raw=None)

    all_nodes = list(walk(root))
    button = next(n for n in all_nodes if n['name'] == 'completeSkullsButton')
    owner = next(n for n in all_nodes if button in n['children'])
    close_menu = next(n for n in all_nodes if n['cls'] == 'CCMenu'
                      and any(any(p['name'] == 'block' and p['value'] == ('onClose', 2)
                                  for p in child['props']) for child in n['children']))
    # Move the original bound button, rather than copying it: native
    # disableSkullButtons/enableSkullButtons still prevent repeated clicks.
    owner['children'].remove(button)
    close_menu['children'].append(button)
    change(button, 'position', (-51, 0, 0))
    change(button, 'scale', (0.7, 0.9, 0))
    label = copy.deepcopy(next(n for n in all_nodes if n['name'] == 'completeSkullsActionLabel'))
    label.update(assignment=0, name='')
    change(label, 'position', (98.23046875, 12.265625, 0))
    change(label, 'string', 'Skip timer')
    root['children'].append(label)
    result = reader.dump(root)
    check = ccb.Reader(result)
    if check.dump(check.read()) != result:
        raise RevivalError('Modified countdown panel did not round-trip exactly.')
    return result
