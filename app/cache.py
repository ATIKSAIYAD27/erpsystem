import time
import threading
import logging
from functools import wraps

logger = logging.getLogger(__name__)


class TTLCache:
    """Thread-safe in-memory cache with TTL (Time-To-Live) support."""

    def __init__(self, default_ttl=300, max_size=1000):
        self._store = {}
        self._timestamps = {}
        self._default_ttl = default_ttl
        self._max_size = max_size
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0

    def get(self, key):
        with self._lock:
            if key in self._store:
                if time.time() - self._timestamps[key] < self._default_ttl:
                    self._hits += 1
                    return self._store[key]
                else:
                    del self._store[key]
                    del self._timestamps[key]
            self._misses += 1
            return None

    def set(self, key, value, ttl=None):
        with self._lock:
            if len(self._store) >= self._max_size and key not in self._store:
                self._evict_oldest()
            self._store[key] = value
            self._timestamps[key] = time.time()

    def delete(self, key):
        with self._lock:
            self._store.pop(key, None)
            self._timestamps.pop(key, None)

    def clear(self, prefix=None):
        with self._lock:
            if prefix:
                keys_to_delete = [k for k in self._store if k.startswith(prefix)]
                for k in keys_to_delete:
                    del self._store[k]
                    del self._timestamps[k]
            else:
                self._store.clear()
                self._timestamps.clear()

    def _evict_oldest(self):
        if not self._store:
            return
        oldest_key = min(self._timestamps, key=self._timestamps.get)
        del self._store[oldest_key]
        del self._timestamps[oldest_key]

    def stats(self):
        with self._lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total * 100) if total > 0 else 0
            return {
                'size': len(self._store),
                'hits': self._hits,
                'misses': self._misses,
                'hit_rate': f"{hit_rate:.1f}%"
            }


cache = TTLCache(default_ttl=300, max_size=2000)


def cached(key_prefix, ttl=300):
    """Decorator to cache function results."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            cache_key = f"{key_prefix}:{str(args)}:{str(sorted(kwargs.items()))}"
            result = cache.get(cache_key)
            if result is not None:
                return result
            result = f(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            return result
        return wrapper
    return decorator


def invalidate_cache(prefix):
    """Invalidate all cache entries with a given prefix."""
    cache.clear(prefix)
