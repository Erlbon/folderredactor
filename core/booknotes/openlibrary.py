"""
core/booknotes/openlibrary.py

Open Library for author notes (D28B: everyone ISFDB does not know). No key; one request a second at most. Only public
author and book data is asked for; nothing about the person running the program is sent.

  OpenLibrary(fetch)           `fetch(url) -> bytes` (the cached one from the engine)
  search_authors(name)         the authors Open Library has under that name, the most prolific first
  author(key)                  one author's dates and Wikidata id
  works(key)                   the author's books (title, first year), oldest first, one per title

The calls are the documented public API: /search/authors.json, /authors/<key>.json, /search.json?author=<key>.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Optional
from urllib.parse import urlencode

from core.version import APP_VERSION
from redactor_common.core.local_db import normalize_words
from redactor_common.core.lookup_client import Throttle, fetch_json, make_default_fetch, throttled

BASE = "https://openlibrary.org"
USER_AGENT = f"folderredactor/{APP_VERSION} ( https://github.com/Erlbon/folderredactor )"
MAX_WORKS = 200
CREDIT = "Books from [Open Library](https://openlibrary.org/)"


class OpenLibraryError(Exception):
    pass


@dataclass
class OlAuthor:
    key: str  # 'OL123A'
    name: str
    birth: str = ""
    death: str = ""
    work_count: int = 0
    top_work: str = ""
    wikidata: str = ""

    @property
    def url(self) -> str:
        return f"{BASE}/authors/{self.key}"

    @property
    def years(self) -> str:
        """'1954-2013', '1954-' (alive or no date of death), '' without a birth year."""
        born, died = _year(self.birth), _year(self.death)
        if not born:
            return ""
        return f"{born}-{died}" if died else f"{born}-"


@dataclass
class OlWork:
    title: str
    year: str = ""


def _year(text: str) -> str:
    found = re.search(r"\b(1\d{3}|20\d{2})\b", text or "")
    return found.group(1) if found else ""


def make_fetch() -> Callable:
    """The real fetch, paced at one request a second for the whole run."""
    return throttled(make_default_fetch(USER_AGENT, timeout=20), Throttle(1.0))


class OpenLibrary:
    def __init__(self, fetch: Callable):
        self._fetch = fetch

    def _get(self, path: str, params: Optional[dict] = None) -> dict:
        url = BASE + path + ("?" + urlencode(params) if params else "")
        data = fetch_json(url, self._fetch, error_cls=OpenLibraryError, source_name="Open Library", ignore_404=True,
                          retry_429=(2.0, 5.0))
        return data if isinstance(data, dict) else {}

    def search_authors(self, name: str) -> list[OlAuthor]:
        data = self._get("/search/authors.json", {"q": name, "limit": 10})
        out = []
        for doc in data.get("docs") or []:
            if not isinstance(doc, dict) or not doc.get("key") or not doc.get("name"):
                continue
            out.append(OlAuthor(str(doc["key"]).rsplit("/", 1)[-1], str(doc["name"]), str(doc.get("birth_date") or ""),
                                str(doc.get("death_date") or ""), int(doc.get("work_count") or 0), str(doc.get("top_work") or "")))
        return sorted(out, key=lambda a: -a.work_count)

    def author(self, key: str) -> Optional[OlAuthor]:
        data = self._get(f"/authors/{key}.json")
        if not data.get("name"):
            return None
        ids = data.get("remote_ids") if isinstance(data.get("remote_ids"), dict) else {}
        return OlAuthor(key, str(data["name"]), str(data.get("birth_date") or ""), str(data.get("death_date") or ""),
                        wikidata=str(ids.get("wikidata") or ""))

    def works(self, key: str) -> list[OlWork]:
        data = self._get("/search.json", {"author": key, "fields": "title,first_publish_year", "sort": "old",
                                          "limit": MAX_WORKS})
        seen: set[str] = set()
        out = []
        for doc in data.get("docs") or []:
            title = str((doc or {}).get("title") or "").strip()
            fold = normalize_words(title)
            if not title or fold in seen:
                continue
            seen.add(fold)
            year = (doc or {}).get("first_publish_year")
            out.append(OlWork(title, str(year) if year else ""))
        return out
