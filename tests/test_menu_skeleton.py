"""The family's menu skeleton on the real MainWindow: the headings of the plan in order, what each menu holds, the
job menus greyed (disable, never hide), the lint, the command palette, File > Recent and opening a library."""

from PyQt6.QtCore import QMimeData, QPointF, Qt, QUrl
from PyQt6.QtGui import QDropEvent, QKeySequence

from core import settings
from core.version import APP_NAME


def _menus(window) -> dict:
    return {a.text().replace("&", ""): a.menu() for a in window.menuBar().actions() if a.menu()}


def _labels(menu) -> list:
    return [a.text().replace("&", "") for a in menu.actions() if not a.isSeparator()]


def test_headings_are_the_skeleton_with_notes_and_clean_up(window):
    assert list(_menus(window)) == ["File", "Edit", "View", "Notes", "Clean Up", "Tools", "Help"]


def test_each_menu_holds_what_the_plan_says(window):
    menus = _menus(window)
    assert _labels(menus["File"]) == ["Open Library Folder…", "Recent", "Exit"]
    assert _labels(menus["Edit"]) == ["Undo"]
    assert _labels(menus["View"]) == ["Command Palette…"]
    assert _labels(menus["Notes"]) == ["Create Notes…", "Refresh Old Notes…", "Switch View"]
    assert _labels(menus["Clean Up"]) == ["Check Folder Tree…", "Open Check Report…", "Apply Decisions…"]
    assert _labels(menus["Tools"]) == ["Preferences…", "API Keys…", "Clear Lookup Cache", "History…"]
    assert _labels(menus["Help"]) == ["Changelog…", "Credits…", "Check for Updates…", f"About {APP_NAME}"]


def test_the_jobs_not_built_yet_are_greyed_not_hidden(window):
    registry = window.actions_by_key
    for key in ("create_notes", "refresh_old_notes", "switch_view", "check_folder_tree", "open_check_report",
                "apply_decisions", "clear_lookup_cache", "undo"):
        assert key in registry and not registry[key].isEnabled(), key
    for key in ("open_library_folder", "api_keys", "history", "preferences", "about", "command_palette"):
        assert registry[key].isEnabled(), key


# Violations the lint reports on purpose: the plan's label "Open Library Folder" on the family's Open Folder key.
DOCUMENTED_LINT_EXCEPTIONS = {
    "File > Open Library Folder is bound to Ctrl+Shift+O: Ctrl+Shift+O is Open Folder",
}


def test_menu_bar_passes_the_skeleton_lint(window):
    from redactor_common.gui.menu_lint import lint_menu_bar

    assert set(lint_menu_bar(window)) == DOCUMENTED_LINT_EXCEPTIONS


def test_no_ctrl_alt_shortcut_anywhere(window):
    from redactor_common.gui.menu_lint import is_ctrl_alt

    for entry in window.actions_by_key.entries():
        for sequence in entry.action.shortcuts():
            assert not is_ctrl_alt(sequence.toString()), entry.key


def test_command_palette_is_on_ctrl_k_and_finds_the_actions(window):
    from redactor_common.gui.command_palette import collect_commands

    action = window.actions_by_key["command_palette"]
    assert action.shortcut() == QKeySequence("Ctrl+K")
    titles = [c.title for c in collect_commands(window, window.actions_by_key)]
    assert "API Keys" in titles and "Open Library Folder" in titles and "Check Folder Tree" in titles


def test_open_library_folder_shows_it_and_remembers_it(window, tmp_path):
    library = tmp_path / "Music"
    library.mkdir()
    assert window.open_library_folder(str(library))
    assert window.library_folder == str(library) and str(library) in window.folder_label.text()
    assert settings.recent_folders() == [str(library)]
    window._fill_recent_menu()
    assert str(library) in _labels(window.recent_menu)[0]


def test_a_missing_folder_is_not_opened(window, tmp_path):
    assert not window.open_library_folder(str(tmp_path / "gone"))
    assert window.library_folder == "" and settings.recent_folders() == []


def test_recent_lists_newest_first_and_clears(window, tmp_path):
    for name in ("A", "B", "A"):
        (tmp_path / name).mkdir(exist_ok=True)
        window.open_library_folder(str(tmp_path / name))
    assert settings.recent_folders() == [str(tmp_path / "A"), str(tmp_path / "B")]
    window._on_clear_recent()
    assert settings.recent_folders() == []
    assert _labels(window.recent_menu) == ["No recent folders", "Clear Recent"]


def test_an_ampersand_in_a_recent_path_is_shown_not_taken_as_a_mnemonic(window, tmp_path):
    folder = tmp_path / "Simon & Garfunkel"
    folder.mkdir()
    window.open_library_folder(str(folder))
    window._fill_recent_menu()
    assert "Simon && Garfunkel" in window.recent_menu.actions()[0].text()


def test_a_dropped_folder_opens_and_dropped_files_do_not(window, tmp_path):
    folder = tmp_path / "Films"
    folder.mkdir()
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")

    def drop(*paths):
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(p)) for p in paths])
        event = QDropEvent(QPointF(5, 5), Qt.DropAction.CopyAction, mime, Qt.MouseButton.NoButton,
                           Qt.KeyboardModifier.NoModifier)
        window.dropEvent(event)

    drop(tmp_path / "a.txt")
    assert window.library_folder == ""
    drop(folder, tmp_path / "a.txt")
    assert window.library_folder == ""
    drop(folder)
    assert window.library_folder == str(folder)


def test_a_folder_on_the_command_line_opens_the_window_with_it(qapp, tmp_path):
    from gui.main_window import MainWindow, folder_from_argv

    folder = tmp_path / "Music"
    folder.mkdir()
    assert folder_from_argv(["folderredactor.exe", str(folder)]) == str(folder)
    assert folder_from_argv(["folderredactor.exe"]) is None
    assert folder_from_argv(["folderredactor.exe", str(tmp_path / "gone")]) is None
    win = MainWindow(folder_from_argv(["folderredactor.exe", str(folder)]))
    try:
        assert win.library_folder == str(folder)
    finally:
        win.close()
