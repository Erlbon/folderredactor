"""
gui/main_window.py

The \u2132older Redactor's window: the family's menu skeleton with every menu of the plan in place, File > Open
Library Folder / Recent, a folder dropped on the window, Notes > Create Notes (music or video, guessed from the library:
gui/music_notes.py, gui/video_notes.py), Tools > API Keys / Clear Lookup Cache / History / Preferences, and Help. The entries
whose steps have not landed yet are shown greyed: disable, never hide.

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

from core import app_paths, history, notes_settings, settings
from core.app_paths import asset_path
from core.video import settings as video_settings
from core.version import APP_NAME, APP_REPO_URL, APP_VERSION, RELEASE_LABEL
from redactor_common.core import labels
from redactor_common.core.version import REDACTOR_COMMON_REPO_URL, REDACTOR_COMMON_VERSION
from redactor_common.gui import standard_shortcuts as keys
from redactor_common.gui.about_dialog import AboutDialog, ChangelogDialog, CreditsDialog
from redactor_common.gui.command_palette import add_command_palette
from redactor_common.gui.history_dialog import HistoryDialog
from redactor_common.gui.menu_builder import MenuAction, Separator, Submenu
from redactor_common.gui.progress import run_busy
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
        self.library_media: str = ""  # 'music' / 'video' / '' (cannot tell), guessed when the library is opened
        self.notes_fetchers = None  # Create Notes: a callable returning core.video.flow.Fetchers (None = the real services; tests inject)

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
                MenuAction("import_old_apps", "&Import from mp3redactor or videoredactor…", self._on_import_old_apps,
                           tooltip="Take over the notes settings, the saved lookup answers and the API keys of the "
                                   "ɯP3 or Ʌideo Redactor (point at the folder its program is in)",
                           keywords="import mp3redactor videoredactor settings cache keys"),
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
                    MenuAction("create_notes", "&Create Notes…", self._on_create_notes,
                               tooltip="Draft the folder notes of a music library (artist.md, album.md, about.md) or a "
                                       "video library (series.md, about.md) and write the ones you say yes to.",
                               keywords="notes artist album genre series film movie about musicbrainz discogs tmdb wikipedia"),
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
                app_settings=[MenuAction("clear_lookup_cache", "&Clear Lookup Cache", self._on_clear_lookup_cache,
                                         tooltip="Forget the saved lookup replies, so the next run asks TMDB and "
                                                 "Wikipedia again")],
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
        from core.media_guess import guess_media

        self.library_folder = folder
        # a bounded look at the file names (at most a few thousand); on a share it can take a moment: never silently
        self.library_media = run_busy(self, "Looking at the library's files…", guess_media, folder, title=APP_NAME)
        kind = {"music": "a music library", "video": "a video library"}.get(self.library_media, "music or video: cannot tell")
        self.folder_label.setText(f"Library folder: {folder}  ({kind})")
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

    # --- Notes ----------------------------------------------------------------------------------------------------

    def notes_media(self) -> str:
        """'music' or 'video' for Notes > Create Notes: guessed from the open library (else the last notes folder) by
        its file names; too close to call, the kind used last time; never used before, asked. '' = the person cancelled."""
        from core.media_guess import guess_media

        if self.library_folder:
            media = self.library_media  # guessed when the library was opened
        else:
            start = notes_settings.last_folder()
            media = guess_media(start) if start else ""
        return media or notes_settings.last_media() or self._ask_media()

    def _ask_media(self) -> str:
        box = QMessageBox(QMessageBox.Icon.Question, "Create Notes",
                          "Is this a music library or a video library? (Open the library folder first and this is "
                          "worked out from its files.)", QMessageBox.StandardButton.Cancel, self)
        music = box.addButton("Music", QMessageBox.ButtonRole.AcceptRole)
        video = box.addButton("Video", QMessageBox.ButtonRole.AcceptRole)
        box.exec()
        clicked = box.clickedButton()
        box.deleteLater()
        return "music" if clicked is music else "video" if clicked is video else ""

    def _on_create_notes(self) -> None:
        """Notes > Create Notes...: music or video first (notes_media), then ALWAYS which folder, as a short list (the
        library folder you opened, one level up, the last notes folder, Another folder...). The review page is
        redactor_common's, run by gui/music_notes.py or gui/video_notes.py."""
        from gui import music_notes, video_notes
        from core.music import settings as music_settings
        from redactor_common.core.notes_scope import merge_choices

        media = self.notes_media()
        if not media:
            return
        hook, kind_settings = (music_notes, music_settings) if media == "music" else (video_notes, video_settings)
        choices = merge_choices(video_notes.scope_candidates([], [], self.library_folder, notes_settings.last_folder()))
        folder, kinds, outdated = hook.scope_question(
            self, choices, notes_settings.include_subfolders(), notes_settings.set_include_subfolders,
            notes_settings.last_folder() or self.library_folder, kind_settings.kinds_text(kind_settings.kinds()))
        if not folder:
            return
        notes_settings.set_last_folder(folder)
        notes_settings.set_last_media(media)
        kind_settings.set_kinds(kinds)
        self._run_create_notes(media, [folder], notes_settings.include_subfolders(), kind_settings.parse_kinds(kinds),
                               outdated)

    def _run_create_notes(self, media: str, paths: list, include_subfolders: bool, kinds: tuple,
                          include_outdated: bool = False) -> None:
        if media == "music":
            from core.music.flow import live_fetchers
            from gui.music_notes import create_notes
        else:
            from core.video.flow import live_fetchers
            from gui.video_notes import create_notes

        create_notes(
            self, paths, include_subfolders, self.notes_fetchers or live_fetchers,
            size_text=notes_settings.dialog_size(), on_size=notes_settings.set_dialog_size, kinds=kinds,
            cache=notes_settings.default_cache(), include_outdated=include_outdated)

    # --- the old apps ---------------------------------------------------------------------------------------------

    def _on_import_old_apps(self) -> None:
        """File > Import from mp3redactor or videoredactor...: the folder the old program is in (its settings file and
        lookup cache sit next to it); then the API keys it has that this program does not."""
        from core import old_apps

        folder = QFileDialog.getExistingDirectory(
            self, "Import: the folder mp3redactor.exe or videoredactor.exe is in", self.library_folder)
        if folder:
            if not old_apps.detect(folder):
                QMessageBox.information(self, "Import", f"No mp3redactor or videoredactor settings or lookup cache in "
                                                        f"{folder}. Pick the folder its program is in.")
            else:
                lines = run_busy(self, "Importing…", old_apps.import_folder, folder, title="Import")
                QMessageBox.information(self, "Import", "\n".join(lines))
        self.offer_old_keys(asked_by_person=True)

    def offer_old_keys(self, asked_by_person: bool = False) -> None:
        """The Discogs token / TMDB key of the old apps, by their names in the credential store: offered, never copied
        silently. At start-up only once ([keys] import_offered); from the File menu every time."""
        from core import old_apps

        if not asked_by_person and settings.get_setting("keys", "import_offered", "") == "1":
            return
        found = old_apps.found_keys()
        if not asked_by_person:
            settings.set_setting("keys", "import_offered", "1")
        if not found:
            if asked_by_person:
                self.status_bar.showMessage("No API keys of mp3redactor or videoredactor to copy (or this program has them).")
            return
        names = "\n".join(f"  {k.label} from {k.app}" for k in found)
        answer = QMessageBox.question(
            self, "API keys", f"Copy these keys into this program (Tools > API Keys)?\n\n{names}\n\nThey stay in the "
                              "other programs too.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        problems = old_apps.copy_keys(found)
        if problems:
            QMessageBox.warning(self, "API keys", "Not copied:\n" + "\n".join(problems))
        else:
            self.status_bar.showMessage(f"{len(found)} key(s) copied.")

    # --- Tools ----------------------------------------------------------------------------------------------------

    def _on_open_preferences(self) -> None:
        from gui.preferences_dialog import PreferencesDialog

        PreferencesDialog(self).exec()

    def _on_open_api_keys(self) -> None:
        from gui.api_keys_dialog import ApiKeysDialog

        ApiKeysDialog(self).exec()

    def _on_clear_lookup_cache(self) -> None:
        removed = notes_settings.clear_cache()
        QMessageBox.information(
            self, "Clear Lookup Cache",
            "The lookup cache was already empty." if not removed
            else f"{removed} saved answer{'' if removed == 1 else 's'} removed. The next run asks the services again.")

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


def start_window(initial_folder: Optional[str] = None) -> MainWindow:
    """The window the program starts with: once it is up, the old apps' API keys are offered (once, never silently)."""
    from PyQt6.QtCore import QTimer

    window = MainWindow(initial_folder)
    QTimer.singleShot(0, window.offer_old_keys)
    return window


def folder_from_argv(argv: list[str]) -> Optional[str]:
    """A folder given on the command line (`folderredactor.exe D:/Music`), else None."""
    candidates = [a for a in argv[1:] if not a.startswith("-")]
    return candidates[0] if len(candidates) == 1 and Path(candidates[0]).is_dir() else None
