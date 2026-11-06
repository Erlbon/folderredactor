"""
core/music/scope.py

Music's words for the shared first question of Notes > Create Notes ("which folder, and what to create?",
redactor_common's NotesScopeDialog): what a folder would get, how many folders a choice covers, how long it takes, and the
review page's sentence about the kinds looked up. Moved from mp3redactor's core/notes_scope.py (its list of choices is the
shared one now: redactor_common.core.notes_scope). Pure logic, no Qt; only the folder structure is read, never a tag.

  count_targets(folder, include_subfolders) -> (artists, albums, genres) that would be looked up
  folder_info(path)                         -> (level, placeholder, existing note) of a folder you might choose
  folder_caption(info, name, kinds)         -> 'would get an artist note: Ultravox'
  scope_hint(counts, kinds)                 -> the one-line time hint of a big scope ('' when there is nothing to warn about)
  kinds_sentence(kinds)                     -> 'Looked up: artist notes only (no album lookups).'
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from core.music import timing
from core.music.kinds import parse_kinds
from core.music.local import (
    ALL_KINDS, KIND_ALBUM, KIND_ARTIST, KIND_GENRE, classify_level, existing_note, is_alphabetical_grouping,
    is_collection_name, is_generic_name, lookup_name, scan,
)


def count_targets(folder: str, include_subfolders: bool = True) -> tuple[int, int, int]:
    """(artist, album, genre) folders under `folder` that would be looked up (no note yet): what the time hint is based on.
    A quick directory walk (no tags are read); it can take a moment on a very large library."""
    found = scan([folder], include_subfolders=include_subfolders, kinds=ALL_KINDS)
    kinds = [t.kind for t in found.targets]
    return kinds.count(KIND_ARTIST), kinds.count(KIND_ALBUM), kinds.count(KIND_GENRE)


def folder_info(path: str) -> tuple[str, bool, str]:
    """(level, placeholder, existing note) of a folder you might choose: its level as the scan sees it ('genre', 'artist',
    'album' or '' for an empty or unreadable one), whether its name is a generic place or an alphabetical grouping, and the
    name of the note it already has ('' for none)."""
    folder = Path(path)
    level = classify_level(folder, True, True)
    placeholder = ((is_generic_name(folder.name.lstrip("_")) or is_alphabetical_grouping(folder.name))
                   and not is_collection_name(folder.name))
    note = existing_note(folder)
    return level, placeholder, Path(note).name if note else ""


def folder_caption(info: tuple[str, bool, str], folder_name: str, kinds) -> str:
    """What the folder would get, in a few words: 'would get a genre note: Ska'."""
    level, placeholder, existing = info
    wanted = parse_kinds(kinds)
    if level == KIND_ARTIST and is_collection_name(folder_name):
        level = KIND_GENRE  # 'Various Artists', 'Soundtracks': a collection, its note is about.md
    if placeholder and level in (KIND_ARTIST, KIND_GENRE, ""):
        return "a library root: no note of its own here; the folders below get theirs"
    if not level:
        return "nothing to write a note for here (empty, or no artist or album folders)"
    noun = {KIND_GENRE: "a genre note", KIND_ARTIST: "an artist note", KIND_ALBUM: "an album note"}[level]
    if level not in wanted:
        return f"a {level} folder ({level} notes are not ticked in What to create)"
    if existing:
        return f"already has {existing}: left alone"
    return f"would get {noun}: {lookup_name(folder_name)}"


def scope_hint(counts: Optional[tuple[int, int, int]], kinds) -> str:
    """The shared question's hint for these counts (core/music/timing.py: measured request costs)."""
    if not counts:
        return ""
    artists, albums, genres = counts
    return timing.scope_hint(artists, albums, genres, kinds)


def kinds_sentence(kinds) -> str:
    """The review page's banner sentence: which kinds of notes were looked up."""
    kinds = parse_kinds(kinds)
    if kinds == (KIND_ARTIST,):
        return "Looked up: artist notes only (no album lookups)."
    if kinds == (KIND_ALBUM,):
        return "Looked up: album notes only."
    if kinds == (KIND_GENRE,):
        return "Looked up: genre / collection notes only (no artist or album lookups, no tags read)."
    names = [{KIND_ARTIST: "artist", KIND_ALBUM: "album", KIND_GENRE: "genre / collection"}[k] for k in kinds]
    return "Looked up: " + (", ".join(names[:-1]) + " and " + names[-1]) + " notes."
