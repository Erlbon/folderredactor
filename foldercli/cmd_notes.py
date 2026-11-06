"""
foldercli/cmd_notes.py

  notes PATH...   draft the Markdown folder notes Pluteus shows beside a folder: for MUSIC artist.md / album.md / about.md
                  (MusicBrainz, Wikipedia and, with the Discogs token, Discogs), for VIDEO series.md / about.md (TMDB and
                  Wikipedia; needs the TMDB key). One command for both, as mp3redactor's and videoredactor's `notes`
                  were (plan step 10): --media auto (the default) tells them apart by the files' names.

A REPORT by default: every target folder is looked up and listed with how sure the match is and what would be written, and
nothing is written. --write writes the drafts (status: draft in the front matter) of the CONFIDENT matches only. Uncertain
and unmatched folders are listed with the reasons and the candidates, never written (--include-uncertain writes the
engine's best guess for them, marked in the report): they are for a person to decide (Notes > Create Notes in the app has
the review page). A folder that already has artist.md / author.md / series.md / album.md / about.md, in any letter case,
is never touched; a note is never overwritten. The engines are core/music/flow.py and core/video/flow.py.
"""

from __future__ import annotations

import argparse
import logging
import time
from dataclasses import dataclass
from typing import Callable

from core import notes_settings
from core.media_guess import MUSIC, VIDEO, guess_media
from core.notes_engine import build_proposals, summarize, write_proposal
from redactor_common.cli import EXIT_INTERRUPTED, EXIT_OK, EXIT_PARTIAL, CliError, Output, add_common_options
from redactor_common.core.notes import STATE_LEGACY
from redactor_common.core.notes_model import Confidence, NotesSummary, Proposal
from redactor_common.core.notes_timing import lookup_sentence

MUSIC_KIND_WORDS = ("artist", "album", "genre", "both", "all", "collection")
VIDEO_KIND_WORDS = ("series", "movie", "film", "both", "all")
MUSIC_ONLY = ("link", "genres", "discogs", "no_discogs", "no_singles", "norwegian_numbers")
MEDIA_QUESTION = "cannot tell whether {path} is music or video (too few or too mixed files): add --media music or --media video"


def make_cache(args: argparse.Namespace):
    """The disk cache of the lookups (the app's one cache, next to the settings), or None for --no-cache / the setting
    off. The tests replace this one function."""
    if args.no_cache:
        return None
    return notes_settings.default_cache()


def make_music_fetchers(use_discogs: bool):
    """The real music services (Discogs only when asked for and a token is saved); the tests replace this function."""
    from core.music.flow import live_fetchers

    return live_fetchers(use_discogs=use_discogs)


def make_video_fetchers(use_wikipedia: bool):
    """The real video services; the tests replace this function."""
    from core.video.flow import live_fetchers

    fetchers = live_fetchers()
    fetchers.wikipedia = use_wikipedia
    return fetchers


def kind_words(text: str) -> str:
    """--kind as argparse checks it: every word must be a kind of SOME media type (an unknown word is a usage error, exit
    2); whether it fits the media type of this run is checked once that is known."""
    found = [w.strip().lower() for w in text.replace(";", ",").replace("+", ",").split(",") if w.strip()]
    known = set(MUSIC_KIND_WORDS) | set(VIDEO_KIND_WORDS)
    bad = [w for w in found if w not in known]
    if not found or bad:
        raise argparse.ArgumentTypeError(f"invalid kind {', '.join(bad) or text!r}: use {', '.join(MUSIC_KIND_WORDS)} "
                                         f"(music) or {', '.join(VIDEO_KIND_WORDS)} (video)")
    return ",".join(found)


def kind_argument(text: str) -> tuple:
    """Music's --kind words as a tuple of kinds (mp3redactor's kind_argument): 'artist,genre' -> ('artist', 'genre')."""
    from core.music.kinds import parse_kinds

    return kinds_argument(MUSIC_KIND_WORDS, parse_kinds, text)


def kinds_argument(words: tuple, parse: Callable, text: str) -> tuple:
    found = [w.strip().lower() for w in text.replace(";", ",").replace("+", ",").split(",") if w.strip()]
    bad = [w for w in found if w not in words]
    if not found or bad:
        raise CliError(f"invalid kind {', '.join(bad) or text!r}: use {', '.join(words)}, or a list like {words[0]},{words[1]}")
    return parse(found)


def add_notes_parser(sub) -> None:
    parser = sub.add_parser(
        "notes", help="draft folder notes (artist.md, album.md, series.md, about.md)",
        description="Draft the Markdown notes Pluteus shows beside a folder: for music artist.md / album.md / about.md "
                    "from MusicBrainz, Wikipedia and Discogs, checked against the albums really in the folder; for video "
                    "series.md / about.md from TMDB and Wikipedia, checked against the seasons and episodes in the "
                    "folder. A report unless --write is given; --write writes only the confident matches "
                    "(status: draft) and never overwrites an existing note.",
    )
    parser.add_argument("paths", nargs="+", metavar="PATH",
                        help="a library, artist, album, series or film folder (or music / video files, wildcards)")
    parser.add_argument("--media", choices=("auto", MUSIC, VIDEO), default="auto",
                        help="music or video; auto (the default) tells them apart by the file names in the first PATH")
    parser.add_argument("-R", "--no-recurse", action="store_true", help="look only at the folders named, not the folders below them")
    parser.add_argument("--kind", type=kind_words, metavar="KIND", default=None,
                        help="which notes. Music: artist (the default: fast, no album lookups at all), album, genre "
                             "(about.md of a genre or collection folder: about one Wikipedia lookup per folder, no tags "
                             "read), both = artist + album, all = all three, or several joined by commas (artist,genre). "
                             "Video: series (series.md), movie (about.md of a film folder), both (the default)")
    parser.add_argument("--update", action="store_true",
                        help="also list the notes made by an older version of this program (stamped, an older format, "
                             "nobody edited them) and, with --write, replace ONLY those (the old note goes to the Recycle "
                             "Bin; on a network drive there is no Recycle Bin and the old note is kept). Notes edited by a "
                             "person or not made by this program are never touched")
    parser.add_argument("--update-legacy", action="store_true",
                        help="with --update --write: ALSO replace the notes of the first versions (no stamp, so it cannot be "
                             "known whether they were edited; still the Recycle Bin, still never an edited or foreign note)")
    parser.add_argument("--link", action="append", default=[], metavar="FOLDER=URL",
                        help="music: the right page for a folder the search does not find: --link \"Leningrad=https://en."
                             "wikipedia.org/wiki/Leningrad_(band)\" (FOLDER is its name, with or without numbering, or its "
                             "path; URL is a Wikipedia, MusicBrainz or Discogs link, or a MusicBrainz id). Only "
                             "musicbrainz.org, discogs.com, wikipedia.org and wikidata.org are used. Repeatable")
    parser.add_argument("--genres", action="append", default=[], metavar="FOLDER=GENRE,GENRE",
                        help="music: the genres a genre / collection folder covers, when its name does not say so: --genres "
                             "\"1.61 - Ska=Ska,Ska punk\". Every genre is verified on Wikipedia; the note gets one section "
                             "per genre. Repeatable")
    parser.add_argument("--no-cache", action="store_true", help="do not use the disk cache of earlier answers (everything is asked again)")
    parser.add_argument("--no-wikipedia", action="store_true", help="no Wikipedia introduction in the notes (fewer requests)")
    parser.add_argument("--write", action="store_true", help="write the drafts of the confident matches (default: report only)")
    parser.add_argument("--include-uncertain", action="store_true",
                        help="with --write: ALSO write the uncertain matches from the engine's best candidate, as drafts "
                             "(never over an existing note, never for nothing found, never for an unclear level); the "
                             "report marks them 'from an uncertain match' so they can be reviewed afterwards")
    parser.add_argument("-n", "--dry-run", action="store_true", help="never write, even with --write: show what would be written")
    parser.add_argument("--discogs", choices=("always", "fallback", "never"), default=None,
                        help="music: when Discogs is asked (with a token saved): fallback (only when MusicBrainz has no "
                             "verified match or Wikipedia has no introduction), always for every artist (slower), never. "
                             "The default is the app's Preferences (fallback unless changed)")
    parser.add_argument("--no-discogs", action="store_true", help="music: do not use Discogs even when a token is saved (= --discogs never)")
    parser.add_argument("--no-singles", action="store_true",
                        help="music: leave the singles out of the artist note's discography (faster; also on when Preferences "
                             "says so)")
    parser.add_argument("--norwegian-numbers", action="store_true",
                        help="music: also read the Norwegian number words that are everyday English words (en, to, tre, "
                             "fire, fem, ni, ti) as numbers when titles are compared ('Fire' = '4'); also on when "
                             "Preferences says so")
    parser.add_argument("--show-drafts", action="store_true", help="print each draft note (text mode) / include it (JSON)")
    add_common_options(parser)
    parser.set_defaults(handler=run_notes)


# ---- the media types ------------------------------------------------------------------------------------------------

@dataclass
class Media:
    name: str
    scan: Callable
    kinds: tuple
    engine: object
    nothing: str  # the message when nothing is found at all
    no_guess: str  # --include-uncertain, when the engine has no best guess and does not say why


def _music(args: argparse.Namespace) -> Media:
    from core.music import settings as music_settings
    from core.music.flow import NotesEngine, scan
    from core.music.kinds import parse_kinds
    from core.music.link import LinkError

    kinds = kinds_argument(MUSIC_KIND_WORDS, parse_kinds, args.kind) if args.kind else ("artist",)
    if args.norwegian_numbers:
        from core.music.numbers import set_norwegian_numbers

        set_norwegian_numbers(True)
    else:
        music_settings.apply_number_words()
    options = music_settings.engine_options()
    mode = "never" if args.no_discogs else (args.discogs or options["discogs_mode"])
    fetchers = make_music_fetchers(mode != "never")
    fetchers.wikipedia = not args.no_wikipedia
    engine = NotesEngine(fetchers, cache=make_cache(args), discogs_mode=mode,
                         singles=options["singles"] and not args.no_singles)
    for spec in args.link:
        folder, sep, url = spec.partition("=")
        if not sep or not folder.strip():
            raise CliError(f"--link wants FOLDER=URL (got {spec!r})")
        try:
            engine.set_links(folder.strip(), url.strip())
        except LinkError as exc:
            raise CliError(f"--link {folder.strip()!r}: {exc}") from exc
    for spec in args.genres:
        folder, sep, genres = spec.rpartition("=")
        if not sep or not folder.strip() or not [g for g in genres.split(",") if g.strip()]:
            raise CliError(f"--genres wants FOLDER=GENRE,GENRE (got {spec!r})")
        engine.set_genres(folder.strip(), genres.split(","))
    return Media(MUSIC, scan, kinds, engine, "no artist or album folders found", "no usable candidate")


def _video(args: argparse.Namespace) -> Media:
    from core.video import settings as video_settings
    from core.video.flow import NotesEngine, scan
    from core.video.local import ALL_KINDS

    used = [f"--{name.replace('_', '-')}" for name in MUSIC_ONLY if getattr(args, name)]
    if used:
        raise CliError(f"{', '.join(used)}: only for music, and this is video")
    kinds = kinds_argument(VIDEO_KIND_WORDS, video_settings.parse_kinds, args.kind) if args.kind else ALL_KINDS
    engine = NotesEngine(make_video_fetchers(not args.no_wikipedia), cache=make_cache(args))
    return Media(VIDEO, scan, kinds, engine, "no series or film folders found", "no candidate fits name and year on its own")


def which_media(args: argparse.Namespace) -> str:
    """--media, else the guess from the first PATH's file names. A folder with no music or video file at all cannot be
    told apart and has nothing to look up either way: the --kind words decide (series / movie = video), else the kind used
    last time, else music, so the report says why nothing was found. A real mix too close to call asks for --media."""
    if args.media != "auto":
        return args.media
    from pathlib import Path

    from core.media_guess import count_media

    def folder_of(path: str) -> Path:
        p = Path(path)
        return p if p.is_dir() else p.parent

    guesses = {path: guess_media(folder_of(path)) for path in args.paths if folder_of(path).is_dir()}
    if len({g for g in guesses.values() if g}) > 1:  # one run is one media type: a video folder would be scanned as music
        kinds = ", ".join(f"{p} ({g})" for p, g in guesses.items() if g)
        raise CliError(f"the PATHs hold music and video: {kinds}. Run them separately, or add --media")
    folder = folder_of(args.paths[0])
    media = guesses.get(args.paths[0], "") or next((g for g in guesses.values() if g), "")
    if media:
        return media
    if any(count_media(folder)) if folder.is_dir() else False:
        raise CliError(MEDIA_QUESTION.format(path=args.paths[0]))
    words = set((args.kind or "").split(","))
    if words & {"series", "movie", "film"}:
        return VIDEO
    if words & {"artist", "album", "genre", "collection"}:
        return MUSIC
    return notes_settings.last_media() or MUSIC


# ---- the report -----------------------------------------------------------------------------------------------------

def _row(proposal: Proposal, status: str, message: str, show_draft: bool) -> dict:
    row = proposal.to_dict(with_text=show_draft)
    row.update({"status": status, "message": message, "path": proposal.path})
    return row


def _print(out: Output, row: dict, media: str) -> None:
    extra = f"  ({row['message']})" if row["message"] else ""
    out.line(f"{row['status']:<11} {row['kind']:<7} {row['folder']}{extra}")
    if row["status"] in ("review", "no-match"):
        for reason in row["reasons"][:4]:
            out.line(f"             - {reason}")
        if row.get("suggested_levels"):
            out.line(f"             level: {row.get('level', '')}; could be: {', '.join(row['suggested_levels'])}")
        for cand in row["candidates"][:3]:
            what = "local album(s) found" if media == MUSIC else "season(s) fit"
            found = f", {len(cand['hits'])} {what}" if cand["hits"] else ""
            out.line(f"             candidate: {cand['source']} {cand['name']} [{cand['detail']}]{found}")
    for problem in row["problems"][:3]:
        out.line(f"             ! {problem}")
    if row.get("draft"):
        out.line("")
        out.line(row["draft"].rstrip("\n"))
        out.line("")


def _blank_row(status: str, kind: str, folder, message: str) -> dict:
    return {"status": status, "kind": kind, "folder": str(folder), "message": message, "reasons": [], "candidates": [],
            "problems": [], "confidence": "", "path": "", "sources": []}


def run_notes(args: argparse.Namespace, out: Output) -> int:
    media = _music(args) if which_media(args) == MUSIC else _video(args)
    engine = media.engine
    try:
        return _run(args, out, media)
    finally:
        getattr(engine, "close", lambda: None)()


def _run(args: argparse.Namespace, out: Output, media: Media) -> int:
    engine = media.engine
    update = args.update or args.update_legacy
    scan_started = time.perf_counter()
    found = media.scan(args.paths, include_subfolders=not args.no_recurse, kinds=media.kinds, include_outdated=update)
    scan_seconds = time.perf_counter() - scan_started
    for argument in found.missing:
        out.error(f"nothing found for {argument}")
    groupings = list(getattr(found, "groupings", []))
    if media.name == MUSIC:
        from core.music.local import LIBRARY_ROOT_MESSAGE

        wrong = found.wrong_level_message(f"add --kind {found.other_level[0][1] if found.other_level else 'album'} (or --kind both)")
        if wrong:
            raise CliError(wrong)
        if found.only_a_library_root:
            raise CliError(LIBRARY_ROOT_MESSAGE)
    if not found.targets and not found.skipped and not groupings:
        raise CliError(media.nothing)
    dry = args.dry_run or not args.write
    for skipped in found.skipped:
        row = _blank_row("left-alone" if skipped.state else ("skipped" if "folder name" in skipped.reason else "has-note"),
                         skipped.kind, skipped.folder, skipped.reason)
        out.record(row)
        _print(out, row, media.name)
    for grouping in groupings:
        row = _blank_row("grouping", grouping.kind, grouping.folder, f"skipped: {grouping.reason}")
        out.record(row)
        _print(out, row, media.name)

    results = {}
    proposals: list[Proposal] = []
    guessed = 0  # notes written (or that would be) from an uncertain match
    failed = 0
    cancelled = False
    engine.phases.add("scan", scan_seconds, count=len(found.targets))
    if hasattr(engine, "on_status"):
        engine.on_status = out.info  # 'MusicBrainz is busy, waiting 4 s' on stderr
    started = time.perf_counter()
    why_no_guess = getattr(engine, "why_no_guess", lambda proposal: "")

    def handle(proposal: Proposal) -> None:
        nonlocal failed, guessed
        guess = None
        unwritten = ""
        if args.include_uncertain and proposal.confidence == Confidence.UNCERTAIN:
            guess = engine.best_guess(proposal)
            if guess is None:
                unwritten = why_no_guess(proposal) or media.no_guess
            else:
                reasons = list(proposal.reasons)
                proposal = engine.rebuild(proposal, candidate=guess)
                if proposal.writable:
                    proposal.reasons = [f"best guess from an UNCERTAIN match: {guess.name} ({guess.source})",
                                        *(proposal.reasons or reasons[:3])]
                else:  # the best guess keeps every check of the engine: it did not hold, say which
                    unwritten = "the best guess did not hold: " + (proposal.reasons[-1] if proposal.reasons else "no note could be built")
        proposals.append(proposal)
        if guess is not None and not proposal.writable:
            guess = None  # the rebuild did not give a note: it is reported like any other uncertain one
        legacy_held = proposal.is_update and proposal.old_state.kind == STATE_LEGACY and not args.update_legacy
        if proposal.writable and legacy_held and not dry:
            status = "legacy"
            message = ("made by the first versions (no stamp), so it cannot be known whether it was edited: "
                       "not replaced (add --update-legacy to replace it)")
        elif proposal.writable:
            with engine.phases.phase("write", count=0 if dry or legacy_held else 1):
                result = write_proposal(proposal, dry_run=dry or legacy_held)
            results[proposal.path] = result
            verb = "update" if proposal.is_update else "write"
            if result.ok:
                if dry:
                    status = f"would-{verb}"
                    message = ", ".join(proposal.sources) + (f"  [{proposal.old_state.kind}]" if proposal.is_update else "")
                    if legacy_held:
                        message += "  (not replaced without --update-legacy)"
                else:
                    status, message = ("updated" if proposal.is_update else "written"), proposal.path
                    if proposal.is_update:
                        message += "  (the old note is in the Recycle Bin)"
                if guess is not None:
                    guessed += 1
                    message += f"  [from an uncertain match: {guess.name} ({guess.source}) - review it]"
            elif result.status in ("exists", "changed"):
                status, message = "has-note", result.message
            else:
                status, message = "failed", result.message
                failed += 1
        elif proposal.confidence == Confidence.NONE:
            status = "no-match"
            message = "; ".join(proposal.reasons[:1])
            if proposal.problems:
                failed += 1
        else:
            status, message = "review", "uncertain: not written" + (f" ({unwritten})" if unwritten else "")
        out.record(_row(proposal, status, message, args.show_drafts))
        out.records[-1]["from_uncertain"] = guess is not None
        _print(out, out.records[-1], media.name)

    def progress(done: int, total: int, label: str) -> None:
        if label:
            out.progress(done + 1, total, label)

    try:
        build_proposals(found.targets, engine, progress=progress, on_proposal=handle)
    except KeyboardInterrupt:
        cancelled = True
        out.warn("interrupted: the folders not yet looked at were left alone")

    summary: NotesSummary = summarize(proposals, results, cancelled=cancelled)
    summary_dict = summary.to_dict()
    summary_dict.update({"media": media.name, "has_note": len(found.skipped), "groupings": len(groupings), "dry_run": dry,
                         "failed": failed, "from_uncertain": guessed})
    out.line("")
    out.line(
        f"{summary.total} folder(s) looked up: {summary.confident} confident, {summary.uncertain} uncertain, "
        f"{summary.none} not found; {summary.written} written, {summary.would_write} would be written, "
        f"{len(found.skipped)} already had a note."
        + (f" {len(groupings)} alphabetical grouping folder(s) skipped." if groupings else ""))
    if guessed:
        out.line(f"{guessed} note(s) {'would be ' if dry else 'were '}written from an UNCERTAIN match (best guess, still "
                 "status: draft): look at them before you trust them.")
    if summary.uncertain + summary.none > 0:
        out.line("Uncertain and unmatched folders were not written; review them (the candidates are listed above).")
    for problem in summary.problems[:3]:
        out.line(f"! {problem}")
    if update:
        left = [x for x in found.skipped if x.state in ("edited", "foreign")]
        current = [x for x in found.skipped if x.state == "current"]
        out.line(f"{len(left)} notes were left alone: edited by a person or not ours."
                 + (f" {len(current)} are already current." if current else ""))
        summary_dict.update({"left_alone": len(left), "already_current": len(current), "updates": summary.updates})
    elapsed = time.perf_counter() - started
    sentence = lookup_sentence(len(proposals), elapsed, engine.stats.requests, engine.stats.from_cache)
    out.line(sentence)
    if out.json_mode:
        out.info(sentence)  # stderr: the JSON document on stdout stays clean
    summary_dict.update({"requests": engine.stats.requests, "from_cache": engine.stats.from_cache,
                         "elapsed_seconds": round(elapsed, 2), "phases": engine.phases.to_dict()})
    if engine.phases.time_line():
        out.line(engine.phases.time_line())
        if out.json_mode:
            out.info(engine.phases.time_line())
    logging.getLogger("folderredactor.notes").debug("%s | %s", sentence, engine.phases.detail())
    out.finish(summary_dict)
    if cancelled:
        return EXIT_INTERRUPTED
    return EXIT_PARTIAL if failed else EXIT_OK
