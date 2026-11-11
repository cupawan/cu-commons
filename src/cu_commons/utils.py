"""Helpers for reading loosely structured JSON from APIs."""
from typing import Any


def find_key(data: Any, name: str) -> Any:
    """First non-None value stored under `name` anywhere in nested dicts/lists (depth-first)."""
    if isinstance(data, dict):
        if data.get(name) is not None:
            return data[name]
        children = data.values()
    elif isinstance(data, list):
        children = data
    else:
        return None
    for child in children:
        found = find_key(child, name)
        if found is not None:
            return found
    return None


def dig(data: Any, *path: str, default: Any = None) -> Any:
    """Safe nested lookup; a list on the way is replaced by its first element."""
    for key in path:
        if isinstance(data, list):
            data = data[0] if data else None
        if not isinstance(data, dict):
            return default
        data = data.get(key)
    if isinstance(data, list):
        data = data[0] if data else None
    return default if data is None else data


def to_int(value: Any) -> int | None:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None
