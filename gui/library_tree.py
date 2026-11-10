"""
gui/library_tree.py

The left side of the window: the library's folders as a tree, each with its note light (gui/lights.py) and, when it has a
draft that can be written, a tick box (window review 2026-11-10, cards 1 and 11).

Light on the library: a folder's children are listed when it is opened (one listing, never a walk of the tree), and the
note state of each child (does it have a note, is it ours, current, outdated, edited) is read by one background thread, so
a slow share never freezes the window; until it is known the light stays empty.

  LibraryTree.set_root(folder)              show a library
  LibraryTree.set_draft(path, waiting, tickable, ticked)   the window's drafts, as lights and tick boxes
  LibraryTree.refresh_state(path)           read a folder's note again (after a write or an edit)
  signals: folderSelected(str), tickToggled(str, bool)
"""

from __future__ import annotations

import os
import queue
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtWidgets import QAbstractItemView, QTreeWidget, QTreeWidgetItem

from core.music.local import is_alphabetical_grouping
from gui.lights import LIGHT_PLAIN, folder_light, light_icon
from redactor_common.core.notes import existing_note, note_status
from redactor_common.core.temp_names import is_app_temp_name

PATH_ROLE = Qt.ItemDataRole.UserRole
LOADED_ROLE = Qt.ItemDataRole.UserRole + 1


def path_key(path: str | os.PathLike) -> str:
    return os.path.normcase(os.path.abspath(os.fspath(path)))


def subfolders(folder: str) -> list[str]:
    """The folders directly in `folder`, by name (case-blind); hidden ones (a leading dot) and this program's temp files left
    out. An unreadable folder has none."""
    try:
        with os.scandir(folder) as entries:
            names = [e.name for e in entries if e.is_dir(follow_symlinks=False)
                     and not e.name.startswith(".") and not is_app_temp_name(e.name)]
    except OSError:
        return []
    return [os.path.join(folder, n) for n in sorted(names, key=str.casefold)]


class NoteStateReader(QThread):
    """Reads (note state, note path, has subfolders) of the folders it is given, one at a time, off the GUI thread."""

    found = pyqtSignal(str, object, str, bool)  # path, STATE_* or None, the note's path or '', has subfolders

    def __init__(self, parent=None):
        super().__init__(parent)
        self._queue: queue.Queue = queue.Queue()

    def ask(self, path: str) -> None:
        self._queue.put(path)

    def stop(self) -> None:
        self._queue.put(None)
        self.wait(5000)

    def run(self) -> None:
        while True:
            path = self._queue.get()
            if path is None:
                return
            try:
                note = existing_note(path)
                state = note_status(note).kind if note else None
                has_dirs = bool(subfolders(path))
            except OSError:
                note, state, has_dirs = None, None, False
            self.found.emit(path, state, note or "", has_dirs)


class LibraryTree(QTreeWidget):
    folderSelected = pyqtSignal(str)
    tickToggled = pyqtSignal(str, bool)
    stateRead = pyqtSignal(str)  # a folder's note state is known (tests wait on it)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setColumnCount(1)
        self.setUniformRowHeights(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.root = ""
        self._items: dict[str, QTreeWidgetItem] = {}
        self.states: dict[str, tuple[Optional[str], str]] = {}  # path key -> (STATE_* or None, note path)
        self._drafts: dict[str, tuple[bool, bool, bool]] = {}  # path key -> (waiting, tickable, ticked)
        self._reader = NoteStateReader(self)
        self._reader.found.connect(self._on_found)
        self._reader.start()
        self.itemExpanded.connect(self._load_children)
        self.currentItemChanged.connect(self._on_current)
        self.itemChanged.connect(self._on_item_changed)

    # -- the library -----------------------------------------------------------------------------------------

    def shutdown(self) -> None:
        if self._reader.isRunning():
            self._reader.stop()

    def set_root(self, folder: str) -> None:
        self.blockSignals(True)
        self.clear()
        self._items.clear()
        self.states.clear()
        self._drafts.clear()
        self.root = folder
        top = self._make_item(folder, folder)
        self.addTopLevelItem(top)
        self.blockSignals(False)
        top.setExpanded(True)  # lists the first level
        self.setCurrentItem(top)

    def _make_item(self, path: str, text: str) -> QTreeWidgetItem:
        item = QTreeWidgetItem([text])
        item.setData(0, PATH_ROLE, path)
        item.setData(0, LOADED_ROLE, False)
        item.setToolTip(0, path)
        item.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator)
        self._items[path_key(path)] = item
        self._style(item)
        self._reader.ask(path)
        return item

    def _load_children(self, item: QTreeWidgetItem) -> None:
        if item.data(0, LOADED_ROLE):
            return
        item.setData(0, LOADED_ROLE, True)
        children = subfolders(item.data(0, PATH_ROLE))
        self.blockSignals(True)
        for child in children:
            item.addChild(self._make_item(child, os.path.basename(child)))
        self.blockSignals(False)
        if not children:
            item.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.DontShowIndicator)

    def item_for(self, path: str | os.PathLike) -> Optional[QTreeWidgetItem]:
        return self._items.get(path_key(path))

    def reveal(self, path: str | os.PathLike) -> Optional[QTreeWidgetItem]:
        """The item of `path`, opening the folders above it on the way (it must lie under the root)."""
        item = self.item_for(path)
        if item is not None or not self.root:
            return item
        try:
            rel = Path(os.path.relpath(os.fspath(path), self.root))
        except ValueError:
            return None
        if rel.parts and rel.parts[0] == "..":
            return None
        current = self.item_for(self.root)
        walked = Path(self.root)
        for part in rel.parts:
            if current is None:
                return None
            self._load_children(current)
            walked = walked / part
            current = self.item_for(walked)
        return current

    def current_path(self) -> str:
        item = self.currentItem()
        return item.data(0, PATH_ROLE) if item is not None else ""

    def select(self, path: str | os.PathLike) -> bool:
        item = self.reveal(path)
        if item is None:
            return False
        parent = item.parent()
        while parent is not None:
            parent.setExpanded(True)
            parent = parent.parent()
        self.setCurrentItem(item)
        self.scrollToItem(item)
        return True

    def visible_paths(self) -> list[str]:
        """Every folder shown (opened) in the tree, top to bottom."""
        out: list[str] = []

        def walk(item: QTreeWidgetItem) -> None:
            out.append(item.data(0, PATH_ROLE))
            if item.isExpanded():
                for i in range(item.childCount()):
                    walk(item.child(i))

        for i in range(self.topLevelItemCount()):
            walk(self.topLevelItem(i))
        return out

    # -- lights and ticks --------------------------------------------------------------------------------------

    def note_state(self, path: str) -> tuple[Optional[str], str]:
        return self.states.get(path_key(path), (None, ""))

    def state_known(self, path: str) -> bool:
        return path_key(path) in self.states

    def refresh_state(self, path: str) -> None:
        self._reader.ask(path)

    def set_draft(self, path: str, waiting: bool, tickable: bool = False, ticked: bool = False) -> None:
        key = path_key(path)
        if waiting or tickable:
            self._drafts[key] = (waiting, tickable, ticked)
        else:
            self._drafts.pop(key, None)
        item = self.reveal(path)
        if item is not None:
            self._style(item)

    def _on_found(self, path: str, state, note: str, has_dirs: bool) -> None:
        self.states[path_key(path)] = (state, note)
        item = self.item_for(path)
        if item is not None:
            if not has_dirs and not item.data(0, LOADED_ROLE):
                item.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.DontShowIndicator)
            self._style(item)
        self.stateRead.emit(path)

    def _style(self, item: QTreeWidgetItem) -> None:
        path = item.data(0, PATH_ROLE)
        key = path_key(path)
        waiting, tickable, ticked = self._drafts.get(key, (False, False, False))
        self.blockSignals(True)
        try:
            if item.parent() is not None and is_alphabetical_grouping(os.path.basename(path)) and not waiting:
                item.setIcon(0, light_icon(LIGHT_PLAIN))
            elif key in self.states or waiting:
                item.setIcon(0, light_icon(folder_light(self.states.get(key, (None, ""))[0], waiting)))
            else:
                item.setIcon(0, light_icon(LIGHT_PLAIN))  # not read yet
            flags = item.flags()
            if tickable:
                item.setFlags(flags | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(0, Qt.CheckState.Checked if ticked else Qt.CheckState.Unchecked)
            else:
                item.setFlags(flags & ~Qt.ItemFlag.ItemIsUserCheckable)
                item.setData(0, Qt.ItemDataRole.CheckStateRole, None)
        finally:
            self.blockSignals(False)

    # -- signals -----------------------------------------------------------------------------------------------

    def _on_current(self, current, _previous) -> None:
        if current is not None:
            self.folderSelected.emit(current.data(0, PATH_ROLE))

    def _on_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if column != 0 or not (item.flags() & Qt.ItemFlag.ItemIsUserCheckable):
            return
        self.tickToggled.emit(item.data(0, PATH_ROLE), item.checkState(0) == Qt.CheckState.Checked)
