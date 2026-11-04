"""
gui/main_window.py

The \u2132older Redactor's window. This is the skeleton (plan step 4): the family's menu skeleton with every menu of
the plan in place, File > Open Library Folder / Recent, a folder dropped on the window, Tools > API Keys / History /
Preferences, and Help. The two jobs' entries (Notes, Clean Up) are shown greyed until their steps land: disable,
never hide.

Menus (plan section 4): File (Open Library Folder, Recent, Exit), Edit (Undo), View (Command Palette), Notes (Create
Notes, Refresh Old Notes, Switch View), Clean Up (Check Folder Tree, Open Check Report, Apply Decisions), Tools
(Preferences, API Keys, Clear Lookup Cache, History), Help. Ctrl+K opens the command palette.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QFileDialog, QLabel, QMainWindow, QMenu, QMessageBox, QStatusBar, QVBoxLayout, QWidget,
)

from core import app_paths, history, settings
from core.app_paths import asset_path
from core.version import APP_NAME, APP_REPO_URL, APP_VERSION, RELEASE_LABEL
from redactor_common.core import labels
from redactor_common.core.version import REDACTOR_COMMON_REPO_URL, REDACTOR_COMMON_VERSION
from redactor_common.gui import standard_shortcuts as keys
from redactor_common.gui.about_dialog import AboutDialog, ChangelogDialog, CreditsDialog
from redactor_common.gui.command_palette import add_command_palette
from redactor_common.gui.history_dialog import HistoryDialog
from redactor_common.gui.menu_builder import MenuAction, Separator, Submenu
from redactor_common.gui.standard_menus import (
    KEY_COMMAND_PALETTE, KEY_EXIT, AppMenu, StandardMenuSpec, build_standard_menu_bar, get_action_registry,
    standard_help_items, standard_tools_items,
)
from redactor_common.gui.update_controller import UpdateController

PROJECT_ROOT = app_paths.PROJECT_ROOT
ICON_PATH = asset_path("assets/icon.ico")
ABOUT_PATH = PROJECT_ROOT / "ABOUT.md"
CHANGELOG_PATH = PROJECT_ROOT / "CHANGELOG.md"
CREDITS_PATH = PROJECT_ROOT / "CREDITS.md"

MENU_NOTES = "&Notes"
MENU_CLEAN_UP = "&Clean Up"
NOT_YET = "Not built yet: comes with a later step of the plan"

INTRO = (
    "Open a library folder (File > Open Library Folder, or drop a folder on this window).\n\n"
    "Notes: drafts the Markdown folder notes Pluteus shows (artist.md, album.md, series.md, about.md), and writes "
    "only the ones you say yes to.\n"
    "Clean Up: checks a library's folder tree against its conventions and renames only what you say yes to.\n\n"
    "Into a library this program writes .md folder notes and nothing else."
)


class MainWindow(QMainWindow):
    def __init__(self, initial_folder: Optional[str] = None):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} ({APP_VERSION})")
        self.resize(900, 560)
        if ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(ICON_PATH)))
        self.setAcceptDrops(True)
        self.library_folder: str = ""

        self._build_ui()
        self.updates = UpdateController(self, APP_NAME, APP_VERSION, APP_REPO_URL, app_paths.updates_json_path())
        self._build_menu_bar()
        self.updates.start_auto_check()  # nothing unless switched on in Preferences
        if initial_folder:
            self.open_library_folder(initial_folder)

    # --- layout -------------------------------------------------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        layout = QVBoxLayout(central)
        self.folder_label = QLabel("No library folder open.")
        self.folder_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        font = self.folder_label.font()
        font.setBold(True)
        self.folder_label.setFont(font)
        layout.addWidget(self.folder_label)
        self.intro_label = QLabel(INTRO)
        self.intro_label.setWordWrap(True)
        self.intro_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.intro_label, 1)
        self.setCentralWidget(central)
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

    def _build_menu_bar(self) -> None:
        """The family's standard menu skeleton (redactor_common.gui.standard_menus) with this app's two menus,
        Notes and Clean Up, between View and Tools."""
        def later(key: str, text: str, tooltip: str) -> MenuAction:
            return MenuAction(key, text, self._not_yet, tooltip=f"{tooltip}. {NOT_YET}.", enabled=False)

        self.recent_menu_spec = Submenu("&Recent", [])
        spec = StandardMenuSpec(
            file=[
                # Ctrl+Shift+O is the family's Open Folder; the label says which folder (see the menu test's
                # DOCUMENTED_LINT_EXCEPTIONS).
                MenuAction("open_library_folder", "&Open Library Folder…", self._on_open_library_folder,
                           shortcut=keys.OPEN_FOLDER, keywords="open folder library"),
                self.recent_menu_spec,
                Separator(),
                MenuAction(KEY_EXIT, labels.EXIT, self.close),
            ],
            edit=[
                MenuAction("undo", labels.UNDO, self._not_yet, shortcut=keys.UNDO, enabled=False,
                           tooltip=f"Undo the last note written or folder renamed. {NOT_YET}."),
            ],
            view=[
                MenuAction(KEY_COMMAND_PALETTE, labels.COMMAND_PALETTE, self._not_yet,
                           shortcut=keys.COMMAND_PALETTE, keywords="search commands actions"),
            ],
            app_menus=[
                AppMenu(MENU_NOTES, [
                    later("create_notes", "&Create Notes…", "Draft the folder notes for the open library"),
                    later("refresh_old_notes", "&Refresh Old Notes…", "Draft a new version of notes already written"),
                    Separator(),
                    later("switch_view", "&Switch View", "Between one note at a time and the list with ticks"),
                ]),
                AppMenu(MENU_CLEAN_UP, [
                    later("check_folder_tree", "&Check Folder Tree…",
                          "Check the library's folder tree against its conventions (read-only)"),
                    later("open_check_report", "&Open Check Report…", "Open a report made here or on the server"),
                    Separator(),
                    later("apply_decisions", "&Apply Decisions…", "Rename what you said yes to (a dry run first)"),
                ]),
            ],
            tools=standard_tools_items(
                preferences=self._on_open_preferences,
                api_keys=self._on_open_api_keys,
                app_settings=[later("clear_lookup_cache", "&Clear Lookup Cache", "Forget the saved lookup replies")],
                history=self._on_open_history,
            ),
            help=standard_help_items(
                APP_NAME, self._on_show_changelog, self._on_show_credits, self._on_show_about,
                updates_slot=self.updates.check_now,
            ),
        )
        menus = build_standard_menu_bar(self, spec)
        self.actions_by_key = get_action_registry(self)
        self.menus = menus
        add_command_palette(self, self.actions_by_key)
        self.recent_menu = self._find_submenu(menus["File"], "Recent")
        self.recent_menu.aboutToShow.connect(self._fill_recent_menu)
        self._fill_recent_menu()

    @staticmethod
    def _find_submenu(menu: QMenu, plain_title: str) -> QMenu:
        for action in menu.actions():
            sub = action.menu()
            if sub is not None and labels.plain_label(action.text()) == plain_title:
                return sub
        raise LookupError(plain_title)

    def _fill_recent_menu(self) -> None:
        """File > Recent: the library folders opened last, newest first, then Clear Recent."""
        self.recent_menu.clear()
        folders = settings.recent_folders()
        for index, folder in enumerate(folders, 1):
            mnemonic = f"&{index % 10} " if index <= 10 else ""
            action = self.recent_menu.addAction(mnemonic + folder.replace("&", "&&"))  # '&' in a path is no mnemonic
            action.triggered.connect(lambda _checked=False, f=folder: self.open_library_folder(f))
        if not folders:
            self.recent_menu.addAction("No recent folders").setEnabled(False)
        self.recent_menu.addSeparator()
        clear = self.recent_menu.addAction("&Clear Recent")
        clear.setEnabled(bool(folders))
        clear.triggered.connect(self._on_clear_recent)

    # --- File -----------------------------------------------------------------------------------------------------

    def _on_open_library_folder(self) -> None:
        start = self.library_folder or (settings.recent_folders() or [""])[0]
        folder = QFileDialog.getExistingDirectory(self, "Open Library Folder", start)
        if folder:
            self.open_library_folder(folder)

    def open_library_folder(self, folder: str) -> bool:
        """Makes `folder` the open library (File > Open Library Folder, File > Recent, a folder dropped on the
        window or given on the command line). Reads nothing in it yet: the media-type guess and the jobs come with
        later steps."""
        folder = os.path.normpath(folder)
        if not os.path.isdir(folder):
            self.status_bar.showMessage(f"Not a folder: {folder}")
            return False
        self.library_folder = folder
        self.folder_label.setText(f"Library folder: {folder}")
        settings.add_recent_folder(folder)
        self.status_bar.showMessage(f"Opened {folder}")
        return True

    def _on_clear_recent(self) -> None:
        settings.clear_recent_folders()
        self._fill_recent_menu()

    def dragEnterEvent(self, event) -> None:  # noqa: N802 -- Qt override
        if self._dropped_folder(event) is not None:
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802 -- Qt override
        folder = self._dropped_folder(event)
        if folder is not None:
            event.acceptProposedAction()
            self.open_library_folder(folder)

    @staticmethod
    def _dropped_folder(event) -> Optional[str]:
        """The one folder being dragged in, else None (files and several folders are not a library)."""
        mime = event.mimeData()
        if mime is None or not mime.hasUrls():
            return None
        paths = [url.toLocalFile() for url in mime.urls() if url.isLocalFile()]
        return paths[0] if len(paths) == 1 and os.path.isdir(paths[0]) else None

    def _not_yet(self) -> None:
        self.status_bar.showMessage(NOT_YET)

    # --- Tools ----------------------------------------------------------------------------------------------------

    def _on_open_preferences(self) -> None:
        from gui.preferences_dialog import PreferencesDialog

        PreferencesDialog(self).exec()

    def _on_open_api_keys(self) -> None:
        from gui.api_keys_dialog import ApiKeysDialog

        ApiKeysDialog(self).exec()

    def _on_open_history(self) -> None:
        """Tools > History: what this program wrote (notes, and later renames), each with its undo. Opt-in: with
        nothing recorded yet, offer to turn recording on first."""
        enabled = history.history_enabled()
        if not enabled and not history.journal_exists():
            answer = QMessageBox.question(
                self, "History",
                "History is off. Turn it on? From then on, the notes this program writes are recorded here, so "
                "they can be undone. Nothing has been recorded so far.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            history.set_history_enabled(True)
            enabled = True
        title = "History" if enabled else "History (recording is off)"
        HistoryDialog(history.get_journal(), history.apply_restore, self, title,
                      undo_handlers=history.note_undo_handlers()).exec()

    # --- Help -----------------------------------------------------------------------------------------------------

    def _on_show_about(self) -> None:
        AboutDialog(
            app_name=APP_NAME,
            app_version=APP_VERSION,
            release_label=RELEASE_LABEL,
            icon_path=str(ICON_PATH),
            about_path=str(ABOUT_PATH),
            component_versions={"redactor_common": REDACTOR_COMMON_VERSION},
            repo_url=APP_REPO_URL,
            component_repo_urls={"redactor_common": REDACTOR_COMMON_REPO_URL},
            parent=self,
        ).exec()

    def _on_show_changelog(self) -> None:
        ChangelogDialog(str(CHANGELOG_PATH), parent=self).exec()

    def _on_show_credits(self) -> None:
        CreditsDialog(str(CREDITS_PATH), parent=self).exec()


def folder_from_argv(argv: list[str]) -> Optional[str]:
    """A folder given on the command line (`folderredactor.exe D:/Music`), else None."""
    candidates = [a for a in argv[1:] if not a.startswith("-")]
    return candidates[0] if len(candidates) == 1 and Path(candidates[0]).is_dir() else None
