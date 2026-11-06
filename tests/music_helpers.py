"""Shared helpers for the music notes tests: tiny REAL music files of every format the app reads (MP3, FLAC, M4A, Ogg
Vorbis, Opus), built from bytes in tmp_path and tagged through mutagen (no encoder, no binary fixture); a small library
builder; and a fake `fetch(url) -> bytes` that answers from recorded replies (tests/fixtures/notes/recorded.json).

The engine helpers of mp3redactor's tests/notes_helpers.py (ultravox_fetchers, cristina_fetchers, set_kinds) come with the
engine, plan step 8."""

from __future__ import annotations

import base64
import json
import re
import struct
import urllib.error
import urllib.request
from pathlib import Path

import mutagen

FIXTURES = Path(__file__).parent / "fixtures"
RECORDED = json.loads((FIXTURES / "notes" / "recorded.json").read_text(encoding="utf-8"))
SECONDS = 2  # every built file says it is this long (MP3: about one second, from its frames)


class FakeFetch:
    """fetch(url) -> bytes from routes [(regex, payload)]; payload None = HTTP 404, a callable gets the URL. An
    unexpected URL fails the test (nothing here may reach the network)."""

    def __init__(self, routes):
        self.routes = list(routes)
        self.urls: list[str] = []

    def __call__(self, request) -> bytes:
        url = request.full_url if isinstance(request, urllib.request.Request) else request
        self.urls.append(url)
        for pattern, payload in self.routes:
            if re.search(pattern, url):
                if payload is None:
                    raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
                if callable(payload):
                    payload = payload(url)
                return json.dumps(payload).encode("utf-8")
        raise AssertionError(f"unexpected request: {url}")

    def count(self, pattern: str) -> int:
        return sum(1 for u in self.urls if re.search(pattern, u))


# ---- tiny real files -------------------------------------------------------------------------------------------------

def _mp3_bytes(frames: int = 40) -> bytes:
    """MPEG-1 Layer III frames, 128 kbit/s, 44.1 kHz, no padding, no CRC: 417 bytes each."""
    return (b"\xff\xfb\x90\x64" + b"\x00" * 413) * frames


def _flac_bytes() -> bytes:
    """'fLaC' and a STREAMINFO block (the last metadata block): 44.1 kHz, stereo, 16 bit, SECONDS long, no frames."""
    rate, channels, bits = 44100, 2, 16
    packed = (rate << 44) | ((channels - 1) << 41) | ((bits - 1) << 36) | (rate * SECONDS)
    info = struct.pack(">HH", 4096, 4096) + b"\x00" * 6 + packed.to_bytes(8, "big") + b"\x00" * 16
    return b"fLaC" + b"\x80" + len(info).to_bytes(3, "big") + info


def _ogg_bytes(opus: bool = False) -> bytes:
    """An Ogg stream of the identification and comment headers (and a setup header for Vorbis) and one last page whose
    granule position gives the length."""
    from mutagen.ogg import OggPage

    if opus:
        ident = b"OpusHead" + bytes([1, 2]) + struct.pack("<HIhB", 312, 48000, 0, 0)
        heads = [ident, b"OpusTags" + struct.pack("<I", 4) + b"test" + struct.pack("<I", 0)]
        end = 48000 * SECONDS + 312
    else:
        ident = (b"\x01vorbis" + struct.pack("<I", 0) + bytes([2]) + struct.pack("<I", 44100)
                 + struct.pack("<iii", 0, 128000, 0) + bytes([0xB8]) + b"\x01")
        heads = [ident, b"\x03vorbis" + struct.pack("<I", 4) + b"test" + struct.pack("<I", 0) + b"\x01",
                 b"\x05vorbis" + b"\x00" * 8]
        end = 44100 * SECONDS
    pages = []
    for sequence, packets in enumerate([[heads[0]], heads[1:], [b"\x00" * 10]]):
        page = OggPage()
        page.serial, page.sequence, page.packets = 1, sequence, packets
        page.first, page.last = sequence == 0, sequence == 2
        page.position = end if sequence == 2 else 0
        pages.append(page)
    return b"".join(p.write() for p in pages)


def _box(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", 8 + len(payload)) + kind + payload


def _m4a_bytes() -> bytes:
    """ftyp + moov (mvhd and one sound track) + an empty mdat: enough for mutagen to read the length and keep tags."""
    ftyp = _box(b"ftyp", b"M4A " + struct.pack(">I", 0) + b"M4A mp42isom")
    mvhd = _box(b"mvhd", b"\x00" * 4 + struct.pack(">IIII", 0, 0, 1000, 1000 * SECONDS) + b"\x00\x01\x00\x00"
                + b"\x01\x00" + b"\x00" * 70 + struct.pack(">I", 2))
    mdhd = _box(b"mdhd", b"\x00" * 4 + struct.pack(">IIII", 0, 0, 44100, 44100 * SECONDS) + b"\x55\xc4\x00\x00")
    hdlr = _box(b"hdlr", b"\x00" * 8 + b"soun" + b"\x00" * 13)
    moov = _box(b"moov", mvhd + _box(b"trak", _box(b"mdia", mdhd + hdlr)))
    return ftyp + moov + _box(b"mdat", b"")


BUILDERS = {".mp3": _mp3_bytes, ".flac": _flac_bytes, ".m4a": _m4a_bytes, ".ogg": _ogg_bytes,
            ".oga": _ogg_bytes, ".opus": lambda: _ogg_bytes(opus=True)}
FORMATS = (".mp3", ".flac", ".m4a", ".ogg", ".opus")


def make_audio(
    path: Path, title: str = "", artist: str = "", album: str = "", track: int = 0, year: str = "",
    albumartist: str = "", composer: str = "", genre: str = "", disc: int = 0,
) -> Path:
    """A tiny real music file of the format its extension names, with these tags (through mutagen's easy tags)."""
    from core.music.tags import _register_mp4_keys

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(BUILDERS[path.suffix.lower()]())
    _register_mp4_keys()
    audio = mutagen.File(path, easy=True)
    if audio.tags is None:
        audio.add_tags()
    for key, value in (("title", title), ("artist", artist), ("album", album), ("tracknumber", str(track) if track else ""),
                       ("date", year), ("albumartist", albumartist), ("composer", composer), ("genre", genre),
                       ("discnumber", str(disc) if disc else "")):
        if value:
            audio[key] = value
    audio.save()
    return path


def make_mp3(path: Path, *args, **kwargs) -> Path:
    """mp3redactor's name for make_audio (its tests call this one): the format still follows the extension."""
    return make_audio(path, *args, **kwargs)


def embed_cover(path: Path, data: bytes, mime: str = "image/jpeg") -> None:
    """Puts `data` in the file as its front cover, the way each format keeps a picture."""
    from mutagen.flac import FLAC, Picture
    from mutagen.id3 import APIC, ID3
    from mutagen.mp4 import MP4, MP4Cover

    suffix = path.suffix.lower()
    if suffix == ".mp3":
        tags = ID3(path)
        tags.add(APIC(encoding=3, mime=mime, type=3, desc="", data=data))
        tags.save(path)
        return
    if suffix == ".m4a":
        audio = MP4(path)
        kind = MP4Cover.FORMAT_PNG if mime == "image/png" else MP4Cover.FORMAT_JPEG
        audio.tags["covr"] = [MP4Cover(data, imageformat=kind)]
        audio.save()
        return
    picture = Picture()
    picture.type, picture.mime, picture.data = 3, mime, data
    if suffix == ".flac":
        audio = FLAC(path)
        audio.add_picture(picture)
        audio.save()
        return
    audio = mutagen.File(path)
    audio["metadata_block_picture"] = [base64.b64encode(picture.write()).decode("ascii")]
    audio.save()


VIENNA_TRACKS = ["Astradyne", "New Europeans", "Private Lives", "Passing Strangers", "Sleepwalk", "Mr. X",
                 "Western Promise", "Vienna", "All Stood Still"]


def ultravox_library(root: Path, vienna_tracks: int = 3, with_quartet: bool = True) -> Path:
    """root/Ultravox/Vienna (1980)/NN Title.mp3 (+ Quartet (1982)); returns the artist folder."""
    artist = root / "Ultravox"
    for i, title in enumerate(VIENNA_TRACKS[:vienna_tracks], start=1):
        make_audio(artist / "Vienna (1980)" / f"{i:02d} {title}.mp3", title, "Ultravox", "Vienna", i, "1980")
    if with_quartet:
        make_audio(artist / "Quartet (1982)" / "01 Reap the Wild Wind.mp3", "Reap the Wild Wind", "Ultravox", "Quartet", 1, "1982")
        make_audio(artist / "Quartet (1982)" / "02 Hymn.mp3", "Hymn", "Ultravox", "Quartet", 2, "1982")
    return artist
