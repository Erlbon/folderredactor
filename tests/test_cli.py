"""The command line in the one exe: which first arguments start it, the entry point, and ABOUT.md's "Command line"
section kept in step with the parser (every command and option documented, the exit codes and the ways to script
it). The commands themselves are tested in their own files (test_notes_cli.py)."""

import argparse
from pathlib import Path

import pytest

ABOUT = Path(__file__).parent.parent / "ABOUT.md"


def test_only_a_command_name_or_help_starts_the_command_line(tmp_path):
    from foldercli import COMMANDS, cli_requested

    assert COMMANDS == ("notes",)
    assert cli_requested(["folderredactor.exe", "notes", str(tmp_path)])
    assert cli_requested(["folderredactor.exe", "--version"]) and cli_requested(["folderredactor.exe", "--help"])
    assert not cli_requested(["folderredactor.exe"]) and not cli_requested(["folderredactor.exe", str(tmp_path)])


def test_version_prints_the_program_and_its_version(capsys):
    from core.version import APP_VERSION
    from foldercli.main import main

    with pytest.raises(SystemExit) as info:
        main(["--version"])
    assert info.value.code == 0 and capsys.readouterr().out.strip() == f"folderredactor {APP_VERSION}"


def test_the_parser_lists_exactly_the_commands():
    from foldercli import COMMANDS
    from foldercli.main import build_parser

    subparsers = next(a for a in build_parser()._actions if isinstance(a, argparse._SubParsersAction))
    assert tuple(subparsers.choices) == COMMANDS


def test_the_entry_point_runs_the_command_line_without_a_window(monkeypatch, capsys):
    import main as app

    monkeypatch.setattr(app.sys, "argv", ["folderredactor", "--version"])
    monkeypatch.setattr(app, "run_app", lambda **kw: pytest.fail("the window was started"))
    with pytest.raises(SystemExit) as info:  # argparse's --version exits by itself, with 0
        app.main()
    assert info.value.code == 0 and capsys.readouterr().out.startswith("folderredactor ")


def test_the_entry_point_starts_the_window_for_no_command_or_a_folder(monkeypatch, tmp_path):
    import main as app

    started = []
    monkeypatch.setattr(app, "run_app", lambda **kw: started.append(kw["window_factory"]) or 0)
    monkeypatch.setattr(app.sys, "argv", ["folderredactor"])
    assert app.main() == 0
    monkeypatch.setattr(app.sys, "argv", ["folderredactor", str(tmp_path)])
    assert app.main() == 0 and len(started) == 2


# --- the documentation covers every command and option ------------------------------------------------------------


def _cli_section() -> str:
    text = ABOUT.read_text(encoding="utf-8")
    start = text.index("## Command line")
    end = text.find("\n## ", start + 5)
    return text[start:end if end != -1 else None]


def test_about_documents_every_command_and_option():
    from foldercli.main import build_parser

    section = _cli_section()
    parser = build_parser()
    missing = [o for action in parser._actions for o in action.option_strings if o not in section]
    subparsers = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    for name, sub in subparsers.choices.items():
        if f"### {name}" not in section:
            missing.append(f"### {name}")
        missing += [f"{name} {o}" for action in sub._actions for o in action.option_strings if o not in section]
    assert missing == [], f"the Command line section of ABOUT.md does not mention: {missing}"


def test_about_lists_the_exit_codes_and_the_scripting_ways():
    section = _cli_section()
    for code in ("| 0 |", "| 1 |", "| 2 |", "| 70 |", "| 130 |"):
        assert code in section
    for way in ("start /wait", "Start-Process", "Out-Null", "--output"):
        assert way in section
