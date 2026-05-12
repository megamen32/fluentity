import asyncio

from fluentity import attempt


async def fetch_user(user_id: int) -> dict:
    await asyncio.sleep(0.01)
    return {"id": user_id, "active": True}


async def fetch_orders(user: dict) -> list[str]:
    await asyncio.sleep(0.01)
    return [f"order-for-{user['id']}"]


async def main() -> None:
    # Explicit .arun() is optional: Attempt is awaitable.
    result = await (
        attempt(fetch_user, 42)
        .retry(times=3, delay=0.1)
        .timeout(2)
        .ensure(lambda user: user["active"], "Inactive user")
        .then(fetch_orders)
        .recover_value([])
    )

    print(result.unwrap())


if __name__ == "__main__":
    asyncio.run(main())
