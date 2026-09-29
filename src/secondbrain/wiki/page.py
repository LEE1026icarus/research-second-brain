"""Obsidian-compatible markdown page with YAML frontmatter (spec §23).

A page is a markdown file whose body is divided into ``##`` sections. The
:class:`WikiPage` helper lets the Wiki Agent read a page, update a single
section (append or replace) while leaving the rest untouched, and write it
back. This is what makes wiki updates *incremental* (spec §2.2) instead of
regenerated from scratch.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import yaml

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.DOTALL)


def wikilink(target: str, alias: str | None = None) -> str:
    """Render an Obsidian ``[[wikilink]]`` (spec §23)."""
    return f"[[{target}|{alias}]]" if alias else f"[[{target}]]"


@dataclass
class WikiPage:
    """In-memory representation of a wiki markdown file."""

    title: str
    frontmatter: dict = field(default_factory=dict)
    # Ordered list of (section_heading, body_text).
    sections: list[tuple[str, str]] = field(default_factory=list)

    # --- parsing / rendering ---
    @classmethod
    def parse(cls, text: str) -> WikiPage:
        fm: dict = {}
        body = text
        m = _FRONTMATTER_RE.match(text)
        if m:
            fm = yaml.safe_load(m.group(1)) or {}
            body = m.group(2)

        # Title is the first H1, if present.
        title = ""
        title_m = re.match(r"\s*#\s+(.+)", body)
        if title_m:
            title = title_m.group(1).strip()
            body = body[title_m.end():]

        sections: list[tuple[str, str]] = []
        # Split on H2 headings.
        parts = re.split(r"\n##\s+", "\n" + body)
        # parts[0] is any preamble before the first H2 (ignored/kept as intro).
        preamble = parts[0].strip("\n")
        if preamble:
            sections.append(("", preamble))
        for part in parts[1:]:
            head, _, rest = part.partition("\n")
            sections.append((head.strip(), rest.strip("\n")))
        return cls(title=title or fm.get("title", ""), frontmatter=fm, sections=sections)

    def render(self) -> str:
        out = []
        if self.frontmatter:
            fm = yaml.safe_dump(self.frontmatter, sort_keys=False, allow_unicode=True).strip()
            out.append(f"---\n{fm}\n---")
        if self.title:
            out.append(f"# {self.title}")
        for head, body in self.sections:
            if head == "":
                if body.strip():
                    out.append(body.strip())
            else:
                out.append(f"## {head}\n\n{body}".rstrip())
        return "\n\n".join(out).rstrip() + "\n"

    # --- section helpers ---
    def get_section(self, heading: str) -> str | None:
        for h, b in self.sections:
            if h.lower() == heading.lower():
                return b
        return None

    def set_section(self, heading: str, body: str) -> None:
        for i, (h, _) in enumerate(self.sections):
            if h.lower() == heading.lower():
                self.sections[i] = (heading, body.strip())
                return
        self.sections.append((heading, body.strip()))

    def append_bullet(self, heading: str, bullet: str) -> bool:
        """Append a bullet to a section if not already present. Returns True if added."""
        existing = self.get_section(heading) or ""
        line = bullet if bullet.startswith("- ") else f"- {bullet}"
        # Idempotency: don't duplicate the same bullet.
        norm = {ln.strip() for ln in existing.splitlines()}
        if line.strip() in norm:
            return False
        body = (existing + "\n" + line).strip() if existing else line
        self.set_section(heading, body)
        return True
