"""FastAPI application factory for SignalScout AI.

Usage (from the project root):

    python -m uvicorn src.main:app --reload
    python main.py

CORS is enabled for the dashboard dev/preview servers; settings come
from environment variables (see ``src/config.py`` and ``.env.example``).
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.routes import router
from src.api.state import PipelineStore
from src.config import Settings, load_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the ASGI application (dependency-injectable for tests)."""
    settings = settings or load_settings()

    app = FastAPI(
        title="SignalScout AI API",
        version="1.0.0",
        description=(
            "Funding and AI-hiring signal intelligence with transparent "
            "source reliability and rule-based opportunity scoring."
        ),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    app.state.settings = settings
    app.state.store = PipelineStore(settings)

    @app.exception_handler(RequestValidationError)
    def _validation_error(request: Request,
                          exc: RequestValidationError) -> JSONResponse:
        # Never echo internal structures; messages come from FastAPI's
        # public validation context.
        errors = [
            {
                "location": [str(part) for part in error.get("loc", ())],
                "message": error.get("msg", "invalid value"),
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={"error": "validation_error", "details": errors},
        )

    @app.exception_handler(Exception)
    def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logging.getLogger(__name__).exception(
            "unhandled error on %s %s", request.method, request.url.path,
        )
        return JSONResponse(
            status_code=500,
            content={"error": "internal_error",
                     "message": "An unexpected error occurred."},
        )

    app.include_router(router)
    return app


#: Module-level application for ``uvicorn src.main:app``.
app = create_app()
