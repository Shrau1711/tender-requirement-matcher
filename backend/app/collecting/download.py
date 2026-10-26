"""Fetching web addresses politely, and saving a downloaded PDF into a manufacturer's folder with a record of where it came from."""
from __future__ import annotations

import hashlib
import re
import time
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path
from typing import NamedTuple
from urllib.parse import unquote, urlparse

from app.collecting.crawl import Fetch, Page, allowed_by

AGENT = "tender-matcher-catalogue-crawler (research use; contact the repo owner)"
DELAY_SECONDS = 1.5  # between two requests to the same site: a manufacturer's website is not ours to hammer
TIMEOUT_SECONDS = 30
MAX_BYTES = 80_000_000  # a catalogue larger than this is skipped


class Saved(NamedTuple):
    url: str
    file: str
    sha256: str
    bytes: int
    date_downloaded: str
    found_on: str


def polite_fetcher(delay: float = DELAY_SECONDS, sleep=time.sleep) -> Fetch:
    """A fetch function that waits between requests, obeys each site's robots.txt, and returns None on any failure."""
    robots: dict[str, str | None] = {}

    def get(url: str) -> tuple[str, bytes] | None:
        request = urllib.request.Request(url, headers={"User-Agent": AGENT})
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                body = response.read(MAX_BYTES + 1)
                return (response.headers.get("Content-Type", ""), body) if len(body) <= MAX_BYTES else None
        except (urllib.error.URLError, TimeoutError, ValueError):
            return None

    def robots_for(url: str) -> str | None:
        root = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
        if root not in robots:
            answer = get(f"{root}/robots.txt")
            robots[root] = answer[1].decode("utf-8", errors="replace") if answer else None
        return robots[root]

    def fetch(url: str) -> Page | None:
        if not allowed_by(robots_for(url), url, AGENT):
            return None
        sleep(delay)
        answer = get(url)
        return Page(url, answer[0], answer[1]) if answer and answer[1] else None

    return fetch


def file_name(url: str) -> str:
    """A safe file name from the last part of the address, e.g. CR-databooklet%2050Hz.pdf -> CR-databooklet_50Hz.pdf."""
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", unquote(Path(urlparse(url).path).name)).strip("_")
    return name or "catalogue.pdf"


def save_pdf(url: str, found_on: str, body: bytes, folder: Path, known: set[str], today: date | None = None) -> Saved | None:
    """Writes the PDF unless it is not a PDF or the same content is already known (by hash). Returns the record, or None."""
    digest = hashlib.sha256(body).hexdigest()
    if not body.startswith(b"%PDF") or digest in known:
        return None
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / file_name(url)
    if target.exists():  # same name, different content: keep both
        target = target.with_name(f"{target.stem}_{digest[:8]}{target.suffix}")
    target.write_bytes(body)
    known.add(digest)
    return Saved(url, target.name, digest, len(body), (today or datetime.now().astimezone().date()).isoformat(), found_on)
