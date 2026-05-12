from __future__ import annotations

import asyncio
import functools
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Iterable, Optional

import cloudpickle
from peewee import BlobField, CharField, DateTimeField, ForeignKeyField, Model, TextField
from playhouse.sqlite_ext import SqliteExtDatabase

DEFAULT_DB_PATH = "tasks_db.sqlite"
db = SqliteExtDatabase(DEFAULT_DB_PATH, pragmas={"foreign_keys": 1, "journal_mode": "wal"})


class CloudPickleField(BlobField):
    """Peewee field that stores arbitrary Python objects with cloudpickle."""

    def python_value(self, value: bytes | None) -> Any:
        if value is None:
            return None
        return cloudpickle.loads(value)

    def db_value(self, value: Any) -> bytes | None:
        if value is None:
            return None
        return cloudpickle.dumps(value)


class BaseModel(Model):
    class Meta:
        database = db


class TaskManager(BaseModel):
    """A tiny persistent SQLite-backed task manager.

    It is intentionally simple: tasks are stored locally, picked up by status,
    executed concurrently, and marked as completed or failed.
    """

    name = CharField(primary_key=True)
    created_at = DateTimeField(default=datetime.now)

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.task_callbacks: list[Callable[[Any], Any | Awaitable[Any]]] = []

    @classmethod
    def configure_database(cls, path: str | Path = DEFAULT_DB_PATH) -> None:
        """Point the task manager to another SQLite file before initialization."""

        if not db.is_closed():
            db.close()
        db.init(str(path), pragmas={"foreign_keys": 1, "journal_mode": "wal"})

    @classmethod
    def initialize(cls) -> None:
        """Create required database tables if they do not exist."""

        if db.is_closed():
            db.connect()
        db.create_tables([TaskManager, BaseTask], safe=True)

    @classmethod
    def instance(
        cls,
        name: str,
        callback: Callable[[Any], Any | Awaitable[Any]] | None = None,
    ) -> "TaskManager":
        cls.initialize()
        manager, _ = cls.get_or_create(name=name)
        manager.task_callbacks = [callback] if callback else []
        return manager

    def add_callback(self, callback: Callable[[Any], Any | Awaitable[Any]]) -> "TaskManager":
        self.task_callbacks.append(callback)
        return self

    def add_task(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> "BaseTask":
        """Persist a task call and return the created task row."""

        return BaseTask.create(parent=self, run_function=functools.partial(func, *args, **kwargs))

    def to_task(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> "BaseTask":
        """Backward-compatible helper for turning a callable into a queued task."""

        return self.add_task(func, *args, **kwargs)

    def task(self, func: Callable[..., Any]) -> Callable[..., "BaseTask"]:
        """Decorator that queues a call instead of executing it immediately."""

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> "BaseTask":
            return self.add_task(func, *args, **kwargs)

        return wrapper

    async def start_tasks(
        self,
        *,
        poll_interval: float = 10.0,
        batch_size: int = 100,
        once: bool = False,
        reset_in_progress: bool = True,
    ) -> None:
        """Run pending tasks forever, or one batch when ``once=True``."""

        if reset_in_progress:
            BaseTask.update(status="pending").where(
                (BaseTask.parent == self) & (BaseTask.status == "in_progress")
            ).execute()

        while True:
            started = time.time()
            tasks = list(
                BaseTask.select()
                .where((BaseTask.parent == self) & (BaseTask.status == "pending"))
                .order_by(BaseTask.created_at.asc())
                .limit(batch_size)
            )

            if tasks:
                await asyncio.gather(*(self.run_task(task) for task in tasks))

            if once:
                return

            sleep_for = max(0.0, poll_interval - (time.time() - started))
            await asyncio.sleep(sleep_for)

    async def run_task(self, task: "BaseTask") -> Any:
        result = await task.run()
        for callback in self.task_callbacks:
            callback_result = callback(result)
            if asyncio.iscoroutine(callback_result):
                await callback_result
        return result


class BaseTask(BaseModel):
    parent = ForeignKeyField(TaskManager, backref="tasks")
    status = CharField(default="pending", index=True)
    error = TextField(null=True)
    created_at = DateTimeField(default=datetime.now)
    started_at = DateTimeField(null=True)
    finished_at = DateTimeField(null=True)
    result = CloudPickleField(null=True)
    run_function = CloudPickleField(null=True)

    async def run(self) -> Any:
        self.status = "in_progress"
        self.started_at = datetime.now()
        self.save()

        try:
            run = self.run_function or self.start
            result = await _execute_callable(run)
        except Exception as exc:
            self.status = "failed"
            self.error = repr(exc)
            self.finished_at = datetime.now()
            self.save()
            raise

        self.result = result
        self.status = "completed"
        self.error = None
        self.finished_at = datetime.now()
        self.save()
        return result

    async def start(self) -> Any:
        raise NotImplementedError("BaseTask.start() must be implemented or run_function must be provided.")

    def __str__(self) -> str:
        if self.result is None:
            return ""
        if isinstance(self.result, Iterable) and not isinstance(self.result, (str, bytes, dict)):
            return "\n".join(str(item) for item in self.result)
        return str(self.result)


async def _execute_callable(func: Callable[..., Any]) -> Any:
    if asyncio.iscoroutinefunction(func):
        return await func()

    result = await asyncio.get_running_loop().run_in_executor(None, func)
    if asyncio.iscoroutine(result):
        return await result
    if asyncio.iscoroutinefunction(result):
        return await result()
    return result


def async_callback_wrapper(async_func: Callable[..., Awaitable[Any]], *args: Any, **kwargs: Any) -> Callable[[], Awaitable[Any]]:
    @functools.wraps(async_func)
    async def wrapped() -> Any:
        return await async_func(*args, **kwargs)

    return wrapped
