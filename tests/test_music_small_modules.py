"""The small modules that moved with the music notes and have no engine-free test of their own in mp3redactor: 'What to
create' (core/music/kinds.py), 'Look up by link' (core/music/link.py) and the troubleshooting log (core/notes_debug.py).
MusicBrainz and Discogs (core/music/musicbrainz.py, discogs.py) are tested through the engine, plan step 8."""

import pytest

from core import notes_debug, notes_settings
from core.music.kinds import kinds_text, parse_kinds
from core.music.link import LinkError, parse_link


@pytest.mark.parametrize("text,expected", [
    ("artist", ("artist",)), ("album,artist", ("artist", "album")), ("both", ("artist", "album")),
    ("all", ("artist", "album", "genre")), ("collection", ("genre",)), ("", ("artist",)), ("nonsense", ("artist",)),
    (["genre", "artist"], ("artist", "genre")), ("albums+genres", ("album", "genre")),
])
def test_what_to_create_is_read_forgivingly_in_a_fixed_order(text, expected):
    assert parse_kinds(text) == expected and kinds_text(text) == ",".join(expected)


def test_a_link_names_what_it_points_at_without_any_network():
    mbid = "2bf704b3-4f4b-4f1c-9a1d-3f9e8f2a1c11"
    linked, bare = parse_link(f"https://musicbrainz.org/artist/{mbid}"), parse_link(mbid)
    assert (linked.kind, linked.id) == (bare.kind, bare.id) == ("mb-artist", mbid)  # `raw` keeps what was pasted
    assert parse_link(mbid, bare_as="release-group").kind == "mb-release-group"
    page = parse_link("https://en.wikipedia.org/wiki/Leningrad_(band)")
    assert (page.kind, page.id, page.lang) == ("wikipedia", "Leningrad (band)", "en")
    assert parse_link("https://www.discogs.com/artist/55646-Cristina").kind == "discogs-artist"


@pytest.mark.parametrize("text", ["", "https://example.com/artist/1", "https://musicbrainz.org/recording/2bf704b3-4f4b-4f1c-9a1d-3f9e8f2a1c11"])
def test_a_link_from_elsewhere_is_refused_with_a_plain_message(text):
    with pytest.raises(LinkError) as info:
        parse_link(text)
    assert str(info.value)


@pytest.fixture
def debug_log(monkeypatch):
    monkeypatch.delenv("FOLDERREDACTOR_NOTES_DEBUG", raising=False)
    notes_debug.set_enabled(None)
    yield
    notes_debug.set_enabled(None)


def test_the_troubleshooting_log_is_off_by_default_and_writes_nothing(app_files, debug_log):
    assert not notes_debug.enabled()
    notes_debug.record("scrolled", rows=3, folders=["A"])
    assert not notes_debug.log_exists() and not list(app_files.glob("*debug*"))


def test_switched_on_it_writes_next_to_the_settings_and_can_be_deleted(app_files, debug_log):
    notes_settings.set_debug_log_enabled(True)
    assert notes_debug.enabled()
    notes_debug.record("scrolled", rows=3, folders=["Ultravox", "Vienna (1980)"])
    assert notes_debug.log_path() == app_files / "folderredactor_notes_debug.log"
    line = notes_debug.log_path().read_text(encoding="utf-8")
    assert "scrolled" in line and "rows=3" in line and "Ultravox" in line
    assert notes_debug.delete_log() == "" and not notes_debug.log_exists()


def test_the_environment_variable_switches_it_on_too(app_files, debug_log, monkeypatch):
    monkeypatch.setenv("FOLDERREDACTOR_NOTES_DEBUG", "1")
    assert notes_debug.enabled()
