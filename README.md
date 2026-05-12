# Fluentity

[![Tests](https://github.com/megamen32/fluentity/actions/workflows/tests.yml/badge.svg)](https://github.com/megamen32/fluentity/actions/workflows/tests.yml)
[![PyPI](https://img.shields.io/pypi/v/fluentity.svg)](https://pypi.org/project/fluentity/)
[![Python](https://img.shields.io/pypi/pyversions/fluentity.svg)](https://pypi.org/project/fluentity/)
[![License](https://img.shields.io/github/license/megamen32/fluentity.svg)](LICENSE)

**Fluent reliability primitives for Python functions.**

Fluentity is a small dependency-free Python library for safe execution chains:
retries, timeouts, fallbacks, validation, explicit `Result` values, and async workflows.

```python
from fluentity import attempt

result = await (
    attempt(fetch_user, user_id)
    .retry(times=3, delay=1)
    .timeout(10)
    .ensure(lambda user: user.is_active, "Inactive user")
    .then(fetch_orders)
    .recover_value([])
)

orders = result.unwrap()
```
It is not another fluent collection wrapper. Libraries such as [flupy](https://github.com/olirice/flupy) and [pyfluent-iterables](https://github.com/feynmanix/pyfluent-iterables) are great when your main problem is transforming iterables with .map(), .filter(), .chunk(), .to_list(), and similar operations.

For async code, you can skip the explicit `.arun()` and await the configured attempt directly:

```python
result = await (
    attempt(fetch_user, user_id)
    .retry(times=3, delay=1)
    .timeout(10)
    .ensure(lambda user: user.is_active, "Inactive user")
    .then(fetch_orders)
    .recover_value([])
)
```

## Why Fluentity?

Use Fluentity when an operation can fail, return invalid data, need a retry, require a fallback, or be composed with more steps.

Good fit:

- HTTP/API calls;
- Telegram bots and background handlers;
- parsers and scraping scripts;
- local automation scripts;
- ETL steps;
- LLM calls;
- code where you want explicit `Ok(...)` / `Err(...)` instead of uncontrolled exceptions.

Not the main goal:

- replacing list comprehensions;
- replacing `itertools`;
- becoming a DataFrame library;
- cloning fluent iterable libraries.

## Installation

```bash
pip install fluentity
```

For the optional SQLite task manager:

```bash
pip install "fluentity[tasks]"
```

For development:

```bash
git clone https://github.com/megamen32/fluentity.git
cd fluentity
pip install -e .[dev]
pytest
```

Build and check the package locally before publishing:

```bash
python -m build
python -m twine check dist/*
```

## Core API

```python
from fluentity import (
    attempt,
    policy,
    try_catch,
    chain,
    choose,
    get_path,
    safe,
    retryable,
    timeoutable,
    Ok,
    Err,
    Result,
)
```

`attempt(...)` builds one reliable operation.

`policy(...)` builds reusable reliability settings.

`try_catch(...)` gives you a fluent explicit `try/except/else/finally` block.

`chain()` builds a readable async-first pipeline with steps, delays, waits, and hooks.

`choose()` builds a compact conditional branch tree.

`get_path(...)` safely reads nested dictionaries, lists, and objects.

`Result` makes success and failure explicit.

## Safe function execution

```python
from fluentity import attempt

result = attempt(int, "123").run()

assert result.unwrap() == 123
```

If the function raises, the program does not crash:

```python
result = attempt(int, "abc").run()

assert result.is_err
assert result.unwrap_or(0) == 0
```

## Retry

```python
result = (
    attempt(fetch_json, "https://example.com/api/user")
    .retry(times=3, delay=1, backoff=2)
    .run()
)
```

Retries apply to the initial unsafe call. Later steps are only executed if the call succeeds.

## Retry by result with `retry_if`

Sometimes the function succeeds technically, but returns a temporary bad value such as `"pending"`, `None`, or an incomplete response.

```python
result = (
    attempt(fetch_status)
    .retry_if(lambda status: status == "pending", times=5, delay=1)
    .run()
)
```

If every attempt still matches the predicate, the result becomes `Err(RetryConditionError(...))`.

## Validation with `ensure` and `ensure_not_none`

```python
result = (
    attempt(load_user, user_id)
    .ensure(lambda user: user.is_active, "User is inactive")
    .ensure(lambda user: user.email, "User has no email")
    .run()
)
```

`ensure` is not collection filtering. It is a contract check for a successful value.

For the common `None` case:

```python
result = (
    attempt(find_user, user_id)
    .ensure_not_none("User not found")
    .then(send_message)
    .run()
)
```

## Step composition with `then`

```python
result = (
    attempt(load_user, user_id)
    .then(load_orders)
    .then(build_report)
    .run()
)
```

If any step raises, the chain stops and returns `Err(exception)`.

## Side effects with `tap`, `tap_error`, and `finally_`

```python
result = (
    attempt(load_user, user_id)
    .tap(lambda user: logger.info(f"Loaded user {user.id}"))
    .then(load_orders)
    .tap_error(lambda error: logger.warning(f"Operation failed: {error}"))
    .finally_(lambda: logger.info("operation finished"))
    .run()
)
```

`tap` observes successful values without changing them.

`tap_error` observes final errors.

`finally_` always runs after success, error, or recovery.

## Fallbacks with `recover` and `recover_value`

```python
config = (
    attempt(load_config, "config.json")
    .recover(lambda error: {"debug": False})
    .run()
    .unwrap()
)
```

For a fixed fallback value, use `recover_value`:

```python
config = (
    attempt(load_config, "config.json")
    .recover_value({"debug": False})
    .run()
    .unwrap()
)
```

You can limit fallback handling to selected exception types:

```python
number = (
    attempt(int, user_input)
    .recover_value(0, exceptions=(ValueError,))
    .run()
    .unwrap()
)
```

## Async support

Use `.arun()` when you prefer explicit async execution:

```python
result = await (
    attempt(fetch_user, user_id)
    .retry(times=3, delay=1)
    .timeout(10)
    .then(fetch_orders)
    .arun()
)
```

Or await the configured attempt directly:

```python
result = await (
    attempt(fetch_user, user_id)
    .retry(times=3, delay=1)
    .timeout(10)
    .then(fetch_orders)
)
```

You can also pass timeout to execution instead of configuring it fluently:

```python
result = await attempt(fetch_user, user_id).then(fetch_orders).arun(timeout=10)
```

`timeout(...)` and `arun(timeout=...)` are designed for async execution. Synchronous `run(timeout=...)` is accepted for API symmetry, but returns an error because arbitrary synchronous Python code cannot be safely cancelled without threads or processes.

## Reusable policies

```python
from fluentity import policy

network = (
    policy()
    .retry(times=3, delay=1, backoff=2)
    .timeout(10)
    .tap_error(lambda error: logger.warning(f"Network failed: {error}"))
    .recover_value(None)
)

user = await network.arun(fetch_user, user_id)
orders = await network.arun(fetch_orders, user_id)
```

Policies are useful when many calls should share the same retry, timeout, logging, and fallback behavior.

## Explicit `try/except/else/finally`

`try_catch` keeps the useful idea of a fluent try block, but returns `Result` instead of hiding errors.

```python
from fluentity import try_catch

result = (
    try_catch(lambda: int(user_input))
    .except_(lambda error: 0, ValueError)
    .else_(lambda value: logger.info(f"parsed={value}"))
    .finally_(lambda: logger.info("parse attempt finished"))
    .run()
)

number = result.unwrap()
```

Use `attempt(...)` for retry/timeout/validation/recovery policies. Use `try_catch(...)` when you specifically want readable `try/except/else/finally` semantics.

## Async pipelines with `chain()`

`attempt(...)` is for reliable operations. `chain()` is for readable async-first pipelines where the workflow itself matters: steps, delays, waits, and completion/error hooks.

```python
from fluentity import chain

result = await (
    chain()
    .then(lambda value: value + 1)
    .delay(0.1)
    .then(load_user)
    .wait_until(lambda: cache_is_ready(), timeout=5)
    .then(build_response)
    .on_complete(lambda value: logger.info(f"done={value}"))
    .on_error(lambda error: logger.warning(f"failed={error}"))
    .run(41, timeout=10)
)
```

## Compact conditional branches with `choose()`

```python
from fluentity import choose

message = (
    choose()
    .when(lambda: status == "admin", lambda: "Full access")
    .when(lambda: status == "premium", lambda: "Premium access")
    .otherwise(lambda: "Basic access")
    .run()
    .unwrap()
)
```

Async predicates and actions are supported through `await choose(...).arun()` or simply `await choose(...)`.

## Safe nested access with `get_path`

```python
from fluentity import get_path

username = get_path(payload, "user.profile.username", default="anonymous")
first_title = get_path(payload, ["items", 0, "title"], default="untitled")
```

`get_path` works with dictionaries, lists/tuples, and ordinary object attributes.

## Classic safe getters

The older compact helpers are still available because they are useful in small scripts:

```python
from fluentity import try_get, try_gete, try_geta, try_get_attrs, apply_to_list

username = try_get(lambda: payload["user"]["profile"]["username"], default="anonymous")
value, error = try_gete(lambda: int(user_input), default=0)
```

## Decorators

```python
from fluentity import safe, retryable, timeoutable

@safe
def parse_int(text: str) -> int:
    return int(text)

@retryable(times=3, delay=1)
def load_config() -> dict:
    return read_config_from_disk()

@timeoutable(10)
async def fetch_json(url: str) -> dict:
    return await client.get_json(url)
```

Decorated functions return `Result`.

## Optional local task manager

The task manager is intentionally optional because most users should not install database-related dependencies unless they need them.

```bash
pip install "fluentity[tasks]"
```

```python
from fluentity import TaskManager

manager = TaskManager.instance("demo")

@manager.task
def heavy_square(value: int) -> int:
    return value * value
```

This is useful for local bots, prototypes, and automation scripts. It is not a replacement for Celery, RQ, Airflow, or distributed workers.

## Project structure

```text
fluentity/
  __init__.py
  attempt.py
  chain.py
  choose.py
  path.py
  policy.py
  result.py
  safe_getter.py
  task_manager_db.py
  try_catch.py
examples/
  async_reliability_usage.py
  reliability_usage.py
  task_manager_usage.py
tests/
  test_core.py
pyproject.toml
README.md
```

## Continuous integration

The repository includes a GitHub Actions workflow at `.github/workflows/tests.yml`. It runs the test suite on Python 3.10, 3.11, 3.12, and 3.13 for pushes and pull requests to `main` or `master`.

## Design principles

- Prefer practical reliability over fluent style for its own sake.
- Keep the core dependency-free.
- Make failures explicit with `Result`.
- Keep collection processing out of scope.
- Support async workflows without forcing verbose `.arun()` everywhere.
- Keep heavier features, such as the SQLite task manager, optional.

## When not to use this library

Use a larger framework if you need distributed workers, scheduled DAGs, complex observability, transactional queues, horizontal scaling, or durable cross-machine orchestration. Fluentity is intentionally small and local-first.

## License

MIT
