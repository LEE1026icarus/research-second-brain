from __future__ import annotations

from secondbrain.models import (
    Claim,
    Direction,
    EvidenceLevel,
    Provenance,
    Source,
    SourceType,
)


def test_evidence_level_ordering():
    assert EvidenceLevel.PEER_REVIEWED.rank > EvidenceLevel.NEWS.rank
    assert EvidenceLevel.NEWS.rank > EvidenceLevel.BLOG.rank
    assert EvidenceLevel.UNKNOWN.rank == 0


def test_source_fingerprints_normalize():
    s = Source(
        source_id="s1",
        source_type=SourceType.JOURNAL_ARTICLE,
        title="  A   Great  Paper ",
        doi="10.1/AbC",
        url="https://x.org/a/",
    )
    fp = s.fingerprints()
    assert fp["doi"] == "10.1/abc"
    assert fp["title"] == "a great paper"
    assert fp["url"] == "https://x.org/a"


def test_claim_signature_and_oneline():
    c = Claim(
        subject="Perceived Usefulness",
        object="Adoption Intention",
        direction=Direction.POSITIVE,
        provenance=Provenance(source_id="s1"),
    )
    assert c.signature() == "perceived usefulness=>adoption intention"
    assert "→(+)" in c.one_line()


def test_provenance_short_ref():
    p = Provenance(source_id="s1", authors=["Smith, Jane"], year=2021)
    assert p.short_ref() == "Smith (2021)"
