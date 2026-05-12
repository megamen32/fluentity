import asyncio
import time

from demiurgelib import TaskManager


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


if __name__ == "__main__":
    asyncio.run(main())
