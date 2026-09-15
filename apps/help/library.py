"""Loads the help library from disk.

Help content lives as Markdown files under ``apps/help/content/``, one file per
topic, grouped into numbered section directories. Keeping it in the repository
rather than the database means it ships with the code it describes, is
reviewed alongside it, and is present on a freshly installed system before
anyone has seeded anything.

Each file opens with a small frontmatter block:

    ---
    title: Entering results
    summary: How to record, validate and verify a result.
    audience: scientist, medic, manager
    keywords: worklist, panel, keyboard, delta
    ---

Ordering comes from the numeric prefix on directories and files, so the reading
order is visible in the filesystem and does not need a separate manifest.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import markdown

CONTENT_ROOT = Path(__file__).resolve().parent / "content"

FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)
ORDER_PREFIX = re.compile(r"^(\d+)[-_]")

#: Markdown extensions. `toc` gives each heading an id so the in-page contents
#: can link to it; `tables` and `fenced_code` are used throughout the content.
MARKDOWN_EXTENSIONS = ["extra", "tables", "fenced_code", "sane_lists", "toc", "attr_list"]


def _strip_order(name: str) -> str:
    return ORDER_PREFIX.sub("", name)


def _order_of(name: str) -> int:
    match = ORDER_PREFIX.match(name)
    return int(match.group(1)) if match else 999


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    match = FRONTMATTER.match(text)
    if not match:
        return {}, text

    meta: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        meta[key.strip().lower()] = value.strip()
    return meta, text[match.end():]


@dataclass(frozen=True)
class Topic:
    slug: str
    section_slug: str
    title: str
    summary: str
    audience: tuple[str, ...]
    keywords: tuple[str, ...]
    body: str
    order: int
    source: Path

    @property
    def path(self) -> str:
        return f"{self.section_slug}/{self.slug}"

    @property
    def haystack(self) -> str:
        return " ".join(
            [self.title, self.summary, " ".join(self.keywords), self.body]
        ).lower()

    def render(self) -> tuple[str, str]:
        """Return (html, table_of_contents_html) for this topic."""
        converter = markdown.Markdown(extensions=MARKDOWN_EXTENSIONS)
        html = converter.convert(self.body)
        return html, getattr(converter, "toc", "")


@dataclass(frozen=True)
class Section:
    slug: str
    title: str
    summary: str
    order: int
    topics: tuple[Topic, ...] = field(default_factory=tuple)


def _load_section(directory: Path) -> Section | None:
    slug = _strip_order(directory.name)
    index = directory / "_section.md"

    title, summary = slug.replace("-", " ").title(), ""
    if index.exists():
        meta, _ = _parse_frontmatter(index.read_text(encoding="utf-8"))
        title = meta.get("title", title)
        summary = meta.get("summary", "")

    topics = []
    for path in sorted(directory.glob("*.md")):
        if path.name == "_section.md":
            continue
        meta, body = _parse_frontmatter(path.read_text(encoding="utf-8"))
        topic_slug = _strip_order(path.stem)
        topics.append(Topic(
            slug=topic_slug,
            section_slug=slug,
            title=meta.get("title", topic_slug.replace("-", " ").capitalize()),
            summary=meta.get("summary", ""),
            audience=tuple(
                part.strip() for part in meta.get("audience", "").split(",") if part.strip()
            ),
            keywords=tuple(
                part.strip() for part in meta.get("keywords", "").split(",") if part.strip()
            ),
            body=body,
            order=_order_of(path.stem),
            source=path,
        ))

    if not topics:
        return None

    topics.sort(key=lambda topic: (topic.order, topic.title))
    return Section(
        slug=slug,
        title=title,
        summary=summary,
        order=_order_of(directory.name),
        topics=tuple(topics),
    )


@lru_cache(maxsize=1)
def load() -> tuple[Section, ...]:
    """Every section, in reading order. Cached; call ``reload`` after an edit."""
    if not CONTENT_ROOT.exists():
        return ()

    sections = []
    for directory in sorted(CONTENT_ROOT.iterdir()):
        if not directory.is_dir():
            continue
        section = _load_section(directory)
        if section is not None:
            sections.append(section)

    sections.sort(key=lambda section: (section.order, section.title))
    return tuple(sections)


def reload() -> None:
    load.cache_clear()


def all_topics() -> list[Topic]:
    return [topic for section in load() for topic in section.topics]


def get_section(slug: str) -> Section | None:
    return next((section for section in load() if section.slug == slug), None)


def get_topic(section_slug: str, topic_slug: str) -> Topic | None:
    section = get_section(section_slug)
    if section is None:
        return None
    return next((topic for topic in section.topics if topic.slug == topic_slug), None)


def neighbours(topic: Topic) -> tuple[Topic | None, Topic | None]:
    """The previous and next topic in reading order, across section boundaries."""
    topics = all_topics()
    try:
        index = topics.index(topic)
    except ValueError:
        return None, None
    return (
        topics[index - 1] if index > 0 else None,
        topics[index + 1] if index + 1 < len(topics) else None,
    )


@dataclass(frozen=True)
class SearchHit:
    topic: Topic
    score: int
    excerpt: str


def search(query: str, limit: int = 25) -> list[SearchHit]:
    """Rank topics against a query.

    A title match outranks a keyword match, which outranks a body match, so
    searching "westgard" leads with the quality control topic rather than every
    page that happens to mention it.
    """
    terms = [term for term in re.split(r"\s+", query.strip().lower()) if term]
    if not terms:
        return []

    hits = []
    for topic in all_topics():
        title = topic.title.lower()
        keywords = " ".join(topic.keywords).lower()
        summary = topic.summary.lower()
        body = topic.body.lower()

        score = 0
        for term in terms:
            if term in title:
                score += 10
            if term in keywords:
                score += 6
            if term in summary:
                score += 4
            score += min(body.count(term), 5)

        if score:
            hits.append(SearchHit(topic=topic, score=score, excerpt=_excerpt(topic, terms)))

    hits.sort(key=lambda hit: (-hit.score, hit.topic.title))
    return hits[:limit]


def _excerpt(topic: Topic, terms: list[str], width: int = 180) -> str:
    """A snippet of body text around the first matching term."""
    plain = re.sub(r"[#*`>|\-]{1,}", " ", topic.body)
    plain = re.sub(r"\s+", " ", plain).strip()
    lowered = plain.lower()

    for term in terms:
        position = lowered.find(term)
        if position != -1:
            start = max(position - width // 3, 0)
            snippet = plain[start:start + width].strip()
            return ("… " if start else "") + snippet + ("…" if start + width < len(plain) else "")
    return plain[:width] + ("…" if len(plain) > width else "")
