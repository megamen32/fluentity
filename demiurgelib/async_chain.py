from __future__ import annotations

import asyncio
import inspect
from typing import Any, Awaitable, Callable, List, Optional

Step = Callable[..., Any | Awaitable[Any]]


class AsyncChain:
    """Small fluent pipeline for mixing sync and async steps."""

    def __init__(self, initial: Any = None):
        self.initial = initial
        self.tasks: List[Step] = []
        self.on_complete_handler: Optional[Step] = None
        self.error_handler: Optional[Step] = None

    def add(self, func: Step) -> "AsyncChain":
        self.tasks.append(func)
        return self

    def then(self, func: Step) -> "AsyncChain":
        return self.add(func)

    def on_complete(self, func: Step) -> "AsyncChain":
        self.on_complete_handler = func
        return self

    def on_error(self, func: Step) -> "AsyncChain":
        self.error_handler = func
        return self

    def add_delay(self, seconds: float) -> "AsyncChain":
        async def delay(value: Any) -> Any:
            await asyncio.sleep(seconds)
            return value

        self.tasks.append(delay)
        return self

    def add_condition_wait(
        self,
        condition_func: Callable[[], bool | Awaitable[bool]],
        timeout: float | None = None,
        interval: float = 0.1,
    ) -> "AsyncChain":
        async def wait_condition(value: Any) -> Any:
            start_time = asyncio.get_running_loop().time()
            while True:
                condition = condition_func()
                if inspect.isawaitable(condition):
                    condition = await condition
                if condition:
                    return value
                if timeout is not None and (asyncio.get_running_loop().time() - start_time) > timeout:
                    raise TimeoutError("Condition wait timed out")
                await asyncio.sleep(interval)

        self.tasks.append(wait_condition)
        return self

    async def run(self, initial: Any = None) -> Any:
        result = self.initial if initial is None else initial
        try:
            for task in self.tasks:
                result = await _call_step(task, result)
        except Exception as exc:
            if self.error_handler is None:
                raise
            return await _call_step(self.error_handler, exc)

        if self.on_complete_handler is not None:
            result = await _call_step(self.on_complete_handler, result)
        return result


async def _call_step(func: Step, value: Any) -> Any:
    signature = inspect.signature(func)
    if signature.parameters:
        result = func(value)
    else:
        result = func()
    if inspect.isawaitable(result):
        return await result
    return result
