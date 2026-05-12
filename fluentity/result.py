from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Generic, NoReturn, TypeGuard, TypeVar, Union

T = TypeVar("T")
U = TypeVar("U")


@dataclass(frozen=True)
class Ok(Generic[T]):
    """A successful explicit result."""

    value: T
    __match_args__ = ("value",)

    @property
    def is_ok(self) -> bool:
        return True

    @property
    def is_err(self) -> bool:
        return False

    def unwrap(self) -> T:
        return self.value

    def unwrap_or(self, default: U) -> T:
        return self.value

    def unwrap_or_else(self, func: Callable[[BaseException], U]) -> T:
        return self.value

    def map(self, func: Callable[[T], U]) -> Result[U]:
        try:
            return Ok(func(self.value))
        except Exception as exc:  # noqa: BLE001 - Result intentionally captures unsafe user functions.
            return Err(exc)

    def bind(self, func: Callable[[T], Result[U]]) -> Result[U]:
        try:
            return func(self.value)
        except Exception as exc:  # noqa: BLE001
            return Err(exc)

    def map_error(self, func: Callable[[BaseException], BaseException]) -> Ok[T]:
        return self

    def match(self, *, ok: Callable[[T], U], err: Callable[[BaseException], U]) -> U:
        return ok(self.value)


@dataclass(frozen=True)
class Err:
    """A failed explicit result."""

    error: BaseException
    __match_args__ = ("error",)

    @property
    def is_ok(self) -> bool:
        return False

    @property
    def is_err(self) -> bool:
        return True

    def unwrap(self) -> NoReturn:
        raise self.error

    def unwrap_or(self, default: U) -> U:
        return default

    def unwrap_or_else(self, func: Callable[[BaseException], U]) -> U:
        return func(self.error)

    def map(self, func: Callable[[Any], U]) -> Err:
        return self

    def bind(self, func: Callable[[Any], Result[U]]) -> Err:
        return self

    def map_error(self, func: Callable[[BaseException], BaseException]) -> Err:
        try:
            return Err(func(self.error))
        except Exception as exc:  # noqa: BLE001
            return Err(exc)

    def match(self, *, ok: Callable[[Any], U], err: Callable[[BaseException], U]) -> U:
        return err(self.error)


Result = Union[Ok[T], Err]


def is_ok(result: Result[T]) -> TypeGuard[Ok[T]]:
    return isinstance(result, Ok)


def is_err(result: Result[T]) -> TypeGuard[Err]:
    return isinstance(result, Err)


def capture(func: Callable[..., T], *args: Any, **kwargs: Any) -> Result[T]:
    """Run a callable and return Ok(value) or Err(exception)."""

    try:
        return Ok(func(*args, **kwargs))
    except Exception as exc:  # noqa: BLE001
        return Err(exc)


def safe(func: Callable[..., T]) -> Callable[..., Result[T]]:
    """Decorate a function so it returns Result instead of raising."""

    def wrapper(*args: Any, **kwargs: Any) -> Result[T]:
        return capture(func, *args, **kwargs)

    wrapper.__name__ = getattr(func, "__name__", "safe_wrapper")
    wrapper.__doc__ = getattr(func, "__doc__", None)
    wrapper.__module__ = getattr(func, "__module__", __name__)
    return wrapper


# Backward-compatible alias for old versions of the project.
result = capture
