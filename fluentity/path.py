from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

_MISSING = object()


def get_path(obj: Any, path: str | Sequence[Any], default: Any = None, *, separator: str = ".") -> Any:
    """Safely read nested dict/list/object values by path.

    Examples:
        get_path(payload, "user.profile.name", default="anonymous")
        get_path(payload, ["items", 0, "title"])
    """

    parts = path.split(separator) if isinstance(path, str) else list(path)
    current = obj
    for part in parts:
        current = _get_one(current, part)
        if current is _MISSING:
            return default
    return current


def _get_one(obj: Any, key: Any) -> Any:
    if obj is None:
        return _MISSING
    if isinstance(obj, Mapping):
        return obj.get(key, _MISSING)
    if isinstance(obj, (list, tuple)):
        try:
            index = int(key)
        except (TypeError, ValueError):
            return _MISSING
        try:
            return obj[index]
        except IndexError:
            return _MISSING
    return getattr(obj, str(key), _MISSING)
