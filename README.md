# demiurgelib

**A compact Python utility library for safer execution, fluent control flow, async pipelines, and lightweight persisted task queues.**

`demiurgelib` is a small toolbox for projects where you repeatedly need the same pragmatic patterns:

- run fragile code without breaking the whole pipeline;
- express conditional logic in a fluent, readable style;
- build sequential async/sync chains;
- wrap tasks, persist them in SQLite, and execute them later;
- use a tiny Rust-like `Result` pattern when exceptions are not the best control-flow mechanism.

The library is intentionally lightweight. It does not try to become a framework. It gives you small building blocks that can be copied into scripts, bots, automation tools, parsers, and backend utilities.

## Why use it?

Python projects often accumulate the same small helpers again and again: `try/except` wrappers, fallback getters, delayed task execution, conditional callbacks, simple async chains, and database-backed background jobs. `demiurgelib` puts these patterns in one place with a minimal API.

Use it when you want practical utilities that keep code short without hiding too much behavior behind abstractions.

## Features

- **Safe getters** — execute a callable and return a fallback instead of crashing.
- **Batch-safe mapping** — apply a function to a list while skipping failed elements.
- **Rust-like `Result` objects** — return `Ok(value)` or `Err(error)` explicitly.
- **Fluent conditional execution** — chain `if_`, `then`, `elif_`, `else_`, `finally_` calls.
- **Fluent try/except/finally wrapper** — describe error handling as a small execution object.
- **AsyncChain** — compose sync and async steps into one sequential pipeline.
- **SQLite task manager** — persist callable tasks with `peewee` and `cloudpickle`.

## Examples

### Safe execution with fallback values

```python
from safe_getter import try_get, try_gete

value = try_get(lambda: int("42"), default=0)
print(value)  # 42

value = try_get(lambda: int("not-a-number"), default=0)
print(value)  # 0

result, error = try_gete(lambda: 1 / 0, default=None)
print(result)  # None
print(error)   # division by zero
```

### Apply a risky function to a list

```python
from safe_getter import try_geta

items = ["1", "2", "bad", "4"]
converted = try_geta(items, int, skip_none=True)

print(converted)  # [1, 2, 4]
```

### Rust-like `Result` objects

```python
from safe_getter_rust import Ok, Err, divide

result = divide(10, 2)

match result:
    case Ok(value):
        print(f"Success: {value}")
    case Err(error):
        print(f"Failed: {error}")
```

You can also unwrap successful values:

```python
value = divide(10, 2).unwrap()
```

If the result is `Err`, `unwrap()` raises the stored exception.

### Fluent conditional logic

```python
from ifer import ConditionalExecutor

user_score = 87

(
    ConditionalExecutor()
    .if_(lambda: user_score >= 90)
    .then(lambda: print("excellent"))
    .elif_(lambda: user_score >= 70)
    .then(lambda: print("good"))
    .else_(lambda: print("needs improvement"))
    .finally_(lambda: print("checked"))
    .execute()
)
```

### Fluent try/except/finally logic

```python
from tryer import TryExecutor

result = (
    TryExecutor(lambda: int("bad"))
    .except_(lambda error: print(f"Handled: {error}"))
    .else_(lambda: print("No error"))
    .finally_(lambda: print("Cleanup"))
    .execute()
)
```

### Sequential async/sync pipeline

```python
import asyncio
from AsyncChain import AsyncChain

async def load_data():
    return 10

def multiply(value):
    return value * 2

async def save_result(value):
    print(f"Saved: {value}")
    return value

async def main():
    result = await (
        AsyncChain()
        .add(load_data)
        .add_delay(1)
        .add(multiply)
        .on_complete(save_result)
        .run()
    )

    print(result)  # 20

asyncio.run(main())
```

### Persisted task queue with SQLite

```python
import asyncio
import time

from task_manager_db import TaskManager, BaseTask

TaskManager.create_table(safe=True)
BaseTask.create_table(safe=True)

manager = TaskManager.instance(name="example")

@manager.task
def heavy_job(x: int) -> int:
    time.sleep(2)
    return x * x

async def main():
    heavy_job(5)
    await manager.start_tasks()

asyncio.run(main())
```

The task manager stores tasks in `tasks_db.sqlite` and executes pending tasks asynchronously.

## Installation

### From source

```bash
git clone https://github.com/<your-username>/demiurgelib.git
cd demiurgelib
python -m pip install -e .
```

### Required dependencies

The core helpers use only the Python standard library. The SQLite task manager additionally requires:

```bash
python -m pip install peewee cloudpickle
```

When installed through `pyproject.toml`, these dependencies are installed automatically.

## Project structure

```text
.
├── AsyncChain.py              # Sequential sync/async pipeline builder
├── ifer.py                    # Fluent conditional executor
├── safe_getter.py             # Safe fallback helpers
├── safe_getter_rust.py        # Rust-like Result / Ok / Err helpers
├── task_manager_db.py         # SQLite-backed task manager
├── task_manager_example.py    # Example task manager usage
├── tryer.py                   # Fluent try/except/finally executor
├── example.ipynb              # Notebook example
├── pyproject.toml             # Packaging metadata
└── README.md
```

## API overview

### `safe_getter`

| Function | Purpose |
| --- | --- |
| `try_gete(func, default=None, log_exc=False)` | Return `(result, exception)` after executing a callable. |
| `try_get(func, default=None, return_exception=False, **kwargs)` | Return result, default value, or exception. |
| `try_geta(arr, func, skip_none=True, default_element=None)` | Apply a callable to each item safely. |
| `try_get_attrs(obj_func, attrs, defaults)` | Safely read several attributes from an object. |
| `apply_to_list(lst, func, filter_func=None, return_all=True)` | Apply a callable to filtered list items. |

### `safe_getter_rust`

| Object | Purpose |
| --- | --- |
| `Ok(value)` | Successful result wrapper. |
| `Err(error)` | Failed result wrapper. |
| `Result` | Type alias for `Ok[T] | Err[E]`. |
| `result(func)` | Execute a callable and wrap the result in `Ok` or `Err`. |
| `divide(x, y)` | Small example function returning `Result`. |

### `AsyncChain`

| Method | Purpose |
| --- | --- |
| `add(func)` | Add a sync or async step. |
| `add_delay(seconds)` | Add an async delay step. |
| `add_condition_wait(condition_func, timeout=None)` | Wait until a condition becomes true. |
| `on_complete(func)` | Add a final handler. |
| `on_error(func)` | Add an error handler. |
| `run()` | Execute the chain and return the final result. |

## Requirements

- Python 3.10+
- `peewee` and `cloudpickle` for the task manager

## Notes

`demiurgelib` is best treated as a small utility package rather than a strict application framework. The modules are independent, so you can use only the parts you need.

For production systems, review task serialization carefully: `cloudpickle` is powerful, but persisted executable callables should be treated as trusted code only.
