from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable

from .result import Err, Ok, Result


@dataclass(frozen=True)
class Case:
    predicate: Callable[[], bool]
    action: Callable[[], Any]


@dataclass(frozen=True)
class Chooser:
    """Small fluent conditional helper for menu/status/business branches."""

    cases: tuple[Case, ...] = ()
    fallback: Callable[[], Any] | None = None

    def when(self, predicate: Callable[[], bool], action: Callable[[], Any]) -> Chooser:
        return Chooser(self.cases + (Case(predicate, action),), self.fallback)

    def otherwise(self, action: Callable[[], Any]) -> Chooser:
        return Chooser(self.cases, action)

    def run(self) -> Result[Any]:
        try:
            for case in self.cases:
                if case.predicate():
                    value = case.action()
                    if inspect.isawaitable(value):
                        return Err(TypeError("choose().run() received an awaitable action; use arun()"))
                    return Ok(value)
            if self.fallback is None:
                return Ok(None)
            value = self.fallback()
            if inspect.isawaitable(value):
                return Err(TypeError("choose().run() received an awaitable fallback; use arun()"))
            return Ok(value)
        except Exception as exc:  # noqa: BLE001
            return Err(exc)

    async def arun(self) -> Result[Any]:
        try:
            for case in self.cases:
                predicate_value = case.predicate()
                if inspect.isawaitable(predicate_value):
                    predicate_value = await predicate_value
                if predicate_value:
                    value = case.action()
                    if inspect.isawaitable(value):
                        value = await value
                    return Ok(value)
            if self.fallback is None:
                return Ok(None)
            value = self.fallback()
            if inspect.isawaitable(value):
                value = await value
            return Ok(value)
        except Exception as exc:  # noqa: BLE001
            return Err(exc)

    def __await__(self):
        return self.arun().__await__()


def choose() -> Chooser:
    return Chooser()
