"""Command-line interface for the Vitiligo Initiative engine.

Run `vitiligo --help` for available commands.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import httpx
import typer
from rich.console import Console
from rich.table import Table
from sqlmodel import func, select

from vitiligo import __version__
from vitiligo.config import get_settings
from vitiligo.embed import DEFAULT_MODEL, embed_documents, semantic_search
from vitiligo.evidence import classify_document, evidence_level_label
from vitiligo.graph import (
    export_graph_snapshot,
    get_neighbors,
    run_graph_build,
    search_entities,
    summarize_graph,
)
from vitiligo.graph.build import GraphBuildStats
from vitiligo.graph.extract import extract_graph_from_documents
from vitiligo.graph.seed import seed_graph_from_structured_sources
from vitiligo.ingest import (
    run_ctgov_ingestion,
    run_drugbank_ingestion,
    run_euctr_ingestion,
    run_geo_ingestion,
    run_ictrp_ingestion,
    run_opentargets_ingestion,
    run_pmc_ingestion,
    run_pubmed_ingestion,
)
from vitiligo.ingest.repair import repair_corpus
from vitiligo.logging import configure_logging, get_logger
from vitiligo.priors import list_drug_priors, list_target_priors, summarize_priors
from vitiligo.reasoning import (
    CorpusUnavailable,
    LLMUnavailable,
    ask_with_citations,
    generate_hypotheses,
)
from vitiligo.reports import (
    atlas_to_dict,
    build_candidate_report,
    build_jak_atlas,
    render_candidate_report_markdown,
    render_jak_atlas_markdown,
    report_to_dict,
    write_jak_atlas_csv,
)
from vitiligo.reports.jak_arms import (
    ArmEndpointRow,
    harmonize_arms,
    summarize_arms,
    write_arms_csv,
)
from vitiligo.sources.ctgov import DEFAULT_VITILIGO_QUERY as CTGOV_DEFAULT_QUERY
from vitiligo.sources.drugbank import DEFAULT_VITILIGO_QUERY as DRUGBANK_DEFAULT_QUERY
from vitiligo.sources.euctr import DEFAULT_VITILIGO_QUERY as EUCTR_DEFAULT_QUERY
from vitiligo.sources.geo import DEFAULT_VITILIGO_QUERY as GEO_DEFAULT_QUERY
from vitiligo.sources.opentargets import DEFAULT_DISEASE_QUERY as OPENTARGETS_DEFAULT_QUERY
from vitiligo.sources.opentargets import DEFAULT_TARGET_LIMIT
from vitiligo.sources.pmc import DEFAULT_VITILIGO_QUERY as PMC_DEFAULT_QUERY
from vitiligo.sources.pubmed import DEFAULT_VITILIGO_QUERY as PUBMED_DEFAULT_QUERY
from vitiligo.storage import (
    Document,
    Embedding,
    IngestionRun,
    SourceKind,
    Trial,
    TrialSourceKind,
    init_db,
    session_scope,
)
from vitiligo.trials import TrialFilter, list_trials, summarize_trials

app = typer.Typer(
    add_completion=False,
    help="Vitiligo Initiative engine — ingestion, search, and reasoning.",
    no_args_is_help=True,
)
ingest_app = typer.Typer(
    help="Ingest documents and trials from external sources.", no_args_is_help=True
)
db_app = typer.Typer(help="Inspect the local document store.", no_args_is_help=True)
embed_app = typer.Typer(help="Generate and inspect embeddings.", no_args_is_help=True)
trials_app = typer.Typer(help="Browse the local clinical-trials store.", no_args_is_help=True)
priors_app = typer.Typer(help="Browse drug/target priors from Open Targets.", no_args_is_help=True)
graph_app = typer.Typer(help="Build and query the vitiligo knowledge graph.", no_args_is_help=True)
report_app = typer.Typer(help="Generate reproducible research reports.", no_args_is_help=True)
model_app = typer.Typer(
    help="Scenario models over the JAK arm table (needs: pip install -e '.[model]').",
    no_args_is_help=True,
)
app.add_typer(ingest_app, name="ingest")
app.add_typer(db_app, name="db")
app.add_typer(embed_app, name="embed")
app.add_typer(trials_app, name="trials")
app.add_typer(priors_app, name="priors")
app.add_typer(graph_app, name="graph")
app.add_typer(report_app, name="report")
app.add_typer(model_app, name="model")
discover_app = typer.Typer(
    help="Discovery loop: propose hypotheses, test on held-out evidence, keep a ledger.",
    no_args_is_help=True,
)
app.add_typer(discover_app, name="discover")
papers_app = typer.Typer(
    help="Results tables from open-access papers (curated, cell-verified).", no_args_is_help=True
)
app.add_typer(papers_app, name="papers")
geo_data_app = typer.Typer(
    help="GEO supplementary data files: the matrices themselves, not the metadata.",
    no_args_is_help=True,
)
app.add_typer(geo_data_app, name="geo-data")
mechanism_app = typer.Typer(
    help="Mechanistic hypotheses: claim, evidence, competing explanation, and the test.",
    no_args_is_help=True,
)
app.add_typer(mechanism_app, name="mechanism")
PAPER_CURATION = Path("curation/paper-results.json")
MECHANISM_CURATION = Path("curation/mechanisms.json")

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
    skipped = getattr(stats_obj, "skipped", 0)
    if skipped:
        table.add_row("Skipped", str(skipped))
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


@ingest_app.command("geo")
def ingest_geo(
    query: str = typer.Option(
        GEO_DEFAULT_QUERY,
        "--query",
        "-q",
        help="GEO DataSets search expression.",
    ),
    batch_size: int = typer.Option(100, "--batch-size", "-b", help="UIDs per esearch page."),
    limit: int | None = typer.Option(None, "--limit", "-l", help="Cap total records."),
) -> None:
    """Search NCBI GEO and persist series metadata (GSE) into the local store."""
    settings = get_settings()
    console.rule("[bold]GEO ingestion[/bold]")
    console.print(f"Database: [cyan]{settings.resolved_db_path}[/cyan]")
    console.print(f"Query:    [yellow]{query}[/yellow]")
    if limit:
        console.print(f"Limit:    [magenta]{limit}[/magenta] (smoke test)")
    console.print()

    stats = run_geo_ingestion(query=query, batch_size=batch_size, limit=limit)

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
    page_size: int = typer.Option(100, "--page-size", "-p", help="Studies per request (max 1000)."),
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


@ingest_app.command("euctr")
def ingest_euctr(
    query: str = typer.Option(
        EUCTR_DEFAULT_QUERY,
        "--query",
        "-q",
        help="EU CTR / CTIS medical-condition query.",
    ),
    page_size: int = typer.Option(50, "--page-size", "-p", help="Records per page."),
    limit: int | None = typer.Option(
        None, "--limit", "-l", help="Cap total trials (smoke testing)."
    ),
    skip_details: bool = typer.Option(
        False,
        "--skip-details/--with-details",
        help="Skip the per-trial /retrieve detail call (faster but loses eligibility + objective).",
    ),
) -> None:
    """Fetch vitiligo trials from the EU CTR (CTIS) public API and persist them."""
    settings = get_settings()
    console.rule("[bold]EU CTR (CTIS) ingestion[/bold]")
    console.print(f"Database: [cyan]{settings.resolved_db_path}[/cyan]")
    console.print(f"Query:    [yellow]{query}[/yellow]")
    if limit:
        console.print(f"Limit:    [magenta]{limit}[/magenta] (smoke test)")
    console.print()

    stats = run_euctr_ingestion(
        query=query,
        page_size=page_size,
        limit=limit,
        with_details=not skip_details,
    )

    console.print()
    console.rule("[bold green]Done[/bold green]")
    _print_ingest_stats(stats)


@ingest_app.command("opentargets")
def ingest_opentargets(
    query: str = typer.Option(
        OPENTARGETS_DEFAULT_QUERY,
        "--query",
        "-q",
        help="Disease query for Open Targets resolution.",
    ),
    efo_id: str | None = typer.Option(
        None,
        "--efo-id",
        help="Skip resolution and use this EFO id directly (e.g. EFO_0004208).",
    ),
    target_limit: int = typer.Option(
        DEFAULT_TARGET_LIMIT,
        "--target-limit",
        help="Max associated targets to persist (drugs are fetched in full).",
    ),
) -> None:
    """Fetch vitiligo drug and target priors from Open Targets."""
    settings = get_settings()
    console.rule("[bold]Open Targets ingestion[/bold]")
    console.print(f"Database: [cyan]{settings.resolved_db_path}[/cyan]")
    console.print(f"Query:    [yellow]{query}[/yellow]")
    if efo_id:
        console.print(f"EFO id:   [magenta]{efo_id}[/magenta]")
    console.print()

    stats = run_opentargets_ingestion(query=query, efo_id=efo_id, target_limit=target_limit)

    console.print()
    console.rule("[bold green]Done[/bold green]")
    _print_ingest_stats(stats)


@ingest_app.command("ictrp")
def ingest_ictrp(
    file: str = typer.Argument(..., help="Path to an ICTRP XML export file."),
    limit: int | None = typer.Option(
        None,
        "--limit",
        "-l",
        help="Cap total records (smoke testing).",
    ),
    keep_duplicates: bool = typer.Option(
        False,
        "--keep-duplicates/--skip-duplicates",
        help="Keep trials that duplicate ctgov/euctr records (default: skip).",
    ),
) -> None:
    """Import vitiligo trials from a WHO ICTRP XML export file.

    Export from https://trialsearch.who.int/ → Export results to XML.
    """
    settings = get_settings()
    xml_path = Path(file)
    console.rule("[bold]WHO ICTRP (XML) ingestion[/bold]")
    console.print(f"Database: [cyan]{settings.resolved_db_path}[/cyan]")
    console.print(f"File:     [yellow]{xml_path}[/yellow]")
    if limit:
        console.print(f"Limit:    [magenta]{limit}[/magenta] (smoke test)")
    console.print()

    stats = run_ictrp_ingestion(
        file=xml_path,
        skip_duplicates=not keep_duplicates,
        limit=limit,
    )

    console.print()
    console.rule("[bold green]Done[/bold green]")
    _print_ingest_stats(stats)


@ingest_app.command("drugbank")
def ingest_drugbank(
    file: str = typer.Argument(..., help="Path to DrugBank full-database XML or .zip export."),
    query: str = typer.Option(
        DRUGBANK_DEFAULT_QUERY,
        "--query",
        "-q",
        help="Text filter for vitiligo relevance (searches indication, mechanism, names).",
    ),
    limit: int | None = typer.Option(
        None,
        "--limit",
        "-l",
        help="Cap matching drugs (targets from those drugs are still emitted).",
    ),
    no_seed: bool = typer.Option(
        False,
        "--no-seed-from-opentargets",
        help="Do not also include DrugBank drugs matching Open Targets drug names.",
    ),
) -> None:
    """Import vitiligo drug/target priors from a local DrugBank XML export.

    Requires an academic DrugBank account to download the full database from
    https://go.drugbank.com/releases/latest (Export → all-full-database).
    """
    settings = get_settings()
    xml_path = Path(file)
    console.rule("[bold]DrugBank (XML) ingestion[/bold]")
    console.print(f"Database: [cyan]{settings.resolved_db_path}[/cyan]")
    console.print(f"File:     [yellow]{xml_path}[/yellow]")
    console.print(f"Query:    [magenta]{query}[/magenta]")
    if limit:
        console.print(f"Limit:    [magenta]{limit}[/magenta] (smoke test)")
    console.print()

    stats = run_drugbank_ingestion(
        file=xml_path,
        query=query,
        seed_from_opentargets=not no_seed,
        limit=limit,
    )

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


@db_app.command("repair")
def db_repair(
    apply: bool = typer.Option(
        False, "--apply", help="Write the fixes (default: dry run that only reports)."
    ),
) -> None:
    """Fix truncated PubMed titles and drop non-series GEO records in an existing corpus."""
    init_db()
    stats = repair_corpus(apply=apply)
    mode = "[green]applied[/green]" if apply else "[yellow]dry run[/yellow]"
    console.rule(f"[bold]Corpus repair[/bold] — {mode}")
    console.print(
        f"PubMed titles re-derived from stored XML: [cyan]{stats.pubmed_titles_fixed}[/cyan]"
    )
    console.print(
        f"Non-series GEO documents removed:        [cyan]{stats.geo_documents_removed}[/cyan]"
    )
    if apply:
        console.print(
            f"Embeddings dropped:                      [cyan]{stats.embeddings_dropped}[/cyan]"
        )
    for source_id, old, new in stats.title_examples:
        console.print(f"  [dim]PMID {source_id}:[/dim] {old!r} -> {new!r}")
    if not apply:
        console.print("\n[dim]Re-run with --apply to write. Back up the database first.[/dim]")
    elif stats.embeddings_dropped:
        console.print("\n[dim]Next: vitiligo embed run  (re-embeds the repaired documents)[/dim]")


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


@embed_app.command("full-text")
def embed_full_text_cmd(
    limit: int | None = typer.Option(None, "--limit", "-l", help="Cap documents (smoke tests)."),
    batch_size: int = typer.Option(64, "--batch-size", "-b", help="Passages per encode call."),
) -> None:
    """Chunk and embed the body of full-text papers, so search can see past the abstract."""
    from vitiligo.embed.full_text import embed_full_text

    console.rule("[bold]Full-text passages[/bold]")
    stats = embed_full_text(batch_size=batch_size, limit=limit)
    table = Table(show_header=False, box=None)
    table.add_row("Model", stats.model)
    table.add_row("Documents embedded", f"{stats.documents_embedded:,}")
    table.add_row("Passages written", f"{stats.chunks_written:,}")
    table.add_row("Unchanged (skipped)", f"{stats.documents_unchanged:,}")
    table.add_row("No body text", f"{stats.documents_without_text:,}")
    console.print(table)
    if stats.chunks_written:
        console.print("[dim]Search them with: vitiligo search --full-text[/dim]")


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
    full_text: bool = typer.Option(
        False,
        "--full-text",
        help="Search the body of full-text papers instead of titles and abstracts.",
    ),
    show_abstract: bool = typer.Option(
        False,
        "--show-abstract/--no-abstract",
        help="Include a short abstract excerpt in the output.",
    ),
) -> None:
    """Semantic search over the embedded corpus."""
    console.rule(f"[bold]Search[/bold] — [yellow]{query}[/yellow]")
    if full_text:
        from vitiligo.embed.search import search_full_text

        hits = search_full_text(query=query, top_k=top_k, model_name=model)
    else:
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
        level = classify_document(doc)
        meta_bits.append(f"[magenta]{evidence_level_label(level)}[/magenta]")
        if meta_bits:
            console.print("  ".join(meta_bits))
        if hit.snippet:
            where = f"[dim]{hit.section}[/dim] " if hit.section else ""
            console.print(f"{where}{hit.snippet}", highlight=False)
        elif show_abstract and doc.abstract:
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
    except (LLMUnavailable, CorpusUnavailable) as exc:
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
    top_trials: int = typer.Option(12, "--top-trials", help="Trials to retrieve."),
) -> None:
    """Generate ranked therapeutic candidates from the corpus (requires Anthropic API key)."""
    console.rule(f"[bold]Hypothesize[/bold] — [yellow]{intent}[/yellow]")
    try:
        report = generate_hypotheses(intent=intent, top_k=top_k, top_trials=top_trials)
    except (LLMUnavailable, CorpusUnavailable) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc

    if report.notes:
        console.print(f"[dim]{report.notes}[/dim]")
        console.print()

    console.print(
        f"[dim]Evidence base: {len(report.citations)} papers, "
        f"{len(report.trial_citations)} trials, "
        f"{len(report.prior_citations)} priors, "
        f"{len(report.graph_citations)} graph edges[/dim]"
    )
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
            console.print(f"[bold]Papers:[/bold] {cand.citation_indices}")
        if cand.trial_citation_indices:
            console.print(f"[bold]Trials:[/bold] {[f'T{i}' for i in cand.trial_citation_indices]}")
        if cand.prior_citation_indices:
            console.print(f"[bold]Priors:[/bold] {[f'P{i}' for i in cand.prior_citation_indices]}")
        if cand.graph_citation_indices:
            console.print(f"[bold]Graph:[/bold] {[f'G{i}' for i in cand.graph_citation_indices]}")
        console.print()


# --------------------------------------------------------------------- graph


@graph_app.command("seed")
def graph_seed_cmd() -> None:
    """Seed the knowledge graph from priors and trials (no LLM)."""
    init_db()
    console.rule("[bold]Knowledge graph — seed[/bold]")
    stats = seed_graph_from_structured_sources()
    table = Table(show_header=False, box=None)
    table.add_row("Entities", str(stats.entities))
    table.add_row("Edges inserted", str(stats.edges_inserted))
    table.add_row("Edges merged", str(stats.edges_merged))
    console.print(table)


@graph_app.command("extract")
def graph_extract_cmd(
    limit: int = typer.Option(50, "--limit", "-l", help="Max documents to extract."),
) -> None:
    """Run LLM extraction over document abstracts (requires Anthropic API key)."""
    init_db()
    console.rule(f"[bold]Knowledge graph — extract[/bold] (limit={limit})")
    try:
        stats = extract_graph_from_documents(limit=limit)
    except LLMUnavailable as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc

    table = Table(show_header=False, box=None)
    table.add_row("Processed", str(stats.documents_processed))
    table.add_row("Failed", str(stats.documents_failed))
    table.add_row("Skipped", str(stats.documents_skipped))
    table.add_row("Entities added", str(stats.entities_added))
    table.add_row("Edges inserted", str(stats.edges_inserted))
    table.add_row("Edges merged", str(stats.edges_merged))
    console.print(table)


@graph_app.command("build")
def graph_build_cmd(
    no_seed: bool = typer.Option(False, "--no-seed", help="Skip structured seeding."),
    extract: bool = typer.Option(False, "--extract", help="Run LLM extraction after seed."),
    extract_limit: int = typer.Option(50, "--extract-limit", help="Documents for LLM extract."),
) -> None:
    """Seed structured sources and optionally run LLM extraction."""
    console.rule("[bold]Knowledge graph — build[/bold]")
    try:
        stats: GraphBuildStats = run_graph_build(
            seed=not no_seed,
            extract=extract,
            extract_limit=extract_limit,
        )
    except LLMUnavailable as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc

    if stats.seed:
        console.print(
            f"[green]Seed:[/green] {stats.seed.entities} entities, "
            f"{stats.seed.edges_inserted} edges inserted, "
            f"{stats.seed.edges_merged} merged"
        )
    if stats.extract:
        console.print(
            f"[green]Extract:[/green] {stats.extract.documents_processed} docs, "
            f"{stats.extract.edges_inserted + stats.extract.edges_merged} edges"
        )


@graph_app.command("stats")
def graph_stats_cmd() -> None:
    """Show knowledge graph statistics."""
    init_db()
    summary = summarize_graph()
    total = summary["total"]
    entities = next((r.count for r in total if r.label == "entities"), 0)
    edges = next((r.count for r in total if r.label == "edges"), 0)
    console.rule("[bold]Knowledge graph[/bold]")
    console.print(f"Entities: [cyan]{entities}[/cyan]  Edges: [cyan]{edges}[/cyan]")
    if summary["by_kind"]:
        kind_table = Table(title="Entities by kind", show_header=True, header_style="bold")
        kind_table.add_column("Kind")
        kind_table.add_column("Count", justify="right")
        for row in summary["by_kind"]:
            kind_table.add_row(row.label, str(row.count))
        console.print(kind_table)
    if summary["by_predicate"]:
        pred_table = Table(title="Edges by predicate", show_header=True, header_style="bold")
        pred_table.add_column("Predicate")
        pred_table.add_column("Count", justify="right")
        for row in summary["by_predicate"]:
            pred_table.add_row(row.label, str(row.count))
        console.print(pred_table)


@graph_app.command("search")
def graph_search_cmd(
    query: str = typer.Argument(..., help="Entity name or fragment."),
    limit: int = typer.Option(20, "--limit", "-l"),
) -> None:
    """Search graph entities by name."""
    init_db()
    rows = search_entities(query, limit=limit)
    if not rows:
        console.print("[yellow]No entities match.[/yellow]")
        return
    for entity in rows:
        kind = entity.kind.value if hasattr(entity.kind, "value") else str(entity.kind)
        console.print(f"[cyan]{kind}[/cyan]:{entity.key} — [bold]{entity.name}[/bold]")


@graph_app.command("neighbors")
def graph_neighbors_cmd(
    name_or_key: str = typer.Argument(..., help="Entity name or normalized key."),
    hops: int = typer.Option(1, "--hops", "-h", min=1, max=2),
    limit: int = typer.Option(30, "--limit", "-l"),
) -> None:
    """Show edges adjacent to an entity."""
    init_db()
    edges = get_neighbors(name_or_key, hops=hops, limit=limit)
    if not edges:
        console.print("[yellow]No neighbors found (try `vitiligo graph seed` first).[/yellow]")
        return
    for edge in edges:
        console.print(
            f"[bold]{edge.subject_name}[/bold] ({edge.subject_kind}) "
            f"—[{edge.predicate}]→ "
            f"[bold]{edge.object_name}[/bold] ({edge.object_kind}) "
            f"[dim]conf={edge.confidence:.2f} {edge.extraction_method}[/dim]"
        )


@graph_app.command("export")
def graph_export_cmd(
    output: str = typer.Option(
        None,
        "--output",
        "-o",
        help="Write JSON snapshot to this path (default: stdout).",
    ),
    edge_limit: int | None = typer.Option(
        None,
        "--edge-limit",
        help="Cap edges exported (default: all).",
    ),
) -> None:
    """Export the knowledge graph as JSON for expert review or archival."""
    import json
    from pathlib import Path

    init_db()
    snapshot = export_graph_snapshot(edge_limit=edge_limit)
    text = json.dumps(snapshot, indent=2)

    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        console.print(
            f"[green]Exported[/green] {len(snapshot['entities'])} entities, "
            f"{len(snapshot['edges'])} edges -> [cyan]{path}[/cyan]"
        )
    else:
        console.print(text)


# --------------------------------------------------------------------- priors


@priors_app.command("stats")
def priors_stats() -> None:
    """High-level statistics over the priors table."""
    init_db()
    summary = summarize_priors()
    console.rule("[bold]Priors store[/bold]")
    total = summary["total"][0].count if summary["total"] else 0
    console.print(f"Total priors: [cyan]{total}[/cyan]")

    if total == 0:
        console.print(
            "[yellow]No priors yet. Run `vitiligo ingest opentargets` or `vitiligo ingest drugbank`.[/yellow]"
        )
        return

    console.print()
    console.print("[bold]By kind[/bold]")
    for row in summary["by_kind"]:
        console.print(f"  {row.label}: [cyan]{row.count}[/cyan]")

    if summary.get("by_clinical_stage"):
        console.print()
        console.print("[bold]Drug clinical stages[/bold]")
        for row in summary["by_clinical_stage"]:
            console.print(f"  {row.label}: [cyan]{row.count}[/cyan]")


@priors_app.command("sample")
def priors_sample(
    kind: str = typer.Option("drug", "--kind", help="drug | target"),
    limit: int = typer.Option(10, "--limit", "-l"),
) -> None:
    """Show a sample of stored priors."""
    init_db()
    if kind == "drug":
        rows = list_drug_priors(limit=limit)
    elif kind == "target":
        rows = list_target_priors(limit=limit)
    else:
        console.print("[red]kind must be 'drug' or 'target'[/red]")
        raise typer.Exit(code=2)

    if not rows:
        console.print(
            "[yellow]No priors found. Run `vitiligo ingest opentargets` or `vitiligo ingest drugbank`.[/yellow]"
        )
        return

    console.rule(f"[bold]Sample {kind} priors[/bold]")
    for p in rows:
        score = f" score={p.score:.3f}" if p.score is not None else ""
        stage = f" stage={p.clinical_stage}" if p.clinical_stage else ""
        console.print(f"[cyan]{p.source_id}[/cyan] {p.name}{score}{stage}")


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
            "[yellow]No trials yet. Run `vitiligo ingest ctgov` or `vitiligo ingest euctr`.[/yellow]"
        )
        return

    if summary.get("by_source"):
        src_table = Table(title="By source", show_header=True, header_style="bold")
        src_table.add_column("Source")
        src_table.add_column("Count", justify="right")
        for row in summary["by_source"]:
            src_table.add_row(row.label, str(row.count))
        console.print(src_table)

    if summary["by_status"]:
        status_table = Table(title="By status", show_header=True, header_style="bold")
        status_table.add_column("Status")
        status_table.add_column("Count", justify="right")
        for row in summary["by_status"]:
            status_table.add_row(row.label, str(row.count))
        console.print(status_table)

    if summary["by_results"]:
        results_table = Table(title="Reported results", show_header=True, header_style="bold")
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
                f"{iv.get('type', '?')}: {iv.get('name', '?')}" for iv in trial.interventions[:5]
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
    source: str | None = typer.Option(
        None,
        "--source",
        help="Restrict to a single registry: ctgov | euctr | ictrp.",
    ),
    has_results: bool | None = typer.Option(
        None, "--has-results/--no-has-results", help="Only trials with reported results."
    ),
    limit: int = typer.Option(20, "--limit", "-l", help="Max trials to display."),
) -> None:
    """Structured search over the trials table."""
    init_db()
    if source:
        try:
            sources = (TrialSourceKind(source.lower()),)
        except ValueError as exc:
            console.print(f"[red]Unknown source '{source}'. Allowed: ctgov, euctr, ictrp.[/red]")
            raise typer.Exit(code=2) from exc
    else:
        sources = tuple(TrialSourceKind)  # type: ignore[assignment]

    filt = TrialFilter(
        query=query,
        status=status,
        phase=phase,
        country=country,
        sources=sources,
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
                f"{iv.get('type', '?')}: {iv.get('name', '?')}" for iv in trial.interventions[:4]
            ]
            console.print(f"Interventions: {' | '.join(ivs)}")
        if trial.countries:
            console.print(f"Countries: {', '.join(trial.countries[:6])}")
        console.print()


# --------------------------------------------------------------------- web


@report_app.command("candidates")
def report_candidates_cmd(
    json_out: str | None = typer.Option(
        None,
        "--json",
        help="Write machine-readable report JSON (e.g. exports/candidate-report.json).",
    ),
    markdown_out: str | None = typer.Option(
        None,
        "--markdown",
        help="Write human-readable Markdown (e.g. docs/candidate-report-v1.md).",
    ),
    intents: str | None = typer.Option(
        None,
        "--intents",
        help="Path to an intents JSON file (default: the packaged candidate-intents.json).",
    ),
    top_n: int = typer.Option(10, "--top-n", "-n", help="Candidates per intent / global list."),
    llm: bool = typer.Option(
        False,
        "--llm",
        help="Attach LLM rationale when ANTHROPIC_API_KEY is set (advisory only).",
    ),
) -> None:
    """Build an evidence-first ranked candidate report (deterministic, reproducible)."""
    init_db()
    console.rule("[bold]Candidate report[/bold] — evidence-first ranking")
    report = build_candidate_report(
        intents_path=Path(intents) if intents else None,
        top_n=top_n,
        include_llm=llm,
    )

    console.print(
        f"[dim]Corpus: {report.corpus.get('documents', 0):,} docs, "
        f"{report.corpus.get('trials', 0)} trials, "
        f"{len(report.global_top)} global candidates[/dim]"
    )
    console.print()

    table = Table(title="Global top candidates")
    table.add_column("#", style="cyan")
    table.add_column("Name")
    table.add_column("Strength")
    table.add_column("Score", justify="right")
    table.add_column("Stage")
    for cand in report.global_top:
        table.add_row(
            str(cand.rank),
            cand.name,
            cand.evidence_strength,
            str(cand.score.total),
            cand.clinical_stage or "—",
        )
    console.print(table)

    if json_out:
        json_path = Path(json_out)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(report_to_dict(report), indent=2) + "\n")
        console.print(f"\n[green]Wrote[/green] {json_path}")

    if markdown_out:
        md_path = Path(markdown_out)
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(render_candidate_report_markdown(report))
        console.print(f"[green]Wrote[/green] {md_path}")

    if not json_out and not markdown_out:
        console.print(
            "\n[dim]Tip: pass --json exports/candidate-report.json "
            "--markdown docs/candidate-report-v1.md[/dim]"
        )


@report_app.command("jak")
def report_jak_cmd(
    json_out: str | None = typer.Option(
        None,
        "--json",
        help="Write the full atlas as JSON (e.g. exports/jak-atlas.json).",
    ),
    markdown_out: str | None = typer.Option(
        None,
        "--markdown",
        help="Write a human-readable Markdown atlas (e.g. exports/jak-atlas.md).",
    ),
    csv_dir: str | None = typer.Option(
        None,
        "--csv-dir",
        help="Write trials.csv, outcomes.csv, adverse_events.csv into this directory.",
    ),
) -> None:
    """Build the open JAK-inhibitor evidence atlas (registry data, no LLM)."""
    init_db()
    console.rule("[bold]JAK inhibitor atlas[/bold] — registry evidence for vitiligo")
    atlas = build_jak_atlas()

    studies = len({t.study_id for t in atlas.trials})
    console.print(
        f"[dim]{studies} studies ({len(atlas.trials)} registry records) across "
        f"{sum(1 for a in atlas.agents if a.studies)} agents[/dim]"
    )
    console.print()

    table = Table(title="JAK-family agents in vitiligo")
    table.add_column("Agent")
    table.add_column("OT stage")
    table.add_column("Top trial phase")
    table.add_column("Studies", justify="right")
    table.add_column("Posted results", justify="right")
    table.add_column("Routes")
    for summary in atlas.agents:
        table.add_row(
            summary.name,
            summary.prior_stage or "—",
            summary.max_trial_stage or "—",
            str(summary.studies),
            str(summary.studies_with_posted_results),
            ", ".join(summary.routes) or "—",
        )
    console.print(table)

    if json_out:
        json_path = Path(json_out)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(atlas_to_dict(atlas), indent=2) + "\n")
        console.print(f"\n[green]Wrote[/green] {json_path}")

    if markdown_out:
        md_path = Path(markdown_out)
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(render_jak_atlas_markdown(atlas))
        console.print(f"[green]Wrote[/green] {md_path}")

    if csv_dir:
        for path in write_jak_atlas_csv(atlas, Path(csv_dir)):
            console.print(f"[green]Wrote[/green] {path}")

    if not (json_out or markdown_out or csv_dir):
        console.print(
            "\n[dim]Tip: pass --json exports/jak-atlas.json --markdown exports/jak-atlas.md "
            "--csv-dir exports/jak-atlas[/dim]"
        )


@report_app.command("jak-arms")
def report_jak_arms_cmd(
    csv_out: str = typer.Option(
        "exports/jak-arms.csv", "--csv", help="Harmonized arm-level table (CSV)."
    ),
    json_out: str | None = typer.Option(None, "--json", help="Also write rows + summary as JSON."),
    with_papers: bool = typer.Option(
        False,
        "--with-papers",
        help=f"Append curated paper rows the registry lacks ({PAPER_CURATION}), flagged by source "
        "and analysis population.",
    ),
) -> None:
    """Build the harmonized arm x endpoint x week table from posted JAK trial results."""
    init_db()
    console.rule("[bold]JAK arm table[/bold] — harmonized responder endpoints")
    rows = harmonize_arms(build_jak_atlas())
    if with_papers:
        from vitiligo.reports.paper_results import (
            cross_check,
            load_curation,
            new_rows,
            to_arm_rows,
        )

        paper = to_arm_rows(load_curation(PAPER_CURATION))
        for check in cross_check(paper, rows):
            colour = "green" if check["agree"] else "red"
            console.print(
                f"[{colour}]paper {check['paper']} vs registry {check['registry']}[/{colour}] "
                f"{check['row']}"
            )
        added = new_rows(paper, rows)
        rows = rows + added
        console.print(f"Added {len(added)} paper rows (of {len(paper)} curated).")
    summary = summarize_arms(rows)
    console.print(
        f"{summary['rows']} rows from {summary['trials']} trials / {summary['arms']} arms; "
        f"[cyan]{summary['model_ready_rows']}[/cyan] model-ready rows "
        f"from {summary['model_ready_trials']} trials"
    )
    for key in ("by_agent", "by_endpoint", "by_week", "flags"):
        console.print(f"[bold]{key}:[/bold] {summary[key]}")

    write_arms_csv(rows, Path(csv_out))
    console.print(f"\n[green]Wrote[/green] {csv_out}")
    if json_out:
        json_path = Path(json_out)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"summary": summary, "rows": [asdict(r) for r in rows]}
        json_path.write_text(json.dumps(payload, indent=2) + "\n")
        console.print(f"[green]Wrote[/green] {json_path}")


def _paper_tables(pmcids: list[str]) -> dict[str, Any]:
    from vitiligo.reports.paper_results import parse_tables
    from vitiligo.sources.pmc import PMCClient

    with PMCClient() as client:
        return {p: parse_tables(client.fetch_article_xml(p)) for p in pmcids}


@papers_app.command("tables")
def papers_tables_cmd(pmcid: str = typer.Argument(..., help="e.g. PMC11169949")) -> None:
    """Print an open-access article's tables as parsed (for curation)."""
    for table in _paper_tables([pmcid])[pmcid]:
        console.rule(f"{table.label}  {table.caption[:100]}")
        for cells in table.rows:
            console.print(" | ".join(cells), markup=False, highlight=False)
        if table.footnote:
            console.print(f"[dim]{table.footnote}[/dim]")


@papers_app.command("verify")
def papers_verify_cmd(
    path: str = typer.Option(str(PAPER_CURATION), "--file", help="Curation file."),
) -> None:
    """Check every curated number against the printed table cell in the article."""
    from vitiligo.reports.paper_results import load_curation, verify

    results = load_curation(Path(path))
    tables = _paper_tables(sorted({r.pmcid for r in results}))
    problems = verify(results, tables)
    for problem in problems:
        console.print(f"[red]{problem}[/red]")
    console.print(
        f"{len(results) - len(problems)} of {len(results)} curated numbers match their cells."
    )
    if problems:
        raise typer.Exit(code=1)


def _geo_accessions(accessions: list[str] | None) -> list[str]:
    """Explicit accessions, or every GEO series in the corpus."""
    if accessions:
        return accessions
    init_db()
    with session_scope() as session:
        rows = session.exec(
            select(Document.source_id)
            .where(Document.source == SourceKind.GEO)
            .order_by(Document.source_id)
        ).all()
    return [str(r) for r in rows]


@geo_data_app.command("list")
def geo_data_list_cmd(
    accessions: list[str] | None = typer.Argument(  # noqa: B008 (variadic arguments are lists)
        None, help="GSE accessions (default: every GEO series in the corpus)."
    ),
) -> None:
    """Show what each series offers for download, without fetching anything."""
    from vitiligo.sources.geo_files import list_files

    table = Table(title="GEO supplementary files")
    table.add_column("Series", style="cyan")
    table.add_column("Files", justify="right")
    table.add_column("Listed size", justify="right")
    table.add_column("Largest file")
    total = 0
    with httpx.Client(timeout=httpx.Timeout(60.0, connect=15.0), follow_redirects=True) as client:
        for accession in _geo_accessions(accessions):
            files = list_files(accession, client)
            size = sum(f.listed_bytes for f in files)
            total += size
            largest = max(files, key=lambda f: f.listed_bytes).name if files else "—"
            table.add_row(
                accession,
                str(len(files)) if files else "0 (on samples)",
                f"{size / 1e6:.1f} MB",
                largest[:46],
            )
    console.print(table)
    console.print(f"[dim]Listed total: {total / 1e9:.2f} GB (the listing rounds sizes).[/dim]")


@geo_data_app.command("fetch")
def geo_data_fetch_cmd(
    accessions: list[str] | None = typer.Argument(  # noqa: B008 (variadic arguments are lists)
        None, help="GSE accessions (default: every GEO series in the corpus)."
    ),
    cache: str = typer.Option("data/geo", "--cache", help="Where files are stored."),
    max_mb: float | None = typer.Option(
        None, "--max-mb", help="Skip any single file larger than this."
    ),
) -> None:
    """Download series supplementary files, recording URL, size and SHA-256 for each."""
    from vitiligo.sources.geo_files import cache_summary, fetch_series

    cache_dir = Path(cache)
    downloaded = cached = skipped = 0
    new_bytes = 0
    with httpx.Client(timeout=httpx.Timeout(300.0, connect=15.0), follow_redirects=True) as client:
        for remote, result, note in fetch_series(
            _geo_accessions(accessions),
            cache_dir,
            client=client,
            max_bytes=int(max_mb * 1e6) if max_mb else None,
        ):
            if note == "downloaded" and result is not None:
                downloaded += 1
                new_bytes += result.bytes
                console.print(
                    f"[green]↓[/green] {remote.accession}/{remote.name} ({result.megabytes:.1f} MB)"
                )
            elif note == "cached":
                cached += 1
            else:
                skipped += 1
                console.print(f"[yellow]-[/yellow] {remote.accession}/{remote.name}: {note}")

    summary = cache_summary(cache_dir)
    console.print(
        f"\n[bold]{downloaded}[/bold] downloaded ({new_bytes / 1e9:.2f} GB), "
        f"{cached} already cached, {skipped} skipped."
    )
    console.print(
        f"Cache: {summary['files']} files from {summary['series']} series, "
        f"{summary['bytes'] / 1e9:.2f} GB in {cache_dir}/"
    )


@geo_data_app.command("status")
def geo_data_status_cmd(
    cache: str = typer.Option("data/geo", "--cache", help="Where files are stored."),
) -> None:
    """What the local cache holds."""
    from vitiligo.sources.geo_files import cache_summary

    summary = cache_summary(Path(cache))
    if not summary["files"]:
        console.print(f"[yellow]Nothing cached in {cache}/[/yellow] — run: vitiligo geo-data fetch")
        return
    table = Table(title=f"GEO data cache ({cache}/)")
    table.add_column("Series", style="cyan")
    table.add_column("Files", justify="right")
    table.add_column("Size", justify="right")
    for accession, entry in summary["by_series"].items():
        table.add_row(accession, str(entry["files"]), f"{entry['bytes'] / 1e6:.1f} MB")
    console.print(table)
    console.print(
        f"[dim]{summary['files']} files, {summary['bytes'] / 1e9:.2f} GB. "
        f"Provenance in {cache}/manifest.json[/dim]"
    )


def _load_mechanisms(path: str) -> list[Any]:
    from vitiligo.mechanisms import load

    try:
        return load(Path(path))
    except FileNotFoundError as exc:
        console.print(f"[red]No curation file at {path}[/red]")
        raise typer.Exit(code=2) from exc


@mechanism_app.command("list")
def mechanism_list_cmd(
    path: str = typer.Option(str(MECHANISM_CURATION), "--file", help="Curation file."),
) -> None:
    """List mechanistic hypotheses with what their supporting evidence reaches."""
    from vitiligo.mechanisms import CAUSAL_LABELS, OUTCOMES

    mechanisms = _load_mechanisms(path)
    table = Table(title="Mechanistic hypotheses")
    table.add_column("ID", style="cyan", overflow="fold")
    table.add_column("Outcome")
    table.add_column("Status")
    table.add_column("Supporting evidence reaches")
    table.add_column("For / against", justify="right")
    for m in mechanisms:
        table.add_row(
            m.id,
            f"{m.outcome}. {OUTCOMES.get(m.outcome, '?')}",
            m.status,
            CAUSAL_LABELS.get(m.causal_support, m.causal_support),
            f"{len(m.supporting())} / {len(m.against())}",
        )
    console.print(table)
    console.print(
        "[dim]Supporting evidence reaches: the strongest rung any supporting source "
        "reaches on the causal ladder. It is computed, not curated.[/dim]"
    )


@mechanism_app.command("show")
def mechanism_show_cmd(
    mechanism_id: str = typer.Argument(..., help="e.g. trm-il15-relapse"),
    path: str = typer.Option(str(MECHANISM_CURATION), "--file", help="Curation file."),
    json_out: bool = typer.Option(False, "--json", help="Print the record as JSON."),
) -> None:
    """Print one hypothesis: the chain, its evidence, the rivals, and the test."""
    from vitiligo.mechanisms import CAUSAL_LABELS, OUTCOMES, to_dict

    mechanisms = _load_mechanisms(path)
    found = next((m for m in mechanisms if m.id == mechanism_id), None)
    if found is None:
        console.print(f"[red]No hypothesis {mechanism_id!r}[/red] in {path}")
        raise typer.Exit(code=1)
    if json_out:
        console.print_json(json.dumps(to_dict(found), default=str))
        return

    console.rule(f"[bold]{found.title}[/bold]")
    console.print(
        f"[dim]{found.id} · {found.status} · outcome {found.outcome}: "
        f"{OUTCOMES.get(found.outcome, '?')} · reviewed {found.last_reviewed}[/dim]\n"
    )
    chain = Table(show_header=False, box=None, pad_edge=False)
    chain.add_column("Level", style="cyan", no_wrap=True)
    chain.add_column("Statement")
    for label, value in (
        ("Biological state", found.biological_state),
        ("Mechanistic hypothesis", found.mechanistic_claim),
        ("Intervention hypothesis", found.intervention),
        ("Experimental outcome", found.experimental_outcome),
        ("Clinical outcome", found.clinical_outcome),
    ):
        chain.add_row(label, value)
    console.print(chain)
    console.print(
        f"\n[bold]Context[/bold]: {found.context.subtype} · {found.context.tissue} · "
        f"{found.context.cell_type} · {found.context.disease_stage}"
    )
    console.print(
        f"[bold]Supporting evidence reaches[/bold]: "
        f"{CAUSAL_LABELS.get(found.causal_support, found.causal_support)}\n"
    )

    evidence = Table(title="Evidence")
    evidence.add_column("Stance")
    evidence.add_column("Causal level")
    evidence.add_column("Source", style="cyan")
    evidence.add_column("What it shows")
    for e in found.evidence:
        evidence.add_row(
            e.stance, CAUSAL_LABELS.get(e.causal_level, e.causal_level), e.ref, e.shows
        )
    console.print(evidence)

    console.print("\n[bold]Competing explanations[/bold]")
    for c in found.competing:
        console.print(f"- {c.explanation}")
        console.print(f"  [dim]Told apart by: {c.distinguished_by}[/dim]")

    console.print("\n[bold]Test[/bold]")
    for label, value in (
        ("Question", found.test.question),
        ("Data", found.test.data),
        ("If correct", found.test.if_correct),
        ("If incorrect", found.test.if_incorrect),
        ("Decides", found.test.decides),
    ):
        console.print(f"- [cyan]{label}[/cyan]: {value}")
    console.print(f"\n[bold]Uncertainty[/bold]: {found.uncertainty}")
    if found.seal:
        console.print(
            f"[dim]Sealed {found.seal.get('sealed_at')} · {found.seal.get('sha256')}[/dim]"
        )


@mechanism_app.command("verify")
def mechanism_verify_cmd(
    path: str = typer.Option(str(MECHANISM_CURATION), "--file", help="Curation file."),
    structure_only: bool = typer.Option(
        False, "--structure-only", help="Skip the corpus checks (no local corpus needed)."
    ),
) -> None:
    """Check the chain, falsifiability, citations, causal levels and seals."""
    from vitiligo.mechanisms import check_structure, verify

    mechanisms = _load_mechanisms(path)
    if structure_only:
        problems = check_structure(mechanisms)
    else:
        init_db()
        problems = verify(mechanisms)
    for problem in problems:
        console.print(f"[red]{problem}[/red]")
    checked = "structure" if structure_only else "structure, citations and seals"
    console.print(
        f"{len(mechanisms) - len({p.split(':')[0] for p in problems})} of {len(mechanisms)} "
        f"hypotheses pass ({checked})."
    )
    if problems:
        raise typer.Exit(code=1)


@mechanism_app.command("seal")
def mechanism_seal_cmd(
    mechanism_id: str = typer.Argument(..., help="Hypothesis to seal."),
    path: str = typer.Option(str(MECHANISM_CURATION), "--file", help="Curation file."),
) -> None:
    """Freeze a hypothesis's claim, context and test with a SHA-256 (evidence stays open)."""
    from datetime import UTC, datetime

    from vitiligo.mechanisms import from_dict, seal_hash, verify

    raw = json.loads(Path(path).read_text())
    record = next((r for r in raw["mechanisms"] if r.get("id") == mechanism_id), None)
    if record is None:
        console.print(f"[red]No hypothesis {mechanism_id!r}[/red] in {path}")
        raise typer.Exit(code=1)
    if record.get("seal"):
        console.print(f"[yellow]{mechanism_id} is already sealed[/yellow]; edit the seal by hand.")
        raise typer.Exit(code=1)

    init_db()
    mechanism = from_dict(record)
    problems = verify([mechanism])
    if problems:
        for problem in problems:
            console.print(f"[red]{problem}[/red]")
        console.print("[red]Not sealed: fix the problems above first.[/red]")
        raise typer.Exit(code=1)

    sealed_at = datetime.now(UTC).isoformat()
    record["seal"] = {"sha256": seal_hash(mechanism), "sealed_at": sealed_at}
    record["status"] = "sealed"
    Path(path).write_text(json.dumps(raw, indent=1, ensure_ascii=False) + "\n")
    console.print(f"[green]Sealed[/green] {mechanism_id}: {record['seal']['sha256']}")
    console.print(
        "[dim]The seal covers the claim, context and test; evidence may still grow.[/dim]"
    )


def _backtest_summary(path: Path) -> dict[str, Any]:
    """Overall metrics of a back-test file, plus its SHA-256, for sealing into a forecast."""
    raw = path.read_bytes()
    data = json.loads(raw)
    loto = data["leave_one_trial_out"]
    timing = data["time_extrapolation"]
    loto_points = [p for fold in loto["folds"].values() for p in fold["points"]]

    def signed_error(points: list[dict[str, Any]]) -> float | None:
        """Mean of (predicted median - observed), percentage points; > 0 = over-prediction."""
        if not points:
            return None
        diffs = [float(p["predicted"]["median"]) - float(p["observed"]) for p in points]
        return round(100 * sum(diffs) / len(diffs), 2)

    return {
        "file": str(path),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "leave_one_trial_out": loto["overall"],
        "leave_one_trial_out_mean_signed_error_pp": signed_error(loto_points),
        "leave_one_trial_out_all_converged": loto.get("all_folds_converged"),
        "time_extrapolation": timing["overall"],
        "time_extrapolation_mean_signed_error_pp": signed_error(timing["points"]),
        "time_extrapolation_converged": timing.get("converged"),
    }


def _model_inputs() -> tuple[list[ArmEndpointRow], dict[str, str]]:
    """Arm table rows plus each agent's route from the atlas (all registries)."""
    init_db()
    atlas = build_jak_atlas()
    routes = {s.name: s.routes[0] for s in atlas.agents if len(s.routes) == 1}
    return harmonize_arms(atlas), routes


def _committed_code_or_exit() -> dict[str, str]:
    """The commit to seal into a forecast; exits if the model code is uncommitted."""
    from vitiligo.discovery.forecasts import committed_code

    try:
        return committed_code()
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc


TOPLINE_CURATION = Path("curation/topline-results.json")


def model_inputs_v03(
    *, with_toplines: bool, with_papers: bool = True
) -> tuple[list[ArmEndpointRow], dict[str, str], dict[str, bool]]:
    """v0.3 inputs: registry rows + curated paper rows the registry lacks (+ toplines),
    agent routes, and which trials are phase 3 (from the registry record)."""
    from vitiligo.reports.paper_results import load_curation, load_toplines, new_rows, to_arm_rows

    init_db()
    atlas = build_jak_atlas()
    routes = {s.name: s.routes[0] for s in atlas.agents if len(s.routes) == 1}
    rows = harmonize_arms(atlas)
    if with_papers:
        rows = rows + new_rows(to_arm_rows(load_curation(PAPER_CURATION)), rows)
    phase3 = {t.source_id: "PHASE3" in (t.phases or []) for t in atlas.trials}
    if with_toplines:
        toplines = load_toplines(TOPLINE_CURATION)
        rows = rows + toplines
        phase3 |= {r.source_id: True for r in toplines}  # all toplines are phase 3
    return rows, routes, phase3


@model_app.command("backtest")
def model_backtest_cmd(
    instrument: str = typer.Option("F-VASI", "--instrument", help="F-VASI or T-VASI."),
    out: str | None = typer.Option(None, "--out", help="Write full back-test results as JSON."),
) -> None:
    """Leave-one-trial-out and week-24 -> later-weeks back-tests of the scenario model."""
    from vitiligo.models.jak_mbma import backtest_leave_one_trial_out, backtest_time_extrapolation

    rows, routes = _model_inputs()
    console.rule(f"[bold]Scenario model back-tests[/bold] — {instrument}")
    loto = backtest_leave_one_trial_out(rows, instrument, agent_routes=routes)
    console.print(f"[bold]Leave-one-trial-out[/bold] ({loto['design']}): {loto['overall']}")
    for trial, fold in loto["folds"].items():
        status = "converged" if fold["converged"] else "[red]NOT converged[/red]"
        console.print(f"  {trial}: {fold['metrics']}  {status}")
    time_bt = backtest_time_extrapolation(rows, instrument, agent_routes=routes)
    console.print(f"[bold]Time extrapolation[/bold] ({time_bt['design']}): {time_bt['overall']}")
    if out:
        path = Path(out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"leave_one_trial_out": loto, "time_extrapolation": time_bt}, indent=2)
            + "\n"
        )
        console.print(f"[green]Wrote[/green] {path}")


@model_app.command("predict")
def model_predict_cmd(
    agent: str = typer.Option(
        ..., "--agent", help="e.g. ritlecitinib (unseen agents use the class prior)."
    ),
    dose: float = typer.Option(
        ..., "--dose", help="Dose per administration (mg, or % for creams)."
    ),
    unit: str = typer.Option("mg", "--unit", help="mg or %."),
    frequency: str = typer.Option("QD", "--frequency", help="QD or BID."),
    week: int = typer.Option(24, "--week"),
    threshold: int = typer.Option(75, "--threshold", help="VASI improvement threshold (25-100)."),
    instrument: str = typer.Option("F-VASI", "--instrument", help="F-VASI or T-VASI."),
    loading_dose: bool = typer.Option(
        False, "--loading-dose", help="Regimen starts with a loading dose."
    ),
    route: str | None = typer.Option(
        None, "--route", help="oral or topical (only used for agents without data)."
    ),
    phototherapy: bool = typer.Option(False, "--phototherapy", help="Combined with phototherapy."),
    n_active: int | None = typer.Option(None, "--n-active", help="Trial size: active arm."),
    n_control: int | None = typer.Option(None, "--n-control", help="Trial size: control arm."),
    label: str | None = typer.Option(None, "--label", help="Name for a frozen forecast."),
    freeze: str | None = typer.Option(
        None, "--freeze", help="Write a timestamped, SHA-256-sealed forecast JSON to this path."
    ),
    backtest: str | None = typer.Option(
        None,
        "--backtest",
        help="Back-test JSON (from `model backtest`) whose summary is sealed into the forecast.",
    ),
    public_check: str | None = typer.Option(
        None,
        "--public-results-check",
        help="Where you searched for already-public results (sponsor press releases, conference abstracts, publications) and what you found; sealed into the record."
        + " Required with --freeze.",
    ),
) -> None:
    """Predict a scenario's responder rate vs placebo in a new trial, with uncertainty."""
    if freeze and not (public_check or "").strip():
        console.print(
            "[red]--freeze needs --public-results-check: registry status alone misses "
            "toplines announced in press releases or at conferences.[/red]"
        )
        raise typer.Exit(code=2)
    code = _committed_code_or_exit() if freeze else None
    from vitiligo.models.jak_mbma import (
        PRIORS,
        Scenario,
        build_dataset,
        converged,
        fit,
        predict,
    )
    from vitiligo.models.jak_mbma import freeze as freeze_record

    rows, routes = _model_inputs()
    data = build_dataset(rows, instrument, agent_routes=routes)
    posterior = fit(data)
    if not converged(posterior):
        console.print(
            f"[red]Model did not converge: {posterior.diagnostics}. No prediction made.[/red]"
        )
        raise typer.Exit(code=1)
    scenario = Scenario(
        agent=agent,
        dose=dose,
        dose_unit=unit,
        frequency=frequency,
        week=week,
        threshold=threshold,
        loading_dose=loading_dose,
        phototherapy=phototherapy,
        route=route,
    )
    result = predict(posterior, scenario, n_active=n_active, n_control=n_control)

    def pct(interval: dict[str, float]) -> str:
        return (
            f"{100 * interval['median']:.1f}% (80%: {100 * interval['lo80']:.1f}-"
            f"{100 * interval['hi80']:.1f}; 95%: {100 * interval['lo95']:.1f}-{100 * interval['hi95']:.1f})"
        )

    endpoint = f"{instrument}{threshold} at week {week}"
    console.rule(f"[bold]Scenario[/bold] — {agent} {dose:g}{unit} {frequency}, {endpoint}")
    console.print(f"Active:     {pct(result['p_active'])}")
    console.print(f"Placebo:    {pct(result['p_control'])}")
    console.print(f"Difference: {pct(result['difference'])}")
    console.print(f"P(active > placebo): {result['p_active_beats_control']:.3f}")
    for note in result["extrapolation"]:
        console.print(f"[yellow]Extrapolation:[/yellow] {note}")
    console.print(f"[dim]Model diagnostics: {posterior.diagnostics}[/dim]")

    if freeze:
        observations = [asdict(o) for o in data.observations]
        record = freeze_record(
            {
                "label": label or f"{agent} {endpoint}",
                "engine_version": __version__,
                "model": "jak_mbma ordered-probit v0.2",
                "priors": PRIORS,
                "dataset": data.summary(),
                "data_sha256": hashlib.sha256(
                    json.dumps(observations, sort_keys=True).encode()
                ).hexdigest(),
                "diagnostics": posterior.diagnostics,
                "backtest_at_freeze": _backtest_summary(Path(backtest)) if backtest else None,
                "prediction": result,
                "public_results_check": public_check,
                "code": code,
                "disclaimer": "Research forecast; not medical advice or a treatment recommendation.",
            }
        )
        path = Path(freeze)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record, indent=2, default=str) + "\n")
        console.print(f"[green]Frozen[/green] {path}  sha256={record['sha256']}")


def _ledger() -> Any:
    from vitiligo.discovery.ledger import Ledger

    return Ledger(get_settings().resolved_ledger_path)


@discover_app.command("run")
def discover_run_cmd(
    alpha: float = typer.Option(0.10, "--alpha", help="Target false discovery rate (e-LOND)."),
    belief: float = typer.Option(
        0.80, "--belief", help="Only test claims the held-out model believes at least this much."
    ),
    max_trials: int | None = typer.Option(
        None, "--max-trials", help="Rounds (held-out trials) to run."
    ),
    seed: int = typer.Option(20261014, "--seed"),
) -> None:
    """Run discovery rounds over held-out trials with unspent evidence (needs '[model]')."""
    from vitiligo.discovery.loop import LoopConfig, run_discovery

    rows, routes = _model_inputs()
    ledger = _ledger()
    console.rule(f"[bold]Discovery loop[/bold] — ledger {ledger.path}")
    logs = run_discovery(
        rows,
        ledger,
        LoopConfig(alpha=alpha, belief_threshold=belief, seed=seed),
        agent_routes=routes,
        max_trials=max_trials,
    )
    if not logs:
        console.print("No unspent evidence units left — new data is needed for more tests.")
    for log in logs:
        console.print(
            f"\n[bold]Round {log.trial}[/bold]: {len(log.tests)} tests, {log.abstained} abstained"
            + (
                f" ({', '.join(f'{n} {r}' for r, n in sorted(log.abstain_reasons.items()))})"
                if log.abstain_reasons
                else ""
            )
        )
        for note in log.notes:
            console.print(f"  [yellow]{note}[/yellow]")
        for test in log.tests:
            colour = {"discovery": "green", "evidence": "cyan"}.get(test["status"], "dim")
            console.print(
                f"  t={test['t']:<3} [{colour}]{test['status']:<13}[/{colour}] "
                f"log10 e={test['log10_e']:>7} (needs {test['threshold_log10_e']}) "
                f"belief={test['belief']}  {test['statement']}"
            )
    console.print(f"\n[bold]Ledger:[/bold] {ledger.summary()}")


@discover_app.command("ledger")
def discover_ledger_cmd() -> None:
    """Show the ledger: tests, discoveries, policy statistics, pending forecasts."""
    ledger = _ledger()
    summary = ledger.summary()
    console.rule(f"[bold]Discovery ledger[/bold] — {ledger.path}")
    console.print(summary)
    table = Table(title="Tests (global order)")
    for column in ("t", "status", "log10 e", "belief", "statement"):
        table.add_column(column)
    for row in ledger.tested():
        table.add_row(
            str(row["t"]),
            row["status"],
            f"{row['log_e'] / 2.302585092994046:.2f}",
            f"{row['belief']:.2f}" if row["belief"] is not None else "-",
            row["statement"],
        )
    console.print(table)


@discover_app.command("import-forecasts")
def discover_import_cmd(
    directory: str = typer.Argument(..., help="Folder with sealed forecast JSON files."),
) -> None:
    """Add sealed forecasts to the ledger as pending tier-2 hypotheses (seals verified)."""
    ledger = _ledger()
    for path in sorted(Path(directory).glob("*.json")):
        record = json.loads(path.read_text())
        if "sha256" not in record or "prediction" not in record:
            continue  # e.g. back-test files stored alongside the forecasts
        added = ledger.import_forecast(record, str(path))
        console.print(f"{'[green]imported[/green]' if added else 'already present'}: {path.name}")


@discover_app.command("forecast-pending")
def discover_forecast_pending_cmd(
    out: str = typer.Option(
        ..., "--out", help="Folder for sealed forecasts (commit it to timestamp them)."
    ),
    backtest_dir: str | None = typer.Option(
        None, "--backtest-dir", help="Folder with backtest-*-<INSTRUMENT>.json to seal alongside."
    ),
    public_check: str = typer.Option(
        ...,
        "--public-results-check",
        help="Where you searched for already-public results (sponsor press releases, conference abstracts, publications) and what you found; sealed into the record.",
    ),
    skip_trials: list[str] | None = typer.Option(  # noqa: B008 (repeatable options are lists)
        None, "--skip", help="Trial id to leave out, e.g. results already public (repeatable)."
    ),
) -> None:
    """Seal forecasts for every unreported JAK trial the registry describes well enough."""
    if not public_check.strip():
        console.print("[red]--public-results-check must say what was searched and found.[/red]")
        raise typer.Exit(code=2)
    code = _committed_code_or_exit()
    from vitiligo.discovery.forecasts import forecast_target, registry_targets, write_forecast
    from vitiligo.models.jak_mbma import PRIORS, build_dataset, converged, fit

    init_db()
    atlas = build_jak_atlas()
    routes = {s.name: s.routes[0] for s in atlas.agents if len(s.routes) == 1}
    rows = harmonize_arms(atlas)
    ledger = _ledger()
    already = " ".join(ledger.forecast_labels())
    protocols = []
    with session_scope() as session:
        for jt in atlas.trials:
            if jt.outcomes or jt.source != "ctgov" or jt.source_id in already:
                continue
            if jt.source_id in (skip_trials or []):
                console.print(f"[dim]skip {jt.source_id}: --skip[/dim]")
                continue
            trial = session.exec(select(Trial).where(Trial.source_id == jt.source_id)).first()
            study = (trial.raw_metadata or {}).get("study") if trial else None
            if study:
                protocols.append(
                    (jt.source_id, jt.status or "", study.get("protocolSection") or {})
                )
    targets, skips = registry_targets(protocols)
    console.rule(f"[bold]Forecasting unreported trials[/bold] — {len(targets)} targets")
    for skip in skips:
        console.print(f"[dim]skip {skip.trial}: {skip.reason}[/dim]")

    posteriors: dict[str, Any] = {}
    for instrument in sorted({t.instrument for t in targets}):
        data = build_dataset(rows, instrument, agent_routes=routes)
        posterior = fit(data)
        if not converged(posterior):
            console.print(
                f"[red]{instrument}: fit did not converge {posterior.diagnostics}; skipped[/red]"
            )
            continue
        observations = [asdict(o) for o in data.observations]
        posteriors[instrument] = (
            posterior,
            data,
            hashlib.sha256(json.dumps(observations, sort_keys=True).encode()).hexdigest(),
        )

    directory = Path(out)
    for target in targets:
        if target.instrument not in posteriors:
            continue
        posterior, data, data_sha = posteriors[target.instrument]
        summary, p_active, p_control = forecast_target(posterior, target, routes=routes)
        backtest = None
        if backtest_dir:
            candidates = sorted(Path(backtest_dir).glob(f"backtest-*-{target.instrument}.json"))
            backtest = _backtest_summary(candidates[-1]) if candidates else None
        path, record = write_forecast(
            target,
            summary,
            p_active,
            p_control,
            directory,
            context={
                "engine_version": __version__,
                "model": "jak_mbma ordered-probit v0.2",
                "priors": PRIORS,
                "dataset": data.summary(),
                "data_sha256": data_sha,
                "diagnostics": posterior.diagnostics,
                "backtest_at_freeze": backtest,
                "public_results_check": public_check,
                "code": code,
                "disclaimer": "Research forecast; not medical advice. No results for this trial were consulted.",
            },
        )
        ledger.import_forecast(record, str(path))
        a, c = summary["p_active"], summary["p_control"]
        console.print(
            f"[green]sealed[/green] {target.key}: active {100 * a['median']:.1f}% "
            f"(80%: {100 * a['lo80']:.1f}-{100 * a['hi80']:.1f}) vs control {100 * c['median']:.1f}%; "
            f"P(beats)={summary['p_active_beats_control']:.2f}"
        )


def _model_name(record: dict[str, Any]) -> str:
    """Short model name of a sealed forecast. The first manual records (Tranquillo,
    2026-10-14) carry a stale "v0" label but were made with v0.2."""
    name = str(record.get("model", "?")).removeprefix("jak_mbma ordered-probit ")
    return "v0.2" if name == "v0" else name.removesuffix(" (challenger)")


@discover_app.command("check-forecasts")
def discover_check_forecasts_cmd(
    paths: list[str] | None = typer.Argument(  # noqa: B008 (variadic arguments are lists)
        None, help="Forecast files or folders (default: forecasts/)."
    ),
    json_out: str | None = typer.Option(None, "--json", help="Write all results as JSON."),
    markdown_out: str | None = typer.Option(
        None, "--markdown", help="Append a Markdown table (e.g. $GITHUB_STEP_SUMMARY)."
    ),
) -> None:
    """Score sealed forecasts against ClinicalTrials.gov posted results (no corpus needed)."""
    from vitiligo.discovery.forecasts import check_forecasts
    from vitiligo.sources.ctgov import CTGovClient

    with CTGovClient() as client:
        results = check_forecasts([Path(p) for p in (paths or ["forecasts"])], client.fetch_study)

    def cell(detail: dict[str, Any], key: str) -> str:
        value = detail.get(key)
        return (
            "-"
            if value is None
            else ("yes" if value is True else "no" if value is False else f"{value:.2f}")
        )

    lines = [
        "| Forecast | Model | Status | Observed active / control | In 80% | Direction | Log score |",
        "|---|---|---|---|---|---|---|",
    ]
    for path, r in results:
        model = _model_name(json.loads(path.read_text()))
        obs = r.detail.get("observed")
        observed = f"{obs['rate_active']:.1%} / {obs['rate_control']:.1%}" if obs else "-"
        status = "scored" if r.resolved else r.detail.get("reason", "pending")
        lines.append(
            f"| {r.label} | {model} | {status} | {observed} | {cell(r.detail, 'active_in80')} "
            f"| {cell(r.detail, 'direction_correct')} | {cell(r.detail, 'log_score')} |"
        )
    scored = sum(r.resolved for _p, r in results)
    lines.append("")
    lines.append(f"{scored} of {len(results)} sealed forecasts have posted results.")
    from vitiligo.discovery.forecasts import PREREGISTERED_COMPARISON, compare_models

    records = [(p, json.loads(p.read_text())) for p, _r in results]
    scored_by_model = [
        (_model_name(rec), rec, r) for (_p, rec), (_p2, r) in zip(records, results, strict=True)
    ]
    for title, keep in (
        ("Pre-registered comparison (decides the default)", PREREGISTERED_COMPARISON.__contains__),
        ("Other targets (reported, not decisive)", lambda k: k not in PREREGISTERED_COMPARISON),
    ):
        for pair, summary in compare_models(scored_by_model, keys=keep).items():
            if summary["targets"]:
                scores = ", ".join(f"{k} {v:.2f}" for k, v in summary.items() if k != "targets")
                lines.append(
                    f"{title}, {pair}: {summary['targets']} common resolved targets; "
                    f"log score {scores}"
                )
    console.print("\n".join(lines))
    if json_out:
        payload = [{"file": str(p), **asdict(r)} for p, r in results]
        Path(json_out).write_text(json.dumps(payload, indent=2, default=str) + "\n")
    if markdown_out:
        with open(markdown_out, "a") as fh:
            fh.write("## Sealed forecasts vs posted results\n\n" + "\n".join(lines) + "\n")


@discover_app.command("watch")
def discover_watch_cmd(
    paths: list[str] | None = typer.Argument(  # noqa: B008 (variadic arguments are lists)
        None, help="Sealed forecast files or folders (default: forecasts/)."
    ),
    days: int = typer.Option(8, "--days", help="Look back this many days."),
    since: str | None = typer.Option(
        None, "--since", help="Look back to this date (YYYY-MM-DD); overrides --days."
    ),
    json_out: str | None = typer.Option(None, "--json", help="Write the report as JSON."),
    markdown_out: str | None = typer.Option(
        None, "--markdown", help="Append the report as Markdown (e.g. $GITHUB_STEP_SUMMARY)."
    ),
) -> None:
    """Rank pending results by what they would tell us, and list what is new.

    New: Europe PMC papers and preprints, JAK vitiligo trials registered or updated
    on ClinicalTrials.gov, and SEC filings mentioning vitiligo (needs SEC_USER_AGENT).
    """
    from datetime import date, timedelta

    import httpx

    from vitiligo.discovery import watch
    from vitiligo.discovery.forecasts import check_forecasts
    from vitiligo.sources.ctgov import CTGovClient

    start = date.fromisoformat(since) if since else date.today() - timedelta(days=days)
    studies: dict[str, Any] = {}
    with CTGovClient() as client:

        def fetch(nct_id: str) -> dict[str, Any] | None:
            studies[nct_id] = client.fetch_study(nct_id)
            return studies[nct_id]

        results = check_forecasts([Path(p) for p in (paths or ["forecasts"])], fetch)
    sealed = []
    for path, result in results:
        record = json.loads(path.read_text())
        sealed.append((_model_name(record), path, record, result))
    ranked = watch.rank_pending(sealed, studies)

    lines = [
        "## What pending results would tell us",
        "",
        "Mutual information between each result and which sealed model is right "
        "(maximum: log of the number of models).",
        "",
        "| Target | Models | Arm sizes | Information (nats) | P(true model gets 75%) |",
        "|---|---|---|---|---|",
    ]
    for t in ranked:
        trial, instrument, threshold, week, dose = t.key
        lines.append(
            f"| {trial} {instrument}{threshold} wk {week}, dose {dose:g} | {', '.join(t.models)} "
            f"| {t.n_active} / {t.n_control} ({t.sizes_from}) "
            f"| {t.mutual_information_nats:.2f} of {t.max_nats:.2f} | {t.p_true_model_gets_75pct:.2f} |"
        )
    if not ranked:
        lines.append("| none pending | | | | |")

    pending_trials = {t.key[0] for t in ranked}
    evidence_ranking = watch.ranked_trials(Path("forecasts/voi/ranking"))
    durability = watch.durability_trials(Path("forecasts/durability"))
    sources: list[tuple[str, Any]] = [
        ("Europe PMC", lambda: watch.europe_pmc(start)),
        ("ClinicalTrials.gov", lambda: watch.ctgov(start)),
        ("SEC filings", lambda: watch.sec_filings(start, get_settings().sec_user_agent)),
    ]
    report: dict[str, Any] = {"since": start.isoformat(), "ranked": [asdict(t) for t in ranked]}
    lines += ["", f"## New since {start.isoformat()}", ""]
    for name, run in sources:
        try:
            hits = run()
        except (httpx.HTTPError, ValueError) as exc:
            lines += [f"**{name}:** unavailable ({type(exc).__name__}).", ""]
            report[name] = {"error": str(exc)}
            continue
        if hits is None:
            lines += [f"**{name}:** skipped; set SEC_USER_AGENT to a contact name and email.", ""]
            report[name] = {"skipped": "SEC_USER_AGENT not set"}
            continue
        report[name] = [asdict(h) for h in hits]
        if not hits:
            lines += [f"**{name}:** nothing new.", ""]
            continue
        lines += [
            f"**{name}** ({len(hits)})",
            "",
            "| Date | Item | Agents | Note |",
            "|---|---|---|---|",
        ]
        for h in sorted(hits, key=lambda h: h.date, reverse=True):
            note = h.note
            if any(trial in h.title for trial in pending_trials):
                note = f"{note}; **sealed forecast pending**".lstrip("; ")
            if any(trial in h.title for trial in evidence_ranking):
                note = f"{note}; **in the evidence ranking**".lstrip("; ")
            if any(trial in h.title for trial in durability):
                note = f"{note}; **durability forecast pending**".lstrip("; ")
            title = h.title.replace("|", "/")
            lines.append(
                f"| {h.date} | [{title}]({h.url}) | {', '.join(h.agents) or '-'} | {note} |"
            )
        lines.append("")
    lines.append("Every item is a lead to read, not a curated result.")
    console.print("\n".join(lines))
    if json_out:
        Path(json_out).write_text(json.dumps(report, indent=2, default=str) + "\n")
    if markdown_out:
        with open(markdown_out, "a") as fh:
            fh.write("\n".join(lines) + "\n")


@discover_app.command("resolve")
def discover_resolve_cmd() -> None:
    """Score pending forecasts whose results are now posted (run after a corpus refresh)."""
    from vitiligo.discovery.forecasts import resolve

    init_db()
    rows = harmonize_arms(build_jak_atlas())
    for result in resolve(_ledger(), rows):
        status = "[green]resolved[/green]" if result.resolved else "[dim]pending[/dim]"
        console.print(f"{status} {result.label}: {result.detail}")


@app.command("serve")
def serve_cmd(
    host: str = typer.Option(None, "--host", help="Override bind host."),
    port: int = typer.Option(None, "--port", help="Override bind port."),
    reload: bool = typer.Option(False, "--reload", help="Auto-reload on code changes (dev only)."),
) -> None:
    """Run the Evidence Engine web UI."""
    settings = get_settings()
    bind_host = host or settings.effective_web_host
    bind_port = port or settings.effective_web_port

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
