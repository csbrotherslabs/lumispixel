"""Allowlisted platform handlers. Only transactional database effects are supported."""
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Definition:
    handler: Callable
    max_attempts: int = 5


_registry = {}


def register(kind, handler, *, max_attempts=5):
    if not kind or len(kind) > 100 or kind in _registry or not 1 <= max_attempts <= 20:
        raise ValueError("Invalid or duplicate automation definition")
    _registry[kind] = Definition(handler, max_attempts)


def definition(kind):
    return _registry[kind]
