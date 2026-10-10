"""Known theories and methods (bilingual gazetteer).

The heuristic extractor only reports a theory/method when one of these
patterns actually occurs in the source text, so nothing is invented
(spec §18). Canonical names give one wiki page per entity regardless of the
language the source was written in (e.g. "기대 불일치" and
"Expectancy-Disconfirmation" both map to the same theory page).

Extend these tables as your library grows; an LLM extractor can replace this
in a later phase.
"""

from __future__ import annotations

import re

_I = re.IGNORECASE

THEORIES: dict[str, list[str]] = {
    "Expectancy-Disconfirmation Theory": [r"expectan\w*[\s-]*disconfirmation", r"기대\s*불일치"],
    "Technology Acceptance Model (TAM)": [
        r"technology\s+acceptance",
        r"기술\s*수용\s*모[델형]",
        r"\bTAM\b",
    ],
    "UTAUT": [r"\bUTAUT2?\b", r"unified\s+theory\s+of\s+acceptance", r"통합\s*기술\s*수용"],
    "Theory of Planned Behavior (TPB)": [r"planned\s+behaviou?r", r"계획된\s*행동\s*이론"],
    "Diffusion of Innovations": [r"diffusion\s+of\s+innovations?", r"혁신\s*확산"],
    "Expectancy Theory": [r"(?<!disconfirmation )expectancy\s+theory", r"(?<!불일치 )기대\s*이론"],
    "Goal Theory": [r"goal(-setting)?\s+theory", r"목표\s*(설정\s*)?이론"],
    "Uses and Gratifications Theory": [r"uses\s+and\s+gratifications?", r"이용과\s*충족"],
    "Self-Determination Theory": [r"self[\s-]*determination\s+theory", r"자기\s*결정\s*이론"],
    "Two-Factor Theory": [r"two[\s-]*factor\s+theory", r"herzberg", r"2\s*요인\s*이론"],
}

METHODS: dict[str, list[str]] = {
    "Joint Sentiment Topic Model (JST)": [r"joint\s*sentiment", r"\bJST\b"],
    "Latent Dirichlet Allocation (LDA)": [r"latent\s+dirichlet", r"\bLDA\b"],
    "BERTopic": [r"bertopic"],
    "Topic Modeling": [r"topic\s*model", r"토픽\s*모델"],
    "Text Mining": [r"text\s*mining", r"텍스트\s*마이닝"],
    "Sentiment Analysis": [r"sentiment\s+analysis", r"감성\s*분석"],
    "Keyword Network Analysis": [r"(keyword|semantic)\s+network", r"네트워크\s*(분석|다이어그램)"],
    "Morphological Analysis": [r"morphological\s+analysis", r"형태소\s*분석"],
    "Structural Equation Modeling (SEM)": [
        r"structural\s+equation",
        r"구조\s*방정식",
        r"\bSEM\b",
        r"\bPLS-SEM\b",
    ],
    "Regression Analysis": [r"regression\s+analysis", r"회귀\s*분석"],
    "Latent Profile Analysis (LPA)": [r"latent\s+profile", r"잠재\s*프로파일", r"\bLPA\b"],
    "Survey": [r"\bsurvey\b", r"설문\s*조사"],
    "Interview": [r"\binterviews?\b", r"심층\s*면접", r"인터뷰"],
}

_COMPILED = {
    table: {name: [re.compile(p, _I) for p in pats] for name, pats in data.items()}
    for table, data in (("theory", THEORIES), ("method", METHODS))
}


def count_mentions(kind: str, text: str) -> dict[str, int]:
    """Return {canonical_name: number_of_mentions} for a gazetteer ('theory'|'method')."""
    counts: dict[str, int] = {}
    for name, pats in _COMPILED[kind].items():
        n = sum(len(p.findall(text)) for p in pats)
        if n:
            counts[name] = n
    return counts


def canonical(kind: str, term: str) -> str | None:
    """Canonical name if ``term`` refers to a known theory/method, else ``None``."""
    for name, pats in _COMPILED[kind].items():
        if any(p.search(term) for p in pats):
            return name
    return None


def is_known_entity(term: str) -> bool:
    """True if a keyword is really a known theory or method (avoids duplicate pages)."""
    return canonical("theory", term) is not None or canonical("method", term) is not None
