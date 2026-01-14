import time
import functools
from typing import Any, Callable, Dict, Tuple

class SimpleCache:
    def __init__(self):
        self._cache: Dict[Any, Tuple[Any, float, float]] = {}

    def get(self, key):
        value, timestamp, ttl = self._cache.get(key, (None, 0, 0))
        if value is not None and (time.time() - timestamp) < ttl:
            return value
        return None

    def set(self, key, value, ttl):
        self._cache[key] = (value, time.time(), ttl)

    def clear(self, key=None):
        if key is not None:
            self._cache.pop(key, None)
        else:
            self._cache.clear()

cache = SimpleCache()

def cacheable(ttl=30):
    """Decorator to cache endpoint results for a given TTL (seconds)."""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Use function name and args as cache key
            key = (func.__name__, str(args), str(kwargs))
            cached = cache.get(key)
            if cached is not None:
                return cached
            result = await func(*args, **kwargs)
            cache.set(key, result, ttl)
            return result
        return wrapper
    return decorator

def get_or_set_cache(key, fetch_func: Callable, ttl=30):
    """For custom cache logic: get from cache or set if missing/expired."""
    cached = cache.get(key)
    if cached is not None:
        return cached
    value = fetch_func()
    cache.set(key, value, ttl)
    return value 