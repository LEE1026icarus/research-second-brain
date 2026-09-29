"""Wiki Agent: incremental, provenance-preserving knowledge integration.

This implements the ingest procedure of spec §7::

    New Source -> Extraction -> Concept Detection -> Existing Wiki Retrieval
    -> Comparison -> Existing Page Update -> Cross-link Creation
    -> Overview Update -> Open Question Detection

Design principles (spec §18):
* never delete content, only add/annotate while keeping provenance,
* never record unverified inference as a wiki fact,
* surface contradictions rather than hide them,
* every synthesized bullet carries a source reference.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from ..config import StoreConfig
from ..models import (
    PaperExtraction,
    Provenance,
    Source,
    UpdateEffect,
    WikiPageType,
)
from .page import WikiPage
from .store import WikiStore
from .templates import sections_for


@dataclass
class WikiUpdate:
    """Record of what the agent changed during one ingest (feeds the Digest, spec §27)."""

    paper_page: str | None = None
    created_pages: list[str] = field(default_factory=list)
    updated_pages: list[str] = field(default_factory=list)
    concepts_touched: list[str] = field(default_factory=list)
    theories_touched: list[str] = field(default_factory=list)
    methods_touched: list[str] = field(default_factory=list)
    effects: dict[str, UpdateEffect] = field(default_factory=dict)
    open_questions: list[str] = field(default_factory=list)


class WikiAgent:
    def __init__(self, store: StoreConfig) -> None:
        self.store = store
        self.wiki = WikiStore(store)

    # -- public entry point --
    def integrate(self, source: Source, extraction: PaperExtraction) -> WikiUpdate:
        update = WikiUpdate()
        prov = self._provenance(source, extraction)
        concepts = self._detect_concepts(extraction)

        self._write_paper_page(source, extraction, prov, concepts, update)
        for concept in concepts:
            self._update_entity_page(WikiPageType.CONCEPT, concept, prov, extraction, update)
        for theory in extraction.theoretical_background:
            self._update_entity_page(WikiPageType.THEORY, theory, prov, extraction, update)
        for method in extraction.analysis_methods:
            self._update_entity_page(WikiPageType.METHOD, method, prov, extraction, update)
        self._update_overviews(concepts, prov, extraction, update)
        self._detect_open_questions(extraction, prov, update)
        return update

    # -- helpers for links / citations --
    def _paper_name(self, prov: Provenance) -> str:
        return prov.title or prov.source_id

    def _cite(self, prov: Provenance) -> str:
        """Inline citation that links back to the paper page (resolvable in Obsidian)."""
        return f"({self.wiki.link(WikiPageType.PAPER, self._paper_name(prov), prov.short_ref())})"

    def _paper_bullet(self, prov: Provenance) -> str:
        """Bullet used in 'Related Papers' / 'Key Papers': title link + short citation."""
        name = self._paper_name(prov)
        return f"{self.wiki.link(WikiPageType.PAPER, name)} — {prov.short_ref()}"

    # -- steps --
    def _provenance(self, source: Source, extraction: PaperExtraction) -> Provenance:
        return Provenance(
            source_id=source.source_id,
            title=extraction.title or source.title,
            authors=extraction.authors or source.author,
            year=extraction.year
            or (source.publication_date.year if source.publication_date else None),
            doi=extraction.doi or source.doi,
            url=source.url,
        )

    def _write_paper_page(
        self,
        source: Source,
        ex: PaperExtraction,
        prov: Provenance,
        concepts: list[str],
        update: WikiUpdate,
    ) -> None:
        name = self._paper_name(prov)
        existed = self.wiki.exists(WikiPageType.PAPER, name)
        page = self.wiki.load(WikiPageType.PAPER, name) or self._blank(name, WikiPageType.PAPER)

        page.frontmatter.update(
            {
                "type": "paper",
                "source_id": source.source_id,
                "title": name,
                "authors": prov.authors,
                "year": prov.year,
                "journal": ex.journal,
                "doi": prov.doi,
                "url": source.url,
                "language": ex.language,
                "keywords": ex.keywords,
                "source_type": source.source_type.value,
                "evidence_level": source.evidence_level.value,
                "tags": ["paper", source.source_type.value],
                "updated": date.today().isoformat(),
            }
        )

        if ex.abstract:
            page.set_section("Summary", f"> [!quote] 원문 요약 (Source Fact)\n> {ex.abstract}")
        link = self.wiki.link
        self._fill_list(page, "Research Context", {
            "Purpose": [ex.purpose] if ex.purpose else [],
            "Research Questions": ex.research_questions,
            "Theoretical Background": [
                link(WikiPageType.THEORY, t) for t in ex.theoretical_background
            ],
            "Key Concepts": [link(WikiPageType.CONCEPT, c) for c in concepts],
        })
        self._fill_list(page, "Research Design", {
            "Methodology": [ex.methodology] if ex.methodology else [],
            "Design": [ex.research_design] if ex.research_design else [],
            "Data": [ex.data] if ex.data else [],
            "Sample": [ex.sample] if ex.sample else [],
        })
        self._fill_list(page, "Variables", {
            "Independent": ex.independent_variables,
            "Dependent": ex.dependent_variables,
            "Mediating": ex.mediating_variables,
            "Moderating": ex.moderating_variables,
            "Control": ex.control_variables,
        })
        self._fill_list(page, "Analysis", {
            "Methods": [link(WikiPageType.METHOD, m) for m in ex.analysis_methods],
            "Models": ex.models,
            "Algorithms": ex.algorithms,
            "Metrics": ex.evaluation_metrics,
        })
        self._fill_list(page, "Results", {
            "Key Findings": ex.key_findings,
            "Significant Relationships": ex.significant_relationships,
            "Non-significant Relationships": ex.nonsignificant_relationships,
        })
        self._fill_list(page, "Discussion", {
            "Theoretical Contributions": ex.theoretical_contributions,
            "Practical Contributions": ex.practical_contributions,
            "Limitations": ex.limitations,
            "Future Work": ex.future_work,
        })

        if ex.claims:
            body = "\n".join(f"- {c.one_line()}  {self._cite(c.provenance)}" for c in ex.claims)
            page.set_section("Claims", body)

        related = [link(WikiPageType.CONCEPT, c) for c in concepts]
        related += [link(WikiPageType.THEORY, t) for t in ex.theoretical_background]
        related += [link(WikiPageType.METHOD, m) for m in ex.analysis_methods]
        if concepts:
            related.append(link(WikiPageType.OVERVIEW, concepts[0], f"Overview: {concepts[0]}"))
        if related:
            page.set_section("Related Pages", "\n".join(f"- {r}" for r in dict.fromkeys(related)))

        local = (
            f"- Local file: `{source.local_file}`"
            if source.local_file
            else "- Local file: (metadata-only)"
        )
        prov_lines = [
            f"- Source ID: `{source.source_id}`",
            local,
            f"- DOI: {prov.doi}" if prov.doi else "",
            f"- URL: {source.url}" if source.url else "",
            f"- Evidence level: {source.evidence_level.value}",
            "- Extractor: heuristic (rule-based) — 추출 항목은 원문 문장 그대로이며 검토 필요",
        ]
        page.set_section("Provenance", "\n".join(line for line in prov_lines if line))

        self.wiki.save(WikiPageType.PAPER, name, page)
        rel = self.wiki.rel_path(WikiPageType.PAPER, name)
        update.paper_page = rel
        (update.updated_pages if existed else update.created_pages).append(rel)

    def _detect_concepts(self, ex: PaperExtraction) -> list[str]:
        """Relevant concepts to attach this source to (spec §7)."""
        concepts: list[str] = []
        seen: set[str] = set()
        for c in ex.key_concepts:
            key = c.lower().strip()
            if key and key not in seen and len(c) >= 2:
                seen.add(key)
                concepts.append(c)
        return concepts[:8]

    def _update_entity_page(
        self,
        page_type: WikiPageType,
        name: str,
        prov: Provenance,
        ex: PaperExtraction,
        update: WikiUpdate,
    ) -> None:
        """Create or incrementally update a concept / theory / method page."""
        kind = {
            WikiPageType.CONCEPT: "concept",
            WikiPageType.THEORY: "theory",
            WikiPageType.METHOD: "method",
        }[page_type]
        existed = self.wiki.exists(page_type, name)
        page = self.wiki.load(page_type, name) or self._blank(name, page_type)
        page.frontmatter.setdefault("type", kind)
        page.frontmatter.setdefault("title", name)
        page.frontmatter["tags"] = sorted(set(page.frontmatter.get("tags", [])) | {kind})
        page.frontmatter["updated"] = date.today().isoformat()

        before = page.get_section("Established Findings") or ""
        added = page.append_bullet(
            "Related Papers", self._paper_bullet(prov)
        )
        if page_type is WikiPageType.METHOD:
            added |= page.append_bullet(
                "Applications",
                f"{ex.language == 'ko' and '적용 분야' or 'Applied to'}: "
                f"{', '.join(ex.keywords[:3]) or self._paper_name(prov)} {self._cite(prov)}",
            )

        # Structured relationships only (never free-text inference) (spec §18).
        for finding in ex.significant_relationships[:3]:
            page.append_bullet("Established Findings", f"{finding} {self._cite(prov)}")
        for finding in ex.nonsignificant_relationships[:3]:
            page.append_bullet(
                "Conflicting Findings", f"(non-significant) {finding} {self._cite(prov)}"
            )

        effect = self._classify_effect(before, ex, existed)
        self.wiki.save(page_type, name, page)
        rel = self.wiki.rel_path(page_type, name)
        {
            WikiPageType.CONCEPT: update.concepts_touched,
            WikiPageType.THEORY: update.theories_touched,
            WikiPageType.METHOD: update.methods_touched,
        }[page_type].append(name)
        update.effects[name] = effect
        if not existed:
            update.created_pages.append(rel)
        elif added or effect is not UpdateEffect.UNCHANGED:
            update.updated_pages.append(rel)

    @staticmethod
    def _classify_effect(
        established_before: str, ex: PaperExtraction, existed: bool
    ) -> UpdateEffect:
        """Classify how this source affects an existing page (spec §2.2).

        Conservative Phase-1 rules based only on structured relationships:
        non-significant results against existing findings => CONTRADICT;
        significant results on a page with findings => STRENGTHEN; a new page or
        new evidence => EXTEND; otherwise UNCHANGED. An LLM comparator can
        replace this later.
        """
        has_prior = bool(established_before.strip())
        if ex.nonsignificant_relationships and has_prior:
            return UpdateEffect.CONTRADICT
        if ex.significant_relationships:
            return UpdateEffect.STRENGTHEN if has_prior else UpdateEffect.EXTEND
        return UpdateEffect.EXTEND if not existed else UpdateEffect.UNCHANGED

    def _update_overviews(
        self,
        concepts: list[str],
        prov: Provenance,
        ex: PaperExtraction,
        update: WikiUpdate,
    ) -> None:
        """Attach the paper to a topic overview (spec §8).

        Phase 1 anchors the overview on the first concept (the first author
        keyword when available) so related sources accrete into one overview.
        """
        if not concepts:
            return
        topic = concepts[0]
        existed = self.wiki.exists(WikiPageType.OVERVIEW, topic)
        page = self.wiki.load(WikiPageType.OVERVIEW, topic) or self._blank(
            topic, WikiPageType.OVERVIEW
        )
        page.frontmatter.setdefault("type", "overview")
        page.frontmatter.setdefault("title", topic)
        page.frontmatter["tags"] = sorted(set(page.frontmatter.get("tags", [])) | {"overview"})
        page.frontmatter["updated"] = date.today().isoformat()
        cite = self._cite(prov)
        lk = self.wiki.link
        page.append_bullet("Key Papers", self._paper_bullet(prov))
        for t in ex.theoretical_background:
            page.append_bullet("Major Theories", f"{lk(WikiPageType.THEORY, t)} {cite}")
        for c in concepts[1:]:
            page.append_bullet("Important Variables", f"{lk(WikiPageType.CONCEPT, c)} {cite}")
        for m in ex.analysis_methods:
            method_link = lk(WikiPageType.METHOD, m)
            page.append_bullet("Recent Developments", f"방법론: {method_link} {cite}")
        for fw in ex.future_work[:3]:
            page.append_bullet("Open Questions", f"{fw} {cite}")
        self.wiki.save(WikiPageType.OVERVIEW, topic, page)
        rel = self.wiki.rel_path(WikiPageType.OVERVIEW, topic)
        (update.updated_pages if existed else update.created_pages).append(rel)

    def _detect_open_questions(
        self, ex: PaperExtraction, prov: Provenance, update: WikiUpdate
    ) -> None:
        """Turn 'future work' statements into open-question pages (spec §7)."""
        for fw in ex.future_work[:3]:
            name = self._question_title(fw)
            existed = self.wiki.exists(WikiPageType.QUESTION, name)
            page = self.wiki.load(WikiPageType.QUESTION, name) or self._blank(
                name, WikiPageType.QUESTION
            )
            page.frontmatter.setdefault("type", "question")
            page.frontmatter["tags"] = sorted(
                set(page.frontmatter.get("tags", [])) | {"open-question"}
            )
            page.frontmatter["status"] = page.frontmatter.get("status", "detected")
            page.set_section("Question", fw)
            page.set_section(
                "Why It Is Open", f"원 논문의 향후 연구 제안으로 언급됨 {self._cite(prov)}"
            )
            for c in self._detect_concepts(ex)[:3]:
                page.append_bullet("Related Concepts", self.wiki.link(WikiPageType.CONCEPT, c))
            page.append_bullet(
                "Related Papers", self._paper_bullet(prov)
            )
            page.set_section("Status", page.frontmatter["status"])
            self.wiki.save(WikiPageType.QUESTION, name, page)
            rel = self.wiki.rel_path(WikiPageType.QUESTION, name)
            if not existed:
                update.created_pages.append(rel)
            update.open_questions.append(fw)

    # -- helpers --
    @staticmethod
    def _question_title(sentence: str, limit: int = 50) -> str:
        """Short page title for an open question: drop ordinal/connective prefixes."""
        s = re.sub(
            r"^(첫째|둘째|셋째|넷째|다섯째|또한|아울러|그리고|따라서|즉|마지막으로"
            r"|first(ly)?|second(ly)?|third(ly)?|also|finally|moreover)\s*,?\s*",
            "",
            sentence.strip(),
            flags=re.IGNORECASE,
        )
        s = re.sub(r"^(향후\s*연구에서는|future research)\s*", "", s, flags=re.IGNORECASE)
        return s if len(s) <= limit else s[:limit].rstrip() + "…"

    def _blank(self, name: str, page_type: WikiPageType) -> WikiPage:
        page = WikiPage(title=name, frontmatter={"title": name})
        for section in sections_for(page_type):
            page.set_section(section, "")
        return page

    @staticmethod
    def _fill_list(page: WikiPage, section: str, groups: dict[str, list[str]]) -> None:
        lines: list[str] = []
        for label, values in groups.items():
            vals = [v for v in values if v]
            if vals:
                lines.append(f"**{label}:**")
                lines.extend(f"- {v}" for v in vals)
        if lines:
            page.set_section(section, "\n".join(lines))
