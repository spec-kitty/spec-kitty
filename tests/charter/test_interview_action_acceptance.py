"""AC-8 — interview accepts declared, non-fast-path actions (#3596, WP02).

FR-008 (ADR 2026-08-21-1-charter-gate-predicate-inversion, squad note S6):
``validate_local_support_declarations`` now consults the fast-path
``BOOTSTRAP_ACTIONS`` constant PLUS a declared-node source (type-agnostic —
any label present on some DRG action node passes) as two explicit inputs, so
the fast-path set never becomes the closed acceptance allowlist. A
``local_supporting_files`` entry with ``action: tasks`` is now RETAINED, not
warn-dropped — ``tasks`` is a declared ``action:software-dev/tasks`` node
(``packs/built-in/action.graph.yaml``) even though it sits outside the
4-token fast-path set.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.activation.interview import (
    LocalSupportDeclaration,
    validate_local_support_declarations,
)

pytestmark = [pytest.mark.fast, pytest.mark.unit]


class TestDeclaredNonFastPathActionAccepted:
    def test_declared_non_fast_path_action_is_retained(self, tmp_path: Path) -> None:
        """RED BY DESIGN pre-fix: 'tasks' is outside BOOTSTRAP_ACTIONS and was
        unconditionally warn-dropped to action=None. Post-fix it is retained
        because it is a declared action:software-dev/tasks DRG node."""
        decls = [LocalSupportDeclaration(path="docs/guide.md", action="tasks")]

        valid, errors = validate_local_support_declarations(decls, repo_root=tmp_path)

        assert {v.path for v in valid} == {"docs/guide.md"}
        assert valid[0].action == "tasks", "declared action must be retained, not warn-dropped"
        assert errors == []

    def test_declared_retrospect_action_is_retained(self, tmp_path: Path) -> None:
        """action:documentation/retrospect and action:research/retrospect are
        also declared nodes; the acceptance source is type-agnostic (any
        label present on SOME action node passes, not just software-dev's)."""
        decls = [LocalSupportDeclaration(path="docs/guide.md", action="retrospect")]

        valid, errors = validate_local_support_declarations(decls, repo_root=tmp_path)

        assert valid[0].action == "retrospect"
        assert errors == []

    def test_genuinely_unknown_action_still_normalizes_to_none(self, tmp_path: Path) -> None:
        """A label reachable on NO action node anywhere is still rejected --
        the declared-node source widens acceptance, it does not disable it."""
        decls = [LocalSupportDeclaration(path="docs/guide.md", action="deploy")]

        valid, errors = validate_local_support_declarations(decls, repo_root=tmp_path)

        assert {v.path for v in valid} == {"docs/guide.md"}
        assert valid[0].action is None
        assert any("deploy" in e for e in errors)

    def test_malformed_project_drg_degrades_to_fast_path(self, tmp_path: Path) -> None:
        """A malformed overlay falls back to fast-path-only acceptance."""
        overlay = tmp_path / ".kittify" / "charter-packs" / "graph.yaml"
        overlay.parent.mkdir(parents=True)
        overlay.write_text(
            """\
            schema_version: '1.0'
            generated_at: STATIC
            generated_by: test
            nodes:
            - urn: action:software-dev/customstep
              kind: action
              label: customstep
            edges:
            - source: action:software-dev/customstep
              target: directive:does-not-exist
              relation: requires
            """,
            encoding="utf-8",
        )
        decls = [LocalSupportDeclaration(path="docs/guide.md", action="tasks")]

        valid, errors = validate_local_support_declarations(decls, repo_root=tmp_path)

        assert valid[0].action is None
        assert any("tasks" in error for error in errors)


class TestBackwardCompatibleWithoutRepoRoot:
    """repo_root is optional (existing callers, existing tests) -- omitting it
    degrades to fast-path-only acceptance, the pre-fix behaviour."""

    def test_fast_path_actions_still_accepted_without_repo_root(self) -> None:
        for action in ("specify", "plan", "implement", "review"):
            decls = [LocalSupportDeclaration(path="docs/guide.md", action=action)]
            valid, errors = validate_local_support_declarations(decls)
            assert valid[0].action == action
            assert errors == []

    def test_declared_action_without_repo_root_falls_back_to_warn_drop(self) -> None:
        """Without repo_root the declared-node source cannot be consulted, so
        a non-fast-path action degrades to the pre-fix warn-drop rather than
        silently accepting on no evidence."""
        decls = [LocalSupportDeclaration(path="docs/guide.md", action="tasks")]
        valid, errors = validate_local_support_declarations(decls)
        assert valid[0].action is None
        assert any("tasks" in e for e in errors)
