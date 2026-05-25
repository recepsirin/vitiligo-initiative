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
from vitiligo.ingest import run_pubmed_ingestion
from vitiligo.logging import configure_logging, get_logger
from vitiligo.sources.pubmed import DEFAULT_VITILIGO_QUERY
from vitiligo.storage import Document, IngestionRun, SourceKind, init_db, session_scope

app = typer.Typer(
    add_completion=False,
    help="Vitiligo Initiative engine — ingestion, search, and (soon) reasoning.",
    no_args_is_help=True,
)
ingest_app = typer.Typer(help="Ingest documents from external sources.", no_args_is_help=True)
db_app = typer.Typer(help="Inspect the local document store.", no_args_is_help=True)
app.add_typer(ingest_app, name="ingest")
app.add_typer(db_app, name="db")

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


@ingest_app.command("pubmed")
def ingest_pubmed(
    query: str = typer.Option(
        DEFAULT_VITILIGO_QUERY,
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
    table = Table(show_header=False, box=None)
    table.add_row("Source", str(stats.source.value))
    table.add_row("Total found", str(stats.total_found))
    table.add_row("Fetched", str(stats.fetched))
    table.add_row("Inserted", str(stats.inserted))
    table.add_row("Updated", str(stats.updated))
    table.add_row("Run id", str(stats.run_id))
    console.print(table)


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
            runs_table.add_row(
                str(run.id),
                run.source.value,
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


if __name__ == "__main__":
    app()
