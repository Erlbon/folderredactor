"""Driving Notes > Create Notes through the REAL main window, for the music and the video window-flow tests: the modal
dialogs (the folder question, the review page, the message boxes) are stepped by a generator on a timer, so a test can
click their widgets the way a person does."""

from __future__ import annotations

import time
import traceback

import pytest
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox

from redactor_common.gui.notes_review_dialog import NotesReviewDialog
from redactor_common.gui.notes_scope_dialog import NotesScopeDialog


class Script:
    def __init__(self, generator):
        self.gen, self.error, self.done = generator, "", False
        self.timer = QTimer()
        self.timer.timeout.connect(self.tick)
        self.busy = False
        self.timer.start(20)

    def tick(self):
        if self.busy or self.done:
            return
        self.busy = True
        try:
            next(self.gen)
        except StopIteration:
            self.done = True
        except BaseException:  # noqa: BLE001
            self.error, self.done = traceback.format_exc(), True
        finally:
            self.busy = False
        if self.done:
            self.timer.stop()
            for w in QApplication.topLevelWidgets():
                if isinstance(w, (NotesReviewDialog, NotesScopeDialog)) and w.isVisible():
                    w.done(0)


def review():
    found = [w for w in QApplication.topLevelWidgets() if isinstance(w, NotesReviewDialog) and w.isVisible()]
    return found[0] if found else None


def scope():
    found = [w for w in QApplication.topLevelWidgets() if isinstance(w, NotesScopeDialog) and w.isVisible()]
    return found[0] if found else None


def wait(cond, what, timeout=30):
    end = time.perf_counter() + timeout
    while not cond():
        assert time.perf_counter() < end, what
        yield


def click(widget):
    QTest.mouseClick(widget, Qt.MouseButton.LeftButton)


@pytest.fixture
def boxes(monkeypatch):
    """Every message box answered at once and kept as (title, text); a question is answered No unless `boxes.yes` holds
    a word of it."""
    seen = Boxes()
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda p, t, x, *a, **k: seen.append((t, x)) or QMessageBox.StandardButton.Ok))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda p, t, x, *a, **k: seen.append((t, x)) or QMessageBox.StandardButton.Ok))

    def question(p, t, x, *a, **k):
        seen.append((t, x))
        return QMessageBox.StandardButton.Yes if any(w in x for w in seen.yes) else QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "question", staticmethod(question))
    return seen


class Boxes(list):
    """The (title, text) of every box shown; `yes` lists words of the questions to answer Yes."""

    def __init__(self):
        super().__init__()
        self.yes: list[str] = []

    def said(self, words: str) -> bool:
        return any(words in text for _title, text in self)


def run(window, monkeypatch, folder, fetchers, scenario, must_finish=True, choose=None):
    """Notes > Create Notes on the opened library `folder`: the folder question first (`choose(dialog)` sets it up; by
    default the folder is picked with Another folder...), then the scenario."""
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: str(folder)))
    window.open_library_folder(str(folder))
    window.notes_fetchers = lambda: fetchers

    def with_scope_step():
        yield from wait(lambda: scope() is not None, "the scope dialog")
        dialog = scope()
        if choose is not None:
            choose(dialog)
        else:
            dialog.other_radio.click()
        click(dialog.continue_button)
        yield from scenario()

    script = Script(with_scope_step())
    window.actions_by_key["create_notes"].trigger()
    script.timer.stop()
    assert script.error == "", script.error
    assert script.done or not must_finish, "the scenario did not finish"
