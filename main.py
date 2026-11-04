"""The Ⅎolder Redactor -- entry point.

Startup (crash logging, taskbar icon ID, theme, message-box width) is redactor_common.gui.app_bootstrap.run_app(),
shared with the other Redactor apps. A first argument that is a command name runs the command line instead
(foldercli); anything else, a folder path for example, starts the window.
"""

import sys

from core import crash_log
from core.app_paths import asset_path
from core.version import APP_NAME
from foldercli import cli_requested
from redactor_common.gui.app_bootstrap import run_app


def main() -> int:
    if cli_requested(sys.argv):
        # One exe: `folderredactor notes ...` is the command line (no window). See foldercli/main.py.
        from redactor_common.cli import run
        from foldercli.main import main as cli_main

        return run(cli_main, sys.argv[1:])

    from gui.main_window import MainWindow, folder_from_argv

    initial_folder = folder_from_argv(sys.argv)  # `folderredactor.exe D:/Music` opens that library
    return run_app(
        app_name=APP_NAME,
        window_factory=lambda: MainWindow(initial_folder),
        crash_log_path=crash_log.log_path(),
        app_user_model_id="Erlbon.FolderRedactor.GUI.1",
        icon_path=asset_path("assets/icon.ico"),
    )


if __name__ == "__main__":
    sys.exit(main())
