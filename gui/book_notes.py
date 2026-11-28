"""
gui/book_notes.py

What the window needs to know about book notes (core/booknotes/flow.py is the engine): the kinds Look Up can be told to
make and the engine as the window's lookup thread makes it. No key is needed (Open Library and Wikipedia are open; the
ISFDB database is a local file). The review controls are the plain ones of redactor_common's ProposalPanel.

  KIND_CHECKS                     (kind, Look Up menu label)
  make_engine(fetchers, cache)    the engine of one library
  book_hooks()                    the review controls' hooks (none: the plain page)
"""

from __future__ import annotations

from core import notes_settings
from core.booknotes.flow import KIND_AUTHOR, KIND_GENRE, KIND_SERIES, Fetchers, NotesEngine
from redactor_common.gui.notes_review_dialog import ReviewHooks

KIND_CHECKS = (
    (KIND_AUTHOR, "A&uthors (author.md in an author folder)"),
    (KIND_SERIES, "Book Ser&ies (series.md in a series folder)"),
    (KIND_GENRE, "B&ook Genres (about.md in a genre folder)"),
)


def make_engine(fetchers: Fetchers, cache=None) -> NotesEngine:
    fetchers.wikipedia = fetchers.wikipedia and notes_settings.wikipedia_enabled()
    return NotesEngine(fetchers, cache=cache)


def book_hooks() -> ReviewHooks:
    return ReviewHooks()
