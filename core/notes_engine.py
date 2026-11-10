"""
core/notes_engine.py

The one engine core of the folder notes, shared by every media type (plan step 8). A media type's engine
(core/music/flow.py, core/video/flow.py) knows how to find and judge a folder; everything around that is here, the same for
all of them:

  build_proposals(targets, engine, ...)     one Proposal per target in order (progress, cancel, on_proposal); never writes
  write_proposal(proposal, dry_run=...)     the shared writer: never overwrites, status: draft, a refresh to the Recycle Bin
  save_edited_note(path, text, expect)      a note a person edited in the note pane (only while unchanged on disk)
  record_note_created(path, text, ...)      the opt-in History entry of a written note
  undo_note_entry(entry)                    its undo (Recycle Bin, only while the note is unchanged)
  summarize(proposals, results)             counts for a report
  wiki_fetch()                              the one process-wide Wikipedia fetch (one pace for every engine of the run)

What an ENGINE provides (the review page, the command line and build_proposals rely on these and nothing else):

  build_proposal(target) -> Proposal         never raises for a service failure (the problem is in `problems`)
  rebuild(proposal, candidate=None, level="") the proposal again: from a picked candidate, or an explicit level
  can_choose(proposal, candidate) -> bool     may a person pick this candidate?
  best_guess(proposal) -> Candidate | None    the candidate an --include-uncertain run would write from
  local_note(proposal) -> Proposal            the explicit minimal note from the folder alone
  close()                                     ends any helper thread
  stats, phases                               the request counts and where the time went (redactor_common)

Qt-free.
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

from core import history
from core.version import APP_VERSION
from redactor_common.core import wikipedia as wp
from redactor_common.core.notes import NoteWriteResult
from redactor_common.core.notes_model import NotesSummary, Proposal, build_each, record_note_entry
from redactor_common.core.notes_model import summarize as _summarize
from redactor_common.core.notes_model import undo_note_entry as _undo_note_entry
from redactor_common.core.notes_model import write_proposal as _write_proposal
from redactor_common.core.trash import trash_with_fallback

WIKI_USER_AGENT = f"folderredactor/{APP_VERSION} ( https://github.com/Erlbon/folderredactor )"
_WIKI_FETCH = wp.make_fetch(WIKI_USER_AGENT)

Progress = Callable[[int, int, str], None]


def wiki_fetch() -> Callable:
    """The real Wikipedia fetch, one for the whole process: music and video lookups keep to one pace together."""
    return _WIKI_FETCH


def build_proposals(
    targets: list, engine, progress: Optional[Progress] = None, cancel: Optional[Callable[[], bool]] = None,
    on_proposal: Optional[Callable[[Proposal], None]] = None,
) -> list:
    """One Proposal per target, in order, from `engine.build_proposal`. `progress(done, total, label)` is called before
    each target; `cancel()` returning True ends the run early (the proposals built so far are returned); `on_proposal(p)`
    is called as each one is ready (the command line reports it there, so an interrupted run keeps what it did). Network
    only; this function writes no file."""
    return build_each(targets, engine.build_proposal, progress, cancel, on_proposal)


def summarize(proposals: list, results: Optional[dict[str, NoteWriteResult]] = None, cancelled: bool = False) -> NotesSummary:
    return _summarize(proposals, results, cancelled)


def _trash():
    """The Recycle Bin. On a drive without one (a network share) the move fails and the file is kept: this app has no
    backup-folder setting yet."""
    return trash_with_fallback(None)


def write_proposal(proposal: Proposal, dry_run: bool = False, allow_uncertain: bool = False) -> NoteWriteResult:
    """Writes the draft of a CONFIDENT proposal (the shared write_proposal: an uncertain / none one is refused with status
    'skipped' unless a person chose it, an existing note is never overwritten). With the opt-in History on, a written note
    is recorded so it can be undone from Tools > History (undo_note_entry). A refresh sends the older note to the Recycle
    Bin; where there is none (a network share) the refresh fails and the older note is kept.

    A proposal with `amend` set (music: the `layout:` line added to an about.md that is there) changes a note that may be the
    person's own: core/note_amend.py writes it, only while the note is still what was looked at, the old one to the Recycle Bin."""
    if getattr(proposal, "amend", False) and proposal.is_update:
        return _amend(proposal, dry_run, allow_uncertain)
    return _write_proposal(proposal, dry_run, allow_uncertain, record=record_note_created, trash=_trash())


def _amend(proposal: Proposal, dry_run: bool, allow_uncertain: bool) -> NoteWriteResult:
    from redactor_common.core.notes_model import STATUS_SKIPPED  # noqa: PLC0415

    from core.note_amend import amend_note  # noqa: PLC0415

    if (proposal.confidence.value != "confident" and not allow_uncertain) or not proposal.note_text:
        return NoteWriteResult(STATUS_SKIPPED, proposal.path, "there is no change to write", dry_run)
    path = proposal.old_state.path
    old_bytes = None
    if not dry_run:
        try:
            with open(path, "rb") as handle:
                old_bytes = handle.read()
        except OSError:
            old_bytes = None
    result = amend_note(path, proposal.note_text, proposal.old_state, dry_run=dry_run, trash=_trash())
    if result.ok and not dry_run:
        record_note_created(result.path, proposal.note_text, True, old_bytes=old_bytes)
    return result


def save_edited_note(path: str, text: str, expect, trash=None) -> NoteWriteResult:
    """A note a person edited in the note pane (window review 2026-11-10, card 7): written only while the note on disk is
    still what was read (`expect`, its NoteState), the old one to the Recycle Bin (on a share without one the save is refused
    and the note stays as it was). The body-sha line is left as it was, so the note reads as edited by a person from now
    on and no lookup touches it again. Recorded in the opt-in History as a refresh, so it can be undone."""
    from core.note_amend import amend_note  # noqa: PLC0415

    try:
        with open(path, "rb") as handle:
            old_bytes = handle.read()
    except OSError:
        old_bytes = None
    result = amend_note(path, text, expect, trash=trash or _trash())
    if result.ok:
        record_note_created(result.path, text, True, old_bytes=old_bytes)
    return result


def record_note_created(path: str, text: str, replaced: bool = False, old_bytes=None) -> None:
    """History entry for a written note when the opt-in History is on (otherwise nothing is touched, nothing stored). A
    created note is 'note'; a refresh is 'note-update' and keeps the replaced text in notes_backup next to the settings, so
    the undo can put it back. The entry keeps the SHA-256 of what was written so an undo can tell whether the person edited
    it since."""
    if not history.history_enabled():
        return
    try:
        record_note_entry(history.get_journal(), history.notes_backup_base(), path, text, replaced, old_bytes)
    except Exception as exc:  # noqa: BLE001 -- the note is already written; a journal failure never undoes it
        _report(exc)


def undo_note_entry(entry, journal=None) -> str:
    """Undoes a History entry of a written note (the shared undo: the Recycle Bin, only if the note still holds exactly what
    was written; a refresh gets its older text back). Returns '' or a plain-language problem."""
    return _undo_note_entry(entry, journal if journal is not None else history.get_journal(), trash=_trash(),
                            backup_base=history.notes_backup_base())


def _report(exc: BaseException) -> None:
    """A History failure is logged, never raised: the note itself was written."""
    try:
        logging.getLogger("folderredactor.history").warning("the note was written but History could not record it: %s", exc)
    except Exception:  # noqa: BLE001 -- reporting must never fail the write
        pass
