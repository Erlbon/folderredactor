"""
core/music/cache.py -- the request layer of the music notes. The cache itself (ResponseCache, CachedFetch, RequestStats)
is redactor_common's (redactor_common/core/notes_cache.py), and its file is the app's one lookup cache next to the settings,
shared with video (core/notes_settings.py); what is music's own here is the Discogs wrapper (only music asks Discogs).
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

from core import notes_settings
from redactor_common.core import notes_cache as _shared
from redactor_common.core.notes_cache import (  # noqa: F401 -- re-exported: the engine and the tests import them from here
    MAX_BYTES, NEGATIVE_TTL_SECONDS, TTL_SECONDS, CachedFetch, RequestStats, ResponseCache, looks_empty,
)

CACHE_FILE_NAME = notes_settings.CACHE_FILE_NAME

__all__ = ["CachedDiscogs", "CachedFetch", "RequestStats", "ResponseCache", "cache_path", "default_cache",
           "clear_default_cache", "looks_empty", "MAX_BYTES", "NEGATIVE_TTL_SECONDS", "TTL_SECONDS"]


def cache_path() -> Path:
    """Next to the settings file (never in a library folder): the same file as video's."""
    return notes_settings.cache_path()


def default_cache(enabled: bool = True) -> Optional[ResponseCache]:
    """The process-wide cache at cache_path(), or None when switched off."""
    return _shared.default_cache(cache_path(), enabled)


def clear_default_cache() -> int:
    """Tools > Clear Lookup Cache: the entries removed (0 when there is none)."""
    return notes_settings.clear_cache()


class CachedDiscogs:
    """The Discogs client's `get_json` with the same memo and cache. Only GET lookups: the key is the endpoint and its
    parameters, never the token (it is sent in a header by the client and is not part of the key or the stored data)."""

    def __init__(self, client, cache: Optional[ResponseCache] = None, stats: Optional[RequestStats] = None, phases=None):
        self._client = client
        self.phases = phases
        self.cache = cache
        self.stats = stats if stats is not None else RequestStats()
        self._memo: dict[str, dict] = {}
        self._lock = threading.Lock()

    def __getattr__(self, name):  # rate_limited and anything else the engine asks of the client
        return getattr(self._client, name)

    def get_json(self, path: str, **params) -> dict:
        key = "discogs|" + path + "?" + urlencode(sorted((k, str(v)) for k, v in params.items()))
        with self._lock:
            if key in self._memo:
                self.stats.from_memory += 1
                return self._memo[key]
        if self.cache is not None:
            found = self.cache.get(key)
            if found is not None and found[0] == 200:
                try:
                    data = json.loads(found[1])
                except (ValueError, UnicodeDecodeError):
                    data = None
                if isinstance(data, dict):
                    self.stats.from_cache += 1
                    with self._lock:
                        self._memo[key] = data
                    return data
        self.stats.requests += 1
        started = time.perf_counter()
        try:
            data = self._client.get_json(path, **params)
        finally:
            if self.phases is not None:
                self.phases.add("discogs", time.perf_counter() - started)
        with self._lock:
            self._memo[key] = data
        if self.cache is not None and isinstance(data, dict) and data:
            self.cache.put(key, json.dumps(data).encode("utf-8"), 200)
        return data
