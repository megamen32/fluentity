import asyncio

import pytest

from fluentity import Err, Ok, attempt, policy, safe


def test_attempt_success_chain():
    result = (
        attempt(int, "21")
        .then(lambda value: value * 2)
        .ensure(lambda value: value == 42, "not forty-two")
        .run()
    )

    assert result.is_ok
    assert result.unwrap() == 42


def test_attempt_captures_error_and_recovers():
    result = attempt(int, "bad").recover(lambda error: 0).run()

    assert result.is_ok
    assert result.unwrap() == 0


def test_retry_repeats_initial_call():
    state = {"calls": 0}

    def unstable():
        state["calls"] += 1
        if state["calls"] < 3:
            raise RuntimeError("not yet")
        return "ok"

    result = attempt(unstable).retry(times=3).run()

    assert result.unwrap() == "ok"
    assert state["calls"] == 3


def test_ensure_turns_bad_value_into_error():
    result = attempt(lambda: {"active": False}).ensure(lambda user: user["active"], "inactive").run()

    assert result.is_err
    with pytest.raises(ValueError, match="inactive"):
        result.unwrap()


def test_policy_reuses_reliability_settings():
    safe_network = policy().retry(times=2).recover(lambda error: "fallback")

    assert safe_network.run(lambda: "ok").unwrap() == "ok"
    assert safe_network.run(lambda: (_ for _ in ()).throw(RuntimeError("boom"))).unwrap() == "fallback"


def test_safe_decorator():
    @safe
    def parse(text: str) -> int:
        return int(text)

    assert parse("10").unwrap() == 10
    assert parse("bad").unwrap_or(0) == 0


def test_result_map_bind_match():
    assert Ok("2").map(int).bind(lambda x: Ok(x + 1)).unwrap() == 3
    assert Err(ValueError("bad")).match(ok=str, err=lambda error: "err") == "err"


def test_async_attempt_chain():
    async def load_user(user_id: int):
        return {"id": user_id, "active": True}

    async def load_orders(user):
        return [user["id"]]

    async def main():
        return await (
            attempt(load_user, 42)
            .timeout(1)
            .ensure(lambda user: user["active"], "inactive")
            .then(load_orders)
            .arun()
        )

    assert asyncio.run(main()).unwrap() == [42]


def test_try_catch_keeps_try_except_else_finally_semantics():
    from fluentity import try_catch

    events = []
    result = (
        try_catch(lambda: int("10"))
        .else_(lambda value: events.append(f"else={value}"))
        .finally_(lambda: events.append("finally"))
        .run()
    )

    assert result.unwrap() == 10
    assert events == ["else=10", "finally"]


def test_try_catch_exception_handler_returns_ok_fallback():
    from fluentity import try_catch

    result = (
        try_catch(lambda: int("bad"))
        .except_(lambda error: 0, ValueError)
        .run()
    )

    assert result.unwrap() == 0


def test_recover_value_and_finally():
    events = []
    result = (
        attempt(int, "bad")
        .recover_value(7)
        .finally_(lambda: events.append("done"))
        .run()
    )

    assert result.unwrap() == 7
    assert events == ["done"]


def test_retryable_decorator():
    from fluentity import retryable

    state = {"calls": 0}

    @retryable(times=2)
    def unstable():
        state["calls"] += 1
        if state["calls"] == 1:
            raise RuntimeError("boom")
        return "ok"

    assert unstable().unwrap() == "ok"
    assert state["calls"] == 2


def test_get_path_reads_dict_list_and_default():
    from fluentity import get_path

    payload = {"user": {"profiles": [{"name": "Nikita"}]}}

    assert get_path(payload, "user.profiles.0.name") == "Nikita"
    assert get_path(payload, "user.profile.name", default="anonymous") == "anonymous"


def test_choose_returns_first_matching_branch():
    from fluentity import choose

    status = "premium"
    result = (
        choose()
        .when(lambda: status == "admin", lambda: "admin")
        .when(lambda: status == "premium", lambda: "premium")
        .otherwise(lambda: "basic")
        .run()
    )

    assert result.unwrap() == "premium"


def test_retry_if_retries_successful_bad_values():
    state = {"calls": 0}

    def fetch_status():
        state["calls"] += 1
        return "pending" if state["calls"] < 3 else "ready"

    result = attempt(fetch_status).retry_if(lambda value: value == "pending", times=3).run()

    assert result.unwrap() == "ready"
    assert state["calls"] == 3


def test_ensure_not_none():
    result = attempt(lambda: None).ensure_not_none("missing").run()

    assert result.is_err
    with pytest.raises(ValueError, match="missing"):
        result.unwrap()


def test_recover_by_exception_type():
    value_error_result = attempt(lambda: int("bad")).recover_value(0, exceptions=(ValueError,)).run()
    type_error_result = attempt(lambda: (_ for _ in ()).throw(TypeError("bad"))).recover_value(0, exceptions=(ValueError,)).run()

    assert value_error_result.unwrap() == 0
    assert type_error_result.is_err


def test_await_attempt_without_arun():
    async def load_number():
        return 21

    async def main():
        return await attempt(load_number).then(lambda value: value * 2)

    assert asyncio.run(main()).unwrap() == 42


def test_async_chain_helper():
    from fluentity import chain

    async def main():
        events = []
        return await (
            chain()
            .then(lambda value: value + 1)
            .delay(0)
            .then(lambda value: value * 2)
            .on_complete(lambda value: events.append(value))
            .run(2, timeout=1)
        ), events

    result, events = asyncio.run(main())

    assert result.unwrap() == 6
    assert events == [6]
