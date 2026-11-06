"""Shared test setup. No test may touch the real settings file, History journal, update switch, crash log or the
Windows Credential Manager: each gets its own in tmp_path, and the API key environment variables are cleared.

Like the siblings' (redactor_common's conftest), the process ends with pytest's own exit code once pytest is done,
skipping the interpreter's shutdown, which with Python 3.15 on Windows sometimes crashed after a green run (an access
violation, exit code 139) and so blocked the pre-push hook. A failing run still exits 1."""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

_status = {"code": None}


def pytest_sessionfinish(session, exitstatus):
    _status["code"] = int(exitstatus)


def pytest_unconfigure(config):
    code = _status["code"]
    if code is None:
        return
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    except Exception:  # noqa: BLE001 -- nothing may stop the exit code from being passed on
        pass
    os._exit(code)


class FakeKeyring:
    """In-memory stand-in for the OS credential store (keyring's API)."""

    def __init__(self):
        self.data = {}

    def get_password(self, service, name):
        return self.data.get((service, name))

    def set_password(self, service, name, value):
        self.data[(service, name)] = value

    def delete_password(self, service, name):
        if (service, name) not in self.data:
            raise type("PasswordDeleteError", (Exception,), {})("not found")
        del self.data[(service, name)]


@pytest.fixture(autouse=True)
def app_files(tmp_path, monkeypatch):
    """The app's own files in tmp_path/app: settings, update switch, crash log. Returns that folder."""
    from core import app_paths, crash_log, settings

    folder = tmp_path / "app"
    folder.mkdir()
    monkeypatch.setattr(settings, "CONFIG_PATH", folder / "folderredactor_settings.ini")
    monkeypatch.setattr(app_paths, "updates_json_path", lambda: folder / "folderredactor_updates.json")
    monkeypatch.setattr(crash_log, "log_path", lambda: str(folder / "folderredactor_crash.log"))
    return folder


@pytest.fixture(autouse=True)
def notes_cache(app_files, monkeypatch):
    """The Create Notes lookup cache follows the settings file into tmp_path; the process-wide one starts empty in each
    test and is closed after it (so no test sees another's answers, and the file is not held open)."""
    from redactor_common.core import notes_cache as shared

    monkeypatch.setattr(shared, "_default", None)
    yield
    if shared._default is not None:
        shared._default.close()


@pytest.fixture(autouse=True)
def journal(app_files):
    """The Tools > History journal next to the test's settings file. History is opt-in: it stays off (nothing
    written) unless a test turns it on."""
    from core import history

    j = history.GatedJournal(str(app_files / "folderredactor_journal.jsonl"))
    history.set_journal(j)
    yield j
    history.set_journal(None)


class FakeRecycleBin:
    """Stands in for the Recycle Bin: moves the file into a folder of the test's own and remembers it, so nothing real is
    ever trashed. `fail_with` makes the next moves raise (a drive without a bin, a locked file)."""

    def __init__(self, folder):
        self.folder = folder
        self.trashed: list[str] = []
        self.fail_with: Exception | None = None

    def __call__(self, path: str, fallback_folder: str | None = None) -> None:
        import shutil

        if self.fail_with is not None:
            raise self.fail_with
        self.folder.mkdir(exist_ok=True)
        shutil.move(path, str(self.folder / f"{len(self.trashed)}-{os.path.basename(path)}"))
        self.trashed.append(path)


@pytest.fixture(autouse=True)
def recycle_bin(monkeypatch, tmp_path):
    """Replacing an older note and undoing a written one trash through redactor_common's move_to_trash (looked up at call
    time): every test gets the fake bin."""
    from redactor_common.core import trash

    bin_ = FakeRecycleBin(tmp_path / "_recycle_bin")
    monkeypatch.setattr(trash, "move_to_trash", bin_)
    return bin_


@pytest.fixture(autouse=True)
def fake_keyring(tmp_path, monkeypatch):
    from redactor_common.core import secret_store

    backend = FakeKeyring()
    secret_store.set_backend(backend)
    secret_store.set_fallback_dir(tmp_path / "secrets")
    secret_store.set_allow_unencrypted_fallback(False)
    for var in ("DISCOGS_TOKEN", "TMDB_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    yield backend
    secret_store.set_backend(None)
    secret_store.set_fallback_dir(None)
    secret_store.set_allow_unencrypted_fallback(False)


@pytest.fixture(scope="session")
def qapp():
    from PyQt6.QtWidgets import QApplication

    return QApplication.instance() or QApplication(sys.argv)


@pytest.fixture
def window(qapp):
    from gui.main_window import MainWindow

    win = MainWindow()
    yield win
    win.close()
    win.deleteLater()
