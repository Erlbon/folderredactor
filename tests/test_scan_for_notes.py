"""Notes > Scan for Notes (2026-11-21): Look Up's own scan of the selected folder and below, with nothing looked up. The tree
opens down to every folder still left (no note yet), each folder above them gets a grey count ('3 left', 'all done'), the
bottom line gives the totals, and a note written later takes its folder off the count."""

from pathlib import Path

import pytest

from core.music.local import scan as music_scan
from core.video.local import scan as video_scan
from gui.library_tree import ALL_DONE, COUNT_ROLE
from gui.lookup_worker import MUSIC, LookupWorker, ScanJob, ScanSummary
from gui.main_window import scan_summary_text
from tests.music_helpers import make_audio
from tests.notes_gui_helpers import open_library, pump, select, set_options
from tests.video_helpers import make_movie, make_series


@pytest.fixture
def lib(tmp_path):
    folder = tmp_path / "Library"
    folder.mkdir()
    return folder


def album(root: Path, artist: str, title: str) -> Path:
    make_audio(root / artist / title / "01 One.mp3", "One", artist, title.split(" (")[0], 1, "1980")
    return root / artist / title


def note(folder: Path, name: str) -> None:
    (folder / name).write_text(f"# {folder.name}\n\nSomebody's note.\n", encoding="utf-8")


def bands(lib: Path) -> Path:
    """Library/0 - bands/A/ABBA (all noted), B/Black Sabbath (noted, one album without), B/Blondie (nothing)."""
    root = lib / "0 - bands"
    note(album(root / "A", "ABBA", "Arrival (1976)"), "album.md")
    note(root / "A" / "ABBA", "artist.md")
    album(root / "B", "Black Sabbath", "Paranoid (1970)")
    note(album(root / "B", "Black Sabbath", "Master of Reality (1971)"), "album.md")
    note(root / "B" / "Black Sabbath", "artist.md")
    album(root / "B", "Blondie", "Parallel Lines (1978)")
    return root


def scan_in_window(window, lib: Path, folder: Path, kinds=("artist", "album")) -> None:
    open_library(window, lib)
    set_options(window, below=True, kinds=kinds)
    window.library_media = MUSIC
    select(window, folder)
    window.actions_by_key["scan_notes"].trigger()
    pump(lambda: not window._scan_running, "the scan")


def test_the_scans_report_every_folder_they_walk_into(lib):
    root = bands(lib)
    walked: list[str] = []
    music_scan([root], kinds=("artist", "album"), on_folder=lambda f: walked.append(Path(f).name))
    assert {"0 - bands", "A", "B", "ABBA", "Black Sabbath", "Paranoid (1970)", "Blondie"} <= set(walked)
    make_series(lib / "Video")
    make_movie(lib / "Video")
    seen: list[str] = []
    video_scan([lib / "Video"], on_folder=lambda f: seen.append(Path(f).name))
    assert seen[0] == "Video" and len(seen) == 3


def test_scan_opens_the_tree_to_every_folder_left_with_a_count_above_them(window, lib):
    root = bands(lib)
    scan_in_window(window, lib, root)
    tree = window.tree
    b, sabbath, blondie = root / "B", root / "B" / "Black Sabbath", root / "B" / "Blondie"
    for folder in (blondie, blondie / "Parallel Lines (1978)", sabbath / "Paranoid (1970)"):
        assert tree.item_for(folder) is not None, folder
    assert tree.item_for(b).isExpanded() and tree.item_for(sabbath).isExpanded()
    assert not tree.item_for(root / "A").isExpanded()  # nothing left there: stays closed
    assert tree.count_label(str(root)) == "3 left" and tree.count_label(str(b)) == "3 left"
    assert tree.count_label(str(sabbath)) == "1 left" and tree.count_label(str(blondie)) == "1 left"
    assert tree.count_label(str(root / "A")) == ALL_DONE
    assert tree.count_label(str(sabbath / "Paranoid (1970)")) == ""  # a folder left has its light, no count
    assert tree.item_for(b).data(0, COUNT_ROLE) == "3 left"  # what the delegate paints in grey
    tree.resize(500, 400)
    assert not tree.grab().isNull()  # the delegate paints the counts without an error
    assert window.progress_label.text() == "Scanned 0 - bands: 3 left without a note, 4 have a note."


def test_a_note_written_later_takes_its_folder_off_the_count(window, lib):
    root = bands(lib)
    scan_in_window(window, lib, root)
    tree = window.tree
    paranoid = root / "B" / "Black Sabbath" / "Paranoid (1970)"
    note(paranoid, "album.md")
    tree.refresh_state(str(paranoid))
    pump(lambda: tree.left_count(str(root)) == 2, "the count to drop")
    assert tree.count_label(str(root / "B")) == "2 left" and tree.count_label(str(root / "B" / "Black Sabbath")) == ""


def test_opening_another_library_forgets_the_counts(window, lib, tmp_path):
    root = bands(lib)
    scan_in_window(window, lib, root)
    other = tmp_path / "Other"
    other.mkdir()
    window.open_library_folder(str(other))
    assert window.tree.count_label(str(root)) == "" and window.tree.left_count(str(root)) == 0


def test_a_cancelled_scan_leaves_the_tree_alone(lib):
    root = bands(lib)
    worker = LookupWorker(lambda media: None)
    worker._cancel.set()
    summary = worker._run_scan(ScanJob(MUSIC, str(root), ("artist", "album"), False, 1))
    assert summary.cancelled and not summary.left


def test_the_bottom_line_says_the_outdated_apart_and_nothing_left():
    s = ScanSummary("x", left=["a"] * 312, without=298, outdated=14, have=1240)
    assert scan_summary_text("0 - bands", s) == "Scanned 0 - bands: 312 left (298 without a note, 14 outdated), 1,240 have a note."
    assert scan_summary_text("Z", ScanSummary("x", have=1)) == "Scanned Z: nothing left, 1 has a note."
