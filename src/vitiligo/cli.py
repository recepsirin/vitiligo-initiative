"""Command-line interface for the Vitiligo Initiative engine.

Run `vitiligo --help` for available commands.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table
from sqlmodel import func, select

from vitiligo import __version__
from vitiligo.config import get_settings
from vitiligo.embed import DEFAULT_MODEL, embed_documents, semantic_search
from vitiligo.ingest import run_ctgov_ingestion, run_pmc_ingestion, run_pubmed_ingestion
from vitiligo.logging import configure_logging, get_logger
from vitiligo.reasoning import (
    LLMUnavailable,
    ask_with_citations,
    generate_hypotheses,
)
from vitiligo.sources.ctgov import DEFAULT_VITILIGO_QUERY as CTGOV_DEFAULT_QUERY
from vitiligo.sources.pmc import DEFAULT_VITILIGO_QUERY as PMC_DEFAULT_QUERY
from vitiligo.sources.pubmed import DEFAULT_VITILIGO_QUERY as PUBMED_DEFAULT_QUERY
from vitiligo.storage import (
    Document,
    Embedding,
    IngestionRun,
    SourceKind,
    Trial,
    init_db,
    session_scope,
)
from vitiligo.trials import TrialFilter, list_trials, summarize_trials

app = typer.Typer(
    add_completion=False,
    help="Vitiligo Initiative engine — ingestion, search, and reasoning.",
    no_args_is_help=True,
)
ingest_app = typer.Typer(help="Ingest documents and trials from external sources.", no_args_is_help=True)
db_app = typer.Typer(help="Inspect the local document store.", no_args_is_help=True)
embed_app = typer.Typer(help="Generate and inspect embeddings.", no_args_is_help=True)
trials_app = typer.Typer(help="Browse the local clinical-trials store.", no_args_is_help=True)
app.add_typer(ingest_app, name="ingest")
app.add_typer(db_app, name="db")
app.add_typer(embed_app, name="embed")
app.add_typer(trials_app, name="trials")

console = Console()
logger = get_logger(__name__)


@app.callback()
def _root(
    log_level: str = typer.Option(
        None,
        "--log-level",
        envvar="LOG_LEVEL",
        help="Override log level (DEBUG | INFO | WARNING | ERROR).",
    ),
) -> None:
    configure_logging(log_level)


@app.command("version")
def version_cmd() -> None:
    """Print the installed version."""
    console.print(f"vitiligo {__version__}")


# --------------------------------------------------------------------- ingest


def _print_ingest_stats(stats_obj: object) -> None:
    table = Table(show_header=False, box=None)
    src = stats_obj.source  # type: ignore[attr-defined]
    table.add_row("Source", src.value if hasattr(src, "value") else str(src))
    table.add_row("Total found", str(stats_obj.total_found))  # type: ignore[attr-defined]
    table.add_row("Fetched", str(stats_obj.fetched))  # type: ignore[attr-defined]
    table.add_row("Inserted", str(stats_obj.inserted))  # type: ignore[attr-defined]
    table.add_row("Updated", str(stats_obj.updated))  # type: ignore[attr-defined]
    table.add_row("Run id", str(stats_obj.run_id))  # type: ignore[attr-defined]
    console.print(table)


@ingest_app.command("pubmed")
def ingest_pubmed(
    query: str = typer.Option(
        PUBMED_DEFAULT_QUERY,
        "--query",
        "-q",
        help="PubMed search expression.",
    ),
    batch_size: int = typer.Option(200, "--batch-size", "-b", help="Records per efetch call."),
    limit: int | None = typer.Option(
        None,
        "--limit",
        "-l",
        help="Cap total records (smoke testing).",
    ),
) -> None:
    """Search PubMed and persist all matching records into the local store."""
    settings = get_settings()
    console.rule("[bold]PubMed ingestion[/bold]")
    console.print(f"Database: [cyan]{settings.resolved_db_path}[/cyan]")
    console.print(f"Query:    [yellow]{query}[/yellow]")
    if limit:
        console.print(f"Limit:    [magenta]{limit}[/magenta] (smoke test)")
    console.print()

    stats = run_pubmed_ingestion(query=query, batch_size=batch_size, limit=limit)

    console.print()
    console.rule("[bold green]Done[/bold green]")
    _print_ingest_stats(stats)


@ingest_app.command("pmc")
def ingest_pmc(
    query: str = typer.Option(
        PMC_DEFAULT_QUERY,
        "--query",
        "-q",
        help="PMC search expression (Open Access subset by default).",
    ),
    batch_size: int = typer.Option(50, "--batch-size", "-b", help="Records per efetch call."),
    limit: int | None = typer.Option(None, "--limit", "-l", help="Cap total records."),
) -> None:
    """Search PMC Open Access and persist full-text records into the local store."""
    settings = get_settings()
    console.rule("[bold]PMC OA ingestion[/bold]")
    console.print(f"Database: [cyan]{settings.resolved_db_path}[/cyan]")
    console.print(f"Query:    [yellow]{query}[/yellow]")
    if limit:
        console.print(f"Limit:    [magenta]{limit}[/magenta] (smoke test)")
    console.print()

    stats = run_pmc_ingestion(query=query, batch_size=batch_size, limit=limit)

    console.print()
    console.rule("[bold green]Done[/bold green]")
    _print_ingest_stats(stats)


@ingest_app.command("ctgov")
def ingest_ctgov(
    query: str = typer.Option(
        CTGOV_DEFAULT_QUERY,
        "--query",
        "-q",
        help="ClinicalTrials.gov condition query.",
    ),
    page_size: int = typer.Option(
        100, "--page-size", "-p", help="Studies per request (max 1000)."
    ),
    limit: int | None = typer.Option(
        None, "--limit", "-l", help="Cap total trials (smoke testing)."
    ),
) -> None:
    """Fetch vitiligo trials from ClinicalTrials.gov v2 and persist them."""
    settings = get_settings()
    console.rule("[bold]ClinicalTrials.gov ingestion[/bold]")
    console.print(f"Database: [cyan]{settings.resolved_db_path}[/cyan]")
    console.print(f"Query:    [yellow]{query}[/yellow]")
    if limit:
        console.print(f"Limit:    [magenta]{limit}[/magenta] (smoke test)")
    console.print()

    stats = run_ctgov_ingestion(query=query, page_size=page_size, limit=limit)

    console.print()
    console.rule("[bold green]Done[/bold green]")
    _print_ingest_stats(stats)


# --------------------------------------------------------------------- db


@db_app.command("init")
def db_init() -> None:
    """Create the database schema if it does not exist."""
    init_db()
    settings = get_settings()
    console.print(f"Initialized schema at [cyan]{settings.resolved_db_path}[/cyan]")


@db_app.command("stats")
def db_stats() -> None:
    """Print a summary of stored documents and ingestion runs."""
    init_db()
    with session_scope() as session:
        total_docs = session.exec(select(func.count()).select_from(Document)).one()
        by_source = session.exec(
            select(Document.source, func.count()).group_by(Document.source)
        ).all()
        latest_runs = session.exec(
            select(IngestionRun).order_by(IngestionRun.started_at.desc()).limit(5)
        ).all()

    console.rule("[bold]Document store[/bold]")
    console.print(f"Total documents: [cyan]{total_docs}[/cyan]")

    if by_source:
        sources_table = Table(title="By source", show_header=True, header_style="bold")
        sources_table.add_column("Source")
        sources_table.add_column("Count", justify="right")
        for source, count in by_source:
            label = source.value if isinstance(source, SourceKind) else str(source)
            sources_table.add_row(label, str(count))
        console.print(sources_table)

    if latest_runs:
        runs_table = Table(title="Recent ingestion runs", show_header=True, header_style="bold")
        runs_table.add_column("ID", justify="right")
        runs_table.add_column("Source")
        runs_table.add_column("Status")
        runs_table.add_column("Found", justify="right")
        runs_table.add_column("Inserted", justify="right")
        runs_table.add_column("Updated", justify="right")
        runs_table.add_column("Started")
        for run in latest_runs:
            src = run.source
            runs_table.add_row(
                str(run.id),
                src.value if hasattr(src, "value") else str(src),
                run.status,
                str(run.total_found or "-"),
                str(run.inserted),
                str(run.updated),
                run.started_at.strftime("%Y-%m-%d %H:%M:%S"),
            )
        console.print(runs_table)


@db_app.command("sample")
def db_sample(
    n: int = typer.Option(3, "--n", "-n", help="How many sample documents to show."),
) -> None:
    """Print a few documents as a sanity check."""
    init_db()
    with session_scope() as session:
        docs = session.exec(select(Document).limit(n)).all()

    if not docs:
        console.print("[yellow]No documents in the store yet.[/yellow]")
        return

    for doc in docs:
        console.rule(f"[bold]{doc.source.value}:{doc.source_id}[/bold]")
        console.print(f"[bold]Title:[/bold] {doc.title}")
        console.print(f"[bold]Journal:[/bold] {doc.journal}  [bold]Year:[/bold] {doc.year}")
        console.print(f"[bold]DOI:[/bold] {doc.doi}")
        if doc.mesh_terms:
            console.print(f"[bold]MeSH:[/bold] {', '.join(doc.mesh_terms[:8])}")
        if doc.abstract:
            preview = doc.abstract[:400] + ("..." if len(doc.abstract) > 400 else "")
            console.print(f"[bold]Abstract:[/bold] {preview}")
        console.print()


# --------------------------------------------------------------------- embed


@embed_app.command("run")
def embed_run(
    model: str = typer.Option(DEFAULT_MODEL, "--model", "-m", help="Embedding model identifier."),
    scope: str = typer.Option("title_abstract", "--scope", "-s", help="Embedding scope name."),
    batch_size: int = typer.Option(64, "--batch-size", "-b", help="Encode batch size."),
    limit: int | None = typer.Option(None, "--limit", "-l", help="Cap documents to embed."),
) -> None:
    """Encode documents that don't yet have an embedding for (model, scope)."""
    console.rule(
        f"[bold]Embedding[/bold] — model=[cyan]{model}[/cyan] scope=[yellow]{scope}[/yellow]"
    )
    stats = embed_documents(model_name=model, scope=scope, batch_size=batch_size, limit=limit)
    console.print()
    console.rule("[bold green]Done[/bold green]")
    table = Table(show_header=False, box=None)
    table.add_row("Model", stats.model)
    table.add_row("Scope", stats.scope)
    table.add_row("Embedded", str(stats.embedded))
    table.add_row("Skipped (no text)", str(stats.skipped_no_text))
    console.print(table)


@embed_app.command("stats")
def embed_stats() -> None:
    """Show embedding coverage by model and scope."""
    init_db()
    with session_scope() as session:
        rows = session.exec(
            select(Embedding.model, Embedding.scope, func.count())
            .group_by(Embedding.model, Embedding.scope)
            .order_by(Embedding.model, Embedding.scope)
        ).all()

    if not rows:
        console.print("[yellow]No embeddings stored yet. Run `vitiligo embed run`.[/yellow]")
        return

    table = Table(title="Embeddings", show_header=True, header_style="bold")
    table.add_column("Model")
    table.add_column("Scope")
    table.add_column("Count", justify="right")
    for model, scope, count in rows:
        table.add_row(str(model), str(scope), str(count))
    console.print(table)


# --------------------------------------------------------------------- search


@app.command("search")
def search_cmd(
    query: str = typer.Argument(..., help="Free-text search query."),
    top_k: int = typer.Option(10, "--top-k", "-k", help="How many hits to return."),
    model: str = typer.Option(DEFAULT_MODEL, "--model", "-m", help="Embedding model identifier."),
    scope: str = typer.Option("title_abstract", "--scope", "-s", help="Embedding scope to search."),
    show_abstract: bool = typer.Option(
        False,
        "--show-abstract/--no-abstract",
        help="Include a short abstract excerpt in the output.",
    ),
) -> None:
    """Semantic search over the embedded corpus."""
    console.rule(f"[bold]Search[/bold] — [yellow]{query}[/yellow]")
    hits = semantic_search(query=query, top_k=top_k, model_name=model, scope=scope)
    if not hits:
        console.print("[yellow]No results.[/yellow]")
        return

    for rank, hit in enumerate(hits, start=1):
        doc = hit.document
        header = f"#{rank}  score={hit.score:.3f}  [cyan]{doc.source.value}:{doc.source_id}[/cyan]"
        console.rule(header, align="left")
        console.print(f"[bold]{doc.title}[/bold]")
        meta_bits: list[str] = []
        if doc.journal:
            meta_bits.append(doc.journal)
        if doc.year:
            meta_bits.append(str(doc.year))
        if doc.doi:
            meta_bits.append(f"doi:{doc.doi}")
        if meta_bits:
            console.print("  ".join(meta_bits))
        if show_abstract and doc.abstract:
            preview = doc.abstract[:400] + ("..." if len(doc.abstract) > 400 else "")
            console.print(preview)
        console.print()


# --------------------------------------------------------------------- reasoning


@app.command("ask")
def ask_cmd(
    question: str = typer.Argument(..., help="Research question."),
    top_k: int = typer.Option(8, "--top-k", "-k", help="Sources to retrieve."),
) -> None:
    """Ask the corpus a question and print a cited answer (requires Anthropic API key)."""
    console.rule(f"[bold]Ask[/bold] — [yellow]{question}[/yellow]")
    try:
        result = ask_with_citations(question=question, top_k=top_k)
    except LLMUnavailable as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc

    console.print(result.answer)
    console.print()
    console.rule("[bold]Sources[/bold]")
    for c in result.citations:
        bits = [c.title or "(no title)"]
        meta = " ".join(
            filter(None, [c.journal or "", str(c.year or ""), f"doi:{c.doi}" if c.doi else ""])
        ).strip()
        if meta:
            bits.append(meta)
        console.print(f"[cyan][{c.index}][/cyan] " + " — ".join(bits))


@app.command("hypothesize")
def hypothesize_cmd(
    intent: str = typer.Argument(..., help="Research intent (e.g. 'stop spread')."),
    top_k: int = typer.Option(25, "--top-k", "-k", help="Papers to retrieve."),
) -> None:
    """Generate ranked therapeutic candidates from the corpus (requires Anthropic API key)."""
    console.rule(f"[bold]Hypothesize[/bold] — [yellow]{intent}[/yellow]")
    try:
        report = generate_hypotheses(intent=intent, top_k=top_k)
    except LLMUnavailable as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc

    if report.notes:
        console.print(f"[dim]{report.notes}[/dim]")
        console.print()

    for idx, cand in enumerate(report.candidates, start=1):
        console.rule(
            f"[bold]#{idx}  {cand.name}[/bold]  [dim]{cand.kind}[/dim]  "
            f"[magenta]{cand.evidence_strength}[/magenta]",
            align="left",
        )
        if cand.mechanism:
            console.print(f"[bold]Mechanism:[/bold] {cand.mechanism}")
        if cand.rationale:
            console.print(f"[bold]Rationale:[/bold] {cand.rationale}")
        if cand.risks_or_caveats:
            console.print(f"[bold]Risks/caveats:[/bold] {cand.risks_or_caveats}")
        if cand.citation_indices:
            console.print(f"[bold]Citations:[/bold] {cand.citation_indices}")
        console.print()


# --------------------------------------------------------------------- trials


@trials_app.command("stats")
def trials_stats() -> None:
    """High-level statistics over the trials table."""
    init_db()
    summary = summarize_trials()
    console.rule("[bold]Trials store[/bold]")
    total = summary["total"][0].count if summary["total"] else 0
    console.print(f"Total trials: [cyan]{total}[/cyan]")

    if total == 0:
        console.print(
            "[yellow]No trials yet. Run `vitiligo ingest ctgov` to populate.[/yellow]"
        )
        return

    if summary["by_status"]:
        status_table = Table(title="By status", show_header=True, header_style="bold")
        status_table.add_column("Status")
        status_table.add_column("Count", justify="right")
        for row in summary["by_status"]:
            status_table.add_row(row.label, str(row.count))
        console.print(status_table)

    if summary["by_results"]:
        results_table = Table(
            title="Reported results", show_header=True, header_style="bold"
        )
        results_table.add_column("Has results")
        results_table.add_column("Count", justify="right")
        for row in summary["by_results"]:
            results_table.add_row(row.label, str(row.count))
        console.print(results_table)


@trials_app.command("sample")
def trials_sample(
    n: int = typer.Option(3, "--n", "-n", help="How many sample trials to show."),
) -> None:
    """Print a few trials as a sanity check."""
    init_db()
    with session_scope() as session:
        rows = session.exec(select(Trial).limit(n)).all()

    if not rows:
        console.print("[yellow]No trials in the store yet.[/yellow]")
        return

    for trial in rows:
        src = trial.source
        src_label = src.value if hasattr(src, "value") else str(src)
        console.rule(f"[bold]{src_label}:{trial.source_id}[/bold]")
        console.print(f"[bold]Title:[/bold] {trial.brief_title or trial.official_title}")
        console.print(
            f"[bold]Status:[/bold] {trial.status}   [bold]Phases:[/bold] {', '.join(trial.phases) or '-'}"
        )
        if trial.conditions:
            console.print(f"[bold]Conditions:[/bold] {', '.join(trial.conditions[:6])}")
        if trial.interventions:
            ivs = [
                f"{iv.get('type','?')}: {iv.get('name','?')}" for iv in trial.interventions[:5]
            ]
            console.print(f"[bold]Interventions:[/bold] {' | '.join(ivs)}")
        if trial.countries:
            console.print(f"[bold]Countries:[/bold] {', '.join(trial.countries[:8])}")
        if trial.summary:
            preview = trial.summary[:400] + ("..." if len(trial.summary) > 400 else "")
            console.print(f"[bold]Summary:[/bold] {preview}")
        console.print()


@trials_app.command("search")
def trials_search(
    query: str = typer.Argument(None, help="Optional free-text term."),
    status: str | None = typer.Option(None, "--status", help="Filter by overall status."),
    phase: str | None = typer.Option(None, "--phase", help="Filter by trial phase."),
    country: str | None = typer.Option(None, "--country", help="Filter by location country."),
    has_results: bool | None = typer.Option(
        None, "--has-results/--no-has-results", help="Only trials with reported results."
    ),
    limit: int = typer.Option(20, "--limit", "-l", help="Max trials to display."),
) -> None:
    """Structured search over the trials table."""
    init_db()
    filt = TrialFilter(
        query=query,
        status=status,
        phase=phase,
        country=country,
        has_results=has_results,
        limit=limit,
    )
    rows = list_trials(filt)
    if not rows:
        console.print("[yellow]No trials match.[/yellow]")
        return

    for trial in rows:
        src = trial.source
        src_label = src.value if hasattr(src, "value") else str(src)
        console.rule(
            f"[cyan]{src_label}:{trial.source_id}[/cyan]  "
            f"[magenta]{trial.status or 'UNKNOWN'}[/magenta]  "
            f"[dim]{', '.join(trial.phases) or 'phase=-'}[/dim]",
            align="left",
        )
        console.print(f"[bold]{trial.brief_title or trial.official_title}[/bold]")
        if trial.conditions:
            console.print(f"Conditions: {', '.join(trial.conditions[:6])}")
        if trial.interventions:
            ivs = [
                f"{iv.get('type','?')}: {iv.get('name','?')}" for iv in trial.interventions[:4]
            ]
            console.print(f"Interventions: {' | '.join(ivs)}")
        if trial.countries:
            console.print(f"Countries: {', '.join(trial.countries[:6])}")
        console.print()


# --------------------------------------------------------------------- web


@app.command("serve")
def serve_cmd(
    host: str = typer.Option(None, "--host", help="Override bind host."),
    port: int = typer.Option(None, "--port", help="Override bind port."),
    reload: bool = typer.Option(False, "--reload", help="Auto-reload on code changes (dev only)."),
) -> None:
    """Run the Evidence Engine web UI."""
    settings = get_settings()
    bind_host = host or settings.web_host
    bind_port = port or settings.web_port

    import uvicorn

    console.rule("[bold]Vitiligo Initiative — Evidence Engine[/bold]")
    console.print(f"Serving on [cyan]http://{bind_host}:{bind_port}[/cyan]")
    if not settings.anthropic_api_key:
        console.print(
            "[yellow]Note: ANTHROPIC_API_KEY is not set — Search works, but Ask and Hypothesize will return 503.[/yellow]"
        )

    uvicorn.run(
        "vitiligo.web.app:app",
        host=bind_host,
        port=bind_port,
        reload=reload,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    app()
