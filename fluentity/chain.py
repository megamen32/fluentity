from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass, field
from typing import Any, Callable

from .result import Err, Ok, Result, is_err


@dataclass(frozen=True)
class ChainStep:
    kind: str
    func: Callable[..., Any] | None = None
    seconds: float | None = None
    timeout: float | None = None
    interval: float = 0.1


@dataclass(frozen=True)
class Chain:
    """Readable async-first pipeline for steps, delays, waits, and hooks."""

    steps: tuple[ChainStep, ...] = ()
    complete_hooks: tuple[Callable[[Any], Any], ...] = ()
    error_hooks: tuple[Callable[[BaseException], Any], ...] = ()

    def then(self, func: Callable[[Any], Any]) -> Chain:
        return self._with_step(ChainStep("then", func=func))

    def add(self, func: Callable[[Any], Any]) -> Chain:
        return self.then(func)

    def delay(self, seconds: float) -> Chain:
        if seconds < 0:
            raise ValueError("delay seconds must be >= 0")
        return self._with_step(ChainStep("delay", seconds=seconds))

    def wait_until(self, condition: Callable[[], bool], *, timeout: float | None = None, interval: float = 0.1) -> Chain:
        if timeout is not None and timeout <= 0:
            raise ValueError("timeout must be > 0")
        if interval <= 0:
            raise ValueError("interval must be > 0")
        return self._with_step(ChainStep("wait", func=condition, timeout=timeout, interval=interval))

    def on_complete(self, func: Callable[[Any], Any]) -> Chain:
        return Chain(self.steps, self.complete_hooks + (func,), self.error_hooks)

    def on_error(self, func: Callable[[BaseException], Any]) -> Chain:
        return Chain(self.steps, self.complete_hooks, self.error_hooks + (func,))

    def __await__(self):
        return self.run().__await__()

    async def run(self, initial: Any = None, *, timeout: float | None = None) -> Result[Any]:
        try:
            if timeout is not None:
                return await asyncio.wait_for(self._run(initial), timeout=timeout)
            return await self._run(initial)
        except Exception as exc:  # noqa: BLE001
            await self._notify_error(exc)
            return Err(exc)

    async def _run(self, initial: Any) -> Result[Any]:
        current = initial
        for step in self.steps:
            try:
                if step.kind == "then":
                    assert step.func is not None
                    value = step.func(current)
                    if inspect.isawaitable(value):
                        value = await value
                    current = value
                elif step.kind == "delay":
                    await asyncio.sleep(step.seconds or 0)
                elif step.kind == "wait":
                    assert step.func is not None
                    await self._wait_until(step.func, step.timeout, step.interval)
            except Exception as exc:  # noqa: BLE001
                await self._notify_error(exc)
                return Err(exc)
        await self._notify_complete(current)
        return Ok(current)

    async def _wait_until(self, condition: Callable[[], bool], timeout: float | None, interval: float) -> None:
        async def loop() -> None:
            while True:
                value = condition()
                if inspect.isawaitable(value):
                    value = await value
                if value:
                    return
                await asyncio.sleep(interval)

        if timeout is None:
            await loop()
        else:
            await asyncio.wait_for(loop(), timeout=timeout)

    async def _notify_complete(self, value: Any) -> None:
        for hook in self.complete_hooks:
            try:
                result = hook(value)
                if inspect.isawaitable(result):
                    await result
            except Exception:
                pass

    async def _notify_error(self, error: BaseException) -> None:
        for hook in self.error_hooks:
            try:
                result = hook(error)
                if inspect.isawaitable(result):
                    await result
            except Exception:
                pass

    def _with_step(self, step: ChainStep) -> Chain:
        return Chain(self.steps + (step,), self.complete_hooks, self.error_hooks)


def chain() -> Chain:
    return Chain()
