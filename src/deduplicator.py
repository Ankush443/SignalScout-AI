"""Cross-source duplicate detection for normalized signals.

The first deduplication stage (``src.signal_detector.deduplicate_signals``)
only removes records with identical ``signal_id`` values.  Real feeds
report the same announcement under different IDs, so this module adds a
second, conservative stage that groups likely duplicates:

    Source A: "NovaAI raises $12 million in Series A"      (ID: A_123)
    Source B: "NovaAI Technologies secures $12M Series A"  (ID: B_987)

Matching rules (all must hold):

1. Canonical company names match (equal, or one name's tokens are a
   subset of the other's - "NovaAI" vs "NovaAI Technologies").
2. Signal types match (funding never merges with hiring).
3. Normalized title similarity reaches the merge threshold.
4. Publication dates are compatible:
   - both parsed and within ``date_tolerance_days`` -> compatible,
   - both parsed but further apart -> NOT compatible,
   - either missing -> only compatible with strong title similarity
     (optionally corroborated by an equal money amount).

Titles are compared as token sets after whitespace/punctuation
normalization, money normalization ("$12 million" == "$12M") and light
stopword removal, using a containment score (intersection over the
smaller set) so that a short title contained in a longer one still scores
highly.

Every merge is explained and all original records, IDs and source URLs
are preserved on the merged result.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

from src.normalizer import (
    canonical_company_name,
    extract_amount_key,
    normalize_title_tokens,
    parse_date,
)

#: Minimum containment score for two titles to be considered the same
#: announcement when both dates are known and close.
TITLE_MERGE_THRESHOLD = 0.60

#: Titles must score at least this much before a high score alone can
#: justify merging (without corroborating amount/round evidence).
STRONG_TITLE_THRESHOLD = 0.75

#: Required title score when a publication date is missing on either side.
NO_DATE_TITLE_THRESHOLD = 0.85

#: Required title score when a date is missing but money amounts match.
NO_DATE_WITH_AMOUNT_THRESHOLD = 0.75

#: Maximum day distance between publication dates of the same announcement.
DATE_TOLERANCE_DAYS = 7


def _title_score(left: Any, right: Any) -> float:
    """Containment similarity of two titles in ``[0.0, 1.0]``."""
    left_tokens = normalize_title_tokens(left)
    right_tokens = normalize_title_tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    shared = len(left_tokens & right_tokens)
    smaller = min(len(left_tokens), len(right_tokens))
    if smaller == 0:
        return 0.0
    return shared / smaller


def _company_matches(left: Any, right: Any) -> bool:
    """Conservative company comparison using canonical names."""
    left_key = canonical_company_name(left)
    right_key = canonical_company_name(right)
    if not left_key or not right_key:
        return False
    if left_key == right_key:
        return True
    left_tokens = set(left_key.split())
    right_tokens = set(right_key.split())
    # One name fully contained in the other ("novaai" in "novaai tech").
    return bool(left_tokens) and bool(right_tokens) and (
        left_tokens <= right_tokens or right_tokens <= left_tokens
    )


def _dates_compatible(left: Any, right: Any,
                      tolerance_days: int) -> tuple[bool, Optional[str]]:
    """Return ``(compatible, explanation)`` for two publication dates."""
    left_date = parse_date(left)
    right_date = parse_date(right)
    if left_date is None or right_date is None:
        return True, "publication date missing on at least one side"
    delta = abs((left_date - right_date).days)
    if delta <= tolerance_days:
        return True, f"dates {delta} day(s) apart (<= {tolerance_days})"
    return False, f"dates {delta} day(s) apart (> {tolerance_days})"


def are_duplicates(left: dict, right: dict,
                   *, date_tolerance_days: int = DATE_TOLERANCE_DAYS
                   ) -> tuple[bool, str]:
    """Decide whether two normalized signals are the same announcement.

    Returns ``(is_duplicate, reason)`` where ``reason`` explains the
    decision in plain language.  Conservative by design: ambiguous pairs
    are kept separate.
    """
    if not isinstance(left, dict) or not isinstance(right, dict):
        return False, "one or both records are not dictionaries"

    if left.get("signal_type") != right.get("signal_type"):
        return False, "different signal types"

    if not _company_matches(left.get("company_name"),
                            right.get("company_name")):
        return False, "different companies"

    same_company = canonical_company_name(left.get("company_name"))
    title_score = _title_score(left.get("title"), right.get("title"))

    left_amount = extract_amount_key(left.get("amount"))
    right_amount = extract_amount_key(right.get("amount"))
    amount_match = (left_amount is not None
                    and left_amount == right_amount)

    date_ok, date_reason = _dates_compatible(
        left.get("source_published_at") or left.get("detected_at"),
        right.get("source_published_at") or right.get("detected_at"),
        date_tolerance_days,
    )
    left_date = parse_date(left.get("source_published_at")
                           or left.get("detected_at"))
    right_date = parse_date(right.get("source_published_at")
                            or right.get("detected_at"))
    dates_missing = left_date is None or right_date is None

    if not date_ok:
        return False, f"same company but {date_reason}"

    evidence = []
    if amount_match:
        evidence.append(f"equal amount ({left_amount})")
    strong = title_score >= STRONG_TITLE_THRESHOLD
    if strong:
        evidence.append(f"high title similarity ({title_score:.2f})")

    if dates_missing:
        threshold = NO_DATE_TITLE_THRESHOLD
        if amount_match and title_score >= NO_DATE_WITH_AMOUNT_THRESHOLD:
            threshold = NO_DATE_WITH_AMOUNT_THRESHOLD
        if title_score >= threshold:
            return (True,
                    f"company '{same_company}' matches, title similarity "
                    f"{title_score:.2f} >= {threshold:.2f}, "
                    f"{date_reason}" + (
                        f", {', '.join(evidence)}" if evidence else ""))
        return (False,
                f"company '{same_company}' matches but title similarity "
                f"{title_score:.2f} < {threshold:.2f} with "
                f"{date_reason}")

    # Both dates known and within tolerance.
    if title_score >= STRONG_TITLE_THRESHOLD or (
            title_score >= TITLE_MERGE_THRESHOLD and evidence):
        detail = [f"company '{same_company}' matches",
                  f"title similarity {title_score:.2f}",
                  date_reason]
        detail.extend(evidence)
        return True, "; ".join(detail)

    return (False,
            f"same company and {date_reason}, but title similarity "
            f"{title_score:.2f} is too low to merge")


def _source_evidence(signal: dict) -> list[dict]:
    """Extract unique, non-empty source references from one signal."""
    url = signal.get("source_url")
    name = signal.get("source_name")
    if not url and not name:
        return []
    return [{
        "source_name": name,
        "source_url": url,
        "source_published_at": signal.get("source_published_at"),
    }]


def _merge_group(group: list[dict]) -> dict:
    """Combine a group of duplicate signals into one merged record.

    The primary record is the first entry; all other records, their IDs
    and their source URLs are preserved on the result.
    """
    primary = dict(group[0])

    if len(group) == 1:
        return primary

    all_ids: list[str] = []
    sources: list[dict] = []
    seen_sources: set[tuple] = set()
    duplicate_records: list[dict] = []
    reasons: list[str] = []

    for index, signal in enumerate(group):
        signal_id = signal.get("signal_id")
        if signal_id and signal_id not in all_ids:
            all_ids.append(signal_id)
        for source in _source_evidence(signal):
            key = (source["source_url"], source["source_name"])
            if key not in seen_sources:
                seen_sources.add(key)
                sources.append(source)
        if index > 0:
            duplicate_records.append(dict(signal))

    for index in range(1, len(group)):
        _is_dup, reason = are_duplicates(group[0], group[index])
        if reason and reason not in reasons:
            reasons.append(reason)

    primary["signal_id"] = group[0].get("signal_id")
    primary["merged_signal_ids"] = all_ids
    primary["supporting_sources"] = sources
    primary["duplicate_count"] = len(group)
    primary["duplicate_records"] = duplicate_records
    primary["merge_reason"] = "; ".join(reasons) if reasons else (
        "grouped as duplicate announcement")
    return primary


def deduplicate_cross_source(
    signals: Iterable[dict],
    *, date_tolerance_days: int = DATE_TOLERANCE_DAYS,
) -> list[dict]:
    """Group likely cross-source duplicates while preserving evidence.

    Input must be normalized signals (see ``src.normalizer``).  Returns a
    new list of signals in original order; duplicate partners are merged
    into the earliest record of their group and all supporting source
    URLs are retained.
    """
    if not isinstance(signals, (list, tuple)):
        return []

    accepted: list[dict] = []
    group_indexes: list[list[int]] = []

    for signal in signals:
        if not isinstance(signal, dict):
            continue
        placed = False
        for group in group_indexes:
            representative = accepted[group[0]]
            is_dup, _reason = are_duplicates(
                representative, signal,
                date_tolerance_days=date_tolerance_days,
            )
            if is_dup:
                group.append(len(accepted))
                accepted.append(signal)
                placed = True
                break
        if not placed:
            group_indexes.append([len(accepted)])
            accepted.append(signal)

    # Groups were created in first-appearance order, so merging them in
    # that order keeps the original signal ordering.
    merged: list[dict] = []
    for group in group_indexes:
        members = [accepted[i] for i in group]
        merged.append(_merge_group(members))
    return merged
