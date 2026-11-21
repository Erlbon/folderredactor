"""
core/shelf_scan.py

What books and comics share for Notes > Scan for Notes (2026-11-21, plan steps 17 and 18 brought forward for the level rules
only): the scan result, how a folder is judged as having a note, which folder names are a place rather than a genre, and one
listing of a folder. Look Up for books and comics (Open Library, Comic Vine) is not built yet; these levels are what Scan
needs. Qt-free, no network, never opens a file: names and folder structure only.

  ShelfScan           the scan result, shaped like music's and video's (targets, skipped) so the window treats them alike
  Recorder            consider(folder, kind): a target, or skipped when the folder already has a note
  entries(folder)     (file names, sub-folders) directly in a folder
  is_place_name(name) 'Books', 'eLib', '741.59 - Comic Books': the library root gets no about.md
  is_note_free_name   letter buckets (A, B-C, 0-9) and the bare '_' attention marker: never a note
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from core.music.local import fold_name, is_alphabetical_grouping, is_generic_name, lookup_name
from redactor_common.core.notes import existing_note
from redactor_common.core.temp_names import is_app_temp_name

HAS_NOTE = "already has"  # the start of a skipped folder's reason (the window counts these as 'have a note')
PLACE_NAMES = frozenset({
    "books", "book", "ebooks", "ebook", "e books", "elib", "e lib", "library", "bibliotek", "comics", "comic", "comic books",
    "comicbooks", "tegneserier", "documents", "docs", "papers",
})
ATTENTION_MARKER = "_"  # a folder named only '_' singles a folder out for attention (Erlend, 2026-11-04): no note


@dataclass
class Target:
    folder: Path
    kind: str
    update: object = None  # no older notes of ours to refresh yet (nothing writes book or comic notes)


@dataclass
class Skipped:
    folder: Path
    kind: str
    reason: str
    state: str = ""


@dataclass
class ShelfScan:
    targets: list[Target] = field(default_factory=list)
    skipped: list[Skipped] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)


class Recorder:
    def __init__(self, kinds) -> None:
        self.wanted = set(kinds)
        self.result = ShelfScan()
        self._seen: set[str] = set()

    def consider(self, folder: Path, kind: str) -> None:
        key = os.path.normcase(str(folder))
        if key in self._seen or kind not in self.wanted:
            return
        self._seen.add(key)
        found = existing_note(literal(folder))
        if found:
            self.result.skipped.append(Skipped(folder, kind, f"{HAS_NOTE} {Path(found).name}"))
        else:
            self.result.targets.append(Target(folder, kind))


LONG_PREFIX = "\\\\?\\"  # Windows' literal-path prefix
UNC_LONG_PREFIX = "\\\\?\\UNC\\"


def literal(folder: Path) -> str:
    """`folder` as a path Windows opens as written. A name ending in a dot or a space ('Banks, Iain M.') is otherwise cut
    short by Windows and opens nothing (the comics and books trees have such names; comic-checker met the same)."""
    text = str(folder)
    if not os.path.isabs(text):
        text = os.path.abspath(text)  # (abspath itself cuts a trailing dot: only for a relative path)
    if os.name != "nt" or not any(part.endswith((".", " ")) for part in Path(text).parts[1:]):
        return text
    if text.startswith("\\\\"):
        return UNC_LONG_PREFIX + text[2:]
    return LONG_PREFIX + text


def entries(folder: Path) -> tuple[list[str], list[Path]]:
    """(file names, sub-folders) directly in `folder`, sub-folders by name (as plain paths). Hidden names, symbolic links
    and this program's temp files are left out; an unreadable folder has none. Names ending in a dot are read too."""
    files: list[str] = []
    dirs: list[Path] = []
    try:
        with os.scandir(literal(folder)) as found:
            for entry in found:
                if entry.name.startswith(".") or is_app_temp_name(entry.name):
                    continue
                try:
                    if entry.is_dir(follow_symlinks=False):
                        dirs.append(Path(folder) / entry.name)
                    else:
                        files.append(entry.name)
                except OSError:
                    continue
    except OSError:
        return [], []
    dirs.sort(key=lambda p: p.name.casefold())
    return files, dirs


def has_extension(names, extensions) -> bool:
    return any(os.path.splitext(n)[1].lower() in extensions for n in names)


def is_place_name(name: str) -> bool:
    """A place to keep things, not a genre: music's generic names plus the book and comic ones, raw or without numbering."""
    return is_generic_name(name) or any(fold_name(n) in PLACE_NAMES for n in {name, lookup_name(name)})


def is_note_free_name(name: str) -> bool:
    return name.strip() == ATTENTION_MARKER or is_alphabetical_grouping(name)


def roots_of(paths) -> tuple[list[Path], list[str]]:
    roots: list[Path] = []
    missing: list[str] = []
    for p in paths:
        path = Path(p)
        if path.is_dir():
            roots.append(path)
        elif path.is_file():
            roots.append(path.parent)
        else:
            missing.append(str(p))
    return roots, missing


Callback = Optional[Callable[[Path], None]]
