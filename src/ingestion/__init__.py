"""Data ingestion layer for SignalScout AI.

Sources implement :class:`base.BaseSource`; the pipeline fetches records
through :func:`base.safe_fetch` so a single failing source never crashes
the application.  All sources return raw records that
:func:`src.normalizer.normalize_signal` converts into the normalized
signal schema.
"""

from src.ingestion.base import (
    BaseSource,
    IngestionError,
    deduplicate_records,
    safe_fetch,
)
from src.ingestion.rss_ingestion import RSSFeedSource, classify_text
from src.ingestion.sample_ingestion import SampleSource

__all__ = [
    "BaseSource",
    "IngestionError",
    "RSSFeedSource",
    "SampleSource",
    "classify_text",
    "deduplicate_records",
    "safe_fetch",
]
