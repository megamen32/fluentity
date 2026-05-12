from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Sequence

from .attempt import Attempt, RetryConfig, attempt
from .result import Result


@dataclass(frozen=True)
class Policy:
    """Reusable reliability settings for many operations."""

    retry_config: Optional[RetryConfig] = None
    timeout_seconds: Optional[float] = None
    recover_handlers: tuple[tuple[tuple[type[BaseException], ...], Callable[[BaseException], Any]], ...] = ()
    error_taps: tuple[Callable[[BaseException], Any], ...] = field(default_factory=tuple)
    final_taps: tuple[Callable[[], Any], ...] = field(default_factory=tuple)

    def retry(
        self,
        times: int = 3,
        delay: float = 0.0,
        backoff: float = 1.0,
        exceptions: Sequence[type[BaseException]] = (Exception,),
    ) -> Policy:
        if times < 1:
            raise ValueError("retry times must be >= 1")
        if delay < 0:
            raise ValueError("retry delay must be >= 0")
        if backoff < 1:
            raise ValueError("retry backoff must be >= 1")
        return Policy(
            retry_config=RetryConfig(times, delay, backoff, tuple(exceptions)),
            timeout_seconds=self.timeout_seconds,
            recover_handlers=self.recover_handlers,
            error_taps=self.error_taps,
            final_taps=self.final_taps,
        )

    def timeout(self, seconds: float) -> Policy:
        if seconds <= 0:
            raise ValueError("timeout seconds must be > 0")
        return Policy(self.retry_config, seconds, self.recover_handlers, self.error_taps, self.final_taps)

    def recover(
        self,
        func: Callable[[BaseException], Any],
        exceptions: Sequence[type[BaseException]] = (Exception,),
    ) -> Policy:
        handler = (tuple(exceptions), func)
        return Policy(self.retry_config, self.timeout_seconds, self.recover_handlers + (handler,), self.error_taps, self.final_taps)

    def recover_value(self, value: Any, exceptions: Sequence[type[BaseException]] = (Exception,)) -> Policy:
        return self.recover(lambda error: value, exceptions=exceptions)

    def tap_error(self, func: Callable[[BaseException], Any]) -> Policy:
        return Policy(self.retry_config, self.timeout_seconds, self.recover_handlers, self.error_taps + (func,), self.final_taps)

    def finally_(self, func: Callable[[], Any]) -> Policy:
        return Policy(self.retry_config, self.timeout_seconds, self.recover_handlers, self.error_taps, self.final_taps + (func,))

    def attempt(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Attempt:
        chain = attempt(func, *args, **kwargs)
        if self.retry_config is not None:
            chain = chain.retry(
                times=self.retry_config.times,
                delay=self.retry_config.delay,
                backoff=self.retry_config.backoff,
                exceptions=self.retry_config.exceptions,
            )
        if self.timeout_seconds is not None:
            chain = chain.timeout(self.timeout_seconds)
        for tap in self.error_taps:
            chain = chain.tap_error(tap)
        for exceptions, handler in self.recover_handlers:
            chain = chain.recover(handler, exceptions=exceptions)
        for tap in self.final_taps:
            chain = chain.finally_(tap)
        return chain

    def run(self, func: Callable[..., Any], *args: Any, timeout: float | None = None, **kwargs: Any) -> Result[Any]:
        return self.attempt(func, *args, **kwargs).run(timeout=timeout)

    async def arun(self, func: Callable[..., Any], *args: Any, timeout: float | None = None, **kwargs: Any) -> Result[Any]:
        return await self.attempt(func, *args, **kwargs).arun(timeout=timeout)


def policy() -> Policy:
    """Create a reusable reliability policy."""

    return Policy()
