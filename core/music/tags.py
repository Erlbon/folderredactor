"""
core/music/tags.py

The tags and the cover of a music file, for the folder notes: MP3, FLAC, M4A (AAC / ALAC), Ogg Vorbis and Opus, all through
mutagen. It replaces mp3redactor's own MP3 reader (core/mp3_file.py, core/scan_service.py, core/cover_art.py), which knew
only MP3. Read-only: this app never changes a tag. Qt-free, never raises, safe in a worker thread.

  read_tags(path)     -> AudioTags   the few fields the notes use, as the file carries them (never normalised)
  load_files(paths)   -> [AudioTags] in order (core/music/local.py's loader)
  read_cover(path)    -> (bytes, MIME type) of the front cover inside the file, or None
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

# What counts as a music file in a folder. '.oga' is Ogg audio by its other name.
AUDIO_EXTENSIONS = frozenset({".mp3", ".flac", ".m4a", ".ogg", ".oga", ".opus"})
FRONT_COVER = 3  # the APIC / FLAC picture type of the front cover


@dataclass
class AudioTags:
    """The fields the notes read, under the names mp3redactor's MP3File used, so core/music/local.py did not change shape."""

    path: str
    title: str = ""
    artist: str = ""
    albumartist: str = ""
    album: str = ""
    track: str = ""  # '3' or '3/10', as the file carries it
    discnumber: str = ""
    year: str = ""  # the date tag as it is ('1980', '1980-07-11')
    composer: str = ""
    genre: str = ""
    duration_seconds: Optional[float] = None
    load_error: str = ""


def is_audio_name(name: str) -> bool:
    return os.path.splitext(name)[1].lower() in AUDIO_EXTENSIONS


_mp4_keys_registered = False


def _register_mp4_keys() -> None:
    """mutagen's easy MP4 interface has no composer key: add it once (the iTunes atom is '\xa9wrt')."""
    global _mp4_keys_registered
    if _mp4_keys_registered:
        return
    from mutagen.easymp4 import EasyMP4Tags

    if "composer" not in EasyMP4Tags.Set:
        EasyMP4Tags.RegisterTextKey("composer", "\xa9wrt")
    _mp4_keys_registered = True


def _first(tags, *keys: str) -> str:
    """The first value of the first key that has one (easy tags hold lists of strings)."""
    if tags is None:
        return ""
    for key in keys:
        try:
            values = tags.get(key)
        except (KeyError, ValueError):
            continue
        if values:
            value = values[0] if isinstance(values, list) else values
            text = str(value).strip()
            if text:
                return text
    return ""


def read_tags(path: str | os.PathLike) -> AudioTags:
    """The tags of one file. A file mutagen cannot read gets `load_error` and empty fields (an MP3 whose audio is
    damaged still gives its ID3 tags)."""
    import mutagen

    _register_mp4_keys()
    path = os.fspath(path)
    out = AudioTags(path=path)
    audio = None
    try:
        audio = mutagen.File(path, easy=True)
    except Exception as exc:  # noqa: BLE001 -- mutagen raises many kinds; a bad file is said, never a traceback
        out.load_error = f"{type(exc).__name__}: {exc}"
    tags = getattr(audio, "tags", None) if audio is not None else None
    if audio is None and Path(path).suffix.lower() == ".mp3":
        try:
            from mutagen.easyid3 import EasyID3

            tags = EasyID3(path)
            out.load_error = ""
        except Exception as exc:  # noqa: BLE001
            out.load_error = out.load_error or f"{type(exc).__name__}: {exc}"
    elif audio is None and not out.load_error:
        out.load_error = "not a music file mutagen can read"
    out.title = _first(tags, "title")
    out.artist = _first(tags, "artist")
    out.albumartist = _first(tags, "albumartist", "album artist", "album_artist")
    out.album = _first(tags, "album")
    out.track = _first(tags, "tracknumber", "track")
    out.discnumber = _first(tags, "discnumber", "disc")
    out.year = _first(tags, "date", "originaldate", "year")
    out.composer = _first(tags, "composer")
    out.genre = _first(tags, "genre")
    length = getattr(getattr(audio, "info", None), "length", None)
    out.duration_seconds = float(length) if length else None
    return out


def load_files(paths: Iterable[str | os.PathLike]) -> list[AudioTags]:
    return [read_tags(p) for p in paths]


# ---- covers ----------------------------------------------------------------------------------------------------------

def _sniff_mime(data: bytes) -> str:
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


def _pick(pictures: list, type_of) -> Optional[object]:
    """The front cover when there is one, else the first picture."""
    usable = [p for p in pictures if p is not None]
    for picture in usable:
        if type_of(picture) == FRONT_COVER:
            return picture
    return usable[0] if usable else None


def read_cover(path: str | os.PathLike) -> Optional[tuple[bytes, str]]:
    """(image bytes, MIME type) of the cover stored inside the file, or None when it has none or cannot be read."""
    import mutagen

    try:
        audio = mutagen.File(os.fspath(path))  # not easy: the pictures are in the raw tags
    except Exception:  # noqa: BLE001 -- an unreadable file shows no cover
        audio = None
    if audio is None:
        if Path(path).suffix.lower() == ".mp3":
            return _id3_cover(path)
        return None
    try:
        from mutagen.flac import FLAC, Picture
        from mutagen.mp4 import MP4, MP4Cover

        if isinstance(audio, FLAC):
            picture = _pick(list(audio.pictures), lambda p: p.type)
            return (bytes(picture.data), picture.mime or _sniff_mime(picture.data)) if picture and picture.data else None
        if isinstance(audio, MP4):
            covers = list((audio.tags or {}).get("covr") or [])
            if not covers:
                return None
            data = bytes(covers[0])
            mime = "image/png" if getattr(covers[0], "imageformat", None) == MP4Cover.FORMAT_PNG else _sniff_mime(data)
            return data, mime
        tags = audio.tags
        if tags is None:
            return None
        if hasattr(tags, "getall"):  # ID3 (MP3, and ID3 in other containers)
            frame = _pick(tags.getall("APIC"), lambda f: f.type)
            return (bytes(frame.data), frame.mime or _sniff_mime(frame.data)) if frame and frame.data else None
        # Vorbis comments (Ogg Vorbis, Opus): METADATA_BLOCK_PICTURE, base64 of a FLAC picture block
        pictures = []
        for raw in tags.get("metadata_block_picture") or []:
            try:
                pictures.append(Picture(base64.b64decode(raw)))
            except Exception:  # noqa: BLE001 -- one broken picture does not hide the next
                continue
        picture = _pick(pictures, lambda p: p.type)
        if picture is not None and picture.data:
            return bytes(picture.data), picture.mime or _sniff_mime(picture.data)
        for raw in tags.get("coverart") or []:  # the old, unofficial form
            try:
                data = base64.b64decode(raw)
            except Exception:  # noqa: BLE001
                continue
            if data:
                return data, _sniff_mime(data)
    except Exception:  # noqa: BLE001
        return None
    return None


def _id3_cover(path) -> Optional[tuple[bytes, str]]:
    """The cover of an MP3 whose audio mutagen could not read (its ID3 tag may still be fine)."""
    try:
        from mutagen.id3 import ID3

        frame = _pick(ID3(os.fspath(path)).getall("APIC"), lambda f: f.type)
    except Exception:  # noqa: BLE001
        return None
    return (bytes(frame.data), frame.mime or _sniff_mime(frame.data)) if frame and frame.data else None
