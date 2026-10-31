"""Compute each currency check once per read request (D-189).

Every packaging stage proves its inputs are current by rebuilding them from
their own inputs, all the way back to the approved script. Each stage does that
once per item it checks, so one Final Packaging snapshot rebuilt the same
packaging brief and pairing inputs dozens of times. With the 25-pair matrix of
a Short, ``/api/status`` took minutes and the Command Center stayed on
"Loading...".

Inside :func:`scope`, a function decorated with :func:`memoized` runs once per
distinct argument list and later calls get a deep copy of its result (or the
same exception). Outside a scope it runs every time, as before. Scopes wrap
read-only work only (a GET request, one readiness check of the automatic run),
so nothing written during the scope can be hidden by a cached answer.
"""

from __future__ import annotations

import copy
import functools
import json
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, TypeVar

_CACHE: ContextVar[dict[Any, tuple[bool, Any]] | None] = ContextVar("request_memo", default=None)

F = TypeVar("F", bound=Callable[..., Any])


@contextmanager
def scope() -> Iterator[None]:
    """Cache memoized results until the scope ends; a nested scope shares the outer one."""
    if _CACHE.get() is not None:
        yield
        return
    token = _CACHE.set({})
    try:
        yield
    finally:
        _CACHE.reset(token)


def active() -> bool:
    return _CACHE.get() is not None


def _key(fn: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
    name = (fn.__module__, fn.__qualname__)
    try:
        key = (name, args, tuple(sorted(kwargs.items())))
        hash(key)
        return key
    except TypeError:
        return (name, json.dumps([args, kwargs], sort_keys=True, default=str))


def memoized(fn: F) -> F:
    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        cache = _CACHE.get()
        if cache is None:
            return fn(*args, **kwargs)
        key = _key(fn, args, kwargs)
        if key not in cache:
            try:
                cache[key] = (True, fn(*args, **kwargs))
            except Exception as exc:
                cache[key] = (False, exc)
        ok, value = cache[key]
        if not ok:
            raise value
        return copy.deepcopy(value)

    return wrapper  # type: ignore[return-value]
