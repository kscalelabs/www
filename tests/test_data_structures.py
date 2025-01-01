"""Tests some common shared data structures."""

from www.utils.caching import LRUCache


def test_lru_cache() -> None:
    cache = LRUCache[int, str](3)
    cache.put(1, "one")
    cache.put(2, "two")
    cache.put(3, "three")
    assert len(cache) == 3
    assert cache.get(1) == "one"
    cache.put(4, "four")
    assert len(cache) == 3
    assert 2 not in cache
    assert cache.get(2) is None
    assert 1 in cache
    assert cache.get(1) == "one"
    assert cache.get(3) == "three"
    assert cache.get(4) == "four"
