"""A shipped-skill edit runs the skill tests per PR (#7788, #7790).

#7769 edited two shipped skill files under ``src/charter/offering/skills/**`` and did
not regenerate ``src/specify_cli/skills/data/historical_skill_renders.json``. The
assertion that catches this, ``test_every_current_render_is_listed`` in
``tests/specify_cli/skills/test_historical_renders.py``, sat in an
``out_of_matrix_test_dirs`` directory, so no per-PR shard ran it and ``main`` went red
in the nightly only. The fix claims ``tests/specify_cli/skills`` in the ``cli`` module
row and fans the skill sources (and the digest generator) out to ``cli`` through the
NON-src ``skill_sources`` router group (``gate_selection.ASSET_SURFACE_MODULE_FANOUT``).

Every assertion drives the production entry points ``select_modules`` /
``out_of_matrix_test_paths``; none restates the routing.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from scripts.ci.gate_selection import (
    ASSET_SURFACE_MODULE_FANOUT,
    DEFAULT_REGISTRY_PATH,
    load_router,
    out_of_matrix_test_paths,
    select_gates,
    select_modules,
)

pytestmark = pytest.mark.fast

GROUP = "skill_sources"
DIGEST_TEST = "tests/specify_cli/skills/test_historical_renders.py"

#: #7769's changed-file list (the PR whose unregenerated digest list reddened the nightly).
PR_7769_PATHS: tuple[str, ...] = (
    "docs/api/agent-subcommands.md",
    "docs/changelog/unreleased/7677-review-skills-rejection-refused.fixed.md",
    "src/charter/offering/skills/spec-kitty-implement-review/references/rejection-loop-checklist.md",
    "src/charter/offering/skills/spec-kitty-runtime-review/SKILL.md",
    "src/specify_cli/_completion_manifest.json",
    "src/specify_cli/cli/commands/agent/tasks.py",
    "tests/cli/test_move_task_lane_help_7677.py",
    "tests/specify_cli/cli/commands/agent/fixtures/tasks_cli/help/move-task.help",
)

#: Paths whose edit changes what the digest assertion checks, each alone.
SKILL_SOURCE_PATHS: tuple[str, ...] = (
    "src/charter/offering/skills/spec-kitty-runtime-review/SKILL.md",
    "src/charter/offering/skills/spec-kitty-implement-review/references/rejection-loop-checklist.md",
    "src/charter/offering/skills/README.md",
    "scripts/skills/build_historical_skill_digests.py",
    "src/specify_cli/skills/data/historical_skill_renders.json",
)


def _digest_test_owners() -> frozenset[str]:
    """The modules whose shard EXECUTES the digest test: ``test_dirs``, else ``tests/<module>``.

    Not ``select_modules([DIGEST_TEST])``: that maps a test path to the modules a src change
    would select (the selection mirror), which is non-empty even for a nightly-only directory.
    """
    registry = yaml.safe_load(Path(DEFAULT_REGISTRY_PATH).read_text(encoding="utf-8"))
    owners = frozenset(
        str(row["module"])
        for row in registry["modules"]
        if any(DIGEST_TEST.startswith(f"{str(d).rstrip('/')}/") for d in (row.get("test_dirs") or [f"tests/{row['module']}"]))
    )
    assert owners, f"no module shard runs {DIGEST_TEST}"
    return owners


def test_skill_tests_are_in_the_per_pr_matrix() -> None:
    assert out_of_matrix_test_paths([DIGEST_TEST]) == ()
    assert "cli" in _digest_test_owners()


def test_replaying_pr_7769_runs_the_digest_test() -> None:
    """#7769's changed files, replayed, select a module whose shard runs the digest assertion."""
    assert select_modules(PR_7769_PATHS) & _digest_test_owners()


@pytest.mark.parametrize("path", SKILL_SOURCE_PATHS)
def test_a_skill_source_edit_alone_runs_the_digest_test(path: str) -> None:
    assert select_modules([path]) & _digest_test_owners()


def test_group_is_non_src_and_wired() -> None:
    """The group carries no ``src/`` glob, so it never masks FR-004, and fans out to ``cli``."""
    router = load_router()
    assert ASSET_SURFACE_MODULE_FANOUT[GROUP] == frozenset({"cli"})
    globs = router.filters[GROUP]
    assert globs and not any(glob.startswith("src/") for glob in globs), globs
    assert GROUP not in router.src_backed_groups
    selection = select_gates(["src/charter/offering/skills/spec-kitty-runtime-review/SKILL.md"], router=router)
    assert GROUP in selection.matched_groups
    assert not selection.unmatched_src


@pytest.mark.parametrize(
    "path",
    [
        "src/charter/offering/templates/README.md",
        "src/charter/offering/drg/merge.py",
        "scripts/ci/gate_selection.py",
    ],
)
def test_a_neighbouring_path_does_not_match_the_group(path: str) -> None:
    """Negative controls: a glob matching everything cannot satisfy the positives vacuously."""
    assert GROUP not in select_gates([path], router=load_router()).matched_groups
