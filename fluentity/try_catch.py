from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Sequence

from .result import Err, Ok, Result


@dataclass(frozen=True)
class CatchHandler:
    exceptions: tuple[type[BaseException], ...]
    handler: Callable[[BaseException], Any]


@dataclass(frozen=True)
class TryCatch:
    """Fluent try/except/else/finally block that returns Result.

    This keeps the useful old `try_catch` idea, but makes failure explicit:
    `.run()` returns `Ok(value)` or `Err(error)` instead of hiding exceptions.
    """

    func: Callable[..., Any]
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] = field(default_factory=dict)
    handlers: tuple[CatchHandler, ...] = ()
    else_action: Optional[Callable[[Any], Any]] = None
    final_action: Optional[Callable[[], Any]] = None

    def except_(
        self,
        handler: Callable[[BaseException], Any],
        exceptions: type[BaseException] | Sequence[type[BaseException]] = Exception,
    ) -> TryCatch:
        if isinstance(exceptions, type):
            normalized = (exceptions,)
        else:
            normalized = tuple(exceptions)
        return TryCatch(
            self.func,
            self.args,
            self.kwargs,
            self.handlers + (CatchHandler(normalized, handler),),
            self.else_action,
            self.final_action,
        )

    def else_(self, action: Callable[[Any], Any]) -> TryCatch:
        return TryCatch(self.func, self.args, self.kwargs, self.handlers, action, self.final_action)

    def finally_(self, action: Callable[[], Any]) -> TryCatch:
        return TryCatch(self.func, self.args, self.kwargs, self.handlers, self.else_action, action)

    def run(self) -> Result[Any]:
        try:
            value = self.func(*self.args, **self.kwargs)
            if inspect.isawaitable(value):
                return Err(TypeError("run() cannot execute an async function; use arun()"))
            if self.else_action is not None:
                side_value = self.else_action(value)
                if inspect.isawaitable(side_value):
                    return Err(TypeError("run() received an awaitable else_ action; use arun()"))
            return Ok(value)
        except Exception as exc:  # noqa: BLE001
            return self._handle_sync(exc)
        finally:
            if self.final_action is not None:
                self.final_action()

    async def arun(self) -> Result[Any]:
        try:
            value = self.func(*self.args, **self.kwargs)
            if inspect.isawaitable(value):
                value = await value
            if self.else_action is not None:
                side_value = self.else_action(value)
                if inspect.isawaitable(side_value):
                    await side_value
            return Ok(value)
        except Exception as exc:  # noqa: BLE001
            return await self._handle_async(exc)
        finally:
            if self.final_action is not None:
                side_value = self.final_action()
                if inspect.isawaitable(side_value):
                    await side_value

    # Familiar alias for people who search for "execute try/catch".
    execute = run

    def _handle_sync(self, exc: BaseException) -> Result[Any]:
        for catch in self.handlers:
            if isinstance(exc, catch.exceptions):
                try:
                    value = catch.handler(exc)
                    if inspect.isawaitable(value):
                        return Err(TypeError("run() received an awaitable except_ handler; use arun()"))
                    return Ok(value)
                except Exception as handler_exc:  # noqa: BLE001
                    return Err(handler_exc)
        return Err(exc)

    async def _handle_async(self, exc: BaseException) -> Result[Any]:
        for catch in self.handlers:
            if isinstance(exc, catch.exceptions):
                try:
                    value = catch.handler(exc)
                    if inspect.isawaitable(value):
                        value = await value
                    return Ok(value)
                except Exception as handler_exc:  # noqa: BLE001
                    return Err(handler_exc)
        return Err(exc)


def try_catch(func: Callable[..., Any], *args: Any, **kwargs: Any) -> TryCatch:
    """Create a fluent explicit try/except/else/finally block."""

    return TryCatch(func=func, args=args, kwargs=kwargs)
