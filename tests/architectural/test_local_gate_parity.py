"""Local pre-PR gate-selection parity (FR-016 / #2476, WP18).

``scripts/ci/local_gate_parity.py`` (T095) is the local pre-PR consumer of
WP07's single gate-selection authority (``scripts/ci/gate_selection.py``):
it answers "which gates/shards will CI select for my current diff" **by
importing that authority**, never by re-encoding the path→group / group→job
routing a second time. Re-encoding would silently drift from CI's answer —
exactly the #2476 hazard the authority exists to close.

These tests are deliberately red-first (T094): before ``local_gate_parity.py``
exists, every test below fails for the right reason (a missing file / module,
not a routing disagreement) while still collecting cleanly on base — no
test does a module-level ``from scripts.ci.local_gate_parity import ...``,
so a missing module never breaks *collection*, only the assertions that read
or import it.

Two things are asserted, per the reviewer guidance in
``kitty-specs/ci-pipeline-reinstatement-01M1X35E/tasks/WP18-local-gate-parity.md``:

1. **Singularity** — the local module imports ``select_gates`` from
   ``scripts.ci.gate_selection`` and carries no second parser (no ``yaml``
   import, no ``fnmatch``-based glob matching of its own).
2. **Parity (#2476)** — for a docs-only diff, a single-module ``src/**``
   diff, and an unmatched ``src/**`` diff, the local selection is IDENTICAL
   to what ``select_gates`` (the CI-routing authority) returns for the same
   paths — proving there is one authority, reused, not two answers that
   happen to agree today and can silently diverge tomorrow.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from scripts.ci.gate_selection import Router, load_router, select_gates

pytestmark = pytest.mark.architectural

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LOCAL_PARITY_MODULE = _REPO_ROOT / "scripts" / "ci" / "local_gate_parity.py"


@pytest.fixture(scope="module")
def router() -> Router:
    return load_router()


def _read_local_parity_source() -> str:
    """Read the local consumer's source (red-first: raises pre-T095)."""
    return _LOCAL_PARITY_MODULE.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# T094 red-first anchor
# ---------------------------------------------------------------------------


def test_local_gate_parity_module_exists() -> None:
    """T095's deliverable must exist as the local pre-PR parity consumer."""
    assert _LOCAL_PARITY_MODULE.is_file(), (
        "scripts/ci/local_gate_parity.py must exist: the local pre-PR parity consumer of the gate-selection authority (#2476, T095)."
    )


# ---------------------------------------------------------------------------
# Singularity: one authority, imported, never re-encoded
# ---------------------------------------------------------------------------


def test_local_parity_imports_the_shared_authority() -> None:
    """The local module MUST import ``select_gates`` from ``scripts.ci.gate_selection``."""
    tree = ast.parse(_read_local_parity_source(), filename=str(_LOCAL_PARITY_MODULE))
    imported_from_authority = {
        alias.name for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module == "scripts.ci.gate_selection" for alias in node.names
    }
    assert "select_gates" in imported_from_authority, (
        "local_gate_parity.py must `from scripts.ci.gate_selection import select_gates` "
        "— the single authority WP07 built. An absent import here means the local path "
        "answers from somewhere else, reopening #2476."
    )


def test_local_parity_carries_no_second_parser() -> None:
    """Singularity guard: only ``gate_selection.py`` may parse the router YAML.

    A second hand-maintained routing map would show up as either a direct
    ``yaml`` import (re-parsing ``ci-router.yml`` independently) or an
    ``fnmatch``-based glob match reimplementing ``_match_groups``. Neither may
    appear in the local consumer.
    """
    source = _read_local_parity_source()
    tree = ast.parse(source, filename=str(_LOCAL_PARITY_MODULE))
    top_level_imports = {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names} | {
        node.module.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module
    }
    assert "yaml" not in top_level_imports, (
        "local_gate_parity.py imports `yaml` directly — that means it is parsing ci-router.yml itself instead of reusing scripts.ci.gate_selection (#2476 hazard)."
    )
    assert "fnmatch" not in source, (
        "local_gate_parity.py references `fnmatch` — that is gate_selection.py's own "
        "glob-matching internals; re-implementing it here is the #2476 second-parser hazard."
    )


# ---------------------------------------------------------------------------
# Parity proof (#2476): local selection == CI-routing selection, for the three
# concrete scenarios the WP calls out.
# ---------------------------------------------------------------------------


def test_docs_only_diff_local_parity_matches_ci_zero_shards(router: Router) -> None:
    """A docs-only diff selects zero code shards, identically, on both paths."""
    from scripts.ci.local_gate_parity import resolve_selection

    paths = ["docs/architecture/status-model.md"]
    ci_selection = select_gates(paths, router=router)
    local_selection = resolve_selection(paths, router=router)

    assert local_selection == ci_selection
    assert local_selection.selected_code_shards == frozenset()
    assert not local_selection.unmatched_src


def test_single_module_src_diff_local_parity_matches_ci(router: Router) -> None:
    """A single-module `src/**` diff selects that module's group + the battery + always-on gates, identically."""
    from scripts.ci.local_gate_parity import resolve_selection

    paths = ["src/specify_cli/consolidation/executor.py"]
    ci_selection = select_gates(paths, router=router)
    local_selection = resolve_selection(paths, router=router)

    assert local_selection == ci_selection
    assert "architectural-heavy" in local_selection.selected_code_shards
    assert local_selection.matched_groups == frozenset({"consolidation"})
    assert {"terminology", "layer-rules"} <= local_selection.selected_jobs


def test_unmatched_src_diff_local_parity_matches_ci_run_all(router: Router) -> None:
    """A no-group-match `src/**` diff forces fail-closed run-all, identically (#2476 proof)."""
    from scripts.ci.local_gate_parity import resolve_selection

    paths = ["src/specify_cli/__unmapped_probe__/thing.py"]
    ci_selection = select_gates(paths, router=router)
    local_selection = resolve_selection(paths, router=router)

    assert local_selection == ci_selection
    assert local_selection.unmatched_src is True
    assert local_selection.selected_code_shards == router.code_shard_jobs


def test_local_parity_report_carries_the_changed_paths_and_selection() -> None:
    """``build_report``/``ParityReport`` shape used by the CLI entrypoint (T096)."""
    from scripts.ci.local_gate_parity import ParityReport, build_report

    report = build_report(repo_root=_REPO_ROOT, base_ref="HEAD")
    assert isinstance(report, ParityReport)
    assert report.base_ref == "HEAD"
    assert report.changed_paths == ()  # HEAD..HEAD: no changes
    assert report.selection.selected_code_shards == frozenset()
