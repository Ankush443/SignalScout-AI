"""Pipeline state container for the API.

The pipeline result is computed lazily on first use and cached; the
``POST /ingest`` endpoint refreshes it explicitly.  A lock keeps
concurrent requests from triggering duplicate runs.  State lives on the
FastAPI application object (``app.state``) rather than in module-level
globals.

Each run uses its own ingestion identity set: repeated refreshes
re-read the configured sources, and duplicate records *within* a run
are still skipped (cross-source dedup guarantees the final signal list
never contains the same announcement twice).
"""

from __future__ import annotations

import logging
import threading
from typing import Optional

from src.config import Settings
from src.pipeline import run_pipeline

logger = logging.getLogger(__name__)


class PipelineStore:
    """Thread-safe cache of the latest pipeline result."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._result: Optional[dict] = None
        self._lock = threading.Lock()

    def get(self) -> dict:
        """Return the current result, running the pipeline if needed."""
        with self._lock:
            if self._result is None:
                self._result = run_pipeline(self.settings)
            return self._result

    def refresh(self) -> dict:
        """Force a fresh pipeline run (used by ``POST /ingest``)."""
        with self._lock:
            self._result = run_pipeline(self.settings)
            return self._result

    @property
    def last_result(self) -> Optional[dict]:
        return self._result
