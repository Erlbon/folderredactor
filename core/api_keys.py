"""
core/api_keys.py

The Discogs token and the TMDB API key: the Redactor family's SHARED keys (redactor_common's secret store, decided
2026-11-06, plan D25): one entry per service for every Redactor (`<name>@redactor/shared` in the OS credential store),
never in the settings file. Read: an environment variable (DISCOGS_TOKEN, TMDB_API_KEY) > the shared entry > this app's
own old entry. Saved (Tools > API Keys): to the shared entry, so mp3redactor / videoredactor see it too once they read
the shared keys. A key that is still only in an app's own entry is offered for sharing (core/old_apps.py).

The entry names below are permanent: renaming one orphans every user's stored key.
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
    return secret_store.get_key(name, APP, env_var=env_var).strip() or None


def apply_fallback_preference() -> Callable[[], None]:
    """Re-apply the remembered consent and return the `remember` callable for save_with_fallback_prompt(): it
    persists a yes (never a silent no)."""
    return secret_store.bind_fallback_preference(
        lambda: get_setting(_FALLBACK_SECTION, _FALLBACK_KEY, "") == "1",
        lambda on: set_setting(_FALLBACK_SECTION, _FALLBACK_KEY, "1") if on else None,
    )
