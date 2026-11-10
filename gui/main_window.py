"""
gui/main_window.py

The \u2132older Redactor's window (window review 2026-11-10, docs/ui-review-2026-11-10.md): the notes are the program, so
there is no separate notes window. The library's folders are a tree on the left, each with its note light (gui/lights.py),
with the Local files of the selected folder under it (music); the note pane on the right is always open
(gui/note_pane.py). Look Up runs on the selected folder in the background (gui/lookup_worker.py): each draft lands in the
tree as it is ready, and can be judged while the rest are looked up. Drafts are ticked in the tree and written with one
button; Enter in the tree writes the selected one and moves on.

Menus (the family's skeleton): File (Open Library Folder, Recent, Import, Exit), Edit (Undo), View (Command Palette, Folder
Panel, Preview / Raw / Before-after), Notes (Look Up, Look Up Options, Cancel Look Up, Write Ticked Notes, Write This Note,
Next Waiting Folder, Tick All Confident, Tick Best Guesses, Untick All, Edit Note), Tools (Preferences, API Keys, Clear
Lookup Cache, History), Help. Ctrl+K opens the command palette.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Callable, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QMainWindow, QMenu, QMessageBox, QPushButton, QSplitter, QStatusBar, QVBoxLayout,
    QWidget,
)

from core import app_paths, history, notes_settings, settings
from core.app_paths import asset_path
from core.version import APP_NAME, APP_REPO_URL, APP_VERSION, RELEASE_LABEL
from gui.library_tree import LibraryTree, path_key
from gui.lookup_worker import MUSIC, VIDEO, LookupWorker
from gui.note_pane import VIEW_DIFF, VIEW_PREVIEW, VIEW_RAW, MatchStrip, NotePane
from redactor_common.core import labels
from redactor_common.core.notes_review import PENDING, STATE_WORDS, WRITTEN, ReviewItem, ReviewSession
from redactor_common.core.notes import STATE_LEGACY
from redactor_common.core.version import REDACTOR_COMMON_REPO_URL, REDACTOR_COMMON_VERSION
from redactor_common.gui import standard_shortcuts as keys
from redactor_common.gui.about_dialog import AboutDialog, ChangelogDialog, CreditsDialog
from redactor_common.gui.command_palette import add_command_palette
from redactor_common.gui.history_dialog import HistoryDialog
from redactor_common.gui.menu_builder import MenuAction, Separator, Submenu
from redactor_common.gui.notes_review_dialog import open_in_system
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
LOOK_UP_KEY = "Ctrl+L"
WRITE_TICKED_KEY = keys.APPLY  # Ctrl+Return
NEXT_WAITING_KEY = "F8"
EDIT_NOTE_KEY = "F4"
VIEW_KEYS = ("Ctrl+1", "Ctrl+2", "Ctrl+3")
UPDATE_QUESTION = "Replace {n} made by an older version?\n\n{recycle}"


class _EngineStandIn:
    """What the review controls call on 'the engine' (best_guess, why_cannot_choose, can_choose): the lookup thread's
    engine of the media type, found when it is called (it is made with the first Look Up)."""

    def __init__(self, worker: LookupWorker, media: str):
        self._worker, self._media = worker, media

    def __getattr__(self, name: str):
        engine = self._worker.engine(self._media)
        if engine is None:
            raise AttributeError(name)
        return getattr(engine, name)

    def can_choose(self, proposal, candidate) -> bool:
        engine = self._worker.engine(self._media)
        return engine.can_choose(proposal, candidate) if engine is not None else False


class FolderPanel(QWidget):
    """Under the tree: the Local files of the selected music folder (cover, albums, tracks, tags), read in the background
    (gui/music_evidence_view.py). Whether a folder is an artist or an album folder is worked out off the GUI thread too."""

    _kind_found = pyqtSignal(str, str, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        from gui.music_evidence_view import LocalEvidenceView

        self.view = LocalEvidenceView()
        self.caption = QLabel("Local files")
        font = self.caption.font()
        font.setBold(True)
        self.caption.setFont(font)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.addWidget(self.caption)
        layout.addWidget(self.view, 1)
        self._token = 0
        self._kind_found.connect(self._show)

    def show_folder(self, folder: str, media: str) -> None:
        self._token += 1
        token = self._token
        self.view.clear()
        if not folder:
            return
        if media == VIDEO:
            self.view.status.setText("Local files are shown for music folders.")
            return

        def work() -> None:
            from core.music.local import classify  # noqa: PLC0415

            try:
                kind = classify(Path(folder))
            except OSError:
                kind = ""
            try:
                self._kind_found.emit(folder, kind, token)
            except RuntimeError:  # the window was closed meanwhile
                pass

        self.view.status.setText("Reading the files ...")
        threading.Thread(target=work, name="folder-kind", daemon=True).start()

    def _show(self, folder: str, kind: str, token: int) -> None:
        if token != self._token:
            return
        if not kind:
            self.view.clear()
            self.view.status.setText("No album or artist folder here.")
            return
        self.view.show_folder(Path(folder), kind)


class MainWindow(QMainWindow):
    def __init__(self, initial_folder: Optional[str] = None):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} ({APP_VERSION})")
        self.resize(1200, 760)
        if ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(ICON_PATH)))
        self.setAcceptDrops(True)
        self.library_folder: str = ""
        self.library_media: str = ""  # 'music' / 'video' / '' (cannot tell), guessed when the library is opened
        self.notes_fetchers = None  # a callable returning the media type's Fetchers (None = the real services; tests inject)
        self.open_path: Callable[[str], None] = open_in_system  # tests replace it
        self.session = ReviewSession([], write_fn=self._write_proposal)
        self._index: dict[str, int] = {}  # folder key -> index in session.items
        self._media_of: dict[str, str] = {}  # folder key -> the media type whose engine built the draft
        self._rebuilding: set[str] = set()  # folder keys with a rebuild on the way
        self._written: list[str] = []  # the notes written or saved since the window opened, newest last (Edit > Undo)
        self._shown = ""  # the folder the pane shows
        self._lookup_running = 0  # the Look Up job in hand (0: none)

        self.worker = LookupWorker(self._make_engine, self)
        from core.music.link import LinkError  # noqa: PLC0415

        self.worker.link_errors = (LinkError, ValueError)
        self._connect_worker()
        self.worker.start()

        self._build_ui()
        self.updates = UpdateController(self, APP_NAME, APP_VERSION, APP_REPO_URL, app_paths.updates_json_path())
        self._build_menu_bar()
        self.updates.start_auto_check()  # nothing unless switched on in Preferences
        self._update_buttons()
        if initial_folder:
            self.open_library_folder(initial_folder)

    # --- layout -------------------------------------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.tree = LibraryTree()
        self.tree.folderSelected.connect(self._on_folder_selected)
        self.tree.tickToggled.connect(self._on_tick)
        self.tree.stateRead.connect(self._on_state_read)
        self.tree.installEventFilter(self)
        self.folder_panel = FolderPanel()
        self.folder_panel_on = settings.get_setting("view", "folder_panel", "1") == "1"
        self.folder_panel.setVisible(self.folder_panel_on)
        left = QSplitter(Qt.Orientation.Vertical)
        left.addWidget(self.tree)
        left.addWidget(self.folder_panel)
        left.setStretchFactor(0, 3)
        left.setStretchFactor(1, 1)
        left.setSizes([480, 200])

        self.pane = NotePane()
        self.pane.saveRequested.connect(self._save_edit)
        self.pane.openNoteRequested.connect(self._open_note)
        self.pane.showFolderRequested.connect(lambda: self._shown and self.open_path(self._shown))
        self.strips: dict[str, MatchStrip] = {}

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.addWidget(left)
        self.splitter.addWidget(self.pane)
        self.splitter.setStretchFactor(0, 2)
        self.splitter.setStretchFactor(1, 3)
        self.splitter.setSizes([440, 760])

        self.progress_label = QLabel("")
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setAutoDefault(False)
        self.cancel_button.clicked.connect(self._on_cancel_look_up)
        self.ticked_label = QLabel("")
        self.look_up_button = QPushButton("Look Up")
        self.look_up_button.setToolTip(f"Look up the selected folder ({LOOK_UP_KEY}); Notes > Look Up Options says what")
        self.look_up_button.clicked.connect(self._on_look_up)
        self.write_button = QPushButton("Write ticked notes")
        self.write_button.clicked.connect(self._on_write_ticked)
        for b in (self.look_up_button, self.write_button):
            b.setAutoDefault(False)
        bottom = QHBoxLayout()
        bottom.addWidget(self.progress_label, 1)
        bottom.addWidget(self.cancel_button)
        bottom.addSpacing(24)
        bottom.addWidget(self.ticked_label)
        bottom.addWidget(self.look_up_button)
        bottom.addWidget(self.write_button)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(self.splitter, 1)
        layout.addLayout(bottom)
        self.setCentralWidget(central)
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

    def _build_menu_bar(self) -> None:
        """The family's standard menu skeleton (redactor_common.gui.standard_menus) with this app's one menu, Notes,
        between View and Tools."""
        from gui import music_notes, video_notes  # noqa: PLC0415

        self.recent_menu_spec = Submenu("&Recent", [])
        self.kind_actions: dict[tuple[str, str], str] = {}  # (media, kind) -> action key
        option_items: list = [
            MenuAction("look_up_below", "This Folder and &Below", self._on_options_changed, checkable=True,
                       tooltip="Look up the folders below the selected one too (off: only the selected folder, as what it "
                               "is)"),
            Separator(),
        ]
        for media, checks in ((MUSIC, music_notes.KIND_CHECKS), (VIDEO, video_notes.KIND_CHECKS)):
            for kind, label in checks:
                key = f"look_up_{media}_{kind}"
                self.kind_actions[(media, kind)] = key
                option_items.append(MenuAction(key, label, self._on_options_changed, checkable=True,
                                               tooltip=f"With This Folder and Below: look up {kind} folders"))
            option_items.append(Separator())
        option_items.append(MenuAction(
            "look_up_outdated", "Also &Refresh Outdated Notes", self._on_options_changed, checkable=True,
            tooltip="Notes made by an older version of this program get a new draft (never ticked by itself; the old note "
                    "goes to the Recycle Bin when you write it)"))
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
                MenuAction("undo", labels.UNDO, self._on_undo, shortcut=keys.UNDO,
                           tooltip="Undo the last note written or saved here (needs Tools > History switched on)"),
            ],
            view=[
                MenuAction(KEY_COMMAND_PALETTE, labels.COMMAND_PALETTE, lambda: None,
                           shortcut=keys.COMMAND_PALETTE, keywords="search commands actions"),
                Separator(),
                MenuAction("folder_panel", "&Folder Panel", self._on_toggle_folder_panel, checkable=True,
                           tooltip="The Local files of the selected folder under the tree (music)"),
                Separator(),
                MenuAction("view_preview", "Pre&view", lambda: self._set_view(VIEW_PREVIEW), shortcut=VIEW_KEYS[0]),
                MenuAction("view_raw", "&Raw Text", lambda: self._set_view(VIEW_RAW), shortcut=VIEW_KEYS[1]),
                MenuAction("view_diff", "&Before / After", lambda: self._set_view(VIEW_DIFF), shortcut=VIEW_KEYS[2]),
            ],
            app_menus=[
                AppMenu(MENU_NOTES, [
                    MenuAction("look_up", "&Look Up", self._on_look_up, shortcut=LOOK_UP_KEY,
                               tooltip="Draft the notes of the selected folder (and below, if ticked under Look Up "
                                       "Options) from MusicBrainz, Discogs, TMDB and Wikipedia; nothing is written",
                               keywords="create notes artist album genre series film movie about musicbrainz discogs tmdb "
                                        "wikipedia"),
                    Submenu("Look Up &Options", option_items),
                    MenuAction("cancel_look_up", "&Cancel Look Up", self._on_cancel_look_up,
                               tooltip="Stop after the folder in hand; the drafts so far stay"),
                    Separator(),
                    MenuAction("write_ticked", "&Write Ticked Notes", self._on_write_ticked, shortcut=WRITE_TICKED_KEY),
                    MenuAction("write_this", "Write T&his Note", self._on_write_this,
                               tooltip="The selected folder's draft (Enter in the tree), then the next folder waiting"),
                    MenuAction("next_waiting", "&Next Waiting Folder", self._on_next_waiting, shortcut=NEXT_WAITING_KEY,
                               tooltip="The next folder with a draft waiting for you"),
                    Separator(),
                    MenuAction("tick_confident", "Tick &All Confident", self._on_tick_confident),
                    MenuAction("tick_guesses", "Tick Best &Guesses", self._on_tick_guesses,
                               tooltip="Uncertain matches that have a candidate and a clear level: use the top candidate "
                                       "and tick them. RISK: the match was not confirmed by what is in your folders, so a "
                                       "note may describe the wrong one. Nothing is written until you click Write."),
                    MenuAction("untick_all", "&Untick All", self._on_untick_all),
                    Separator(),
                    MenuAction("edit_note", "&Edit Note", self._on_edit_note, shortcut=EDIT_NOTE_KEY,
                               tooltip="Edit the selected folder's note in the pane; Save writes it (it then reads as "
                                       "edited by you, and Look Up leaves it alone)"),
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
        self._load_options()
        self.actions_by_key["folder_panel"].setChecked(self.folder_panel_on)

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

    # --- Look Up options (remembered) ------------------------------------------------------------------------------

    def _load_options(self) -> None:
        from core.music import settings as music_settings  # noqa: PLC0415
        from core.video import settings as video_settings  # noqa: PLC0415

        registry = self.actions_by_key
        registry["look_up_below"].setChecked(notes_settings.include_subfolders())
        registry["look_up_outdated"].setChecked(settings.get_setting("notes", "look_up_outdated", "0") == "1")
        chosen = {MUSIC: set(music_settings.kinds()), VIDEO: set(video_settings.kinds())}
        for (media, kind), key in self.kind_actions.items():
            registry[key].setChecked(kind in chosen[media])

    def _on_options_changed(self) -> None:
        from core.music import settings as music_settings  # noqa: PLC0415
        from core.video import settings as video_settings  # noqa: PLC0415

        registry = self.actions_by_key
        notes_settings.set_include_subfolders(registry["look_up_below"].isChecked())
        settings.set_setting("notes", "look_up_outdated", "1" if registry["look_up_outdated"].isChecked() else "0")
        music_settings.set_kinds(",".join(self.chosen_kinds(MUSIC)))
        video_settings.set_kinds(",".join(self.chosen_kinds(VIDEO)))

    def chosen_kinds(self, media: str) -> tuple:
        return tuple(kind for (m, kind), key in self.kind_actions.items()
                     if m == media and self.actions_by_key[key].isChecked())

    # --- File -----------------------------------------------------------------------------------------------------

    def _on_open_library_folder(self) -> None:
        start = self.library_folder or (settings.recent_folders() or [""])[0]
        folder = QFileDialog.getExistingDirectory(self, "Open Library Folder", start)
        if folder:
            self.open_library_folder(folder)

    def open_library_folder(self, folder: str) -> bool:
        """Makes `folder` the open library (File > Open Library Folder, File > Recent, a folder dropped on the window or
        given on the command line): its first level in the tree, music or video guessed from a bounded look at its files.
        The drafts of the library open before are dropped (asked first when some are ticked)."""
        folder = os.path.normpath(folder)
        if not os.path.isdir(folder):
            self.status_bar.showMessage(f"Not a folder: {folder}")
            return False
        if not self._may_drop_drafts("Open another library"):
            return False
        from core.media_guess import guess_media

        self.worker.reset()
        self._lookup_running = 0
        self.session = ReviewSession([], write_fn=self._write_proposal)
        self._index.clear()
        self._media_of.clear()
        self._rebuilding.clear()
        self.library_folder = folder
        # a bounded look at the file names (at most a few thousand); on a share it can take a moment: never silently
        self.library_media = run_busy(self, "Looking at the library's files…", guess_media, folder, title=APP_NAME)
        self._shown = ""
        self.tree.set_root(folder)
        settings.add_recent_folder(folder)
        kind = {"music": "a music library", "video": "a video library"}.get(self.library_media, "music or video: cannot tell")
        self.status_bar.showMessage(f"Opened {folder} ({kind})")
        self.progress_label.setText("")
        self._update_buttons()
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

    # --- the tree and the pane ---------------------------------------------------------------------------------

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 -- Qt override
        """Enter in the tree writes the selected folder's draft and moves to the next folder waiting (card 11)."""
        if obj is self.tree and event.type() == event.Type.KeyPress and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) \
                and event.modifiers() == Qt.KeyboardModifier.NoModifier:
            self._on_write_this()
            return True
        return super().eventFilter(obj, event)

    def item_of(self, folder: str) -> Optional[ReviewItem]:
        index = self._index.get(path_key(folder))
        return self.session.items[index] if index is not None else None

    def _on_folder_selected(self, folder: str) -> None:
        if folder == self._shown:
            return
        if self.pane.is_modified():
            answer = QMessageBox.question(
                self, "Edit Note", "Save the changes to the note first?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save)
            if answer == QMessageBox.StandardButton.Cancel:
                self.tree.blockSignals(True)
                self.tree.select(self._shown)
                self.tree.blockSignals(False)
                return
            if answer == QMessageBox.StandardButton.Save and not self._save_edit(self.pane.raw.toPlainText(), reshow=False):
                self.tree.blockSignals(True)
                self.tree.select(self._shown)
                self.tree.blockSignals(False)
                return
        self._shown = folder
        self._show_current()
        if self.folder_panel_on:
            self.folder_panel.show_folder(folder, self._media_for_panel())

    def _media_for_panel(self) -> str:
        return self.library_media or notes_settings.last_media() or MUSIC

    def _show_current(self) -> None:
        folder = self._shown
        if not folder:
            self.pane.show_nothing()
            return
        item = self.item_of(folder)
        media = self._media_of.get(path_key(folder), "")
        if item is not None and media:
            self.pane.set_strip(self._strip(media))
        state, note = self.tree.note_state(folder)
        self.pane.show_folder(folder, state, note, item)
        self._update_buttons()

    def _on_state_read(self, folder: str) -> None:
        if self._shown and path_key(folder) == path_key(self._shown) and not self.pane.is_editing():
            self._show_current()

    def _strip(self, media: str) -> MatchStrip:
        strip = self.strips.get(media)
        if strip is None:
            from gui import music_notes, video_notes  # noqa: PLC0415

            stand_in = _EngineStandIn(self.worker, media)
            if media == MUSIC:
                strip = MatchStrip(stand_in.can_choose, music_notes.music_hooks(stand_in), music_notes.CANDIDATE_COLUMNS)
            else:
                strip = MatchStrip(stand_in.can_choose, video_notes.video_hooks())
            strip.candidateChosen.connect(lambda c: self._rebuild_current(candidate=c, what=c.name))
            strip.levelChosen.connect(self._choose_level)
            strip.genresChosen.connect(lambda g: self._rebuild_current(what=", ".join(g), genres=g))
            strip.linkChosen.connect(lambda link: self._rebuild_current(what="the link", link=link))
            self.strips[media] = strip
        return strip

    def _set_view(self, view: int) -> None:
        self.pane.set_view(view)

    def _on_toggle_folder_panel(self) -> None:
        on = self.actions_by_key["folder_panel"].isChecked()
        self.folder_panel_on = on
        self.folder_panel.setVisible(on)
        settings.set_setting("view", "folder_panel", "1" if on else "0")
        if on and self._shown:
            self.folder_panel.show_folder(self._shown, self._media_for_panel())

    # --- Look Up --------------------------------------------------------------------------------------------------

    def _make_engine(self, media: str):
        """On the lookup thread: the engine of `media` for this library."""
        cache = notes_settings.default_cache()
        if media == MUSIC:
            from core.music.flow import live_fetchers  # noqa: PLC0415
            from gui.music_notes import make_engine  # noqa: PLC0415
        else:
            from core.video.flow import live_fetchers  # noqa: PLC0415
            from gui.video_notes import make_engine  # noqa: PLC0415
        fetchers = (self.notes_fetchers or live_fetchers)()
        return make_engine(fetchers, cache)

    def _connect_worker(self) -> None:
        w = self.worker
        w.scanned.connect(self._on_scanned)
        w.started_folder.connect(self._on_started_folder)
        w.proposal.connect(self._on_proposal)
        w.finished_job.connect(self._on_finished)
        w.rebuilt.connect(self._on_rebuilt)
        w.rebuild_failed.connect(self._on_rebuild_failed)
        w.status.connect(lambda text: self.progress_label.setText(f"{text}…  {self.progress_label.text()}"))

    def media_for(self, folder: str) -> str:
        """Music or video for a Look Up on `folder`: its own files first, else the library's guess, else the kind used last
        time, else asked once (and kept for this library). '' = the person cancelled."""
        from core.media_guess import guess_media

        media = run_busy(self, "Looking at the folder's files…", guess_media, folder, title=APP_NAME) if folder else ""
        media = media or self.library_media or notes_settings.last_media() or self._ask_media()
        if media and not self.library_media:
            self.library_media = media
        return media

    def _ask_media(self) -> str:
        box = QMessageBox(QMessageBox.Icon.Question, "Look Up",
                          "Is this a music library or a video library? (It could not be told from the file names.)",
                          QMessageBox.StandardButton.Cancel, self)
        music = box.addButton("Music", QMessageBox.ButtonRole.AcceptRole)
        video = box.addButton("Video", QMessageBox.ButtonRole.AcceptRole)
        box.exec()
        clicked = box.clickedButton()
        box.deleteLater()
        return MUSIC if clicked is music else VIDEO if clicked is video else ""

    def _on_look_up(self) -> None:
        folder = self.tree.current_path() or self.library_folder
        if not folder:
            self.status_bar.showMessage("Open a library folder first (File > Open Library Folder).")
            return
        media = self.media_for(folder)
        if not media:
            return
        if media == VIDEO:
            from core.video.flow import live_fetchers  # noqa: PLC0415
            from gui.video_notes import TMDB_KEY_MESSAGE, has_tmdb_key  # noqa: PLC0415

            if not has_tmdb_key((self.notes_fetchers or live_fetchers)()):
                QMessageBox.information(self, "Look Up", TMDB_KEY_MESSAGE)
                return
        if media == MUSIC:
            from core.music.local import ALL_KINDS  # noqa: PLC0415
        else:
            from core.video.local import ALL_KINDS  # noqa: PLC0415
        below = self.actions_by_key["look_up_below"].isChecked()
        kinds = self.chosen_kinds(media) if below else ALL_KINDS  # one folder: what it is, whatever is ticked
        if not kinds:
            self.status_bar.showMessage("Nothing ticked under Notes > Look Up Options.")
            return
        notes_settings.set_last_folder(folder)
        notes_settings.set_last_media(media)
        self._lookup_running = self.worker.look_up(media, folder, below, kinds,
                                                   self.actions_by_key["look_up_outdated"].isChecked())
        self._lookup_media = media
        self.progress_label.setText(f"Looking at {os.path.basename(folder) or folder}…")
        self._update_buttons()

    def _on_cancel_look_up(self) -> None:
        if self._lookup_running:
            self.worker.cancel()
            self.progress_label.setText("Cancelling after the folder in hand…")

    def _on_scanned(self, job: int, count: int, message: str) -> None:
        if count == 0:
            self.progress_label.setText(message or "Nothing to look up.")
        else:
            self.progress_label.setText(f"{count} folder{'s' if count != 1 else ''} to look up…")

    def _on_started_folder(self, job: int, done: int, total: int, name: str) -> None:
        self.progress_label.setText(f"Looking up {name} ({done + 1} of {total})…")

    def _on_finished(self, job: int, built: int, cancelled: bool, problem: str) -> None:
        if job == self._lookup_running:
            self._lookup_running = 0
        if built:
            text = f"Looked up {built} folder{'s' if built != 1 else ''}" + (" (cancelled)" if cancelled else "") + "."
            waiting = sum(1 for i in self.session.items if i.state == PENDING)
            text += f"  {waiting} waiting for you (amber light; {NEXT_WAITING_KEY} goes to the next)."
            self.progress_label.setText(text + (f"  {problem}" if problem else ""))
        elif problem:
            self.progress_label.setText(problem)
        elif cancelled:
            self.progress_label.setText("Cancelled before anything was looked up.")
        self._update_buttons()

    def _on_proposal(self, media: str, proposal) -> None:
        key = path_key(proposal.folder)
        self._media_of[key] = media
        index = self._index.get(key)
        if index is None:
            item = ReviewItem(proposal)
            item.ticked = item.tickable and not proposal.is_update
            self.session.items.append(item)
            self._index[key] = len(self.session.items) - 1
        else:
            self.session.replace(index, proposal, user_resolved=False)
        self._sync_folder(str(proposal.folder))

    def _sync_folder(self, folder: str) -> None:
        item = self.item_of(folder)
        if item is None:
            self.tree.set_draft(folder, False)
        else:
            self.tree.set_draft(folder, item.state == PENDING, item.tickable, item.ticked)
        if self._shown and path_key(folder) == path_key(self._shown):
            self._show_current()
        self._update_buttons()

    # --- a person's choices on a draft --------------------------------------------------------------------------

    def _choose_level(self, level: str) -> None:
        strip = self.pane.strip
        if strip is not None and level == strip.hooks.skip_level:
            index = self._index.get(path_key(self._shown))
            if index is not None:
                self.session.skip(index)
                self._sync_folder(self._shown)
            return
        self._rebuild_current(level=level, what=strip.hooks.level_labels.get(level, level) if strip else level)

    def _rebuild_current(self, candidate=None, level: str = "", what: str = "the note", **extra) -> None:
        folder = self._shown
        key = path_key(folder)
        item = self.item_of(folder)
        if item is None or key in self._rebuilding:
            return
        self._rebuilding.add(key)
        self.worker.rebuild(self._media_of[key], key, item.proposal, candidate, level, **extra)
        self.status_bar.showMessage(f"Looking up {what} for {os.path.basename(folder)}…")

    def _on_rebuilt(self, key: str, proposal) -> None:
        self._rebuilding.discard(key)
        index = self._index.get(key)
        if index is None:
            return
        self.session.replace(index, proposal)
        self.status_bar.showMessage(f"{proposal.folder.name}: " + ("draft ready." if proposal.writable else
                                                                    "still no draft from that."))
        self._sync_folder(str(proposal.folder))

    def _on_rebuild_failed(self, key: str, message: str, is_link: bool) -> None:
        self._rebuilding.discard(key)
        if is_link and self.pane.strip is not None and path_key(self._shown) == key:
            self.pane.strip.set_link_error(message)
            return
        self.status_bar.showMessage(message)
        if not message.startswith("No best guess"):
            QMessageBox.warning(self, "Look Up", message)

    # --- ticks ------------------------------------------------------------------------------------------------

    def _on_tick(self, folder: str, on: bool) -> None:
        index = self._index.get(path_key(folder))
        if index is not None:
            self.session.set_ticked(index, on)
        self._update_buttons()

    def _resync_all(self) -> None:
        for item in self.session.items:
            self._sync_folder(str(item.proposal.folder))

    def _on_tick_confident(self) -> None:
        self.session.tick_confident()
        self._resync_all()

    def _on_untick_all(self) -> None:
        for i in range(len(self.session.items)):
            self.session.set_ticked(i, False)
        self._resync_all()

    def _on_tick_guesses(self) -> None:
        asked = 0
        for item in self.session.items:
            p = item.proposal
            key = path_key(p.folder)
            media = self._media_of.get(key, "")
            engine = self.worker.engine(media)
            if (item.state != PENDING or p.writable or key in self._rebuilding or engine is None
                    or not hasattr(engine, "best_guess") or engine.best_guess(p) is None):
                continue
            self._rebuilding.add(key)
            self.worker.rebuild(media, key, p, best_guess=True)
            asked += 1
        self.status_bar.showMessage(f"Looking up {asked} best guess{'es' if asked != 1 else ''}…" if asked else
                                    "No uncertain match has a candidate and a clear level to guess from.")

    # --- writing ----------------------------------------------------------------------------------------------

    def _write_proposal(self, proposal):
        media = self._media_of.get(path_key(proposal.folder), MUSIC)
        if media == MUSIC:
            from core.music.flow import write_proposal  # noqa: PLC0415
        else:
            from core.video.flow import write_proposal  # noqa: PLC0415
        return write_proposal(proposal)

    def _confirm_updates(self, indices: list[int]) -> bool:
        """An UPDATE replaces an existing note: asked once, saying where the old one goes."""
        updates = [self.session.items[i] for i in indices if self.session.items[i].proposal.is_update]
        if not updates:
            return True
        n = len(updates)
        recycle = self.pane.strip.hooks.recycle_note if self.pane.strip is not None else ""
        text = UPDATE_QUESTION.format(n=f"{n} note" + ("s" if n != 1 else ""), recycle=recycle)
        legacy = sum(1 for i in updates if i.proposal.old_state.kind == STATE_LEGACY)
        if legacy:
            text += (f"\n\n{legacy} of them {'was' if legacy == 1 else 'were'} made by the first versions: it cannot be "
                     "told whether you edited " + ("it." if legacy == 1 else "them."))
        answer = QMessageBox.question(self, "Write", text, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                      QMessageBox.StandardButton.No)
        return answer == QMessageBox.StandardButton.Yes

    def _write(self, indices: list[int]) -> int:
        if not indices or not self._confirm_updates(indices):
            return 0
        written, problems = 0, []
        for i in indices:
            result = self.session.write(i)
            item = self.session.items[i]
            folder = str(item.proposal.folder)
            if item.state == WRITTEN:
                written += 1
                self._written.append(item.written_path)
            elif item.state != PENDING:
                problems.append(f"{item.proposal.folder.name}: {item.message or STATE_WORDS.get(item.state, result.status)}")
            self.tree.refresh_state(folder)
            self._sync_folder(folder)
        text = f"Wrote {written} note{'s' if written != 1 else ''}."
        if written and history.history_enabled():
            text += " Recorded in Tools > History (Edit > Undo takes the last one back)."
        self.status_bar.showMessage(text + (f" {len(problems)} not written." if problems else ""))
        if problems:
            QMessageBox.warning(self, "Write", "Not written:\n\n" + "\n".join(problems[:20]))
        return written

    def _on_write_ticked(self) -> None:
        self._write(self.session.ticked_pending())

    def _on_write_this(self) -> None:
        index = self._index.get(path_key(self._shown)) if self._shown else None
        if index is None or not self.session.items[index].tickable:
            self.status_bar.showMessage("This folder has no draft that can be written yet.")
            return
        if self._write([index]):
            self._on_next_waiting()

    def _on_next_waiting(self) -> None:
        """The next folder (in tree order, wrapping round) whose draft waits for a decision."""
        waiting = sorted((str(i.proposal.folder) for i in self.session.items if i.state == PENDING), key=str.casefold)
        if not waiting:
            self.status_bar.showMessage("No folder is waiting for you.")
            return
        current = (self._shown or "").casefold()
        target = next((f for f in waiting if f.casefold() > current), waiting[0])
        self.tree.select(target)

    def _update_buttons(self) -> None:
        if not hasattr(self, "actions_by_key"):
            return
        n = len(self.session.ticked_pending())
        self.write_button.setText(f"Write {n} ticked note{'s' if n != 1 else ''}")
        self.write_button.setEnabled(n > 0)
        self.ticked_label.setText("")
        self.cancel_button.setVisible(bool(self._lookup_running))
        self.actions_by_key["cancel_look_up"].setEnabled(bool(self._lookup_running))
        self.actions_by_key["write_ticked"].setEnabled(n > 0)
        has_library = bool(self.library_folder)
        self.look_up_button.setEnabled(has_library)
        self.actions_by_key["look_up"].setEnabled(has_library)
        item = self.item_of(self._shown) if self._shown else None
        self.actions_by_key["write_this"].setEnabled(item is not None and item.tickable)
        self.actions_by_key["edit_note"].setEnabled(self.pane.can_edit())

    # --- editing a note (card 7, B) ------------------------------------------------------------------------------

    def _on_edit_note(self) -> None:
        self.pane.start_edit()

    def _save_edit(self, text: str, reshow: bool = True) -> bool:
        from core.notes_engine import save_edited_note  # noqa: PLC0415

        state = self.pane.note_state
        if state is None:
            return False
        if text == state.text:
            self.pane.cancel_edit()
            return True
        result = save_edited_note(state.path, text, state)
        if not result.ok:
            QMessageBox.warning(self, "Edit Note", f"The note was not saved.\n\n{result.message or result.status}")
            return False
        self._written.append(result.path)
        self.pane.end_edit()
        self.tree.refresh_state(os.path.dirname(result.path))
        self.status_bar.showMessage(f"Saved {result.path}. It now reads as edited by you: Look Up leaves it alone.")
        if reshow:
            self._show_current()
        return True

    def _open_note(self) -> None:
        state, note = self.tree.note_state(self._shown)
        if note:
            self.open_path(note)

    # --- Edit > Undo -----------------------------------------------------------------------------------------------

    def _on_undo(self) -> None:
        """Takes back the last note written or saved in this window, through History's own undo (the Recycle Bin, only while
        the note is still exactly what was written). Without History there is no record to undo from."""
        if not self._written:
            self.status_bar.showMessage("Nothing written here to undo.")
            return
        if not history.history_enabled():
            QMessageBox.information(self, "Undo", "Undo needs Tools > History switched on before the note is written: "
                                                  "History keeps what is needed to take a note back.")
            return
        path = self._written[-1]
        entries = [e for e in history.get_journal().entries(path=path, limit=5) if not e.restored_by]
        handlers = history.note_undo_handlers()
        entry = next((e for e in entries if e.kind in handlers), None)
        if entry is None:
            self.status_bar.showMessage(f"No History record of {path} to undo.")
            self._written.pop()
            return
        ok, message = handlers[entry.kind](entry)
        if not ok:
            QMessageBox.warning(self, "Undo", message or "The note could not be taken back.")
            return
        self._written.pop()
        folder = os.path.dirname(path)
        index = self._index.get(path_key(folder))
        if index is not None and self.session.items[index].state == WRITTEN:
            del self._index[path_key(folder)]  # the draft is gone with the note; Look Up drafts it again
        self.tree.refresh_state(folder)
        self._sync_folder(folder)
        self.status_bar.showMessage(message or f"Took back {path}.")

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
        """The keys this program uses (Discogs token, TMDB key) that are still only in one app's own credential entry
        (mp3redactor's, videoredactor's, or this program's from before): offered for sharing with every Redactor, never
        shared silently. At start-up only once ([keys] import_offered); from the File menu every time."""
        from core import old_apps

        if not asked_by_person and settings.get_setting("keys", "import_offered", "") == "1":
            return
        found = old_apps.found_keys()
        if not asked_by_person:
            settings.set_setting("keys", "import_offered", "1")
        if not found:
            if asked_by_person:
                self.status_bar.showMessage("No API keys to share: they are shared already, or no Redactor has them.")
            return
        names = "\n".join(f"  {k.label} (now in {k.app} only)" for k in found)
        answer = QMessageBox.question(
            self, "API keys", f"Share these keys with all the Redactors?\n\n{names}\n\nThen a key is entered once (Tools > "
                              "API Keys in any of them) and every Redactor that uses it has it. Nothing is removed.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        problems = old_apps.copy_keys(found)
        if problems:
            QMessageBox.warning(self, "API keys", "Not shared:\n" + "\n".join(problems))
        else:
            self.status_bar.showMessage(f"{len(found)} key(s) shared with the Redactors.")

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
        """Tools > History: what this program wrote, each with its undo. Opt-in: with nothing recorded yet, offer to turn
        recording on first."""
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

    # --- closing --------------------------------------------------------------------------------------------------

    def _may_drop_drafts(self, what: str) -> bool:
        """Asked when ticked drafts would be lost (closing, another library); True = go on."""
        waiting = len(self.session.ticked_pending())
        if not waiting:
            return True
        answer = QMessageBox.question(
            self, what, f"{waiting} ticked note{'s have' if waiting != 1 else ' has'} not been written. Go on anyway?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        return answer == QMessageBox.StandardButton.Yes

    def closeEvent(self, event) -> None:  # noqa: N802 -- Qt override
        if self.pane.is_modified():
            answer = QMessageBox.question(
                self, "Edit Note", "Save the changes to the note first?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save)
            if answer == QMessageBox.StandardButton.Cancel or (
                    answer == QMessageBox.StandardButton.Save and not self._save_edit(self.pane.raw.toPlainText())):
                event.ignore()
                return
        if not self._may_drop_drafts("Exit"):
            event.ignore()
            return
        self.shutdown()
        super().closeEvent(event)

    def shutdown(self) -> None:
        """Ends the lookup thread and the note-state reader (closing does it; a test calls it when it leaves the window
        open). Safe to call twice."""
        if self.worker.isRunning():
            self.worker.stop()
        self.tree.shutdown()


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
