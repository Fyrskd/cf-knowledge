#!/usr/bin/env python3
"""Build an evidence-backed Codeforces problem/knowledge index.

The crawler deliberately keeps raw sources and provenance.  It does not invent
editorials: a problem is marked as missing or incomplete unless an editorial
URL and usable source text were found.  ``editorial_status`` describes the
source kind (official/community/associated), while ``editorial_quality``
describes whether the fetched section is complete, partial, or URL-only.

Examples:
  python tools/cf_knowledge_index.py crawl --since 2024-09-05 --until 2026-09-06
  python tools/cf_knowledge_index.py index --data .
  python tools/cf_knowledge_index.py all --since 2024-09-05 --out .

Only the Python standard library is required.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import html
import json
import re
import signal
import sys
import threading
import time
from collections import Counter, defaultdict
from html.parser import HTMLParser
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Callable, Iterable, Iterator
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urljoin, urlparse
from urllib.request import HTTPCookieProcessor, Request, build_opener


PROJECT_ROOT = Path(__file__).resolve().parents[1]
API = "https://codeforces.com/api"
STATEMENT_MIRROR = "https://cf-problemset.herokuapp.com/contest/{contest}/{index}/"
CF_PROBLEM = "https://codeforces.com/contest/{contest}/problem/{index}"
CF_CONTEST = "https://codeforces.com/contest/{contest}"
TUTORIAL_ENDPOINT = "https://codeforces.com/data/problemTutorial"
USER_AGENT = "cf-knowledge-index/1.0 (evidence-backed training tool)"
MAX_FAILURE_LOG = 500
BLOG_RE = re.compile(r"(?:https?://codeforces\.com)?/blog/entry/(\d+)", re.I)
PROBLEM_HREF_RE = re.compile(
    r"<a\b[^>]*href=[\"'](?:https?://codeforces\.com)?/contest/(\d+)/problem/([^\"'/?#]+)",
    re.I,
)
PROBLEM_CODE_RE = re.compile(
    r"problemcode\s*=\s*[\"'](\d+)([A-Z][0-9]*)[\"']", re.I
)
OFFICIAL_EDITORIAL_RE = re.compile(
    r"\b(editorial|tutorial|official\s+solution(?:s)?)\b", re.I
)
COMMUNITY_EDITORIAL_RE = re.compile(
    r"\b(alternative|discussion|with\s+hints?|video\s+editorial|unofficial)\b", re.I
)
TUTORIAL_LABEL_RE = re.compile(
    r"\b(tutorial|editorial|discussion|hint(?:s)?|solution(?:s)?)\b", re.I
)
TUTORIAL_LOADING_RE = re.compile(r"\btutorial\s+is\s+loading\s*\.{0,3}", re.I)
EDITORIAL_META_LINE_RE = re.compile(
    r"^(?:author|developer|development|preparation|prepared by|hinter|"
    r"editorialist|problem credits?|first blood|submission|my submission|"
    r"special thanks|credits?|idea by|solution by|editorial by)"
    r"\s*:?\s*.*$",
    re.I,
)
EDITORIAL_TITLE_RE = re.compile(
    r"^(?:\d{3,5}[A-Z][0-9]{0,2}|[A-H](?:[12])?)\s*[-:.)—–]\s*.+$",
    re.I,
)
EDITORIAL_SECTION_RE = re.compile(
    r"^(?:hint(?:\s*#?\s*[0-9A-Z]+)?|hints|solution|tutorial|editorial|"
    r"proof|analysis|implementation|code(?:\s*\([^)]*\))?|note|extra|"
    r"approach|idea|complexity)(?:\s*#?\s*[0-9A-Z]+)?\s*:?[ \t]*$",
    re.I,
)
EDITORIAL_RATING_RE = re.compile(
    r"(?:\[likes:|^rate(?:\s+the)?\s+problem\b|^quality\b|^difficulty\b|"
    r"^rate\s+this\s+problem\b|"
    r"^(?:amazing|excellent|epic|trivial|impossible|horrible|bad|average|"
    r"good)\s+problem\b|^didn['’]?t\s+solve\b)",
    re.I,
)
EDITORIAL_CODE_START_RE = re.compile(
    r"^(?://|/\*|\*/|#\s*(?:include|define|if|endif)\b|#include\b|"
    r"using\s+namespace\b|using\s+(?:ll|i64|int|std)\b|import\s+\w|from\s+\w+\s+import\b|"
    r"(?:public\s+)?class\s+\w+|struct\s+\w+|template\s*<|"
    r"(?:const|constexpr|typedef)\s+(?:int|long|ll|double|char|bool)\b|"
    r"int\s+main\s*\(|(?:void|int|long|bool)\s+solve\s*\(|"
    r"def\s+\w+\s*\(|function\s+\w+\s*\(|"
    r"(?:for|while|if|switch)\s*\(|(?:return|cin|cout|scanf|printf)\b|"
    r"(?:vector|array|map|set|unordered_map|priority_queue)\s*<|"
    r"(?:int|long\s+long|ll|double|float|char|bool|string)\s+[A-Za-z_]\w*"
    r"(?:\s*\[[^\]]+\])?\s*(?:=|;|,))",
)
EDITORIAL_CODE_HEADING_RE = re.compile(
    r"^(?:code|implementation|source\s+code|plaintext|source)"
    r"(?:\s*\([^)]*\))?\s*:?[ \t]*$|"
    r"^solution\s*\((?:c\+\+|cpp|python|java|rust|go|kotlin|pypy)[^)]*\)"
    r"\s*:?[ \t]*$",
    re.I,
)
EDITORIAL_EXPLANATION_CUE_RE = re.compile(
    r"\b(?:because|therefore|thus|hence|observe|observation|note that|"
    r"consider|suppose|assume|let\s+\w|if\b|when\b|otherwise|"
    r"choose|construct|count|calculate|find|solve|pattern|prove|proof|lemma|invariant|"
    r"complexity|algorithm|greedy|dynamic programming|\bdp\b|"
    r"binary search|sort(?:ing)?|minimum|maximum|answer|possible|"
    r"need to|can be|we can|we need|it follows|equivalent|gcd|lcm|"
    r"parity|matching|tree|graph|substring|subsequence)\b",
    re.I,
)
EDITORIAL_WEAK_RE = re.compile(
    r"\b(?:my solution|check what i did|t(?:le|ime limit exceeded)\s+solution|"
    r"video editorial|chat qn?a|tutorial will be added|first official\s+\(?human\)?\s+solve)\b",
    re.I,
)


class Fetcher:
    def __init__(self, delay: float = 0.7, retries: int = 3, timeout: int = 30):
        self.delay, self.retries, self.timeout = delay, retries, timeout
        self.last = 0.0
        # The Codeforces blog page loads tutorial bodies through a CSRF-
        # protected POST endpoint.  Keep one cookie jar so the initial GET
        # and subsequent POSTs share the same session.
        self.opener = build_opener(HTTPCookieProcessor(CookieJar()))

    def get(self, url: str) -> bytes:
        wait = self.delay - (time.monotonic() - self.last)
        if wait > 0:
            time.sleep(wait)
        err = None
        for attempt in range(self.retries):
            try:
                req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/json,*/*"})
                with request_hard_timeout(self.timeout, url):
                    with self.opener.open(req, timeout=self.timeout) as response:
                        data = response.read()
                self.last = time.monotonic()
                return data
            except (HTTPError, URLError, TimeoutError) as exc:
                err = exc
                time.sleep(min(2 ** attempt, 8))
        self.last = time.monotonic()
        raise RuntimeError(f"fetch failed: {url}: {err}")

    def post(self, url: str, form: dict[str, str], headers: dict[str, str] | None = None) -> bytes:
        """POST a form while reusing the fetcher's rate limit and cookies."""
        wait = self.delay - (time.monotonic() - self.last)
        if wait > 0:
            time.sleep(wait)
        err = None
        payload = urlencode(form).encode("utf-8")
        merged = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            **(headers or {}),
        }
        for attempt in range(self.retries):
            try:
                req = Request(url, data=payload, headers=merged, method="POST")
                with request_hard_timeout(self.timeout, url):
                    with self.opener.open(req, timeout=self.timeout) as response:
                        data = response.read()
                self.last = time.monotonic()
                return data
            except (HTTPError, URLError, TimeoutError) as exc:
                err = exc
                time.sleep(min(2 ** attempt, 8))
        self.last = time.monotonic()
        raise RuntimeError(f"post failed: {url}: {err}")


@contextlib.contextmanager
def request_hard_timeout(seconds: int, url: str) -> Iterator[None]:
    """Interrupt a response read that ignores the socket timeout."""
    if (
        seconds <= 0
        or not hasattr(signal, "SIGALRM")
        or threading.current_thread() is not threading.main_thread()
    ):
        yield
        return

    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.getitimer(signal.ITIMER_REAL)

    def handle_timeout(signum: int, frame: object) -> None:
        raise TimeoutError(f"request timed out after {seconds}s: {url}")

    signal.signal(signal.SIGALRM, handle_timeout)
    signal.setitimer(signal.ITIMER_REAL, float(seconds))
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer[0] > 0:
            signal.setitimer(signal.ITIMER_REAL, *previous_timer)


class TextParser(HTMLParser):
    """Small HTML-to-text parser; keeps headings and code blocks readable."""

    BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "pre"}
    SKIP = {"script", "style", "svg", "noscript"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        if tag in self.BLOCK and self.parts and not self.parts[-1].endswith("\n"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        if tag in self.BLOCK and self.parts and not self.parts[-1].endswith("\n"):
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)

    def text(self) -> str:
        s = html.unescape("".join(self.parts))
        s = re.sub(r"[ \t]+", " ", s)
        s = re.sub(r"\n[ \t]+", "\n", s)
        s = re.sub(r"\n{3,}", "\n\n", s)
        return s.strip()


class ScopedTextParser(TextParser):
    """Extract text from the first element carrying a target CSS class."""

    VOID_TAGS = {
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr",
    }

    def __init__(self, target_class: str):
        super().__init__()
        self.target_class = target_class
        self.depth = 0
        self.target_depth: int | None = None

    def handle_starttag(self, tag, attrs):
        classes = set(str(dict(attrs).get("class") or "").split())
        if self.target_depth is None and self.target_class in classes:
            self.target_depth = self.depth
        if self.target_depth is not None:
            if tag in self.BLOCK and self.parts and not self.parts[-1].endswith("\n"):
                self.parts.append("\n")
            if tag not in self.VOID_TAGS:
                self.depth += 1

    def handle_startendtag(self, tag, attrs):
        if self.target_depth is not None and tag in self.BLOCK and self.parts and not self.parts[-1].endswith("\n"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if self.target_depth is None:
            return
        if tag in self.BLOCK and self.parts and not self.parts[-1].endswith("\n"):
            self.parts.append("\n")
        if tag not in self.VOID_TAGS:
            self.depth -= 1
            if self.depth == self.target_depth:
                self.target_depth = None

    def handle_data(self, data):
        if self.target_depth is not None:
            self.parts.append(data)


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self.current: str | None = None
        self.buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href")
            self.current, self.buf = href, []

    def handle_data(self, data):
        if self.current is not None:
            self.buf.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.current is not None:
            self.links.append((self.current, re.sub(r"\s+", " ", "".join(self.buf)).strip()))
            self.current, self.buf = None, []


class TutorialLinkParser(HTMLParser):
    """Collect links in the mirror page's ``Tutorials`` section only."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_heading = False
        self.heading: list[str] = []
        self.section: str | None = None
        self.current: str | None = None
        self.buf: list[str] = []
        self.links: list[tuple[str, str]] = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.in_heading = True
            self.heading = []
        elif tag == "a":
            self.current = dict(attrs).get("href")
            self.buf = []

    def handle_data(self, data):
        if self.in_heading:
            self.heading.append(data)
        if self.current is not None:
            self.buf.append(data)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"} and self.in_heading:
            heading = re.sub(r"\s+", " ", "".join(self.heading)).strip().lower()
            self.section = "tutorials" if heading == "tutorials" else None
            self.in_heading = False
        elif tag == "a" and self.current is not None:
            label = re.sub(r"\s+", " ", "".join(self.buf)).strip()
            if self.section == "tutorials" and self.current:
                self.links.append((self.current, label))
            self.current, self.buf = None, []


def parse_date(s: str) -> dt.datetime:
    return dt.datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc)


def iso_date(seconds: int | None) -> str | None:
    return dt.datetime.fromtimestamp(seconds, dt.timezone.utc).date().isoformat() if seconds else None


def clean_text(raw: bytes | str) -> str:
    p = TextParser()
    p.feed(raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw)
    return p.text()


STATEMENT_METADATA_MARKERS = (
    "codeforces search problemset",
    "codeforces search problems",
    "back to search problems",
    "solutions are presented as using the least memory",
)
STATEMENT_CUES = (
    "given ",
    "you are given",
    "input",
    "output",
    "for each test",
    "constraints",
    "determine",
    "calculate",
    "find ",
    "what is",
    " teams",
    "this is",
    "integer",
    " choose ",
    " operation",
    "every ",
    "vertex",
)


def is_problem_statement(text: str) -> bool:
    """Reject mirror navigation/submission pages masquerading as statements."""
    normalized = re.sub(r"\s+", " ", str(text or "")).strip().lower()
    if len(normalized) < 80:
        return False
    if sum(cue in normalized for cue in STATEMENT_CUES) >= 1:
        # Historical mirror captures may include navigation after a real
        # statement.  The problem-language cue takes precedence over that
        # harmless trailing metadata.
        return True
    return not any(marker in normalized for marker in STATEMENT_METADATA_MARKERS)


def parse_mirror_problem(raw: bytes) -> dict:
    """Extract fields from cf-problemset's single-problem mirror page."""
    source = raw.decode("utf-8", "replace")
    lp = LinkParser(); lp.feed(source)
    tlp = TutorialLinkParser(); tlp.feed(source)
    tp = TextParser(); tp.feed(source)
    text = tp.text()
    # The mirror page puts the statement in the last table between the
    # ``Problems`` and ``Tutorials`` headings.  Extract that table so the
    # saved statement does not include navigation or thousands of submissions.
    statement = ""
    phead = re.search(r"<h[1-6][^>]*>\s*Problems\s*</h[1-6]>", source, re.I)
    thead = re.search(r"<h[1-6][^>]*>\s*Tutorials\s*</h[1-6]>", source, re.I)
    if phead and thead and phead.end() < thead.start():
        region = source[phead.end():thead.start()]
        table_start = region.rfind("<table")
        table_end = region.find("</table>", table_start)
        if table_start >= 0 and table_end >= table_start:
            statement = clean_text(region[table_start:table_end + len("</table>")])
    if not is_problem_statement(statement):
        # Older mirror pages put the statement in an explicit table.  Some
        # newer pages contain only contest metadata and submissions; never
        # fall back to that navigation text as a fake statement.
        statement = text if is_problem_statement(text) else ""
    return {
        "mirror_text": statement,
        "statement_quality": "available" if statement else "missing",
        "mirror_links": lp.links,
        "tutorial_links": tlp.links,
    }


def parse_codeforces_problem(raw: bytes) -> dict:
    """Extract the official ``problem-statement`` block when it is reachable."""
    parser = ScopedTextParser("problem-statement")
    parser.feed(raw.decode("utf-8", "replace"))
    statement = parser.text()
    if not is_problem_statement(statement):
        statement = ""
    return {
        "mirror_text": statement,
        "statement_quality": "available" if statement else "missing",
        "mirror_links": [],
        "tutorial_links": [],
    }


def statement_source_candidates(record: dict) -> list[tuple[str, str, Callable[[bytes], dict]]]:
    """Return ordered statement sources, without duplicating a URL."""
    contest_id = record.get("contest_id")
    index = record.get("index")
    mirror_url = str(
        record.get("statement_url")
        or STATEMENT_MIRROR.format(contest=contest_id, index=index)
    )
    problem_url = str(
        record.get("problem_url")
        or CF_PROBLEM.format(contest=contest_id, index=index)
    )
    candidates = [
        ("cf-problemset-mirror", mirror_url, parse_mirror_problem),
        ("codeforces-problem-page", problem_url, parse_codeforces_problem),
    ]
    seen: set[str] = set()
    unique: list[tuple[str, str, Callable[[bytes], dict]]] = []
    for item in candidates:
        if item[1] and item[1] not in seen:
            seen.add(item[1])
            unique.append(item)
    return unique


def fetch_statement_with_fallback(fetcher: Fetcher, record: dict) -> dict:
    """Fetch a verified statement while preserving every source attempt."""
    attempts: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []
    statement_links: list[tuple[str, str]] = []
    tutorial_links: list[tuple[str, str]] = []
    for source, url, parser in statement_source_candidates(record):
        try:
            raw = fetcher.get(url)
            parsed = parser(raw)
            statement_links.extend(parsed.get("mirror_links", []))
            tutorial_links.extend(parsed.get("tutorial_links", []))
            if parsed.get("statement_quality") == "available":
                attempts.append({"source": source, "url": url, "status": "available"})
                return {
                    "statement_text": parsed["mirror_text"],
                    "statement_quality": "available",
                    "statement_links": statement_links,
                    "tutorial_links": tutorial_links,
                    "statement_source": source,
                    "statement_source_url": url,
                    "statement_source_attempts": attempts,
                    "statement_raw": raw,
                    "errors": errors,
                }
            attempts.append({"source": source, "url": url, "status": "no_statement"})
        except Exception as exc:
            attempts.append({"source": source, "url": url, "status": "error"})
            errors.append({"url": url, "error": str(exc)})
    return {
        "statement_text": "",
        "statement_quality": "missing",
        "statement_links": statement_links,
        "tutorial_links": tutorial_links,
        "statement_source": None,
        "statement_source_url": None,
        "statement_source_attempts": attempts,
        "statement_raw": None,
        "errors": errors,
    }


def apply_statement_result(record: dict, result: dict) -> None:
    """Apply a fallback result without discarding existing Tutorial evidence."""
    record["statement_source_attempts"] = result["statement_source_attempts"]
    if result.get("statement_source"):
        record["statement_text"] = result["statement_text"]
        record["statement_quality"] = result["statement_quality"]
        record["statement_source"] = result["statement_source"]
        record["statement_source_url"] = result["statement_source_url"]
    elif not is_problem_statement(str(record.get("statement_text") or "")):
        record["statement_text"] = ""
        record["statement_quality"] = "missing"
        record["statement_source"] = None
        record["statement_source_url"] = None
    if result.get("statement_links"):
        record["statement_links"] = result["statement_links"]
    if result.get("tutorial_links"):
        record["tutorial_links"] = tutorial_links_for_record(result)
    raw = result.get("statement_raw")
    if raw is not None:
        record["statement_textsha256"] = hashlib.sha256(raw).hexdigest()


def select_tutorial_link(links: Iterable) -> tuple[str | None, str | None, str]:
    """Select a usable tutorial/editorial URL from mirror links.

    Codeforces blog entries are preferred.  Other links are retained as
    ``related`` provenance, but are not silently treated as official CF
    editorials.
    """
    candidates = []
    for item in links or []:
        if isinstance(item, dict):
            h, l = item.get("url"), item.get("label", "")
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            h, l = item[0], item[1]
        else:
            continue
        if h:
            candidates.append((h, l))
    # When reading records produced by an older version, ``statement_links``
    # contains every anchor on the mirror page (including submissions).  Do
    # not accidentally select a submission or problem URL as a tutorial.
    candidates = [
        (h, l) for h, l in candidates
        if canonical_blog_url(h)
        or re.search(r"\b(tutorial|editorial|discussion|hint|solution)\b", l or "", re.I)
    ]
    if not candidates:
        return None, None, "missing"
    for href, label in candidates:
        normalized = canonical_blog_url(href)
        if normalized:
            return normalized, label, "codeforces-blog"
    href, label = candidates[0]
    return href, label, "external"


def apply_contest_editorial_fallback(
    record: dict, url: str | None, discovery: str | None = None
) -> None:
    """Use a contest-level editorial URL when the mirror has no Tutorial link.

    A mapping/search result identifies one blog for the whole contest, while
    the mirror normally provides the stronger per-problem link.  This helper
    only fills an absent link so a mirror-discovered Tutorial always wins.
    The subsequent blog splitter is responsible for attaching a section to
    the individual problem; an unidentifiable section remains URL-only.
    """
    if record.get("tutorial_url") or not url:
        return
    normalized = canonical_blog_url(url)
    record["tutorial_url"] = normalized or str(url)
    record["tutorial_label"] = f"contest editorial ({discovery or 'discovered'})"
    record["tutorial_source"] = "codeforces-blog" if normalized else "external"


def tutorial_links_for_record(parsed: dict) -> list[dict]:
    """Return normalized tutorial links with their source labels."""
    return sanitize_tutorial_links(parsed.get("tutorial_links", []))


def sanitize_tutorial_links(links: Iterable) -> list[dict]:
    """Recover tutorial links from legacy records without keeping navigation.

    Early versions stored every anchor from the mirror page in
    ``statement_links`` and later accidentally treated that list as if it
    were the ``Tutorials`` section.  Keep only Codeforces blog URLs or links
    whose labels explicitly identify a tutorial/editorial/solution.  This
    function is also intentionally idempotent so it can clean an existing
    dataset during an enrichment run.
    """
    out: list[dict] = []
    seen: set[str] = set()
    for item in links or []:
        if isinstance(item, dict):
            href, label = item.get("url"), item.get("label", "")
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            href, label = item[0], item[1]
        else:
            continue
        if not href:
            continue
        normalized = canonical_blog_url(str(href))
        if not normalized and not TUTORIAL_LABEL_RE.search(str(label or "")):
            continue
        url = normalized or str(href)
        if url in seen:
            continue
        seen.add(url)
        out.append({
            "url": url,
            "label": str(label or ""),
            "source": "codeforces-blog" if normalized else "external",
        })
    return out


def editorial_status(kind: str, text: str, url: str | None) -> str:
    """Return the source-kind status kept for backwards compatibility.

    Completeness is tracked separately by :func:`editorial_quality`.  This
    lets the index distinguish an official blog containing only a loading
    placeholder or code from an official blog with a readable explanation.
    """
    if not url:
        return "missing_url"
    quality = editorial_quality(text, url)
    if quality in {"url_only", "missing_url", "fetch_failed"}:
        return "url_only"
    if kind == "official":
        return "official"
    if kind == "community":
        return "community"
    if kind == "external":
        return "external"
    return "associated"


def _editorial_meta_line(line: str) -> bool:
    """Return whether a line is attribution/boilerplate rather than prose."""
    if EDITORIAL_META_LINE_RE.fullmatch(line):
        return True
    # ``Solution: handle`` and ``Editorial: handle`` are common credit lines,
    # but ``Solution: observe ...`` is real prose and must be retained.
    m = re.match(
        r"^(solution|editorial|analysis|idea|code|implementation)\s*:\s*(.*)$",
        line,
        re.I,
    )
    if not m:
        return False
    rest = m.group(2).strip()
    if not rest:
        return True
    if EDITORIAL_EXPLANATION_CUE_RE.search(rest):
        return False
    # A credit line usually consists of one or more handles/names.  A line
    # containing an explanation cue or a sufficiently long sentence is kept.
    if EDITORIAL_EXPLANATION_CUE_RE.search(rest):
        return False
    if re.search(r"[.!?]", rest) and len(rest) >= 120:
        return False
    return True


def _editorial_code_line(line: str) -> bool:
    """Heuristically discard source-code lines from the evidence prose."""
    if line.startswith("```") or line.endswith("```"):
        return True
    if EDITORIAL_CODE_START_RE.search(line):
        return True
    if re.fullmatch(r"(?:code|submission|implementation)?\s*[:#-]?\s*\d+(?:\s+\d+)*", line, re.I):
        return True
    # Most remaining C++/Python lines have a high density of syntax markers;
    # this avoids treating identifiers/comments in a code block as editorial
    # prose while leaving normal mathematical text alone.
    letters = len(re.findall(r"[A-Za-z]", line))
    syntax = len(re.findall(r"[{};]|=>|<<|>>|\b(?:std|endl|nullptr|true|false)\b", line))
    return syntax >= 2 and syntax * 3 >= max(letters, 1)


def editorial_prose(text: str) -> str:
    """Extract explanation-like lines while preserving the original section.

    The crawler keeps the complete cleaned section in ``editorial_text`` for
    provenance.  This derived field is intentionally a small, auditable
    heuristic used for quality scoring and vocabulary matching; it is not a
    general-purpose code or Markdown parser.
    """
    meaningful: list[str] = []
    in_code = False
    for raw_line in str(text or "").splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            if in_code:
                continue
            if meaningful and meaningful[-1] != "":
                meaningful.append("")
            continue
        if line.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            # Code blocks in API blog HTML are often rendered without a
            # surrounding <pre> after clean_text().  End the heuristic block
            # at the next explicit editorial/rating section heading.
            if EDITORIAL_CODE_HEADING_RE.fullmatch(line):
                continue
            if (EDITORIAL_SECTION_RE.fullmatch(line)
                    and not EDITORIAL_CODE_HEADING_RE.fullmatch(line)) \
                    or EDITORIAL_RATING_RE.search(line):
                in_code = False
            else:
                continue
        if TUTORIAL_LOADING_RE.search(line):
            continue
        if EDITORIAL_RATING_RE.search(line):
            continue
        if EDITORIAL_TITLE_RE.fullmatch(line):
            continue
        if EDITORIAL_SECTION_RE.fullmatch(line):
            if EDITORIAL_CODE_HEADING_RE.fullmatch(line):
                in_code = True
            continue
        if _editorial_meta_line(line):
            continue
        if EDITORIAL_WEAK_RE.search(line):
            continue
        if _editorial_code_line(line):
            # A code block may start directly after ``Solution`` without an
            # explicit ``Code`` heading.  The code-line matcher is anchored
            # to language syntax, so entering a persistent block here is the
            # conservative choice; the next editorial/rating heading ends it.
            in_code = True
            continue
        meaningful.append(line)
    while meaningful and meaningful[-1] == "":
        meaningful.pop()
    return "\n".join(meaningful).strip()


def _editorial_labels(text: str) -> set[str]:
    labels: set[str] = set()
    for raw_line in str(text or "").splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip().lower()
        if not line:
            continue
        m = re.match(r"^(hint|hints|solution|tutorial|editorial|analysis|proof|implementation|code|approach|idea|complexity)\b", line)
        if m:
            labels.add(m.group(1))
    return labels


def editorial_analysis(text: str) -> dict[str, object]:
    """Return derived prose and conservative completeness signals."""
    original = str(text or "")
    prose = editorial_prose(original)
    lines = [x for x in prose.splitlines() if x.strip()]
    chars = len(" ".join(lines))
    cue_lines = sum(bool(EDITORIAL_EXPLANATION_CUE_RE.search(x)) for x in lines)
    sentence_lines = sum(bool(re.search(r"[.!?]", x)) for x in lines)
    labels = _editorial_labels(original)
    return {
        "prose": prose,
        "prose_chars": chars,
        "cue_lines": cue_lines,
        "sentence_lines": sentence_lines,
        "labels": labels,
        "has_loading": bool(TUTORIAL_LOADING_RE.search(original)),
        "has_weak_marker": bool(EDITORIAL_WEAK_RE.search(original)),
    }


def editorial_quality(text: str, url: str | None) -> str:
    """Classify how much usable explanation a fetched editorial section has.

    ``editorial_status`` says who/what the source appears to be; this field
    says whether the section is useful as training evidence.  Boilerplate,
    author metadata, rating widgets, and source code are retained in the full
    section but excluded from the derived prose used here.
    """
    if not url:
        return "missing_url"
    if not text or not text.strip():
        return "url_only"
    analysis = editorial_analysis(text)
    chars = int(analysis["prose_chars"])
    if chars == 0:
        return "url_only"
    labels = analysis["labels"]
    # A hint-only section, a community/video note, or a blog whose tutorial is
    # still loading is useful partial evidence but not a complete editorial.
    if analysis["has_loading"] or analysis["has_weak_marker"]:
        # A section containing only the title/labels and a loading marker has
        # no usable hint yet.  Keep it distinct from a real partial hint.
        if chars < 80 or (
            not analysis["cue_lines"] and not analysis["sentence_lines"]
        ):
            return "url_only"
        return "partial"
    if chars < 80:
        return "partial"
    if "hint" in labels and not labels.intersection({"solution", "tutorial", "editorial", "analysis", "proof", "approach"}):
        return "partial"
    if not analysis["cue_lines"] and not analysis["sentence_lines"]:
        return "partial"
    return "complete"


def blog_metadata_and_text(fetcher: Fetcher, url: str) -> tuple[dict, str, str]:
    """Fetch one Codeforces blog entry and return metadata plus clean text."""
    m = BLOG_RE.search(url)
    if not m:
        raw = fetcher.get(url)
        return {"url": url}, clean_text(raw), raw.decode("utf-8", "replace")
    raw = fetcher.get(f"{API}/blogEntry.view?blogEntryId={m.group(1)}")
    obj = json.loads(raw)
    if obj.get("status") != "OK":
        raise RuntimeError(f"blogEntry.view failed for {url}: {obj}")
    result = obj["result"]
    content = result.get("content", "")
    title = clean_text(result.get("title", ""))
    metadata = {
        "url": f"https://codeforces.com/blog/entry/{m.group(1)}",
        "blog_entry_id": int(m.group(1)),
        "title": title,
        "author": result.get("authorHandle"),
        "creation_time": iso_date(result.get("creationTimeSeconds")),
        "original_locale": result.get("originalLocale"),
    }
    return metadata, clean_text(content), content


def blog_csrf_token(raw_html: str) -> str | None:
    """Extract the CSRF token emitted on a Codeforces HTML page."""
    patterns = (
        # Attribute order differs between Codeforces templates and mirrors;
        # use bounded look-aheads instead of requiring ``name`` before
        # ``content`` (or ``class`` before ``data-csrf``).
        r'<meta\b(?=[^>]*\bname=["\']X-Csrf-Token["\'])(?=[^>]*\bcontent=["\']([^"\']+)["\'])[^>]*>',
        r'<span\b(?=[^>]*\bclass=["\'][^"\']*csrf-token[^"\']*["\'])(?=[^>]*\bdata-csrf=["\']([^"\']+)["\'])[^>]*>',
    )
    for pattern in patterns:
        match = re.search(pattern, raw_html, re.I)
        if match and len(match.group(1)) >= 16:
            return match.group(1)
    return None


def fetch_problem_tutorials(fetcher: Fetcher, blog_url: str, raw_html: str) -> dict[str, str]:
    """Load dynamic ``problemTutorial`` bodies used by CF blog editorials.

    Editorial blog HTML often contains only ``Tutorial is loading...`` and a
    ``problemcode`` attribute.  The browser fills the placeholder by POSTing
    to ``/data/problemTutorial`` with the page's CSRF token.  This function
    mirrors that request and returns cleaned HTML keyed by problem code.
    """
    codes = []
    seen: set[str] = set()
    for match in re.finditer(r'problemcode\s*=\s*["\'](\d+[A-Z][0-9]*)["\']', raw_html, re.I):
        code = match.group(1).upper()
        if code not in seen:
            seen.add(code)
            codes.append(code)
    token = blog_csrf_token(raw_html)
    if not codes or not token:
        return {}
    parsed = urlparse(blog_url)
    endpoint = f"{parsed.scheme or 'https'}://{parsed.netloc or 'codeforces.com'}{TUTORIAL_ENDPOINT[len('https://codeforces.com'):]}"
    headers = {
        "Referer": blog_url,
        "Origin": f"{parsed.scheme or 'https'}://{parsed.netloc or 'codeforces.com'}",
        "X-Requested-With": "XMLHttpRequest",
        "X-Csrf-Token": token,
    }
    out: dict[str, str] = {}
    for code in codes:
        try:
            raw = fetcher.post(endpoint, {"problemCode": code, "csrf_token": token}, headers)
            obj = json.loads(raw)
            if obj.get("success") in {True, "true", 1, "1"} and obj.get("html"):
                out[code] = obj["html"]
        except Exception:
            # A missing dynamic body should not discard the editorial URL or
            # the static parts of the blog; callers retain the placeholder.
            continue
    return out


def merge_dynamic_tutorials(raw_html: str, dynamic: dict[str, str]) -> str:
    """Replace per-problem loading placeholders with fetched tutorial HTML."""
    if not dynamic:
        return raw_html

    def replace(match: re.Match[str]) -> str:
        code = match.group(1).upper()
        replacement = dynamic.get(code)
        if not replacement:
            return match.group(0)
        # Keep an explicit, non-nesting marker around the server response.
        # The response itself contains several nested divs, so a regex that
        # tries to delimit a wrapper ``<div>...</div>`` is inherently brittle.
        # Comment markers survive the HTML-to-text pass harmlessly and let the
        # section splitter recover the exact problem boundary later.
        return (
            f"<!-- cf-knowledge-hydrated:{code} -->"
            f"{replacement}"
            "<!-- /cf-knowledge-hydrated -->"
        )

    # The placeholder is a div whose body is exactly the loading marker; use
    # a bounded tag match so unrelated text and code are untouched.
    return re.sub(
        r'<div\b'
        r'(?=[^>]*\bclass=["\'][^"\']*problemTutorial[^"\']*["\'])'
        r'(?=[^>]*\bproblemcode=["\'](\d+[A-Z][0-9]*)["\'])'
        r'[^>]*>.*?</div>',
        replace,
        raw_html,
        flags=re.I | re.S,
    )


def hydrate_blog_tutorials(fetcher: Fetcher, blog_url: str, raw_html: str) -> str:
    """Hydrate loading placeholders when a blog uses CF's dynamic endpoint.

    The public ``blogEntry.view`` API supplies the article content but not the
    CSRF token rendered in the full HTML page.  A lightweight page GET creates
    the session/token; failure to obtain it is deliberately non-fatal and
    leaves the original placeholder in place.
    """
    if not re.search(r"problemTutorial", raw_html, re.I):
        return raw_html
    try:
        page = fetcher.get(blog_url).decode("utf-8", "replace")
        dynamic = fetch_problem_tutorials(fetcher, blog_url, page)
        return merge_dynamic_tutorials(raw_html, dynamic)
    except Exception:
        return raw_html


def problem_codes_in_editorial(raw_html: str) -> list[tuple[int, str]]:
    """Extract problem references from blog HTML, preserving order."""
    found = []
    for m in PROBLEM_HREF_RE.finditer(raw_html):
        found.append((int(m.group(1)), m.group(2).upper()))
    for m in PROBLEM_CODE_RE.finditer(raw_html):
        found.append((int(m.group(1)), m.group(2).upper()))
    ans, seen = [], set()
    for x in found:
        if x not in seen:
            seen.add(x)
            ans.append(x)
    return ans


def _is_heading_problem_link(raw_html: str, match: re.Match[str]) -> bool:
    """Whether a problem link looks like a section heading, not a cross-ref."""
    prefix = raw_html[: match.start()]
    # Editorials conventionally start each solution with a paragraph/heading
    # whose first meaningful item is the problem link.  Cross-references have
    # prose before the link (for example, "problems like 1954D").
    openings = list(re.finditer(r"<(?:p|h[1-6])\b[^>]*>", prefix, re.I))
    if not openings:
        return False
    last = openings[-1]
    # If a closing paragraph/heading occurs after the opening, this anchor is
    # not in that block (a malformed page can contain nested tags).
    between = prefix[last.end() :]
    if re.search(r"</(?:p|h[1-6])>", between, re.I):
        return False
    before = re.sub(r"<[^>]*>", "", between)
    before = html.unescape(before).replace("\xa0", " ")
    return not re.sub(r"\s+", "", before)


def _problem_block_matches(raw_html: str, match: re.Match[str]) -> list[re.Match[str]]:
    """Return all problem links in the heading/paragraph starting ``match``.

    Official editorials frequently introduce versioned problems with one
    paragraph such as ``E1 ..., E2 ...``.  Treating only the first link as a
    boundary loses the E2 section (and similarly F1/F2/F3).  Restricting the
    lookup to the enclosing ``p``/heading avoids assigning ordinary
    cross-references found later in the solution body.
    """
    opening = None
    for candidate in re.finditer(r"<(?:p|h[1-6])\b[^>]*>", raw_html[: match.start()], re.I):
        opening = candidate
    if opening is None:
        return [match]
    closing = re.search(r"</(?:p|h[1-6])\s*>", raw_html[match.start():], re.I)
    if closing is None:
        return [match]
    block_end = match.start() + closing.end()
    # Search in the original string with bounds instead of searching a sliced
    # block.  ``re.Match.start()`` is relative to the searched string; using a
    # sliced block here made every block appear to start at the same offset
    # (usually 3 or 4), so unrelated problem headings were deduplicated.
    # Keeping the original match objects also means callers can safely use
    # their absolute offsets as editorial section boundaries.
    links = list(PROBLEM_HREF_RE.finditer(raw_html, opening.start(), block_end))
    # ``opening`` may be a stale outer paragraph on malformed HTML.  In that
    # case, keep only links at or after the requested match.
    links = [m for m in links if m.start() >= match.start()]
    return links or [match]


def editorial_problem_starts(raw_html: str) -> list[re.Match[str]]:
    """Find likely per-problem section starts in an editorial HTML document."""
    linked = list(PROBLEM_HREF_RE.finditer(raw_html))
    if linked:
        # Links inside h1--h6 are unambiguous section starts.  Older
        # editorials use paragraph links instead, and newer mixed-format
        # editorials can contain both forms.  Do not choose one class over the
        # other: collect and merge both, then deduplicate by absolute position.
        heading_link_spans = []
        for hm in re.finditer(r"<h[1-6][^>]*>.*?</h[1-6]>", raw_html, re.I | re.S):
            heading_link_spans.extend(
                x for x in linked if hm.start() <= x.start() < hm.end()
            )
        paragraph_or_heading_starts = [
            m for m in linked if _is_heading_problem_link(raw_html, m)
        ]
        candidates = {
            m.start(): m for m in heading_link_spans + paragraph_or_heading_starts
        }
        if candidates:
            linked = [candidates[pos] for pos in sorted(candidates)]
        # Keep only the first heading for each exact problem.  This prevents a
        # later cross-reference or a repeated version heading from truncating
        # the real solution section.
        out, seen, blocks = [], set(), set()
        for m in linked:
            key = (int(m.group(1)), m.group(2).upper())
            block_matches = _problem_block_matches(raw_html, m)
            block_key = (
                (block_matches[0].start(), block_matches[-1].end())
                if block_matches
                else (m.start(), m.end())
            )
            if key not in seen and block_key not in blocks:
                seen.add(key)
                blocks.add(block_key)
                out.append(m)
        return out
    placeholders = list(PROBLEM_CODE_RE.finditer(raw_html))
    out, seen = [], set()
    for m in placeholders:
        key = (int(m.group(1)), m.group(2).upper())
        if key not in seen:
            seen.add(key)
            out.append(m)
    return out


def _dynamic_problem_section_matches(raw_html: str) -> list[re.Match[str]]:
    """Find Codeforces dynamic tutorial blocks by their ``problemcode``.

    The API blog content can contain a heading/link for a different division
    followed by a generic ``problemTutorial`` block.  Once hydrated, the block
    itself carries the exact contest/index pair and is a safer boundary than
    guessing from nearby prose.  Return synthetic-like real matches by
    locating the opening div; callers only need its offsets.
    """
    return list(re.finditer(
        r'<!--\s*cf-knowledge-hydrated\s*:\s*(\d+[A-Z][0-9]*)\s*-->'
        r'.*?<!--\s*/cf-knowledge-hydrated\s*-->',
        raw_html,
        re.I | re.S,
    ))


def _problem_title_key(value: str) -> str:
    """Normalize a problem title for conservative cross-division matching."""
    value = clean_text(value)
    value = re.sub(r"^\d{3,5}[A-Z][0-9]{0,2}\s*[-:.—–)]\s*", "", value)
    value = re.sub(r"\s*\((?:easy|hard|extreme)\s+version\)\s*$", "", value, flags=re.I)
    value = re.sub(r"[^\w]+", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip().casefold()


def _dynamic_problem_alias(
    block_html: str,
    code: str,
    contest_ids: Iterable[int],
    metadata: dict[tuple[int, str], dict],
) -> tuple[int, str] | None:
    """Resolve a dynamic tutorial whose blog uses the wrong division ID.

    Combined Div. 1/Div. 2 editorials occasionally link a Div. 2 URL while
    the problem is stored under the paired Div. 1 contest (or vice versa).
    Exact contest/index matching remains primary; this title-based fallback
    is used only when the code is absent from the supplied metadata and the
    normalized title identifies exactly one candidate.
    """
    exact = re.match(r"(\d+)([A-Z][0-9]*)$", code.upper())
    if not exact:
        return None
    exact_key = (int(exact.group(1)), exact.group(2))
    if exact_key in metadata:
        return exact_key
    anchor = re.search(
        r"<a\b[^>]*href=[\"'][^\"']*/contest/\d+/problem/[^\"']+[\"'][^>]*>(.*?)</a>",
        block_html,
        re.I | re.S,
    )
    if not anchor:
        return None
    title_key = _problem_title_key(anchor.group(1))
    if not title_key:
        return None
    allowed = {int(x) for x in contest_ids}
    candidates = []
    for (cid, idx), problem in metadata.items():
        if cid not in allowed:
            continue
        name = problem.get("name", "") if isinstance(problem, dict) else ""
        if _problem_title_key(str(name)) == title_key:
            candidates.append((cid, idx))
    return candidates[0] if len(candidates) == 1 else None


def split_editorial_by_problem(raw_html: str) -> dict[tuple[int, str], str]:
    """Split a blog into per-problem evidence using linked problem headings.

    We retain the raw HTML boundaries, then clean each section.  If a blog has
    no explicit problem headings, the caller can keep the full blog text as
    contest-level evidence but must not assign it to every problem.
    """
    matches = editorial_problem_starts(raw_html)
    sections: dict[tuple[int, str], str] = {}
    for i, match in enumerate(matches):
        cid, idx = int(match.group(1)), match.group(2).upper()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw_html)
        section = clean_text(raw_html[match.start():end])
        # A repeated cross-reference can otherwise overwrite a fuller section;
        # keep the longest evidence block for each problem.
        # One heading/paragraph can name several versions (E1/E2, F1/F2/F3).
        # Assign the same evidence block to every explicitly linked version;
        # the section still ends at the next distinct problem heading.
        group = _problem_block_matches(raw_html, match)
        keys = {(int(x.group(1)), x.group(2).upper()) for x in group}
        keys.add((cid, idx))
        for key in keys:
            if len(section) > len(sections.get(key, "")):
                sections[key] = section
    return sections


def infer_sections_from_headings(
    raw_html: str,
    contest_ids: Iterable[int],
    metadata: dict[tuple[int, str], dict],
    contest_names: dict[int, str] | None = None,
) -> dict[tuple[int, str], str]:
    """Fallback splitter for blogs that use headings like ``Div2A`` only.

    The mapping is constrained by the exact contest name and available problem
    indexes from the Codeforces API.  Ambiguous headings are left unresolved.
    """
    heading_re = re.compile(
        r"<h[1-6][^>]*>\s*(?:<[^>]+>\s*)*(?:div(?:ision)?\s*)?([12])?\s*[-:#.]?\s*([A-Z][0-9]*)\b.*?</h[1-6]>",
        re.I | re.S,
    )
    matches = list(heading_re.finditer(raw_html))
    # A separate common format uses ordinary headings (for example
    # ``Statement``/``Solution``) and discusses exactly one contest/problem.
    # It cannot be assigned safely without an explicit problem reference, so
    # leave it unresolved here.
    if not matches:
        return {}
    ids = list(dict.fromkeys(int(x) for x in contest_ids))
    div_by_id: dict[int, int | None] = {}
    # The caller should normally pass only contests associated with this blog.
    # If it passes the full corpus, use a round-number hint where available;
    # otherwise retain the supplied set and let ambiguity checks below reject
    # unsafe assignments.
    if len(ids) > 16:
        mentioned = set()
        for cid in ids:
            name = str((contest_names or {}).get(cid, ""))
            round_match = re.search(r"(?:round|global round)\s*#?\s*(\d+)", name, re.I)
            marker = round_match.group(1) if round_match else None
            if marker and re.search(rf"\b{re.escape(marker)}\b", raw_html, re.I):
                mentioned.add(cid)
        if mentioned:
            ids = [cid for cid in ids if cid in mentioned]
    for cid in ids:
        sample = next((p for (pcid, _), p in metadata.items() if pcid == cid), {})
        name = str((contest_names or {}).get(cid, sample.get("contest_name", "")))
        m = re.search(r"\bDiv\.??\s*([12])\b", name, re.I)
        div_by_id[cid] = int(m.group(1)) if m else None
    out: dict[tuple[int, str], str] = {}
    for i, m in enumerate(matches):
        div = int(m.group(1)) if m.group(1) else None
        idx = m.group(2).upper()
        # Compact headings such as ``Div2A`` are parsed by the regex as a
        # division prefix embedded in the first token; recover it explicitly.
        heading_text = re.sub(r"<[^>]*>", "", m.group(0))
        compact = re.search(r"\bDiv(?:ision)?\s*([12])\s*([A-Z][0-9]*)", heading_text, re.I)
        if compact:
            div, idx = int(compact.group(1)), compact.group(2).upper()
        # ``Div1E1+E2`` is a single section explicitly covering both
        # versions.  Preserve both problem keys rather than dropping E2.
        indexes = [idx]
        # Compact headings used by combined-version editorials are commonly
        # written as ``Div1E1+E2``.  There is no word boundary immediately
        # before the first index (the preceding ``1`` in ``Div1`` is also a
        # word character), so requiring ``\b`` here silently dropped the
        # second version.  Keep the match conservative by requiring the
        # version-shaped tokens and the literal ``+`` separator, but allow a
        # compact division prefix before the first token.
        plus = re.search(r"([A-Z][0-9]*)\s*\+\s*([A-Z][0-9]*)\b", heading_text, re.I)
        if plus:
            indexes = [plus.group(1).upper(), plus.group(2).upper()]
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw_html)
        section = clean_text(raw_html[m.start():end])
        for current_idx in indexes:
            candidates = [cid for cid in ids if (cid, current_idx) in metadata]
            if div is not None:
                candidates = [cid for cid in candidates if div_by_id.get(cid) == div]
            if len(candidates) != 1:
                continue
            key = (candidates[0], current_idx)
            if len(section) > len(out.get(key, "")):
                out[key] = section
    return out


def infer_sections_from_blog(
    raw_html: str,
    blog_url: str,
    contest_ids: Iterable[int],
    metadata: dict[tuple[int, str], dict],
    contest_names: dict[int, str],
) -> dict[tuple[int, str], str]:
    """Combine safe splitters, including blogs with only problemcode tags."""
    sections = split_editorial_by_problem(raw_html)
    # Some blogs have a complete static attribution paragraph for every
    # problem but the actual solution is loaded into separate dynamic blocks.
    # Prefer those exact blocks whenever they are present and non-placeholder;
    # otherwise the generic heading splitter can accidentally attach the whole
    # following section to the preceding problem.
    dynamic_blocks = _dynamic_problem_section_matches(raw_html)
    # Track both hydrated markers and still-unhydrated placeholders.  A
    # failed POST leaves the original ``problemTutorial`` div in place; if we
    # only inspect hydrated markers, the static attribution paragraph for that
    # problem can become a false editorial section and absorb later text.
    dynamic_sections: dict[tuple[int, str], str] = {}
    dynamic_keys: set[tuple[int, str]] = set()
    for match in dynamic_blocks:
        code = match.group(1).upper()
        m = re.match(r"(\d+)([A-Z][0-9]*)$", code)
        if not m:
            continue
        resolved = _dynamic_problem_alias(
            raw_html[match.start():match.end()], code, contest_ids, metadata
        )
        if resolved is None:
            cid, idx = int(m.group(1)), m.group(2)
        else:
            cid, idx = resolved
        # Remember every exact/dynamically aliased problem represented by
        # a hydrated block, even when the endpoint returned only a
        # loading placeholder.  A static attribution section for such a
        # key is not a safe fallback: if a middle block is missing, the
        # heading splitter would otherwise attach all following problems
        # to it.  Missing dynamic bodies must remain URL-only.
        dynamic_keys.add((cid, idx))
        section = clean_text(raw_html[match.start():match.end()])
        if len(section) > len(dynamic_sections.get((cid, idx), "")):
            dynamic_sections[(cid, idx)] = section
    placeholder_re = re.compile(
        r'<div\b'
        r'(?=[^>]*\bclass=["\'][^"\']*problemTutorial[^"\']*["\'])'
        r'(?=[^>]*\bproblemcode=["\'](\d+[A-Z][0-9]*)["\'])'
        r'[^>]*>',
        re.I,
    )
    for match in placeholder_re.finditer(raw_html):
        code = match.group(1).upper()
        m = re.match(r"(\d+)([A-Z][0-9]*)$", code)
        if not m:
            continue
        resolved = _dynamic_problem_alias(
            raw_html[match.start():match.end()], code, contest_ids, metadata
        )
        dynamic_keys.add(resolved or (int(m.group(1)), m.group(2)))
    if dynamic_keys:
        useful_dynamic = {
            key: value for key, value in dynamic_sections.items()
            if not TUTORIAL_LOADING_RE.search(value)
        }
        if useful_dynamic:
            # Drop static sections for every key represented by a dynamic
            # block before overlaying the usable hydrated bodies.  This keeps
            # a failed/missing middle tutorial from swallowing later sections
            # while preserving static sections for unrelated keys in a shared
            # blog that are genuinely not dynamic.
            sections = {
                key: value for key, value in sections.items()
                if key not in dynamic_keys
            }
            sections.update(useful_dynamic)
        elif dynamic_keys:
            # All dynamic requests may have failed.  Static attribution text
            # is not an editorial body and must not be assigned as evidence.
            sections = {
                key: value for key, value in sections.items()
                if key not in dynamic_keys
            }
    if sections:
        return sections
    ids = list(dict.fromkeys(int(x) for x in contest_ids))
    # For a blog that has no references at all, there is no defensible way to
    # assign text to a problem.  The URL remains useful as provenance only.
    if not (PROBLEM_CODE_RE.search(raw_html) or re.search(r"Div(?:ision)?\s*[12]", raw_html, re.I)):
        return {}
    return infer_sections_from_headings(raw_html, ids, metadata, contest_names)


def problem_codes_from_text(text: str) -> list[tuple[int, str]]:
    """Extract explicit ``1234A`` references from clean blog text."""
    ans, seen = [], set()
    for m in re.finditer(r"(?<![A-Za-z0-9])(\d{3,5})([A-Z][0-9]{0,2})(?![A-Za-z0-9])", text):
        key = (int(m.group(1)), m.group(2).upper())
        if key not in seen:
            seen.add(key)
            ans.append(key)
    return ans


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def compact_failures(failures: object) -> list[dict]:
    """Keep only the latest failure for each URL and cap retry history."""
    if not isinstance(failures, list):
        return []
    latest: dict[str, dict] = {}
    order: list[str] = []
    anonymous: list[dict] = []
    for item in failures:
        if not isinstance(item, dict):
            continue
        entry = dict(item)
        url = str(entry.get("url") or "")
        if url:
            if url in latest:
                order.remove(url)
            latest[url] = entry
            order.append(url)
        else:
            anonymous.append(entry)
    recent = [latest[key] for key in order[-MAX_FAILURE_LOG:]]
    return [*recent, *anonymous[-MAX_FAILURE_LOG:]][-MAX_FAILURE_LOG:]


def record_failure(failures: list[dict], url: object, error: object) -> None:
    """Record a retryable failure without growing state forever."""
    failures.append({
        "url": str(url) if url else None,
        "error": str(error),
        "time": dt.datetime.now(dt.timezone.utc).isoformat(),
    })
    failures[:] = compact_failures(failures)


def save_state(path: Path, records: object, failures: list[dict]) -> None:
    save_json(path, {
        "records": records,
        "failures": compact_failures(failures),
        "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    })


def cf_api(fetcher: Fetcher, method: str, **params):
    query = "&".join(f"{quote(str(k))}={quote(str(v))}" for k, v in params.items())
    raw = fetcher.get(f"{API}/{method}?{query}")
    obj = json.loads(raw)
    if obj.get("status") != "OK":
        raise RuntimeError(f"Codeforces API error for {method}: {obj}")
    return obj["result"]


def contest_window(
    fetcher: Fetcher,
    since: dt.datetime,
    until: dt.datetime,
    contest_id: int | None = None,
) -> list[dict]:
    contests = cf_api(fetcher, "contest.list", gym="false")
    ans = []
    for c in contests:
        start = c.get("startTimeSeconds")
        if c.get("type") != "CF" or not start:
            continue
        if contest_id is not None and int(c.get("id", -1)) != contest_id:
            continue
        when = dt.datetime.fromtimestamp(start, dt.timezone.utc)
        in_window = contest_id is not None or since <= when < until
        if in_window and c.get("phase") in {"FINISHED", "CODING", "PENDING_SYSTEM_TEST"}:
            ans.append({**c, "date": when.date().isoformat()})
    return sorted(ans, key=lambda x: x["startTimeSeconds"])


def problem_metadata(
    fetcher: Fetcher, contest_ids: Iterable[int] | None = None
) -> dict[tuple[int, str], dict]:
    result = cf_api(fetcher, "problemset.problems")
    out = {}
    for p in result["problems"]:
        if p.get("contestId") is not None:
            out[(int(p["contestId"]), p["index"])] = p
    if contest_ids is None:
        return out

    known_contests = {contest_id for contest_id, _ in out}
    missing_contests = sorted({int(contest_id) for contest_id in contest_ids} - known_contests)
    for contest_id in missing_contests:
        standings = cf_api(fetcher, "contest.standings", contestId=contest_id)
        for problem in standings.get("problems", []):
            index = problem.get("index")
            if not index:
                continue
            out[(contest_id, str(index))] = {**problem, "contestId": contest_id}
    return out


def apply_problem_metadata(record: dict, problem: dict, contest: dict | None = None) -> None:
    """Refresh API-owned metadata without touching statement/editorial evidence."""
    fields = {
        "title": problem.get("name"),
        "rating": problem.get("rating"),
        "tags": problem.get("tags"),
    }
    if contest:
        fields.update(
            {
                "contest_name": contest.get("name"),
                "contest_date": contest.get("date"),
            }
        )
    for field, value in fields.items():
        if value not in (None, "", [], {}):
            record[field] = value


def editorial_urls(path: Path | None) -> dict[str, str]:
    """Read optional contest->editorial URL mappings.

    Accepted formats: JSON object, or TSV/CSV-like ``contest_id<TAB>url``.
    """
    if not path or not path.exists():
        return {}
    if path.suffix.lower() == ".json":
        return {str(k): v for k, v in load_json(path, {}).items()}
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        a = re.split(r"[\t, ]+", line, maxsplit=1)
        if len(a) == 2:
            out[a[0]] = a[1].strip()
    return out


def canonical_blog_url(url: str | None) -> str | None:
    """Normalize a Codeforces blog-entry URL and reject unrelated URLs."""
    if not url:
        return None
    m = BLOG_RE.search(url)
    return f"https://codeforces.com/blog/entry/{m.group(1)}" if m else None


def contest_page_editorial_links(raw_html: str) -> list[tuple[str, str]]:
    """Extract ranked Tutorial/Editorial blog links from a contest page.

    Older contest scrapers (notably ``ritwiksaha/Codeforces-Contest-Scraper``)
    use the contest page as the authoritative place to find both problems and
    tutorials.  We keep that useful discovery strategy, but return normalized
    links instead of downloading files or trusting the first blog link (which
    is usually the contest announcement).
    """
    parser = LinkParser()
    parser.feed(raw_html)
    candidates: list[tuple[str, str]] = []
    seen: set[str] = set()
    for href, label in parser.links:
        normalized = canonical_blog_url(href)
        label = re.sub(r"\s+", " ", str(label or "")).strip()
        if not normalized or not OFFICIAL_EDITORIAL_RE.search(label):
            continue
        # Contest pages also link an announcement, registration posts, and
        # clarifications.  Do not mistake those for a Tutorial merely because
        # their surrounding HTML contains the word "contest".
        if re.search(r"\bannouncement\b|clarification|registration", label, re.I):
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        candidates.append((normalized, label))

    def rank(item: tuple[str, str]) -> tuple[int, str]:
        label = item[1].lower()
        # Prefer an explicit editorial/tutorial over a generic solution link.
        if re.search(r"\beditorial\b", label):
            return (0, label)
        if re.search(r"\btutorial\b", label):
            return (1, label)
        if re.search(r"\bofficial\b", label):
            return (2, label)
        return (3, label)

    return sorted(candidates, key=rank)


def discover_contest_page_editorial(
    fetcher: Fetcher, contest: dict
) -> tuple[str | None, str]:
    """Discover a contest Tutorial from the official contest HTML page.

    This is a small adaptation of the discovery part of the existing contest
    scraper ecosystem.  It is intentionally best-effort: API/mirror data and
    explicit mappings remain valid when Codeforces HTML is unavailable.
    """
    cid = contest.get("id")
    if cid is None:
        return None, "missing"
    url = f"https://codeforces.com/contest/{int(cid)}?locale=en"
    try:
        raw = fetcher.get(url).decode("utf-8", "replace")
        links = contest_page_editorial_links(raw)
        if links:
            return links[0][0], "contest-page"
    except Exception:
        pass
    return None, "missing"


def classify_editorial(blog_title: str, label: str = "") -> str:
    """Classify a blog entry conservatively for provenance reporting.

    The mirror's link is an official Codeforces-problemset association, but
    some associated entries are community discussions or video hints rather
    than a full official editorial.  Keep that distinction explicit.
    """
    text = f"{blog_title} {label}"
    if COMMUNITY_EDITORIAL_RE.search(text):
        return "community"
    if OFFICIAL_EDITORIAL_RE.search(text):
        return "official"
    return "associated"


def discover_editorial(fetcher: Fetcher, contest: dict, explicit: dict[str, str]) -> tuple[str | None, str]:
    cid = str(contest["id"])
    if cid in explicit:
        return canonical_blog_url(explicit[cid]) or explicit[cid], "mapping"
    # The maintained contest scraper pattern is to inspect the official
    # contest page and select its explicit Tutorial/Editorial anchor.  Prefer
    # this over search-engine guesses: the page also exposes the announcement,
    # so the helper filters and ranks those links conservatively.
    page_url, page_source = discover_contest_page_editorial(fetcher, contest)
    if page_url:
        return page_url, page_source
    # Codeforces exposes the contest's announcement/tutorial blog entry via
    # contest standings metadata for anonymous requests.  This is the most
    # reliable automatic source when the HTML contest page is behind CF.
    try:
        standings = cf_api(fetcher, "contest.standings", contestId=contest["id"])
        for key in ("contest", "contestInfo"):
            info = standings.get(key, {}) if isinstance(standings, dict) else {}
            for value in info.values() if isinstance(info, dict) else []:
                normalized = canonical_blog_url(value) if isinstance(value, str) else None
                if normalized:
                    return normalized, "standings"
    except Exception:
        pass
    # Search results are only a discovery aid.  We retain the search URL and
    # never claim an editorial was found unless a Codeforces blog URL appears.
    q = quote(f"site:codeforces.com/blog/entry \"{contest['name']}\" editorial")
    search_url = f"https://www.bing.com/search?format=rss&q={q}"
    try:
        raw = fetcher.get(search_url).decode("utf-8", "replace")
        links = LinkParser(); links.feed(raw)
        candidates = []
        for href, label in links.links:
            full = urljoin(search_url, href)
            normalized = canonical_blog_url(full)
            if normalized and "bing" not in urlparse(full).netloc:
                candidates.append(normalized)
        if candidates:
            return candidates[0], "search"
    except Exception:
        pass
    return None, "missing"


def fetch_editorial(fetcher: Fetcher, url: str) -> tuple[str, str]:
    """Fetch a blog editorial through the public API when possible.

    The web blog is frequently Cloudflare-protected, while
    ``blogEntry.view`` is available anonymously.  Returning the canonical web
    URL preserves a human-readable source link.
    """
    m = re.search(r"/blog/entry/(\d+)", url)
    if m:
        raw = fetcher.get(f"{API}/blogEntry.view?blogEntryId={m.group(1)}")
        obj = json.loads(raw)
        if obj.get("status") == "OK":
            result = obj["result"]
            content = result.get("content", "")
            return clean_text(content), url
    raw = fetcher.get(url)
    return clean_text(raw), url


def fetch_external_editorial(fetcher: Fetcher, url: str) -> tuple[dict, str, str]:
    """Fetch a non-Codeforces tutorial as related evidence."""
    raw = fetcher.get(url)
    return {"url": url}, clean_text(raw), raw.decode("utf-8", "replace")


# Evidence-oriented vocabulary.  Tags remain the primary machine-readable
# labels; these terms are only candidates extracted from editorial text.
#
# Keep this list deliberately conservative.  A short token such as ``sam``
# or a general word such as ``polynomial``/``matching`` is not evidence by
# itself: the matcher below requires a standalone token, and the vocabulary
# uses specific phrases for concepts where a generic word is too ambiguous.
VOCAB = {
    "suffix automaton": ["suffix automaton", "suffix automata", "sam", "endpos", "suffix link", "suffix links"],
    "suffix array / lcp": ["suffix array", "suffix arrays", "lcp", "longest common prefix"],
    "suffix tree": ["suffix tree", "suffix trees"],
    "palindromic tree": ["palindromic tree", "eertree", "series link", "palindromic substring"],
    "four-square theorem": ["four squares", "four-square", "lagrange's four-square"],
    "cycle lemma": ["cycle lemma", "circular lemma", "rotation lemma"],
    "interval dp": ["interval dp", "interval dynamic programming", "dp[l][r]", "stone merging"],
    "subset / SOS dp": ["subset dp", "sos dp", "sum over subsets", "subset convolution"],
    "generating function": ["generating function", "formal power series", "ordinary generating function", "exponential generating function"],
    "inclusion-exclusion": ["inclusion-exclusion", "inclusion exclusion", "mobius inversion", "möbius inversion"],
    "fft / ntt": ["fft", "ntt", "fast fourier", "number theoretic transform", "polynomial convolution", "cyclic convolution"],
    "linear basis": ["linear basis", "xor basis", "gaussian basis"],
    "centroid / heavy-light decomposition": ["centroid decomposition", "heavy-light", "hld"],
    "virtual tree": ["virtual tree", "key vertices", "lca compression"],
    "cartesian tree": ["cartesian tree", "implicit treap"],
    "min-cost / max-flow": ["min-cost flow", "minimum cut", "max flow", "stoer-wagner"],
    "Hall / matching": ["hall's theorem", "hopcroft-karp", "bipartite matching", "maximum matching", "perfect matching", "dilworth's theorem"],
    "Burnside / Pólya": ["burnside", "polya", "pólya"],
    "Lucas / Kummer": ["lucas theorem", "kummer", "binomial coefficient"],
    "number theory / CRT": ["chinese remainder", "crt", "legendre", "p-adic valuation", "lifting the exponent", "lte"],
    "randomized hashing": ["randomized hash", "random hash", "rolling hash", "polynomial hash", "double hash"],
}


def _term_pattern(needle: str) -> re.Pattern[str]:
    """Compile a case-insensitive standalone-term matcher.

    ``(?<!\\w)``/``(?!\\w)`` prevent ``sam`` from matching ``same`` while
    still allowing punctuation, Markdown markup, and Unicode prose around a
    phrase.  Vocabulary entries are intentionally literal; this keeps the
    extracted evidence auditable instead of turning the file into an opaque
    NLP model.
    """
    normalized = needle.replace("’", "'").replace("–", "-").replace("—", "-")
    return re.compile(r"(?<!\w)" + re.escape(normalized) + r"(?!\w)", re.I)


def _evidence_excerpt(text: str, match: re.Match[str], radius: int = 150) -> str:
    """Return a compact, human-auditable excerpt around one text hit."""
    start = max(0, match.start() - radius)
    end = min(len(text), match.end() + radius)
    excerpt = text[start:end]
    excerpt = re.sub(r"\s+", " ", excerpt).strip()
    if start:
        excerpt = "…" + excerpt
    if end < len(text):
        excerpt += "…"
    return excerpt


def knowledge_candidates(record: dict) -> list[dict]:
    found = []
    # Only editorial text is allowed to produce named theorem candidates.
    # Problem statements can contain arbitrary words such as "SAM" in a
    # story; tags are kept separately as authoritative CF metadata.
    editorial = str(record.get("editorial_text", ""))
    editorial_quality_value = record.get("editorial_quality")
    # A legacy record may not have the derived quality field yet.  In that
    # case retain the historical behaviour, but never use an explicitly
    # URL-only/placeholder section as evidence for a named concept.
    if editorial and not editorial_quality_value:
        editorial_quality_value = editorial_quality(
            editorial, record.get("editorial_url") or "legacy"
        )
    usable_editorial = bool(editorial) and editorial_quality_value in {
        "complete", "partial"
    }
    # Match only explanation-like lines.  Code, attribution, loading markers,
    # and rating widgets remain available in ``editorial_text`` for provenance
    # but must not create named knowledge-point evidence.
    evidence_text = editorial_prose(editorial) if usable_editorial else ""
    normalized_editorial = evidence_text.replace("’", "'").replace("–", "-").replace("—", "-")
    for concept, needles in VOCAB.items():
        if not usable_editorial:
            break
        hits: list[str] = []
        excerpt = ""
        for needle in needles:
            match = _term_pattern(needle).search(normalized_editorial)
            if not match:
                continue
            hits.append(needle)
            if not excerpt:
                excerpt = _evidence_excerpt(evidence_text, match)
        if hits:
            found.append({
                "name": concept,
                "evidence_terms": hits,
                "evidence_excerpt": excerpt,
                "source": "text-match",
                "editorial_quality": editorial_quality_value or "unknown",
            })
    for tag in record.get("tags", []):
        found.append({"name": f"tag:{tag}", "evidence_terms": [tag], "source": "codeforces-tag"})
    # Stable de-duplication.
    ans, seen = [], set()
    for x in found:
        if x["name"] not in seen:
            seen.add(x["name"]); ans.append(x)
    return ans


def update_record_editorial(
    rec: dict,
    *,
    url: str | None,
    label: str | None,
    source: str,
    metadata: dict | None = None,
    text: str = "",
    raw_html: str = "",
    problem_text: str | None = None,
) -> None:
    """Attach one per-problem editorial evidence block to a record."""
    rec["editorial_url"] = url
    rec["editorial_label"] = label
    rec["editorial_source"] = source
    if metadata:
        rec["editorial_blog"] = metadata
    chosen = problem_text if problem_text is not None else text
    rec["editorial_text"] = chosen if len(chosen.strip()) >= 80 else ""
    kind = (
        classify_editorial(str((metadata or {}).get("title", "")), label or "")
        if source == "codeforces-blog"
        else source
    )
    rec["editorial_kind"] = kind
    rec["editorial_quality"] = editorial_quality(rec["editorial_text"], url)
    rec["editorial_status"] = editorial_status(kind, rec["editorial_text"], url)
    if raw_html:
        rec["editorial_raw_sha256"] = hashlib.sha256(raw_html.encode("utf-8")).hexdigest()
    elif rec["editorial_text"]:
        rec["editorial_raw_sha256"] = hashlib.sha256(rec["editorial_text"].encode("utf-8")).hexdigest()
    # Keep blog metadata even for URL-only sections: it is provenance, not
    # evidence that the per-problem body was successfully extracted.


def load_skip_contests(out: Path, value: str | None = None) -> set[int]:
    """Load an explicit local manifest of contests intentionally left alone."""
    skipped: set[int] = set()
    if value:
        for token in re.split(r"[,\s]+", value.strip()):
            if token.isdigit():
                skipped.add(int(token))
    manifest = load_json(out / "skipped-editorial-contests.json", [])
    if isinstance(manifest, dict):
        manifest = manifest.get("contest_ids", [])
    if isinstance(manifest, list):
        for item in manifest:
            if isinstance(item, int) or (isinstance(item, str) and item.isdigit()):
                skipped.add(int(item))
            elif isinstance(item, dict) and str(item.get("contest_id", "")).isdigit():
                skipped.add(int(item["contest_id"]))
    return skipped


def refresh_editorial_classification(record: dict) -> None:
    """Derive quality/kind/status fields for old records without networking."""
    url = record.get("editorial_url") or record.get("tutorial_url")
    source = str(record.get("editorial_source") or record.get("tutorial_source") or "missing")
    blog = record.get("editorial_blog") or {}
    text = str(record.get("editorial_text") or "")
    if record.get("editorial_status") == "fetch_failed" and not text:
        record["editorial_kind"] = str(record.get("editorial_kind") or source)
        record["editorial_quality"] = "fetch_failed"
        record["editorial_status"] = "fetch_failed"
        return
    if source == "codeforces-blog" or url and canonical_blog_url(str(url)):
        kind = classify_editorial(str(blog.get("title", "")), str(record.get("editorial_label") or record.get("tutorial_label") or ""))
    else:
        kind = str(record.get("editorial_kind") or source)
    record["editorial_kind"] = kind
    record["editorial_quality"] = editorial_quality(text, url)
    record["editorial_status"] = editorial_status(kind, text, url)


def record_needs_enrichment(record: dict) -> bool:
    """Queue records missing either a reliable statement or editorial text."""
    return (
        not is_problem_statement(str(record.get("statement_text") or ""))
        or record.get("editorial_quality") != "complete"
        or record.get("editorial_status") in {"missing_url", "url_only", "fetch_failed"}
    )


def load_records_for_enrichment(out: Path) -> tuple[dict[str, dict], list[dict]]:
    """Load resumable records, repairing stale checkpoints from records.json.

    Older enrichment runs checkpointed a sparse/partially normalized record
    into ``state.json``.  If that checkpoint is preferred blindly, a later
    full repair can turn perfectly good Tutorial URLs into ``missing_url``.
    ``records.json`` is the durable corpus snapshot, so merge it as the base
    and overlay only non-empty fields from the checkpoint.  Editorial fields
    with non-empty checkpoint text are deliberately preferred: that is how a
    section-aware repair replaces an older polluted shared-blog section.
    """
    state_path = out / "state.json"
    state = load_json(state_path, None)
    if isinstance(state, dict) and isinstance(state.get("records"), dict):
        checkpoint = state["records"]
        durable = load_json(out / "records.json", [])
        base = {
            f"{r.get('contest_id')}{r.get('index')}": dict(r)
            for r in durable
            if isinstance(r, dict)
        } if isinstance(durable, list) else {}
        merged: dict[str, dict] = {}
        ordered_keys = list(checkpoint)
        ordered_keys.extend(str(key) for key in base if str(key) not in checkpoint)
        for key in ordered_keys:
            b = dict(base.get(key) or {})
            c = checkpoint.get(key) if isinstance(checkpoint.get(key), dict) else {}
            # Empty checkpoint values are not authoritative.  They commonly
            # represent an interrupted/legacy pass, while the durable record
            # still has a valid URL or editorial body.
            for field, value in c.items():
                if field in {"editorial_text", "statement_text"}:
                    if str(value or "").strip():
                        b[field] = value
                elif field in {
                    "editorial_url", "tutorial_url", "statement_url",
                    "editorial_raw_sha256", "editorial_status",
                    "editorial_quality", "editorial_kind", "editorial_source",
                    "editorial_label", "tutorial_label", "tutorial_source",
                }:
                    if value not in (None, "", [], {}):
                        b[field] = value
                elif value not in (None, "", [], {}):
                    b[field] = value
            merged[key] = b
        failures = compact_failures(state.setdefault("failures", []))
        state["failures"] = failures
        return merged, failures
    records = load_json(out / "records.json", [])
    return {f"{r.get('contest_id')}{r.get('index')}": r for r in records}, []


def record_key(record: dict) -> str:
    """Return the stable contest/problem key used by state checkpoints."""
    return f"{record.get('contest_id')}{record.get('index')}"


def normalize_legacy_record(record: dict) -> None:
    """Repair fields written by older crawler versions in-place."""
    # Keep a direct contest link even for records whose editorial URL is
    # intentionally left unresolved.  This is the useful next action for a
    # human reviewing the editorial-gap queue.
    if record.get("contest_id") is not None:
        record["contest_url"] = CF_CONTEST.format(contest=record["contest_id"])
    if "statement_source_attempts" not in record:
        record["statement_source_attempts"] = []
    # ``statement_links`` is intentionally retained as raw provenance, but it
    # must never be reused as a Tutorial list.  Always sanitize the structured
    # list too: old runs may already contain the entire mirror page there.
    record["tutorial_links"] = sanitize_tutorial_links(
        record.get("tutorial_links") or record.get("statement_links") or []
    )
    selected_url, selected_label, selected_source = select_tutorial_link(
        [(x.get("url"), x.get("label", "")) for x in record["tutorial_links"]]
    )
    if selected_url:
        record["tutorial_url"] = selected_url
        record["tutorial_label"] = selected_label
        record["tutorial_source"] = selected_source
    else:
        # Contest-level fallback discovery is intentionally stored without a
        # per-problem ``tutorial_links`` entry.  Older normalization code
        # replaced that already-valid URL with ``None`` on every reindex,
        # which made complete records appear to lose their Tutorial source.
        # Preserve the existing URL/label/source when there are no links to
        # select; ``editorial_url`` is also a valid legacy fallback field.
        existing_url = record.get("tutorial_url") or record.get("editorial_url")
        if existing_url:
            normalized = canonical_blog_url(str(existing_url))
            record["tutorial_url"] = normalized or str(existing_url)
            record["tutorial_label"] = (
                record.get("tutorial_label")
                or record.get("editorial_label")
                or "contest editorial (preserved)"
            )
            existing_source = record.get("tutorial_source")
            if existing_source in {None, "", "missing"}:
                existing_source = "codeforces-blog" if normalized else "external"
            record["tutorial_source"] = existing_source
        else:
            record["tutorial_url"] = None
            record["tutorial_label"] = None
            record["tutorial_source"] = "missing"
    statement_text = str(record.get("statement_text") or "")
    record["statement_quality"] = (
        "available" if is_problem_statement(statement_text) else "missing"
    )
    # Legacy records were crawled from the mirror before source provenance was
    # stored.  Recover that provenance from the persisted statement URL after
    # recomputing quality, while leaving unknown custom URLs untouched.
    if record["statement_quality"] == "available" and not record.get("statement_source"):
        statement_url = str(record.get("statement_url") or "")
        if "cf-problemset.herokuapp.com" in statement_url:
            record["statement_source"] = "cf-problemset-mirror"
            record["statement_source_url"] = statement_url
        elif "codeforces.com/contest/" in statement_url and "/problem/" in statement_url:
            record["statement_source"] = "codeforces-problem-page"
            record["statement_source_url"] = statement_url


def editorial_metadata_from_records(records: Iterable[dict]) -> dict[str, dict]:
    """Build a lightweight blog report when only records are available."""
    report: dict[str, dict] = {}
    for rec in records:
        url = rec.get("editorial_url") or rec.get("tutorial_url")
        if not url:
            continue
        item = report.setdefault(str(url), {"url": str(url), "covered_problems": [], "section_count": 0})
        key = f"{rec.get('contest_id')}{rec.get('index')}"
        if rec.get("editorial_text") and key not in item["covered_problems"]:
            item["covered_problems"].append(key)
    for item in report.values():
        item["covered_problems"].sort()
        item["section_count"] = len(item["covered_problems"])
    return report


def write_editorial_gaps(out: Path, records: list[dict]) -> None:
    """Write a per-problem queue for missing or incomplete editorials."""
    gaps = [
        r for r in records
        if r.get("editorial_quality", "url_only") != "complete"
        or r.get("editorial_status") in {"missing_url", "url_only", "fetch_failed"}
    ]
    gaps.sort(key=lambda r: (r.get("contest_date", ""), int(r.get("contest_id", 0)), r.get("index", "")))
    save_json(out / "editorial-gaps.json", [
        {
            "contest_id": r.get("contest_id"),
            "contest_name": r.get("contest_name"),
            "contest_date": r.get("contest_date"),
            "contest_url": r.get("contest_url") or (
                CF_CONTEST.format(contest=r["contest_id"])
                if r.get("contest_id") is not None else None
            ),
            "index": r.get("index"),
            "title": r.get("title"),
            "rating": r.get("rating"),
            "problem_url": r.get("problem_url"),
            "statement_url": r.get("statement_url"),
            "tutorial_url": r.get("tutorial_url"),
            "tutorial_label": r.get("tutorial_label"),
            "editorial_status": r.get("editorial_status"),
            "editorial_discovery": r.get("editorial_discovery"),
        }
        for r in gaps
    ])
    lines = [
        "# Editorial 缺口清单",
        "",
        "此文件列出没有完整逐题题解正文的记录；`partial` 表示来源为官方/社区博客但正文含占位内容或只有部分说明，`url_only` 表示找到 URL 但没有可安全使用的正文，`missing_url` 表示镜像页没有 Tutorial 链接，`fetch_failed` 表示请求失败。",
        "",
        f"总数：{len(gaps)}",
        "",
    ]
    current = None
    for r in gaps:
        contest = (r.get("contest_id"), r.get("contest_name"), r.get("contest_date"))
        if contest != current:
            if current is not None:
                lines.append("")
            current = contest
            contest_url = r.get("contest_url") or (
                CF_CONTEST.format(contest=contest[0])
                if contest[0] is not None else None
            )
            heading = f"{contest[0]} {contest[1]} ({contest[2]})"
            if contest_url:
                heading = f"[{heading}]({contest_url})"
            lines += [f"## {heading}", ""]
        problem = f"{r.get('contest_id')}{r.get('index')} {r.get('title')}"
        links = [f"[题面]({r.get('problem_url')})"]
        contest_url = r.get("contest_url") or (
            CF_CONTEST.format(contest=r["contest_id"])
            if r.get("contest_id") is not None else None
        )
        if contest_url and r.get("editorial_status") == "missing_url":
            links.insert(0, f"[比赛]({contest_url})")
        if r.get("tutorial_url"):
            links.append(f"[Tutorial]({r['tutorial_url']})")
        quality = r.get("editorial_quality", "url_only")
        lines.append(f"- {' · '.join(links)} — `{problem}`，rating={r.get('rating') or '?'}，status=`{r.get('editorial_status')}`，quality=`{quality}`")
    (out / "editorial-gaps.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_statement_gaps(out: Path, records: list[dict]) -> None:
    """Write a separate queue for records without a reliable problem statement."""
    gaps = [r for r in records if not is_problem_statement(str(r.get("statement_text") or ""))]
    gaps.sort(key=lambda r: (r.get("contest_date", ""), int(r.get("contest_id", 0)), r.get("index", "")))
    items = []
    for record in gaps:
        quality = record.get("statement_quality") or "missing"
        items.append({
            "contest_id": record.get("contest_id"),
            "contest_name": record.get("contest_name"),
            "contest_date": record.get("contest_date"),
            "index": record.get("index"),
            "title": record.get("title"),
            "rating": record.get("rating"),
            "problem_url": record.get("problem_url"),
            "statement_url": record.get("statement_url"),
            "statement_source": record.get("statement_source"),
            "statement_source_url": record.get("statement_source_url"),
            "statement_source_attempts": record.get("statement_source_attempts", []),
            "statement_quality": quality,
            "reason": "缺少可靠题面正文，自动摘要与训练结论生成应暂停。",
        })
    save_json(out / "statement-gaps.json", items)
    lines = [
        "# 题面缺口清单",
        "",
        "此文件只列出没有可靠题面正文的记录。自动摘要任务不会根据题目标题、标签或 URL 猜测题意。",
        "",
        f"总数：{len(items)}",
        "",
    ]
    for item in items:
        links = [f"[题面]({item['problem_url']})"]
        if item.get("statement_url") and item["statement_url"] != item.get("problem_url"):
            links.append(f"[本地抓取地址]({item['statement_url']})")
        problem = f"{item.get('contest_id')}{item.get('index')} {item.get('title')}"
        lines.append(
            f"- {' · '.join(links)} — `{problem}`，rating={item.get('rating') or '?'}，"
            f"quality=`{item.get('statement_quality')}`；{item['reason']}"
        )
    (out / "statement-gaps.md").write_text(
        "\n".join(lines).rstrip("\n") + "\n",
        encoding="utf-8",
    )


def write_coverage(
    out: Path,
    records: list[dict],
    failures: list[dict] | None = None,
    blogs: dict[str, dict] | None = None,
) -> None:
    """Write machine-readable and human-readable crawl coverage statistics."""
    statuses = Counter(r.get("editorial_status", "missing_url") for r in records)
    qualities = Counter(r.get("editorial_quality", "missing_url") for r in records)
    statement_sources = Counter(
        r.get("statement_source") or "unknown"
        for r in records
        if is_problem_statement(str(r.get("statement_text") or ""))
    )
    gap_qualities = {"missing_url", "url_only", "partial", "fetch_failed"}
    statement_gaps = [r for r in records if not is_problem_statement(str(r.get("statement_text") or ""))]
    coverage = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "records": len(records),
        "statement_text": sum(bool(r.get("statement_text")) for r in records),
        "tutorial_url": sum(bool(r.get("tutorial_url")) for r in records),
        "editorial_text": sum(bool(r.get("editorial_text")) for r in records),
        "editorial_complete": qualities.get("complete", 0),
        "editorial_partial": qualities.get("partial", 0),
        "editorial_quality": dict(sorted(qualities.items())),
        "editorial_status": dict(sorted(statuses.items())),
        "unique_editorial_urls": len({r.get("editorial_url") for r in records if r.get("editorial_url")}),
        "failures": len(failures or []),
        "failed_urls": sorted({x.get("url") for x in (failures or []) if x.get("url")}),
        "blogs": len(blogs or {}),
        "editorial_gaps": sum(r.get("editorial_quality", "missing_url") in gap_qualities for r in records),
        "statement_gaps": len(statement_gaps),
        "statement_sources": dict(sorted(statement_sources.items())),
    }
    save_json(out / "coverage.json", coverage)
    lines = [
        "# Codeforces 抓取覆盖率",
        "",
        f"- 题目记录：{coverage['records']}",
        f"- 题面文本：{coverage['statement_text']}",
        f"- Tutorial URL：{coverage['tutorial_url']}",
        f"- 题解文本：{coverage['editorial_text']}",
        f"- 完整题解正文：{coverage['editorial_complete']}",
        f"- 部分题解正文：{coverage['editorial_partial']}",
        f"- 唯一题解博客：{coverage['unique_editorial_urls']}",
        f"- 失败请求数（含历史重试）：{coverage['failures']}",
        f"- Editorial 缺口：{coverage['editorial_gaps']}",
        f"- 题面缺口：{coverage['statement_gaps']}",
        "",
        "## 题面来源",
        "",
    ]
    for key, value in sorted(statement_sources.items()):
        lines.append(f"- {key}：{value}")
    lines += [
        "",
        "## 题解状态",
        "",
    ]
    for key, value in sorted(statuses.items()):
        lines.append(f"- `{key}`：{value}")
    lines += ["", "## 题解完整度", ""]
    for key, value in sorted(qualities.items()):
        lines.append(f"- `{key}`：{value}")
    if coverage["failed_urls"]:
        lines += ["", "## 失败 URL", ""]
        lines.extend(f"- {url}" for url in coverage["failed_urls"])
    (out / "coverage.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_editorial_gaps(out, records)
    write_statement_gaps(out, records)


def enrich_editorials(args) -> None:
    """Resolve Tutorial links already present in a crawled problem dataset."""
    out = Path(args.data)
    records_by_key, failures = load_records_for_enrichment(out)
    contests = load_json(out / "contests.json", [])
    problem_list = load_json(out / "problems.json", [])
    metadata = {
        (int(p["contestId"]), p["index"]): p
        for p in problem_list
        if p.get("contestId") is not None and p.get("index")
    }
    contest_names = {int(c["id"]): c.get("name", "") for c in contests if c.get("id") is not None}
    contest_ids = list(contest_names)
    fetcher = Fetcher(args.delay, args.retries, args.timeout)
    explicit = editorial_urls(Path(args.editorials) if getattr(args, "editorials", None) else None)
    blog_cache: dict[str, tuple[dict, str, str, dict[tuple[int, str], str]]] = {}
    blog_report: dict[str, dict] = {}
    checkpoint_every = max(1, int(getattr(args, "checkpoint_every", 25)))
    all_records = sorted(
        records_by_key.values(),
        key=lambda x: (x.get("contest_date", ""), x.get("contest_id", 0), x.get("index", "")),
    )
    context_records = all_records
    target_contest_id = getattr(args, "contest_id", None)
    if target_contest_id is not None:
        all_records = [
            record for record in all_records
            if int(record.get("contest_id", -1)) == target_contest_id
        ]
    only_missing_url = bool(getattr(args, "only_missing_url", False))
    only_incomplete = bool(getattr(args, "only_incomplete", False))
    if only_incomplete:
        records = [r for r in all_records if record_needs_enrichment(r)]
    elif only_missing_url:
        records = [
            r for r in all_records
            if not r.get("tutorial_url")
            or r.get("editorial_status") in {"missing_url", "fetch_failed"}
        ]
    else:
        records = all_records
    for rec in records:
        normalize_legacy_record(rec)
        refresh_editorial_classification(rec)
        rec["knowledge_candidates"] = knowledge_candidates(rec)
    # Keep already-known Tutorial links in the context even when the work
    # queue is filtered to missing URLs.  Shared/division blogs may need those
    # links to resolve compact headings safely.
    contest_fallbacks: dict[int, tuple[str | None, str]] = {}
    skip_missing_contests = bool(getattr(args, "skip_missing_contests", False))
    contest_problem_counts: Counter[int] = Counter(int(r["contest_id"]) for r in context_records)
    contest_link_counts: Counter[int] = Counter(
        int(r["contest_id"]) for r in context_records if r.get("tutorial_url")
    )
    skipped_contests = {
        cid for cid, count in contest_problem_counts.items()
        if skip_missing_contests and contest_link_counts.get(cid, 0) == 0
    }
    needed_contests = sorted({
        int(r["contest_id"])
        for r in records
        if not r.get("tutorial_url") and int(r["contest_id"]) not in skipped_contests
    })
    contest_by_id = {
        int(c["id"]): c for c in contests if c.get("id") is not None
    }
    for cid in needed_contests:
        contest = contest_by_id.get(cid, {"id": cid, "name": contest_names.get(cid, "")})
        contest_fallbacks[cid] = discover_editorial(fetcher, contest, explicit)
    # Build the precise set of contest IDs associated with each Tutorial URL
    # from the already-crawled mirror links.  This is essential for blogs that
    # use compact headings such as ``Div2A`` and cover multiple divisions.
    url_contests: dict[str, set[int]] = {}
    for item in context_records:
        for link in item.get("tutorial_links", []):
            if isinstance(link, dict) and link.get("url"):
                url_contests.setdefault(link["url"], set()).add(int(item["contest_id"]))
    for cid, (url, _source) in contest_fallbacks.items():
        if url:
            url_contests.setdefault(url, set()).add(cid)

    for n, rec in enumerate(records, 1):
        cid, idx = int(rec["contest_id"]), str(rec["index"])
        parsed = None
        if cid in skipped_contests:
            # Keep the approved gap explicit and attach only the contest
            # landing page.  No search or tutorial request is made for this
            # record.
            rec["tutorial_url"] = None
            rec["tutorial_label"] = None
            rec["tutorial_source"] = "missing"
            rec["editorial_discovery"] = "skipped-missing-url"
            update_record_editorial(
                rec, url=None, label=None, source="missing", text=""
            )
            rec["knowledge_candidates"] = knowledge_candidates(rec)
            if n % checkpoint_every == 0:
                save_state(out / "state.json", records_by_key, failures)
            continue
        # Old crawl outputs contain all mirror anchors but not the structured
        # tutorial_links field.  Reuse those anchors before making a request.
        if rec.get("statement_links") and not rec.get("tutorial_links"):
            rec["tutorial_links"] = sanitize_tutorial_links(rec["statement_links"])
        if args.refresh_statements or not rec.get("statement_text") or rec.get("statement_quality") != "available":
            result = fetch_statement_with_fallback(fetcher, rec)
            apply_statement_result(rec, result)
            for failure in result["errors"]:
                record_failure(failures, failure["url"], failure["error"])
        if rec.get("tutorial_links"):
            selected_url, selected_label, selected_source = select_tutorial_link(
                [(x.get("url"), x.get("label", "")) for x in rec["tutorial_links"] if isinstance(x, dict)]
            )
            rec["tutorial_url"] = selected_url
            rec["tutorial_label"] = selected_label
            rec["tutorial_source"] = selected_source
        elif not rec.get("tutorial_url"):
            rec["tutorial_url"] = None
            rec["tutorial_label"] = None
            rec["tutorial_source"] = "missing"

        fallback_url, fallback_source = contest_fallbacks.get(cid, (None, "missing"))
        had_problem_link = bool(rec.get("tutorial_url"))
        apply_contest_editorial_fallback(rec, fallback_url, fallback_source)
        if rec.get("tutorial_url") and not had_problem_link:
            rec["editorial_discovery"] = fallback_source if fallback_url else "mirror-tutorial"

        tutorial_url = rec.get("tutorial_url")
        if tutorial_url:
            try:
                if tutorial_url not in blog_cache:
                    if rec.get("tutorial_source") == "codeforces-blog":
                        meta, blog_text, raw_html = blog_metadata_and_text(fetcher, tutorial_url)
                        raw_html = hydrate_blog_tutorials(fetcher, tutorial_url, raw_html)
                        blog_text = clean_text(raw_html)
                        sections = infer_sections_from_blog(
                            raw_html,
                            tutorial_url,
                            url_contests.get(tutorial_url, {cid}),
                            metadata,
                            contest_names,
                        )
                        # ``problemcode`` blogs often contain only loading
                        # placeholders.  Do not turn those into evidence; the
                        # splitters intentionally return the placeholder block
                        # so the status becomes ``url_only``.
                    else:
                        meta, blog_text, raw_html = fetch_external_editorial(fetcher, tutorial_url)
                        sections = {}
                    blog_cache[tutorial_url] = (meta, blog_text, raw_html, sections)
                    blog_report[tutorial_url] = {
                        **meta,
                        "source": rec.get("tutorial_source"),
                        "label": rec.get("tutorial_label"),
                        "section_count": len(sections),
                        "covered_problems": [f"{a}{b}" for a, b in sorted(sections)],
                        "raw_sha256": hashlib.sha256(raw_html.encode("utf-8")).hexdigest(),
                    }
                meta, blog_text, raw_html, sections = blog_cache[tutorial_url]
                section = sections.get((cid, idx))
                update_record_editorial(
                    rec,
                    url=tutorial_url,
                    label=rec.get("tutorial_label"),
                    source=rec.get("tutorial_source", "associated"),
                    metadata=meta,
                    text=blog_text,
                    raw_html=raw_html,
                    problem_text=section or "",
                )
            except Exception as exc:
                rec["editorial_url"] = tutorial_url
                rec["editorial_status"] = "fetch_failed"
                record_failure(failures, tutorial_url, exc)
        else:
            update_record_editorial(rec, url=None, label=None, source="missing", text="")
        rec["knowledge_candidates"] = knowledge_candidates(rec)
        if n % checkpoint_every == 0:
            save_state(out / "state.json", records_by_key, failures)

    save_state(out / "state.json", records_by_key, failures)
    save_json(out / "records.json", records)
    existing_blogs = {
        str(x.get("url")): x
        for x in load_json(out / "editorials.json", [])
        if isinstance(x, dict) and x.get("url")
    }
    existing_blogs.update(blog_report)
    save_json(out / "editorials.json", sorted(existing_blogs.values(), key=lambda x: x.get("blog_entry_id", 0)))
    write_coverage(out, records, failures, existing_blogs)
    # Always write the complete corpus, not just the filtered work queue.
    # ``records_by_key`` already contains untouched records when either
    # incremental filter is used.
    if only_missing_url or only_incomplete:
        complete_records = sorted(
            records_by_key.values(),
            key=lambda x: (x.get("contest_date", ""), x.get("contest_id", 0), x.get("index", "")),
        )
        save_json(out / "records.json", complete_records)
        write_coverage(out, complete_records, failures, existing_blogs)
    print(f"enriched problems={len(records)} blogs={len(blog_report)} failures={len(failures)}")


def repair_editorial_sections(args) -> None:
    """Re-fetch and re-split already-linked editorial blogs in one pass.

    This is intentionally narrower than ``enrich``: it never searches for
    new URLs or re-fetches statement mirrors.  It treats the current durable
    records as the queue, fetches each distinct Codeforces blog once, hydrates
    dynamic ``problemTutorial`` bodies, and replaces a record only when a
    non-placeholder per-problem section can be assigned safely.  The command
    is therefore suitable for repairing historical shared-blog contamination
    (for example, a last problem absorbing the rest of a combined editorial).
    """
    out = Path(args.data)
    records_by_key, failures = load_records_for_enrichment(out)
    contests = load_json(out / "contests.json", [])
    problem_list = load_json(out / "problems.json", [])
    metadata = {
        (int(p["contestId"]), p["index"]): p
        for p in problem_list
        if p.get("contestId") is not None and p.get("index")
    }
    contest_names = {
        int(c["id"]): c.get("name", "")
        for c in contests
        if c.get("id") is not None
    }
    records = sorted(
        records_by_key.values(),
        key=lambda x: (x.get("contest_date", ""), int(x.get("contest_id", 0)), x.get("index", "")),
    )
    for rec in records:
        normalize_legacy_record(rec)
        refresh_editorial_classification(rec)
        rec["knowledge_candidates"] = knowledge_candidates(rec)

    grouped: dict[str, list[dict]] = defaultdict(list)
    for rec in records:
        url = rec.get("editorial_url") or rec.get("tutorial_url")
        canonical = canonical_blog_url(str(url)) if url else None
        if canonical:
            grouped[canonical].append(rec)

    fetcher = Fetcher(args.delay, args.retries, args.timeout)
    blog_report: dict[str, dict] = {}
    repaired = 0
    for blog_url, group in sorted(grouped.items()):
        try:
            meta, blog_text, raw_html = blog_metadata_and_text(fetcher, blog_url)
            raw_html = hydrate_blog_tutorials(fetcher, blog_url, raw_html)
            sections = infer_sections_from_blog(
                raw_html,
                blog_url,
                {int(r["contest_id"]) for r in group},
                metadata,
                contest_names,
            )
            blog_report[blog_url] = {
                **meta,
                "source": "codeforces-blog",
                "section_count": len(sections),
                "covered_problems": [f"{a}{b}" for a, b in sorted(sections)],
                "raw_sha256": hashlib.sha256(raw_html.encode("utf-8")).hexdigest(),
            }
            for rec in group:
                key = (int(rec["contest_id"]), str(rec["index"]).upper())
                section = sections.get(key)
                # A Div.1/Div.2 alias may be represented by a dynamic code
                # from the paired contest; try the title-based resolver only
                # when the exact key is absent from the section map.
                if section and not TUTORIAL_LOADING_RE.search(section):
                    old_text = str(rec.get("editorial_text") or "")
                    update_record_editorial(
                        rec,
                        url=blog_url,
                        label=rec.get("editorial_label") or rec.get("tutorial_label") or "editorial",
                        source="codeforces-blog",
                        metadata=meta,
                        text=blog_text,
                        raw_html=raw_html,
                        problem_text=section,
                    )
                    if section != old_text:
                        repaired += 1
                # If hydration/splitting cannot prove a section boundary,
                # retain the durable old text instead of degrading it to an
                # URL-only record.  The unresolved URL remains auditable.
                rec["knowledge_candidates"] = knowledge_candidates(rec)
        except Exception as exc:
            record_failure(failures, blog_url, exc)
        print(f"REPAIR_BLOG {blog_url} records={len(group)} repaired={repaired}", flush=True)

    save_json(out / "records.json", records)
    save_state(
        out / "state.json",
        {f"{r.get('contest_id')}{r.get('index')}": r for r in records},
        failures,
    )
    existing_blogs = {
        str(x.get("url")): x
        for x in load_json(out / "editorials.json", [])
        if isinstance(x, dict) and x.get("url")
    }
    existing_blogs.update(blog_report)
    save_json(out / "editorials.json", sorted(existing_blogs.values(), key=lambda x: x.get("blog_entry_id", 0)))
    write_coverage(out, records, failures, existing_blogs)
    print(f"repaired editorial sections: records={len(records)} blogs={len(blog_report)} changed={repaired} failures={len(failures)}")


def crawl(args) -> None:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    state_path = out / "state.json"
    state = load_json(state_path, {"records": {}, "failures": []})
    if not isinstance(state, dict):
        state = {"records": {}, "failures": []}
    state["failures"] = compact_failures(state.get("failures", []))
    # ``records.json`` may contain later enrichment than the resumable
    # checkpoint. Use it as the durable base and overlay only non-empty
    # checkpoint fields so an incremental crawl cannot erase saved evidence.
    durable_records = load_json(out / "records.json", [])
    checkpoint_records = state.get("records", {}) if isinstance(state, dict) else {}
    if isinstance(durable_records, list) and isinstance(checkpoint_records, dict):
        merged_records: dict[str, dict] = {
            record_key(record): dict(record)
            for record in durable_records
            if isinstance(record, dict)
        }
        for key, checkpoint in checkpoint_records.items():
            if not isinstance(checkpoint, dict):
                continue
            base = merged_records.setdefault(str(key), {})
            for field, value in checkpoint.items():
                if value not in (None, "", [], {}):
                    base[field] = value
        state["records"] = merged_records
    fetcher = Fetcher(args.delay, args.retries, args.timeout)
    since = parse_date(args.since)
    until = parse_date(args.until) + dt.timedelta(days=1)
    contests = contest_window(fetcher, since, until, getattr(args, "contest_id", None))
    contest_names = {int(c["id"]): c.get("name", "") for c in contests}
    contest_ids = list(contest_names)
    metadata = problem_metadata(fetcher, contest_ids)
    explicit = editorial_urls(Path(args.editorials) if args.editorials else None)
    blog_cache: dict[str, tuple[dict, str, str, dict[tuple[int, str], str]]] = {}
    save_json(out / "contests.json", contests)
    save_json(out / "problems.json", list(metadata.values()))
    checkpoint_every = max(1, int(getattr(args, "checkpoint_every", 25)))
    processed = 0
    for c in contests:
        cid = int(c["id"])
        ed_url, ed_source = discover_editorial(fetcher, c, explicit) if not args.no_search else (explicit.get(str(cid)), "mapping" if str(cid) in explicit else "missing")
        for (pcid, idx), p in sorted(metadata.items()):
            if pcid != cid:
                continue
            key = f"{cid}{idx}"
            rec = state["records"].setdefault(key, {
                "contest_id": cid, "index": idx, "contest_name": c["name"],
                "contest_date": c["date"], "title": p.get("name", ""),
                "rating": p.get("rating"), "tags": p.get("tags", []),
                "problem_url": CF_PROBLEM.format(contest=cid, index=idx),
                "statement_url": STATEMENT_MIRROR.format(contest=cid, index=idx),
            })
            apply_problem_metadata(rec, p, c)
            normalize_legacy_record(rec)
            existing_editorial_url = rec.get("tutorial_url") or rec.get("editorial_url")
            effective_editorial_url = ed_url or existing_editorial_url
            effective_editorial_source = (
                ed_source if ed_url else rec.get("tutorial_source") or rec.get("editorial_source") or "preserved"
            )
            if ed_url or not rec.get("editorial_discovery"):
                rec["editorial_discovery"] = ed_source if ed_url else "preserved"
            # A previous run may already have the cleaned statement but not
            # the Tutorial links.  Re-fetch the mirror page in that case so
            # the editorial phase can be resumed without deleting state.
            statement_needs_fetch = (
                not rec.get("statement_text")
                or not rec.get("tutorial_links")
                or rec.get("statement_quality") != "available"
            )
            if rec.get("statement_links") and not rec.get("tutorial_links"):
                selected_url, selected_label, selected_source = select_tutorial_link(rec["statement_links"])
                rec["tutorial_url"] = selected_url
                rec["tutorial_label"] = selected_label
                rec["tutorial_source"] = selected_source
            for field, url in [("statement_text", rec["statement_url"]), ("editorial_text", ed_url)]:
                # Editorials are attached below per problem.  Do not use the
                # generic field loop for them; a contest blog must be split by
                # problem before it becomes evidence for this record.
                if field == "editorial_text":
                    continue
                if (rec.get(field) and not (field == "statement_text" and statement_needs_fetch)) or not url:
                    continue
                try:
                    if field == "statement_text":
                        result = fetch_statement_with_fallback(fetcher, rec)
                        apply_statement_result(rec, result)
                        for failure in result["errors"]:
                            record_failure(state["failures"], failure["url"], failure["error"])
                        continue
                    raw = fetcher.get(url)
                    text = clean_text(raw)
                    raw_for_hash = raw
                    # Search engines sometimes return a result page; retain it
                    # only if it has meaningful content.
                    rec[field] = text if len(text) >= 80 else ""
                    rec[field + "sha256"] = hashlib.sha256(raw_for_hash.encode("utf-8") if isinstance(raw_for_hash, str) else raw_for_hash).hexdigest()
                except Exception as exc:
                    if field == "statement_text" and rec.get("statement_quality") != "available":
                        rec["statement_text"] = ""
                        rec["statement_quality"] = "missing"
                    record_failure(state["failures"], url, exc)
            # A contest-level mapping/search result is a fallback only.  A
            # Tutorial link discovered on this problem's mirror page wins.
            apply_contest_editorial_fallback(rec, effective_editorial_url, effective_editorial_source)
            # Resolve and cache the tutorial linked by this problem's mirror
            # page.  A blog commonly covers many contests/problems; split it
            # once and assign only the matching section to this record.
            tutorial_url = rec.get("tutorial_url") or effective_editorial_url
            if tutorial_url:
                try:
                    if tutorial_url not in blog_cache:
                        if rec.get("tutorial_source") == "codeforces-blog":
                            meta, blog_text, raw_html = blog_metadata_and_text(fetcher, tutorial_url)
                            raw_html = hydrate_blog_tutorials(fetcher, tutorial_url, raw_html)
                            blog_text = clean_text(raw_html)
                            # Use the same section-aware splitter as the
                            # incremental enrichment path.  Codeforces
                            # editorials frequently ship attribution
                            # paragraphs plus dynamically hydrated
                            # ``problemTutorial`` blocks.  The plain linked
                            # heading splitter sees only the attribution
                            # paragraphs and would otherwise attach the
                            # entire remainder of a shared blog (especially
                            # the last problem) to one record.  The
                            # inferencer prefers exact hydrated blocks and
                            # falls back to safe static headings when needed.
                            sections = infer_sections_from_blog(
                                raw_html,
                                tutorial_url,
                                contest_ids,
                                metadata,
                                contest_names,
                            )
                        else:
                            meta, blog_text, raw_html = fetch_external_editorial(fetcher, tutorial_url)
                            sections = {}
                        blog_cache[tutorial_url] = (meta, blog_text, raw_html, sections)
                    meta, blog_text, raw_html, sections = blog_cache[tutorial_url]
                    section = sections.get((cid, idx))
                    # If the official blog contains no explicit heading for
                    # this problem, do not copy the entire contest blog into
                    # every record.  Keep the URL and a url_only status.
                    update_record_editorial(
                        rec,
                        url=tutorial_url,
                        label=rec.get("tutorial_label"),
                        source=rec.get("tutorial_source", "associated"),
                        metadata=meta,
                        text=blog_text,
                        raw_html=raw_html,
                        problem_text=section or "",
                    )
                except Exception as exc:
                    rec["editorial_url"] = tutorial_url
                    rec["editorial_status"] = "fetch_failed"
                    record_failure(state["failures"], tutorial_url, exc)
            else:
                update_record_editorial(rec, url=None, label=None, source="missing", text="")
            rec["knowledge_candidates"] = knowledge_candidates(rec)
            processed += 1
            if processed % checkpoint_every == 0:
                save_state(state_path, state["records"], state["failures"])
    save_state(state_path, state["records"], state["failures"])
    records = sorted(state["records"].values(), key=lambda x: (x["contest_date"], x["contest_id"], x["index"]))
    save_json(out / "records.json", records)
    print(f"crawled contests={len(contests)} problems={len(records)} failures={len(state['failures'])}")


def build_index(args) -> None:
    out = Path(args.data)
    records = load_json(out / "records.json", [])
    by = defaultdict(list)
    for r in records:
        for k in r.get("knowledge_candidates", []):
            by[k["name"]].append(r)
    statuses = Counter(r.get("editorial_status", "missing_url") for r in records)
    qualities = Counter(r.get("editorial_quality", "missing_url") for r in records)
    lines = ["# Codeforces 题目—知识点索引", "", "> 这是题目证据索引，不是凭空生成的定理表。每条知识点都链接到真实题面；来源类型由 `editorial_status` 表示，正文完整度由 `editorial_quality` 表示。", ""]
    lines += [
        f"- 题目数：{len(records)}",
        f"- 有题解文本：{sum(bool(r.get('editorial_text')) for r in records)}",
        f"- 完整题解正文：{qualities.get('complete', 0)}",
        f"- 部分题解正文：{qualities.get('partial', 0)}",
        f"- 官方来源（含部分正文）：{statuses.get('official', 0)}",
        f"- 官方完整题解：{sum(r.get('editorial_status') == 'official' and r.get('editorial_quality') == 'complete' for r in records)}",
        f"- 社区/视频文本：{statuses.get('community', 0)}",
        f"- 仅有题解 URL：{statuses.get('url_only', 0)}",
        f"- 缺题解 URL：{statuses.get('missing_url', 0)}",
        f"- 抓取失败：{statuses.get('fetch_failed', 0)}",
        "",
    ]
    for concept in sorted(by, key=lambda x: (x.startswith("tag:"), x.lower())):
        lines += [f"## {concept}", ""]
        unique = {(r["contest_id"], r["index"]): r for r in by[concept]}
        for r in sorted(unique.values(), key=lambda x: (x["contest_date"], x["contest_id"], x["index"])):
            cid, idx = r["contest_id"], r["index"]
            evidence = next((x for x in r.get("knowledge_candidates", []) if x["name"] == concept), {})
            terms = ", ".join(evidence.get("evidence_terms", []))
            status = r.get("editorial_status", "missing_url") if r.get("editorial_text") else "statement/tags"
            quality = r.get("editorial_quality", "missing_url")
            problem_url = r.get("problem_url")
            editorial_url = r.get("editorial_url")
            links = f"[题面]({problem_url})"
            if editorial_url and editorial_url != problem_url:
                links += f" · [题解]({editorial_url})"
            excerpt = evidence.get("evidence_excerpt", "")
            excerpt_text = f"；摘录：{excerpt}" if excerpt else ""
            lines.append(f"- {links} — `{cid}{idx} {r['title']}`，{r['contest_date']}，rating={r.get('rating') or '?'}，来源={status}，完整度={quality}；命中：{terms}{excerpt_text}")
        lines.append("")
    (out / "knowledge-index.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out / 'knowledge-index.md'} concepts={len(by)}")


def reindex_data(args) -> None:
    """Repair legacy link fields and regenerate derived reports offline."""
    out = Path(args.data)
    records = load_json(out / "records.json", [])
    if not isinstance(records, list):
        raise ValueError(f"{out / 'records.json'} must contain a JSON array")
    problem_metadata_by_key = {
        (int(item["contestId"]), str(item["index"])): item
        for item in load_json(out / "problems.json", [])
        if isinstance(item, dict) and item.get("contestId") is not None and item.get("index")
    }
    for rec in records:
        key = (int(rec["contest_id"]), str(rec["index"]))
        problem = problem_metadata_by_key.get(key)
        if problem:
            apply_problem_metadata(rec, problem)
        normalize_legacy_record(rec)
        refresh_editorial_classification(rec)
        rec["knowledge_candidates"] = knowledge_candidates(rec)
        if rec.get("tutorial_url") and rec.get("editorial_discovery") in {None, "missing"}:
            rec["editorial_discovery"] = "mirror-tutorial"
    save_json(out / "records.json", records)
    # Keep state resumable, but do not discard its failure history if present.
    state = load_json(out / "state.json", {"records": {}, "failures": []})
    if isinstance(state, dict):
        state["records"] = {record_key(r): r for r in records}
        state["failures"] = compact_failures(state.get("failures", []))
        save_json(out / "state.json", state)
    blogs = {str(x.get("url")): x for x in load_json(out / "editorials.json", []) if isinstance(x, dict) and x.get("url")}
    if not blogs:
        blogs = editorial_metadata_from_records(records)
    write_coverage(out, records, state.get("failures", []) if isinstance(state, dict) else [], blogs)
    build_index(argparse.Namespace(data=str(out)))
    print(f"reindexed records={len(records)}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)
    def common(p):
        p.add_argument("--since", default=(dt.date.today() - dt.timedelta(days=730)).isoformat())
        p.add_argument("--until", default=(dt.date.today() + dt.timedelta(days=1)).isoformat())
        p.add_argument("--out", default=str(PROJECT_ROOT))
        p.add_argument("--delay", type=float, default=0.7)
        p.add_argument("--retries", type=int, default=3)
        p.add_argument("--timeout", type=int, default=30)
        p.add_argument("--checkpoint-every", type=int, default=25, help="write state every N problems")
        p.add_argument("--editorials", help="JSON/TSV mapping contest id to official editorial URL")
        p.add_argument("--contest-id", type=int, help="only process this Codeforces contest")
    p = sub.add_parser("crawl", help="fetch contests, statements and editorials")
    common(p); p.add_argument("--no-search", action="store_true"); p.set_defaults(func=crawl)
    p = sub.add_parser("index", help="build Markdown knowledge index from records")
    p.add_argument("--data", default=str(PROJECT_ROOT)); p.set_defaults(func=build_index)
    p = sub.add_parser("reindex", help="repair legacy derived fields and rebuild reports offline")
    p.add_argument("--data", default=str(PROJECT_ROOT)); p.set_defaults(func=reindex_data)
    p = sub.add_parser("enrich", help="resolve and split Tutorial/editorial links in an existing dataset")
    p.add_argument("--data", default=str(PROJECT_ROOT))
    p.add_argument("--delay", type=float, default=0.7)
    p.add_argument("--retries", type=int, default=3)
    p.add_argument("--timeout", type=int, default=30)
    p.add_argument("--checkpoint-every", type=int, default=25)
    p.add_argument("--editorials", help="JSON/TSV mapping contest id to official editorial URL")
    p.add_argument("--contest-id", type=int, help="only enrich this Codeforces contest")
    p.add_argument("--refresh-statements", action="store_true", help="refetch mirror pages lacking Tutorial links")
    p.add_argument(
        "--only-missing-url",
        action="store_true",
        help="only process records without a Tutorial URL (useful for incremental recovery)",
    )
    p.add_argument(
        "--only-incomplete",
        action="store_true",
        help="only reprocess records whose editorial is not complete (including URL-only sections)",
    )
    p.add_argument(
        "--skip-missing-contests",
        action="store_true",
        help="skip contest-level editorial search for contests with no Tutorial URL; keep them as explicit gaps",
    )
    p.set_defaults(func=enrich_editorials)
    p = sub.add_parser(
        "repair-editorials",
        help="re-fetch linked Codeforces blogs and repair per-problem sections without URL search",
    )
    p.add_argument("--data", default=str(PROJECT_ROOT))
    p.add_argument("--delay", type=float, default=0.7)
    p.add_argument("--retries", type=int, default=3)
    p.add_argument("--timeout", type=int, default=30)
    p.set_defaults(func=repair_editorial_sections)
    p = sub.add_parser("all", help="crawl then build index")
    common(p); p.add_argument("--no-search", action="store_true"); p.set_defaults(func=lambda a: (crawl(a), build_index(argparse.Namespace(data=a.out))))
    args = ap.parse_args()
    try:
        args.func(args)
    except KeyboardInterrupt:
        print("interrupted; rerun to resume from state.json", file=sys.stderr)
        raise SystemExit(130)


if __name__ == "__main__":
    main()
