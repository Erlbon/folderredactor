"""
gui/video_notes.py

What the window needs to know about video notes (core/video/flow.py is the engine): the kinds Look Up can be told to make,
the TMDB key check, and the engine as the window's lookup thread makes it. The review controls are the plain ones of
redactor_common's ProposalPanel (no extras); the window is gui/main_window.py.

  KIND_CHECKS                     (kind, Look Up menu label)
  has_tmdb_key(fetchers)          False: say TMDB_KEY_MESSAGE and look nothing up
  make_engine(fetchers, cache)    the engine of one library
  video_hooks()                   the review controls' hooks (none: the plain page)
"""

from __future__ import annotations

from core import notes_settings
from core.video.flow import Fetchers, NotesEngine
from core.video.local import KIND_MOVIE, KIND_SERIES
from redactor_common.core.lookups.tmdb import get_api_key
from redactor_common.gui.notes_review_dialog import ReviewHooks

KIND_CHECKS = (
    (KIND_SERIES, "&Series (series.md in a series folder)"),
    (KIND_MOVIE, "&Films (about.md in a film folder)"),
)
TMDB_KEY_MESSAGE = ("Look Up asks TMDB about films and series, which needs your own (free) API key.\n\n"
                    "Add it under Tools > API Keys, then try again.")


def has_tmdb_key(fetchers: Fetchers) -> bool:
    return fetchers.key is not None or bool(get_api_key())


def make_engine(fetchers: Fetchers, cache=None) -> NotesEngine:
    fetchers.wikipedia = fetchers.wikipedia and notes_settings.wikipedia_enabled()
    return NotesEngine(fetchers, cache=cache)


def video_hooks() -> ReviewHooks:
    return ReviewHooks()
