"""FastAPI application exposing search, ask, and hypothesize endpoints.

This is intentionally small: JSON endpoints + one static HTML page.
The HTML page (`static/index.html`) is the Evidence Engine UI.

For public deployment (Docker / Render / VPS), configure:
- ``VITILIGO_DB_PATH`` pointing at a persistent volume with the corpus DB
- ``ANTHROPIC_API_KEY`` for Ask / Hypothesize
- ``VITILIGO_RATE_LIMIT_POST_PER_MINUTE`` (default 30) for basic abuse protection
"""

from __future__ import annotations

import asyncio
import logging
import threading
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from vitiligo import __version__
from vitiligo.config import get_settings
from vitiligo.corpus_stats import get_corpus_stats
from vitiligo.embed import semantic_search
from vitiligo.evidence import classify_document, evidence_level_label
from vitiligo.graph import export_graph_snapshot, get_neighbors, search_entities, summarize_graph
from vitiligo.reasoning import (
    CorpusUnavailable,
    LLMUnavailable,
    ask_with_citations,
    generate_hypotheses,
)
from vitiligo.reasoning.hypothesize import report_to_dict as hypothesize_report_to_dict
from vitiligo.reports import build_candidate_report
from vitiligo.reports import report_to_dict as candidate_report_to_dict
from vitiligo.storage import TrialSourceKind, init_db
from vitiligo.trials import TrialFilter, list_trials, summarize_trials
from vitiligo.trials.query import count_trials
from vitiligo.web.llm_budget import LLMBudget, LLMBudgetExceeded
from vitiligo.web.proxy import ForwardedProtoMiddleware
from vitiligo.web.ratelimit import RateLimitMiddleware

STATIC_DIR = Path(__file__).resolve().parent / "static"
logger = logging.getLogger(__name__)


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Free-text search query.")
    top_k: int = Field(10, ge=1, le=50)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1)
    top_k: int = Field(8, ge=1, le=25)


class HypothesizeRequest(BaseModel):
    intent: str = Field(..., min_length=1, description="Research intent, e.g. 'stop spread'.")
    top_k: int = Field(25, ge=5, le=50)


class TrialsSearchRequest(BaseModel):
    query: str | None = Field(None, description="Free-text term over title / summary / conditions.")
    status: str | None = Field(None, description="Overall status (e.g. RECRUITING, COMPLETED).")
    phase: str | None = Field(None, description="Phase (e.g. PHASE2).")
    country: str | None = Field(None, description="Location country.")
    source: str | None = Field(None, description="Restrict to a registry: ctgov | euctr | ictrp.")
    has_results: bool | None = Field(None, description="Restrict to trials with reported results.")
    limit: int = Field(25, ge=1, le=100)
    offset: int = Field(0, ge=0)


def _trial_to_dict(trial: Any) -> dict[str, Any]:
    src = trial.source
    return {
        "source": src.value if hasattr(src, "value") else str(src),
        "source_id": trial.source_id,
        "brief_title": trial.brief_title,
        "official_title": trial.official_title,
        "status": trial.status,
        "phases": trial.phases,
        "study_type": trial.study_type,
        "summary": trial.summary,
        "conditions": trial.conditions,
        "interventions": trial.interventions,
        "sponsors": trial.sponsors,
        "countries": trial.countries,
        "enrollment_count": trial.enrollment_count,
        "enrollment_type": trial.enrollment_type,
        "primary_outcomes": trial.primary_outcomes,
        "secondary_outcomes": trial.secondary_outcomes,
        "start_date": trial.start_date,
        "completion_date": trial.completion_date,
        "last_update_date": trial.last_update_date,
        "has_results": trial.has_results,
    }


# Candidate reports are deterministic for a given corpus, but each build runs
# several semantic searches. Cache per (top_n, DB file, DB mtime) so repeated
# GETs are cheap; any DB write invalidates.
_candidate_report_cache: dict[tuple[int, str, int], dict[str, Any]] = {}
_candidate_report_lock = threading.Lock()


def _cached_candidate_report(top_n: int) -> dict[str, Any]:
    db_path = get_settings().resolved_db_path
    mtime = db_path.stat().st_mtime_ns if db_path.is_file() else 0
    key = (top_n, str(db_path), mtime)
    with _candidate_report_lock:
        cached = _candidate_report_cache.get(key)
        if cached is None:
            cached = candidate_report_to_dict(build_candidate_report(top_n=top_n))
            stale = [k for k in _candidate_report_cache if k[1:] != key[1:]]
            for k in stale:
                del _candidate_report_cache[k]
            _candidate_report_cache[key] = cached
        return cached


def _prewarm_embeddings() -> None:
    from vitiligo.embed.cache import warm_embedding_index
    from vitiligo.embed.encoder import get_encoder

    logger.info("Prewarming embedding model...")
    get_encoder().encode(["vitiligo evidence engine warmup"])
    count = warm_embedding_index()
    logger.info("Embedding model ready (index vectors=%d).", count)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    settings = get_settings()
    if settings.prewarm_embeddings:
        try:
            await asyncio.to_thread(_prewarm_embeddings)
        except Exception:
            logger.exception("Embedding prewarm failed; first search may be slow.")
    yield


def create_app() -> FastAPI:
    init_db()
    settings = get_settings()

    app = FastAPI(
        title="Vitiligo Initiative — Evidence Engine",
        version=__version__,
        description="Open, AI-native research engine for stopping vitiligo spread and driving repigmentation.",
        lifespan=_lifespan,
    )

    if settings.rate_limit_post_per_minute > 0:
        app.add_middleware(
            RateLimitMiddleware,
            post_limit_per_minute=settings.rate_limit_post_per_minute,
            trusted_proxy_hops=settings.trusted_proxy_hops,
        )

    if settings.trusted_proxy_hops > 0:
        app.add_middleware(
            ForwardedProtoMiddleware,
            trusted_proxy_hops=settings.trusted_proxy_hops,
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        stats = get_corpus_stats()
        ready = stats["database"]["exists"] and stats["documents"] > 0
        return {
            "status": "ok" if ready else "degraded",
            "version": __version__,
            "ready": ready,
            "llm_configured": settings.anthropic_api_key is not None,
            "corpus": stats,
        }

    @app.get("/api/stats")
    def stats() -> dict[str, Any]:
        corpus = get_corpus_stats()
        trial_summary = summarize_trials()
        return {
            "corpus": corpus,
            "trials": {
                "total": trial_summary["total"][0].count if trial_summary["total"] else 0,
                "by_source": [
                    {"label": r.label, "count": r.count} for r in trial_summary.get("by_source", [])
                ],
            },
        }

    @app.post("/api/search")
    def search(req: SearchRequest) -> dict[str, Any]:
        """Semantic search. Each result ``score`` is cosine similarity minus a small
        evidence-level penalty (mouse -0.08, in-vitro -0.05), not raw embedding similarity."""
        hits = semantic_search(query=req.query, top_k=req.top_k)
        results = []
        for rank, hit in enumerate(hits, start=1):
            level = classify_document(hit.document)
            results.append(
                {
                    "rank": rank,
                    "score": hit.score,
                    "source": hit.document.source.value,
                    "source_id": hit.document.source_id,
                    "title": hit.document.title,
                    "journal": hit.document.journal,
                    "year": hit.document.year,
                    "doi": hit.document.doi,
                    "abstract": hit.document.abstract,
                    "mesh_terms": hit.document.mesh_terms,
                    "evidence_level": level.value,
                    "evidence_level_label": evidence_level_label(level),
                }
            )
        return {"query": req.query, "results": results}

    llm_budget = LLMBudget(
        settings.resolved_state_db_path,
        requests_per_minute=settings.llm_requests_per_minute,
        daily_token_budget=settings.llm_daily_token_budget,
    )

    def _reserve_llm(endpoint: str) -> int | None:
        try:
            return llm_budget.reserve(endpoint)
        except LLMBudgetExceeded as exc:
            raise HTTPException(
                status_code=429,
                detail=str(exc),
                headers={"Retry-After": str(exc.retry_after_s)},
            ) from exc

    @app.post("/api/ask")
    def ask(req: AskRequest) -> dict[str, Any]:
        call_id = _reserve_llm("ask")
        try:
            answer = ask_with_citations(question=req.question, top_k=req.top_k)
        except (LLMUnavailable, CorpusUnavailable) as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        llm_budget.record(call_id, answer.input_tokens, answer.output_tokens)
        return {
            "question": answer.question,
            "answer": answer.answer,
            "model": answer.model,
            "citations": [asdict(c) for c in answer.citations],
        }

    @app.post("/api/hypothesize")
    def hypothesize(req: HypothesizeRequest) -> dict[str, Any]:
        call_id = _reserve_llm("hypothesize")
        try:
            report = generate_hypotheses(intent=req.intent, top_k=req.top_k)
        except (LLMUnavailable, CorpusUnavailable) as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        llm_budget.record(call_id, report.input_tokens, report.output_tokens)
        return hypothesize_report_to_dict(report)

    @app.get("/api/report/candidates")
    async def report_candidates(top_n: int = 10) -> dict[str, Any]:
        """Deterministic evidence-scored candidate rankings (no LLM)."""
        if top_n < 1 or top_n > 20:
            raise HTTPException(status_code=400, detail="top_n must be between 1 and 20.")
        return await asyncio.to_thread(_cached_candidate_report, top_n)

    @app.post("/api/trials/search")
    def trials_search(req: TrialsSearchRequest) -> dict[str, Any]:
        if req.source:
            try:
                sources = (TrialSourceKind(req.source.lower()),)
            except ValueError as exc:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown source '{req.source}'. Allowed: ctgov, euctr, ictrp.",
                ) from exc
        else:
            sources = tuple(TrialSourceKind)  # type: ignore[assignment]

        filt = TrialFilter(
            query=req.query,
            status=req.status,
            phase=req.phase,
            country=req.country,
            sources=sources,
            has_results=req.has_results,
            limit=req.limit,
            offset=req.offset,
        )
        trials = list_trials(filt)
        total = count_trials(filt)
        return {
            "total": total,
            "limit": req.limit,
            "offset": req.offset,
            "results": [_trial_to_dict(t) for t in trials],
        }

    @app.get("/api/trials/stats")
    def trials_stats() -> dict[str, Any]:
        summary = summarize_trials()
        return {
            "total": summary["total"][0].count if summary["total"] else 0,
            "by_source": [
                {"label": r.label, "count": r.count} for r in summary.get("by_source", [])
            ],
            "by_status": [{"label": r.label, "count": r.count} for r in summary["by_status"]],
            "by_results": [{"label": r.label, "count": r.count} for r in summary["by_results"]],
        }

    @app.get("/api/graph/stats")
    def graph_stats() -> dict[str, Any]:
        summary = summarize_graph()
        return {
            "total": [{"label": r.label, "count": r.count} for r in summary["total"]],
            "by_kind": [{"label": r.label, "count": r.count} for r in summary["by_kind"]],
            "by_predicate": [{"label": r.label, "count": r.count} for r in summary["by_predicate"]],
            "by_method": [{"label": r.label, "count": r.count} for r in summary["by_method"]],
        }

    @app.get("/api/graph/search")
    def graph_search(q: str, limit: int = 25) -> dict[str, Any]:
        if not q.strip():
            raise HTTPException(status_code=400, detail="Query parameter q is required.")
        entities = search_entities(q.strip(), limit=min(limit, 100))
        return {
            "query": q,
            "results": [
                {
                    "kind": e.kind.value if hasattr(e.kind, "value") else str(e.kind),
                    "key": e.key,
                    "name": e.name,
                    "aliases": e.aliases,
                    "external_ids": e.external_ids,
                }
                for e in entities
            ],
        }

    @app.get("/api/graph/neighbors")
    def graph_neighbors(
        name: str,
        hops: int = 1,
        limit: int = 50,
    ) -> dict[str, Any]:
        if not name.strip():
            raise HTTPException(status_code=400, detail="Query parameter name is required.")
        edges = get_neighbors(name.strip(), hops=hops, limit=min(limit, 200))
        return {
            "name": name,
            "hops": hops,
            "results": [
                {
                    "subject_kind": e.subject_kind,
                    "subject_name": e.subject_name,
                    "predicate": e.predicate,
                    "object_kind": e.object_kind,
                    "object_name": e.object_name,
                    "confidence": e.confidence,
                    "extraction_method": e.extraction_method,
                    "evidence_count": e.evidence_count,
                }
                for e in edges
            ],
        }

    @app.get("/api/graph/export")
    def graph_export(edge_limit: int | None = None) -> dict[str, Any]:
        if edge_limit is not None and edge_limit < 1:
            raise HTTPException(status_code=400, detail="edge_limit must be >= 1.")
        return export_graph_snapshot(
            edge_limit=min(edge_limit, 10_000) if edge_limit is not None else None
        )

    app.mount(
        "/static",
        StaticFiles(directory=str(STATIC_DIR)),
        name="static",
    )

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/privacy")
    def privacy() -> FileResponse:
        return FileResponse(STATIC_DIR / "privacy.html")

    @app.get("/terms")
    def terms() -> FileResponse:
        return FileResponse(STATIC_DIR / "terms.html")

    return app


app = create_app()
