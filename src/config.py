"""Environment-based configuration for SignalScout AI.

Every setting has a working default so the application runs in demo
mode with no API keys and no internet access.  See ``.env.example``.

If a ``.env`` file exists in the project root it is read on startup
(stdlib parser, no extra dependency).  Real environment variables always
win over ``.env`` values, so exports and CI overrides keep working.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_FILE = PROJECT_ROOT / "data" / "sample_companies.json"
ENV_FILE = PROJECT_ROOT / ".env"


def load_dotenv(path: Path = ENV_FILE) -> dict:
    """Load simple ``KEY=VALUE`` lines into ``os.environ``.

    Deliberately minimal: comments and blank lines are skipped, outer
    quotes are removed, and names already present in the environment are
    never overwritten (shell exports take precedence).  Returns the
    values that were applied.  A missing file is not an error.
    """
    applied: dict = {}
    if not path.is_file():
        return applied
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return applied
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, _, value = stripped.partition("=")
        name = name.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if not name or name in os.environ:
            continue
        os.environ[name] = value
        applied[name] = value
    return applied


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass
class Settings:
    """Runtime settings; all fields fall back to safe defaults."""

    #: Comma-separated RSS/Atom feed URLs (``RSS_FEED_URLS``).
    feed_urls: List[str] = field(default_factory=list)
    #: Whether the bundled sample dataset is loaded (``INCLUDE_SAMPLE_DATA``).
    include_sample_data: bool = True
    #: Sample dataset location (``SAMPLE_DATA_FILE``).
    sample_data_file: Optional[Path] = None
    #: Network timeout for feed requests, seconds (``INGEST_TIMEOUT``).
    ingest_timeout_seconds: int = 10
    #: Funding recency window in days for scoring (``RECENT_WINDOW_DAYS``).
    recent_window_days: int = 90
    #: CORS origins (``CORS_ORIGINS``), comma separated. Default: allow the
    #: Vite dev/preview servers used by the dashboard.
    cors_origins: List[str] = field(default_factory=lambda: [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ])

    @property
    def data_file(self) -> Path:
        return self.sample_data_file or DEFAULT_DATA_FILE


def load_settings() -> Settings:
    """Build :class:`Settings` from environment variables (with defaults).

    ``.env`` in the project root is loaded first (see
    :func:`load_dotenv`); variables already set in the process
    environment are never overridden.
    """
    load_dotenv()
    raw_feeds = os.environ.get("RSS_FEED_URLS", "")
    feed_urls = [url.strip() for url in raw_feeds.split(",")
                 if url.strip()]

    raw_origins = os.environ.get("CORS_ORIGINS", "")
    cors_origins = None
    if raw_origins.strip():
        cors_origins = [o.strip() for o in raw_origins.split(",")
                        if o.strip()]

    data_file_raw = os.environ.get("SAMPLE_DATA_FILE", "")
    data_file = Path(data_file_raw) if data_file_raw.strip() else None

    settings = Settings(
        feed_urls=feed_urls,
        include_sample_data=_env_bool("INCLUDE_SAMPLE_DATA", True),
        sample_data_file=data_file,
        ingest_timeout_seconds=_env_int("INGEST_TIMEOUT", 10),
        recent_window_days=_env_int("RECENT_WINDOW_DAYS", 90),
    )
    if cors_origins is not None:
        settings.cors_origins = cors_origins
    return settings
