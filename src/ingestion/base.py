"""Base abstractions shared by every ingestion source.

Design goals (spec section 7):

- one failing source must never crash the application,
- repeated ingestion of the same records is prevented,
- source attribution is kept on every record,
- network access always uses a timeout.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

logger = logging.getLogger(__name__)

#: Default network timeout (seconds) for every external request.
DEFAULT_TIMEOUT_SECONDS = 10


class IngestionError(Exception):
    """Raised when a source cannot provide records (network, parse error)."""


class BaseSource(ABC):
    """A source of raw signal records (feeds, fixtures, APIs)."""

    #: Human-readable source label used in logs and error summaries.
    name: str = "source"

    @abstractmethod
    def fetch(self, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> list[dict]:
        """Return raw records, or raise :class:`IngestionError`."""

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<{type(self).__name__} name={self.name!r}>"


def safe_fetch(source: BaseSource,
               timeout: float = DEFAULT_TIMEOUT_SECONDS
               ) -> tuple[list[dict], Optional[str]]:
    """Fetch from ``source`` without ever raising.

    Returns ``(records, error_message)``; on failure ``records`` is empty
    and ``error_message`` explains what happened.  Errors are logged.
    """
    try:
        records = source.fetch(timeout=timeout)
    except Exception as exc:  # noqa: BLE001 - boundary guard by design
        message = f"{source.name}: {type(exc).__name__}: {exc}"
        logger.warning("ingestion failed for %s", message)
        return [], message

    if not isinstance(records, list):
        message = f"{source.name}: source returned a non-list result"
        logger.warning("ingestion failed for %s", message)
        return [], message

    return [r for r in records if isinstance(r, dict)], None


def _record_key(record: dict) -> Optional[tuple]:
    """Identity used to skip records already ingested this run.

    Returns ``None`` when the record carries no usable identity (no
    title, source or date) - such records are kept rather than silently
    dropped, because two unrelated unidentifiable records must not be
    treated as duplicates of each other.
    """
    url = record.get("source_url")
    if isinstance(url, str) and url.strip():
        return ("url", url.strip().lower())
    content = (
        str(record.get("title") or "").strip().lower(),
        str(record.get("source_name") or "").strip().lower(),
        str(record.get("source_published_at")
            or record.get("detected_at") or "").strip(),
    )
    if not any(content):
        return None
    return ("content",) + content


def deduplicate_records(records: Any,
                        seen: Optional[set] = None
                        ) -> tuple[list[dict], set]:
    """Drop records already present in ``seen`` and update ``seen``.

    Records without a usable identity key are kept.  Returns
    ``(new_records, updated_seen)``; the caller should persist the seen
    set across ingestion runs to prevent re-ingesting the same items.
    """
    if not isinstance(records, (list, tuple)):
        return [], seen if seen is not None else set()

    if seen is None:
        seen = set()

    fresh: list[dict] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        key = _record_key(record)
        if key is None:
            fresh.append(record)
            continue
        if key in seen:
            continue
        seen.add(key)
        fresh.append(record)
    return fresh, seen
