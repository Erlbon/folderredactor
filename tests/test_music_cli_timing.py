"""How long a notes run takes, said plainly on the command line: the elapsed time, the requests and the cache hits, in the
JSON document and on stderr."""

import json

from tests.music_helpers import ultravox_fetchers, ultravox_library


def test_cli_reports_elapsed_requests_and_cache_hits_in_json_and_on_stderr(tmp_path, capsys, monkeypatch):
    from foldercli import cmd_notes
    from foldercli.main import main

    pass  # the conftest isolates the settings
    fetchers = ultravox_fetchers()
    monkeypatch.setattr(cmd_notes, "make_music_fetchers", lambda use: fetchers)
    ultravox_library(tmp_path)
    code = main(["notes", str(tmp_path), "--json", "--no-cache"])
    captured = capsys.readouterr()
    document = json.loads(captured.out)
    assert code == 0 and document["requests"] == 5 and document["from_cache"] == 0
    assert isinstance(document["elapsed_seconds"], float) and document["elapsed_seconds"] >= 0
    assert "Looked up 1 folder in 0:00:0" in captured.err and "(5 requests, 0 from the cache)" in captured.err
