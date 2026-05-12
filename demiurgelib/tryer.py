from __future__ import annotations

import logging
from typing import Callable, Optional, Type, TypeVar, Generic

T = TypeVar("T")


class TryExecutor(Generic[T]):
    """Fluent wrapper around try/except/else/finally."""

    def __init__(self, try_func: Callable[[], T]):
        self.try_func = try_func
        self.exception_handler: Optional[Callable[[BaseException], object]] = None
        self.exception_type: Type[BaseException] = Exception
        self.else_action: Optional[Callable[[T], object]] = None
        self.final_action: Optional[Callable[[], object]] = None
        self.result: Optional[T] = None
        self.exception: Optional[BaseException] = None

    def except_(
        self,
        exception_handler: Callable[[BaseException], object],
        exception_type: Type[BaseException] = Exception,
    ) -> "TryExecutor[T]":
        self.exception_handler = exception_handler
        self.exception_type = exception_type
        return self

    def else_(self, else_action: Callable[[T], object]) -> "TryExecutor[T]":
        self.else_action = else_action
        return self

    def finally_(self, final_action: Callable[[], object]) -> "TryExecutor[T]":
        self.final_action = final_action
        return self

    def execute(self) -> Optional[T]:
        try:
            self.result = self.try_func()
        except self.exception_type as exc:
            self.exception = exc
            if self.exception_handler:
                self.exception_handler(exc)
            else:
                logging.exception(f"TryExecutor failed: {exc}")
        else:
            if self.else_action:
                self.else_action(self.result)
        finally:
            if self.final_action:
                self.final_action()
        return self.result
