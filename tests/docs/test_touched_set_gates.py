"""Red-first tests for the WP04 gate scaffolding (IC-03a).

Covers the extended structural-lint check-fns (T011), the touched-set gates
(T012), the root-allowlist gate (T041), and the rename/redirect reconciliation
(T013). Every gate is proven **green on a clean fixture** and **red on an
injected violation**, with non-vacuous denominators — the git-diff touched set,
the enumerated root files, and the rename source set are each shown to be
non-empty in the discriminating cases.

The occurrence-map / redirect-map spine lives on the planning branch and is not
required to be materialized in the execution lane; the reconcile gate is
therefore exercised entirely against in-test fixtures and a throwaway git repo,
never the live spine (C-010).
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from scripts.docs import rename_reconcile as rr
from scripts.docs import touched_set_gates as tsg

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_REPO_ROOT = Path(__file__).resolve().parents[2]


# --------------------------------------------------------------------------- #
# T011 — extended structural-lint check-fns (loaded from the shipped asset).
# --------------------------------------------------------------------------- #


_LINT_ASSET_MODULE_NAME = "docs_structural_lint_asset_wp04"

#: Populated by the autouse ``_lint_module`` fixture below, once per module.
LintConfig: type[Any]
check_one_index_per_dir: Callable[..., Any]
check_sanctioned_section_membership: Callable[..., Any]


@pytest.fixture(scope="module", autouse=True)
def _lint_module() -> Iterator[ModuleType]:
    """Load the structural-lint asset once for this module's tests.

    The module defines ``@dataclass`` types, and dataclasses resolves their
    string annotations via ``sys.modules[cls.__module__]`` — which must
    already be present before ``exec_module`` runs. A module-scoped
    ``pytest.MonkeyPatch.context()`` — not the function-scoped ``monkeypatch``
    fixture, which a module-scoped fixture cannot depend on — keeps that
    registration and undoes it once every test in this module has run.
    """
    from charter.offering.service import CharterOfferingService

    global LintConfig, check_one_index_per_dir, check_sanctioned_section_membership
    asset_path = CharterOfferingService().assets.resolve_path("common-docs-structural-lint")
    with pytest.MonkeyPatch.context() as mp:
        spec = importlib.util.spec_from_file_location(_LINT_ASSET_MODULE_NAME, asset_path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        mp.setitem(sys.modules, _LINT_ASSET_MODULE_NAME, module)
        spec.loader.exec_module(module)
        LintConfig = module.LintConfig
        check_one_index_per_dir = module.check_one_index_per_dir
        check_sanctioned_section_membership = module.check_sanctioned_section_membership
        yield module


def _lint_config(**overrides: object) -> object:
    """Build a minimal LintConfig; the new T004 fields default to empty/false."""
    base: dict[str, object] = {
        "curated_complete_sections": (),
        "concern_bucket_to_section": {},
        "point_in_time_patterns": (),
        "point_in_time_markers": (),
        "point_in_time_allowlist": (),
        "frontmatter_required_fields": (),
        "frontmatter_in_scope_exclusions": (),
        "shadow_tree_nav_exemptions": (),
        "redirect_stub_description_prefix": "Redirect stub:",
        "guides_boundary": "n/a",
    }
    base.update(overrides)
    return LintConfig(**base)


def _touch(path: Path, body: str = "# x\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def test_one_index_per_dir_is_noop_when_disabled(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    _touch(docs / "architecture" / "index.md")
    _touch(docs / "architecture" / "README.md")
    md_files = sorted(docs.rglob("*.md"))
    config = _lint_config(one_index_per_dir=False)

    assert check_one_index_per_dir(md_files, docs, tmp_path, config) == []


def test_one_index_per_dir_flags_competing_landing_pages(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    _touch(docs / "architecture" / "index.md")
    _touch(docs / "architecture" / "README.md")
    _touch(docs / "guides" / "index.md")  # single landing — clean
    md_files = sorted(docs.rglob("*.md"))
    config = _lint_config(one_index_per_dir=True)

    violations = check_one_index_per_dir(md_files, docs, tmp_path, config)

    assert len(violations) == 1  # non-vacuous: exactly the two-landing dir
    assert violations[0].rule_id == "one_index_per_dir"
    assert violations[0].path == "docs/architecture/README.md"


def test_sanctioned_section_membership_flags_off_structure_page(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    _touch(docs / "architecture" / "design.md")  # sanctioned
    _touch(docs / "assets" / "logo.md")  # non_content_dir
    _touch(docs / "core-concepts" / "intro.md")  # off-structure
    _touch(docs / "top-level.md")  # implicit index — sanctioned
    md_files = sorted(docs.rglob("*.md"))
    config = _lint_config(
        sanctioned_content_sections=("architecture", "index"),
        non_content_dirs=("assets/",),
    )

    violations = check_sanctioned_section_membership(md_files, docs, tmp_path, config)

    assert [v.path for v in violations] == ["docs/core-concepts/intro.md"]
    assert violations[0].rule_id == "sanctioned_section_membership"


def test_sanctioned_section_membership_all_green(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    _touch(docs / "architecture" / "design.md")
    _touch(docs / "guides" / "howto.md")
    md_files = sorted(docs.rglob("*.md"))
    config = _lint_config(sanctioned_content_sections=("architecture", "guides"))

    assert check_sanctioned_section_membership(md_files, docs, tmp_path, config) == []


# --------------------------------------------------------------------------- #
# Git-repo fixture for the touched-set / rename gates.
# --------------------------------------------------------------------------- #


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "base")
    return repo


def _commit_all(repo: Path, message: str) -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)


def _page(fm: dict[str, str], body: str = "body\n") -> str:
    lines = ["---", *[f"{k}: {v}" for k, v in fm.items()], "---", body]
    return "\n".join(lines)


_GOOD_DESC = "x" * 90  # inside the 50-180 band


# --------------------------------------------------------------------------- #
# T012 — touched-set gates.
# --------------------------------------------------------------------------- #


def test_compute_touched_set_scopes_to_docs_content_pages(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    base = _git(repo, "rev-parse", "HEAD").strip()
    _touch(repo / "docs" / "guides" / "a.md")
    _touch(repo / "docs" / "guides" / "index.md")  # nav — excluded
    _touch(repo / "src" / "code.md")  # outside docs — excluded
    _commit_all(repo, "changes")

    pages = tsg.compute_touched_set(base, repo)

    assert [p.name for p in pages] == ["a.md"]  # non-vacuous, scoped


def test_audience_presence_red_first_and_clean(tmp_path: Path) -> None:
    repo = tmp_path
    catalog = repo / "docs" / "context" / "audience" / "internal"
    _touch(catalog / "maintainer.md")
    good = repo / "docs" / "guides" / "good.md"
    good.parent.mkdir(parents=True, exist_ok=True)
    good.write_text(
        _page({"audience": "../context/audience/internal/maintainer.md"}),
        encoding="utf-8",
    )
    missing = repo / "docs" / "guides" / "missing.md"
    missing.write_text(_page({"title": "no audience"}), encoding="utf-8")
    dangling = repo / "docs" / "guides" / "dangling.md"
    dangling.write_text(_page({"audience": "../context/audience/internal/ghost.md"}), encoding="utf-8")
    catalog_root = repo / "docs" / "context" / "audience"

    assert tsg.check_audience_presence([good], repo, catalog_root) == []
    flagged = tsg.check_audience_presence([good, missing, dangling], repo, catalog_root)
    assert {v.path for v in flagged} == {
        "docs/guides/missing.md",
        "docs/guides/dangling.md",
    }
    assert all(v.rule_id == "audience_presence" for v in flagged)


def test_description_band_red_first_and_clean(tmp_path: Path) -> None:
    repo = tmp_path
    good = repo / "docs" / "guides" / "good.md"
    good.parent.mkdir(parents=True, exist_ok=True)
    good.write_text(_page({"description": _GOOD_DESC}), encoding="utf-8")
    short = repo / "docs" / "guides" / "short.md"
    short.write_text(_page({"description": "too short"}), encoding="utf-8")
    missing = repo / "docs" / "guides" / "missing.md"
    missing.write_text(_page({"title": "x"}), encoding="utf-8")

    assert tsg.check_description_band([good], repo) == []
    flagged = tsg.check_description_band([good, short, missing], repo)
    assert {v.path for v in flagged} == {
        "docs/guides/short.md",
        "docs/guides/missing.md",
    }


def test_audience_placement_flags_misfiled_howto(tmp_path: Path) -> None:
    repo = tmp_path
    docs = repo / "docs"
    config = {
        "concern_bucket_to_section": {
            "how_to_internal": "development/",
            "how_to_external": "guides/",
        }
    }
    # internal how_to filed in guides/ (wrong) → flagged
    bad = docs / "guides" / "internal-howto.md"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text(
        _page(
            {
                "type": "how_to",
                "audience": "../context/audience/internal/maintainer.md",
            }
        ),
        encoding="utf-8",
    )
    # internal how_to filed in development/ (right) → clean
    ok = docs / "development" / "ok-howto.md"
    ok.parent.mkdir(parents=True, exist_ok=True)
    ok.write_text(
        _page(
            {
                "type": "how_to",
                "audience": "../context/audience/internal/maintainer.md",
            }
        ),
        encoding="utf-8",
    )

    violations = tsg.check_audience_placement([bad, ok], repo, docs, config)

    assert [v.path for v in violations] == ["docs/guides/internal-howto.md"]
    assert violations[0].rule_id == "audience_placement"


def test_audience_placement_skips_when_homes_unresolvable(tmp_path: Path) -> None:
    repo = tmp_path
    docs = repo / "docs"
    page = docs / "guides" / "howto.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        _page({"type": "how_to", "audience": "../context/audience/internal/m.md"}),
        encoding="utf-8",
    )
    # Baseline (pre-WP01) routing has no how_to_internal/how_to_external split.
    config = {"concern_bucket_to_section": {"how_to": "development/"}}

    assert tsg.check_audience_placement([page], repo, docs, config) == []


# --------------------------------------------------------------------------- #
# T041 — root-allowlist gate.
# --------------------------------------------------------------------------- #


_ALLOWLIST = ["README.md", "CHANGELOG.md", "ascii-art.txt", ".all-contributorsrc"]


def test_root_allowlist_flags_unsanctioned_and_is_non_vacuous(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("ok\n", encoding="utf-8")
    (tmp_path / "ascii-art.txt").write_text("ok\n", encoding="utf-8")
    (tmp_path / "STRAY-NOTES.md").write_text("stray\n", encoding="utf-8")
    (tmp_path / "scratch.txt").write_text("stray\n", encoding="utf-8")
    (tmp_path / "code.py").write_text("x=1\n", encoding="utf-8")  # not doc-bearing
    config = {"root_allowlist": _ALLOWLIST}

    violations, examined = tsg.check_root_allowlist(tmp_path, config)

    assert examined == 4  # README, ascii-art, STRAY-NOTES, scratch — non-vacuous
    assert {v.path for v in violations} == {"STRAY-NOTES.md", "scratch.txt"}
    assert all(v.rule_id == "root_allowlist" for v in violations)


def test_root_allowlist_all_green(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("ok\n", encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text("ok\n", encoding="utf-8")
    config = {"root_allowlist": _ALLOWLIST}

    violations, examined = tsg.check_root_allowlist(tmp_path, config)

    assert violations == []
    assert examined == 2


def test_root_allowlist_non_vacuity_floor_raises(tmp_path: Path) -> None:
    config = {"root_allowlist": _ALLOWLIST}
    with pytest.raises(RuntimeError, match="non-vacuity guard"):
        tsg.check_root_allowlist(tmp_path, config, min_files=1)


def test_run_gates_end_to_end_advisory_vs_strict(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    styleguide = repo / "sg.yaml"
    styleguide.write_text(
        "structural_lint_config:\n  root_allowlist: [README.md]\n  concern_bucket_to_section: {}\n",
        encoding="utf-8",
    )
    base = _git(repo, "rev-parse", "HEAD").strip()
    # a touched docs page with no audience + a stray root file → findings
    _touch(repo / "docs" / "guides" / "p.md", _page({"title": "x"}))
    (repo / "STRAY.md").write_text("stray\n", encoding="utf-8")
    _commit_all(repo, "c")

    report = tsg.run_gates(base=base, repo_root=repo, styleguide_path=styleguide)

    assert report.touched_pages_examined == 1
    assert report.root_files_examined >= 1
    rule_ids = {v.rule_id for v in report.violations}
    assert {"audience_presence", "description_band", "root_allowlist"} <= rule_ids
    # advisory exit 0, strict exit 1
    assert tsg.main(["--base", base, "--repo-root", str(repo), "--styleguide", str(styleguide)]) == 0
    assert tsg.main(["--base", base, "--repo-root", str(repo), "--styleguide", str(styleguide), "--strict"]) == 1


# --------------------------------------------------------------------------- #
# T013 — rename / redirect reconciliation.
# --------------------------------------------------------------------------- #


def test_load_moves_absent_file_is_empty(tmp_path: Path) -> None:
    assert rr.load_moves(tmp_path / "nope.yaml") == []


def test_load_moves_parses_scalar_and_list_from(tmp_path: Path) -> None:
    occ = tmp_path / "occ.yaml"
    occ.write_text(
        "moves:\n"
        "  - {from: ['docs/reference/'], to: 'docs/api'}\n"
        "  - {from: 'docs/status-model.md', to: 'docs/architecture'}\n"
        "  - {from: ['research/'], to: 'RETIRE'}\n",
        encoding="utf-8",
    )
    moves = rr.load_moves(occ)
    assert [(m.from_paths, m.to) for m in moves] == [
        (("docs/reference/",), "docs/api"),
        (("docs/status-model.md",), "docs/architecture"),
        (("research/",), "RETIRE"),
    ]


def test_renames_and_deletions_from_git(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _touch(repo / "docs" / "old.md", "same content used for rename detection\n" * 5)
    _touch(repo / "docs" / "gone.md")
    _commit_all(repo, "seed")
    base = _git(repo, "rev-parse", "HEAD").strip()
    _git(repo, "mv", "docs/old.md", "docs/new.md")
    (repo / "docs" / "gone.md").unlink()
    _commit_all(repo, "move+delete")

    sources = rr.renames_and_deletions(base, repo)

    assert "docs/old.md" in sources  # rename → original path
    assert "docs/gone.md" in sources  # deletion


def test_check_renames_covered_flags_off_spine(tmp_path: Path) -> None:
    moves = [
        rr.Move(from_paths=("docs/reference/",), to="docs/api"),
        rr.Move(from_paths=("research/",), to="RETIRE"),
    ]
    sources = [
        "docs/reference/cli.md",  # covered by prefix
        "research/agent-x.md",  # covered (retired root dir)
        "docs/architecture/rogue.md",  # off-spine → flagged
    ]

    violations = rr.check_renames_covered(sources, moves)

    assert [v.path for v in violations] == ["docs/architecture/rogue.md"]
    assert violations[0].rule_id == "rename_reconcile"


def test_occurrence_subset_redirect_flags_missing_redirect(tmp_path: Path) -> None:
    moves = [
        rr.Move(from_paths=("docs/status-model.md",), to="docs/architecture"),
        rr.Move(from_paths=("docs/trail-model.md",), to="docs/architecture"),
        rr.Move(from_paths=("docs/reference/",), to="docs/api"),  # dir — skipped
        rr.Move(from_paths=("research/",), to="RETIRE"),  # retire — skipped
    ]
    redirect_keys = {"status-model.html"}  # trail-model missing

    violations = rr.check_occurrence_subset_redirect(moves, redirect_keys)

    assert [v.path for v in violations] == ["docs/trail-model.md"]
    assert violations[0].rule_id == "occurrence_subset_redirect"


def test_run_reconcile_end_to_end_with_fixtures(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _touch(repo / "docs" / "architecture" / "rogue.md", "off spine\n" * 5)
    _commit_all(repo, "seed")
    base = _git(repo, "rev-parse", "HEAD").strip()
    _git(repo, "rm", "-q", "docs/architecture/rogue.md")
    _commit_all(repo, "delete off-spine page")

    occ = repo / "occ.yaml"
    occ.write_text("moves:\n  - {from: ['docs/reference/'], to: 'docs/api'}\n", encoding="utf-8")
    red = repo / "red.yaml"
    red.write_text("{}\n", encoding="utf-8")

    report = rr.run_reconcile(base=base, repo_root=repo, occurrence_map_path=occ, redirect_map_path=red)

    assert report.renames_examined == 1  # non-vacuous
    assert report.moves_examined == 1
    assert any(v.rule_id == "rename_reconcile" for v in report.violations)
    # strict flips exit code
    assert (
        rr.main(
            [
                "--base",
                base,
                "--repo-root",
                str(repo),
                "--occurrence-map",
                str(occ),
                "--redirect-map",
                str(red),
            ]
        )
        == 0
    )
    assert (
        rr.main(
            [
                "--base",
                base,
                "--repo-root",
                str(repo),
                "--occurrence-map",
                str(occ),
                "--redirect-map",
                str(red),
                "--strict",
            ]
        )
        == 1
    )
