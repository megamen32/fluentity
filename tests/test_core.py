import asyncio

import pytest

from demiurgelib import AsyncChain, ConditionalExecutor, Err, Ok, TryExecutor, capture, try_get


def test_try_get_returns_default_on_exception():
    assert try_get(lambda: 1 / 0, default=42) == 42


def test_capture_returns_ok_and_err():
    assert capture(lambda: 2 + 2) == Ok(4)
    assert isinstance(capture(lambda: 1 / 0), Err)


def test_conditional_executor_returns_matching_action():
    result = (
        ConditionalExecutor()
        .if_(lambda: False)
        .then(lambda: "first")
        .elif_(lambda: True)
        .then(lambda: "second")
        .else_(lambda: "else")
        .execute()
    )
    assert result == "second"


def test_try_executor_else_gets_result():
    observed = []
    result = TryExecutor(lambda: 5).else_(lambda value: observed.append(value)).execute()
    assert result == 5
    assert observed == [5]


def test_async_chain_mixes_sync_and_async_steps():
    async def main():
        async def one():
            return 1

        return await AsyncChain().then(one).then(lambda x: x + 1).run()

    assert asyncio.run(main()) == 2
