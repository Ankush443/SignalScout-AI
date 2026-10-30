"""Normalization helpers for the SignalScout AI pipeline.

This module turns raw records (sample JSON, RSS items, API payloads) into
the normalized signal schema used by the rest of the application:

    {
      "signal_id": "FUNDING001",
      "company_name": "NovaAI Technologies",
      "signal_type": "funding",          # or "hiring"
      "title": "...",
      "description": "...",              # optional
      "amount": "$12 million",           # optional, funding only
      "detected_at": "2026-10-19",       # ISO date when known
      "source_name": "Example News",
      "source_url": "https://...",
      "source_published_at": "2026-10-18",
      "verification_status": "unverified",
      "data_origin": "sample"            # "sample" or "live"
    }

Rules:
- Missing optional fields become ``None``; nothing is ever invented.
- Unparseable dates become ``None`` (a wrong date is worse than no date).
- Incoming ``verification_status`` values from raw data are NOT trusted;
  normalization resets them.  Only trusted application logic may mark a
  signal as verified (see ``src/source_reliability.py``).
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Signal type normalization
# ---------------------------------------------------------------------------

#: Raw values accepted as funding signals (matched after lower/strip).
FUNDING_ALIASES = frozenset({
    "funding", "investment", "investments", "fundraising", "financing",
    "seed", "round", "funding_round",
})

#: Raw values accepted as hiring signals.
HIRING_ALIASES = frozenset({
    "hiring", "recruiting", "recruitment", "jobs", "job_postings",
    "talent",
})

_WS_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^\w\s$]", re.UNICODE)
_MONEY_RE = re.compile(
    r"\$?\s*(\d+(?:[.,]\d+)?)\s*(m|mn|mm|million|b|bn|billion|k|thousand)?\b",
    re.IGNORECASE,
)

#: Multipliers that convert a raw amount into millions for comparison.
_AMOUNT_UNIT_MULTIPLIERS = {
    "m": 1.0, "mn": 1.0, "mm": 1.0, "million": 1.0,
    "b": 1000.0, "bn": 1000.0, "billion": 1000.0,
    "k": 0.001, "thousand": 0.001,
}

_DATE_FORMATS = (
    "%Y-%m-%d",        # 2026-10-19
    "%Y/%m/%d",        # 2026/10/19
    "%d %b %Y",        # 19 Oct 2026
    "%d %B %Y",        # 19 October 2026
    "%b %d, %Y",       # Oct 19, 2026
    "%B %d, %Y",       # October 19, 2026
    # RSS (RFC 822) publication dates:
    "%a, %d %b %Y %H:%M:%S %Z",   # Thu, 29 Oct 2026 08:00:00 GMT
    "%a, %d %b %Y %H:%M:%S %z",   # Thu, 29 Oct 2026 08:00:00 +0000
)


def collapse_whitespace(value: str) -> str:
    """Return ``value`` with all runs of whitespace reduced to single spaces."""
    return _WS_RE.sub(" ", value).strip()


def normalize_signal_type(value: Any) -> Optional[str]:
    """Normalize a raw signal type to ``"funding"``, ``"hiring"`` or ``None``.

    Accepts mixed casing and surrounding whitespace.  Unknown or malformed
    values return ``None`` so callers can skip the record instead of
    guessing.
    """
    if value is None:
        return None
    text = collapse_whitespace(str(value)).lower()
    if not text:
        return None
    if text in FUNDING_ALIASES:
        return "funding"
    if text in HIRING_ALIASES:
        return "hiring"
    return None


def normalize_company_name(value: Any) -> Optional[str]:
    """Return a clean display name for a company, or ``None`` if unusable."""
    if value is None:
        return None
    text = collapse_whitespace(str(value)).strip(" ,.-")
    return text or None


#: Legal suffixes stripped when building the canonical matching key.
_COMPANY_SUFFIXES = frozenset({
    "inc", "incorporated", "llc", "ltd", "limited", "llp", "plc", "corp",
    "corporation", "co", "company", "gmbh", "ag", "sa", "sas", "bv", "nv",
    "pty", "pte", "srl", "spa", "oy", "ab", "as", "aps", "kgaa",
})


def canonical_company_name(value: Any) -> Optional[str]:
    """Build a canonical key used to group the same company's signals.

    Lowercases, collapses whitespace, drops punctuation and strips common
    legal suffixes (Inc, Ltd, GmbH, ...).  Returns ``None`` when no
    usable name remains.
    """
    display = normalize_company_name(value)
    if display is None:
        return None
    tokens = re.sub(r"[^\w\s]", " ", display.lower()).split()
    while tokens and tokens[-1] in _COMPANY_SUFFIXES:
        tokens.pop()
    return " ".join(tokens) or None


def normalize_title(value: Any) -> Optional[str]:
    """Return a cleaned title, or ``None`` when nothing usable remains."""
    if value is None:
        return None
    text = collapse_whitespace(str(value))
    return text or None


def normalize_title_tokens(value: Any) -> frozenset:
    """Token set used for conservative title similarity comparisons.

    Lowercases, removes punctuation, normalizes common money expressions
    (``$12 million`` / ``$12M`` -> ``12m``) and drops light stopwords.
    """
    if value is None:
        return frozenset()
    text = str(value).lower().replace("$", " ").replace(",", "")

    def _money(match: "re.Match[str]") -> str:
        key = extract_amount_key(match.group(0))
        if key is None:
            return " "
        # "_" keeps decimal amounts as a single word token; other
        # punctuation is stripped right after this substitution.
        return f" {key.replace('.', '_')} "

    text = _MONEY_RE.sub(_money, text)
    text = re.sub(r"[^\w\s]", " ", text)

    stopwords = frozenset({
        "a", "an", "the", "in", "of", "to", "and", "for", "with", "by",
        "from", "at", "on", "its", "is", "are", "as", "into", "after",
        "has", "have", "will", "be",
    })
    return frozenset(token for token in text.split()
                     if token and token not in stopwords)


def normalize_amount(value: Any) -> Optional[str]:
    """Return a cleaned human-readable amount string, or ``None``.

    Does not convert currencies or invent values; only trims whitespace.
    """
    if value is None:
        return None
    text = collapse_whitespace(str(value))
    return text or None


def extract_amount_key(value: Any) -> Optional[str]:
    """Build a comparable amount key normalized to millions.

    ``"$12 million"`` and ``"$12M"`` both produce ``"12m"``;
    ``"$4.5 million"`` produces ``"4.5m"``; a bare dollar figure such as
    ``"$12,000,000"`` also produces ``"12m"``.  Returns ``None`` when no
    numeric amount can be found.  Used only for equality comparisons -
    values are never displayed as amounts.
    """
    if value is None:
        return None
    # Commas are dropped first so "$12,000,000" is one number, then the
    # dollar sign becomes a word separator.
    match = _MONEY_RE.search(str(value).replace("$", " ").replace(",", ""))
    if not match:
        return None
    raw_number = match.group(1).replace(",", "")
    if not raw_number:
        return None
    try:
        number = float(raw_number)
    except ValueError:
        return None
    unit = (match.group(2) or "").lower()
    if unit:
        multiplier = _AMOUNT_UNIT_MULTIPLIERS.get(unit)
        if multiplier is None:
            return None
        number *= multiplier
    else:
        # No unit: treat the figure as a raw dollar amount.
        number /= 1_000_000
    return f"{number:g}m"


def parse_date(value: Any) -> Optional[date]:
    """Parse a raw date value into a ``datetime.date``.

    Supports ISO (``2026-10-19``), slash (``2026/10/19``) and a few common
    written formats.  Already-date/datetime objects pass through.
    Anything unparseable returns ``None``.
    """
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    text = collapse_whitespace(value)
    if not text:
        return None
    # ISO datetimes ("2026-10-29T08:00:00Z", "2026-10-19 08:00", ...).
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        pass
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def to_iso_date(value: Any) -> Optional[str]:
    """Return the ISO (``YYYY-MM-DD``) form of ``value``, or ``None``."""
    parsed = parse_date(value)
    return parsed.isoformat() if parsed else None


def normalize_source_url(value: Any) -> Optional[str]:
    """Return a trimmed source URL string, or ``None`` when absent.

    Validation (scheme/host checks) is handled by
    ``src.source_reliability.assess_source``; this function only cleans.
    """
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def normalize_signal(record: Any, company_name: Any = None,
                     data_origin: str = "sample") -> Optional[dict]:
    """Convert one raw record into the normalized signal schema.

    Returns ``None`` when the record is not a dictionary or does not carry
    a recognizable funding/hiring signal type (such records are skipped,
    never guessed at).
    """
    if not isinstance(record, dict):
        return None

    signal_type = normalize_signal_type(record.get("signal_type"))
    if signal_type is None:
        return None

    company = normalize_company_name(company_name if company_name is not None
                                     else record.get("company_name"))

    signal_id = record.get("signal_id")
    if signal_id is not None:
        signal_id = str(signal_id).strip() or None

    detected_at = to_iso_date(
        record.get("detected_at") or record.get("source_published_at")
    )
    published_at = to_iso_date(record.get("source_published_at"))

    origin = data_origin
    if record.get("data_origin") in ("sample", "live"):
        origin = record["data_origin"]

    return {
        "signal_id": signal_id,
        "company_name": company,
        "signal_type": signal_type,
        "title": normalize_title(record.get("title")),
        "description": normalize_title(record.get("description")),
        "amount": normalize_amount(record.get("amount")),
        "detected_at": detected_at,
        "source_name": normalize_title(record.get("source_name")),
        "source_url": normalize_source_url(record.get("source_url")),
        "source_published_at": published_at,
        # Raw verification flags are deliberately discarded: only trusted
        # application logic may assign "verified".
        "verification_status": "unverified",
        "data_origin": origin,
    }


def normalize_signals(records: Any, company_name: Any = None,
                      data_origin: str = "sample") -> list[dict]:
    """Normalize an iterable of raw records, skipping malformed entries."""
    if not isinstance(records, (list, tuple)):
        return []
    normalized: list[dict] = []
    for record in records:
        signal = normalize_signal(record, company_name, data_origin)
        if signal is not None:
            normalized.append(signal)
    return normalized
