"""Review of 2026-10-16, batch 3: the notes ENGINE's correctness. Every test drives the app's own engine (NotesEngine /
build_proposals / the CLI) on real tagged MP3 files and fake MusicBrainz / Wikipedia / Discogs replies; nothing reaches the
network (an unexpected URL fails the test).

  1 namesake artists            2 generic titles identify any artist       3 a best guess keeps every veto
  7 one timeout is not forever  8a an album folder is not a library root  8b a collection has no artist.md to replace
"""

import json
import re
import urllib.error
from urllib.parse import unquote_plus

import pytest

from redactor_common.core.lookups.discogs import DiscogsClient
from core.music.flow import (
    Confidence, Fetchers, GuessCandidate, NotesEngine, build_proposals, scan, write_proposal,
)
from core.music.local import ALL_KINDS, KIND_ALBUM, KIND_ARTIST
from redactor_common.core.lookup_client import Throttle
from tests.music_helpers import FakeFetch, make_mp3, ultravox_fetchers, ultravox_library

QUIET_WIKI = [(r"search/title", {"pages": []}), (r"page/summary/", None), (r"wikidata\.org", {"entities": {}})]


def artist_json(aid, name, begin="1980"):
    return {"id": aid, "name": name, "sort-name": name, "type": "Group", "country": "GB", "score": 100,
            "life-span": {"begin": begin}, "aliases": [], "relations": [], "genres": [], "tags": []}


def rg_json(rid, title, date="1985", artist=None):
    out = {"id": rid, "title": title, "first-release-date": date, "primary-type": "Album", "secondary-types": []}
    if artist:
        out["artist-credit"] = [{"name": artist[1], "artist": {"id": artist[0], "name": artist[1]}}]
    return out


def mb_world(artists, search=None, owners=None):
    """FakeFetch routes for a small MusicBrainz. artists: {id: (name, begin, [album titles])}. search: the ids the artist-name
    search returns (default: none). owners: {album title: [artist ids]}: what the search by album title returns (25 per title)."""
    search = search or []
    owners = owners or {}

    def by_title(url):
        text = unquote_plus(url).casefold()
        found = []
        for title, ids in owners.items():
            if f'releasegroup:"{title.casefold()}"' in text or f"releasegroup:{title.casefold()}" in text:
                found += [rg_json(f"t-{i}-{title}", title, artist=(i, artists[i][0])) for i in ids]
        return {"release-groups": found}

    def one_artist(url):
        aid = re.search(r"ws/2/artist/([^?]+)\?", url).group(1)
        name, begin, _titles = artists[aid]
        return artist_json(aid, name, begin)

    def browse(url):
        aid = re.search(r"release-group\?artist=([^&]+)", url).group(1)
        return {"release-groups": [rg_json(f"{aid}-{n}", t) for n, t in enumerate(artists[aid][2])]}

    return [
        (r"ws/2/release-group\?query=[^ ]*limit=25", by_title),
        (r"ws/2/release-group\?query=", {"release-groups": []}),
        (r"ws/2/artist\?query", lambda url: {"artists": [artist_json(i, artists[i][0], artists[i][1]) for i in search]}),
        (r"ws/2/artist/[^?]+\?", one_artist),
        (r"ws/2/release-group\?artist=", browse),
    ]


def fetchers(artists, search=None, owners=None, discogs=None):
    return Fetchers(mb=FakeFetch(mb_world(artists, search, owners)), wiki=FakeFetch(QUIET_WIKI), discogs=discogs)


def one(root, kind):
    [target] = [t for t in scan([root], kinds=ALL_KINDS).targets if t.kind == kind]
    return target


def artist_proposal(tmp_path, folder, album_folder, fetch):
    make_mp3(tmp_path / folder / album_folder / "01 Opening.mp3", "Opening", folder, album_folder.rsplit(" (", 1)[0], 1, "1985")
    [proposal] = build_proposals(list(scan([tmp_path], kinds=(KIND_ARTIST,)).targets), fetch)
    return proposal


# -- 1. namesake artists ------------------------------------------------------------------------------------------











# -- 2. generic titles identify nobody -------------------------------------------------------------------------------

QUEEN = {"queen": ("Queen", "1970", ["Greatest Hits", "Live", "Sheer Heart Attack"])}


def zyx_library(tmp_path, titles):
    for n, title in enumerate(titles):
        make_mp3(tmp_path / "Zyx Obscure" / f"{title} (199{n})" / "01 a.mp3", "a", "Zyx Obscure", title, 1, f"199{n}")








# -- 3. a best guess is not 'chosen by you' --------------------------------------------------------------------------





def lament_library(tmp_path):
    """Ultravox/Lament (1984) whose files do not match the release's tracklist at all."""
    ultravox_library(tmp_path, with_quartet=False)
    folder = tmp_path / "Ultravox" / "Lament (1984)"
    for i, title in enumerate(["Alpha", "Beta", "Gamma", "Delta"], start=1):
        make_mp3(folder / f"{i:02d} {title}.mp3", title, "Ultravox", "Lament", i, "1984")
    return folder






@pytest.fixture
def cli(monkeypatch):
    """The command line with its services replaced; returns run(capsys, *argv) -> (code, out, err)."""
    from foldercli import cmd_notes
    from foldercli.main import main

    pass  # the conftest isolates the settings
    state = {"fetchers": ultravox_fetchers()}
    monkeypatch.setattr(cmd_notes, "make_music_fetchers", lambda use_discogs: state["fetchers"])

    def run(capsys, *argv):
        code = main(list(argv))
        captured = capsys.readouterr()
        return code, captured.out, captured.err

    run.state = state
    return run


def test_the_cli_include_uncertain_writes_no_wrong_tracklist_and_says_why(tmp_path, capsys, cli):
    lament_library(tmp_path)
    code, out, _err = cli(capsys, "notes", str(tmp_path / "Ultravox" / "Lament (1984)"), "--kind", "album", "--write",
                          "--include-uncertain", "--no-cache")
    assert not (tmp_path / "Ultravox" / "Lament (1984)" / "album.md").exists()
    assert "review" in out and "the best guess did not hold" in out and "track titles match" in out
    assert "from an UNCERTAIN match" not in out


def test_the_cli_batch_write_does_not_write_a_namesake(tmp_path, capsys, cli):
    make_mp3(tmp_path / "Mirage" / "Mirage (1985)" / "01 a.mp3", "a", "Mirage", "Mirage", 1, "1985")
    cli.state["fetchers"] = fetchers({"mir-1": ("Mirage", "1980", ["Mirage"]), "mir-2": ("Mirage", "1982", ["Mirage"])},
                                     search=["mir-1", "mir-2"])
    code, out, _err = cli(capsys, "notes", str(tmp_path), "--kind", "artist", "--write", "--no-cache")
    assert not (tmp_path / "Mirage" / "artist.md").exists()
    assert "two artists with this name hold the album" in out


# -- 7. one timeout is not forever -------------------------------------------------------------------------------------



# -- 8a. an album folder given to the default kind ------------------------------------------------------------------------

def test_an_album_folder_with_the_default_kind_says_so_not_library_root(tmp_path, capsys, cli):
    ultravox_library(tmp_path, with_quartet=False)
    album = tmp_path / "Ultravox" / "Vienna (1980)"
    found = scan([album], kinds=(KIND_ARTIST,))
    message = found.wrong_level_message("add --kind album")
    assert not found.targets and "album folder" in message and "--kind album" in message
    from redactor_common.cli import CliError

    with pytest.raises(CliError) as why:
        cli(capsys, "notes", str(album), "--no-cache")
    assert "album folder" in str(why.value) and "--kind album" in str(why.value) and "library root" not in str(why.value)
    code, out, err = cli(capsys, "notes", str(album), "--kind", "album", "--no-cache")
    assert code == 0 and "would-write" in out


# -- 8b. a collection has no artist.md to replace -----------------------------------------------------------------------------



# -- 8e. one link parser ------------------------------------------------------------------------------------------------------

MBID = "2bf704b3-4ffe-4c3e-9f62-0d44a3a8a6c3"








# -- 4. the Norwegian number words are an option ---------------------------------------------------------------------------------

def test_the_norwegian_number_option_is_a_preference_off_by_default_and_a_cli_flag(tmp_path, capsys, cli):
    from core.music import settings as music_settings
    from core.music.numbers import norwegian_numbers, set_norwegian_numbers

    assert music_settings.norwegian_numbers() is False  # off by default (Preferences > Create Notes in the window)
    ultravox_library(tmp_path / "lib", with_quartet=False)
    try:
        cli(capsys, "notes", str(tmp_path / "lib"), "--kind", "both", "--no-cache", "--norwegian-numbers")
        assert norwegian_numbers() is True
        cli(capsys, "notes", str(tmp_path / "lib"), "--kind", "both", "--no-cache")
        assert norwegian_numbers() is False  # every run sets it from its own option (the preference is off)
        music_settings.set_norwegian_numbers(True)
        cli(capsys, "notes", str(tmp_path / "lib"), "--kind", "both", "--no-cache")
        assert norwegian_numbers() is True  # the preference on: without the flag too
    finally:
        set_norwegian_numbers(False)


# -- 6. the lookup cache (redactor_common 2026-10-16#08) ---------------------------------------------------------------------

