"""Zotero → Second Brain sync (read-only).

Zotero stays the source of truth for bibliographic metadata and PDFs. This
module reads items from Zotero and registers them like ``sb add`` does:

* metadata (authors, year, venue, DOI, citekey, Zotero key) comes from Zotero,
  so the agent never has to guess it from parsed text;
* the PDF attachment is copied into ``raw/`` and parsed with page markers;
* items without a PDF are registered as metadata-only (``needs_text``) and get
  their text automatically on a later sync once a PDF is attached in Zotero;
* re-running the sync is safe: items are matched by Zotero key, then DOI/title;
* the user's PDF highlights and notes are written to
  ``structured/<id>.annotations.md``; if they change after the agent compiled
  the source, it shows up in ``sb pending`` again.

Two backends, same JSON format (Zotero Web API v3):

* ``local`` — Zotero desktop's local API at ``http://localhost:23119/api``
  (Settings → Advanced → "Allow other applications on this computer to
  communicate with Zotero"). No key, works offline, reads PDFs from disk.
* ``web`` — ``https://api.zotero.org`` with an API key (``ZOTERO_API_KEY``)
  and numeric user ID (``ZOTERO_USER_ID``). PDFs are downloaded only if they
  were synced to Zotero storage.

Nothing is ever written back to Zotero.
"""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from urllib.request import url2pathname

from .agents import IngestionAgent
from .config import StoreConfig
from .models import SOURCE_TYPE_TO_EVIDENCE, EvidenceLevel, Source, SourceType
from .store import SourceRepository

LOCAL_BASE = "http://localhost:23119/api"
WEB_BASE = "https://api.zotero.org"

# Zotero item types we register, mapped to our source types (spec §3.1).
ITEM_TYPES: dict[str, SourceType] = {
    "journalArticle": SourceType.JOURNAL_ARTICLE,
    "conferencePaper": SourceType.CONFERENCE_PAPER,
    "preprint": SourceType.PREPRINT,
    "report": SourceType.RESEARCH_INSTITUTE_REPORT,
    "thesis": SourceType.OTHER,
    "book": SourceType.OTHER,
    "bookSection": SourceType.OTHER,
    "newspaperArticle": SourceType.NEWS,
    "magazineArticle": SourceType.NEWS,
    "webpage": SourceType.WEBPAGE,
    "blogPost": SourceType.BLOG,
    "patent": SourceType.PATENT,
    "dataset": SourceType.DATASET,
    "presentation": SourceType.PRESENTATION,
    "document": SourceType.OTHER,
    "manuscript": SourceType.OTHER,
}
SKIP_TYPES = {"attachment", "note", "annotation"}


class ZoteroError(RuntimeError):
    pass


Fetch = Callable[[str], tuple[bytes, dict[str, str]]]


def _http_fetch(headers: dict[str, str]) -> Fetch:
    def fetch(url: str) -> tuple[bytes, dict[str, str]]:
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 - fixed hosts
                return resp.read(), {k.lower(): v for k, v in resp.headers.items()}
        except urllib.error.HTTPError as exc:
            if exc.code == 403 and url.startswith(LOCAL_BASE):
                raise ZoteroError(
                    "Zotero local API is disabled. Enable Settings → Advanced → "
                    "'Allow other applications on this computer to communicate with Zotero'."
                ) from exc
            raise ZoteroError(f"HTTP {exc.code} for {url}") from exc
        except urllib.error.URLError as exc:
            raise ZoteroError(
                f"cannot reach {url.split('/api')[0]} — is Zotero running? ({exc.reason})"
            ) from exc

    return fetch


@dataclass
class ZoteroClient:
    """Minimal read-only Zotero API v3 client (local or web)."""

    base: str  # e.g. http://localhost:23119/api/users/0
    fetch: Fetch
    local: bool
    page_size: int = 100

    @classmethod
    def connect(
        cls,
        mode: str = "local",
        user_id: str | None = None,
        api_key: str | None = None,
        group_id: str | None = None,
    ) -> ZoteroClient:
        headers = {"Zotero-API-Version": "3"}
        if mode == "local":
            lib = f"groups/{group_id}" if group_id else "users/0"
            return cls(f"{LOCAL_BASE}/{lib}", _http_fetch(headers), local=True)
        if mode == "web":
            if not api_key or not (user_id or group_id):
                raise ZoteroError("web mode needs ZOTERO_API_KEY and ZOTERO_USER_ID (or --group)")
            headers["Zotero-API-Key"] = api_key
            lib = f"groups/{group_id}" if group_id else f"users/{user_id}"
            return cls(f"{WEB_BASE}/{lib}", _http_fetch(headers), local=False)
        raise ZoteroError("mode must be 'local' or 'web'")

    def _get_json(self, path: str, params: dict | None = None) -> list | dict:
        query = urllib.parse.urlencode({"format": "json", **(params or {})})
        body, _ = self.fetch(f"{self.base}/{path}?{query}")
        return json.loads(body.decode("utf-8"))

    def _paged(self, path: str, params: dict | None = None) -> Iterator[dict]:
        start = 0
        while True:
            batch = self._get_json(
                path, {**(params or {}), "limit": self.page_size, "start": start}
            )
            if not isinstance(batch, list):
                raise ZoteroError(f"unexpected response for {path}")
            yield from batch
            if len(batch) < self.page_size:
                return
            start += self.page_size

    def collections(self) -> list[dict]:
        return list(self._paged("collections"))

    def resolve_collection(self, name_or_key: str) -> str:
        cols = self.collections()
        for c in cols:
            if c["key"] == name_or_key:
                return c["key"]
        matches = [
            c for c in cols if c["data"]["name"].strip().lower() == name_or_key.strip().lower()
        ]
        if len(matches) == 1:
            return matches[0]["key"]
        if not matches:
            raise ZoteroError(f"collection not found: {name_or_key}")
        raise ZoteroError(f"several collections named {name_or_key!r}; pass the key instead")

    def top_items(self, collection: str | None = None, tag: str | None = None) -> Iterator[dict]:
        path = f"collections/{collection}/items/top" if collection else "items/top"
        params = {"tag": tag} if tag else {}
        yield from self._paged(path, params)

    def children(self, item_key: str) -> list[dict]:
        return list(self._paged(f"items/{item_key}/children"))

    def pdf_path(self, attachment: dict, workdir: Path) -> Path | None:
        """Local file path of a PDF attachment (downloads it in web mode)."""
        key = attachment["key"]
        data = attachment["data"]
        if self.local:
            if data.get("linkMode") == "linked_file" and data.get("path"):
                p = Path(data["path"]).expanduser()
                return p if p.is_file() else None
            try:
                body, _ = self.fetch(f"{self.base}/items/{key}/file/view/url")
            except ZoteroError:
                return None
            url = body.decode("utf-8").strip()
            if not url.startswith("file:"):
                return None
            p = Path(url2pathname(urllib.parse.urlparse(url).path))
            return p if p.is_file() else None
        if data.get("linkMode") not in ("imported_file", "imported_url"):
            return None  # linked files and links are not stored on zotero.org
        try:
            body, _ = self.fetch(f"{self.base}/items/{key}/file")
        except ZoteroError:
            return None
        out = workdir / f"{key}.pdf"
        out.write_bytes(body)
        return out


# --- metadata mapping --------------------------------------------------------

_CITEKEY_RE = re.compile(r"^\s*Citation Key:\s*(\S+)", re.IGNORECASE | re.MULTILINE)
_YEAR_RE = re.compile(r"\b(1[5-9]\d\d|20\d\d)\b")


def _creator_name(c: dict) -> str:
    if c.get("name"):
        return c["name"].strip()
    last, first = (c.get("lastName") or "").strip(), (c.get("firstName") or "").strip()
    if re.search(r"[가-힣]", last + first):  # Korean names: family name first, no space
        return f"{last}{first}"
    return f"{last}, {first}".strip(", ")


def item_metadata(item: dict) -> dict:
    """Map a Zotero item JSON object to :class:`Source` fields."""
    d = item["data"]
    creators = d.get("creators") or []
    authors = [
        _creator_name(c)
        for c in creators
        if c.get("creatorType") in ("author", "inventor", "presenter")
    ]
    if not authors:
        authors = [_creator_name(c) for c in creators]
    year_m = _YEAR_RE.search(d.get("date") or "")
    venue = (
        d.get("publicationTitle")
        or d.get("proceedingsTitle")
        or d.get("conferenceName")
        or d.get("bookTitle")
        or d.get("websiteTitle")
        or d.get("blogTitle")
        or d.get("repository")
        or d.get("institution")
        or d.get("university")
        or None
    )
    citekey = d.get("citationKey") or None
    if not citekey:
        m = _CITEKEY_RE.search(d.get("extra") or "")
        citekey = m.group(1) if m else None
    stype = ITEM_TYPES.get(d.get("itemType", ""), SourceType.OTHER)
    library = item.get("library") or {}
    if library.get("type") == "group":
        uri = f"zotero://select/groups/{library.get('id')}/items/{item['key']}"
    else:
        uri = f"zotero://select/library/items/{item['key']}"
    return {
        "source_type": stype,
        "title": (d.get("title") or "").strip() or None,
        "author": authors,
        "year": int(year_m.group(1)) if year_m else None,
        "publication": venue,
        "organization": d.get("institution") or d.get("publisher") or None,
        "doi": (d.get("DOI") or "").strip() or _doi_from_extra(d.get("extra")),
        "url": (d.get("url") or "").strip() or None,
        "language": (d.get("language") or "").strip() or None,
        "keywords": [t["tag"] for t in d.get("tags") or [] if t.get("tag")],
        "zotero_key": item["key"],
        "zotero_uri": uri,
        "citekey": citekey,
        "evidence_level": SOURCE_TYPE_TO_EVIDENCE.get(stype, EvidenceLevel.UNKNOWN),
        "peer_reviewed": True if stype == SourceType.JOURNAL_ARTICLE else None,
    }


def _doi_from_extra(extra: str | None) -> str | None:
    m = re.search(r"^\s*DOI:\s*(\S+)", extra or "", re.IGNORECASE | re.MULTILINE)
    return m.group(1) if m else None


def _pick_pdf(children: list[dict]) -> dict | None:
    pdfs = [
        c
        for c in children
        if c["data"].get("itemType") == "attachment"
        and c["data"].get("contentType") == "application/pdf"
    ]
    # Prefer stored files over links.
    pdfs.sort(key=lambda c: c["data"].get("linkMode") not in ("imported_file", "imported_url"))
    return pdfs[0] if pdfs else None


# --- sync --------------------------------------------------------------------


@dataclass
class SyncReport:
    added: list[Source] = field(default_factory=list)
    metadata_only: list[Source] = field(default_factory=list)
    text_attached: list[Source] = field(default_factory=list)
    linked: list[Source] = field(default_factory=list)  # existing source matched by DOI/title
    unchanged: int = 0
    skipped: list[tuple[str, str]] = field(default_factory=list)  # (title, reason)
    annotations_updated: list[Source] = field(default_factory=list)


def sync(
    store: StoreConfig,
    client: ZoteroClient,
    collection: str | None = None,
    tag: str | None = None,
    dry_run: bool = False,
    annotations: bool = True,
) -> SyncReport:
    report = SyncReport()
    repo = SourceRepository(store)
    agent = IngestionAgent(store)
    col_key = client.resolve_collection(collection) if collection else None

    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        for item in client.top_items(col_key, tag):
            itype = item["data"].get("itemType", "")
            title = item["data"].get("title") or item["key"]
            if itype in SKIP_TYPES:
                continue
            meta = item_metadata(item)
            existing = next((s for s in repo.all() if s.zotero_key == item["key"]), None)
            if existing is None:
                existing = repo.find_duplicate(Source(source_id="_probe", **meta))

            if dry_run:
                if existing is None:
                    report.added.append(Source(source_id="(dry-run)", **meta))
                else:
                    report.unchanged += 1
                continue

            pdf = _pick_pdf(client.children(item["key"]))
            source: Source | None = None

            if existing is not None and existing.local_file:
                source = existing
                if existing.zotero_key is None:
                    _link(repo, existing, meta)
                    report.linked.append(existing)
                else:
                    report.unchanged += 1
            else:
                path = client.pdf_path(pdf, workdir) if pdf else None
                if existing is not None:  # metadata-only before; maybe the PDF arrived now
                    source = existing
                    if existing.zotero_key is None:
                        _link(repo, existing, meta)
                    if path:
                        source = agent.attach_file(existing, path)
                        report.text_attached.append(source)
                    else:
                        report.unchanged += 1
                elif path:
                    res = agent.ingest_file(
                        path,
                        source_type=meta["source_type"],
                        title=meta["title"] or title,
                        metadata=meta,
                    )
                    source = res.source
                    (report.linked if res.is_duplicate else report.added).append(source)
                    if res.is_duplicate and source.zotero_key is None:
                        _link(repo, source, meta)
                else:
                    res = agent.ingest_metadata_only(Source(source_id=f"src-{_new_id()}", **meta))
                    report.metadata_only.append(res.source)
                    reason = (
                        "no PDF attachment in Zotero"
                        if pdf is None
                        else "PDF attachment not available locally"
                    )
                    report.skipped.append((title, reason))

            if annotations and pdf is not None and source is not None and source.local_file:
                if _sync_annotations(store, repo, client, source, pdf):
                    report.annotations_updated.append(source)
    return report


# --- annotations (the user's own highlights and notes) ------------------------

ANNOTATION_TYPES = {"highlight", "underline", "note", "text", "image", "ink"}


def fetch_annotations(client: ZoteroClient, attachment_key: str) -> list[dict]:
    rows = [
        a["data"]
        for a in client.children(attachment_key)
        if a["data"].get("itemType") == "annotation"
        and a["data"].get("annotationType") in ANNOTATION_TYPES
    ]
    return sorted(rows, key=lambda a: a.get("annotationSortIndex") or "")


def _page_of(a: dict) -> str:
    label = (a.get("annotationPageLabel") or "").strip()
    if label:
        return label
    idx = (a.get("annotationSortIndex") or "").split("|")[0]
    return str(int(idx) + 1) if idx.isdigit() else "?"


def render_annotations(source: Source, rows: list[dict]) -> str:
    lines = [
        f"<!-- source_id: {source.source_id} | zotero: {source.zotero_key} | "
        f"annotations: {len(rows)} -->",
        "<!-- 사용자가 Zotero에서 직접 남긴 하이라이트와 메모입니다. sb zotero sync가 덮어씁니다. "
        "하이라이트 문구는 원문 인용, '내 메모'는 사용자의 의견(personal_note)입니다. -->",
        "",
    ]
    for i, a in enumerate(rows, 1):
        kind = a.get("annotationType")
        color = a.get("annotationColor") or ""
        tags = [t["tag"] for t in a.get("tags") or [] if t.get("tag")]
        head = f"## A{i} · p.{_page_of(a)} · {kind}"
        if color:
            head += f" · {color}"
        lines.append(head)
        text = " ".join((a.get("annotationText") or "").split())
        if text:
            lines.append(f'> "{text}"')
        comment = (a.get("annotationComment") or "").strip()
        if comment:
            lines.append(f"- 내 메모: {comment}")
        if tags:
            lines.append(f"- 태그: {', '.join(tags)}")
        if kind in ("image", "ink") and not text:
            lines.append("- (그림/필기 주석 — 내용은 Zotero에서 확인)")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _sync_annotations(
    store: StoreConfig, repo: SourceRepository, client: ZoteroClient, source: Source, pdf: dict
) -> bool:
    """Write structured/<id>.annotations.md. Returns True if the content changed."""
    rows = fetch_annotations(client, pdf["key"])
    if not rows and not source.annotations_file:
        return False
    text = render_annotations(source, rows)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    if digest == source.annotations_hash:
        return False
    out = store.structured / f"{source.source_id}.annotations.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    source.annotations_file = str(out.relative_to(store.root))
    source.annotation_count = len(rows)
    source.annotations_hash = digest
    repo.save(source)
    return True


def _link(repo: SourceRepository, source: Source, meta: dict) -> None:
    """Attach Zotero identity/metadata to a source registered some other way."""
    for key in ("zotero_key", "zotero_uri", "citekey"):
        setattr(source, key, meta.get(key))
    for key in ("author", "year", "publication", "doi", "url"):
        if not getattr(source, key) and meta.get(key):
            setattr(source, key, meta[key])
    repo.save(source)


def _new_id() -> str:
    import uuid

    return uuid.uuid4().hex[:12]
