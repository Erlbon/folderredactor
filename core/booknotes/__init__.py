"""
core/booknotes

Notes > Look Up for a BOOKS library (plan step 17; Erlend's D27-D31, 2026-11-21): author.md, series.md and a genre's
about.md, drafted from the folder, the local ISFDB database, Open Library and Wikipedia. Which folders get a note is
core/books.py (Scan for Notes); this package writes nothing itself (core/notes_engine.py does, after a yes).

  local.py         names from folder names, the books lying in a folder (their own OPF first)
  isfdb.py         the local ISFDB database (built by epubredactor), read-only: an author's books and a series' order
  openlibrary.py   Open Library: the author, the author's books, the Wikidata id
  render.py        the note texts
  flow.py          the engine (NotesEngine), the shape every media type follows
  settings.py      [notes.books] in the settings file
"""
