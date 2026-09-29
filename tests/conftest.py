from __future__ import annotations

import pytest

from secondbrain.config import StoreConfig


@pytest.fixture()
def store(tmp_path) -> StoreConfig:
    st = StoreConfig(root=tmp_path / "store")
    st.ensure()
    return st


SAMPLE_TEXT = """Perceived Usefulness and Generative AI Adoption Intention: A Longitudinal Study

Jane Smith, John Doe
DOI: 10.1234/jis.2023.0456

Abstract
The purpose of this study is to examine how perceived usefulness affects
generative AI adoption intention. Drawing on the Technology Acceptance Model,
we investigate adoption over time. We conducted a longitudinal survey of 512
professionals. Our results show a significant positive effect. However, the
effect of social influence was not significant.

1. Introduction
Research Question: Does perceived usefulness affect adoption intention?

2. Methodology
We used structural equation modeling.

4. Discussion
A limitation of this study is self-reported data. Future research should
examine organizational-level adoption.
"""


@pytest.fixture()
def sample_file(tmp_path):
    p = tmp_path / "sample_paper.txt"
    p.write_text(SAMPLE_TEXT, encoding="utf-8")
    return p
