"""The docs staleness inventory (#7520): one record per published living page.

``python -m scripts.docs.staleness_audit --out <dir>`` writes ``inventory.json`` and
``page-lists.md`` (one list per section sub-issue, #7522-#7528). These tests pin each
field on small fixtures, the published-living page set on the real tree, and that the
output is reproducible.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from scripts.docs import _living_pages as living
from scripts.docs import staleness_audit as audit

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FRONT = "---\ntitle: t\ndescription: d\ndoc_status: active\nkind: How-To\nupdated: '2026-01-01T00:00:00Z'\n---\n"


# --- The page set -------------------------------------------------------------------


def test_living_pages_are_the_published_set_minus_history() -> None:
    pages = living.living_pages(_REPO_ROOT / "docs")
    assert len(pages) >= 300  # non-vacuity: about 340 published living pages
    assert pages == sorted(pages)
    assert "README.md" in pages and "guides/README.md" in pages
    assert not [page for page in pages if page.startswith(("adr/", "plans/", "reports/", "changelog/", "archive/"))]


@pytest.mark.parametrize(
    ("page", "issue"),
    [
        ("context/audience/README.md", "#7522"),
        ("guides/how-to/x.md", "#7523"),
        ("architecture/x.md", "#7524"),
        ("development/x.md", "#7525"),
        ("api/x.md", "#7526"),
        ("migrations/x.md", "#7527"),
        ("operations/x.md", "#7528"),
        ("README.md", "#7528"),
    ],
)
def test_each_page_belongs_to_one_section_sub_issue(page: str, issue: str) -> None:
    assert audit.section_issue(page) == issue


# --- Last real content change ----------------------------------------------------------


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True).stdout.strip()


def _commit(root: Path, rel: str, text: str, message: str, date: str) -> str:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    _git(root, "add", "-A")
    stamp = f"{date}T12:00:00Z"
    env = {**os.environ, "GIT_AUTHOR_DATE": stamp, "GIT_COMMITTER_DATE": stamp}
    identity = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
    subprocess.run(["git", *identity, "commit", "-q", "-m", message], cwd=root, check=True, env=env)
    return _git(root, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    return root


def test_frontmatter_whitespace_and_link_target_commits_are_not_content(repo: Path) -> None:
    body = "# Guide\n\nRun the thing. See [the index](index.md).\n"
    first = _commit(repo, "docs/guides/g.md", _FRONT + body, "add", "2026-01-01")
    _commit(repo, "docs/guides/g.md", _FRONT.replace("2026-01-01T", "2026-06-01T") + body, "frontmatter", "2026-06-01")
    _commit(repo, "docs/guides/g.md", _FRONT + body.replace("Run the thing.", "Run  the\nthing."), "whitespace", "2026-07-01")
    _commit(repo, "docs/guides/g.md", _FRONT + body.replace("index.md", "README.md"), "link target", "2026-08-01")

    change = audit.GitHistory(repo).last_content_change("docs/guides/g.md")

    assert change == audit.ContentChange(sha=first, date="2026-01-01")


def test_a_body_text_change_is_content_and_a_rename_is_followed(repo: Path) -> None:
    _commit(repo, "docs/guides/g.md", _FRONT + "# Guide\n\nOld text.\n", "add", "2026-01-01")
    edited = _commit(repo, "docs/guides/g.md", _FRONT + "# Guide\n\nNew text.\n", "edit", "2026-03-01")
    _git(repo, "mv", "docs/guides/g.md", "docs/guides/README.md")
    _commit(repo, "docs/guides/README.md", _FRONT + "# Guide\n\nNew text.\n", "rename", "2026-09-01")

    change = audit.GitHistory(repo).last_content_change("docs/guides/README.md")

    assert change == audit.ContentChange(sha=edited, date="2026-03-01")


def test_a_shallow_clone_is_refused_rather_than_misdated(repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A shallow clone's boundary commit is not a content change: the audit refuses to guess."""
    _fixture_repo(repo)
    _commit(repo, "docs/guides/b.md", _FRONT + "# b\n\nNew text.\n", "edit", "2026-03-01")
    shallow = tmp_path / "shallow"
    subprocess.run(["git", "clone", "-q", "--depth", "1", f"file://{repo}", str(shallow)], check=True)

    with pytest.raises(audit.ShallowHistoryError, match="git fetch --unshallow"):
        audit.GitHistory(shallow)
    assert audit.main(["--out", str(tmp_path / "out"), "--repo-root", str(shallow)]) == 2
    assert "git fetch --unshallow" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


# --- What a page names --------------------------------------------------------------------


def test_named_paths_are_checked_against_the_tree(tmp_path: Path) -> None:
    (tmp_path / "src" / "kernel").mkdir(parents=True)
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "x.py").write_text("", encoding="utf-8")
    body = "See `src/kernel/`, `scripts/x.py`, `src/ghost/y.py` and docs/foo.md.\n"

    named, missing = audit.named_paths(body, tmp_path)

    assert named == ["scripts/x.py", "src/ghost/y.py", "src/kernel"]
    assert missing == ["src/ghost/y.py"]


_MANIFEST = {
    "commands": {
        "implement": {"hidden": False, "deprecated": False},
        "agent": {"hidden": False, "deprecated": False, "commands": {"tasks": {"hidden": False, "deprecated": False, "commands": {"status": {}}}}},
        "merge": {"hidden": True, "deprecated": True},
    }
}


def test_named_commands_are_checked_against_the_cli() -> None:
    body = "Run `spec-kitty implement WP01`, `spec-kitty agent tasks status`, `spec-kitty frobnicate`,\n`spec-kitty merge` and `spec-kitty agent nope`.\n"

    named, missing = audit.named_commands(body, _MANIFEST)

    assert named == ["spec-kitty agent nope", "spec-kitty agent tasks status", "spec-kitty frobnicate", "spec-kitty implement", "spec-kitty merge"]
    assert missing == ["spec-kitty agent nope", "spec-kitty frobnicate", "spec-kitty merge"]


def test_prose_names_no_command() -> None:
    """Only code names a command: "the spec-kitty project" in prose is not one."""
    body = "The spec-kitty project grew.\n\n```bash\nspec-kitty frobnicate --x\n```\n"

    assert audit.named_commands(body, _MANIFEST) == (["spec-kitty frobnicate"], ["spec-kitty frobnicate"])


def test_the_reader_is_the_named_audience_profile() -> None:
    frontmatter = {"audience": [{"profile": "internal/maintainer", "guidance_text": "x"}, {"profile": "external/ghost"}]}
    assert audit.readers(frontmatter) == ["external/ghost", "internal/maintainer"]
    assert audit.readers({}) == []


# --- Diagrams and Divio type ------------------------------------------------------------------


def test_text_drawn_diagrams_are_counted_but_rendered_ones_and_code_are_not() -> None:
    body = (
        "```\n┌────┐\n│ a  │──►\n└────┘\n```\n\n"
        "```text\nplanned --> claimed --> done\nfoo ---> bar\n```\n\n"
        "```mermaid\nflowchart LR\n  a --> b\n```\n\n"
        "```python\nx = a -> b\n```\n\n"
        "```bash\nspec-kitty next\n```\n"
    )
    assert audit.text_diagrams(body) == 2


@pytest.mark.parametrize(
    ("kind", "body", "mixed"),
    [
        ("How-To", "## Prerequisites\n\n## Steps\n", False),
        ("How-To", "## Prerequisites\n\n## Why it works this way\n", True),
        ("Reference", "## Options\n\n## Flags\n", False),
        ("Hub", "## Pages\n", False),
        ("Hub", "## Steps\n\n## Rationale\n", True),
    ],
)
def test_divio_type_and_mixing(kind: str, body: str, mixed: bool) -> None:
    assert audit.divio(kind, body).mixed is mixed


# --- The inventory ------------------------------------------------------------------------------


def _fixture_repo(root: Path) -> None:
    """A small docs tree with one page per section sub-issue, history pages, and the CLI tree."""
    manifest = root / "src" / "specify_cli" / "_completion_manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps(_MANIFEST), encoding="utf-8")
    for page in ("README.md", "context/a.md", "guides/b.md", "architecture/c.md", "development/d.md", "api/e.md", "migrations/f.md", "operations/g.md"):
        _commit(root, f"docs/{page}", _FRONT + f"# {page}\n\nRun `spec-kitty merge`.\n", f"add {page}", "2026-02-01")
    _commit(root, "docs/plans/p.md", _FRONT + "# plan\n", "add plan", "2026-02-02")


def test_the_inventory_is_reproducible_and_lists_every_section(repo: Path, tmp_path: Path) -> None:
    _fixture_repo(repo)
    first, second = tmp_path / "a", tmp_path / "b"
    assert audit.main(["--out", str(first), "--repo-root", str(repo)]) == 0
    assert audit.main(["--out", str(second), "--repo-root", str(repo)]) == 0

    assert (first / "inventory.json").read_bytes() == (second / "inventory.json").read_bytes()
    assert (first / "page-lists.md").read_bytes() == (second / "page-lists.md").read_bytes()
    data = json.loads((first / "inventory.json").read_text(encoding="utf-8"))
    assert [record["page"] for record in data["pages"]] == living.living_pages(repo / "docs")
    assert "plans/p.md" not in [record["page"] for record in data["pages"]]
    assert data["pages"][1]["retired_surfaces"] == ["spec-kitty merge"]
    assert data["pages"][1]["commands_missing"] == ["spec-kitty merge"]
    lists = (first / "page-lists.md").read_text(encoding="utf-8")
    for issue in ("#7522", "#7523", "#7524", "#7525", "#7526", "#7527", "#7528"):
        assert f"({issue})" in lists


def test_the_inventory_reads_title_and_description_like_the_gate(repo: Path) -> None:
    """One scanning path: a retired surface named only in the published title is in the record."""
    _fixture_repo(repo)
    front = _FRONT.replace("title: t", "title: Run spec-kitty merge")
    _commit(repo, "docs/guides/b.md", front + "# b\n\nRun `spec-kitty consolidate`.\n", "title", "2026-03-01")

    record = next(record for record in audit.build_inventory(repo) if record.page == "guides/b.md")

    assert record.retired_surfaces == ["spec-kitty merge"]
    assert living.published_text(front + "body\n").splitlines()[1] == "Run spec-kitty merge"
