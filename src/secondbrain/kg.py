"""`sb graph` — build the knowledge graph and list Synapse candidates (spec §10–13, §28).

Inputs (all written by the agent or fetched by `sb refs`, never guessed here):

* paper pages' ``## Claims`` lines::

      - **C1** [[wiki/concepts/a|A]] → [[wiki/concepts/b|B]] | direction: + | ... | p.12

  ``A → B → C`` chains become two relations. Ends that are wikilinks are
  identified by their target page, so the same concept in two papers is one
  node; plain-text ends are matched by normalized text.
* links from paper pages to theory / method / dataset / concept pages,
* paper frontmatter fields (``theories``, ``methods``, ``domain``, ``design``, ``year``),
* citation edges inside the library from ``kg/citations.json``.

Output: ``kg/graph.json`` and ``reports/synapse-candidates.md`` — *candidates*
for the agent to judge (AGENTS.md §4.4). Nothing here is an idea or a fact.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from .config import StoreConfig
from .models import Edge, EdgeType, Node, NodeType, Provenance
from .openalex import analyze, load_citations
from .store import GraphRepository, SourceRepository
from .vault import load_pages

CLAIM_RE = re.compile(r"^\s*-\s*\*\*(C\d+)\*\*\s*(.+)$")
ARROW_RE = re.compile(r"\s*(?:→|->|⇒)\s*")
LINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]*))?\]\]")
PAGE_RE = re.compile(r"\bpp?\.\s*(\d{1,4}(?:\s*[–\-]\s*\d{1,4})?)")
DIRECTIONS = {
    "+": "+",
    "positive": "+",
    "−": "-",
    "-": "-",
    "negative": "-",
    "0": "0",
    "none": "0",
    "ns": "0",
    "mixed": "mixed",
    "±": "mixed",
}
FOLDER_NODE = {
    "concepts": NodeType.CONCEPT,
    "theories": NodeType.THEORY,
    "methods": NodeType.METHOD,
    "datasets": NodeType.DATASET,
    "technologies": NodeType.TECHNOLOGY,
    "researchers": NodeType.RESEARCHER,
    "organizations": NodeType.ORGANIZATION,
    "questions": NodeType.RESEARCH_QUESTION,
    "papers": NodeType.PAPER,
    "sources": NodeType.PAPER,
}
FOLDER_EDGE = {
    "theories": EdgeType.BASED_ON,
    "methods": EdgeType.USES_METHOD,
    "datasets": EdgeType.USES_DATASET,
    "concepts": EdgeType.APPLIES_TO,
    "technologies": EdgeType.USES,
}
STRONG_DESIGNS = {"longitudinal", "panel", "experiment", "quasi-experiment"}


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", text.lower()).split())


@dataclass
class Claim:
    paper: str  # wiki page rel
    source_id: str | None
    cid: str
    ends: list[tuple[str, str]]  # (key, label) along the chain
    direction: str | None
    page: str | None
    text: str

    def relations(self) -> list[tuple[tuple[str, str], tuple[str, str]]]:
        return list(zip(self.ends, self.ends[1:], strict=False))


def _end(raw: str) -> tuple[str, str]:
    raw = raw.strip()
    m = LINK_RE.search(raw)
    if m and m.start() == 0:
        return m.group(1).strip(), (m.group(2) or m.group(1).rsplit("/", 1)[-1]).strip()
    label = LINK_RE.sub(lambda x: x.group(2) or x.group(1), raw).strip()
    return f"text:{_norm(label)}", label


def split_fields(text: str) -> list[str]:
    """Split on ``|`` but not inside ``[[target|alias]]`` links."""
    out, buf, depth, i = [], [], 0, 0
    while i < len(text):
        if text.startswith("[[", i):
            depth += 1
            buf.append("[[")
            i += 2
            continue
        if text.startswith("]]", i) and depth:
            depth -= 1
            buf.append("]]")
            i += 2
            continue
        ch = text[i]
        if ch == "|" and not depth:
            out.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
        i += 1
    out.append("".join(buf))
    return out


def parse_claims(rel: str, source_id: str | None, body: str) -> list[Claim]:
    out = []
    in_section = False
    for line in body.splitlines():
        if line.startswith("## "):
            in_section = line[3:].strip().lower().startswith("claims")
            continue
        m = CLAIM_RE.match(line) if in_section else None
        if not m:
            continue
        cid, rest = m.group(1), m.group(2)
        parts = [p.strip() for p in split_fields(rest)]
        head, meta = parts[0], parts[1:]
        direction = None
        for p in meta:
            if p.lower().startswith("direction:"):
                val = p.split(":", 1)[1].strip().lower()
                direction = DIRECTIONS.get(val.split()[0] if val else "", None)
        pm = PAGE_RE.search(rest)
        chain = [c for c in ARROW_RE.split(head) if c.strip()]
        ends = [_end(c) for c in chain] if len(chain) >= 2 else []
        out.append(Claim(rel, source_id, cid, ends, direction, pm.group(1) if pm else None, head))
    return out


@dataclass
class Candidate:
    # contradiction | missing-edge | method-transfer | theory-transfer | evidence-gap | temporal-gap
    kind: str
    title: str
    evidence: list[str] = field(default_factory=list)
    score: float = 0.0


@dataclass
class GraphResult:
    nodes: int = 0
    edges: int = 0
    claims: int = 0
    relations: int = 0
    candidates: list[Candidate] = field(default_factory=list)


def build(store: StoreConfig, today: date | None = None, stale_years: int = 5) -> GraphResult:
    today = today or date.today()
    pages = load_pages(store)
    by_rel = {p.rel: p for p in pages}
    sources = {s.source_id: s for s in SourceRepository(store).all()}
    nodes: dict[str, Node] = {}
    edges: dict[str, Edge] = {}

    def node(key: str, ntype: NodeType, label: str, sid: str | None = None) -> Node:
        n = nodes.get(key)
        if n is None:
            page = key if key in by_rel else None
            n = nodes[key] = Node(node_id=key, node_type=ntype, label=label, wiki_page=page)
        if sid and sid not in n.source_ids:
            n.source_ids.append(sid)
        return n

    def edge(a: str, b: str, etype: EdgeType, sid: str | None, page: str | None = None, **attrs):
        key = f"{a}|{etype.value}|{b}|{attrs.get('claim', '')}"
        e = edges.get(key)
        if e is None:
            e = edges[key] = Edge(edge_id=key, source=a, target=b, edge_type=etype, attrs=attrs)
        if sid:
            e.provenance.append(Provenance(source_id=sid, page=page))

    papers = [p for p in pages if p.area == "wiki" and p.folder in ("papers", "sources")]
    claims: list[Claim] = []
    for p in papers:
        sid = p.frontmatter.get("source_id")
        node(p.rel, NodeType.PAPER, p.title, sid)
        for target in {m.group(1).strip() for m in LINK_RE.finditer(p.body)}:
            folder = (
                target.split("/")[1]
                if target.startswith("wiki/") and target.count("/") >= 2
                else ""
            )
            if folder in FOLDER_EDGE and target in by_rel:
                node(target, FOLDER_NODE[folder], by_rel[target].title, sid)
                edge(p.rel, target, FOLDER_EDGE[folder], sid)
        for c in parse_claims(p.rel, sid, p.body):
            claims.append(c)
            cnode = f"{p.rel}#{c.cid}"
            node(cnode, NodeType.CLAIM, f"{c.cid}: {c.text[:80]}", sid)
            edge(p.rel, cnode, EdgeType.SUPPORTS, sid, c.page)
            for (ka, la), (kb, lb) in c.relations():
                for k, lbl in ((ka, la), (kb, lb)):
                    folder = k.split("/")[1] if k.startswith("wiki/") else ""
                    node(k, FOLDER_NODE.get(folder, NodeType.VARIABLE), lbl, sid)
                edge(
                    ka,
                    kb,
                    EdgeType.PREDICTS,
                    sid,
                    c.page,
                    direction=c.direction or "?",
                    claim=cnode,
                )

    cites = load_citations(store)
    _, internal = analyze(store, cites)
    for a, b in internal:
        pa, pb = sources.get(a), sources.get(b)
        if pa and pb and pa.wiki_page and pb.wiki_page:
            node(pa.wiki_page, NodeType.PAPER, pa.title or a, a)
            node(pb.wiki_page, NodeType.PAPER, pb.title or b, b)
            edge(pa.wiki_page, pb.wiki_page, EdgeType.CITES, a)

    GraphRepository(store).save(list(nodes.values()), list(edges.values()))
    res = GraphResult(len(nodes), len(edges), len(claims), sum(len(c.relations()) for c in claims))
    res.candidates = (
        _contradictions(claims)
        + _missing_edges(claims)
        + _transfers(papers)
        + _evidence_gaps(papers)
        + _temporal_gaps(papers, today.year - stale_years)
    )
    return res


def _cite(c: Claim) -> str:
    page = f", p.{c.page}" if c.page else ""
    return f"[[{c.paper}]] {c.cid}{page}"


def _contradictions(claims: list[Claim]) -> list[Candidate]:
    rel: dict[tuple[str, str], list[Claim]] = defaultdict(list)
    labels: dict[str, str] = {}
    for c in claims:
        for (ka, la), (kb, lb) in c.relations():
            rel[(ka, kb)].append(c)
            labels[ka], labels[kb] = la, lb
    out = []
    for (a, b), cs in rel.items():
        dirs = {c.direction for c in cs if c.direction in ("+", "-", "0", "mixed")}
        papers = {c.paper for c in cs}
        if len(dirs) > 1 and len(papers) > 1:
            ev = [f"{_cite(c)}: direction {c.direction}" for c in cs]
            out.append(
                Candidate(
                    "contradiction",
                    f"{labels[a]} → {labels[b]}: 방향이 서로 다름 ({', '.join(sorted(dirs))})",
                    ev,
                    3 + len(cs),
                )
            )
    return out


def _missing_edges(claims: list[Claim]) -> list[Candidate]:
    out_edges: dict[str, dict[str, list[Claim]]] = defaultdict(lambda: defaultdict(list))
    labels: dict[str, str] = {}
    for c in claims:
        for (ka, la), (kb, lb) in c.relations():
            out_edges[ka][kb].append(c)
            labels[ka], labels[kb] = la, lb
    found = []
    for a, bs in out_edges.items():
        for b, ab in bs.items():
            for cnode, bc in out_edges.get(b, {}).items():
                if cnode in (a, b) or cnode in out_edges[a]:
                    continue
                papers = {c.paper for c in ab + bc}
                if len({(c.paper, c.cid) for c in ab + bc}) < 2:
                    continue  # a single A→B→C chain claim is not a gap
                ev = [
                    f"{labels[a]} → {labels[b]}: {_cite(ab[0])}",
                    f"{labels[b]} → {labels[cnode]}: {_cite(bc[0])}",
                ]
                found.append(
                    Candidate(
                        "missing-edge",
                        f"{labels[a]} → {labels[cnode]} 관계를 직접 다룬 Claim이 없음 "
                        f"(매개: {labels[b]})",
                        ev,
                        2 + len(papers),
                    )
                )
    return found


def _fm_list(p, key: str) -> list[str]:
    v = p.frontmatter.get(key) or []
    return [str(x) for x in v] if isinstance(v, list) else [str(v)]


def _transfers(papers) -> list[Candidate]:
    out = []
    for kind, key in (("method-transfer", "methods"), ("theory-transfer", "theories")):
        used: dict[str, set[str]] = defaultdict(set)  # item -> domains
        domain_papers: dict[str, list[str]] = defaultdict(list)
        item_papers: dict[str, list[str]] = defaultdict(list)
        for p in papers:
            for d in _fm_list(p, "domain"):
                domain_papers[d].append(p.rel)
                for m in _fm_list(p, key):
                    used[m].add(d)
            for m in _fm_list(p, key):
                item_papers[m].append(p.rel)
        for m, doms in used.items():
            for d in sorted(set(domain_papers) - doms):
                if len(domain_papers[d]) < 1 or len(doms) < 1:
                    continue
                ev = [
                    f"{m} 사용: " + ", ".join(f"[[{r}]]" for r in item_papers[m][:3]),
                    f"{d} 분야 논문 {len(domain_papers[d])}편은 {m}를 쓰지 않음: "
                    + ", ".join(f"[[{r}]]" for r in domain_papers[d][:3]),
                ]
                label = "방법" if key == "methods" else "이론"
                out.append(
                    Candidate(
                        kind,
                        f"{label} '{m}'을(를) '{d}' 분야에 적용 "
                        f"({', '.join(sorted(doms))}에서만 사용됨)",
                        ev,
                        len(item_papers[m]) + len(domain_papers[d]) * 0.5,
                    )
                )
    return out


def _evidence_gaps(papers) -> list[Candidate]:
    by_theory: dict[str, list] = defaultdict(list)
    for p in papers:
        for t in _fm_list(p, "theories"):
            by_theory[t].append(p)
    out = []
    for t, ps in by_theory.items():
        designs = {str(p.frontmatter.get("design") or "") for p in ps}
        if len(ps) >= 2 and not designs & STRONG_DESIGNS:
            ev = [f"[[{p.rel}]] design: {p.frontmatter.get('design') or '미기재'}" for p in ps[:5]]
            out.append(
                Candidate(
                    "evidence-gap",
                    f"'{t}' 연구 {len(ps)}편 모두 종단·패널·실험 설계가 아님 (인과·종단 근거 부족)",
                    ev,
                    len(ps),
                )
            )
    return out


def _temporal_gaps(papers, cutoff: int) -> list[Candidate]:
    by_item: dict[str, list] = defaultdict(list)
    for p in papers:
        for t in _fm_list(p, "theories") + _fm_list(p, "methods"):
            by_item[t].append(p)
    out = []
    for t, ps in by_item.items():
        years = [
            p.frontmatter.get("year") for p in ps if isinstance(p.frontmatter.get("year"), int)
        ]
        if len(ps) >= 2 and years and max(years) < cutoff:
            ev = [f"[[{p.rel}]] ({p.frontmatter.get('year')})" for p in ps[:5]]
            out.append(
                Candidate(
                    "temporal-gap",
                    f"'{t}' 관련 내 라이브러리 논문이 {max(years)}년 이후 없음",
                    ev,
                    len(ps),
                )
            )
    return out


KIND_LABEL = {
    "contradiction": "충돌 (같은 관계, 다른 방향)",
    "missing-edge": "빠진 관계 (A→B, B→C는 있는데 A→C 없음)",
    "method-transfer": "방법 이전 후보",
    "theory-transfer": "이론 이전 후보",
    "evidence-gap": "근거 공백 (종단·인과 설계 없음)",
    "temporal-gap": "최근 연구 공백",
}


def render_candidates(res: GraphResult, limit: int = 15) -> str:
    L = [
        "---",
        "type: report",
        "title: Synapse 후보",
        f"updated: '{date.today().isoformat()}'",
        "---",
        "",
        "# Synapse 후보",
        "",
        "> `sb graph`가 Claims·frontmatter·인용 관계에서 **기계적으로** 뽑은 후보입니다. "
        "아이디어도 사실도 아닙니다. 에이전트가 AGENTS.md §4.4에 따라 읽고, "
        "쓸 만한 것만 `ideas/`에 씁니다.",
        "",
        f"그래프: 노드 {res.nodes} · 에지 {res.edges} · Claim {res.claims} "
        f"(관계형 {res.relations})",
        "",
    ]
    for kind, label in KIND_LABEL.items():
        cs = sorted((c for c in res.candidates if c.kind == kind), key=lambda c: -c.score)
        if not cs:
            continue
        L += [f"## {label} ({len(cs)})", ""]
        for c in cs[:limit]:
            L.append(f"- **{c.title}**")
            L += [f"  - {e}" for e in c.evidence]
        L.append("")
    if not res.candidates:
        L.append(
            "후보가 없습니다. 논문이 늘고 Claims에 `A → B` 관계와 방향이 채워질수록 "
            "후보가 생깁니다."
        )
    return "\n".join(L).rstrip() + "\n"
