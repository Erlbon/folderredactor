"""
core/comicnotes

Notes > Look Up for a COMICS library (plan step 18; Erlend's D32, D34-D36, 2026-11-21; D33 changed the same day to "the
comics' own ComicInfo.xml and the folder names only": no Comic Vine, no Bedetheque). series.md and a grouping's about.md.
Which folders get a note is core/comics.py (Scan for Notes); this package writes nothing itself (core/notes_engine.py
does, after a yes).

  local.py         names and years from folder names, the comics lying in a folder (their own ComicInfo.xml first)
  render.py        the note texts
  flow.py          the engine (NotesEngine), the shape every media type follows
  settings.py      [notes.comics] in the settings file
"""
