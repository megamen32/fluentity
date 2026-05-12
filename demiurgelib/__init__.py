"""demiurgelib: small helpers for safe execution and lightweight orchestration."""

from .async_chain import AsyncChain
from .ifer import ConditionalExecutor
from .result import Err, Ok, Result, capture, is_err, is_ok, result
from .safe_getter import apply_to_list, safe_call, safe_map, try_get, try_get_attrs, try_gete, try_geta
from .tryer import TryExecutor

__all__ = [
    "AsyncChain",
    "ConditionalExecutor",
    "TryExecutor",
    "Ok",
    "Err",
    "Result",
    "capture",
    "result",
    "is_ok",
    "is_err",
    "try_get",
    "try_gete",
    "try_geta",
    "try_get_attrs",
    "apply_to_list",
    "safe_call",
    "safe_map",
    "TaskManager",
    "BaseTask",
]


def __getattr__(name: str):
    if name in {"TaskManager", "BaseTask"}:
        try:
            from .task_manager_db import BaseTask, TaskManager
        except ModuleNotFoundError as exc:
            missing = exc.name
            raise ModuleNotFoundError(
                f"{name} requires optional task queue dependencies. "
                f"Install the package normally with `pip install demiurgelib` or install `{missing}`."
            ) from exc
        return {"TaskManager": TaskManager, "BaseTask": BaseTask}[name]
    raise AttributeError(f"module 'demiurgelib' has no attribute {name!r}")
