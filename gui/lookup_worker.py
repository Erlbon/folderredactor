"""
gui/lookup_worker.py

Look Up in the window (window review 2026-11-10, card 2): the scan and the lookups of a folder run on ONE background thread,
and each draft is handed to the window as soon as it is ready, so the first drafts can be read while the rest are looked
up. A person's choice on a draft (a candidate, a level, a link, the genres, a best guess) is a job on the same thread, put
ahead of the lookups still waiting: an engine is only ever used by this one thread.

One engine per media type for as long as the library is open (a draft can only be rebuilt by the engine that built it).

  LookupWorker.look_up(media, folder, below, kinds, outdated)   a job: scan `folder`, then look up every target
  LookupWorker.rebuild(media, key, proposal, candidate, level, **extra)   a job: rebuild one draft
  LookupWorker.scan_only(media, folder, kinds, outdated)   a job: Notes > Scan for Notes, the same scan as Look Up's (no
                                 network), to show which folders are left; ends in scan_done(job, ScanSummary)
  LookupWorker.cancel()          ends the running look-up after the folder in hand, or the scan (rebuilds are not cancelled)
  LookupWorker.reset()           a new library: the engines are closed and made again on the next job
  signals: scanned(job, count, message), started_folder(job, done, total, name), proposal(media, Proposal),
           finished_job(job, built, cancelled, problem), rebuilt(key, Proposal), rebuild_failed(key, message, is_link_problem),
           scan_progress(job, folder), scan_done(job, ScanSummary)
"""

from __future__ import annotations

import collections
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

from PyQt6.QtCore import QThread, pyqtSignal

MUSIC = "music"
VIDEO = "video"


@dataclass
class LookupJob:
    media: str
    folder: str
    below: bool
    kinds: tuple
    outdated: bool
    number: int = 0


@dataclass
class RebuildJob:
    media: str
    key: str
    proposal: object
    candidate: object = None
    level: str = ""
    extra: dict = field(default_factory=dict)
    best_guess: bool = False  # the candidate is the engine's best guess, worked out on this thread


@dataclass
class ScanJob:
    media: str
    folder: str
    kinds: tuple
    outdated: bool
    number: int = 0


@dataclass
class ScanSummary:
    """What Scan for Notes found under `folder`: the folders LEFT (no note yet, or an outdated note of ours when the outdated
    option is on) and every note-level folder it judged (left or not), for the tree's counts."""

    folder: str
    left: list[str] = field(default_factory=list)
    levels: list[str] = field(default_factory=list)
    without: int = 0  # left: no note at all
    outdated: int = 0  # left: an older note of ours to refresh
    have: int = 0  # a note already, left alone
    cancelled: bool = False
    problem: str = ""


class _ScanCancelled(Exception):
    pass


PROGRESS_EVERY = 0.2  # seconds between two scan_progress signals


class LookupWorker(QThread):
    scanned = pyqtSignal(int, int, str)
    scan_progress = pyqtSignal(int, str)  # job, the folder in hand (relative to the scanned folder)
    scan_done = pyqtSignal(int, object)  # job, ScanSummary
    started_folder = pyqtSignal(int, int, int, str)
    proposal = pyqtSignal(str, object)
    finished_job = pyqtSignal(int, int, bool, str)
    rebuilt = pyqtSignal(str, object)
    rebuild_failed = pyqtSignal(str, str, bool)
    status = pyqtSignal(str)  # 'MusicBrainz is busy, waiting 4 s'

    def __init__(self, make_engine: Callable[[str], object], parent=None):
        """`make_engine(media)` makes the engine of a media type (called on this thread)."""
        super().__init__(parent)
        self._make_engine = make_engine
        self._engines: dict[str, object] = {}
        self._jobs: collections.deque = collections.deque()
        self._wake = threading.Condition()
        self._cancel = threading.Event()
        self._stop = False
        self._reset = False
        self._numbers = 0
        self.busy = False
        self.link_errors: tuple = (ValueError,)

    # -- asking (GUI thread) -----------------------------------------------------------------------------------

    def look_up(self, media: str, folder: str, below: bool, kinds: tuple, outdated: bool) -> int:
        self._numbers += 1
        job = LookupJob(media, folder, below, tuple(kinds), outdated, self._numbers)
        self._put(job, front=False)
        return job.number

    def scan_only(self, media: str, folder: str, kinds: tuple, outdated: bool) -> int:
        self._numbers += 1
        job = ScanJob(media, folder, tuple(kinds), outdated, self._numbers)
        self._put(job, front=False)
        return job.number

    def rebuild(self, media: str, key: str, proposal, candidate=None, level: str = "", best_guess: bool = False,
                **extra) -> None:
        self._put(RebuildJob(media, key, proposal, candidate, level, extra, best_guess), front=True)

    def cancel(self) -> None:
        self._cancel.set()
        with self._wake:
            self._jobs = collections.deque(j for j in self._jobs if not isinstance(j, (LookupJob, ScanJob)))

    def reset(self) -> None:
        self.cancel()
        with self._wake:
            self._jobs.clear()
            self._reset = True
            self._wake.notify()

    def stop(self) -> None:
        self.cancel()
        with self._wake:
            self._stop = True
            self._wake.notify()
        self.wait(15000)

    def engine(self, media: str):
        """The engine of `media` if it was made (read-only helpers like best_guess / why_cannot_choose are safe to call)."""
        return self._engines.get(media)

    def waiting(self) -> int:
        with self._wake:
            return len(self._jobs)

    def _put(self, job, front: bool) -> None:
        with self._wake:
            if front:
                self._jobs.appendleft(job)
            else:
                self._jobs.append(job)
            self._wake.notify()

    # -- the thread --------------------------------------------------------------------------------------------

    def _engine(self, media: str):
        engine = self._engines.get(media)
        if engine is None:
            engine = self._engines[media] = self._make_engine(media)
            if hasattr(engine, "on_status"):
                engine.on_status = self.status.emit
        return engine

    def _close_engines(self) -> None:
        for engine in self._engines.values():
            try:
                engine.close()
            except Exception:  # noqa: BLE001 -- closing must never fail the window
                pass
        self._engines.clear()

    def run(self) -> None:
        while True:
            with self._wake:
                while not self._jobs and not self._stop and not self._reset:
                    self._wake.wait()
                if self._reset:
                    self._reset = False
                    self._close_engines()
                    continue
                if self._stop:
                    break
                job = self._jobs.popleft()
                self.busy = True
            try:
                if isinstance(job, RebuildJob):
                    self._run_rebuild(job)
                elif isinstance(job, ScanJob):
                    self._cancel.clear()
                    self.scan_done.emit(job.number, self._run_scan(job))
                else:
                    self._cancel.clear()
                    self._run_lookup(job)
            finally:
                self.busy = False
        self._close_engines()

    def _run_rebuild(self, job: RebuildJob) -> None:
        try:
            engine = self._engine(job.media)
            candidate = engine.best_guess(job.proposal) if job.best_guess else job.candidate
            if job.best_guess and candidate is None:
                self.rebuild_failed.emit(job.key, "No best guess for this folder.", False)
                return
            if not job.level and not job.extra:
                result = engine.rebuild(job.proposal, candidate=candidate)
            else:
                result = engine.rebuild(job.proposal, candidate=candidate, level=job.level, **job.extra)
        except self.link_errors as exc:
            self.rebuild_failed.emit(job.key, str(exc), "link" in job.extra)
            return
        except Exception as exc:  # noqa: BLE001 -- said in plain words, never a traceback
            self.rebuild_failed.emit(job.key, f"The lookup failed: {exc}", False)
            return
        self.rebuilt.emit(job.key, result)

    def _run_lookup(self, job: LookupJob) -> None:
        if job.media == MUSIC:
            from core.music.flow import build_proposals, scan  # noqa: PLC0415
            from gui.music_notes import nothing_found_why  # noqa: PLC0415
        else:
            from core.video.flow import build_proposals, scan  # noqa: PLC0415

            def nothing_found_why(found) -> str:
                return ""
        try:
            engine = self._engine(job.media)
            found = scan([job.folder], job.below, kinds=job.kinds, include_outdated=job.outdated)
        except Exception as exc:  # noqa: BLE001
            self.finished_job.emit(job.number, 0, False, f"The folders could not be read: {exc}")
            return
        targets = list(found.targets)
        message = "" if targets else (nothing_found_why(found) or _nothing_message(found, job))
        self.scanned.emit(job.number, len(targets), message)
        if not targets:
            self.finished_job.emit(job.number, 0, False, "")
            return
        built: list = []

        def report(done: int, total: int, _label: str) -> None:
            if done < total:
                self.started_folder.emit(job.number, done, total, targets[done].folder.name)

        def keep(p) -> None:
            built.append(p)
            self.proposal.emit(job.media, p)

        problem = ""
        try:
            build_proposals(targets, progress=report, cancel=self._cancel.is_set, on_proposal=keep, engine=engine)
        except Exception as exc:  # noqa: BLE001 -- the drafts built so far are kept
            problem = f"The lookup stopped early: {exc}"
        cancelled = self._cancel.is_set() and len(built) < len(targets)
        self.finished_job.emit(job.number, len(built), cancelled, problem)


    def _run_scan(self, job: ScanJob) -> ScanSummary:
        """Look Up's own scan (the same rules, the same ticked kinds and outdated option), with nothing looked up."""
        if job.media == MUSIC:
            from core.music.local import scan  # noqa: PLC0415
        else:
            from core.video.local import scan  # noqa: PLC0415
        summary = ScanSummary(job.folder)
        last = [0.0]

        def on_folder(folder) -> None:
            if self._cancel.is_set():
                raise _ScanCancelled
            now = time.monotonic()
            if now - last[0] >= PROGRESS_EVERY:
                last[0] = now
                try:
                    shown = os.path.relpath(str(folder), job.folder)
                except ValueError:
                    shown = str(folder)
                self.scan_progress.emit(job.number, "" if shown == "." else shown)

        try:
            found = scan([job.folder], True, kinds=job.kinds, include_outdated=job.outdated, on_folder=on_folder)
        except _ScanCancelled:
            summary.cancelled = True
            return summary
        except Exception as exc:  # noqa: BLE001 -- said in plain words, never a traceback
            summary.problem = f"The folders could not be read: {exc}"
            return summary
        for target in found.targets:
            summary.left.append(str(target.folder))
            summary.levels.append(str(target.folder))
            if getattr(target, "update", None) is not None:
                summary.outdated += 1
            else:
                summary.without += 1
        for skipped in found.skipped:
            if skipped.reason.startswith(HAS_NOTE_REASON):
                summary.levels.append(str(skipped.folder))
                summary.have += 1
        return summary


HAS_NOTE_REASON = "already has"  # how both scans start the reason of a folder skipped for its note


def _nothing_message(found, job: LookupJob) -> str:
    left = len(getattr(found, "skipped", []) or [])
    where = "in this folder or below" if job.below else "for this folder"
    return f"Nothing to look up {where}" + (f": {left} folder(s) already have a note." if left else ".")
