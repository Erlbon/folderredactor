"""
core/long_paths.py

Folder and file names that end in a dot or a space ('R.E.M.', 'Tolkien, J.R.R.'). Windows' own tools will not make them,
but they come onto a share from elsewhere (Linux, Samba, copy tools), and an ordinary Windows path to one is cut short:
the dot is dropped and nothing is found. literal(path) gives the path Windows opens as written. comic-checker met the same.

  literal(path)   the path as a string, with Windows' \\\\?\\ prefix only when a name in it ends in a dot or a space
"""

from __future__ import annotations

import os
from pathlib import Path

LONG_PREFIX = "\\\\?\\"  # Windows' literal-path prefix
UNC_LONG_PREFIX = "\\\\?\\UNC\\"


def needs_literal(path: str | os.PathLike) -> bool:
    return os.name == "nt" and any(part.endswith((".", " ")) for part in Path(os.fspath(path)).parts[1:])


def literal(path: str | os.PathLike) -> str:
    text = os.fspath(path)
    if not os.path.isabs(text):
        text = os.path.abspath(text)  # (abspath itself cuts a trailing dot: only for a relative path)
    if text.startswith("\\\\?\\") or not needs_literal(text):
        return text
    if text.startswith("\\\\"):
        return UNC_LONG_PREFIX + text[2:]
    return LONG_PREFIX + text
