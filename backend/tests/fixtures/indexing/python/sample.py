"""Sample module."""

from collections import Counter


CONSTANT = 42


def greet(name: str) -> str:
    """Return a friendly greeting."""
    return f"Hello, {name}"


class Greeter:
    def __init__(self, prefix: str) -> None:
        self.prefix = prefix

    def render(self, name: str) -> str:
        return f"{self.prefix} {greet(name)}"
