"""Find the catalogue PDFs on a manufacturer's website. Pure logic: the page fetcher is passed in, so tests never touch the network."""
from __future__ import annotations

from collections import deque
from collections.abc import Callable, Iterator
from html.parser import HTMLParser
from typing import NamedTuple
from urllib.parse import urldefrag, urljoin, urlparse
from urllib.robotparser import RobotFileParser

MAX_PAGES = 200  # web pages looked at in one crawl: a safety net against endless link trees


class Page(NamedTuple):
    url: str
    content_type: str
    body: bytes


Fetch = Callable[[str], Page | None]  # None when the page cannot be read or the site asks not to be crawled


class Found(NamedTuple):
    pdf: str
    found_on: str


class LinkFinder(HTMLParser):
    """Collects the target of every <a href>."""

    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self.hrefs.extend(value for name, value in attrs if name == "href" and value)


def links_on(html: str, base: str) -> list[str]:
    """Every link of a page as an absolute web address without its #fragment."""
    finder = LinkFinder()
    finder.feed(html)
    absolute = (urldefrag(urljoin(base, href))[0] for href in finder.hrefs)
    return [url for url in absolute if urlparse(url).scheme in ("http", "https")]


def is_pdf(url: str) -> bool:
    return urlparse(url).path.lower().endswith(".pdf")


def same_site(url: str, root: str) -> bool:
    """True when both addresses are on one website; www. is ignored."""
    host = lambda u: (urlparse(u).hostname or "").removeprefix("www.")
    return host(url) == host(root)


def wanted(url: str, include: list[str], exclude: list[str]) -> bool:
    """A PDF is kept when its address says at least one include word (if any are given) and none of the exclude words."""
    low = url.lower()
    if exclude and any(word.lower() in low for word in exclude):
        return False
    return not include or any(word.lower() in low for word in include)


def allowed_by(robots_text: str | None, url: str, agent: str) -> bool:
    """What the site's robots.txt says about this address. A site with no robots.txt allows everything."""
    if robots_text is None:
        return True
    rules = RobotFileParser()
    rules.parse(robots_text.splitlines())
    return rules.can_fetch(agent, url)


def crawl(start_urls: list[str], fetch: Fetch, include: list[str], exclude: list[str], depth: int, max_pdfs: int) -> Iterator[Found]:
    """Breadth-first walk over pages of the start sites, yielding each wanted PDF once with the page that links to it."""
    queue = deque((url, 0) for url in start_urls)
    seen_pages, seen_pdfs = set(start_urls), set()
    while queue and len(seen_pages) <= MAX_PAGES and len(seen_pdfs) < max_pdfs:
        url, level = queue.popleft()
        page = fetch(url)
        if page is None or "html" not in page.content_type.lower():
            continue
        for link in links_on(page.body.decode("utf-8", errors="replace"), page.url):
            if is_pdf(link):
                if link not in seen_pdfs and wanted(link, include, exclude) and len(seen_pdfs) < max_pdfs:
                    seen_pdfs.add(link)
                    yield Found(link, page.url)
            elif level < depth and link not in seen_pages and any(same_site(link, s) for s in start_urls):
                seen_pages.add(link)
                queue.append((link, level + 1))
