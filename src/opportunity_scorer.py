"""Transparent, rule-based opportunity scoring and ranking.

The score is an **opportunity-priority heuristic (0-100)** that helps users
decide which companies deserve attention first.  It is NOT a probability
that a company will buy a product or service, and it is not a prediction.

Scoring factors (defaults, weights sum to 100):

| Factor                                | Weight |
|---------------------------------------|-------:|
| Recent funding announcement           |     30 |
| Multiple AI-related hiring signals    |     30 |
| Presence of funding AND hiring        |     25 |
| Source quality / evidence availability|     15 |

Design rules:

- Every point derives from actual signal data; missing data never earns
  maximum points (a URL provides traceable evidence, not proof of a
  claim: a valid-but-unverified URL earns partial evidence credit only).
- The full breakdown is returned with every score so results can be
  audited and the rules tuned (all weights live in ``SCORING_WEIGHTS``).
- Supporting signals are included for every opportunity.
"""

from __future__ import annotations

from datetime import date
from datetime import date as _today
from typing import Iterable, Optional

from src.company_matcher import RECENT_FUNDING_WINDOW_DAYS

#: Scoring weights (must total 100).
SCORING_WEIGHTS = {
    "recent_funding": 30,
    "ai_hiring": 30,
    "both_signal_types": 25,
    "source_evidence": 15,
}

#: Partial credit for an old (outside the recency window) funding signal.
OLD_FUNDING_POINTS = 15

#: Partial credit for exactly one AI-related hiring signal.
SINGLE_AI_HIRING_POINTS = 15

#: Evidence points granted when at least one signal carries a usable
#: (http/https) source URL.  Traceability only - not proof.
EVIDENCE_URL_POINTS = 8

#: Extra evidence points granted when at least one source has passed an
#: explicit trusted verification process.
EVIDENCE_VERIFIED_POINTS = 7


def _reliability_of(signal: dict) -> str:
    value = signal.get("source_reliability")
    if value in ("missing_source", "invalid_source_url", "unverified",
                 "verified"):
        return value
    return "missing_source"


def _funding_points(profile: dict, reference: date,
                    window_days: int) -> tuple[int, str]:
    if not profile.get("funding_signals"):
        return 0, "No funding signal detected (0/30)"
    if profile.get("recent_funding"):
        return SCORING_WEIGHTS["recent_funding"], (
            "Recent funding signal detected (30/30)"
        )
    # Funding exists but is older than the recency window, or undated:
    # partial credit only, because recency could not be confirmed.
    return OLD_FUNDING_POINTS, (
        f"Funding signal detected but not recent "
        f"(outside {window_days}-day window: {OLD_FUNDING_POINTS}/30)"
    )


def _ai_hiring_points(profile: dict) -> tuple[int, str]:
    count = profile.get("ai_hiring_signals", 0)
    if count >= 2:
        return SCORING_WEIGHTS["ai_hiring"], (
            f"Multiple AI-related hiring signals detected "
            f"({count} signals: 30/30)"
        )
    if count == 1:
        return SINGLE_AI_HIRING_POINTS, (
            f"Single AI-related hiring signal detected (15/30)"
        )
    return 0, "No AI-related hiring signals detected (0/30)"


def _both_types_points(profile: dict) -> tuple[int, str]:
    funding = profile.get("funding_signals", 0)
    hiring = profile.get("hiring_signals", 0)
    if funding and hiring:
        return SCORING_WEIGHTS["both_signal_types"], (
            "Both funding and hiring signals present (25/25)"
        )
    if funding:
        return 0, "Funding signals present but no hiring signals (0/25)"
    if hiring:
        return 0, "Hiring signals present but no funding signals (0/25)"
    return 0, "No signals of either type (0/25)"


def _evidence_points(profile: dict) -> tuple[int, str]:
    signals = profile.get("signals", [])
    if not signals:
        return 0, "No supporting signals, no evidence available (0/15)"

    reliabilities = [_reliability_of(s) for s in signals]
    has_url = any(r in ("unverified", "verified") for r in reliabilities)
    has_verified = "verified" in reliabilities

    points = 0
    notes = []
    if has_url:
        points += EVIDENCE_URL_POINTS
        notes.append(
            f"at least one usable source URL (traceable evidence, "
            f"not proof: +{EVIDENCE_URL_POINTS})"
        )
    if has_verified:
        points += EVIDENCE_VERIFIED_POINTS
        notes.append(
            f"at least one explicitly verified source "
            f"(+{EVIDENCE_VERIFIED_POINTS})"
        )
    if not notes:
        notes.append(
            "all sources missing or invalid, no evidence available (0/15)"
        )
    return points, "Source evidence: " + "; ".join(notes)


def score_opportunity(profile: dict,
                      *, reference_date: Optional[date] = None,
                      recent_window_days: int = RECENT_FUNDING_WINDOW_DAYS
                      ) -> dict:
    """Score one company profile and return a full, auditable result.

    Result keys: ``company``, ``opportunity_score``, ``reasons``,
    ``score_breakdown``, ``evidence_count``,
    ``latest_signal_date``, ``opportunity_tags``, ``data_origins``.
    """
    reference = reference_date or _today.today()
    signals = profile.get("signals", []) if isinstance(profile, dict) else []

    funding_pts, funding_note = _funding_points(profile, reference,
                                                recent_window_days)
    ai_pts, ai_note = _ai_hiring_points(profile)
    both_pts, both_note = _both_types_points(profile)
    evidence_pts, evidence_note = _evidence_points(profile)

    total = funding_pts + ai_pts + both_pts + evidence_pts
    total = max(0, min(100, total))

    breakdown = [
        {"factor": "recent_funding", "points": funding_pts,
         "max_points": SCORING_WEIGHTS["recent_funding"],
         "explanation": funding_note},
        {"factor": "ai_hiring", "points": ai_pts,
         "max_points": SCORING_WEIGHTS["ai_hiring"],
         "explanation": ai_note},
        {"factor": "both_signal_types", "points": both_pts,
         "max_points": SCORING_WEIGHTS["both_signal_types"],
         "explanation": both_note},
        {"factor": "source_evidence", "points": evidence_pts,
         "max_points": SCORING_WEIGHTS["source_evidence"],
         "explanation": evidence_note},
    ]

    reasons = [item["explanation"] for item in breakdown
               if item["points"] > 0]
    if not reasons:
        if signals:
            reasons = [
                f"{len(signals)} signal(s) present, but none met a scoring "
                f"criterion (0/100)"
            ]
        else:
            reasons = ["No qualifying signals detected for this company"]

    return {
        "company": profile.get("company"),
        "company_key": profile.get("company_key"),
        "opportunity_score": total,
        "reasons": reasons,
        "score_breakdown": breakdown,
        "evidence_count": len(signals),
        "funding_signals": profile.get("funding_signals", 0),
        "hiring_signals": profile.get("hiring_signals", 0),
        "ai_hiring_signals": profile.get("ai_hiring_signals", 0),
        "latest_signal_date": profile.get("latest_signal_date"),
        "opportunity_tags": list(profile.get("opportunity_tags", [])),
        "data_origins": list(profile.get("data_origins", [])),
    }


def rank_opportunities(profiles: Iterable[dict],
                       *, reference_date: Optional[date] = None,
                       recent_window_days: int = RECENT_FUNDING_WINDOW_DAYS,
                       sort_by: str = "score") -> list[dict]:
    """Score every profile and rank them.

    ``sort_by`` is ``"score"`` (default; ties broken by recency) or
    ``"recency"`` (ties broken by score).
    """
    results = []
    for profile in profiles if isinstance(profiles, (list, tuple)) else []:
        if not isinstance(profile, dict):
            continue
        results.append(score_opportunity(
            profile, reference_date=reference_date,
            recent_window_days=recent_window_days,
        ))

    if sort_by == "recency":
        results.sort(key=lambda r: (r.get("latest_signal_date") or "",
                                    r.get("opportunity_score", 0)),
                     reverse=True)
    else:
        results.sort(key=lambda r: (r.get("opportunity_score", 0),
                                    r.get("latest_signal_date") or ""),
                     reverse=True)
    return results
