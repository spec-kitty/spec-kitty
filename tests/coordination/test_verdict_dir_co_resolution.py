"""SC-001 multi-consumer co-resolution + AST invariant (WP06, T055), and the
FR-007 concrete location gate (T034).

Two verifications SC-001 names were previously unowned (squad #3) -- this
file delivers both as real, runnable artifacts:

1. **US2 multi-consumer co-resolution** (empirical): under a real,
   materialized coordination topology (and, separately, a flat/single-branch
   one), record a verdict and assert the write, the safety verdict reader,
   the approval probe, and the pointer resolver all resolve the SAME
   directory -- the one ``_review_cycle_wp_dir`` (the T058 owner function,
   ``review/cycle.py``) itself resolves. Per that function's own docstring
   (WP06 correction, FR-011), every one of these consumers relies on its
   ``WORK_PACKAGE_TASK`` (PRIMARY-anchored) default and passes no ``kind``
   argument -- so today, under EVERY topology (coord-materialized or flat),
   they resolve the identical PRIMARY directory. (The "fix-mode" sites named
   in the WP prompt -- ``workflow_executor.py::implement_try_render_fix_mode_prompt``,
   ``workflow_cores.py::has_prior_rejection`` -- are covered structurally by
   the AST invariant below rather than direct invocation: both are large,
   side-effect-heavy orchestration functions, and their OWN source directly
   calls ``_review_cycle_wp_dir``/``_resolve_review_cycle_sub_artifact_dir``
   with the same 3-argument shape this file empirically proves co-resolves.)

2. **AST invariant** (structural, with a poison arm): no consumer resolves a
   review-cycle path from a caller-supplied directory (bypassing the shared
   owner function) or at a divergent ``kind``. A synthetic poison arm proves
   the invariant is non-vacuous (it actually reds on a real violation).

**FR-007 location gate (T034)**: parses the real, documented
``spec-kitty doctor review-cycle-reconcile --json`` command's output for a
clean fixture and asserts zero ``live_coord_pre_adr_primary_record``
findings -- the concrete, runnable form FR-007's pre-flip location gate
requires (not prose).
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tests.architectural._ast_scan import parse_source
from tests.integration.coord_topology_fixture import (  # noqa: F401
    CoordTopologyContext,
    FlatTopologyContext,
    coord_topology_mission,
    flat_topology_mission,
)

# Re-export the fixtures so pytest discovers them in this module.
__all__ = ["coord_topology_mission", "flat_topology_mission"]

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


# ---------------------------------------------------------------------------
# T055 (SC-001) -- US2 multi-consumer co-resolution.
# ---------------------------------------------------------------------------


def _resolved_dirs_for(repo_root: Path, mission_slug: str, wp_slug: str) -> dict[str, Path]:
    """Resolve *wp_slug*'s review-cycle directory via every named consumer's
    OWN real entry point (never re-deriving the join independently)."""
    from specify_cli.cli.commands.agent.tasks_verdict_persistence import (
        _resolve_verdict_wp_dir,
    )
    from specify_cli.cli.commands.agent.workflow_cores import (
        _resolve_review_cycle_sub_artifact_dir,
    )
    from specify_cli.review.cycle import _review_cycle_wp_dir

    feature_dir = repo_root / "kitty-specs" / mission_slug
    wp_path = feature_dir / "tasks" / f"{wp_slug}.md"

    return {
        "canonical (_review_cycle_wp_dir)": _review_cycle_wp_dir(
            repo_root, mission_slug, wp_slug
        ),
        "safety verdict reader (_resolve_verdict_wp_dir)": _resolve_verdict_wp_dir(wp_path),
        "approval probe (_resolve_review_cycle_sub_artifact_dir)": (
            _resolve_review_cycle_sub_artifact_dir(feature_dir, wp_slug)
        ),
    }


def _assert_all_co_resolve(resolved: dict[str, Path]) -> Path:
    values = list(resolved.values())
    canonical = values[0]
    for name, path in resolved.items():
        assert path == canonical, (
            f"co-resolution violated: {name!r} resolved {path}, expected the "
            f"SAME directory as every other consumer ({canonical}). Full set: {resolved}"
        )
    return canonical


def test_multi_consumer_co_resolution_under_coord_topology(
    coord_topology_mission: CoordTopologyContext,
) -> None:
    """Under a REAL, materialized coordination topology, the write seam, the
    safety verdict reader, and the approval probe all resolve the SAME
    directory -- and it is the SAME directory the WRITE actually used
    (``created.artifact_path.parent``), and the SAME directory the pointer
    resolver resolves back to given the pointer the write produced."""
    from specify_cli.review.cycle import create_rejected_review_cycle, resolve_review_cycle_pointer

    ctx = coord_topology_mission
    feedback = ctx.repo / "feedback.md"
    feedback.write_text("**Issue**: Missing regression test.\n", encoding="utf-8")

    created = create_rejected_review_cycle(
        main_repo_root=ctx.repo,
        mission_slug=ctx.slug,
        wp_id="WP01",
        wp_slug="WP01",
        feedback_source=feedback,
        reviewer_agent="reviewer-renata",
    )
    write_dir = created.artifact_path.parent

    resolved = _resolved_dirs_for(ctx.repo, ctx.slug, "WP01")
    resolved["write (create_rejected_review_cycle)"] = write_dir

    pointer_resolution = resolve_review_cycle_pointer(ctx.repo, created.pointer)
    assert pointer_resolution.path is not None, "pointer resolver must resolve the just-written artifact"
    resolved["pointer resolver (resolve_review_cycle_pointer)"] = pointer_resolution.path.parent

    canonical = _assert_all_co_resolve(resolved)
    # And it must be the PRIMARY dir -- the write-side default has NOT flipped
    # to COORD (WP13's disclosed finding; verified structurally, not asserted
    # by fiat): confirms this isn't six consumers agreeing on a wrong answer.
    assert canonical == ctx.primary_feature_dir / "tasks" / "WP01"


def test_multi_consumer_co_resolution_under_flat_topology(
    flat_topology_mission: FlatTopologyContext,
) -> None:
    """The same co-resolution guarantee holds under SINGLE_BRANCH/LANES (no
    coordination topology at all) -- one identical PRIMARY directory."""
    from specify_cli.review.cycle import create_rejected_review_cycle, resolve_review_cycle_pointer

    ctx = flat_topology_mission
    feedback = ctx.repo / "feedback.md"
    feedback.write_text("**Issue**: Missing regression test.\n", encoding="utf-8")

    created = create_rejected_review_cycle(
        main_repo_root=ctx.repo,
        mission_slug=ctx.slug,
        wp_id="WP01",
        wp_slug="WP01",
        feedback_source=feedback,
        reviewer_agent="reviewer-renata",
    )
    write_dir = created.artifact_path.parent

    resolved = _resolved_dirs_for(ctx.repo, ctx.slug, "WP01")
    resolved["write (create_rejected_review_cycle)"] = write_dir

    pointer_resolution = resolve_review_cycle_pointer(ctx.repo, created.pointer)
    assert pointer_resolution.path is not None
    resolved["pointer resolver (resolve_review_cycle_pointer)"] = pointer_resolution.path.parent

    canonical = _assert_all_co_resolve(resolved)
    assert canonical == ctx.primary_feature_dir / "tasks" / "WP01"


# ---------------------------------------------------------------------------
# T055 (SC-001) -- AST invariant: no divergent-kind / caller-supplied-dir
# consumer, with a synthetic poison arm proving non-vacuity.
# ---------------------------------------------------------------------------

_SANCTIONED_RESOLVER_NAME = "_review_cycle_wp_dir"
_SANCTIONED_KIND_ATTR = "REVIEW_CYCLE"  # the ONE sanctioned non-default kind override


def _iter_calls(node: ast.AST) -> list[ast.Call]:
    return [child for child in ast.walk(node) if isinstance(child, ast.Call)]


def _callee_name(call: ast.Call) -> str | None:
    func = call.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return None


def _kind_keyword_violations(tree: ast.AST, *, source_label: str) -> list[str]:
    """Return violation messages for every ``_review_cycle_wp_dir(...)`` call
    whose ``kind=`` keyword (if present) is anything other than the ONE
    sanctioned ``MissionArtifactKind.REVIEW_CYCLE`` override -- e.g. a
    divergent kind, or a non-constant/dynamic kind expression."""
    violations: list[str] = []
    for call in _iter_calls(tree):
        if _callee_name(call) != _SANCTIONED_RESOLVER_NAME:
            continue
        for kw in call.keywords:
            if kw.arg != "kind":
                continue
            value = kw.value
            is_sanctioned = (
                isinstance(value, ast.Attribute) and value.attr == _SANCTIONED_KIND_ATTR
            )
            if not is_sanctioned:
                violations.append(
                    f"{source_label}: {_SANCTIONED_RESOLVER_NAME}(...) called with a "
                    f"kind= argument other than MissionArtifactKind.{_SANCTIONED_KIND_ATTR}"
                )
    return violations


def _positional_arity_violations(tree: ast.AST, *, source_label: str) -> list[str]:
    """Return violation messages for every ``_review_cycle_wp_dir(...)`` call
    that does NOT pass exactly 3 positional arguments (repo_root, mission_slug,
    wp_slug) -- e.g. a caller threading in a pre-resolved/caller-supplied
    directory as a 4th positional, bypassing the identity-pair contract."""
    violations: list[str] = []
    for call in _iter_calls(tree):
        if _callee_name(call) != _SANCTIONED_RESOLVER_NAME:
            continue
        if len(call.args) != 3:
            violations.append(
                f"{source_label}: {_SANCTIONED_RESOLVER_NAME}(...) called with "
                f"{len(call.args)} positional args, expected exactly 3 "
                "(repo_root, mission_slug, wp_slug)"
            )
    return violations


def _check_source(text: str, *, source_label: str) -> list[str]:
    tree = parse_source(text, display=source_label)
    return _kind_keyword_violations(tree, source_label=source_label) + _positional_arity_violations(
        tree, source_label=source_label
    )


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "src" / "specify_cli").is_dir():
            return parent
    raise AssertionError("could not locate repo root from test file")


def test_no_consumer_calls_review_cycle_wp_dir_at_a_divergent_kind_or_caller_dir() -> None:
    """SC-001 AST invariant: every real ``_review_cycle_wp_dir(...)`` call
    site in ``src/`` passes exactly the 3-argument identity shape, and any
    ``kind=`` override is the one sanctioned ``REVIEW_CYCLE`` value."""
    root = _repo_root()
    violations: list[str] = []
    for path in sorted((root / "src").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if _SANCTIONED_RESOLVER_NAME not in text:
            continue
        relpath = path.relative_to(root).as_posix()
        violations.extend(_check_source(text, source_label=relpath))
    assert violations == [], "\n".join(violations)


def test_poison_divergent_kind_call_reds_the_invariant() -> None:
    """Non-vacuity: a synthetic consumer resolving at a DIVERGENT kind (not
    the sanctioned ``REVIEW_CYCLE`` override) is caught by the checker."""
    poison_source = (
        "from mission_runtime import MissionArtifactKind\n"
        "from specify_cli.review.cycle import _review_cycle_wp_dir\n\n"
        "def poisoned_consumer(repo_root, mission_slug, wp_slug):\n"
        "    return _review_cycle_wp_dir(\n"
        "        repo_root, mission_slug, wp_slug, kind=MissionArtifactKind.STATUS_STATE\n"
        "    )\n"
    )
    violations = _check_source(poison_source, source_label="synthetic_poison.py")
    assert violations, "the poison arm (divergent kind) must red the invariant, but nothing was flagged"


def test_poison_caller_supplied_dir_bypass_reds_the_invariant() -> None:
    """Non-vacuity: a synthetic consumer that resolves via a caller-supplied
    directory instead of the shared owner function (e.g. threading a 4th
    positional argument, an ad-hoc pre-resolved directory) is caught."""
    poison_source = (
        "from specify_cli.review.cycle import _review_cycle_wp_dir\n\n"
        "def poisoned_consumer(repo_root, mission_slug, wp_slug, caller_supplied_dir):\n"
        "    return _review_cycle_wp_dir(repo_root, mission_slug, wp_slug, caller_supplied_dir)\n"
    )
    violations = _check_source(poison_source, source_label="synthetic_poison.py")
    assert violations, "the poison arm (extra positional arg) must red the invariant, but nothing was flagged"


def test_clean_default_call_does_not_red_the_invariant() -> None:
    """Negative control: the real, sanctioned 3-arg default-kind shape must
    NOT be flagged (proving the checker isn't simply refusing every call)."""
    clean_source = (
        "from specify_cli.review.cycle import _review_cycle_wp_dir\n\n"
        "def clean_consumer(repo_root, mission_slug, wp_slug):\n"
        "    return _review_cycle_wp_dir(repo_root, mission_slug, wp_slug)\n"
    )
    assert _check_source(clean_source, source_label="synthetic_clean.py") == []


def test_clean_sanctioned_kind_override_does_not_red_the_invariant() -> None:
    """Negative control: the ONE sanctioned ``kind=REVIEW_CYCLE`` override
    must NOT be flagged."""
    clean_source = (
        "from mission_runtime import MissionArtifactKind\n"
        "from specify_cli.review.cycle import _review_cycle_wp_dir\n\n"
        "def clean_consumer(repo_root, mission_slug, wp_slug):\n"
        "    return _review_cycle_wp_dir(\n"
        "        repo_root, mission_slug, wp_slug, kind=MissionArtifactKind.REVIEW_CYCLE\n"
        "    )\n"
    )
    assert _check_source(clean_source, source_label="synthetic_clean.py") == []


# ---------------------------------------------------------------------------
# T034 -- FR-007 concrete LOCATION gate (real, runnable artifact).
# ---------------------------------------------------------------------------

_LIVE_COORD_PRE_ADR_CLASS = "live_coord_pre_adr_primary_record"

runner = CliRunner()


def test_doctor_review_cycle_reconcile_reports_zero_live_coord_pre_adr_findings(
    coord_topology_mission: CoordTopologyContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FR-007's pre-flip location gate, as a real, runnable artifact (not
    prose): parse ``spec-kitty doctor review-cycle-reconcile --json`` for a
    healthy, real coordination-topology mission and assert there are ZERO
    ``live_coord_pre_adr_primary_record`` findings across every report's
    ``findings`` array -- proving the current, correctly-behaving fixture
    does not strand a pre-ADR record now that the write seam and every
    reader co-resolve (per the tests above)."""
    import specify_cli.cli.commands.doctor as doctor_module

    ctx = coord_topology_mission
    monkeypatch.setattr(doctor_module, "locate_project_root", lambda *a, **k: ctx.repo)

    result = runner.invoke(
        doctor_module.app,
        ["review-cycle-reconcile", "--json", "--mission", ctx.slug],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    live_coord_findings = [
        finding
        for report in payload
        for finding in report["findings"]
        if finding["stranded_class"] == _LIVE_COORD_PRE_ADR_CLASS
    ]
    assert live_coord_findings == [], (
        f"expected zero {_LIVE_COORD_PRE_ADR_CLASS!r} findings for a healthy "
        f"fixture, got: {live_coord_findings}"
    )
