"""RSS/Atom ingestion for publicly accessible feeds.

The source fetches a feed URL with a timeout, parses RSS 2.0 and Atom
items with the standard library (no extra dependencies) and converts
each item that matches the funding/hiring keyword rules (spec section 7)
into a raw signal record.

Honesty notes:

- Classification is explainable keyword matching, not machine learning.
- A company name is only extracted when the item title clearly begins
  with one; otherwise ``company_name`` stays ``None`` (nothing is
  invented) and the pipeline reports such signals as unmatched.
- Every record keeps ``data_origin="live"`` so live data is always
  distinguishable from sample data.
"""

from __future__ import annotations

import logging
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from typing import Optional

from src.ingestion.base import (
    DEFAULT_TIMEOUT_SECONDS,
    BaseSource,
    IngestionError,
)

logger = logging.getLogger(__name__)

USER_AGENT = "SignalScoutAI/1.0 (+sample ingestion; contact: local)"

#: Explainable classification rules (checked in order; funding wins when
#: a title mentions both, because funding news often plans hiring).
_FUNDING_PATTERNS = (
    r"\bfunding\b", r"\braises?\b", r"\braised\b", r"\bsecures?\b",
    r"\bsecured\b", r"\bseries\s+[a-e]\b", r"\bpre-?seed\b",
    r"\bseed\s+round\b", r"\bventure\s+(capital|funding)\b",
    r"\binvestment\b", r"\binvests\b", r"\binvested\b",
    r"\bfundraising\b", r"\bcloses?\s+(a|its)\b", r"\bfinancing\b",
)

_HIRING_PATTERNS = (
    r"\bai\s+engineers?\b", r"\bmachine\s+learning\s+engineers?\b",
    r"\bml\s+engineers?\b", r"\bapplied\s+ai\b", r"\bgenerative\s+ai\b",
    r"\bgenai\b", r"\bllm\s+engineers?\b", r"\bai\s+research\b",
    r"\bis\s+hiring\b", r"\bhiring\b", r"\brecruiting\b",
    r"\bjob\s+openings?\b", r"\bopenings\b",
)

_FUNDING_RE = re.compile("|".join(_FUNDING_PATTERNS), re.IGNORECASE)
_HIRING_RE = re.compile("|".join(_HIRING_PATTERNS), re.IGNORECASE)

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

#: Phrases after which the company name starts in an item title.
#: Common announcement verbs (funding rounds, valuations, acquisitions,
#: hiring) - deliberately restricted to verbs; generic nouns are not
#: triggers because they appear in ordinary headlines.
_TRIGGER_RE = re.compile(
    r"\b(raises?|raised|secures?|secured|closes?|closed|announces?|"
    r"lands?|landed|gets?|got|completes?|completed|hits?|hit|"
    r"reaches?|reached|nabs?|nabbed|scores?|scored|banks?|banked|"
    r"acquires?|acquired|buys?|bought|hiring|is\s+hiring|recruiting|"
    r"joins?|joined|to\s+hire)\b",
    re.IGNORECASE,
)

#: Leading words that are clearly not a company name (sentence openers,
#: generic nouns, financial phrases, civic/place words seen in real
#: general-news headlines).
_GENERIC_LEAD_WORDS = frozenset({
    "the", "a", "an", "ai", "startup", "startups", "company", "companies",
    "tech", "technology", "report", "news", "how", "why", "what", "this",
    "these", "those", "after", "as", "with", "for", "investors",
    "investor", "founders", "founder", "vc", "vcs", "meet", "inside",
    "from", "amid", "before", "between", "against", "without", "during",
    "can", "could", "should", "would", "will", "may", "might", "must",
    "when", "where", "here", "there", "who", "whose", "which", "while",
    "because", "whether", "again", "today", "week", "things", "ways",
    "series", "round", "fund",
    # Civic, institutional and place words (general-news headlines).
    "police", "fire", "school", "schools", "county", "counties",
    "government", "admin", "administration", "department", "services",
    "program", "programs", "employers", "employer", "retirement",
    "senator", "sen", "budget", "city", "state", "federal", "u.s.", "us",
    "recruitment", "recruiting", "grant", "grants", "funds", "job",
    "jobs", "salary", "salaries", "market", "markets", "industry",
    "economy", "sector", "outlook", "survey", "study", "analysis",
    "tax", "taxes", "adviser", "advisers", "advisor", "advisors",
    # Common countries/place names: a country before a trigger is
    # almost never the company being announced.
    "japan", "singapore", "china", "india", "canada", "germany",
    "france", "russia", "korea", "britain", "europe", "australia",
    "mexico", "taiwan", "israel", "brazil", "british", "american",
    "french", "german", "european", "asian",
})

#: Connectors that may legitimately appear inside a multi-word name
#: ("Bank of America").
_NAME_CONNECTORS = frozenset({"of", "and", "&", "'"})

#: Words that only occur mid-sentence in a headline; any of them in a
#: candidate means the candidate is a sentence, not a name.
_SENTENCE_TOKENS = frozenset({
    "how", "why", "what", "when", "where", "here", "here's", "here\u2019s",
    "there", "whether", "because", "who", "whom", "which", "while",
    "says", "said", "say", "really", "just", "still", "even", "meet",
    "investors", "investor", "founders", "founder", "startups",
    "startup", "report", "reports", "news", "week", "today",
    # Common sentence verbs seen mid-candidate in real headlines.
    "exposes", "expose", "reveals", "reveal", "unmasks", "unmask",
    "wants", "want", "aims", "aim", "seeks", "seek", "eyes", "eye",
    "plans", "plan", "needs", "need", "faces", "face", "leads", "lead",
    "weighs", "tussles", "unveils", "debuts", "slams", "hits", "faces",
})

#: Descriptor nouns that introduce the real name in a headline
#: ("Legal AI startup Legora ..." -> "Legora").
_DESCRIPTOR_WORDS = frozenset({
    "startup", "startups", "firm", "firms", "company", "companies",
    "maker", "makers", "developer", "developers", "provider",
    "providers", "vendor", "vendors", "studio", "studios",
    "platform", "platforms", "label", "labels",
})


def _strip_html(value: Optional[str]) -> Optional[str]:
    if not isinstance(value, str):
        return None
    text = _HTML_TAG_RE.sub(" ", value)
    text = _WS_RE.sub(" ", text).strip()
    return text or None


def classify_text(text: Optional[str]) -> Optional[str]:
    """Classify free text as ``"funding"``, ``"hiring"`` or ``None``.

    Funding patterns are checked first: funding articles frequently also
    mention hiring plans, while genuine job posts rarely announce
    funding rounds.
    """
    if not isinstance(text, str) or not text.strip():
        return None
    if _FUNDING_RE.search(text):
        return "funding"
    if _HIRING_RE.search(text):
        return "hiring"
    return None


def _clean_token(token: str) -> str:
    """Lowercase a token and strip punctuation for word-level checks."""
    return token.lower().strip(".,:;!?\"'()\u201c\u201d\u2018\u2019")


def extract_company_name(title: Optional[str]) -> Optional[str]:
    """Conservatively extract a company name from an item title.

    Takes the text before the first trigger phrase (``raises``,
    ``hits``, ``hiring``, ...): "NovaAI raises $12M" -> "NovaAI".

    Conservative rules (names are never guessed):

    * A leading descriptor phrase is removed and the name after it is
      kept: "Legal AI startup Legora raises ..." -> "Legora".
    * Tokens like "NYC-based" or "OpenAI-backed" are dropped.
    * The name must start with a capitalized token - a lowercase or
      numeric lead ("$10,000: Employers ...") is a sentence, not a name.
    * Only the leading capitalized run is kept ("Metaview wants to
      eliminate ..." -> "Metaview"); a generic word right after the run
      ("Lassen County Adopts ...") rejects the candidate entirely.
    * Sentence openers, mid-sentence words and possessives reject the
      candidate - a headline sentence is not a name.
    * At most six tokens; otherwise the candidate is too ambiguous.
    """
    if not isinstance(title, str) or not title.strip():
        return None
    match = _TRIGGER_RE.search(title)
    candidate = title[:match.start()] if match else ""
    candidate = _WS_RE.sub(" ", candidate).strip(" ,:;-|.!?\"'()\u201c\u201d")
    # Drop a trailing linking verb ("CloudStack is" -> "CloudStack").
    candidate = re.sub(r"\b(is|are|was|were)\b\s*$", "",
                       candidate, flags=re.IGNORECASE).strip()
    if not candidate:
        return None
    # Drop parenthetical clarifiers ("Thrive Holdings (NASDAQ: ADT)" -> ...).
    candidate = re.sub(r"\([^)]*\)", " ", candidate)
    candidate = _WS_RE.sub(" ", candidate).strip()
    if not candidate:
        return None
    # Drop location/adjective tags such as "NYC-based" or "OpenAI-backed".
    tokens = [t for t in candidate.split()
              if not re.search(r"-(based|backed)$", t, re.IGNORECASE)]
    if not tokens:
        return None
    # A descriptor noun introduces the real name: keep what follows the
    # last descriptor ("Legal AI startup Legora" -> "Legora").  If the
    # descriptor ends the candidate, the title is ambiguous -> reject.
    descriptor_positions = [
        i for i, t in enumerate(tokens)
        if _clean_token(t) in _DESCRIPTOR_WORDS
    ]
    if descriptor_positions:
        tokens = tokens[descriptor_positions[-1] + 1:]
        if not tokens:
            return None
    # A company name starts with a capitalized token; then keep only the
    # leading capitalized run ("Metaview wants to eliminate ..." ->
    # "Metaview").  Connectors ("of", "&") may continue the run; a
    # lowercase run-stopper that is itself generic ("Lassen County
    # Adopts ...") means the run is part of a phrase -> reject.
    if not tokens[0][0].isupper():
        return None
    run: list[str] = []
    for token in tokens:
        if token[0].isupper():
            run.append(token)
            continue
        cleaned_token = _clean_token(token)
        if cleaned_token in _NAME_CONNECTORS:
            run.append(token)
            continue
        if cleaned_token in _GENERIC_LEAD_WORDS:
            return None
        break
    tokens = run
    if not tokens:
        return None
    if len(tokens) > 6:
        return None
    cleaned = [_clean_token(t) for t in tokens]
    # Possessives ("Anthropic's backers") indicate a sentence.
    if any(t.endswith("'s") or t.endswith("\u2019s") for t in cleaned):
        return None
    # Any generic word anywhere in the candidate means a phrase
    # ("Houston Fire Department" is not a startup name).
    if any(t in _GENERIC_LEAD_WORDS for t in cleaned):
        return None
    # Mid-sentence words anywhere in the candidate mean a sentence.
    if any(t in _SENTENCE_TOKENS for t in cleaned):
        return None
    return " ".join(tokens)


def _text(element: Optional[ET.Element], *tags: str) -> Optional[str]:
    """Find the first non-empty child text among ``tags`` (any namespace)."""
    if element is None:
        return None
    for child in element.iter():
        if child is element:
            continue
        local = child.tag.rsplit("}", 1)[-1].lower()
        if local in tags and child.text and child.text.strip():
            return child.text.strip()
    return None


def _link(element: Optional[ET.Element]) -> Optional[str]:
    """RSS uses ``<link>`` text; Atom uses ``<link href=...>``."""
    if element is None:
        return None
    for child in element.iter():
        local = child.tag.rsplit("}", 1)[-1].lower()
        if local == "link":
            href = child.attrib.get("href")
            if href:
                return href.strip()
            if child.text and child.text.strip():
                return child.text.strip()
    return None


def _to_raw_signal(item: ET.Element, feed_name: Optional[str],
                   default_origin: str) -> Optional[dict]:
    title = _strip_html(_text(item, "title"))
    description = _strip_html(
        _text(item, "description", "summary", "content")
    )
    combined = " ".join(part for part in (title, description) if part)
    signal_type = classify_text(combined)
    if signal_type is None or not title:
        return None

    published = _text(item, "pubdate", "published", "updated", "date")
    source_url = _link(item)
    signal_id = _text(item, "guid", "id")

    return {
        "signal_id": signal_id,
        "company_name": extract_company_name(title),
        "signal_type": signal_type,
        "title": title,
        "description": description,
        "detected_at": published,
        "source_name": feed_name,
        "source_url": source_url,
        "source_published_at": published,
        "data_origin": default_origin,
    }


class RSSFeedSource(BaseSource):
    """Fetch and parse one public RSS or Atom feed."""

    def __init__(self, url: str, name: Optional[str] = None,
                 data_origin: str = "live") -> None:
        if not isinstance(url, str) or not url.strip():
            raise ValueError("feed url must be a non-empty string")
        self.url = url.strip()
        self.name = (name or url).strip()
        self.data_origin = data_origin
        #: Observability counters for the most recent ``fetch`` call:
        #: total feed entries parsed and how many classified as
        #: funding/hiring signals (the difference is reported as
        #: "unclassified" rather than silently discarded).
        self.last_fetch_stats = {"items_parsed": 0, "items_classified": 0}

    def fetch(self, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> list[dict]:
        """Download and parse the feed.  Raises ``IngestionError`` on
        network problems or malformed XML so callers can fall back."""
        self.last_fetch_stats = {"items_parsed": 0, "items_classified": 0}
        request = urllib.request.Request(
            self.url, headers={"User-Agent": USER_AGENT},
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = response.read()
        except (urllib.error.URLError, urllib.error.HTTPError,
                TimeoutError, OSError, ValueError) as exc:
            raise IngestionError(
                f"failed to fetch feed {self.url}: {exc}"
            ) from exc

        try:
            root = ET.fromstring(payload)
        except ET.ParseError as exc:
            raise IngestionError(
                f"feed {self.url} is not valid XML: {exc}"
            ) from exc

        local_root = root.tag.rsplit("}", 1)[-1].lower()
        feed_name = None
        records: list[dict] = []

        if local_root == "rss":  # RSS 2.0
            channel = next(
                (c for c in root if c.tag.rsplit("}", 1)[-1].lower()
                 == "channel"), None,
            )
            feed_name = _text(channel, "title")
            items = [c for c in (channel.iter() if channel is not None else [])
                     if c.tag.rsplit("}", 1)[-1].lower() == "item"]
        elif local_root == "feed":  # Atom
            feed_name = _text(root, "title")
            items = [c for c in root
                     if c.tag.rsplit("}", 1)[-1].lower() == "entry"]
        else:
            raise IngestionError(
                f"feed {self.url} has an unsupported root element "
                f"<{local_root}>"
            )

        for item in items:
            record = _to_raw_signal(item, feed_name, self.data_origin)
            if record is not None:
                records.append(record)

        self.last_fetch_stats = {
            "items_parsed": len(items),
            "items_classified": len(records),
        }
        logger.info("fetched %d signal record(s) from %s",
                    len(records), self.name)
        return records
