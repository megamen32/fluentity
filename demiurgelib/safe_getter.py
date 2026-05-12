from __future__ import annotations

import logging
from typing import Any, Callable, Iterable, Optional, Sequence, Tuple, TypeVar, List

T = TypeVar("T")
U = TypeVar("U")


def try_gete(func: Callable[[], T], default: U = None, log_exc: bool = False) -> Tuple[T | U, Optional[Exception]]:
    """Execute a callable and return ``(value, exception)`` without raising."""

    try:
        result = func()
        return (result if result is not None else default), None
    except Exception as exc:
        if log_exc:
            logging.exception(f"An error occurred in {getattr(func, '__name__', repr(func))}")
        return default, exc


def try_get(func: Callable[[], T], default: U = None, return_exception: bool = False, **kwargs: Any) -> T | U | Exception:
    """Execute a callable and return its value, default, or the exception itself."""

    result, exception = try_gete(func, default, **kwargs)
    return exception if return_exception and exception is not None else result


def try_geta(
    items: Iterable[T],
    func: Callable[[T], U],
    skip_none: bool = True,
    default_element: Any = None,
) -> List[U]:
    """Map a callable over items, replacing failures with a default value."""

    output: List[U] = []
    for item in items:
        value = try_get(lambda item=item: func(item), default_element)
        if value is None and skip_none:
            continue
        output.append(value)
    return output


def try_get_attrs(obj_func: Callable[[], Any], attrs: Sequence[str], defaults: Sequence[Any]) -> Tuple[Any, ...]:
    """Safely read several attributes from an object returned by ``obj_func``."""

    if len(attrs) != len(defaults):
        raise ValueError("attrs and defaults must have the same length.")

    obj = try_get(obj_func)
    return tuple(getattr(obj, attr, default) for attr, default in zip(attrs, defaults))


def apply_to_list(
    items: Iterable[T],
    func: Callable[[T], U],
    filter_func: Optional[Callable[[T], bool]] = None,
    return_all: bool = True,
) -> List[U]:
    """Filter and map a collection while safely ignoring per-item failures."""

    output: List[U] = []
    for item in items:
        if filter_func is not None and not filter_func(item):
            continue
        result = try_get(lambda item=item: func(item))
        if return_all or result is not None:
            output.append(result)
    return output


safe_call = try_get
safe_map = try_geta
