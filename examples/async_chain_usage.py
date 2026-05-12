import asyncio

from demiurgelib import AsyncChain


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


if __name__ == "__main__":
    asyncio.run(main())
