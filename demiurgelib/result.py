from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, TypeVar, Union, NoReturn, Any, TypeGuard
import logging

T = TypeVar("T")
U = TypeVar("U")
E = TypeVar("E", bound=BaseException)


@dataclass(frozen=True)
class Ok(Generic[T]):
    """Successful result value."""

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

    def map(self, func: Callable[[T], U]) -> "Result[U]":
        try:
            return Ok(func(self.value))
        except Exception as exc:
            return Err(exc)

    def bind(self, func: Callable[[T], "Result[U]"]) -> "Result[U]":
        return func(self.value)


@dataclass(frozen=True)
class Err:
    """Failed result value."""

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

    def map(self, func: Callable[[Any], U]) -> "Err":
        return self

    def bind(self, func: Callable[[Any], "Result[U]"]) -> "Err":
        return self


Result = Union[Ok[T], Err]


def is_ok(result: Result[T]) -> TypeGuard[Ok[T]]:
    return isinstance(result, Ok)


def is_err(result: Result[T]) -> TypeGuard[Err]:
    return isinstance(result, Err)


def capture(func: Callable[[], T], *, log: bool = False) -> Result[T]:
    """Run a callable and return Ok(value) or Err(exception)."""

    try:
        return Ok(func())
    except Exception as exc:
        if log:
            logging.exception(f"Captured exception in {getattr(func, '__name__', repr(func))}")
        return Err(exc)


# Backward-compatible alias for the previous API.
result = capture
