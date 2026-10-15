"""Purchases from the user's bundled Meego catalog, without invented prices.

The native item shop uses conversion_map["1"] for resource purchases and
points_cost for skull purchases. Research cursors are flat item IDs; each
cursor also unlocks its research_required_item_id ancestors in the client.
"""
from . import local_game as g


def _item(rules, ident):
    rule = rules.get('items', {}).get(str(ident))
    if not rule or not rule.get('active'):
        raise g.ActionError('This item is not available in the bundled catalog.')
    return rule


def _temple_level(gs):
    return int(gs.get('achievements', {}).get('102', {}).get('level', 1))


def _require_achievement(gs, rule):
    achievement = rule.get('unlock_achievement_id')
    if achievement and int(gs.get('achievements', {}).get(str(achievement), {}).get('level', 0)) < int(rule.get('unlock_achievement_level', 1)):
        raise g.ActionError('Upgrade your temple to unlock this item.')


def normalize_research_cursors(gs, rules):
    """Repair the earlier local [ID, ID] encoding without removing unlocks.

    Native cursors are dictionary keys, not ID intervals. Only the known local
    singleton-pair error is migrated; unfamiliar entries remain preserved.
    """
    info = gs.setdefault('unlock_information', {})
    old = info.setdefault('unlocked_item_cursors', [])
    new = []
    for cursor in old:
        if isinstance(cursor, (list, tuple)) and len(cursor) == 2 and cursor[0] == cursor[1]:
            cursor = cursor[0]
        if isinstance(cursor, (int, str)) and not isinstance(cursor, bool) and str(cursor).isdigit():
            cursor = str(cursor)
        if cursor not in new:
            new.append(cursor)
    if new != old:
        info['unlocked_item_cursors'] = new
        return True
    return False


def researched_items(gs, rules):
    """Match the native cursor-to-predecessor expansion, guarding bad cycles."""
    pending = []
    for cursor in gs.get('unlock_information', {}).get('unlocked_item_cursors', []):
        if isinstance(cursor, (list, tuple)) and len(cursor) == 2 and cursor[0] == cursor[1]:
            cursor = cursor[0]
        if isinstance(cursor, (int, str)) and not isinstance(cursor, bool) and str(cursor).isdigit():
            pending.append(str(cursor))
    unlocked = set()
    while pending:
        ident = pending.pop()
        if ident in unlocked:
            continue
        unlocked.add(ident)
        predecessor = rules.get('items', {}).get(ident, {}).get('research_required_item_id', 0)
        if predecessor:
            pending.append(str(predecessor))
    return unlocked


def research_item(gs, ident, rules, now):
    ident = str(ident)
    rule = _item(rules, ident)
    price = rule.get('research_points', 0)
    if not isinstance(price, int) or isinstance(price, bool) or price <= 0:
        raise g.ActionError('This item has no research unlock.')
    unlocked = researched_items(gs, rules)
    if ident in unlocked:
        normalize_research_cursors(gs, rules)
        return
    if _temple_level(gs) < int(rule.get('research_temple_level', 1)):
        raise g.ActionError('Upgrade the temple before researching this item.')
    predecessor = rule.get('research_required_item_id', 0)
    if predecessor and str(predecessor) not in unlocked:
        raise g.ActionError('Research the previous item in this tool path first.')
    resource = gs.get('resources', {}).get('4')
    if not resource or resource.get('count', 0) < price:
        raise g.ActionError('Not enough research points.')
    # Validation is complete. No rejected request changes balances or cursors.
    normalize_research_cursors(gs, rules)
    resource.update(count=resource['count'] - price, last_update=now)
    gs['unlock_information']['unlocked_item_cursors'].append(ident)


def purchase_item(gs, ident, count, use_points, rules, now):
    """Validate then debit an original shop price/recipe and credit inventory.

    Recipe item inputs must be in village inventory. Equipped tools remain
    untouched; the player can unequip one when a recipe requires it.
    """
    ident = str(ident)
    rule = _item(rules, ident)
    if not rule.get('items_store_purchasable'):
        raise g.ActionError('This item is not in the bundled item shop.')
    if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 100:
        raise g.ActionError('Invalid item count.')
    _require_achievement(gs, rule)
    inventory = gs.get('items', {})
    owned = int(inventory.get(ident, {}).get('count', 0))
    owned += sum(int(person.get('items', {}).get(ident, {}).get('count', 0)) for person in gs.get('all_villagers', {}).values())
    maximum = int(rule.get('max_count', 0))
    if maximum and owned + count > maximum:
        raise g.ActionError('Maximum item count reached, including equipped items.')
    resource_costs, item_costs = {}, {}
    skulls = 0
    if use_points:
        price = rule.get('points_cost', 0)
        if isinstance(price, bool) or not isinstance(price, int) or price <= 0:
            raise g.ActionError('This item has no crystal-skull purchase price. Use its resource recipe after research.')
        skulls = price * count
    else:
        if rule.get('research_points') and ident not in researched_items(gs, rules):
            raise g.ActionError('Research this item before crafting it with resources.')
        recipe = rule.get('conversion_map', {}).get('1')
        if not recipe or recipe.get('output_count') != 1 or not recipe.get('input_counter_units'):
            raise g.ActionError('This item has no supported resource purchase recipe in the bundled game.')
        for ingredient in recipe['input_counter_units']:
            item_id, amount = ingredient.get('counter_unit_id'), ingredient.get('count')
            if isinstance(item_id, bool) or not isinstance(item_id, int) or isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
                raise g.ActionError('This item has an unsupported purchase recipe.')
            resource = g.RESOURCE_IDS.get(item_id)
            costs, key = (resource_costs, str(resource)) if resource else (item_costs, str(item_id))
            if not resource and key not in rules.get('items', {}):
                raise g.ActionError('This recipe requires an unknown item.')
            costs[key] = costs.get(key, 0) + amount * count
    if gs.get('points', 0) < skulls:
        raise g.ActionError('Not enough local crystal skulls.')
    for key, amount in resource_costs.items():
        if gs.get('resources', {}).get(key, {}).get('count', 0) < amount:
            raise g.ActionError('Not enough resources for this item recipe.')
    for key, amount in item_costs.items():
        if inventory.get(key, {}).get('count', 0) < amount:
            raise g.ActionError('This recipe needs an earlier tool in village inventory. Unequip it first if a villager is using it.')
    # All inputs and the output cap passed validation; make one atomic action.
    gs['points'] = gs.get('points', 0) - skulls
    for key, amount in resource_costs.items():
        entry = gs['resources'][key]
        entry.update(count=entry['count'] - amount, last_update=now)
    for key, amount in item_costs.items():
        entry = inventory[key]
        entry.update(count=entry['count'] - amount, last_update=now)
    entry = gs.setdefault('items', {}).setdefault(ident, dict(item_id=int(ident), count=0, last_update=now))
    entry.update(count=entry['count'] + count, last_update=now)
