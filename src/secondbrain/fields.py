"""Structured frontmatter fields for paper/source pages (for Dataview tables).

The agent fills these from the paper; `sb lint` checks that they exist and use
the allowed values, so Dataview queries such as "methods contains BERTopic and
design = longitudinal" (spec §25) work reliably.
"""

from __future__ import annotations

# field -> (kind, allowed values or None)
PAPER_FIELDS: dict[str, tuple[str, set[str] | None]] = {
    "research_type": (
        "enum",
        {"quantitative", "qualitative", "mixed", "computational", "review", "conceptual"},
    ),
    "design": (
        "enum",
        {
            "cross-sectional",
            "longitudinal",
            "panel",
            "experiment",
            "quasi-experiment",
            "case-study",
            "text-mining",
            "meta-analysis",
            "systematic-review",
            "simulation",
            "design-science",
            "other",
        },
    ),
    "theories": ("list", None),
    "methods": ("list", None),
    "data_type": (
        "list",
        {
            "survey",
            "experiment",
            "interview",
            "archival",
            "text",
            "log",
            "panel",
            "secondary",
            "observation",
            "simulation",
            "other",
        },
    ),
    "data_source": ("text", None),
    "sample_size": ("int", None),
    "unit_of_analysis": (
        "enum",
        {"individual", "team", "organization", "industry", "country", "document", "other"},
    ),
    "country": ("list", None),
    "period": ("text", None),
    "domain": ("list", None),
}


def check(frontmatter: dict) -> list[tuple[str, str, str]]:
    """Return (level, code, detail) problems for a paper page's structured fields."""
    out: list[tuple[str, str, str]] = []
    missing = [k for k in PAPER_FIELDS if k not in frontmatter]
    if missing:
        out.append(("info", "missing-field", ", ".join(missing)))
    for key, (kind, allowed) in PAPER_FIELDS.items():
        if key not in frontmatter or frontmatter[key] in (None, "", []):
            continue  # empty is allowed: "not reported in the paper"
        value = frontmatter[key]
        if kind == "list":
            if not isinstance(value, list):
                out.append(("warn", "bad-field", f"`{key}` must be a list, got {value!r}"))
                continue
            if allowed:
                bad = [v for v in value if str(v) not in allowed]
                if bad:
                    out.append(
                        ("warn", "bad-field", f"`{key}` has {bad}; allowed: {sorted(allowed)}")
                    )
        elif kind == "enum":
            if str(value) not in allowed:  # type: ignore[operator]
                out.append(("warn", "bad-field", f"`{key}`={value!r}; allowed: {sorted(allowed)}"))
        elif kind == "int":
            if not isinstance(value, int) or isinstance(value, bool):
                out.append(("warn", "bad-field", f"`{key}` must be an integer, got {value!r}"))
    return out
