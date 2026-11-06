"""
core/media_guess.py

Is a library folder music or video? Notes > Create Notes asks the right questions only once it knows (music: artist /
album / genre notes; video: series / film notes). A quick, bounded look at the file names (no file is opened): the
first MAX_FILES files found in a breadth-first walk, at most MAX_DEPTH folders down, counted by extension. The kind with
clearly more files wins; a mix too close to call, or nothing at all, is '' (the window then asks).

A first version for plan step 9 (the music review page needs the window to reach it); plan step 10 makes it the guess
on opening a library.
"""

from __future__ import annotations

import os
from collections import deque
from pathlib import Path

from core.music.tags import AUDIO_EXTENSIONS
from core.video.local import VIDEO_EXTENSIONS

MUSIC, VIDEO = "music", "video"
MAX_FILES = 2000
MAX_DEPTH = 5
CLEAR_MAJORITY = 2.0  # one kind must have at least this many times the files of the other


def count_media(folder: str | os.PathLike, max_files: int = MAX_FILES, max_depth: int = MAX_DEPTH) -> tuple[int, int]:
    """(music files, video files) among the first `max_files` files under `folder`. Unreadable folders are passed over;
    hidden folders and symbolic links are not followed."""
    music = video = seen = 0
    queue: deque[tuple[Path, int]] = deque([(Path(folder), 0)])
    while queue and seen < max_files:
        current, depth = queue.popleft()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    if entry.name.startswith("."):
                        continue
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            if depth < max_depth:
                                queue.append((Path(entry.path), depth + 1))
                            continue
                    except OSError:
                        continue
                    seen += 1
                    ext = os.path.splitext(entry.name)[1].lower()
                    music += ext in AUDIO_EXTENSIONS
                    video += ext in VIDEO_EXTENSIONS
                    if seen >= max_files:
                        break
        except OSError:
            continue
    return music, video


def guess_media(folder: str | os.PathLike) -> str:
    """'music', 'video' or '' (none, or too close to call)."""
    if not folder or not os.path.isdir(folder):
        return ""
    music, video = count_media(folder)
    if music and music >= CLEAR_MAJORITY * video:
        return MUSIC
    if video and video >= CLEAR_MAJORITY * music:
        return VIDEO
    return ""
