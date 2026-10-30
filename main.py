"""SignalScout AI entry point.

Run the API server from the project root:

    python main.py                 # starts uvicorn on 127.0.0.1:8000
    python -m uvicorn main:app     # equivalent

Environment variables are documented in ``.env.example``.
"""

from __future__ import annotations

import os

from src.main import app  # re-exported for `uvicorn main:app`

__all__ = ["app"]


def _port() -> int:
    try:
        return int(os.environ.get("API_PORT", "8000"))
    except ValueError:
        return 8000


def _host() -> str:
    return os.environ.get("API_HOST", "127.0.0.1")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=_host(), port=_port(), reload=False)
