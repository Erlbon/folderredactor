"""
core/api_keys.py

The Discogs token and the TMDB API key, kept in redactor_common's secret store (the OS credential store) under this
app's own name, never in the settings file. An environment variable wins over the store (DISCOGS_TOKEN,
TMDB_API_KEY), as in mp3redactor and videoredactor.

Copying the keys over from mp3redactor's and videoredactor's own entries (found by name, wherever their exes live) is
offered on first start in a later step (plan D5); nothing here reads another app's entries.

The service/entry names below are permanent: renaming one orphans every user's stored key.
"""

from __future__ import annotations

from typing import Callable, Optional

from redactor_common.core import secret_store

from core.settings import get_setting, set_setting

APP = "folderredactor"

# key id -> (secret name, env var, label)
KEYS = {
    "discogs": ("discogs_token", "DISCOGS_TOKEN", "Discogs Token"),
    "tmdb": ("tmdb_api_key", "TMDB_API_KEY", "TMDB API Key"),
}

# The one non-secret setting here: did the user agree to the UNENCRYPTED fallback file on a machine with no
# credential store?
_FALLBACK_SECTION = "secrets"
_FALLBACK_KEY = "allow_unencrypted_fallback"


def get_key(key_id: str) -> Optional[str]:
    name, env_var, _label = KEYS[key_id]
    return secret_store.get_secret(APP, name, env_var=env_var).strip() or None


def apply_fallback_preference() -> Callable[[], None]:
    """Re-apply the remembered consent and return the `remember` callable for save_with_fallback_prompt(): it
    persists a yes (never a silent no)."""
    return secret_store.bind_fallback_preference(
        lambda: get_setting(_FALLBACK_SECTION, _FALLBACK_KEY, "") == "1",
        lambda on: set_setting(_FALLBACK_SECTION, _FALLBACK_KEY, "1") if on else None,
    )
