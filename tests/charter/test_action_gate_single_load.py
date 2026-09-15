"""NFR-001 / AC-7 — action gate single-graph-load budget + vocabulary fold (#3596).

WP02 (``rc3-charter-gate-predicate-inversion``, ADR
``2026-08-21-1-charter-gate-predicate-inversion``) moves the bundle resolve
*before* the ``mode`` decision for non-bootstrap actions, so the node-URN
membership predicate can test the actually-declared DRG action node. That
resolve MUST stay single-load: no second ``load_validated_graph`` call, and
NO memoization (a process-wide cache would serve stale graphs across
project/org overlay changes mid-process — see the ADR).

Two independent things are pinned here:

1. **Precheck** — ``_resolve_action_bundle`` itself (the seam
   ``build_charter_context_json`` reuses) calls ``load_validated_graph``
   exactly once. If this reds, the budget defect is upstream of the gate
   placement and the second test below would red for the wrong reason.
2. **The actual NFR-001 red-first test** — ``build_charter_context_json``
   with a genuinely non-bootstrap, DRG-declared action (``tasks``) still
   resolves the DRG exactly once end to end.

AC-7 (single vocabulary) is pinned in the same file: exactly one
``{"specify", "plan", "implement", "review"}``-shaped constant definition
exists under ``src/charter`` (``charter.activation.context.BOOTSTRAP_ACTIONS``) —
``interview.py``'s ``_KNOWN_ACTIONS`` copy must be gone.
"""

from __future__ import annotations

import ast
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

pytestmark = [pytest.mark.fast, pytest.mark.doctrine, pytest.mark.corpus]


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".kittify" / "charter").is_dir() and (parent / "pyproject.toml").is_file():
            return parent
    raise RuntimeError("could not locate repo root with .kittify/charter")


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Copy the checkout's activated charter into an isolated tmp project.

    No ``git init`` — ``build_charter_context_json`` never needs a git root
    (only ``build_charter_context``'s ``ensure_charter_bundle_fresh`` call
    does, and even that call's ``_bundle_root_for_json`` catch-all degrades
    to *repo_root* outside a git repo). Read-only DRG resolution only.
    """
    src = _repo_root()
    dst_kittify = tmp_path / ".kittify"
    dst_kittify.mkdir()
    shutil.copytree(
        src / ".kittify" / "charter",
        dst_kittify / "charter",
        ignore=shutil.ignore_patterns("context-state.json"),
    )
    shutil.copy(src / ".kittify" / "config.yaml", dst_kittify / "config.yaml")
    return tmp_path


def _counting_wrapper(original: object) -> tuple[object, list[object]]:
    calls: list[object] = []

    def _wrapped(*args: object, **kwargs: object) -> object:
        calls.append((args, kwargs))
        return original(*args, **kwargs)  # type: ignore[operator]

    return _wrapped, calls


def _write_malformed_project_drg(project: Path) -> None:
    overlay = project / ".kittify" / "doctrine" / "bad.graph.yaml"
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


class TestResolveActionBundleSingleLoad:
    """Precheck (NFR-001): ``_resolve_action_bundle`` loads the DRG once."""

    def test_resolve_action_bundle_loads_graph_exactly_once(self, project: Path) -> None:
        import charter.activation._drg_helpers as drg_helpers
        from charter.activation.action_doctrine_bundle import _resolve_action_bundle

        wrapped, calls = _counting_wrapper(drg_helpers.load_validated_graph)

        with patch("charter.activation._drg_helpers.load_validated_graph", side_effect=wrapped):
            bundle = _resolve_action_bundle(
                project,
                action="tasks",
                effective_depth=2,
                org_root=None,
                mission_type="software-dev",
                feature_dir=None,
            )

        assert bundle.merged is not None, "software-dev is a resolvable type; merged must carry the DRG"
        assert len(calls) == 1, f"_resolve_action_bundle must call load_validated_graph exactly once per invocation; observed {len(calls)} call(s)"


class TestActionGateSingleLoad:
    """NFR-001 (red-first): the JSON gate resolves the DRG exactly once."""

    def test_json_non_bootstrap_action_gate_triggers_exactly_one_load(self, project: Path) -> None:
        import charter.activation._drg_helpers as drg_helpers
        from charter.activation.context import build_charter_context_json

        wrapped, calls = _counting_wrapper(drg_helpers.load_validated_graph)

        with patch("charter.activation._drg_helpers.load_validated_graph", side_effect=wrapped):
            payload = build_charter_context_json(project, action="tasks", mission_type="software-dev")

        assert payload.get("mode") == "bootstrap"
        assert len(calls) == 1, (
            "build_charter_context_json(action='tasks', mission_type='software-dev') "
            f"must resolve the DRG exactly once (NFR-001, no memoization); "
            f"observed {len(calls)} loads"
        )


class TestMalformedProjectDrgDegrades:
    def test_malformed_project_drg_degrades_plain_text_context(self, project: Path) -> None:
        from charter.activation.context import build_charter_context

        _write_malformed_project_drg(project)

        result = build_charter_context(
            project,
            action="tasks",
            mission_type="software-dev",
        )

        assert result.mode == "compact"

    def test_malformed_project_drg_degrades_json_context(self, project: Path) -> None:
        from charter.activation.context import build_charter_context_json

        _write_malformed_project_drg(project)

        payload = build_charter_context_json(
            project,
            action="tasks",
            mission_type="software-dev",
        )

        assert payload["mode"] == "compact"


class TestBootstrapActionsSingleDefinitionSite:
    """AC-7 — the 4-token fast-path constant has exactly one definition site."""

    def test_only_context_py_defines_the_fast_path_constant(self) -> None:
        target = frozenset({"specify", "plan", "implement", "review"})
        charter_src = _repo_root() / "src" / "charter"
        definitions: list[str] = []

        for pyfile in charter_src.rglob("*.py"):
            try:
                tree = ast.parse(pyfile.read_text(encoding="utf-8"), filename=str(pyfile))
            except (SyntaxError, UnicodeDecodeError):
                continue
            for node in ast.walk(tree):
                # `BOOTSTRAP_ACTIONS: frozenset[str] = frozenset({...})` is an
                # `AnnAssign` (annotated assignment), not a plain `Assign` --
                # both shapes are checked so a future re-annotation (or an
                # un-annotated copy) is still caught.
                if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                    continue
                if node.value is None:
                    continue
                value = node.value
                # Unwrap `frozenset({...})` / `set({...})` calls to reach the
                # underlying literal.
                if isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id in ("frozenset", "set") and len(value.args) == 1:
                    value = value.args[0]
                if not isinstance(value, ast.Set):
                    continue
                elements: list[str] = []
                for elt in value.elts:
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                        elements.append(elt.value)
                    else:
                        break
                else:
                    if frozenset(elements) == target:
                        definitions.append(str(pyfile.relative_to(charter_src)))

        assert definitions == ["activation/context.py"], (
            "expected exactly one {'specify', 'plan', 'implement', 'review'}-shaped "
            f"constant definition, at src/charter/activation/context.py; found: {definitions}"
        )
