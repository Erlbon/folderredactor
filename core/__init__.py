"""
The app's core package. Importing it sets up the shared lookup clients (redactor_common.core.lookups) the way this
app uses them, so every caller -- the GUI, the command line and the tests -- gets the same User-Agent and reads the
keys from this app's own credential entries (core/api_keys.py).
"""

from redactor_common.core.lookups import discogs as _discogs
from redactor_common.core.lookups import musicbrainz as _musicbrainz
from redactor_common.core.lookups import tmdb as _tmdb

_AGENT_URL = "https://github.com/Erlbon/folderredactor"


def _tmdb_key():
    from core import api_keys  # here, not at the top: api_keys reads the settings file

    return api_keys.get_key("tmdb")


_musicbrainz.configure(f"folderredactor/1.0 ( {_AGENT_URL} )")
_discogs.configure(f"folderredactor/1.0 +{_AGENT_URL}", secret_app="folderredactor")
_tmdb.configure("TheFolderRedactor", key_source=_tmdb_key)
