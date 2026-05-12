"""Backward-compatible import path for the Result API."""

from .result import Err, Ok, Result, capture, is_err, is_ok, result

__all__ = ["Ok", "Err", "Result", "capture", "result", "is_ok", "is_err"]
