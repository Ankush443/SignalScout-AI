"""Fixture ingestion for the bundled sample dataset.

Loads ``data/sample_companies.json`` (clearly labeled ``sample`` data)
so the whole application works offline without any API keys or network
access.  Records keep ``data_origin="sample"`` all the way to the API so
the dashboard can visibly distinguish them from live data.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from src.ingestion.base import BaseSource, IngestionError

logger = logging.getLogger(__name__)

#: Default location of the sample dataset, resolved from this file so no
#: hardcoded absolute paths are used.
DEFAULT_DATA_FILE = (
    Path(__file__).resolve().parent.parent.parent
    / "data" / "sample_companies.json"
)


class SampleSource(BaseSource):
    """Read the local sample companies file and flatten it to records."""

    name = "sample dataset"

    def __init__(self, path: Optional[Path] = None,
                 data_origin: str = "sample") -> None:
        self.path = Path(path) if path else DEFAULT_DATA_FILE
        self.data_origin = data_origin
        self.name = f"sample dataset ({self.path.name})"

    def fetch(self, timeout: float = 0.0) -> list[dict]:
        """Return one raw record per sample signal.

        Raises ``IngestionError`` when the file is missing, unreadable,
        not JSON or not shaped like a list of companies.
        """
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                companies = json.load(handle)
        except FileNotFoundError as exc:
            raise IngestionError(
                f"sample file not found: {self.path}"
            ) from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise IngestionError(
                f"could not read sample file {self.path}: {exc}"
            ) from exc

        if not isinstance(companies, list):
            raise IngestionError(
                "sample file must contain a JSON list of companies"
            )

        records: list[dict] = []
        for company in companies:
            if not isinstance(company, dict):
                continue
            company_name = company.get("name")
            signals = company.get("signals")
            if not isinstance(signals, list):
                # Companies with missing/null signals are valid: they
                # simply contribute no signals.
                continue
            for signal in signals:
                if not isinstance(signal, dict):
                    continue
                record = dict(signal)
                record.setdefault("company_name", company_name)
                record.setdefault("data_origin", self.data_origin)
                records.append(record)

        logger.info("loaded %d sample signal record(s) from %s",
                    len(records), self.path)
        return records
