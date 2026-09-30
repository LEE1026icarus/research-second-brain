"""`sb` — deterministic tools for the LLM agent that maintains the wiki.

The agent (Kiro, Claude Code, Codex, …) does the reading and writing by
following ``AGENTS.md``. These commands do the parts that must be exact:

* ``sb add <file>``       register a source: keep raw, dedup, parse text with page markers
* ``sb add-dir <dir>``    register every supported file in a folder (inbox)
* ``sb pending``          sources waiting for the agent
* ``sb done <id> ...``    mark a source compiled and append a log entry
* ``sb index``            regenerate index.md from page frontmatter
* ``sb lint``             check links, citations, orphans, idea leakage
* ``sb verify``           check quotes/numbers against the cited source pages
* ``sb log ...``          append an entry to log.md
* ``sb search <q>``       keyword search over wiki + ideas
* ``sb status``           counts and review queue
* ``sb digest``           what changed this week (from log.md)
* ``sb refs``             citations from OpenAlex → reading suggestions
* ``sb graph``            knowledge graph + Synapse candidates for the agent
* ``sb discover``         new papers citing my library / matching my projects
* ``sb project add/list`` personal research context (spec §29)
* ``sb zotero sync``      import papers (metadata + PDF) from Zotero
"""

from __future__ import annotations

import json
import os
from collections import Counter
from datetime import date
from pathlib import Path

import typer
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from . import digest as digest_mod
from . import discover as discover_mod
from . import kg as kg_mod
from . import openalex as oa_mod
from . import vault
from . import verify as verify_mod
from . import zotero as zot
from .agents import IngestionAgent
from .config import resolve_store
from .models import CompileStatus, ResearchProject, SourceType
from .parsing import supported_suffixes
from .store import ProjectRepository, SourceRepository

app = typer.Typer(help="Research Second Brain — tools for the LLM wiki agent", no_args_is_help=True)
project_app = typer.Typer(help="Manage personal research projects (spec §29).")
app.add_typer(project_app, name="project")
zotero_app = typer.Typer(help="Import papers from Zotero (read-only).")
app.add_typer(zotero_app, name="zotero")
console = Console()

StoreOpt = typer.Option(
    None, "--store", help="Store (vault) root. Default: $SECOND_BRAIN_STORE or ./store"
)


def _store(store: str | None):
    st = resolve_store(store)
    st.ensure()
    return st


def _register(st, path: Path, source_type: str | None, title: str | None) -> None:
    stype = SourceType(source_type) if source_type else None
    res = IngestionAgent(st).ingest_file(path, source_type=stype, title=title)
    s = res.source
    if res.is_duplicate:
        console.print(
            f"[yellow]duplicate[/yellow] {path.name} → existing {s.source_id} ({s.status.value})"
        )
        return
    vault.append_log(
        st,
        "register",
        s.title or s.source_id,
        [
            f"source: `{s.source_id}` ({s.source_type.value}, {s.evidence_level.value})",
            f"raw: `{s.local_file}`",
            f"text: `{s.text_file}` ({s.pages or 0} pages)"
            if s.text_file
            else "text: none — needs OCR/parser",
        ],
    )
    console.print(f"[green]registered[/green] {s.source_id}  {path.name}")
    if s.status == CompileStatus.NEEDS_TEXT:
        console.print("  [red]no text extracted[/red] (scanned PDF or unsupported format)")
    else:
        console.print(f"  text: {s.text_file}  ({s.pages} pages)")


@app.command()
def init(
    store: str | None = StoreOpt,
    update_dashboards: bool = typer.Option(
        False, "--update-dashboards", help="Overwrite dashboards with the latest templates"
    ),
) -> None:
    """Create an empty vault (folders, index.md, log.md, Dataview dashboards)."""
    st = _store(store)
    for path in vault.install_dashboards(st, overwrite=update_dashboards):
        console.print(f"dashboard: {path.relative_to(st.root)}")
    vault.write_index(st)
    if not st.log_md.exists():
        vault.append_log(st, "note", "vault initialized")
    console.print(f"[green]vault ready[/green] {st.root}  (open this folder in Obsidian)")


@app.command()
def add(
    file: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    source_type: str | None = typer.Option(
        None, "--type", help="e.g. journal_article, news, government_report"
    ),
    title: str | None = typer.Option(None),
    store: str | None = StoreOpt,
) -> None:
    """Register one source for the agent to ingest."""
    _register(_store(store), file, source_type, title)


@app.command("add-dir")
def add_dir(
    directory: Path = typer.Argument(..., exists=True, file_okay=False),
    source_type: str | None = typer.Option(None, "--type"),
    store: str | None = StoreOpt,
) -> None:
    """Register every supported file in a folder (e.g. inbox/)."""
    st = _store(store)
    files = [
        p
        for p in sorted(directory.rglob("*"))
        if p.is_file() and p.suffix.lower() in supported_suffixes()
    ]
    for p in files:
        _register(st, p, source_type, None)
    console.print(f"{len(files)} file(s) processed")


def _pending_reason(s) -> str:
    if s.annotations_changed:
        return "annotations-updated"  # already compiled; re-read the user's highlights/notes
    return s.status.value


@app.command()
def pending(store: str | None = StoreOpt, as_json: bool = typer.Option(False, "--json")) -> None:
    """List sources the agent has not integrated yet."""
    st = _store(store)
    items = [
        s
        for s in SourceRepository(st).all()
        if s.status in (CompileStatus.PENDING, CompileStatus.NEEDS_TEXT) or s.annotations_changed
    ]
    if as_json:
        print(
            json.dumps(
                [
                    {
                        "source_id": s.source_id,
                        "title": s.title,
                        "authors": s.author,
                        "year": s.year,
                        "venue": s.publication,
                        "doi": s.doi,
                        "url": s.url,
                        "citekey": s.citekey,
                        "zotero_key": s.zotero_key,
                        "zotero_uri": s.zotero_uri,
                        "annotations_file": s.annotations_file,
                        "annotation_count": s.annotation_count,
                        "reason": _pending_reason(s),
                        "type": s.source_type.value,
                        "evidence_level": s.evidence_level.value,
                        "status": s.status.value,
                        "text_file": s.text_file,
                        "raw": s.local_file,
                        "pages": s.pages,
                    }
                    for s in items
                ],
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    if not items:
        console.print("nothing pending")
        return
    table = Table(title=f"Pending ({len(items)})")
    for col in ("source_id", "reason", "type", "title", "text_file"):
        table.add_column(col)
    for s in items:
        table.add_row(
            s.source_id,
            _pending_reason(s),
            s.source_type.value,
            (s.title or "")[:40],
            s.text_file or "-",
        )
    console.print(table)


@app.command()
def done(
    source_id: str = typer.Argument(...),
    page: str = typer.Option(
        ..., "--page", help="Source page the agent wrote, e.g. wiki/papers/foo"
    ),
    touched: list[str] = typer.Option(
        [], "--touched", help="Other pages created/updated (repeatable)"
    ),
    effect: list[str] = typer.Option(
        [], "--effect", help='"wiki/concepts/x: strengthen — reason" (repeatable)'
    ),
    note: str | None = typer.Option(None),
    store: str | None = StoreOpt,
) -> None:
    """Mark a source as compiled and log what changed (spec §22)."""
    st = _store(store)
    try:
        vault.mark_compiled(st, source_id, page, touched, effect, note)
    except (KeyError, FileNotFoundError) as exc:
        console.print(f"[red]error[/red] {exc}")
        raise typer.Exit(1) from exc
    vault.write_index(st)
    console.print(
        f"[green]compiled[/green] {source_id} → {page}  (index.md updated, log.md appended)"
    )


@app.command()
def index(store: str | None = StoreOpt) -> None:
    """Regenerate index.md from page frontmatter."""
    path = vault.write_index(_store(store))
    console.print(f"[green]wrote[/green] {path}")


@app.command("lint")
def lint_cmd(
    store: str | None = StoreOpt,
    as_json: bool = typer.Option(False, "--json"),
    log_result: bool = typer.Option(False, "--log", help="Append a summary to log.md"),
) -> None:
    """Deterministic health check. Exit code 1 if there are errors."""
    st = _store(store)
    report = vault.lint(st)
    if as_json:
        print(json.dumps([i.__dict__ for i in report.issues], ensure_ascii=False, indent=2))
    else:
        order = {"error": 0, "warn": 1, "info": 2}
        colors = {"error": "red", "warn": "yellow", "info": "cyan"}
        for i in sorted(report.issues, key=lambda x: (order[x.level], x.code, x.page)):
            console.print(
                f"[{colors[i.level]}]{i.level:5}[/] " + escape(f"{i.code:20} {i.page}  {i.detail}")
            )
        console.print(
            f"\nerrors {report.count('error')} · warnings {report.count('warn')} "
            f"· info {report.count('info')}"
        )
    if log_result:
        counts = Counter(i.code for i in report.issues)
        vault.append_log(
            st,
            "lint",
            f"{report.count('error')} errors, {report.count('warn')} warnings",
            [f"{k}: {v}" for k, v in sorted(counts.items())],
        )
    if report.count("error"):
        raise typer.Exit(1)


@app.command("verify")
def verify_cmd(
    page: str | None = typer.Option(None, "--page", help="Only this page, e.g. wiki/papers/x"),
    store: str | None = StoreOpt,
    as_json: bool = typer.Option(False, "--json"),
    log_result: bool = typer.Option(False, "--log", help="Append a summary to log.md"),
) -> None:
    """Check quoted text and numbers against the cited pages. Exit 1 on errors."""
    st = _store(store)
    rep = verify_mod.verify(st, only=page)
    if as_json:
        print(json.dumps([f.__dict__ for f in rep.findings], ensure_ascii=False, indent=2))
    else:
        order = {"error": 0, "warn": 1, "info": 2}
        colors = {"error": "red", "warn": "yellow", "info": "cyan"}
        for f in sorted(rep.findings, key=lambda x: (order[x.level], x.page, x.line)):
            console.print(
                f"[{colors[f.level]}]{f.level:5}[/] "
                + escape(f"{f.code:20} {f.page}:{f.line}  {f.detail}")
            )
        console.print(
            f"\ncitations {rep.citations} · quotes {rep.checked_quotes} · "
            f"numbers {rep.checked_numbers} · errors {rep.count('error')} · "
            f"warnings {rep.count('warn')}"
        )
    if log_result:
        counts = Counter(f.code for f in rep.findings)
        vault.append_log(
            st,
            "lint",
            f"verify: {rep.count('error')} errors, {rep.count('warn')} warnings",
            [f"{k}: {v}" for k, v in sorted(counts.items())],
        )
    if rep.count("error"):
        raise typer.Exit(1)


@app.command()
def log(
    kind: str = typer.Argument(..., help="query | idea | review | note"),
    title: str = typer.Argument(...),
    bullet: list[str] = typer.Option([], "--bullet", "-b"),
    store: str | None = StoreOpt,
) -> None:
    """Append an entry to log.md."""
    vault.append_log(_store(store), kind, title, bullet)


@app.command()
def search(query: str, store: str | None = StoreOpt, limit: int = 10) -> None:
    """Keyword search over wiki and ideas (spec §25)."""
    hits = vault.search(_store(store), query, limit)
    if not hits:
        console.print("no matches")
        return
    for h in hits:
        console.print(
            f"[bold]{h.score:3}[/bold] " + escape(f"[[{h.rel}]]  {h.title}\n     {h.snippet}")
        )


@app.command()
def digest(
    days: int = typer.Option(7, "--days", help="Period length in days (ending today)"),
    save: bool = typer.Option(False, "--save", help="Also write digests/<date>.md in the vault"),
    store: str | None = StoreOpt,
) -> None:
    """Summarize what changed in the wiki (spec §27)."""
    st = _store(store)
    d = digest_mod.build_digest(st, days=days)
    text = d.render()
    print(text)
    if save:
        out = st.root / "digests" / f"{d.end.isoformat()}.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        console.print(f"[green]wrote[/green] {out.relative_to(st.root)}")


def _openalex() -> oa_mod.OpenAlex:
    return oa_mod.OpenAlex(oa_mod.http_fetch(os.environ.get("OPENALEX_API_KEY")))


@app.command()
def refs(
    source: str | None = typer.Option(None, "--source", help="Only this source_id"),
    force: bool = typer.Option(False, "--force", help="Re-fetch even if cached"),
    limit: int = typer.Option(30, "--limit", help="Suggestions to show"),
    store: str | None = StoreOpt,
) -> None:
    """Fetch reference lists from OpenAlex; write reports/reading-suggestions.md."""
    st = _store(store)
    try:
        rep = oa_mod.refresh_refs(st, _openalex(), only=source, force=force)
    except oa_mod.OpenAlexError as exc:
        console.print(f"[red]error[/red] {exc}")
        raise typer.Exit(1) from exc
    out = st.root / "reports" / "reading-suggestions.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(oa_mod.render_reading_report(st, rep, limit), encoding="utf-8")
    console.print(
        f"updated {len(rep.fetched)} · suggestions {len(rep.suggestions)} · "
        f"links inside library {len(rep.internal)} · unresolved refs {rep.unresolved_refs}"
    )
    for msg in rep.search_errors:
        console.print("[yellow]OpenAlex title search unavailable[/yellow] " + escape(msg))
    for t in rep.no_references:
        console.print("[yellow]no reference list[/yellow] " + escape(t))
    for t in rep.not_found:
        console.print("[yellow]not in OpenAlex[/yellow] " + escape(t))
    for w in rep.suggestions[:10]:
        console.print(
            f"  {len(w['cited_by_mine'])}× "
            + escape(f"{w.get('title')} ({w.get('year')}) — cited {w.get('cited_by_count')}")
        )
    console.print(f"[green]wrote[/green] {out.relative_to(st.root)}")
    if rep.fetched:
        vault.append_log(
            st,
            "note",
            f"refs: {len(rep.fetched)} sources updated from OpenAlex",
            [f"suggestions: {len(rep.suggestions)}", f"internal citations: {len(rep.internal)}"],
        )


@app.command()
def graph(
    limit: int = typer.Option(15, "--limit", help="Candidates per kind in the report"),
    stale_years: int = typer.Option(5, "--stale-years", help="Temporal gap threshold"),
    store: str | None = StoreOpt,
) -> None:
    """Build kg/graph.json and reports/synapse-candidates.md (spec §10–13)."""
    st = _store(store)
    res = kg_mod.build(st, stale_years=stale_years)
    out = st.root / "reports" / "synapse-candidates.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(kg_mod.render_candidates(res, limit), encoding="utf-8")
    kinds = Counter(c.kind for c in res.candidates)
    console.print(
        f"nodes {res.nodes} · edges {res.edges} · claims {res.claims} "
        f"(relations {res.relations}) · candidates "
        + (", ".join(f"{k} {v}" for k, v in sorted(kinds.items())) or "0")
    )
    console.print(
        f"[green]wrote[/green] {st.graph_file.relative_to(st.root)}, {out.relative_to(st.root)}"
    )


@app.command()
def discover(
    days: int = typer.Option(90, "--days", help="Look back this many days"),
    per_seed: int = typer.Option(10, "--per-seed", help="Max results per seed paper/keyword"),
    include_seen: bool = typer.Option(False, "--all", help="Also show works shown before"),
    limit: int = typer.Option(40, "--limit"),
    store: str | None = StoreOpt,
) -> None:
    """Find new papers to read (OpenAlex). Writes reports/discover-<date>.md."""
    st = _store(store)
    try:
        res = discover_mod.discover(
            st, _openalex(), days=days, per_seed=per_seed, include_seen=include_seen
        )
    except oa_mod.OpenAlexError as exc:
        console.print(f"[red]error[/red] {exc}")
        raise typer.Exit(1) from exc
    out = st.root / "reports" / f"discover-{date.today().isoformat()}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(discover_mod.render(res, limit), encoding="utf-8")
    for msg in res.search_errors:
        console.print("[yellow]keyword search unavailable[/yellow] " + escape(msg))
    for h in res.hits[:10]:
        console.print(
            f"  {h.score:.0f} "
            + escape(f"{h.info.get('title')} ({h.info.get('publication_date')}) — {h.reasons[0]}")
        )
    console.print(
        f"seeds {res.seeds} · new candidates {len(res.hits)} · "
        f"skipped (already in library) {res.skipped_known}"
    )
    console.print(f"[green]wrote[/green] {out.relative_to(st.root)}")
    if not st.projects_file.exists():
        console.print(
            'tip: `sb project add "제목" --keywords ... --refs <DOI>` adds project-based alerts'
        )
    vault.append_log(
        st,
        "note",
        f"discover: {len(res.hits)} candidates since {res.since}",
        [f"report: `{out.relative_to(st.root)}`"],
    )


@app.command()
def status(store: str | None = StoreOpt) -> None:
    """Counts of sources and pages, plus the human review queue (spec §32)."""
    st = _store(store)
    sources = SourceRepository(st).all()
    pages = vault.load_pages(st)
    console.print(f"[bold]vault[/bold] {st.root}")
    console.print(
        "sources: "
        + ", ".join(f"{k} {v}" for k, v in Counter(s.status.value for s in sources).items())
        or "sources: 0"
    )
    console.print(
        "pages:   "
        + ", ".join(
            f"{k} {v}" for k, v in sorted(Counter(f"{p.area}/{p.folder}" for p in pages).items())
        )
    )
    review = [p for p in pages if p.frontmatter.get("review") == "pending"]
    if review:
        console.print(f"[yellow]review queue ({len(review)})[/yellow]")
        for p in review:
            console.print(escape(f"  - [[{p.rel}]] {p.frontmatter.get('review_reason', '')}"))


@project_app.command("add")
def project_add(
    title: str = typer.Argument(...),
    research_question: str | None = typer.Option(None, "--rq"),
    keywords: str | None = typer.Option(None, help="Comma-separated."),
    refs: str | None = typer.Option(None, "--refs", help="Key reference DOIs, comma-separated"),
    store: str | None = StoreOpt,
) -> None:
    """Register a personal research project used to prioritise ideas and alerts."""
    st = _store(store)
    proj = ResearchProject(
        title=title,
        research_question=research_question,
        keywords=[k.strip() for k in (keywords or "").split(",") if k.strip()],
        important_references=[r.strip() for r in (refs or "").split(",") if r.strip()],
    )
    ProjectRepository(st).save(proj)
    console.print(f"[green]saved project[/green] {proj.project_id}: {proj.title}")


@project_app.command("list")
def project_list(store: str | None = StoreOpt) -> None:
    for p in ProjectRepository(_store(store)).all():
        console.print(f"- {p.project_id}: {p.title}  (RQ: {p.research_question or '-'})")


ZoteroMode = typer.Option("local", "--mode", help="local (Zotero desktop) or web (api.zotero.org)")
ZoteroGroup = typer.Option(None, "--group", help="Group library ID (default: personal library)")


def _zotero_client(mode: str, group: str | None) -> zot.ZoteroClient:
    try:
        return zot.ZoteroClient.connect(
            mode,
            user_id=os.environ.get("ZOTERO_USER_ID"),
            api_key=os.environ.get("ZOTERO_API_KEY"),
            group_id=group,
        )
    except zot.ZoteroError as exc:
        console.print(f"[red]error[/red] {exc}")
        raise typer.Exit(1) from exc


@zotero_app.command("collections")
def zotero_collections(mode: str = ZoteroMode, group: str | None = ZoteroGroup) -> None:
    """List Zotero collections (name and key)."""
    client = _zotero_client(mode, group)
    try:
        cols = client.collections()
    except zot.ZoteroError as exc:
        console.print(f"[red]error[/red] {exc}")
        raise typer.Exit(1) from exc
    for c in sorted(cols, key=lambda c: c["data"]["name"]):
        n = c.get("meta", {}).get("numItems", "?")
        console.print(escape(f"{c['key']}  {c['data']['name']}  ({n} items)"))


@zotero_app.command("sync")
def zotero_sync(
    collection: str | None = typer.Option(
        None, "--collection", "-c", help="Collection name or key"
    ),
    tag: str | None = typer.Option(None, "--tag", "-t", help="Only items with this Zotero tag"),
    mode: str = ZoteroMode,
    group: str | None = ZoteroGroup,
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be imported"),
    no_annotations: bool = typer.Option(
        False, "--no-annotations", help="Skip importing PDF highlights and notes"
    ),
    store: str | None = StoreOpt,
) -> None:
    """Import Zotero items as sources (metadata + PDF + your highlights). Safe to re-run."""
    st = _store(store)
    client = _zotero_client(mode, group)
    try:
        rep = zot.sync(
            st,
            client,
            collection=collection,
            tag=tag,
            dry_run=dry_run,
            annotations=not no_annotations,
        )
    except zot.ZoteroError as exc:
        console.print(f"[red]error[/red] {exc}")
        raise typer.Exit(1) from exc
    label = "would add" if dry_run else "added"
    for s in rep.added:
        console.print(
            f"[green]{label}[/green] " + escape(f"{s.source_id}  {s.title}  ({s.year or 'n.d.'})")
        )
    for s in rep.text_attached:
        console.print("[green]PDF attached[/green] " + escape(f"{s.source_id}  {s.title}"))
    for s in rep.linked:
        console.print(
            "[cyan]linked[/cyan] " + escape(f"{s.source_id}  {s.title}  (already registered)")
        )
    for s in rep.annotations_updated:
        console.print(
            "[magenta]highlights[/magenta] "
            + escape(f"{s.source_id}  {s.title}  ({s.annotation_count} annotations)")
        )
    for title, reason in rep.skipped:
        console.print("[yellow]metadata only[/yellow] " + escape(f"{title} — {reason}"))
    console.print(
        f"\n{label} {len(rep.added)} · PDF attached {len(rep.text_attached)} · "
        f"linked {len(rep.linked)} · metadata only {len(rep.metadata_only)} · "
        f"unchanged {rep.unchanged} · highlights updated {len(rep.annotations_updated)}"
    )
    changed = (
        rep.added or rep.text_attached or rep.linked or rep.metadata_only or rep.annotations_updated
    )
    if not dry_run and changed:
        bullets = [f"added: `{s.source_id}` {s.title}" for s in rep.added]
        bullets += [f"pdf attached: `{s.source_id}` {s.title}" for s in rep.text_attached]
        bullets += [f"linked: `{s.source_id}` {s.title}" for s in rep.linked]
        bullets += [f"metadata only: `{s.source_id}` {s.title}" for s in rep.metadata_only]
        bullets += [
            f"highlights: `{s.source_id}` {s.title} ({s.annotation_count})"
            for s in rep.annotations_updated
        ]
        where = f"collection {collection}" if collection else "library"
        if tag:
            where += f", tag {tag}"
        vault.append_log(st, "register", f"zotero sync ({where})", bullets)
        console.print("next: ask the agent to ingest pending sources (`sb pending`)")


if __name__ == "__main__":
    app()
