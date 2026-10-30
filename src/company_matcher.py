"""Company matching: group normalized signals into company profiles.

The matcher groups signals that belong to the same company (by canonical
name), counts signal types, recognizes AI-hiring activity and attaches
transparent opportunity tags used later by the scorer.

Example output per company (structure only - not a real finding):

    {
      "company": "DataBridge AI",
      "company_key": "databridge ai",
      "funding_signals": 1,
      "hiring_signals": 2,
      "ai_hiring_signals": 2,
      "opportunity_tags": ["recent_funding", "ai_team_expansion"],
      "latest_signal_date": "2026-10-16",
      "signals": [...]
    }
"""

from __future__ import annotations

from datetime import date
from typing import Any, Iterable, Optional

from src.normalizer import canonical_company_name, parse_date

#: Phrases that mark a hiring signal as AI-related (see spec section 7).
AI_ROLE_PHRASES = (
    "ai engineer",
    "ai engineering",
    "machine learning engineer",
    "machine learning",
    "ml engineer",
    "applied ai",
    "generative ai",
    "genai",
    "llm engineer",
    "llm",
    "ai research",
    "research engineer",
    "data scientist",
)

#: Funding signals at or newer than this many days old count as "recent".
RECENT_FUNDING_WINDOW_DAYS = 90


def _contains_ai_role(signal: dict) -> bool:
    """True when a hiring signal mentions an AI-related role."""
    text = " ".join(
        str(signal.get(field) or "")
        for field in ("title", "description")
    ).lower()
    return any(phrase in text for phrase in AI_ROLE_PHRASES)


def _signal_date(signal: dict) -> Optional[date]:
    """Best-known date of one signal (published, else detected)."""
    return (parse_date(signal.get("source_published_at"))
            or parse_date(signal.get("detected_at")))


def _is_recent(value: Optional[date], reference: date,
               window_days: int) -> bool:
    if value is None:
        return False
    delta = (reference - value).days
    return 0 <= delta <= window_days


def match_companies(signals: Iterable[dict],
                    *, reference_date: Optional[date] = None,
                    recent_window_days: int = RECENT_FUNDING_WINDOW_DAYS
                    ) -> list[dict]:
    """Group normalized signals into one profile per company.

    - Signals without a usable company name are skipped and counted in
      the returned ``orphan_signal_count``.
    - Duplicate company entries are impossible: grouping uses the
      canonical company key.
    - Every profile keeps references to its supporting signals.

    Returns a list of company profiles ordered by latest signal date
    (newest first, undated last).
    """
    reference = reference_date or date.today()

    buckets: dict[str, dict] = {}
    orphans = 0

    for signal in signals if isinstance(signals, (list, tuple)) else []:
        if not isinstance(signal, dict):
            continue
        key = canonical_company_name(signal.get("company_name"))
        if not key:
            orphans += 1
            continue

        profile = buckets.get(key)
        if profile is None:
            profile = {
                "company": signal.get("company_name"),
                "company_key": key,
                "funding_signals": 0,
                "hiring_signals": 0,
                "ai_hiring_signals": 0,
                "recent_funding": False,
                "signals": [],
                "data_origins": set(),
            }
            buckets[key] = profile
        profile["signals"].append(signal)

        kind = signal.get("signal_type")
        if kind == "funding":
            profile["funding_signals"] += 1
            if _is_recent(_signal_date(signal), reference,
                          recent_window_days):
                profile["recent_funding"] = True
        elif kind == "hiring":
            profile["hiring_signals"] += 1
            if _contains_ai_role(signal):
                profile["ai_hiring_signals"] += 1

        origin = signal.get("data_origin")
        if origin in ("sample", "live"):
            profile["data_origins"].add(origin)

    profiles: list[dict] = []
    for profile in buckets.values():
        dated = [d for d in (_signal_date(s) for s in profile["signals"])
                 if d is not None]
        latest = max(dated) if dated else None

        tags: list[str] = []
        if profile["recent_funding"]:
            tags.append("recent_funding")
        elif profile["funding_signals"]:
            tags.append("funding_detected")
        if profile["ai_hiring_signals"] >= 2:
            tags.append("ai_team_expansion")
        elif profile["ai_hiring_signals"] == 1:
            tags.append("ai_hiring")
        if profile["funding_signals"] and profile["hiring_signals"]:
            tags.append("funding_and_hiring")

        profile["latest_signal_date"] = latest.isoformat() if latest else None
        profile["opportunity_tags"] = tags
        profile["data_origins"] = sorted(profile["data_origins"])
        profiles.append(profile)

    profiles.sort(key=lambda p: (p["latest_signal_date"] or ""),
                  reverse=True)
    return profiles


def apply_criteria(profiles: Iterable[dict],
                   criteria: Optional[dict] = None) -> list[dict]:
    """Filter company profiles by configurable opportunity criteria.

    Supported keys (all optional):

    - ``signal_type``: ``"funding"``, ``"hiring"`` or ``"both"``.
    - ``min_ai_hiring``: minimum number of AI-related hiring signals.
    - ``require_both``: require funding and hiring signals together.
    - ``tags``: list; profile must include every listed tag.
    """
    if not isinstance(profiles, (list, tuple)):
        return []
    if not criteria:
        return list(profiles)

    signal_type = criteria.get("signal_type")
    min_ai = criteria.get("min_ai_hiring")
    require_both = criteria.get("require_both")
    required_tags = criteria.get("tags") or []

    if signal_type not in (None, "", "funding", "hiring", "both"):
        raise ValueError(
            "signal_type criteria must be 'funding', 'hiring' or 'both'"
        )

    results = []
    for profile in profiles:
        if not isinstance(profile, dict):
            continue
        funding = profile.get("funding_signals", 0)
        hiring = profile.get("hiring_signals", 0)

        if signal_type == "funding" and funding < 1:
            continue
        if signal_type == "hiring" and hiring < 1:
            continue
        if signal_type == "both" and not (funding and hiring):
            continue
        if require_both and not (funding and hiring):
            continue
        if min_ai is not None and profile.get("ai_hiring_signals", 0) < min_ai:
            continue
        if required_tags and not all(
                tag in profile.get("opportunity_tags", [])
                for tag in required_tags):
            continue
        results.append(profile)
    return results
