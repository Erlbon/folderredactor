"""The family's update framework (redactor_common docs/update-framework.md): the per-user installer includes the shared
installer contract at its end, every build declares its update channel, the release tool's configuration
(pyproject.toml) matches the installer and the build, and Help > Check for Updates and the command line's
--check-update decide through selfupdate.decide() by the release's update-manifest.json."""

import hashlib
import json
import sys
from pathlib import Path

import pytest

from core import version

ROOT = Path(__file__).resolve().parent.parent


def read(*parts) -> str:
    return ROOT.joinpath(*parts).read_text(encoding="utf-8")


def setting(script: str, name: str):
    for line in script.splitlines():
        if line.split("=", 1)[0].strip() == name:
            return line.split("=", 1)[1].strip()
    return None


def release_config():
    from redactor_common import release

    return release.load_config(ROOT)


def github(tag, files=None):
    """A fake GitHub: release `tag` with `files` (name -> bytes) as assets, digests included."""
    files = files or {}
    base = "https://github.com/Erlbon/folderredactor/releases"
    assets = [{"name": name, "browser_download_url": f"{base}/download/{tag}/{name}", "size": len(data),
               "digest": "sha256:" + hashlib.sha256(data).hexdigest()} for name, data in files.items()]
    answer = json.dumps({"tag_name": tag, "body": "", "html_url": f"{base}/tag/{tag}", "assets": assets}).encode()

    def fetch(request):
        url = getattr(request, "full_url", request)
        return answer if url.startswith("https://api.github.com/") else files[url.rsplit("/", 1)[1]]
    return fetch


# --- the installer ----------------------------------------------------------------------------------------------------


def test_the_installer_installs_per_user():
    iss = read("installer", "folderredactor.iss")
    assert setting(iss, "PrivilegesRequired") == "lowest"
    assert setting(iss, "PrivilegesRequiredOverridesAllowed") is None   # no "for all users"
    assert setting(iss, "DefaultDirName").startswith("{autopf}\\")       # %LOCALAPPDATA%\Programs for a per-user install
    assert setting(iss, "OutputBaseFilename") == "folderredactor-setup"


def test_the_installer_ships_the_one_folder_build_and_includes_the_update_contract_at_its_end():
    iss = read("installer", "folderredactor.iss")
    assert 'Source: "..\\dist\\folderredactor\\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs' in iss
    assert '#define UpdateExe "folderredactor.exe"' in iss
    assert iss.rstrip().splitlines()[-1] == "#include UpdateContract"
    assert "#error Pass /DUpdateContract" in iss
    # the header notes sit in "#if 0", as in the contract: no ";" line before it
    assert iss.splitlines()[0] == "#if 0"
    header = iss.split("#endif", 1)[0]
    assert all(line.startswith(";") or line in ("#if 0", "") for line in header.splitlines())
    bat = read("build_exe.bat")
    assert '"/DUpdateContract=%CONTRACT%"' in bat and "redactor_common.release contract-path" in bat


def test_the_contract_the_installer_includes_is_there():
    from redactor_common import release

    contract = Path(release.contract_path()).read_text(encoding="utf-8")
    assert "UpdateContractRelaunch" in contract and "windows-installer" in contract


def test_the_app_id_never_changes_and_the_release_tool_knows_it():
    """A new AppId would install a second copy beside the first instead of upgrading it; the release gate finds the
    scratch install (and refuses to run beside a real one) by the same id."""
    app_id = setting(read("installer", "folderredactor.iss"), "AppId")
    assert app_id == "{{EC5101A1-10C3-479D-9069-EF4B1DFF1A29}"
    assert release_config().installer_app_id == app_id[1:]                 # "{{" is Inno Setup's escaped "{"


# --- the builds -------------------------------------------------------------------------------------------------------


def test_every_build_declares_its_update_channel():
    """The one-file exe carries windows-exe inside (it swaps itself); the folder build gets windows-zip beside its exe,
    which the installer's contract overwrites with windows-installer."""
    spec = read("folderredactor.spec")
    assert 'os.environ.get("FOLDERREDACTOR_BUILD", "") == "folder"' in spec and "COLLECT(" in spec
    assert 'channel.write("windows-exe\\n")' in spec and '[] if FOLDER else [(CHANNEL, ".")]' in spec
    assert 'os.path.join(DISTPATH, "folderredactor", "update-channel")' in spec
    assert 'channel.write("windows-zip\\n")' in spec


def test_no_build_is_packed_with_upx():
    """Defender flags UPX-packed, unsigned exes as malware (the Redactor apps 2026-10-30)."""
    spec = read("folderredactor.spec")
    assert "upx=True" not in spec and spec.count("upx=False") == 2


def test_build_exe_builds_both_programs_and_the_installer_with_this_repos_venv():
    bat = read("build_exe.bat")
    commands = [line for line in bat.splitlines() if not line.lstrip().upper().startswith(("REM", "ECHO"))]
    assert "venv_sync.py" in bat and not any("pip install" in line for line in commands)
    assert bat.count(".venv\\Scripts\\python -m PyInstaller folderredactor.spec --noconfirm") == 2
    assert bat.index('set "FOLDERREDACTOR_BUILD="') < bat.index('set "FOLDERREDACTOR_BUILD=folder"')
    assert "installer\\folderredactor.iss" in bat and "--no-pause" in bat
    for built in ("dist\\folderredactor.exe", "dist\\folderredactor\\folderredactor.exe", "dist\\folderredactor-setup.exe"):
        assert f'if not exist "{built}"' in bat


def test_the_release_tool_publishes_the_exe_and_the_installer():
    cfg = release_config()
    assert (cfg.app, cfg.repo, cfg.exe) == ("folderredactor", "Erlbon/folderredactor", "folderredactor.exe")
    assert {channel: path.name for channel, path in cfg.package_paths().items()} == {
        "windows-installer": "folderredactor-setup.exe", "windows-exe": "folderredactor.exe"}
    assert cfg.version == version.APP_VERSION
    assert cfg.tag == "v" + version.APP_VERSION.replace("#", "-")
    assert cfg.release_title == f"{version.APP_NAME} {cfg.tag}"
    assert cfg.build == ["build_exe.bat", "--no-pause"]
    assert cfg.app == version.APP_REPO_URL.rstrip("/").rsplit("/", 1)[1].lower()   # the manifest's app is the copy's slug


# --- deciding ---------------------------------------------------------------------------------------------------------


def test_check_for_updates_asks_github_and_says_when_this_is_the_newest(window, monkeypatch):
    from redactor_common.gui import update_controller

    told = []
    monkeypatch.setattr(window.updates, "_fetch", github("v" + version.APP_VERSION.replace("#", "-")))
    monkeypatch.setattr(update_controller, "run_busy", lambda parent, label, fn, **kw: fn())
    monkeypatch.setattr(update_controller.QMessageBox, "information", lambda *a: told.append(a[2]))
    help_menu = next(a.menu() for a in window.menuBar().actions() if a.text().replace("&", "") == "Help")
    next(a for a in help_menu.actions() if a.text().replace("&", "").startswith("Check for Updates")).trigger()
    assert f"newest version of {version.APP_NAME}" in told[-1]


@pytest.mark.parametrize("channel, file", [("windows-installer", "folderredactor-setup.exe"),
                                           ("windows-exe", "folderredactor.exe")])
def test_an_installed_copy_and_the_portable_exe_each_take_their_file_from_the_manifest(window, monkeypatch, tmp_path,
                                                                                        channel, file):
    """What the release tool publishes, read the way a copy reads it: the installed copy runs the installer, the
    portable exe swaps itself, each by the file the manifest names for its channel."""
    from redactor_common.core import update_manifest

    cfg = release_config()
    newer = "v2099-01-01-01"
    built = {name: name.encode() * 10 for name in ("folderredactor-setup.exe", "folderredactor.exe")}
    for name, data in built.items():
        (tmp_path / name).write_bytes(data)
    manifest = update_manifest.build(cfg.app, newer, "2099-01-01#01",
                                     {c: tmp_path / p.name for c, p in cfg.package_paths().items()})
    built[update_manifest.MANIFEST_NAME] = json.dumps(manifest).encode()
    monkeypatch.setattr(window.updates, "_fetch", github(newer, built))
    monkeypatch.setattr(window.updates, "channel", channel)
    monkeypatch.setattr(window.updates, "_exe", tmp_path / "folderredactor.exe")
    decision = window.updates.decide()
    assert (decision.action, decision.release.asset_name, decision.reason) == ("install", file, "")


def test_a_copy_run_from_source_never_updates_itself(window, monkeypatch):
    monkeypatch.setattr(window.updates, "_fetch", github("v2099-01-01-01"))
    assert window.updates.channel == "source"
    assert window.updates.decide().action == "page"


def test_the_update_command_line_answers_before_anything_else(tmp_path, monkeypatch):
    """The release gate asks a copy `--version --result-file` and `--check-update`; a plain --version stays the
    command line's."""
    import main

    answer = tmp_path / "v.txt"
    monkeypatch.setattr(sys, "argv", ["folderredactor", "--version", "--result-file", str(answer)])
    assert main.main() == 0
    assert answer.read_text(encoding="utf-8").strip() == version.APP_VERSION
    assert main.update_command(["--check-update", "--release-tag", "v2099-01-01-01"])
    assert main.update_command(["--update"])
    assert not main.update_command(["--version"]) and not main.update_command(["notes", "D:/Music"])
