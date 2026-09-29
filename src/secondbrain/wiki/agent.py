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
from .page import WikiPage, wikilink
from .store import WikiStore
from .templates import sections_for


@dataclass
class WikiUpdate:
    """Record of what the agent changed during one ingest (feeds the Digest, spec §27)."""

    paper_page: str | None = None
    created_pages: list[str] = field(default_factory=list)
    updated_pages: list[str] = field(default_factory=list)
    concepts_touched: list[str] = field(default_factory=list)
    effects: dict[str, UpdateEffect] = field(default_factory=dict)
    open_questions: list[str] = field(default_factory=list)


def _cite(prov: Provenance) -> str:
    """Inline citation with a wikilink back to the paper page."""
    label = prov.short_ref()
    return f"({wikilink(label, label)}, source: `{prov.source_id}`)"


class WikiAgent:
    def __init__(self, store: StoreConfig) -> None:
        self.store = store
        self.wiki = WikiStore(store)

    # -- public entry point --
    def integrate(self, source: Source, extraction: PaperExtraction) -> WikiUpdate:
        update = WikiUpdate()
        prov = self._provenance(source, extraction)

        self._write_paper_page(source, extraction, prov, update)
        concepts = self._detect_concepts(extraction)
        for concept in concepts:
            self._update_concept_page(concept, prov, extraction, update)
        self._update_overviews(concepts, prov, update)
        self._detect_open_questions(extraction, prov, update)
        return update

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

    def _paper_name(self, prov: Provenance) -> str:
        return prov.title or prov.source_id

    def _write_paper_page(
        self,
        source: Source,
        ex: PaperExtraction,
        prov: Provenance,
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
                "doi": prov.doi,
                "url": source.url,
                "source_type": source.source_type.value,
                "evidence_level": source.evidence_level.value,
                "tags": ["paper", source.source_type.value],
                "updated": date.today().isoformat(),
            }
        )

        if ex.abstract:
            page.set_section("Summary", ex.abstract)
        self._fill_list(page, "Research Context", {
            "Purpose": [ex.purpose] if ex.purpose else [],
            "Research Questions": ex.research_questions,
            "Theoretical Background": ex.theoretical_background,
            "Key Concepts": ex.key_concepts,
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
            "Methods": ex.analysis_methods,
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
            body = "\n".join(f"- {c.one_line()}  {_cite(c.provenance)}" for c in ex.claims)
            page.set_section("Claims", body)

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
        ]
        page.set_section("Provenance", "\n".join(line for line in prov_lines if line))

        self.wiki.save(WikiPageType.PAPER, name, page)
        rel = self.wiki.rel_path(WikiPageType.PAPER, name)
        update.paper_page = rel
        (update.updated_pages if existed else update.created_pages).append(rel)

    def _detect_concepts(self, ex: PaperExtraction) -> list[str]:
        """Relevant concepts to attach this source to (spec §7)."""
        concepts: list[str] = []
        seen = set()
        for c in [*ex.key_concepts, *ex.theoretical_background]:
            key = c.lower().strip()
            if key and key not in seen and len(c) > 3:
                seen.add(key)
                concepts.append(c)
        return concepts[:8]

    def _update_concept_page(
        self,
        concept: str,
        prov: Provenance,
        ex: PaperExtraction,
        update: WikiUpdate,
    ) -> None:
        existed = self.wiki.exists(WikiPageType.CONCEPT, concept)
        page = self.wiki.load(WikiPageType.CONCEPT, concept) or self._blank(
            concept, WikiPageType.CONCEPT
        )
        page.frontmatter.setdefault("type", "concept")
        page.frontmatter.setdefault("title", concept)
        tags = set(page.frontmatter.get("tags", []))
        tags.add("concept")
        page.frontmatter["tags"] = sorted(tags)
        page.frontmatter["updated"] = date.today().isoformat()

        # Link the paper under Related Papers with provenance.
        paper_link = wikilink(self._paper_name(prov))
        added = page.append_bullet("Related Papers", f"{paper_link} {_cite(prov)}")

        # Attach any findings as synthesis bullets (never as bare 'facts').
        effect = self._classify_effect(page, ex)
        for finding in ex.significant_relationships[:3]:
            page.append_bullet("Established Findings", f"{finding} {_cite(prov)}")
        for finding in ex.nonsignificant_relationships[:3]:
            page.append_bullet("Conflicting Findings", f"(non-significant) {finding} {_cite(prov)}")

        self.wiki.save(WikiPageType.CONCEPT, concept, page)
        rel = self.wiki.rel_path(WikiPageType.CONCEPT, concept)
        update.concepts_touched.append(concept)
        update.effects[concept] = effect
        if existed:
            if added or effect is not UpdateEffect.UNCHANGED:
                update.updated_pages.append(rel)
        else:
            update.created_pages.append(rel)

    def _classify_effect(self, page: WikiPage, ex: PaperExtraction) -> UpdateEffect:
        """Classify how this source affects an existing concept page (spec §2.2).

        Conservative heuristic for Phase 1: presence of non-significant results
        against existing established findings => CONTRADICT; brand-new page or
        new findings => EXTEND/STRENGTHEN; otherwise UNCHANGED. A later phase
        can replace this with an LLM comparison.
        """
        established = page.get_section("Established Findings") or ""
        if ex.nonsignificant_relationships and established.strip():
            return UpdateEffect.CONTRADICT
        if ex.significant_relationships:
            return UpdateEffect.STRENGTHEN if established.strip() else UpdateEffect.EXTEND
        return UpdateEffect.UNCHANGED

    def _update_overviews(self, concepts: list[str], prov: Provenance, update: WikiUpdate) -> None:
        """Attach the paper to a topic overview (spec §8).

        Phase 1 uses the first detected concept as the overview topic anchor so
        related sources accrete into a single integrated overview rather than a
        list of papers.
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
        page.append_bullet("Key Papers", f"{wikilink(self._paper_name(prov))} {_cite(prov)}")
        self.wiki.save(WikiPageType.OVERVIEW, topic, page)
        rel = self.wiki.rel_path(WikiPageType.OVERVIEW, topic)
        (update.updated_pages if existed else update.created_pages).append(rel)

    def _detect_open_questions(
        self, ex: PaperExtraction, prov: Provenance, update: WikiUpdate
    ) -> None:
        """Turn 'future work' statements into open-question pages (spec §7)."""
        for fw in ex.future_work[:3]:
            name = fw[:80]
            page = self.wiki.load(WikiPageType.QUESTION, name) or self._blank(
                name, WikiPageType.QUESTION
            )
            page.frontmatter.setdefault("type", "question")
            page.frontmatter["tags"] = sorted(
                set(page.frontmatter.get("tags", [])) | {"open-question"}
            )
            page.set_section("Question", fw)
            page.append_bullet(
                "Related Papers", f"{wikilink(self._paper_name(prov))} {_cite(prov)}"
            )
            page.set_section("Status", "detected")
            self.wiki.save(WikiPageType.QUESTION, name, page)
            update.open_questions.append(fw)

    # -- helpers --
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
