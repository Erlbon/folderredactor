"""One `notes` command for music and video (plan step 10): --media auto tells them apart by the file names, a real mix asks
for --media, a folder without any media file goes by the --kind words, music's options are refused for video, and the
music engine's options come from the settings unless a flag says otherwise."""

import json

import pytest

from core.music import settings as music_settings
from foldercli import cmd_notes
from foldercli.main import main
from redactor_common.cli import CliError
from tests.music_helpers import ultravox_fetchers, ultravox_library
from tests.video_helpers import fake_fetchers, make_series, touch


@pytest.fixture(autouse=True)
def services(monkeypatch):
    seen = {}

    def music(use_discogs):
        seen["music"] = use_discogs
        return ultravox_fetchers()

    def video(use_wikipedia):
        seen["video"] = use_wikipedia
        return fake_fetchers(wikipedia=use_wikipedia)

    monkeypatch.setattr(cmd_notes, "make_music_fetchers", music)
    monkeypatch.setattr(cmd_notes, "make_video_fetchers", video)
    monkeypatch.setattr(cmd_notes, "make_cache", lambda args: None)
    return seen


def run_json(capsys, *argv):
    code = main(["notes", *argv, "--json"])
    return code, json.loads(capsys.readouterr().out)


def test_auto_finds_music_and_video_by_their_files(tmp_path, capsys, services):
    ultravox_library(tmp_path / "Music")
    make_series(tmp_path / "Video")
    _code, music = run_json(capsys, str(tmp_path / "Music"))
    _code, video = run_json(capsys, str(tmp_path / "Video"))
    assert music["media"] == "music" and {r["kind"] for r in music["results"]} == {"artist"}
    assert video["media"] == "video" and {r["kind"] for r in video["results"]} == {"series"}
    assert set(services) == {"music", "video"}


def test_a_real_mix_asks_for_media(tmp_path, capsys):
    ultravox_library(tmp_path)
    for n in range(5):
        touch(tmp_path / "Films" / f"Film {n} (2001)" / f"Film.{n}.2001.mkv")
    with pytest.raises(CliError, match="--media music or --media video"):
        main(["notes", str(tmp_path)])
    code, document = run_json(capsys, str(tmp_path), "--media", "music")
    assert code == 0 and document["media"] == "music"


def test_a_folder_without_media_files_goes_by_the_kind_words(tmp_path):
    (tmp_path / "empty").mkdir()
    with pytest.raises(CliError, match="no series or film folders"):
        main(["notes", str(tmp_path), "--kind", "series"])
    with pytest.raises(CliError):
        main(["notes", str(tmp_path), "--kind", "artist"])


def test_musics_options_are_refused_for_video_and_a_kind_of_the_wrong_media_too(tmp_path):
    make_series(tmp_path)
    with pytest.raises(CliError, match="--link, --no-singles: only for music"):
        main(["notes", str(tmp_path), "--link", "x=https://musicbrainz.org/artist/1", "--no-singles"])
    with pytest.raises(CliError, match="invalid kind 'artist'"):
        main(["notes", str(tmp_path), "--kind", "artist"])


def test_the_music_options_come_from_the_settings_unless_a_flag_says_otherwise(tmp_path, capsys, services, monkeypatch):
    ultravox_library(tmp_path)
    made = []
    real = cmd_notes._music

    def spy(args):
        media = real(args)
        made.append((media.engine.discogs_mode, media.engine.singles))
        return media

    monkeypatch.setattr(cmd_notes, "_music", spy)
    run_json(capsys, str(tmp_path))
    music_settings.set_discogs_always(True)
    music_settings.set_skip_singles(True)
    run_json(capsys, str(tmp_path))
    run_json(capsys, str(tmp_path), "--discogs", "fallback")
    run_json(capsys, str(tmp_path), "--no-discogs")
    assert made == [("fallback", True), ("always", False), ("fallback", False), ("never", False)]
    assert services["music"] is False  # --no-discogs: no Discogs client is even made
