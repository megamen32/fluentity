from fluentity import attempt, policy


def load_user(user_id: int) -> dict:
    return {"id": user_id, "active": True}


def load_orders(user: dict) -> list[str]:
    return ["order-1", "order-2"]


orders = (
    attempt(load_user, 42)
    .retry(times=3, delay=0.1)
    .ensure(lambda user: user["active"], "User is inactive")
    .then(load_orders)
    .recover(lambda error: [])
    .run()
    .unwrap()
)

print(orders)

network = policy().retry(times=3, delay=0.1).recover(lambda error: None)
print(network.run(load_user, 7).unwrap())
