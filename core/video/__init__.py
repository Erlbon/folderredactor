"""
core/video -- the folder notes of a video library (moved from videoredactor, plan step 5): series.md in a series
folder, about.md in a film folder, drafted from what the folder holds and what TMDB and Wikipedia say.

  local.py      which folders get a note and what they hold (no network)
  tmdb.py       the TMDB reads the notes need
  render.py     the note text (pure)
  flow.py       the engine: proposals, rebuild after a pick, write, undo
  settings.py   what video notes remember ([notes.video] in the settings file)

Qt-free. The review page is redactor_common's; gui/video_notes.py is video's hook on it.
"""
