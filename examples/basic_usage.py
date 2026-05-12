from fluentity import AsyncChain, ConditionalExecutor, Ok, Err, capture, try_get


value = try_get(lambda: {"user": {"name": "Ada"}}["user"]["name"], default="unknown")
print(value)

match capture(lambda: 10 / 2):
    case Ok(number):
        print(f"success: {number}")
    case Err(error):
        print(f"failed: {error}")


result = (
    ConditionalExecutor()
    .if_(lambda: value == "Ada")
    .then(lambda: "known user")
    .else_(lambda: "anonymous")
    .execute()
)
print(result)
