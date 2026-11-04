"""
foldercli -- folderredactor's command line. It is not a second program: main.py hands over to foldercli.main when its
first argument is one of COMMANDS (see cli_requested), otherwise the window starts. Kept light on purpose: this
package is imported on every start, the commands themselves only when one is asked for.

No commands yet: `notes` (folder notes) and `check` / `apply` / `undo` (folder-tree clean-up) come with their jobs.
Each new command is added to COMMANDS and to the "Command line" section of ABOUT.md (a test checks both).
"""

from redactor_common.cli import is_cli_invocation

COMMANDS: tuple[str, ...] = ()


def cli_requested(argv) -> bool:
    return is_cli_invocation(argv, COMMANDS)
