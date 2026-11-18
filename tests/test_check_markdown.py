"""The site rules of `tools/check_markdown.py`: no link into the developer set, one manifest."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))
import check_markdown


def test_a_published_page_does_not_link_into_the_developer_set() -> None:
    page = check_markdown.ROOT / "docs" / "mcp.md"
    assert check_markdown.link_problems(page, "see [the release](dev/releasing.md)")
    assert not check_markdown.link_problems(page, "see [the compiler](compiler.md)")
    developer = check_markdown.ROOT / "docs" / "dev" / "README.md"
    assert not check_markdown.link_problems(developer, "see [the release](releasing.md)")


def test_a_link_says_what_the_page_holds() -> None:
    assert check_markdown.link_text_problems("see [mcp.md](mcp.md#dialects)")
    assert check_markdown.link_text_problems("see [`docs/dev/writing.md`](docs/dev/writing.md)")
    assert not check_markdown.link_text_problems("see [reading an MCP tool](mcp.md)")
    assert not check_markdown.link_text_problems("see [`llms.txt`](https://example.com/llms.txt)")


def test_a_link_to_the_site_names_a_published_page_and_anchor() -> None:
    site = check_markdown.SITE
    for good in ("", "mcp/", "mcp/#what-a-tools-schema-may-hold", "llms.txt"):
        assert not check_markdown.site_link_problems(f"[x]({site}{good})"), good
    for bad in ("nowhere/", "mcp/#nowhere", "dev/writing/", "05-mcp/"):
        assert check_markdown.site_link_problems(f"[x]({site}{bad})"), bad


def test_the_llms_manifest_is_held_to_the_nav_and_the_descriptions(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("---\ndescription: The first page.\n---\n")
    (tmp_path / "b.md").write_text("---\ndescription: The second page.\n---\n")
    config = (
        "nav:\n  - A: a.md\n  - B: b.md\n"
        "plugins:\n  - llmstxt:\n      sections:\n        S:\n"
        "          - a.md: The first page.\n          - b.md: The second page.\n"
    )
    assert check_markdown.manifest_problems(config, tmp_path) == []
    missing = config.replace("          - b.md: The second page.\n", "")
    assert check_markdown.manifest_problems(missing, tmp_path) == [
        "mkdocs.yml: b.md is in the nav but not the llms.txt manifest"
    ]
    swapped = config.replace(
        "          - a.md: The first page.\n          - b.md: The second page.\n",
        "          - b.md: The second page.\n          - a.md: The first page.\n",
    )
    assert check_markdown.manifest_problems(swapped, tmp_path) == [
        "mkdocs.yml: the llms.txt manifest lists the pages in another order"
    ]
    moved = config.replace("- b.md: The second page.", "- b.md: Another page.")
    assert "the llms.txt line for b.md is not its description" in " ".join(
        check_markdown.manifest_problems(moved, tmp_path)
    )
