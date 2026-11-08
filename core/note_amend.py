"""
core/note_amend.py

Adding ONE line to the front matter of a note that is already there (the `layout:` line of a genre folder's about.md, which
Pluteus reads to find the artists): every other line of the note stays exactly as it was, `status: draft` and the person's own
keys included. Qt-free.

  with_front_matter_line(text, key, value)    the note text with `key: value` added (None when that is not safe)
  amend_note(path, text, expect, ...)         writes it, only while the note is still what was looked at

The stamp: a note of ours that nobody edited (state 'current') gets its body-sha worked out again, so it still reads as ours
and untouched afterwards. An edited note or someone else's keeps its lines as they are; only the new one is added.

The write is the refresh's (redactor_common's replace_note) without its 'only notes of ours' rule, since a person said yes to
exactly this change: the new text goes to a hidden temp file, the note is checked once more, the old one goes to the Recycle
Bin, the new one is linked into place without ever overwriting anything.
"""

from __future__ import annotations

import os
import re
import secrets
from typing import Callable, Optional

from redactor_common.core.notes import (
    MAX_NOTE_BYTES, STATE_CURRENT, STATUS_CHANGED, STATUS_ERROR, STATUS_EXISTS, STATUS_TOO_LARGE, STATUS_WRITTEN, NoteState,
    NoteWriteResult, normalize_note_text, note_hash, note_status, parse_front_matter,
)
from redactor_common.core.temp_names import is_app_temp_name

_SHA_LINE = re.compile(r"^body-sha\s*:")


def with_front_matter_line(text: str, key: str, value: str, restamp: bool = False) -> Optional[str]:
    """`text` with a `key: value` line added at the end of its front matter block (a new block at the top when it has none).
    None when the note already has `key`, or starts with '---' but its block is not clean (it would not be read as front
    matter: adding to it could break it). `restamp`: work the body-sha line out again (a note of ours nobody edited)."""
    text = normalize_note_text(text)
    meta, _body = parse_front_matter(text)
    if key.lower() in meta:
        return None
    line = f"{key}: {value}"
    lines = text.split("\n")
    if not meta:
        if lines and lines[0].rstrip() == "---":
            return None  # a block that is not clean (or an empty one): left alone
        return normalize_note_text(f"---\n{line}\n---\n\n{text}")
    end = next(i for i in range(1, len(lines)) if lines[i].strip() in ("---", "..."))
    stamp = [i for i in range(1, end) if _SHA_LINE.match(lines[i])]
    at = stamp[0] if stamp else end  # before the stamp lines' last one, where the shape keeps it
    for i in range(1, end):
        if re.match(r"^(generator|note-format)\s*:", lines[i]):
            at = min(at, i)
            break
    lines.insert(at, line)
    out = "\n".join(lines)
    if restamp and stamp:
        sha_at = stamp[0] + (1 if at <= stamp[0] else 0)
        lines = out.split("\n")
        lines[sha_at] = f"body-sha: {note_hash(out)}"
        out = "\n".join(lines)
    return normalize_note_text(out)


def _temp_path(folder: str, file_name: str) -> str:
    stem, ext = os.path.splitext(file_name)
    name = f".{stem}.{secrets.token_hex(4)}.redact-part{ext}"
    assert is_app_temp_name(name)
    return os.path.join(folder, name)


def amend_note(path: str, new_text: str, expect: NoteState, *, dry_run: bool = False,
               trash: Optional[Callable[[str], None]] = None) -> NoteWriteResult:
    """Puts `new_text` in place of the note at `path`, ONLY while the note still hashes to what `expect` saw (status 'changed'
    and nothing touched otherwise). The old note goes to the Recycle Bin (`trash`; when it cannot, nothing changes). The result's
    `replaced` is the old note's path."""
    path = os.fspath(path)
    if not os.path.exists(path):
        return NoteWriteResult(STATUS_CHANGED, path, "The note is not there any more.", dry_run)
    if note_status(path).sha != expect.sha:
        return NoteWriteResult(STATUS_CHANGED, path, "The note was changed since it was looked at: left alone.", dry_run)
    data = normalize_note_text(new_text).encode("utf-8")
    if not data:
        return NoteWriteResult(STATUS_ERROR, path, "The note is empty.", dry_run)
    if len(data) > MAX_NOTE_BYTES:
        return NoteWriteResult(STATUS_TOO_LARGE, path, f"The note is {len(data)} bytes; the limit is {MAX_NOTE_BYTES}.", dry_run)
    if dry_run:
        return NoteWriteResult(STATUS_WRITTEN, path, f"Would add to {path}", True, replaced=path)

    from redactor_common.core.trash import TrashError, trash_with_retries

    folder = os.path.dirname(path)
    temp = _temp_path(folder, os.path.basename(path))
    try:
        try:
            fd = os.open(temp, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0), 0o666)
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
        except OSError as exc:
            return NoteWriteResult(STATUS_ERROR, path, f"The new note could not be written: {exc}")
        if note_status(path).sha != expect.sha:  # the last look before the old note goes
            return NoteWriteResult(STATUS_CHANGED, path, "The note was changed meanwhile: left alone.")
        try:
            (trash or trash_with_retries())(path)
        except TrashError as exc:
            return NoteWriteResult(STATUS_ERROR, path, f"The old note could not be moved to the Recycle Bin, so it was kept: {exc}")
        if os.path.lexists(path):
            return NoteWriteResult(STATUS_ERROR, path, "The old note is still there after the move: left alone.")
        try:
            os.link(temp, path)
        except FileExistsError:
            return NoteWriteResult(STATUS_EXISTS, path, "A note appeared there meanwhile: left alone.", replaced=path)
        except OSError:
            try:  # no hard links here (FAT, some shares): reserve the name, then replace our own reservation
                os.close(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o666))
                os.replace(temp, path)
            except FileExistsError:
                return NoteWriteResult(STATUS_EXISTS, path, "A note appeared there meanwhile: left alone.", replaced=path)
            except OSError as exc:
                return NoteWriteResult(STATUS_ERROR, path, f"The old note is in the Recycle Bin but the new one could not be "
                                                           f"written: {exc}", replaced=path)
    finally:
        try:
            os.unlink(temp)
        except OSError:
            pass
    return NoteWriteResult(STATUS_WRITTEN, path, f"Added to {path}", replaced=path)


def is_current(state: Optional[NoteState]) -> bool:
    return state is not None and state.kind == STATE_CURRENT
