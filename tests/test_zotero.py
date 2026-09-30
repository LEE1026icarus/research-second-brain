"""Zotero sync against a fake Zotero API (local-API URL scheme and JSON format)."""

from __future__ import annotations

import json
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from secondbrain import zotero as zot
from secondbrain.agents import IngestionAgent
from secondbrain.models import CompileStatus, SourceType
from secondbrain.store import SourceRepository

BASE = "http://localhost:23119/api/users/0"


def _item(key, title, *, itype="journalArticle", doi="", creators=None, extra="", date="2020-05"):
    return {
        "key": key,
        "library": {"type": "user", "id": 1},
        "data": {
            "key": key,
            "itemType": itype,
            "title": title,
            "creators": creators
            or [
                {"creatorType": "author", "lastName": "최", "firstName": "윤진"},
                {"creatorType": "author", "lastName": "Kim", "firstName": "Hee-Woong"},
                {"creatorType": "editor", "lastName": "Editor", "firstName": "X"},
            ],
            "date": date,
            "DOI": doi,
            "publicationTitle": "Korea Business Review",
            "extra": extra,
            "tags": [{"tag": "tourism"}],
        },
    }


def _pdf_attachment(key, parent):
    return {
        "key": key,
        "data": {
            "key": key,
            "itemType": "attachment",
            "parentItem": parent,
            "contentType": "application/pdf",
            "linkMode": "imported_file",
            "filename": f"{key}.pdf",
        },
    }


class FakeZotero:
    """Serves the subset of the Zotero API that sync() uses."""

    def __init__(self, tmp: Path):
        self.tmp = tmp
        self.items: list[dict] = []
        self.children: dict[str, list[dict]] = {}
        self.files: dict[str, Path] = {}
        self.collections = [{"key": "COL1", "data": {"name": "Tourism"}, "meta": {"numItems": 2}}]
        self.collection_members = {"COL1": set()}

    def add(self, item, pdf_text: str | None = None, collection: str | None = None):
        self.items.append(item)
        if collection:
            self.collection_members[collection].add(item["key"])
        if pdf_text is not None:
            self.attach(item["key"], pdf_text)

    def attach(self, parent: str, text: str):
        att = _pdf_attachment(f"A{parent}", parent)
        path = self.tmp / f"zotero-storage-{parent}.txt"  # parse as text (no real PDF in tests)
        path.write_text(text, encoding="utf-8")
        self.children.setdefault(parent, []).append(att)
        self.files[att["key"]] = path

    def fetch(self, url: str):
        parsed = urllib.parse.urlparse(url)
        path = parsed.path.removeprefix("/api/users/0/")
        q = urllib.parse.parse_qs(parsed.query)
        start, limit = int(q.get("start", ["0"])[0]), int(q.get("limit", ["100"])[0])

        def page(rows):
            return json.dumps(rows[start : start + limit]).encode(), {}

        if path == "collections":
            return page(self.collections)
        if path == "items/top":
            return page(self.items)
        if path.startswith("collections/") and path.endswith("/items/top"):
            members = self.collection_members[path.split("/")[1]]
            return page([i for i in self.items if i["key"] in members])
        if path.endswith("/children"):
            return page(self.children.get(path.split("/")[1], []))
        if path.endswith("/file/view/url"):
            return self.files[path.split("/")[1]].as_uri().encode(), {}
        raise AssertionError(f"unexpected URL {url}")

    def client(self, page_size=100):
        return zot.ZoteroClient(BASE, self.fetch, local=True, page_size=page_size)


@pytest.fixture()
def fake(tmp_path):
    return FakeZotero(tmp_path)


def test_metadata_mapping_korean_names_citekey_and_type():
    item = _item(
        "K1", "제목", extra="Citation Key: choi2020jst\nDOI: 10.1/x", itype="conferencePaper"
    )
    meta = zot.item_metadata(item)
    assert meta["author"] == ["최윤진", "Kim, Hee-Woong"]  # editors excluded, Korean order kept
    assert meta["year"] == 2020 and meta["publication"] == "Korea Business Review"
    assert meta["citekey"] == "choi2020jst" and meta["doi"] == "10.1/x"
    assert meta["source_type"] == SourceType.CONFERENCE_PAPER
    assert meta["zotero_uri"] == "zotero://select/library/items/K1"


def test_sync_imports_pdf_and_metadata_only_then_is_idempotent(store, fake):
    fake.add(_item("K1", "논문 하나", doi="10.1/one"), pdf_text="<!-- page 121 -->\n본문")
    fake.add(_item("K2", "PDF 없는 논문", doi="10.1/two"))
    fake.add({"key": "N1", "data": {"key": "N1", "itemType": "note", "title": ""}})

    rep = zot.sync(store, fake.client(page_size=1))  # page_size=1 exercises pagination
    assert [s.title for s in rep.added] == ["논문 하나"]
    assert [s.title for s in rep.metadata_only] == ["PDF 없는 논문"]

    repo = SourceRepository(store)
    one = next(s for s in repo.all() if s.zotero_key == "K1")
    assert one.status == CompileStatus.PENDING and one.pages == 1
    assert one.author == ["최윤진", "Kim, Hee-Woong"] and one.citekey is None
    assert (store.root / one.text_file).read_text(encoding="utf-8").count("<!-- page 121 -->") == 1
    two = next(s for s in repo.all() if s.zotero_key == "K2")
    assert two.status == CompileStatus.NEEDS_TEXT and two.local_file is None

    again = zot.sync(store, fake.client())
    assert not again.added and not again.metadata_only and again.unchanged == 2
    assert len(repo.all()) == 2


def test_pdf_added_in_zotero_later_is_attached(store, fake):
    fake.add(_item("K2", "나중에 PDF", doi="10.1/two"))
    zot.sync(store, fake.client())
    fake.attach("K2", "이제 본문이 있음")
    rep = zot.sync(store, fake.client())
    assert [s.title for s in rep.text_attached] == ["나중에 PDF"]
    src = SourceRepository(store).all()[0]
    assert src.status == CompileStatus.PENDING and src.local_file and src.text_file


def test_existing_manual_source_is_linked_not_duplicated(store, fake, tmp_path):
    manual = tmp_path / "manual.txt"
    manual.write_text("수동 등록", encoding="utf-8")
    src = IngestionAgent(store).ingest_file(manual, metadata={"doi": "10.1/one"}).source
    fake.add(_item("K1", "논문 하나", doi="10.1/ONE"), pdf_text="본문")
    rep = zot.sync(store, fake.client())
    assert [s.source_id for s in rep.linked] == [src.source_id]
    linked = SourceRepository(store).get(src.source_id)
    assert linked.zotero_key == "K1" and linked.author and linked.year == 2020
    assert len(SourceRepository(store).all()) == 1


def test_collection_filter_and_dry_run(store, fake):
    fake.add(_item("K1", "관광 논문"), pdf_text="본문", collection="COL1")
    fake.add(_item("K3", "다른 논문"), pdf_text="본문")
    rep = zot.sync(store, fake.client(), collection="tourism", dry_run=True)
    assert [s.title for s in rep.added] == ["관광 논문"]
    assert SourceRepository(store).all() == []  # dry run writes nothing
    with pytest.raises(zot.ZoteroError):
        zot.sync(store, fake.client(), collection="없는 컬렉션")


def test_http_client_against_local_server(store, fake):
    """Exercise the real urllib path, query format, and headers."""
    fake.add(_item("K1", "HTTP 논문"), pdf_text="본문")
    seen_headers = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            seen_headers.update({k.lower(): v for k, v in self.headers.items()})
            body, _ = fake.fetch("http://localhost:23119" + self.path)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        headers = {"Zotero-API-Version": "3"}
        base = f"http://127.0.0.1:{server.server_port}/api/users/0"
        client = zot.ZoteroClient(base, zot._http_fetch(headers), local=True)
        rep = zot.sync(store, client)
    finally:
        server.shutdown()
    assert [s.title for s in rep.added] == ["HTTP 논문"]
    assert seen_headers.get("zotero-api-version") == "3"


def test_unreachable_zotero_gives_clear_error():
    client = zot.ZoteroClient("http://127.0.0.1:9/api/users/0", zot._http_fetch({}), local=True)
    with pytest.raises(zot.ZoteroError, match="is Zotero running"):
        client.collections()


def _annotation(key, text, *, page="128", comment="", kind="highlight", sort="00007|000100|00200"):
    return {
        "key": key,
        "data": {
            "key": key,
            "itemType": "annotation",
            "annotationType": kind,
            "annotationText": text,
            "annotationComment": comment,
            "annotationColor": "#ffd400",
            "annotationPageLabel": page,
            "annotationSortIndex": sort,
            "tags": [{"tag": "핵심"}],
        },
    }


def test_highlights_are_imported_and_reopen_compiled_source(store, fake):
    from secondbrain import vault

    fake.add(_item("K1", "하이라이트 논문", doi="10.1/one"), pdf_text="본문")
    fake.children["AK1"] = [
        _annotation("H2", "두 번째", page="130", sort="00009|000001|00001"),
        _annotation("H1", "물가 0.293", comment="가장 큰 토픽", sort="00007|000100|00200"),
        _annotation("H3", "", kind="note", page="", comment="전체 메모", sort="00010|0|0"),
    ]
    rep = zot.sync(store, fake.client())
    src = SourceRepository(store).all()[0]
    assert [s.source_id for s in rep.annotations_updated] == [src.source_id]
    text = (store.root / src.annotations_file).read_text(encoding="utf-8")
    assert text.index('"물가 0.293"') < text.index('"두 번째"')  # sorted by position
    assert "## A1 · p.128 · highlight" in text and "- 내 메모: 가장 큰 토픽" in text
    assert "## A3 · p.11 · note" in text  # no label → page index + 1
    assert src.annotation_count == 3

    # Agent compiles; unchanged highlights do not reopen it.
    page = store.root / "wiki/papers/x.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text("---\ntype: paper\ntitle: x\n---\n", encoding="utf-8")
    vault.mark_compiled(store, src.source_id, "wiki/papers/x", [], [])
    assert not zot.sync(store, fake.client()).annotations_updated
    assert not SourceRepository(store).get(src.source_id).annotations_changed

    # User adds a highlight in Zotero → source needs the agent again.
    fake.children["AK1"].append(_annotation("H4", "새 하이라이트", sort="00011|0|0"))
    assert zot.sync(store, fake.client()).annotations_updated
    assert SourceRepository(store).get(src.source_id).annotations_changed

    assert not zot.sync(store, fake.client(), annotations=False).annotations_updated
