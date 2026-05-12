# fluent-control

**Small Python helpers for code that should keep moving even when individual steps fail.**

`fluent-control` is a compact utility library for scripts, bots, parsers, automation jobs, and small backend services. It gives you a practical set of primitives for safe function calls, Rust-like `Result` values, fluent `try/except` and `if/else` blocks, async pipelines, and a simple SQLite-backed local task queue.

The goal is not to replace large workflow frameworks. The goal is to remove repetitive boilerplate from everyday Python code where you need to run many small operations, handle partial failures, and keep the control flow readable.

## Why it is useful

Real automation code often has the same recurring problems:

- one bad item breaks the whole batch;
- `try/except` blocks hide the main logic;
- sync and async functions need to be chained together;
- small background jobs need persistence, but Celery/RQ/Airflow are too heavy;
- scripts need to look clean enough to maintain later.

`fluent-control` focuses exactly on that middle layer: safer calls, clearer flow, and lightweight orchestration.

## Features

- **Safe calls**: run callables with fallback values instead of crashing the whole process.
- **`Result` API**: use `Ok(value)` / `Err(error)` with `unwrap`, `unwrap_or`, `map`, `bind`, and pattern matching.
- **Fluent control flow**: express `try/except/else/finally` and `if/elif/else/finally` chains declaratively.
- **Async pipelines**: chain sync and async steps in one readable `AsyncChain`.
- **Persistent task queue**: store local tasks in SQLite and execute them later.
- **Small surface area**: no complex service, broker, worker cluster, or configuration system.

## Quick examples

### Safe fallback for fragile code

```python
from fluent_control import try_get

username = try_get(
    lambda: payload["user"]["profile"]["username"],
    default="anonymous",
)
```

### Rust-like `Result`

```python
from fluent_control import Ok, Err, capture

result = capture(lambda: 10 / 2)

match result:
    case Ok(value):
        print(f"Success: {value}")
    case Err(error):
        print(f"Failed: {error}")
```

### Transform only successful values

```python
from fluent_control import capture

result = (
    capture(lambda: "42")
    .map(int)
    .map(lambda value: value * 2)
    .unwrap_or(0)
)

print(result)  # 84
```

### Fluent `try/except/else/finally`

```python
from fluent_control import TryExecutor

value = (
    TryExecutor(lambda: int("123"))
    .except_(lambda error: print(f"Bad value: {error}"), ValueError)
    .else_(lambda result: print(f"Parsed: {result}"))
    .finally_(lambda: print("Done"))
    .execute()
)
```

### Fluent condition tree

```python
from fluent_control import ConditionalExecutor

status = "premium"

message = (
    ConditionalExecutor()
    .if_(lambda: status == "admin")
    .then(lambda: "Full access")
    .elif_(lambda: status == "premium")
    .then(lambda: "Premium access")
    .else_(lambda: "Basic access")
    .execute()
)
```

### Async pipeline with sync and async steps

```python
import asyncio
from fluent_control import AsyncChain

async def fetch_number() -> int:
    await asyncio.sleep(0.1)
    return 21

def double(value: int) -> int:
    return value * 2

async def main() -> None:
    result = await (
        AsyncChain()
        .then(fetch_number)
        .then(double)
        .add_delay(0.1)
        .on_complete(lambda value: f"result={value}")
        .run()
    )
    print(result)

asyncio.run(main())
```

### Local persistent task queue

```python
import asyncio
import time
from fluent_control import TaskManager

manager = TaskManager.instance("demo")

@manager.task
def heavy_square(value: int) -> int:
    time.sleep(1)
    return value * value

async def main() -> None:
    heavy_square(3)
    heavy_square(4)
    await manager.start_tasks(once=True)

    for task in manager.tasks:
        print(task.status, task.result)

asyncio.run(main())
```

## Installation

From PyPI, once published:

```bash
pip install fluent-control
```

From a local checkout:

```bash
git clone https://github.com/YOUR_USERNAME/fluent-control.git
cd fluent-control
pip install -e .
```

For development:

```bash
pip install -e .[dev]
pytest
```

## API overview

### Safe getters

```python
from fluent-control import try_get, try_gete, try_geta, try_get_attrs, apply_to_list
```

| Function | Purpose |
|---|---|
| `try_get(func, default=None)` | Return function result or fallback value. |
| `try_gete(func, default=None)` | Return `(value, exception)` tuple. |
| `try_geta(items, func)` | Safely map a function over a collection. |
| `try_get_attrs(obj_func, attrs, defaults)` | Safely read several attributes. |
| `apply_to_list(items, func, filter_func=None)` | Filter and map a collection with safe per-item execution. |

### Result values

```python
from fluent-control import Ok, Err, capture, result
```

`capture()` executes a callable and returns:

- `Ok(value)` on success;
- `Err(exception)` on failure.

Both result types support:

- `unwrap()`;
- `unwrap_or(default)`;
- `unwrap_or_else(func)`;
- `map(func)`;
- `bind(func)`.

### AsyncChain

```python
from fluent-control import AsyncChain
```

Useful when a workflow has several steps and some of them are async while others are ordinary sync functions.

Main methods:

- `.then(func)` / `.add(func)`;
- `.add_delay(seconds)`;
- `.add_condition_wait(condition, timeout=None, interval=0.1)`;
- `.on_complete(func)`;
- `.on_error(func)`;
- `.run(initial=None)`.

### TaskManager

```python
from fluent-control import TaskManager, BaseTask
```

A tiny local task queue based on SQLite, Peewee, and cloudpickle.

It is suitable for small local automation jobs, prototypes, bots, and scripts. It is not meant to replace distributed job systems such as Celery or Airflow.

## Project structure

```text
fluent_control/
  __init__.py
  async_chain.py
  AsyncChain.py              # backward-compatible import path
  ifer.py
  result.py
  safe_getter.py
  safe_getter_rust.py        # backward-compatible import path
  task_manager_db.py
  tryer.py
examples/
  basic_usage.py
  async_chain_usage.py
  task_manager_usage.py
tests/
  test_core.py
pyproject.toml
README.md
```

## Backward compatibility

The project keeps compatibility shims for older import paths:

```python
from fluent_control.AsyncChain import AsyncChain
from fluent_control.safe_getter_rust import Ok, Err, result
```

New code should prefer:

```python
from fluent_control import AsyncChain, Ok, Err, capture
```

## When not to use this library

Use a larger framework if you need distributed workers, scheduled DAGs, retries with complex policies, observability dashboards, transactional queues, or horizontal scaling. `fluent-control` is intentionally small and local-first.

## License

MIT
