"""Cross-axis integration: Slice F Axis 1 + Axis 2 + Axis 3 together.

FR-300 (broader): proves that the three Slice F axes interact correctly in a
single fixture — an org pack contributes DRG fragments (Axis 1), a monorepo
has per-package CharterScope resolution (Axis 2), and a custom workflow
sequence drives the next-action planner (Axis 3).

The fixture combines:
  - An org pack with a DRG fragment (Axis 1: three-layer DRG)
  - A monorepo layout with two charter scopes (Axis 2: CharterScope)
  - A mission with a custom workflow_id (Axis 3: composable workflow)

All three axes must work together without interfering with each other.

covers: FR-300 (broader) — expected GREEN at: WP12 final commit
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from textwrap import dedent

import pytest
import yaml

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_REPO_ROOT: Path = Path(__file__).resolve().parents[2]
_FIXTURE_ORG_PACK: Path = (
    _REPO_ROOT
    / "tests"
    / "architectural"
    / "_fixtures"
    / "org_packs"
    / "example_org"
)


# ---------------------------------------------------------------------------
# Shared fixture: complex setup combining all three Slice F axes
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_complex_setup(tmp_path: Path) -> Path:
    """Build a combined fixture: org pack + monorepo scopes + custom workflow.

    Layout::

        <tmp>/
          example_org/           # org pack (Axis 1)
            org-charter.yaml
            drg/fragment.yaml
          .kittify/
            config.yaml          # references org pack + charter_scopes
          packages/
            auth/.kittify/charter/charter.md
            auth/some/deep/dir/
            web/.kittify/charter/charter.md
          kitty-specs/
            demo-mission-01CROSS/
              meta.json          # workflow_id = our-team-design-first (Axis 3)
    """
    # Axis 1: copy the fixture org pack alongside the repo
    pack_dest = tmp_path / "example_org"
    if _FIXTURE_ORG_PACK.exists():
        shutil.copytree(_FIXTURE_ORG_PACK, pack_dest)
    else:
        # Minimal org pack if the fixture org pack doesn't exist
        pack_dest.mkdir(parents=True)
        (pack_dest / "org-charter.yaml").write_text(
            dedent("""\
                schema_version: "1.0"
                org_id: example-org
                required_directives: []
            """)
        )
        (pack_dest / "drg").mkdir()
        (pack_dest / "drg" / "fragment.yaml").write_text(
            dedent("""\
                schema_version: "1.0"
                pack_name: example-org
                nodes: []
                edges: []
            """)
        )

    # Axis 2: monorepo with two charter scopes
    (tmp_path / ".kittify").mkdir()
    config: dict = {
        "charter_packs": {"org": {"packs": [{"name": "example-org", "local_path": str(pack_dest)}]}},
        "charter_scopes": [
            {"root": "packages/auth", "name": "auth"},
            {"root": "packages/web", "name": "web"},
        ],
    }
    (tmp_path / ".kittify" / "config.yaml").write_text(yaml.safe_dump(config))
    (tmp_path / ".kittify" / "charter").mkdir()

    auth_root = tmp_path / "packages" / "auth"
    (auth_root / ".kittify" / "charter").mkdir(parents=True)
    (auth_root / ".kittify" / "charter" / "charter.md").write_text(
        "# Auth package charter\n"
    )
    (auth_root / "some" / "deep" / "dir").mkdir(parents=True)

    web_root = tmp_path / "packages" / "web"
    (web_root / ".kittify" / "charter").mkdir(parents=True)
    (web_root / ".kittify" / "charter" / "charter.md").write_text(
        "# Web package charter\n"
    )

    # Axis 3: mission with custom workflow_id
    mission_dir = tmp_path / "kitty-specs" / "demo-mission-01CROSS"
    mission_dir.mkdir(parents=True)
    (mission_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": "01CROSS000000000000000000",
                "mission_slug": "demo-mission",
                "mission_number": None,
                "friendly_name": "Cross-axis demo",
                "workflow_id": "our-team-design-first",
            }
        )
    )

    return tmp_path


# ---------------------------------------------------------------------------
# Axis 1 × Axis 2 × Axis 3 combined test
# ---------------------------------------------------------------------------


def test_org_pack_in_monorepo_with_custom_workflow(tmp_complex_setup: Path) -> None:
    """Axis 1 + Axis 2 + Axis 3 in one fixture.

    Verifies:
      1. (Axis 1) The org pack DRG fragment is loadable from the combined config;
         merged DRG carries provenance from the org layer.
      2. (Axis 2) CharterScope.resolve() selects the nearest enclosing scope for
         a path deep inside a monorepo package.
      3. (Axis 3) The custom workflow_id in meta.json produces a non-default
         next action for the mission planner.

    All three axes must operate without interfering with each other.
    """
    from charter.drg import DRGGraph
    from charter.activation.drg_activation import (
        load_org_drg,
        merge_three_layers,
    )

    # ---- Axis 1: three-layer DRG ----------------------------------------
    fragments = load_org_drg(tmp_complex_setup)
    assert len(fragments) >= 1, (
        "Axis 1 failure: expected at least one DRG fragment from the org pack"
    )
    assert fragments[0].pack_name == "example-org", (
        f"Axis 1 failure: wrong pack name {fragments[0].pack_name!r}"
    )

    built_in = DRGGraph(
        schema_version="1.0",
        generated_at="2026-05-18T00:00:00Z",
        generated_by="cross-axis-test",
        nodes=[],
        edges=[],
    )
    merged = merge_three_layers(
        built_in=built_in, org_fragments=fragments, project=None
    )
    assert merged is not None, "Axis 1 failure: merge_three_layers returned None"

    # ---- Axis 2: CharterScope monorepo resolution ------------------------
    from charter.activation.scope import CharterScope  # noqa: PLC0415

    deep_auth_path = tmp_complex_setup / "packages" / "auth" / "some" / "deep" / "dir"
    scope = CharterScope.resolve(tmp_complex_setup, deep_auth_path)
    assert scope is not None, (
        "Axis 2 failure: CharterScope.resolve returned None for deep auth path"
    )
    # The resolved scope should correspond to the auth package
    assert scope.name == "auth", (
        f"Axis 2 failure: expected scope name 'auth', got {scope.name!r}"
    )

    # ---- Axis 3: composable workflow next-action -------------------------
    from runtime.next._internal_runtime.planner import (  # noqa: PLC0415
        resolve_next_workflow_action,
    )

    mission_dir = tmp_complex_setup / "kitty-specs" / "demo-mission-01CROSS"
    result = resolve_next_workflow_action(
        mission_dir=mission_dir,
        current_action="plan",
    )
    assert result.next_action == "design-review", (
        f"Axis 3 failure: expected 'design-review' for our-team-design-first "
        f"workflow at action='plan', got {result.next_action!r}"
    )

    # ---- Cross-axis invariant: loading DRG did not disturb workflow ------
    # A second call to resolve_next_workflow_action must return the same result
    # (no global state pollution from Axis 1 or Axis 2 operations)
    result2 = resolve_next_workflow_action(
        mission_dir=mission_dir,
        current_action="plan",
    )
    assert result2.next_action == result.next_action, (
        "Cross-axis failure: resolve_next_workflow_action is not idempotent "
        "after org-pack DRG loading"
    )


def test_org_pack_drg_does_not_affect_default_workflow(
    tmp_complex_setup: Path,
) -> None:
    """Axis 1 × Axis 3 isolation: loading an org DRG must not alter the default
    workflow for a mission that does NOT set workflow_id."""
    from charter.activation.drg_activation import load_org_drg
    from runtime.next._internal_runtime.planner import (  # noqa: PLC0415
        resolve_next_workflow_action,
    )

    # Load org DRG (Axis 1 operation)
    _ = load_org_drg(tmp_complex_setup)

    # Create a mission with NO workflow_id
    mission_dir = tmp_complex_setup / "kitty-specs" / "default-mission-01DFLT"
    mission_dir.mkdir(parents=True)
    (mission_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": "01DFLT000000000000000000",
                "mission_slug": "default-mission",
                "mission_number": None,
            }
        )
    )

    result = resolve_next_workflow_action(
        mission_dir=mission_dir,
        current_action="plan",
    )
    # Default workflow: plan → tasks (not design-review)
    assert result.next_action == "tasks", (
        f"Cross-axis isolation failure: Axis 1 DRG load altered default "
        f"workflow; expected 'tasks', got {result.next_action!r}"
    )


def test_monorepo_scope_resolution_does_not_affect_drg(
    tmp_complex_setup: Path,
) -> None:
    """Axis 2 × Axis 1 isolation: resolving a charter scope must not alter the
    DRG fragment list."""
    from charter.activation.drg_activation import load_org_drg
    from charter.activation.scope import CharterScope  # noqa: PLC0415

    # Axis 2 operation first — resolve the web scope
    web_dir = tmp_complex_setup / "packages" / "web"
    _scope = CharterScope.resolve(tmp_complex_setup, web_dir)

    # Axis 1 operation: DRG fragment count must be stable
    fragments = load_org_drg(tmp_complex_setup)
    assert len(fragments) >= 1, (
        "Cross-axis isolation failure: CharterScope resolution altered DRG "
        "fragment list"
    )
    assert fragments[0].pack_name == "example-org", (
        f"Cross-axis isolation failure: DRG pack_name changed after scope "
        f"resolution; got {fragments[0].pack_name!r}"
    )


# ---------------------------------------------------------------------------
# LOW-6: Production prompt-path test for Axis 2 (post-merge remediation)
#
# Previously the cross-axis test invoked CharterScope.resolve directly.
# After HIGH-1 wiring, the production path (_governance_context via
# build_with_scope) must be exercised end-to-end.
#
# covers: FR-010 production path (LOW-6 / post-merge remediation cycle 1)
# ---------------------------------------------------------------------------


def test_governance_context_production_path_uses_monorepo_charter(
    tmp_complex_setup: Path,
) -> None:
    """Axis 2 production-path test: _governance_context(repo_root, feature_dir=...)
    MUST resolve to the nearest enclosing charter in a monorepo.

    This test drives the actual prompt-build production path — the same call
    chain an operator triggers when running `spec-kitty next` from a monorepo
    subpath. It does NOT call CharterScope.resolve directly; it exercises
    the prompt_builder._governance_context function which must now route
    through build_with_scope.

    Assertion: when feature_dir is inside packages/auth/, the resolved charter
    root used in the call to build_with_scope is the auth-package root
    (packages/auth/.kittify/), NOT the repository root. We verify this by
    capturing the repo_root argument that build_with_scope forwards to
    build_charter_context (which equals scope.root for the resolved scope).
    """
    import subprocess  # noqa: PLC0415

    # The complex setup has git-unaware directories; we need git for charter
    # resolution. Initialize a minimal git repo at tmp_complex_setup.
    subprocess.run(
        ["git", "init", "--initial-branch=main"],
        cwd=tmp_complex_setup,
        check=False,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_complex_setup,
        check=False,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_complex_setup,
        check=False,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "commit.gpgsign", "false"],
        cwd=tmp_complex_setup,
        check=False,
        capture_output=True,
    )

    from unittest.mock import patch  # noqa: PLC0415

    from charter.activation.context import CharterContextResult  # noqa: PLC0415
    from runtime.next.prompt_builder import _governance_context  # noqa: PLC0415

    repo_root = tmp_complex_setup
    deep_auth_path = repo_root / "packages" / "auth" / "some" / "deep" / "dir"

    # Capture which root build_with_scope resolves to. For the auth scope,
    # the resolved scope.root should be packages/auth, and build_with_scope
    # passes scope.root as the first positional argument to build_charter_context.
    captured_scope_roots: list[Path] = []

    def _capturing_build_charter_context(
        resolved_root: Path, **kwargs  # type: ignore[no-untyped-def]
    ) -> CharterContextResult:
        captured_scope_roots.append(resolved_root)
        # Return a minimal stub so the rest of the pipeline proceeds.
        from charter.activation.context import build_charter_context  # noqa: PLC0415
        try:
            return build_charter_context(resolved_root, **kwargs)
        except Exception:
            # If the stub charter isn't valid, return a dummy result.
            return CharterContextResult(
                mode="missing",
                text="Governance: stub",
                depth=0,
                loading_context=None,
            )

    with patch(
        "charter.activation.scope_router.build_charter_context",
        side_effect=_capturing_build_charter_context,
    ):
        _governance_context(repo_root, feature_dir=deep_auth_path, action="implement")

    assert captured_scope_roots, (
        "Axis 2 production-path failure: _governance_context with feature_dir "
        "inside packages/auth/ MUST route through build_with_scope, which calls "
        "build_charter_context with the per-package charter root. "
        "Currently build_with_scope is not called from _governance_context — "
        "the HIGH-1 wiring is missing."
    )

    # The resolved scope root must be the auth package root, NOT repo_root.
    resolved_root = captured_scope_roots[0]
    auth_root = repo_root / "packages" / "auth"
    assert resolved_root == auth_root, (
        f"Axis 2 production-path failure: expected scope root {auth_root}, "
        f"got {resolved_root}. _governance_context MUST resolve the nearest "
        f"enclosing charter for the given feature_dir, not always use repo_root."
    )
