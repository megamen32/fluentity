from __future__ import annotations

import asyncio
import inspect
import time
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, Optional, Sequence, TypeVar

from .result import Err, Ok, Result, is_err

T = TypeVar("T")
U = TypeVar("U")


class EnsureError(ValueError):
    """Raised inside Result when an ensure predicate rejects a value."""


class RetryConditionError(RuntimeError):
    """Returned when retry_if keeps rejecting successful values."""

    def __init__(self, value: Any, message: str = "retry condition stayed true") -> None:
        super().__init__(message)
        self.value = value


@dataclass(frozen=True)
class RetryConfig:
    times: int = 3
    delay: float = 0.0
    backoff: float = 1.0
    exceptions: tuple[type[BaseException], ...] = (Exception,)


@dataclass(frozen=True)
class RetryIfConfig:
    predicate: Callable[[Any], bool]
    error: str | BaseException | Callable[[Any], str | BaseException] = "retry condition stayed true"


@dataclass(frozen=True)
class Step:
    kind: str
    func: Callable[..., Any]
    error: Any = None


@dataclass(frozen=True)
class Attempt:
    """A lazy description of a reliable sync or async operation.

    Configure the operation with methods such as retry(), ensure(), then(),
    recover(), and timeout(), then call run()/arun(). For async code you can
    also await the Attempt object directly.
    """

    func: Callable[..., Any]
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] = field(default_factory=dict)
    steps: tuple[Step, ...] = ()
    retry_config: Optional[RetryConfig] = None
    retry_if_config: Optional[RetryIfConfig] = None
    timeout_seconds: Optional[float] = None
    recover_handlers: tuple[tuple[tuple[type[BaseException], ...], Callable[[BaseException], Any]], ...] = ()
    error_taps: tuple[Callable[[BaseException], Any], ...] = ()
    final_taps: tuple[Callable[[], Any], ...] = ()

    def __await__(self):
        """Allow ``await attempt(...)`` as a compact async shorthand."""

        return self.arun().__await__()

    def then(self, func: Callable[[Any], Any]) -> Attempt:
        """Run another step only if the previous step succeeded."""

        return self._with_step(Step("then", func))

    def tap(self, func: Callable[[Any], Any]) -> Attempt:
        """Run a side effect on a successful value without changing it."""

        return self._with_step(Step("tap", func))

    def tap_error(self, func: Callable[[BaseException], Any]) -> Attempt:
        """Run a side effect when the operation fails."""

        return Attempt(**{**self.__dict__, "error_taps": self.error_taps + (func,)})

    def finally_(self, func: Callable[[], Any]) -> Attempt:
        """Run a side effect after success, error, or recovery."""

        return Attempt(**{**self.__dict__, "final_taps": self.final_taps + (func,)})

    def ensure(
        self,
        predicate: Callable[[Any], bool],
        error: str | BaseException | Callable[[Any], str | BaseException] = "Condition failed",
    ) -> Attempt:
        """Reject a successful value unless predicate(value) is truthy."""

        return self._with_step(Step("ensure", predicate, error))

    def ensure_not_none(self, error: str | BaseException = "Expected a value, got None") -> Attempt:
        """Reject a successful value if it is None."""

        return self.ensure(lambda value: value is not None, error)

    def retry(
        self,
        times: int = 3,
        delay: float = 0.0,
        backoff: float = 1.0,
        exceptions: Sequence[type[BaseException]] = (Exception,),
    ) -> Attempt:
        """Retry the initial callable when it raises one of the selected exceptions."""

        if times < 1:
            raise ValueError("retry times must be >= 1")
        if delay < 0:
            raise ValueError("retry delay must be >= 0")
        if backoff < 1:
            raise ValueError("retry backoff must be >= 1")
        return Attempt(**{**self.__dict__, "retry_config": RetryConfig(times, delay, backoff, tuple(exceptions))})

    def retry_if(
        self,
        predicate: Callable[[Any], bool],
        *,
        times: int = 3,
        delay: float = 0.0,
        backoff: float = 1.0,
        error: str | BaseException | Callable[[Any], str | BaseException] = "retry condition stayed true",
    ) -> Attempt:
        """Retry the initial callable while predicate(successful_value) is truthy."""

        return self.retry(times=times, delay=delay, backoff=backoff).replace(retry_if_config=RetryIfConfig(predicate, error))

    def timeout(self, seconds: float) -> Attempt:
        """Limit async execution time."""

        if seconds <= 0:
            raise ValueError("timeout seconds must be > 0")
        return Attempt(**{**self.__dict__, "timeout_seconds": seconds})

    def recover(
        self,
        func: Callable[[BaseException], Any],
        exceptions: Sequence[type[BaseException]] = (Exception,),
    ) -> Attempt:
        """Convert selected final errors into a successful fallback value."""

        handler = (tuple(exceptions), func)
        return Attempt(**{**self.__dict__, "recover_handlers": self.recover_handlers + (handler,)})

    def recover_value(self, value: Any, exceptions: Sequence[type[BaseException]] = (Exception,)) -> Attempt:
        """Convert selected final errors into a fixed successful fallback value."""

        return self.recover(lambda error: value, exceptions=exceptions)

    def replace(self, **changes: Any) -> Attempt:
        """Return a copy with selected fields changed."""

        return Attempt(**{**self.__dict__, **changes})

    def run(self, *, timeout: float | None = None) -> Result[Any]:
        """Execute synchronously and return Result.

        ``timeout`` is accepted for API symmetry, but arbitrary synchronous
        Python code cannot be safely cancelled without threads/processes. Use
        arun(timeout=...) or .timeout(...).arun() for enforceable timeouts.
        """

        if inspect.iscoroutinefunction(self.func):
            return Err(TypeError("run() cannot execute an async function; use arun() or await attempt(...)"))
        if timeout is not None or self.timeout_seconds is not None:
            return Err(TypeError("sync run() does not enforce timeouts; use arun(timeout=...) for async code"))
        result = self._run_initial_sync()
        result = self._run_steps_sync(result)
        try:
            return self._finalize_sync(result)
        finally:
            self._run_final_taps_sync()

    async def arun(self, *, timeout: float | None = None) -> Result[Any]:
        """Execute with async support and return Result."""

        selected_timeout = timeout if timeout is not None else self.timeout_seconds
        coro = self._run_initial_async()
        if selected_timeout is not None:
            if selected_timeout <= 0:
                return Err(ValueError("timeout seconds must be > 0"))
            try:
                result = await asyncio.wait_for(coro, timeout=selected_timeout)
            except Exception as exc:  # noqa: BLE001
                result = Err(exc)
        else:
            result = await coro
        result = await self._run_steps_async(result)
        try:
            return await self._finalize_async(result)
        finally:
            await self._run_final_taps_async()

    def _with_step(self, step: Step) -> Attempt:
        return Attempt(**{**self.__dict__, "steps": self.steps + (step,)})

    def _run_initial_sync(self) -> Result[Any]:
        cfg = self.retry_config or RetryConfig(times=1)
        current_delay = cfg.delay
        last_error: BaseException | None = None
        for attempt_number in range(cfg.times):
            try:
                value = self.func(*self.args, **self.kwargs)
                if inspect.isawaitable(value):
                    return Err(TypeError("sync run() received an awaitable; use arun()"))
                retry_error = self._retry_if_error_sync(value)
                if retry_error is None:
                    return Ok(value)
                last_error = retry_error
                if attempt_number < cfg.times - 1 and current_delay:
                    time.sleep(current_delay)
                    current_delay *= cfg.backoff
            except cfg.exceptions as exc:
                last_error = exc
                if attempt_number < cfg.times - 1 and current_delay:
                    time.sleep(current_delay)
                    current_delay *= cfg.backoff
            except Exception as exc:  # noqa: BLE001
                return Err(exc)
        return Err(last_error or RuntimeError("operation failed"))

    async def _run_initial_async(self) -> Result[Any]:
        cfg = self.retry_config or RetryConfig(times=1)
        current_delay = cfg.delay
        last_error: BaseException | None = None
        for attempt_number in range(cfg.times):
            try:
                value = self.func(*self.args, **self.kwargs)
                if inspect.isawaitable(value):
                    value = await value
                retry_error = await self._retry_if_error_async(value)
                if retry_error is None:
                    return Ok(value)
                last_error = retry_error
                if attempt_number < cfg.times - 1 and current_delay:
                    await asyncio.sleep(current_delay)
                    current_delay *= cfg.backoff
            except cfg.exceptions as exc:
                last_error = exc
                if attempt_number < cfg.times - 1 and current_delay:
                    await asyncio.sleep(current_delay)
                    current_delay *= cfg.backoff
            except Exception as exc:  # noqa: BLE001
                return Err(exc)
        return Err(last_error or RuntimeError("operation failed"))

    def _retry_if_error_sync(self, value: Any) -> BaseException | None:
        if self.retry_if_config is None:
            return None
        should_retry = self.retry_if_config.predicate(value)
        if inspect.isawaitable(should_retry):
            return TypeError("sync run() received an awaitable retry_if predicate; use arun()")
        if should_retry:
            resolved = self._ensure_error(self.retry_if_config.error, value)
            return RetryConditionError(value, str(resolved))
        return None

    async def _retry_if_error_async(self, value: Any) -> BaseException | None:
        if self.retry_if_config is None:
            return None
        should_retry = self.retry_if_config.predicate(value)
        if inspect.isawaitable(should_retry):
            should_retry = await should_retry
        if should_retry:
            resolved = self._ensure_error(self.retry_if_config.error, value)
            return RetryConditionError(value, str(resolved))
        return None

    def _run_steps_sync(self, result: Result[Any]) -> Result[Any]:
        current = result
        for step in self.steps:
            if is_err(current):
                return current
            value = current.value
            try:
                if step.kind == "then":
                    next_value = step.func(value)
                    if inspect.isawaitable(next_value):
                        return Err(TypeError("sync run() received an awaitable step; use arun()"))
                    current = Ok(next_value)
                elif step.kind == "tap":
                    side_value = step.func(value)
                    if inspect.isawaitable(side_value):
                        return Err(TypeError("sync run() received an awaitable tap; use arun()"))
                    current = Ok(value)
                elif step.kind == "ensure":
                    if not step.func(value):
                        current = Err(self._ensure_error(step.error, value))
            except Exception as exc:  # noqa: BLE001
                return Err(exc)
        return current

    async def _run_steps_async(self, result: Result[Any]) -> Result[Any]:
        current = result
        for step in self.steps:
            if is_err(current):
                return current
            value = current.value
            try:
                if step.kind == "then":
                    next_value = step.func(value)
                    if inspect.isawaitable(next_value):
                        next_value = await next_value
                    current = Ok(next_value)
                elif step.kind == "tap":
                    side_value = step.func(value)
                    if inspect.isawaitable(side_value):
                        await side_value
                    current = Ok(value)
                elif step.kind == "ensure":
                    predicate_value = step.func(value)
                    if inspect.isawaitable(predicate_value):
                        predicate_value = await predicate_value
                    if not predicate_value:
                        current = Err(self._ensure_error(step.error, value))
            except Exception as exc:  # noqa: BLE001
                return Err(exc)
        return current

    def _finalize_sync(self, result: Result[Any]) -> Result[Any]:
        if not is_err(result):
            return result
        self._tap_errors_sync(result.error)
        handler = self._select_recover_handler(result.error)
        if handler is None:
            return result
        try:
            value = handler(result.error)
            if inspect.isawaitable(value):
                return Err(TypeError("sync run() received an awaitable recover function; use arun()"))
            return Ok(value)
        except Exception as exc:  # noqa: BLE001
            return Err(exc)

    async def _finalize_async(self, result: Result[Any]) -> Result[Any]:
        if not is_err(result):
            return result
        await self._tap_errors_async(result.error)
        handler = self._select_recover_handler(result.error)
        if handler is None:
            return result
        try:
            value = handler(result.error)
            if inspect.isawaitable(value):
                value = await value
            return Ok(value)
        except Exception as exc:  # noqa: BLE001
            return Err(exc)

    def _select_recover_handler(self, error: BaseException) -> Callable[[BaseException], Any] | None:
        for exceptions, handler in self.recover_handlers:
            if isinstance(error, exceptions):
                return handler
        return None

    def _tap_errors_sync(self, error: BaseException) -> None:
        for tap in self.error_taps:
            try:
                tap(error)
            except Exception:
                pass

    async def _tap_errors_async(self, error: BaseException) -> None:
        for tap in self.error_taps:
            try:
                value = tap(error)
                if inspect.isawaitable(value):
                    await value
            except Exception:
                pass

    def _run_final_taps_sync(self) -> None:
        for tap in self.final_taps:
            try:
                value = tap()
                if inspect.isawaitable(value):
                    pass
            except Exception:
                pass

    async def _run_final_taps_async(self) -> None:
        for tap in self.final_taps:
            try:
                value = tap()
                if inspect.isawaitable(value):
                    await value
            except Exception:
                pass

    @staticmethod
    def _ensure_error(error: str | BaseException | Callable[[Any], str | BaseException], value: Any) -> BaseException:
        resolved = error(value) if callable(error) else error
        if isinstance(resolved, BaseException):
            return resolved
        return EnsureError(str(resolved))


def attempt(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Attempt:
    """Create a reliable operation around a callable."""

    return Attempt(func=func, args=args, kwargs=kwargs)


async def aretry(
    func: Callable[..., Any],
    *args: Any,
    times: int = 3,
    delay: float = 0.0,
    backoff: float = 1.0,
    **kwargs: Any,
) -> Result[Any]:
    return await attempt(func, *args, **kwargs).retry(times=times, delay=delay, backoff=backoff).arun()


def retry(
    func: Callable[..., Any],
    *args: Any,
    times: int = 3,
    delay: float = 0.0,
    backoff: float = 1.0,
    **kwargs: Any,
) -> Result[Any]:
    return attempt(func, *args, **kwargs).retry(times=times, delay=delay, backoff=backoff).run()


def retryable(
    times: int = 3,
    delay: float = 0.0,
    backoff: float = 1.0,
    exceptions: Sequence[type[BaseException]] = (Exception,),
) -> Callable[[Callable[..., Any]], Callable[..., Result[Any]]]:
    """Decorate a sync function so calls are retried and returned as Result."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Result[Any]]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Result[Any]:
            return attempt(func, *args, **kwargs).retry(times=times, delay=delay, backoff=backoff, exceptions=exceptions).run()

        return wrapper

    return decorator


def timeoutable(seconds: float) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorate an async function so calls are timeout-limited and returned as Result."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Result[Any]:
            return await attempt(func, *args, **kwargs).arun(timeout=seconds)

        return wrapper

    return decorator
