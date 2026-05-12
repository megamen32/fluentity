from __future__ import annotations

import logging
from typing import Callable, List, Optional, Tuple, Type

Condition = Callable[[], bool]
Action = Callable[[], object]


class ConditionalExecutor:
    """Fluent if/elif/else/finally helper for dynamic workflows."""

    def __init__(self):
        self.actions: List[Tuple[Condition, Action]] = []
        self._pending_condition: Optional[Condition] = None
        self.else_action: Optional[Action] = None
        self.final_action: Optional[Action] = None
        self.exception_action: Optional[Tuple[Type[BaseException], bool, bool]] = None

    def if_(self, condition: Condition) -> "ConditionalExecutor":
        self._pending_condition = condition
        return self

    def elif_(self, condition: Condition) -> "ConditionalExecutor":
        return self.if_(condition)

    def then(self, action: Action) -> "ConditionalExecutor":
        if self._pending_condition is None:
            raise ValueError("then() must be called after if_() or elif_().")
        self.actions.append((self._pending_condition, action))
        self._pending_condition = None
        return self

    def else_(self, action: Action) -> "ConditionalExecutor":
        self.else_action = action
        return self

    def finally_(self, action: Action) -> "ConditionalExecutor":
        self.final_action = action
        return self

    def on_except(
        self,
        exception_type: Type[BaseException] = Exception,
        log: bool = False,
        continue_after_error: bool = False,
    ) -> "ConditionalExecutor":
        self.exception_action = (exception_type, log, continue_after_error)
        return self

    def execute(self) -> object | None:
        result = None
        try:
            for condition, action in self.actions:
                if condition():
                    result = action()
                    break
            else:
                if self.else_action is not None:
                    result = self.else_action()
        except Exception as exc:
            if self.exception_action is None:
                raise
            exception_type, log, continue_after_error = self.exception_action
            if not isinstance(exc, exception_type):
                raise
            if log:
                logging.exception(f"ConditionalExecutor failed: {exc}")
            if continue_after_error:
                return result
            return None
        finally:
            if self.final_action is not None:
                self.final_action()
        return result
