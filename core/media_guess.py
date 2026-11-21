"""
core/media_guess.py

Is a library folder music, video, books or comics? Notes > Look Up asks the right questions only once it knows (music:
artist / album / genre notes; video: series / film notes), and Notes > Scan for Notes judges the levels by it (books and
comics too, 2026-11-21; Look Up for those is not built yet). A quick, bounded look at the file names (no file is opened):
the first MAX_FILES files found in a breadth-first walk, at most MAX_DEPTH folders down, counted by extension. The kind with
clearly more files wins; a mix too close to call, or nothing at all, is '' (the window then asks).

  guess_kind(folder)    'music', 'video', 'books', 'comics' or ''
  guess_media(folder)   'music', 'video' or '' (what the command line and the library's first guess use)
"""

from __future__ import annotations

import os
from collections import deque
from pathlib import Path

from core.books import BOOK_EXTENSIONS
from core.comics import COMIC_EXTENSIONS
from core.music.tags import AUDIO_EXTENSIONS
from core.video.local import VIDEO_EXTENSIONS
from redactor_common.core.long_paths import literal

MUSIC, VIDEO, BOOKS, COMICS = "music", "video", "books", "comics"
EXTENSIONS = {MUSIC: AUDIO_EXTENSIONS, VIDEO: VIDEO_EXTENSIONS, BOOKS: BOOK_EXTENSIONS, COMICS: COMIC_EXTENSIONS}
MAX_FILES = 2000
MAX_DEPTH = 5
CLEAR_MAJORITY = 2.0  # one kind must have at least this many times the files of the next


def count_kinds(folder: str | os.PathLike, max_files: int = MAX_FILES, max_depth: int = MAX_DEPTH) -> dict[str, int]:
    """Files of each kind among the first `max_files` files under `folder`. Unreadable folders are passed over; hidden
    folders and symbolic links are not followed."""
    counts = dict.fromkeys(EXTENSIONS, 0)
    seen = 0
    queue: deque[tuple[Path, int]] = deque([(Path(folder), 0)])
    while queue and seen < max_files:
        current, depth = queue.popleft()
        try:
            with os.scandir(literal(current)) as entries:  # also 'R.E.M.' (redactor_common core/long_paths.py)
                for entry in entries:
                    if entry.name.startswith("."):
                        continue
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            if depth < max_depth:
                                queue.append((current / entry.name, depth + 1))
                            continue
                    except OSError:
                        continue
                    seen += 1
                    ext = os.path.splitext(entry.name)[1].lower()
                    for kind, extensions in EXTENSIONS.items():
                        if ext in extensions:
                            counts[kind] += 1
                    if seen >= max_files:
                        break
        except OSError:
            continue
    return counts


def count_media(folder: str | os.PathLike, max_files: int = MAX_FILES, max_depth: int = MAX_DEPTH) -> tuple[int, int]:
    """(music files, video files) among the first `max_files` files under `folder`."""
    counts = count_kinds(folder, max_files, max_depth)
    return counts[MUSIC], counts[VIDEO]


def _winner(counts: dict[str, int]) -> str:
    ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    best, best_n = ranked[0]
    second_n = ranked[1][1] if len(ranked) > 1 else 0
    return best if best_n and best_n >= CLEAR_MAJORITY * second_n else ""


def guess_kind(folder: str | os.PathLike) -> str:
    """'music', 'video', 'books', 'comics' or '' (none, or too close to call)."""
    if not folder or not os.path.isdir(literal(folder)):
        return ""
    return _winner(count_kinds(folder))


def guess_media(folder: str | os.PathLike) -> str:
    """'music', 'video' or '' (none, or too close to call); book and comic files do not count."""
    if not folder or not os.path.isdir(literal(folder)):
        return ""
    counts = count_kinds(folder)
    return _winner({MUSIC: counts[MUSIC], VIDEO: counts[VIDEO]})
