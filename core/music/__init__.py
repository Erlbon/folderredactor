"""
core/music -- the folder notes of a music library (moved from mp3redactor, plan steps 6-7): artist.md in an artist folder,
album.md in an album folder, about.md in a genre or collection folder.

  tags.py         the tags and covers of MP3, FLAC, M4A, Ogg Vorbis and Opus files (mutagen; read-only)
  local.py        which folders get a note and what they hold (no network)
  numbers.py      one normaliser for comparing titles ('Seven' = '7')
  match.py        how sure a match is (discography hits, name similarity, track overlap)
  level.py        is this really an artist folder? (collaborations, composers, soundtracks, collections)
  kinds.py        'What to create': artist, album, genre
  link.py         'Look up by link': a pasted MusicBrainz / Discogs / Wikipedia / Wikidata link
  musicbrainz.py  what the notes need from MusicBrainz, on top of redactor_common's client
  discogs.py      the same from Discogs
  render.py       the note text (pure)
  evidence.py     'What is in this folder' for a row of the review page

Qt-free. The engine (mp3redactor's notes_flow) and the review page hooks follow in plan steps 8-9.
"""
