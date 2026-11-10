"""
gui/note_pane.py

The right side of the window, always open (window review 2026-11-10, cards 6-9): the note of the folder selected in the tree.

  header        the folder, the note file and its state in words, a badge (the draft's confidence, or the light's word)
  Match strip   only for a draft that is not settled: redactor_common's ProposalPanel (MatchStrip below) with everything but
                the matching controls hidden (candidates, level, link, minimal note from the tags, genres); folds away
                once the draft can be written, one click opens it again
  the note      Preview / Raw / Before-after, a switch in the header row that stays put from folder to folder; the
                draft if there is one, else the note on disk, else "No note"
  Edit / Save   a note on disk can be edited in the Raw view (card 7, B); Save writes it, it then reads as edited by you
                and lookups leave it alone

The pane decides nothing and writes nothing itself: the window does, on its signals.
"""

from __future__ import annotations

import os
from html import escape
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QTextDocument
from PyQt6.QtWidgets import (
    QAbstractItemView, QButtonGroup, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QSizePolicy, QStackedWidget,
    QTextBrowser, QToolButton, QVBoxLayout, QWidget,
)

from gui.lights import LIGHT_WORDS, STATE_WORDS, folder_light
from redactor_common.core.notes import NoteState, note_status
from redactor_common.core.notes_model import Confidence
from redactor_common.core.notes_review import CONFIDENCE_WORDS, PENDING, ReviewItem
from redactor_common.gui.notes_review_dialog import BADGE_STYLES, ProposalPanel, ReviewHooks, diff_html

VIEW_PREVIEW, VIEW_RAW, VIEW_DIFF = 0, 1, 2
VIEW_NAMES = ("Preview", "Raw", "Before / after")
BADGE_BASE = " border-radius:4px; padding:3px 8px; font-weight:bold;"
LIGHT_BADGE = "background:#e4e4e4; color:#333333;"
MARKDOWN = QTextDocument.MarkdownFeature.MarkdownDialectGitHub | QTextDocument.MarkdownFeature.MarkdownNoHTML
NO_NOTE = "*No note in this folder.* Notes > Look Up (or the Look Up button) drafts one."
CANDIDATE_CAPTION = "Candidates found. Double-click the right one (or select it and press Enter) to build the note from it:"


class MatchStrip(ProposalPanel):
    """ProposalPanel with only its matching controls: the header, the note tabs and the footer are the pane's own."""

    def __init__(self, can_choose, hooks: Optional[ReviewHooks] = None, candidate_columns=("Name", "Details", "Score",
                                                                                                 "Source", "Matches")):
        super().__init__(can_choose, candidate_columns=candidate_columns, hooks=hooks)
        self.candidate_caption.setText(CANDIDATE_CAPTION)
        self.candidate_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.candidate_table.activated.connect(lambda _index: self._candidate_clicked())
        self.reasons_label.setTextFormat(Qt.TextFormat.PlainText)
        self._hide_extras()

    def _hide_extras(self) -> None:
        for w in (self.path_label, self.kind_label, self.badge, self.update_badge, self.state_label, self.tabs,
                  self.sources_label, self.open_note_button, self.show_folder_button, self.candidate_button):
            w.setVisible(False)

    def show_item(self, item: Optional[ReviewItem]) -> None:
        super().show_item(item)
        self._hide_extras()
        if item is None:
            return
        p = item.proposal
        reasons = list(p.reasons) + [r for r in (getattr(p, "level_reasons", []) or []) if r not in p.reasons]
        if item.message and item.state != PENDING:
            reasons.insert(0, f"NOT written: {item.message}")
        if reasons:  # one line; all of them in the tooltip
            more = f"  (+{len(reasons) - 1} more)" if len(reasons) > 1 else ""
            self.reasons_label.setText(reasons[0] + more)
            self.reasons_label.setToolTip("\n".join(reasons))
        rows = self.candidate_table.rowCount()
        if rows:
            header = self.candidate_table.horizontalHeader().height()
            row_height = self.candidate_table.verticalHeader().defaultSectionSize()
            scroll = self.candidate_table.horizontalScrollBar().sizeHint().height()  # the table may need it: never cut a row
            self.candidate_table.setFixedHeight(header + min(rows, 4) * row_height + scroll + 6)

    def has_controls(self) -> bool:
        return any(w.isVisibleTo(self) for w in (self.level_box, self.candidate_box, self.local_box, self.genres_box,
                                                   self.link_box, self.problems_label))


class NotePane(QWidget):
    editStarted = pyqtSignal()
    saveRequested = pyqtSignal(str)  # the edited text
    openNoteRequested = pyqtSignal()
    showFolderRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.path = ""
        self.item: Optional[ReviewItem] = None
        self.note_state: Optional[NoteState] = None  # the note on disk as it was read (Save checks it again)
        self.strip: Optional[MatchStrip] = None
        self._strip_open_for = ""  # the folder whose strip a person opened by hand
        self._editing = False

        self.path_label = QLabel("No library folder open.")
        font = self.path_label.font()
        font.setBold(True)
        self.path_label.setFont(font)
        self.path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.state_label = QLabel("")
        self.badge = QLabel("")
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.badge.setMinimumWidth(110)
        for label in (self.path_label, self.state_label):
            label.setWordWrap(True)
            label.setMinimumWidth(0)
            label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        titles = QVBoxLayout()
        titles.addWidget(self.path_label)
        titles.addWidget(self.state_label)
        head = QHBoxLayout()
        head.addLayout(titles, 1)
        head.addWidget(self.badge, 0, Qt.AlignmentFlag.AlignTop)

        self.match_toggle = QToolButton()
        self.match_toggle.setCheckable(True)
        self.match_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.match_toggle.setArrowType(Qt.ArrowType.RightArrow)
        self.match_toggle.setText("Match")
        self.match_toggle.setAutoRaise(True)
        self.match_toggle.toggled.connect(self._toggle_match)
        self.match_summary = QLabel("")
        self.match_summary.setStyleSheet("color: palette(mid);")
        self.match_row = QWidget()
        match_row = QHBoxLayout(self.match_row)
        match_row.setContentsMargins(0, 0, 0, 0)
        match_row.addWidget(self.match_toggle)
        match_row.addWidget(self.match_summary, 1)
        self.strip_holder = QWidget()
        self.strip_layout = QVBoxLayout(self.strip_holder)
        self.strip_layout.setContentsMargins(16, 0, 0, 0)

        self.view_buttons: list[QPushButton] = []
        self.view_group = QButtonGroup(self)
        self.view_group.setExclusive(True)
        views = QHBoxLayout()
        views.setSpacing(0)
        for index, name in enumerate(VIEW_NAMES):
            button = QPushButton(name)
            button.setCheckable(True)
            button.setAutoDefault(False)
            self.view_group.addButton(button, index)
            self.view_buttons.append(button)
            views.addWidget(button)
        self.view_buttons[0].setChecked(True)
        self.view_group.idClicked.connect(self.set_view)
        self.edit_button = QPushButton("Edit")
        self.save_button = QPushButton("Save")
        self.cancel_edit_button = QPushButton("Cancel")
        self.open_button = QPushButton("Open note")
        self.folder_button = QPushButton("Show in folder")
        for b in (self.edit_button, self.save_button, self.cancel_edit_button, self.open_button, self.folder_button):
            b.setAutoDefault(False)
        self.edit_button.clicked.connect(self.start_edit)
        self.save_button.clicked.connect(lambda: self.saveRequested.emit(self.raw.toPlainText()))
        self.cancel_edit_button.clicked.connect(self.cancel_edit)
        self.open_button.clicked.connect(self.openNoteRequested.emit)
        self.folder_button.clicked.connect(self.showFolderRequested.emit)
        tools = QHBoxLayout()
        tools.addLayout(views)
        tools.addStretch(1)
        for b in (self.edit_button, self.save_button, self.cancel_edit_button, self.open_button, self.folder_button):
            tools.addWidget(b)

        self.preview = QTextBrowser()
        self.preview.setOpenExternalLinks(True)
        self.raw = QPlainTextEdit()
        self.raw.setReadOnly(True)
        mono = self.raw.font()
        mono.setFamily("Consolas")
        self.raw.setFont(mono)
        self.diff = QTextBrowser()
        self.stack = QStackedWidget()
        for w in (self.preview, self.raw, self.diff):
            self.stack.addWidget(w)
        self.sources_label = QLabel("")
        self.sources_label.setStyleSheet("color: palette(mid);")
        self.sources_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(head)
        layout.addWidget(self.match_row)
        layout.addWidget(self.strip_holder)
        layout.addLayout(tools)
        layout.addWidget(self.stack, 1)
        layout.addWidget(self.sources_label)
        self.show_nothing()

    # -- the match strip -------------------------------------------------------------------------------------------

    def set_strip(self, strip: Optional[MatchStrip]) -> None:
        """The media type's strip (its hooks differ): music and video each have one; swapped when the library changes."""
        if self.strip is strip:
            return
        if self.strip is not None:
            self.strip.setParent(None)
        self.strip = strip
        if strip is not None:
            self.strip_layout.addWidget(strip)

    def _toggle_match(self, opened: bool) -> None:
        self.match_toggle.setArrowType(Qt.ArrowType.DownArrow if opened else Qt.ArrowType.RightArrow)
        self.strip_holder.setVisible(opened)
        if self.item is not None:
            self._strip_open_for = self.path if opened else ""

    # -- views -----------------------------------------------------------------------------------------------------

    def set_view(self, index: int) -> None:
        if not self.view_buttons[index].isEnabled() or (self._editing and index != VIEW_RAW):
            return
        self.view_buttons[index].setChecked(True)
        self.stack.setCurrentIndex(index)

    def current_view(self) -> int:
        return self.stack.currentIndex()

    def _enable_diff(self, on: bool) -> None:
        self.view_buttons[VIEW_DIFF].setEnabled(on)
        if not on and self.stack.currentIndex() == VIEW_DIFF:
            self.set_view(VIEW_PREVIEW)

    def _show_text(self, text: str, placeholder: str = "") -> None:
        self.raw.setPlainText(text)
        if text:
            self.preview.document().setMarkdown(ProposalPanel.render_body(text), MARKDOWN)
        else:
            self.preview.document().setMarkdown(placeholder, MARKDOWN)

    def _set_badge(self, text: str, style: str) -> None:
        self.badge.setText(text)
        self.badge.setStyleSheet(style + BADGE_BASE if text else "")
        self.badge.setVisible(bool(text))

    # -- what is shown -----------------------------------------------------------------------------------------------

    def show_nothing(self, text: str = "No library folder open.") -> None:
        self.path, self.item, self.note_state = "", None, None
        self.path_label.setText(text)
        self.state_label.setText("Open one with File > Open Library Folder, or drop a folder on this window."
                                 if text == "No library folder open." else "")
        self._set_badge("", "")
        self.match_row.setVisible(False)
        self.strip_holder.setVisible(False)
        self._show_text("", "")
        self._enable_diff(False)
        for b in (self.edit_button, self.save_button, self.cancel_edit_button, self.open_button, self.folder_button):
            b.setVisible(False)
        self.sources_label.setText("")

    def show_folder(self, path: str, state_kind: Optional[str], note_path: str, item: Optional[ReviewItem]) -> None:
        """The folder `path`: its draft `item` (pending) if there is one, else its note on disk (`note_path`, read here)."""
        if self._editing:
            self.cancel_edit()
        moved = path != self.path
        self.path, self.item = path, item
        self.path_label.setText(path)
        self.folder_button.setVisible(True)
        pending = item is not None and item.state == PENDING
        if pending:
            self._show_draft(item, state_kind, moved)
        else:
            self._show_note(path, state_kind, note_path, item)

    def _show_draft(self, item: ReviewItem, state_kind: Optional[str], moved: bool) -> None:
        p = item.proposal
        self.note_state = None
        name = os.path.basename(p.path)
        level = str(getattr(p, "level", "") or "")
        words = [f"{name}: draft" + (f" ({level})" if level else "")]
        if p.is_update:
            words.append(f"replaces the {STATE_WORDS.get(p.old_state.kind, 'note')}")
        elif state_kind:
            words.append(f"the folder has a {STATE_WORDS.get(state_kind, 'note')}")
        self.state_label.setText(";  ".join(words))
        self._set_badge(CONFIDENCE_WORDS[p.confidence], BADGE_STYLES[p.confidence])
        settled = p.writable
        if self.strip is not None:
            self.strip.show_item(item)
        has_controls = self.strip is not None and self.strip.has_controls()
        self.match_row.setVisible(has_controls)
        self.match_summary.setText(_match_summary(item))
        opened = has_controls and (not settled or self._strip_open_for == self.path)
        if moved:
            self._strip_open_for = ""
            opened = has_controls and not settled
        self.match_toggle.blockSignals(True)
        self.match_toggle.setChecked(opened)
        self.match_toggle.blockSignals(False)
        self.match_toggle.setArrowType(Qt.ArrowType.DownArrow if opened else Qt.ArrowType.RightArrow)
        self.strip_holder.setVisible(opened)
        placeholder = ("*No draft yet.* " + ("Pick one of the candidates above, or a level, to build a note."
                                             if p.candidates else "Nothing was found online for this folder: paste a link "
                                             "above, or make a minimal note from the tags."))
        self._show_text(p.note_text, placeholder)
        self._enable_diff(p.is_update and bool(p.note_text))
        if p.is_update and p.note_text:
            recycle = self.strip.hooks.recycle_note if self.strip is not None else ""
            self.diff.setHtml(diff_html(p.old_text, p.note_text) + f"<p>{escape(recycle)}</p>")
        else:
            self.diff.clear()
        self.edit_button.setVisible(False)
        self.save_button.setVisible(False)
        self.cancel_edit_button.setVisible(False)
        self.open_button.setVisible(p.is_update)
        self.sources_label.setText("Sources: " + ", ".join(p.sources) if p.sources else "Sources: none yet")

    def _show_note(self, path: str, state_kind: Optional[str], note_path: str, item: Optional[ReviewItem]) -> None:
        self.match_row.setVisible(False)
        self.strip_holder.setVisible(False)
        self._enable_diff(False)
        self.diff.clear()
        self.save_button.setVisible(False)
        self.cancel_edit_button.setVisible(False)
        if not note_path:
            self.note_state = None
            message = item.message if item is not None and item.message else ""
            self.state_label.setText(message or "No note.")
            self._set_badge(LIGHT_WORDS[folder_light(None, False)], LIGHT_BADGE)
            self._show_text("", NO_NOTE)
            self.edit_button.setVisible(False)
            self.open_button.setVisible(False)
            self.sources_label.setText("")
            return
        state = note_status(note_path)
        self.note_state = state
        written = item is not None and item.written_path and os.path.normcase(item.written_path) == os.path.normcase(note_path)
        words = f"{os.path.basename(note_path)}: {STATE_WORDS.get(state.kind, state.kind)}"
        self.state_label.setText(words + ("  (written just now)" if written else ""))
        self._set_badge(LIGHT_WORDS[folder_light(state.kind, False)], LIGHT_BADGE)
        self._show_text(state.text, "*The note could not be read as text.* " + escape(state.message))
        self.edit_button.setVisible(bool(state.text))
        self.open_button.setVisible(True)
        self.sources_label.setText("")

    # -- editing (card 7, B) -----------------------------------------------------------------------------------------

    def can_edit(self) -> bool:
        """A note on disk is shown (not a draft) and it reads as text."""
        return not self._editing and self.note_state is not None and bool(self.note_state.text)

    def is_editing(self) -> bool:
        return self._editing

    def is_modified(self) -> bool:
        return self._editing and self.note_state is not None and self.raw.toPlainText() != self.note_state.text

    def start_edit(self) -> None:
        if not self.can_edit():
            return
        self._editing = True
        self.set_view(VIEW_RAW)
        self.raw.setReadOnly(False)
        self.raw.setFocus()
        for b in self.view_buttons:
            b.setEnabled(b is self.view_buttons[VIEW_RAW])
        self.edit_button.setVisible(False)
        self.save_button.setVisible(True)
        self.cancel_edit_button.setVisible(True)
        self.editStarted.emit()

    def cancel_edit(self) -> None:
        if not self._editing:
            return
        self._editing = False
        self.raw.setReadOnly(True)
        self.raw.setPlainText(self.note_state.text if self.note_state is not None else "")
        self.view_buttons[VIEW_PREVIEW].setEnabled(True)
        self.view_buttons[VIEW_RAW].setEnabled(True)
        self.save_button.setVisible(False)
        self.cancel_edit_button.setVisible(False)
        self.edit_button.setVisible(self.note_state is not None and bool(self.note_state.text))

    def end_edit(self) -> None:
        """After a successful save: the window shows the folder again."""
        self._editing = False
        self.raw.setReadOnly(True)
        for b in self.view_buttons[:2]:
            b.setEnabled(True)


def _match_summary(item: ReviewItem) -> str:
    p = item.proposal
    if p.writable:
        source = ", ".join(p.sources[:2]) if p.sources else ""
        return (f"{p.title or p.folder.name}" + (f"  ({source})" if source else "")
                + ("  - chosen by you" if item.user_resolved else ""))
    if p.confidence == Confidence.UNCERTAIN:
        n = len(p.candidates)
        return f"{n} candidate{'s' if n != 1 else ''}: pick the right one"
    return "Nothing found online"
