"""Completeness assertion (WP06 / T027, C-008): issue-matrix JSON migration.

Closes out the FR-002 reader migration for write-side-seam-matrix-tracer-
01KYP3MH. WP05 introduced ``issue-matrix.json`` as the single canonical
artifact (with a legacy ``.md`` failover-read); WP08/WP09 switched the
individual code consumers; WP06 (this test) proves the class-closing
invariant across the WHOLE live-consumer set at once:

* every live consumer reads the issue-matrix through the ONE canonical
  reader (``validate_issue_matrix`` / ``issue_matrix_artifact_present`` /
  ``load_issue_matrix``) -- never a private markdown-only parse;
* no code path CREATES a fresh ``issue-matrix.md`` going forward (a legacy
  failover-read of an ALREADY-EXISTING ``.md`` is the only sanctioned
  touch-point -- see :mod:`specify_cli.tasks.issue_matrix_migration` and
  the #2804 legacy merge driver, neither of which is "emission");
* the finalize-time advisory lint BEHAVIOURALLY validates a JSON-only
  mission (the C1 net: the prior hardcoded ``.md`` ``.exists()`` precheck
  returned before ``validate_issue_matrix`` ever ran for exactly this
  mission shape -- a static import check would not have caught that).

Scope boundary (m2 / E2, WP06 prompt "Context"): the dashboard (net-new
build, follow-up #3068, parent epic #650) and ``policy/merge_gates.py``
(net-new reader, WP08/FR-004) are explicitly NOT migration targets -- they
were never ``.md`` consumers, so they are excluded from every assertion set
below by construction, and the exclusion itself is pinned at the bottom of
this file so a future edit cannot silently fold them back in.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

import specify_cli

pytestmark = [pytest.mark.architectural]

_SRC_ROOT = Path(specify_cli.__file__).resolve().parent
_REPO_ROOT = _SRC_ROOT.parents[1]

# Canonical + legacy filenames (S1192: each recurs >=3x below -- named once).
_ISSUE_MATRIX_JSON_FILENAME = "issue-matrix.json"
_ISSUE_MATRIX_MD_FILENAME = "issue-matrix.md"

# ---------------------------------------------------------------------------
# T027a -- every LIVE consumer module imports a canonical reader symbol
# ---------------------------------------------------------------------------

_CANONICAL_READER_SYMBOLS: frozenset[str] = frozenset(
    {"validate_issue_matrix", "issue_matrix_artifact_present", "load_issue_matrix"}
)

# The live consumer set (m2/E2 scope boundary, WP06 prompt "Context"): doctor,
# post-merge review (Gate 4), finalize-lint, and the shared approval-blocker
# rule. #5222 (F4) moved the approval-blocker's IMPLEMENTATION out of
# ``tasks_parsing_validation.py`` onto its own domain home,
# ``specify_cli.tasks.issue_matrix_approval`` (``policy.merge_gates`` reuses
# the same rule, so it needed a policy -> domain edge, not policy -> CLI);
# ``tasks_parsing_validation.py`` now only RE-EXPORTS the name (a plain
# ``from ... import X as X``, no canonical-reader import of its own left in
# its AST), so the module pinned here moved with the implementation.
# ``tasks_move_task.py`` imports ``_issue_matrix_approval_blocker`` FROM
# ``tasks_parsing_validation.py`` (the re-export), which resolves to the SAME
# function object this module's own call site does, so covering
# ``issue_matrix_approval.py`` covers the move-task/approval call site
# transitively -- it is not enumerated a second time here.
_LIVE_CONSUMER_MODULES: tuple[Path, ...] = (
    _SRC_ROOT / "status" / "doctor.py",
    _SRC_ROOT / "cli" / "commands" / "review" / "__init__.py",
    _SRC_ROOT / "tasks" / "issue_matrix_approval.py",
    _SRC_ROOT / "cli" / "commands" / "agent" / "mission_finalize.py",
)


def _imported_names(module_path: Path) -> set[str]:
    """Every name a module imports FROM another module, at ANY nesting depth.

    ``ast.walk`` descends into function bodies, so a deferred/local import
    (the prevailing style in this codebase for dodging import cycles -- e.g.
    ``mission_finalize.py``'s ``validate_issue_matrix`` import inside
    ``_advisory_issue_matrix_lint``) is found exactly like a module-level one.
    """
    tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                names.add(alias.asname or alias.name)
    return names


class TestLiveConsumersRouteThroughCanonicalReader:
    """No live consumer parses ``issue-matrix.md`` with a private markdown scan."""

    @pytest.mark.parametrize("module_path", _LIVE_CONSUMER_MODULES, ids=lambda p: p.name)
    def test_consumer_imports_a_canonical_reader_symbol(self, module_path: Path) -> None:
        imported = _imported_names(module_path)
        hit = imported & _CANONICAL_READER_SYMBOLS
        assert hit, (
            f"{module_path.relative_to(_REPO_ROOT)} imports none of "
            f"{sorted(_CANONICAL_READER_SYMBOLS)} -- it looks like it still "
            "parses issue-matrix.md directly instead of routing through the "
            "ONE canonical reader (C-008)."
        )


# ---------------------------------------------------------------------------
# T027b -- no code path CREATES a fresh issue-matrix.md going forward
# ---------------------------------------------------------------------------
#
# Behavioural (not a static grep): drive the two REAL creation entry points
# -- the canonical writer and the finalize-time scaffold -- against a
# hermetic tmp_path, with only the git-write-seam plumbing stubbed out, and
# assert neither ever materializes issue-matrix.md. A legacy mission's
# EXISTING .md is still read via failover (issue_matrix_migration.py) and
# the #2804 legacy merge driver (merge_driver.py::merge_driver_issue_matrix)
# still resolves conflicts on an ALREADY-EXISTING .md file for a
# not-yet-migrated mission -- neither of those is "emission" of a fresh
# file, so neither is asserted against here.


class _AlwaysUnprotectedPolicy:
    def is_protected(self, ref: str) -> bool:  # noqa: ARG002 - fixed-answer stub
        return False


def _stub_write_artifact_committed(monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.coordination import write_seam

    def _fake_write_artifact(**kwargs: object) -> write_seam.WriteSeamResult:
        # WP06 (#3073 / T029): issue_matrix.py now passes stage=, not the
        # historical pre-staged files= contract -- invoke it (mirroring
        # what production write_artifact does after a successful probe) so
        # this test's on-disk assertions still observe the materialized
        # file.
        stage = kwargs.get("stage")
        if callable(stage):
            stage()
        return write_seam.WriteSeamResult(
            status="committed",
            entry_id=str(kwargs["entry_id"]),
            destination_surface="main",
            commit_hash="deadbeef1234",
        )

    monkeypatch.setattr(write_seam, "write_artifact", _fake_write_artifact)


def test_canonical_writer_never_emits_markdown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from specify_cli.tasks.issue_matrix import IssueMatrixEntry, write_issue_matrix

    _stub_write_artifact_committed(monkeypatch)
    feature_dir = tmp_path / "kitty-specs" / "999-completeness-demo"
    feature_dir.mkdir(parents=True)

    write_issue_matrix(
        repo_root=tmp_path,
        mission_slug="999-completeness-demo",
        feature_dir=feature_dir,
        rows={"#1": IssueMatrixEntry(verdict="fixed", evidence_ref="ref")},
        policy=_AlwaysUnprotectedPolicy(),
    )

    assert (feature_dir / _ISSUE_MATRIX_JSON_FILENAME).exists()
    assert not (feature_dir / _ISSUE_MATRIX_MD_FILENAME).exists()


def test_finalize_scaffold_never_emits_markdown_for_a_fresh_mission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import mission_runtime
    from specify_cli.tasks.issue_matrix import scaffold_issue_matrix

    monkeypatch.setattr(mission_runtime, "coord_read_dir_for", lambda *a, **k: None)
    _stub_write_artifact_committed(monkeypatch)
    feature_dir = tmp_path / "kitty-specs" / "999-completeness-demo"
    feature_dir.mkdir(parents=True)
    spec_md = feature_dir / "spec.md"
    spec_md.write_text("Mission closes #1163.\n", encoding="utf-8")

    out_path = scaffold_issue_matrix(
        feature_dir,
        spec_md,
        repo_root=tmp_path,
        mission_slug="999-completeness-demo",
        policy=_AlwaysUnprotectedPolicy(),
    )

    assert out_path == feature_dir / _ISSUE_MATRIX_JSON_FILENAME
    assert out_path.exists()
    assert not (feature_dir / _ISSUE_MATRIX_MD_FILENAME).exists()


# ---------------------------------------------------------------------------
# T027c -- BEHAVIOURAL: finalize-lint validates a JSON-only mission (C1 net)
# ---------------------------------------------------------------------------
#
# The regression this closes (mission-review "correct-but-late" gap, #2223,
# reopened as C1 by this mission): the finalize-time advisory lint used a
# hardcoded ``issue-matrix.md`` ``.exists()`` precheck, so a JSON-only
# mission (no ``.md`` on disk at all) returned BEFORE ``validate_issue_matrix``
# ever ran -- silently skipping the lint. This drives the REAL phase function
# end-to-end against a tmp_path carrying ONLY ``issue-matrix.json`` (never
# touching ``issue-matrix.md``), not a static import check.


def test_finalize_lint_behaviourally_validates_a_json_only_mission(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from specify_cli.cli.commands.agent.mission_finalize import (
        _advisory_issue_matrix_lint,
    )

    planning_dir = tmp_path / "kitty-specs" / "999-json-only-demo"
    planning_dir.mkdir(parents=True)
    assert not (planning_dir / _ISSUE_MATRIX_MD_FILENAME).exists()
    (planning_dir / _ISSUE_MATRIX_JSON_FILENAME).write_text(
        json.dumps(
            {
                "schema_version": 1,
                "rows": {"#1": {"verdict": "not-a-real-verdict", "evidence_ref": "x"}},
            }
        ),
        encoding="utf-8",
    )

    _advisory_issue_matrix_lint(planning_dir, json_output=False)

    out = capsys.readouterr().out
    assert "Advisory" in out
    assert not (planning_dir / _ISSUE_MATRIX_MD_FILENAME).exists()


def test_finalize_lint_is_silent_for_a_valid_json_only_mission(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from specify_cli.cli.commands.agent.mission_finalize import (
        _advisory_issue_matrix_lint,
    )

    planning_dir = tmp_path / "kitty-specs" / "999-json-only-demo-valid"
    planning_dir.mkdir(parents=True)
    (planning_dir / _ISSUE_MATRIX_JSON_FILENAME).write_text(
        json.dumps(
            {"schema_version": 1, "rows": {"#1": {"verdict": "fixed", "evidence_ref": "x"}}}
        ),
        encoding="utf-8",
    )

    _advisory_issue_matrix_lint(planning_dir, json_output=False)

    out = capsys.readouterr().out
    assert "Advisory" not in out


# ---------------------------------------------------------------------------
# T027d -- doctrine/skills (M8/T025): name the JSON artifact, not bare .md
# ---------------------------------------------------------------------------


def test_doctrine_skills_name_the_json_artifact() -> None:
    """The two review skills must mention ``issue-matrix.json``.

    A skill is allowed to ALSO mention the legacy ``issue-matrix.md``
    failover (both do, describing back-compat) -- what must not happen is a
    skill teaching only the retired markdown path.
    """
    skill_paths = (
        _REPO_ROOT / "src/charter/offering/skills/spec-kitty-implement-review/SKILL.md",
        _REPO_ROOT / "src/charter/offering/skills/spec-kitty-mission-review/SKILL.md",
    )
    for skill_path in skill_paths:
        text = skill_path.read_text(encoding="utf-8")
        assert _ISSUE_MATRIX_JSON_FILENAME in text, (
            f"{skill_path.relative_to(_REPO_ROOT)} never mentions "
            f"{_ISSUE_MATRIX_JSON_FILENAME} -- still teaches the retired "
            "markdown path only."
        )


def test_glossary_pack_names_the_json_artifact() -> None:
    glossary_path = (
        _REPO_ROOT / "packs/built-in/glossary_packs/spec-kitty-core.glossary-pack.yaml"
    )
    text = glossary_path.read_text(encoding="utf-8")
    assert _ISSUE_MATRIX_JSON_FILENAME in text


# ---------------------------------------------------------------------------
# T027e -- excluded surfaces stay excluded (m2/E2 scope-boundary pin)
# ---------------------------------------------------------------------------


def test_merge_gates_is_a_net_new_json_reader_not_a_migration_target() -> None:
    """``policy/merge_gates.py`` (WP08/FR-004) is excluded from the live-
    consumer set above BY DESIGN -- it was never a markdown consumer; it
    gains its first issue-matrix reader here, JSON-first from day one (WP08
    module docstring). Pin both halves of that claim so a future edit can't
    silently fold it into (or drop the reason for excluding it from) the
    completeness set above.
    """
    merge_gates_path = _SRC_ROOT / "policy" / "merge_gates.py"
    assert merge_gates_path not in _LIVE_CONSUMER_MODULES
    text = merge_gates_path.read_text(encoding="utf-8")
    assert "load_issue_matrix" in text  # net-new reader, JSON-first by construction


def test_dashboard_is_excluded_pending_followup_3068() -> None:
    """The dashboard (net-new build, #3068, parent epic #650) is out of
    scope for this migration -- pin that the excluded surface exists and is
    not part of the live-consumer set enumerated above.
    """
    dashboard_dir = _SRC_ROOT / "dashboard"
    assert dashboard_dir.exists()  # sanity: the excluded surface really exists
    assert not any(dashboard_dir in module_path.parents for module_path in _LIVE_CONSUMER_MODULES)
