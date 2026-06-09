"""Simple disk-backed cache for tool results.

Cache is stored as JSON in user's temp directory and persists across restarts.
"""

import json
import os
import hashlib
import time
from pathlib import Path
from functools import wraps
from typing import Any, Callable

_CACHE_DIR = Path(os.environ.get("TEMP", ".")) / ".travel_planner_cache"
_CACHE_FILE = _CACHE_DIR / "tool_cache.json"
_DEFAULT_TTL = 3600  # 1 hour

_cache: dict[str, dict] = {}
_loaded = False


def _load():
    global _loaded, _cache
    if _loaded:
        return
    _loaded = True
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        if _CACHE_FILE.exists():
            with open(_CACHE_FILE, "r", encoding="utf-8") as f:
                _cache = json.load(f)
    except (json.JSONDecodeError, OSError):
        _cache = {}


def _save():
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(_cache, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def _make_key(func_name: str, args: tuple, kwargs: dict) -> str:
    raw = func_name + "|" + str(args) + "|" + str(sorted(kwargs.items()))
    return hashlib.md5(raw.encode()).hexdigest()


def _clean_expired():
    now = time.time()
    expired = [k for k, v in _cache.items() if v.get("expires", 0) < now]
    for k in expired:
        del _cache[k]
    if expired:
        _save()


def cache_result(ttl: int = _DEFAULT_TTL) -> Callable:
    """Decorator: cache function return values to disk.

    Args:
        ttl: seconds before cache entry expires (default 3600).
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            _load()
            _clean_expired()

            key = _make_key(func.__name__, args, kwargs)
            if key in _cache:
                entry = _cache[key]
                return entry["value"]

            result = func(*args, **kwargs)

            _cache[key] = {
                "value": result,
                "expires": time.time() + ttl,
                "created": time.time(),
                "func": func.__name__,
            }
            _save()
            return result

        return wrapper

    return decorator


def clear_cache():
    """Clear all cached results."""
    global _cache
    _cache = {}
    try:
        if _CACHE_FILE.exists():
            _CACHE_FILE.unlink()
    except OSError:
        pass


def get_cache_stats() -> dict:
    """Return cache statistics."""
    _load()
    _clean_expired()
    now = time.time()
    return {
        "total_entries": len(_cache),
        "valid_entries": sum(1 for v in _cache.values() if v.get("expires", 0) > now),
        "expired_entries": sum(1 for v in _cache.values() if v.get("expires", 0) <= now),
        "cache_file": str(_CACHE_FILE),
        "functions": list(set(v.get("func", "?") for v in _cache.values())),
    }
