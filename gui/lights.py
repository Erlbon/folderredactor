"""
gui/lights.py

The note light of a folder in the library tree (window review 2026-11-10, card 1, Erlend's pick B): told apart by shape as
well as colour, and never red (a folder without a note is not an error).

  ●  green        a current note (also a note not made by this program: there is one, Pluteus shows it)
  ◐  amber        a draft waiting for a decision (confident, uncertain or nothing found), or an outdated note of ours
  ✎  green        a note a person edited
  ○  hollow grey  no note

  folder_light(note_state, has_draft)   which light a folder gets
  light_icon(light)                     its QIcon (painted once, cached)
  LIGHT_WORDS                           what the note pane's header says for it
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QIcon, QPainter, QPen, QPixmap

from redactor_common.core.notes import STATE_CURRENT, STATE_EDITED, STATE_FOREIGN, STATE_LEGACY, STATE_OUTDATED

LIGHT_NONE = "none"
LIGHT_NOTE = "note"
LIGHT_WAITING = "waiting"
LIGHT_EDITED = "edited"
LIGHT_PLAIN = ""  # an alphabet grouping folder (A, B-C, 0-9): no light at all

GREEN = "#2e9d4f"
AMBER = "#d99a1e"
GREY = "#8a8a8a"

LIGHT_WORDS = {
    LIGHT_NONE: "No note",
    LIGHT_NOTE: "Note",
    LIGHT_WAITING: "Waiting for you",
    LIGHT_EDITED: "Note edited by you",
    LIGHT_PLAIN: "",
}

STATE_WORDS = {
    STATE_CURRENT: "current note",
    STATE_OUTDATED: "outdated note (made by an older version)",
    STATE_LEGACY: "note made by the first versions",
    STATE_EDITED: "edited by you",
    STATE_FOREIGN: "not made by this program",
}


def folder_light(note_state: Optional[str], has_draft: bool) -> str:
    """`note_state` is the redactor_common STATE_* of the folder's note (None: no note); `has_draft` is a draft waiting."""
    if has_draft or note_state in (STATE_OUTDATED, STATE_LEGACY):
        return LIGHT_WAITING
    if note_state == STATE_EDITED:
        return LIGHT_EDITED
    if note_state in (STATE_CURRENT, STATE_FOREIGN):
        return LIGHT_NOTE
    return LIGHT_NONE


_ICONS: dict[str, QIcon] = {}
SIZE = 16


def _paint(light: str) -> QPixmap:
    pixmap = QPixmap(SIZE, SIZE)
    pixmap.fill(Qt.GlobalColor.transparent)
    if light == LIGHT_PLAIN:
        return pixmap
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    box = QRectF(3, 3, SIZE - 6, SIZE - 6)
    if light == LIGHT_NOTE:
        p.setPen(QPen(QColor(GREEN), 1.2))
        p.setBrush(QBrush(QColor(GREEN)))
        p.drawEllipse(box)
    elif light == LIGHT_NONE:
        p.setPen(QPen(QColor(GREY), 1.4))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(box)
    elif light == LIGHT_WAITING:
        p.setPen(QPen(QColor(AMBER), 1.4))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(box)
        p.setBrush(QBrush(QColor(AMBER)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPie(box, 90 * 16, 180 * 16)  # the left half filled
    elif light == LIGHT_EDITED:
        font = QFont()
        font.setPixelSize(SIZE - 1)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor(GREEN))
        p.drawText(QRectF(0, 0, SIZE, SIZE), Qt.AlignmentFlag.AlignCenter, "✎")  # Qt falls back to a font that has it
    p.end()
    return pixmap


def light_icon(light: str) -> QIcon:
    icon = _ICONS.get(light)
    if icon is None:
        icon = _ICONS[light] = QIcon(_paint(light))
    return icon
