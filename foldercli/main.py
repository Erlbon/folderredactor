"""
foldercli/main.py

The folderredactor command line, run through the app's own exe (main.py dispatches here when its first argument is a
command; the window never starts). The commands come with the app's two jobs:

    folderredactor notes  FOLDER... [--write]     draft the folder notes (dry run unless --write)      (to come)
    folderredactor check  ROOT --output FILE      check a library's folder tree, report only           (to come)
    folderredactor apply  ROOT --report FILE --decisions FILE [--write]   rename on the yes decisions  (to come)
    folderredactor undo   LOG                     undo such renames                                    (to come)

Every command takes --json (one JSON document), --quiet and --output FILE, and the ones that change something are a
dry run unless --write. Exit codes: 0 done, 1 some items failed or have problems, 2 bad arguments, 70 internal error,
130 interrupted. It reads the same settings file as the app.
"""

from __future__ import annotations

from core.version import APP_VERSION
from redactor_common.cli.main_factory import make_main

from foldercli import COMMANDS

PROG = "folderredactor"

build_parser, main = make_main(
    PROG, APP_VERSION,
    "The Folder Redactor on the command line: folder notes and folder-tree clean-up for media libraries.",
    [],
    commands=COMMANDS,
)
