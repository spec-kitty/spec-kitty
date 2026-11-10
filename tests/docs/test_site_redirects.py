"""Acceptance tests for the legacy redirect map generator (#6933; ADR 2026-10-31-1 D-5).

``scripts/docs/site_redirects.py`` derives ``site/legacy-redirects.json`` (doc-kitty's
``legacyHtmlRedirects``) from the URL baseline, the moves ledger and the published set.
These tests build a small ``docs/`` tree, a moves ledger and a baseline, and check
each D-5 rule and each refusal on its own mutant: a rule that stops applying changes
the map, and a refusal that stops firing lets a broken map through.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import ModuleType

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _gen() -> ModuleType:
    return importlib.import_module("scripts.docs.site_redirects")


def _write(root: Path, rel: str, text: str = "") -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _page(status: str = "active") -> str:
    return f"---\ntitle: t\ndoc_status: {status}\n---\n\n# Body\n"


BASELINE = [
    "/index.html",
    "/guides/README.html",
    "/guides/index.html",
    "/guides/live.html",
    "/guides/wip.html",
    "/guides/old.html",
    "/guides/older.html",
    "/guides/moved-to-draft.html",
    "/plans/engineering-notes/note.html",
    "/assets/tool.html",
    "/adr/1.x/README.html",
]

MOVES = [
    ("/guides/old.html", "/guides/older.html"),
    ("/guides/older.html", "/guides/new.html"),
    ("/guides/moved-to-draft.html", "/guides/wip.html"),
]

EXPECTED = {
    "/adr/1.x/README.html": "/adr/1.x/",
    "/assets/tool.html": "/assets/",
    "/guides/README.html": "/guides/",
    "/guides/live.html": "/guides/live/",
    "/guides/moved-to-draft.html": "/guides/",
    "/guides/old.html": "/guides/new/",
    "/guides/older.html": "/guides/new/",
    "/guides/wip.html": "/guides/",
    "/plans/engineering-notes/note.html": "/plans/",
}


def _moves_yaml(moves: list[tuple[str, str]]) -> str:
    rows = "".join(f'  - {{from: {source}, to: {target}, ref: "#6933"}}\n' for source, target in moves)
    return f"kind: docs-moves-ledger\nversion: 1\nmoves:\n{rows}"


@pytest.fixture
def tree(tmp_path: Path) -> dict[str, Path]:
    """docs/, site/public, a baseline and a moves ledger whose map is :data:`EXPECTED`."""
    docs = tmp_path / "docs"
    _write(docs, "index.md", _page())
    _write(docs, "guides/README.md", _page())
    _write(docs, "guides/live.md", _page())
    _write(docs, "guides/new.md", _page())
    _write(docs, "guides/wip.md", _page("draft"))
    _write(docs, "plans/index.md", _page())
    _write(docs, "plans/engineering-notes/note.md", _page("active"))
    _write(docs, "assets/index.md", _page())
    _write(docs, "assets/tool.html", "<html>a standalone resource</html>")
    _write(docs, "adr/1.x/README.md", _page())
    public = tmp_path / "site" / "public"
    _write(public, "favicon.svg", "<svg/>")
    baseline = _write(tmp_path, "site/url-baseline.txt", "# routes\n" + "\n".join(BASELINE) + "\n")
    moves = _write(tmp_path, "site/moves.yaml", _moves_yaml(MOVES))
    return {"docs": docs, "public": public, "baseline": baseline, "moves": moves, "map": tmp_path / "site" / "legacy-redirects.json"}


def _build(tree: dict[str, Path]) -> dict[str, str]:
    gen = _gen()
    return dict(gen.build_map(baseline=tree["baseline"], moves=tree["moves"], docs=tree["docs"], public=tree["public"]))


def test_the_map_follows_every_d5_rule(tree: dict[str, Path]) -> None:
    assert _build(tree) == EXPECTED


def test_a_live_unmoved_section_index_gets_no_key(tree: dict[str, Path]) -> None:
    built = _build(tree)

    assert "/guides/index.html" not in built
    assert "/index.html" not in built


def test_a_page_flipped_to_draft_redirects_to_its_section_hub(tree: dict[str, Path]) -> None:
    _write(tree["docs"], "guides/live.md", _page("draft"))

    assert _build(tree)["/guides/live.html"] == "/guides/"


def test_a_hub_that_is_unpublished_too_falls_through_to_the_next_live_ancestor(tree: dict[str, Path]) -> None:
    _write(tree["docs"], "guides/README.md", _page("draft"))

    built = _build(tree)

    assert built["/guides/wip.html"] == "/"
    assert built["/guides/README.html"] == "/"


def _refusal(tree: dict[str, Path]) -> str:
    gen = _gen()
    with pytest.raises(gen.RedirectMapError) as raised:
        gen.build_map(baseline=tree["baseline"], moves=tree["moves"], docs=tree["docs"], public=tree["public"])
    return str(raised.value)


def test_a_baseline_route_with_no_page_no_move_and_no_resource_is_refused(tree: dict[str, Path]) -> None:
    tree["baseline"].write_text("\n".join([*BASELINE, "/guides/ghost.html"]) + "\n", encoding="utf-8")

    assert "/guides/ghost.html" in _refusal(tree)


def test_a_cycle_in_the_moves_ledger_is_refused(tree: dict[str, Path]) -> None:
    tree["moves"].write_text(_moves_yaml([*MOVES, ("/guides/new.html", "/guides/old.html")]), encoding="utf-8")

    assert "cycle" in _refusal(tree)


def test_a_key_that_would_overwrite_a_live_page_is_refused(tree: dict[str, Path]) -> None:
    tree["moves"].write_text(_moves_yaml([*MOVES, ("/guides/index.html", "/guides/live.html")]), encoding="utf-8")

    assert "/guides/index.html" in _refusal(tree)


def test_a_key_that_would_overwrite_a_public_file_is_refused(tree: dict[str, Path]) -> None:
    _write(tree["public"], "guides/live.html", "<html>static copy</html>")

    assert "/guides/live.html" in _refusal(tree)


def test_render_is_a_sorted_flat_json_object_with_no_comment_key(tree: dict[str, Path]) -> None:
    gen = _gen()
    text = gen.render(baseline=tree["baseline"], moves=tree["moves"], docs=tree["docs"], public=tree["public"])

    data = json.loads(text)
    assert data == EXPECTED
    assert list(data) == sorted(data)
    assert text.endswith("\n")


def _main(tree: dict[str, Path], *extra: str) -> int:
    paths = [
        "--path", str(tree["map"]), "--baseline", str(tree["baseline"]),
        "--moves", str(tree["moves"]), "--docs", str(tree["docs"]), "--public", str(tree["public"]),
    ]  # fmt: skip
    return int(_gen().main([*paths, *extra]))


def test_check_passes_on_the_written_map(tree: dict[str, Path]) -> None:
    assert _main(tree) == 0

    assert _main(tree, "--check") == 0


def test_check_fails_when_a_page_flips_to_draft_without_regenerating(tree: dict[str, Path], capsys: pytest.CaptureFixture[str]) -> None:
    _main(tree)
    _write(tree["docs"], "guides/live.md", _page("draft"))

    assert _main(tree, "--check") == 1
    assert "python -m scripts.docs.site_redirects" in capsys.readouterr().err


def test_check_fails_when_the_map_is_missing(tree: dict[str, Path]) -> None:
    assert _main(tree, "--check") == 1


def test_check_reports_a_refusal_instead_of_a_traceback(tree: dict[str, Path], capsys: pytest.CaptureFixture[str]) -> None:
    tree["baseline"].write_text("/guides/ghost.html\n", encoding="utf-8")

    assert _main(tree, "--check") == 1
    assert "/guides/ghost.html" in capsys.readouterr().err


def test_a_route_with_no_published_ancestor_is_refused(tree: dict[str, Path]) -> None:
    for rel in ("index.md", "guides/README.md"):
        _write(tree["docs"], rel, _page("draft"))

    assert "no published ancestor" in _refusal(tree)
