"""Meego village save format check, shared by the plugin, adapter and backups."""
from ..util import RevivalError


def validate_meego_save(value):
    if not isinstance(value,dict) or value.get("format_version")!=1 or not isinstance(value.get("game_user"),dict) or not isinstance(value.get("game_state"),dict):raise RevivalError("Invalid Meego save. Existing progress was not replaced.")
    state=value["game_state"]
    for field in ["buildings","all_villagers","resources","global_state"]:
        if not isinstance(state.get(field),dict):raise RevivalError("Invalid Meego save field: "+field)
