import time
from threading import RLock

class TTLCache:
    """Thread‑safe in‑memory cache with per‑key TTL.
    Keys are tuples (latitude, longitude). Values are the full JSON payload.
    """
    def __init__(self, default_ttl_seconds: int = 600):
        self.ttl = default_ttl_seconds
        self.store = {}
        self.lock = RLock()

    def _now(self) -> float:
        return time.time()

    def get(self, key):
        with self.lock:
            entry = self.store.get(key)
            if not entry:
                return None
            value, expires_at = entry
            if expires_at < self._now():
                # expired – drop it
                del self.store[key]
                return None
            return value

    def set(self, key, value, ttl: int = None):
        with self.lock:
            expiry = self._now() + (ttl if ttl is not None else self.ttl)
            self.store[key] = (value, expiry)

    def clear(self):
        with self.lock:
            self.store.clear()
