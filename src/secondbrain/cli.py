"""Command-line interface for the Research Second Brain (`sb`).

Phase 1 commands:

* ``sb ingest <file>``   -- run the full ingest pipeline on a file.
* ``sb ingest-dir <d>``  -- ingest every supported file in a folder (spec §31).
* ``sb sources``         -- list registered sources.
* ``sb wiki``            -- list wiki pages.
* ``sb show <path>``     -- print a wiki page.
* ``sb search <query>``  -- keyword search the wiki (spec §25).
* ``sb digest``          -- print the knowledge-base digest (spec §27).
* ``sb project add ...`` -- register a personal research project (spec §29).
* ``sb init``            -- create an empty store.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .config import resolve_store
from .digest import build_digest
from .models import ResearchProject, SourceType
from .pipeline import IngestPipeline
from .search import keyword_search
from .store import ProjectRepository, SourceRepository

app = typer.Typer(help="Research Second Brain CLI", no_args_is_help=True)
project_app = typer.Typer(help="Manage personal research projects (spec §29).")
app.add_typer(project_app, name="project")
console = Console()

_SUPPORTED = {".pdf", ".txt", ".md", ".html", ".htm", ".docx", ".pptx", ".xlsx"}


def _store(store: str | None):
    st = resolve_store(store)
    st.ensure()
    return st


@app.command()
def init(store: str | None = typer.Option(None, help="Store root path.")) -> None:
    """Create an empty knowledge store."""
    st = _store(store)
    console.print(f"[green]Store ready at[/green] {st.root}")


@app.command()
def ingest(
    file: Path = typer.Argument(..., exists=True, readable=True),
    store: str | None = typer.Option(None),
    source_type: str | None = typer.Option(None, help="Override source type."),
    title: str | None = typer.Option(None),
) -> None:
    """Ingest a single file through the full pipeline."""
    st = _store(store)
    stype = SourceType(source_type) if source_type else None
    result = IngestPipeline(st).run(file, source_type=stype, title=title)
    if result.was_duplicate:
        console.print(f"[yellow]Duplicate[/yellow] of existing source {result.source.source_id}")
        return
    u = result.wiki_update
    console.print(
        f"[green]Ingested[/green] {result.source.source_id} "
        f"({result.source.source_type.value})"
    )
    console.print(f"  paper page: {u.paper_page}")
    if u.created_pages:
        console.print(f"  created: {', '.join(u.created_pages)}")
    if u.updated_pages:
        console.print(f"  updated: {', '.join(u.updated_pages)}")
    if u.concepts_touched:
        console.print(f"  concepts: {', '.join(u.concepts_touched)}")
    if u.theories_touched:
        console.print(f"  theories: {', '.join(u.theories_touched)}")
    if u.methods_touched:
        console.print(f"  methods: {', '.join(u.methods_touched)}")
    if u.open_questions:
        console.print(f"  open questions: {len(u.open_questions)}")


@app.command("ingest-dir")
def ingest_dir(
    directory: Path = typer.Argument(..., exists=True, file_okay=False),
    store: str | None = typer.Option(None),
) -> None:
    """Ingest every supported file in a folder (folder watcher target, spec §31)."""
    st = _store(store)
    pipeline = IngestPipeline(st)
    n_new = n_dup = 0
    for path in sorted(directory.rglob("*")):
        if path.suffix.lower() not in _SUPPORTED or not path.is_file():
            continue
        res = pipeline.run(path)
        if res.was_duplicate:
            n_dup += 1
        else:
            n_new += 1
            console.print(f"  + {path.name} -> {res.source.source_id}")
    console.print(f"[green]Done.[/green] {n_new} new, {n_dup} duplicates.")


@app.command()
def sources(store: str | None = typer.Option(None)) -> None:
    """List all registered sources."""
    st = _store(store)
    items = SourceRepository(st).all()
    table = Table(title=f"Sources ({len(items)})")
    for col in ("source_id", "type", "title", "evidence", "access"):
        table.add_column(col)
    for s in items:
        table.add_row(
            s.source_id,
            s.source_type.value,
            (s.title or "")[:50],
            s.evidence_level.value,
            s.access_status.value,
        )
    console.print(table)


@app.command()
def wiki(store: str | None = typer.Option(None)) -> None:
    """List all wiki pages grouped by type."""
    st = _store(store)
    table = Table(title="Wiki pages")
    table.add_column("type")
    table.add_column("page")
    for path in sorted(st.wiki.rglob("*.md")):
        table.add_row(path.parent.name, path.stem)
    console.print(table)


@app.command()
def show(
    page: str = typer.Argument(..., help="Relative path under the store, e.g. wiki/papers/foo.md"),
    store: str | None = typer.Option(None),
) -> None:
    """Print a wiki page."""
    st = _store(store)
    path = st.root / page
    if not path.exists():
        console.print(f"[red]Not found:[/red] {path}")
        raise typer.Exit(1)
    console.print(path.read_text(encoding="utf-8"))


@app.command()
def search(
    query: str = typer.Argument(...),
    store: str | None = typer.Option(None),
    limit: int = typer.Option(10),
) -> None:
    """Keyword search across the wiki (spec §25)."""
    st = _store(store)
    hits = keyword_search(st, query, limit=limit)
    if not hits:
        console.print("[yellow]No matches.[/yellow]")
        return
    table = Table(title=f"Search: {query}")
    for col in ("score", "title", "path"):
        table.add_column(col)
    for h in hits:
        table.add_row(str(h.score), h.title[:50], h.path)
    console.print(table)


@app.command()
def digest(store: str | None = typer.Option(None)) -> None:
    """Print a digest of the current knowledge base (spec §27)."""
    st = _store(store)
    console.print(build_digest(st).render())


@project_app.command("add")
def project_add(
    title: str = typer.Argument(...),
    research_question: str | None = typer.Option(None, "--rq"),
    keywords: str | None = typer.Option(None, help="Comma-separated."),
    store: str | None = typer.Option(None),
) -> None:
    """Register a personal research project used to personalize idea generation."""
    st = _store(store)
    proj = ResearchProject(
        title=title,
        research_question=research_question,
        keywords=[k.strip() for k in (keywords or "").split(",") if k.strip()],
    )
    ProjectRepository(st).save(proj)
    console.print(f"[green]Saved project[/green] {proj.project_id}: {proj.title}")


@project_app.command("list")
def project_list(store: str | None = typer.Option(None)) -> None:
    st = _store(store)
    for p in ProjectRepository(st).all():
        console.print(f"- {p.project_id}: {p.title}")


if __name__ == "__main__":
    app()
