"""Exact-original native stats control and free stat-preserving revival panel.

Only patch recipes ship. The user's original CCB assets are checked and rebuilt
locally; the new button uses the already implemented onResurrect callback.
"""
import copy
import hashlib

from ..util import RevivalError
from . import ccb

REVISION = 1
ASSETS = {
    'assets/Full_Character_Stats.ccbi': '1e9b3fc5ca41b87eaa5d1511afa8705b1f77c774427d40bb321f13e7f1abc00a',
    'assets/Full_Character_Stats-ipad.ccbi': 'b58b0f4f9bb6ef911bb6e99f6a4a9fffe5164ea5bfec0fecc0f14bfcfa831fbe',
    'assets/TombstonePopUp.ccbi': 'f2bba4a2d859bc080f80b413ad2ff95909b76c60e8c016e8ba413677510def61',
}


def walk(node):
    yield node
    for child in node['children']:
        yield from walk(child)


def props(node):
    return {p['name']: p['value'] for p in node['props']}


def change(node, name, value, kind=None):
    prop = next((p for p in node['props'] if p['name'] == name), None)
    if prop is None:
        if kind is None:
            raise RevivalError('Reviewed stats panel property is missing: ' + name)
        prop = dict(name=name, type=kind, platform=0)
        node['props'].append(prop)
    prop.update(value=value, raw=None)


def unbound(node):
    node = copy.deepcopy(node)
    node.update(assignment=0, name='', animations=b'\x01')
    return node


def patched_panel(path, raw):
    if path not in ASSETS or hashlib.sha256(raw).hexdigest() != ASSETS[path]:
        raise RevivalError('Villager age control requires the reviewed original stats asset.')
    reader = ccb.Reader(raw)
    root = reader.read()
    if reader.dump(root) != raw:
        raise RevivalError('Villager stats asset did not round-trip exactly.')
    nodes = list(walk(root))
    if path.endswith('TombstonePopUp.ccbi'):
        _confirmation(nodes)
    else:
        _stats(nodes)
    result = reader.dump(root)
    check = ccb.Reader(result)
    if check.dump(check.read()) != result:
        raise RevivalError('Updated villager age asset did not round-trip exactly.')
    return result


def _stats(nodes):
    age = next(n for n in nodes if n['name'] == 'ageView')
    menu = unbound(next(n for n in age['children'] if n['cls'] == 'CCMenu'))
    menu['children'] = []
    button = unbound(next(n for n in nodes if n['name'] == 'buttonDeadResurrect'))
    change(button, 'position', (400, 62, 0))
    change(button, 'scale', (1.25, .75, 0))
    change(button, 'block', ('onResurrect', 2))
    button['children'] = []
    menu['children'].append(button)
    age['children'].append(menu)
    template = next(n for n in nodes if n['cls'] == 'CCLabelBMFont'
                    and props(n).get('fntFile') == 'Badonkadonk10.fnt')
    for text, y, scale in (('Return to age 20', 62, .82), ('Keep all stats', 39, .7)):
        label = unbound(template)
        change(label, 'position', (400, y, 0))
        change(label, 'anchorPoint', (.5, .5))
        change(label, 'scale', (scale, scale, 0))
        change(label, 'string', text)
        label['children'] = []
        age['children'].append(label)


def _confirmation(nodes):
    # Keep the original FREE callback and close control. Do not retain a paid
    # "partial stats" alternative when both requested actions preserve all stats.
    for node in nodes:
        values = props(node)
        callback = values.get('block')
        text = values.get('string')
        if callback == ('onResurrect', 2):
            change(node, 'visible', 0, 9)
            change(node, 'isEnabled', 0)
        elif callback == ('onResurrectFree', 2):
            change(node, 'position', (106.94140625, 113.4, 0))
            change(node, 'scale', (1.35, 1, 0))
        if node['name'] == 'labelTitle':
            change(node, 'string', 'RETURN TO AGE 20')
        elif node['name'] == 'labelMessage':
            change(node, 'string', '')
            change(node, 'visible', 0, 9)
        elif text == 'Partial Stat\n':
            change(node, 'string', 'Return to 20')
            change(node, 'position', (0, 20, 0))
        elif text == 'Resurrection\n':
            change(node, 'string', 'All stats kept')
            change(node, 'position', (0, 7, 0))
        elif text == 'FREE\n':
            change(node, 'position', (0, -20, 0))
        elif text in ('Full Stat', 'Resurrection', 'x\n') or node['name'] == 'skullCostLabel':
            change(node, 'visible', 0, 9)
