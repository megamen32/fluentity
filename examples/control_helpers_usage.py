import asyncio

from fluentity import attempt, chain, choose, get_path


async def main() -> None:
    payload = {"user": {"profile": {"name": "Nikita"}}, "status": "premium"}

    name = get_path(payload, "user.profile.name", default="anonymous")

    access = (
        choose()
        .when(lambda: payload["status"] == "admin", lambda: "full")
        .when(lambda: payload["status"] == "premium", lambda: "premium")
        .otherwise(lambda: "basic")
        .run()
        .unwrap()
    )

    result = await (
        chain()
        .then(lambda _: name)
        .then(lambda value: value.upper())
        .delay(0.01)
        .then(lambda value: {"name": value, "access": access})
        .run(timeout=1)
    )

    print(result.unwrap())

    status = {"calls": 0}

    def fetch_status() -> str:
        status["calls"] += 1
        return "pending" if status["calls"] < 3 else "ready"

    print(
        attempt(fetch_status)
        .retry_if(lambda value: value == "pending", times=3)
        .run()
        .unwrap()
    )


if __name__ == "__main__":
    asyncio.run(main())
