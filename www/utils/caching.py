"""Defines package-wide utility functions."""

import datetime
import functools
from collections import OrderedDict
from typing import Awaitable, Callable, Generic, Hashable, ParamSpec, TypeVar, overload

Tk = TypeVar("Tk", bound=Hashable)
Tv = TypeVar("Tv")
P = ParamSpec("P")


class LRUCache(Generic[Tk, Tv]):
    def __init__(self, capacity: int) -> None:
        super().__init__()

        self.cache: OrderedDict[Tk, Tv] = OrderedDict()
        self.capacity = capacity

    @overload
    def get(self, key: Tk) -> Tv | None: ...

    @overload
    def get(self, key: Tk, default: Tv) -> Tv: ...

    def get(self, key: Tk, default: Tv | None = None) -> Tv | None:
        if key not in self.cache:
            return None
        else:
            self.cache.move_to_end(key)
            return self.cache[key]

    def __contains__(self, key: Tk) -> bool:
        return key in self.cache

    def __len__(self) -> int:
        return len(self.cache)

    def put(self, key: Tk, value: Tv) -> None:
        self.cache[key] = value
        self.cache.move_to_end(key)
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)

    def pop(self, key: Tk) -> Tv:
        return self.cache.pop(key)

    def __getitem__(self, key: Tk) -> Tv:
        if (item := self.get(key)) is None:
            raise KeyError(key)
        return item

    def __setitem__(self, key: Tk, value: Tv) -> None:
        self.put(key, value)


def cache_result(num_seconds: float, capacity: int = 2**16) -> Callable[[Callable[P, Tv]], Callable[P, Tv]]:
    """Cache the result of a function for a certain number of seconds.

    Usage:

        ```python
        @cache_result(num_seconds=60)
        def expensive_function(arg):
            ...
        ```

    Args:
        num_seconds: The number of seconds to cache the result.
        capacity: The number of results to cache.

    Returns:
        A decorator that caches the result of the function.
    """

    def decorator(func: Callable[P, Tv]) -> Callable[P, Tv]:
        cache = LRUCache[str, tuple[datetime.datetime, Tv]](capacity)

        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> Tv:
            cur_time = datetime.datetime.now()
            key = str((args, kwargs))
            if key in cache:
                last_time, result = cache[key]
                if (cur_time - last_time).total_seconds() < num_seconds:
                    return result
            result = func(*args, **kwargs)
            cache[key] = (cur_time, result)
            return result

        return wrapper

    return decorator


def cache_async_result(
    num_seconds: float,
    capacity: int = 2**16,
) -> Callable[[Callable[P, Awaitable[Tv]]], Callable[P, Awaitable[Tv]]]:
    """Cache the result of an async function for a certain number of seconds.

    Usage:

        ```python
        @cache_async_result(num_seconds=60)
        async def expensive_function(arg):
            ...
        ```

    Args:
        num_seconds: The number of seconds to cache the result.
        capacity: The number of results to cache.

    Returns:
        A decorator that caches the result of the function.
    """

    def decorator(func: Callable[P, Awaitable[Tv]]) -> Callable[P, Awaitable[Tv]]:
        cache = LRUCache[str, tuple[datetime.datetime, Tv]](capacity)

        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> Tv:
            cur_time = datetime.datetime.now()
            key = str((args, kwargs))
            if key in cache:
                last_time, result = cache[key]
                if (cur_time - last_time).total_seconds() < num_seconds:
                    return result
            result = await func(*args, **kwargs)
            cache[key] = (cur_time, result)
            return result

        return wrapper

    return decorator
