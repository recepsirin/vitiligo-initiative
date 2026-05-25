"""FastAPI application exposing search, ask, and hypothesize endpoints.

This is intentionally small: three JSON endpoints + one static HTML page.
The HTML page (`static/index.html`) is the Evidence Engine UI; it talks
to the JSON endpoints via fetch.

CORS is open by default — this is a research tool meant to run locally
or behind a reverse proxy you control. Don't expose it directly to the
public internet without auth + rate limiting.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from vitiligo import __version__
from vitiligo.embed import semantic_search
from vitiligo.reasoning import (
    LLMUnavailable,
    ask_with_citations,
    generate_hypotheses,
)
from vitiligo.reasoning.hypothesize import report_to_dict
from vitiligo.storage import init_db

STATIC_DIR = Path(__file__).resolve().parent / "static"


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Free-text search query.")
    top_k: int = Field(10, ge=1, le=50)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1)
    top_k: int = Field(8, ge=1, le=25)


class HypothesizeRequest(BaseModel):
    intent: str = Field(..., min_length=1, description="Research intent, e.g. 'stop spread'.")
    top_k: int = Field(25, ge=5, le=50)


def create_app() -> FastAPI:
    init_db()

    app = FastAPI(
        title="Vitiligo Initiative — Evidence Engine",
        version=__version__,
        description="Open, AI-native research engine for stopping vitiligo spread and driving repigmentation.",
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
        return {"status": "ok", "version": __version__}

    @app.post("/api/search")
    def search(req: SearchRequest) -> dict[str, Any]:
        hits = semantic_search(query=req.query, top_k=req.top_k)
        return {
            "query": req.query,
            "results": [
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
                }
                for rank, hit in enumerate(hits, start=1)
            ],
        }

    @app.post("/api/ask")
    def ask(req: AskRequest) -> dict[str, Any]:
        try:
            answer = ask_with_citations(question=req.question, top_k=req.top_k)
        except LLMUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return {
            "question": answer.question,
            "answer": answer.answer,
            "model": answer.model,
            "citations": [asdict(c) for c in answer.citations],
        }

    @app.post("/api/hypothesize")
    def hypothesize(req: HypothesizeRequest) -> dict[str, Any]:
        try:
            report = generate_hypotheses(intent=req.intent, top_k=req.top_k)
        except LLMUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return report_to_dict(report)

    app.mount(
        "/static",
        StaticFiles(directory=str(STATIC_DIR)),
        name="static",
    )

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    return app


app = create_app()
