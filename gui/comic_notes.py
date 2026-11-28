"""
gui/comic_notes.py

What the window needs to know about comics notes (core/comicnotes/flow.py is the engine): the kinds Look Up can be told to
make and the engine as the window's lookup thread makes it. No key is needed (the comics' own ComicInfo.xml and Wikipedia;
no Comic Vine, no Bedetheque: Erlend, 2026-11-21). The review controls are the plain ones of redactor_common's
ProposalPanel.

  KIND_CHECKS                     (kind, Look Up menu label)
  make_engine(fetchers, cache)    the engine of one library
  comic_hooks()                   the review controls' hooks (none: the plain page)
"""

from __future__ import annotations

from core import notes_settings
from core.comicnotes.flow import KIND_GROUPING, KIND_SERIES, Fetchers, NotesEngine
from redactor_common.gui.notes_review_dialog import ReviewHooks

KIND_CHECKS = (
    (KIND_SERIES, "&Comic Series (series.md in a series folder)"),
    (KIND_GROUPING, "Comic &Publishers and Groupings (about.md)"),
)


def make_engine(fetchers: Fetchers, cache=None) -> NotesEngine:
    fetchers.wikipedia = fetchers.wikipedia and notes_settings.wikipedia_enabled()
    return NotesEngine(fetchers, cache=cache)


def comic_hooks() -> ReviewHooks:
    return ReviewHooks()
