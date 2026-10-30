"""API routes for SignalScout AI.

Endpoints (spec section 10):

=============================== ===========================================
``GET /``                       API health and project information
``GET /health``                 Health check
``GET /stats``                  Overview metrics for the dashboard
``GET /companies``              Detected companies (filterable)
``GET /signals``                Normalized signals (filterable)
``GET /opportunities``          Ranked opportunities
``GET /companies/{company}``    Company details + supporting signals
``POST /ingest``                Re-run ingestion (configured sources only)
=============================== ===========================================

The routes only filter/serialize cached pipeline output; detection and
scoring logic live in their own modules.  ``POST /ingest`` never accepts
URLs - it re-runs the configured sample/RSS sources only, so it cannot
be abused to fetch arbitrary destinations.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query, Request

from src.api.state import PipelineStore
from src.company_matcher import apply_criteria
from src.normalizer import canonical_company_name

router = APIRouter()


def _store(request: Request) -> PipelineStore:
    return request.app.state.store


@router.get("/")
def root_info() -> dict:
    """API health and project information."""
    return {
        "name": "SignalScout AI",
        "description": (
            "Business opportunity intelligence: funding and AI-hiring "
            "signals, transparent source reliability, and rule-based "
            "opportunity scoring."
        ),
        "status": "ok",
        "docs": "/docs",
        "endpoints": [
            "/health", "/stats", "/companies", "/signals",
            "/opportunities", "/companies/{company_name}", "/ingest",
        ],
        "notice": (
            "Signals may come from a bundled sample dataset; check each "
            "record's data_origin and source_reliability fields. "
            "Scores are priority heuristics, not predictions."
        ),
    }


@router.get("/health")
def health(request: Request) -> dict:
    """Health check (does not force a pipeline run)."""
    store = _store(request)
    return {
        "status": "ok",
        "pipeline_computed": store.last_result is not None,
    }


@router.get("/stats")
def stats(request: Request) -> dict:
    """Overview metrics for the dashboard (includes diagnostics)."""
    result = _store(request).get()
    return {
        "generated_at": result["generated_at"],
        "reference_date": result["reference_date"],
        **result["stats"],
        "diagnostics": result.get("diagnostics", {}),
        "sources": result["sources"],
        "errors": result["errors"],
    }


@router.get("/companies")
def list_companies(
    request: Request,
    signal_type: Optional[Literal["funding", "hiring", "both"]] = Query(
        None, description="Only companies with this signal type"),
    q: Optional[str] = Query(None, max_length=200,
                             description="Company name search"),
    min_score: int = Query(0, ge=0, le=100,
                           description="Minimum opportunity score"),
    limit: int = Query(100, ge=1, le=500),
) -> dict:
    """List detected companies with optional filtering."""
    result = _store(request).get()
    scores = {item["company_key"]: item
              for item in result["opportunities"]}

    criteria = {"signal_type": signal_type} if signal_type else None
    companies = []
    for profile in apply_criteria(result["companies"], criteria):
        opportunity = scores.get(profile["company_key"], {})
        score = opportunity.get("opportunity_score", 0)
        if q:
            if q.lower() not in (profile.get("company") or "").lower():
                continue
        if score < min_score:
            continue
        companies.append({**profile, "opportunity": opportunity})

    return {"count": len(companies), "companies": companies[:limit]}


@router.get("/signals")
def list_signals(
    request: Request,
    signal_type: Optional[Literal["funding", "hiring"]] = Query(
        None, description="Filter by signal type"),
    company: Optional[str] = Query(None, max_length=200,
                                   description="Company name substring"),
    days: Optional[int] = Query(None, ge=1, le=3650,
                                description="Only signals from the last "
                                            "N days"),
    limit: int = Query(200, ge=1, le=1000),
) -> dict:
    """List normalized signals with basic filtering."""
    result = _store(request).get()
    signals = result["signals"]

    cutoff = None
    if days is not None:
        cutoff = date.today() - timedelta(days=days)

    filtered = []
    for signal in signals:
        if signal_type and signal.get("signal_type") != signal_type:
            continue
        if company and company.lower() not in (
                signal.get("company_name") or "").lower():
            continue
        if cutoff is not None:
            detected = signal.get("detected_at")
            if not detected:
                continue
            try:
                if date.fromisoformat(detected) < cutoff:
                    continue
            except ValueError:
                continue
        filtered.append(signal)

    return {"count": len(filtered), "signals": filtered[:limit]}


@router.get("/opportunities")
def list_opportunities(
    request: Request,
    min_score: int = Query(0, ge=0, le=100,
                           description="Minimum opportunity score"),
    sort: Literal["score", "recency"] = Query(
        "score", description="Sort by score or recency"),
    limit: int = Query(100, ge=1, le=500),
) -> dict:
    """List ranked opportunities (score is a priority heuristic)."""
    result = _store(request).get()

    opportunities = [item for item in result["opportunities"]
                     if item.get("opportunity_score", 0) >= min_score]
    if sort == "recency":
        opportunities.sort(
            key=lambda r: (r.get("latest_signal_date") or "",
                           r.get("opportunity_score", 0)),
            reverse=True,
        )

    return {
        "count": len(opportunities),
        "sort": sort,
        "notice": (
            "opportunity_score is a transparent rule-based priority "
            "heuristic, not a prediction of commercial intent."
        ),
        "opportunities": opportunities[:limit],
    }


@router.get("/companies/{company_name}")
def company_detail(company_name: str, request: Request) -> dict:
    """Company details with supporting signals and score breakdown."""
    result = _store(request).get()
    key = canonical_company_name(company_name)
    if not key:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown company: {company_name}",
        )

    profile = next(
        (p for p in result["companies"] if p.get("company_key") == key),
        None,
    )
    if profile is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown company: {company_name}",
        )

    opportunity = next(
        (o for o in result["opportunities"]
         if o.get("company_key") == key),
        None,
    )
    return {
        "company": profile.get("company"),
        "profile": profile,
        "opportunity": opportunity,
        "signals": profile.get("signals", []),
        "generated_at": result["generated_at"],
    }


@router.post("/ingest")
def ingest(request: Request) -> dict:
    """Re-run ingestion for the configured sources (sample + RSS feeds).

    The endpoint takes no URL parameters: it only reads the sample
    dataset and the feeds configured through ``RSS_FEED_URLS``, so it
    cannot be used to fetch arbitrary destinations.
    """
    result = _store(request).refresh()
    return {
        "status": "ok",
        "generated_at": result["generated_at"],
        "stats": result["stats"],
        "diagnostics": result.get("diagnostics", {}),
        "sources": result["sources"],
        "errors": result["errors"],
    }
