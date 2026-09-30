from __future__ import annotations

from secondbrain.wiki.page import WikiPage, wikilink


def test_roundtrip_frontmatter_and_sections():
    text = "---\ntitle: Foo\ntags:\n- a\n---\n# Foo\n\n## Summary\n\nhello\n\n## Notes\n\n- one\n"
    page = WikiPage.parse(text)
    assert page.title == "Foo"
    assert page.frontmatter["title"] == "Foo"
    assert page.get_section("Summary") == "hello"
    rendered = page.render()
    reparsed = WikiPage.parse(rendered)
    assert reparsed.get_section("Notes") == "- one"


def test_append_bullet_is_idempotent():
    page = WikiPage(title="C")
    assert page.append_bullet("Related Papers", "[[A]]") is True
    assert page.append_bullet("Related Papers", "[[A]]") is False  # no duplicate
    body = page.get_section("Related Papers")
    assert body.count("[[A]]") == 1


def test_set_section_updates_existing():
    page = WikiPage(title="C")
    page.set_section("Summary", "first")
    page.set_section("Summary", "second")
    assert page.get_section("Summary") == "second"


def test_wikilink():
    assert wikilink("A") == "[[A]]"
    assert wikilink("A", "alias") == "[[A|alias]]"
