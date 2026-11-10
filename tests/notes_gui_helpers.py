"""Driving the REAL main window for the music and the video window-flow tests: open a library, select a folder in the tree,
Notes > Look Up with the recorded replies as the network, and wait (pumping events) until the lookup thread is done. Message
boxes are answered at once and kept (the `boxes` fixture)."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QMessageBox


def pump(cond, what: str, timeout: float = 30) -> None:
    """Processes events until `cond()` is true (the lookup thread and the note-state reader report through signals)."""
    end = time.perf_counter() + timeout
    while not cond():
        assert time.perf_counter() < end, f"waited too long for {what}"
        QApplication.processEvents()
        time.sleep(0.005)
    QApplication.processEvents()


def click(widget):
    QTest.mouseClick(widget, Qt.MouseButton.LeftButton)


def idle(window) -> bool:
    w = window.worker
    return not window._lookup_running and not w.busy and not w.waiting() and not window._rebuilding


def open_library(window, folder: Path) -> None:
    window.open_library_folder(str(folder))
    pump(lambda: window.tree.state_known(str(folder)), "the library's first note states")


def select(window, folder: Path) -> None:
    assert window.tree.select(folder), folder
    pump(lambda: window.tree.state_known(str(folder)), f"the note state of {folder.name}")
    assert Path(window._shown) == Path(folder)


def set_options(window, below: bool = True, kinds=None, outdated: bool = False) -> None:
    registry = window.actions_by_key
    registry["look_up_below"].setChecked(below)
    registry["look_up_outdated"].setChecked(outdated)
    if kinds is not None:
        for (_media, kind), key in window.kind_actions.items():
            registry[key].setChecked(kind in kinds)
    window._on_options_changed()


def look_up(window, folder: Path, fetchers, *, library: Path | None = None, below: bool = True, kinds=None,
            outdated: bool = False) -> None:
    """Opens `library` (default: `folder`) if it is not open yet, selects `folder`, Look Up, waits until it is done."""
    library = library or folder
    if Path(window.library_folder or ".") != Path(library):
        open_library(window, library)
    window.notes_fetchers = lambda: fetchers
    set_options(window, below, kinds, outdated)
    select(window, folder)
    window.actions_by_key["look_up"].trigger()
    pump(lambda: idle(window), "the lookup", 60)


def wait_rebuilt(window) -> None:
    pump(lambda: idle(window), "the rebuild", 30)


def item(window, folder: Path):
    return window.item_of(str(folder))


def light(window, folder: Path) -> str:
    """The light the tree shows for `folder` (gui/lights.py), worked out the way the tree does."""
    from gui.library_tree import path_key
    from gui.lights import folder_light

    state, _note = window.tree.note_state(str(folder))
    waiting = window.tree._drafts.get(path_key(folder), (False, False, False))[0]
    return folder_light(state, waiting)


def tick_box(window, folder: Path):
    """The check state of `folder`'s row: None when it has no tick box."""
    row = window.tree.item_for(folder)
    if row is None or not (row.flags() & Qt.ItemFlag.ItemIsUserCheckable):
        return None
    return row.checkState(0) == Qt.CheckState.Checked


@pytest.fixture
def boxes(monkeypatch):
    """Every message box answered at once and kept as (title, text); a question is answered No unless `boxes.yes` holds
    a word of it."""
    seen = Boxes()
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda p, t, x, *a, **k: seen.append((t, x)) or QMessageBox.StandardButton.Ok))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda p, t, x, *a, **k: seen.append((t, x)) or QMessageBox.StandardButton.Ok))

    def question(p, t, x, *a, **k):
        seen.append((t, x))
        if any(w in x for w in seen.yes):
            buttons = a[0] if a else QMessageBox.StandardButton.Yes
            return (QMessageBox.StandardButton.Save if buttons & QMessageBox.StandardButton.Save
                    else QMessageBox.StandardButton.Yes)
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "question", staticmethod(question))
    return seen


class Boxes(list):
    """The (title, text) of every box shown; `yes` lists words of the questions to answer Yes."""

    def __init__(self):
        super().__init__()
        self.yes: list[str] = []

    def said(self, words: str) -> bool:
        return any(words in text for _title, text in self)
