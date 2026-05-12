"""Fluentity: fluent reliability primitives for Python functions."""

from .attempt import Attempt, EnsureError, RetryConditionError, aretry, attempt, retry, retryable, timeoutable
from .policy import Policy, policy
from .result import Err, Ok, Result, capture, is_err, is_ok, result, safe
from .try_catch import TryCatch, try_catch
from .chain import Chain, chain
from .choose import Chooser, choose
from .path import get_path
from .safe_getter import apply_to_list, safe_call, safe_map, try_get, try_get_attrs, try_geta, try_gete

__all__ = [
    "Attempt",
    "EnsureError",
    "RetryConditionError",
    "Policy",
    "Ok",
    "Err",
    "Result",
    "attempt",
    "policy",
    "Chain",
    "chain",
    "Chooser",
    "choose",
    "get_path",
    "retry",
    "aretry",
    "retryable",
    "timeoutable",
    "TryCatch",
    "try_catch",
    "capture",
    "safe",
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
]


def __getattr__(name: str):
    if name in {"TaskManager", "BaseTask"}:
        from .task_manager_db import BaseTask, TaskManager

        return {"TaskManager": TaskManager, "BaseTask": BaseTask}[name]
    raise AttributeError(f"module 'fluentity' has no attribute {name!r}")
