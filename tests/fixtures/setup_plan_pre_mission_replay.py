"""Replay the controlled setup-plan matrix against an isolated source tree."""

from __future__ import annotations

from contextlib import ExitStack
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

import typer
from pydantic import BaseModel, ConfigDict

from specify_cli.cli.commands.agent import mission as mission_mod
from specify_cli.cli.commands.agent import mission_branch_context
from specify_cli.cli.commands.agent import mission_setup_plan as seam
from specify_cli.runtime.resolver import TemplateConfigurationError

try:
    setup_plan_hosted_effects = importlib.import_module("specify_cli.cli.commands.agent.setup_plan_hosted_effects")
except ModuleNotFoundError:
    # The immutable pre-mission source predates the physical-effects module.
    setup_plan_hosted_effects = seam

CASES: dict[str, dict[str, object]] = {
    "substantive_complete": {"plan_substantive": True},
    "pristine_scaffold": {"plan_exists": False},
    "populated_insufficient": {},
    "committed_insufficient": {"plan_committed": True},
    "non_substantive_spec": {"spec_substantive": False},
    "uncommitted_spec": {"spec_committed": False},
    "missing_spec": {"spec_exists": False},
    "template_configuration": {"template_error": "configuration"},
    "missing_template": {"template_error": "missing"},
    "generic_local_exception": {"template_error": "generic"},
    "context_resolution": {"context_error": True},
    "git_preflight": {"git_error": True},
}


class ReplayResult(BaseModel):
    """Typed, test-local envelope for one immutable setup-plan replay."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    exit_code: int
    payload: dict[str, object]


def _normalize(value: object, root: Path) -> object:
    if isinstance(value, dict):
        return {key: _normalize(item, root) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize(item, root) for item in value]
    if isinstance(value, str):
        return value.replace(str(root.resolve()), "{{ROOT}}").replace(str(root), "{{ROOT}}")
    return value


def _invoke(case: dict[str, object]) -> ReplayResult:  # noqa: C901
    root = Path(tempfile.mkdtemp(prefix="setup-plan-pinned-replay-"))
    feature_dir = root / "kitty-specs" / "001-matrix"
    feature_dir.mkdir(parents=True)
    spec_file = feature_dir / "spec.md"
    plan_file = feature_dir / "plan.md"
    template = root / "plan-template.md"
    if bool(case.get("spec_exists", True)):
        spec_file.write_text(
            "# Spec\n\n## Functional Requirements\n\n- FR-001: Real content.\n",
            encoding="utf-8",
        )
    if bool(case.get("plan_exists", True)):
        plan_file.write_text("# Plan\n\nPopulated but insufficient.\n", encoding="utf-8")
    template.write_text(
        "# Plan\n\n## Technical Context\n\n**Language/Version**: [NEEDS CLARIFICATION]\n",
        encoding="utf-8",
    )
    emitted: list[dict[str, object]] = []

    def _is_substantive(path: Path, kind: str, *, mission_type: str = "software-dev") -> bool:
        if kind == "spec":
            return bool(case.get("spec_substantive", True))
        assert path == plan_file
        return bool(case.get("plan_substantive", False))

    def _is_committed(
        path: Path,
        _root: Path,
        diagnostics: list[str] | None = None,
    ) -> bool:
        if diagnostics is not None:
            diagnostics.append("matrix-surface")
        key = "spec_committed" if path.name == "spec.md" else "plan_committed"
        return bool(case.get(key, key == "spec_committed"))

    def _git_preflight(*_args: object, **_kwargs: object) -> None:
        if not bool(case.get("git_error")):
            return
        mission_mod._emit_json(
            {
                "result": "error",
                "error_code": "GIT_PREFLIGHT_FAILED",
                "error": "baseline git failure",
                "remediation": ["git worktree prune"],
            }
        )
        raise typer.Exit(1)

    def _find(*_args: object, **_kwargs: object) -> Path:
        if bool(case.get("context_error")):
            raise ValueError("context failure")
        return feature_dir

    def _resolve(*_args: object, **_kwargs: object) -> SimpleNamespace:
        error = case.get("template_error")
        if error == "configuration":
            raise TemplateConfigurationError(
                mission_type="software-dev",
                artifact_kind="plan",
                reason="has no configured template",
            )
        if error == "missing":
            raise FileNotFoundError("missing")
        if error == "generic":
            raise RuntimeError("generic local failure")
        return SimpleNamespace(path=template)

    with ExitStack() as stack:
        replacements: tuple[tuple[object, str, object], ...] = (
            (mission_mod, "_emit_json", lambda payload: emitted.append(dict(payload))),
            (mission_mod, "locate_project_root", lambda: root),
            (mission_mod, "_enforce_git_preflight", _git_preflight),
            (mission_mod, "_find_feature_directory", _find),
            (mission_mod, "_planning_read_dir", lambda *_args, **_kwargs: feature_dir),
            (mission_mod, "_show_branch_context", lambda *_args, **_kwargs: (root, "main")),
            (mission_mod, "get_current_branch", lambda _root: "main"),
            (mission_mod, "_branch_tree_relative_path", lambda path, _root: path.name),
            (
                mission_mod,
                "_commit_to_branch",
                lambda *_args, **_kwargs: seam.CommitToBranchResult("committed", "main", "abc123"),
            ),
            (
                seam,
                "resolve_planning_checkout_verdict",
                lambda *_args, **_kwargs: mission_branch_context.PlanningCheckoutVerdict("main", "main", "main"),
            ),
            (seam, "_resolve_plan_template", _resolve),
            (seam, "_emit_spec_plan_phase_events", lambda *_args, **_kwargs: None),
            (seam, "_run_documentation_wiring", lambda *_args, **_kwargs: (None, [])),
            (
                setup_plan_hosted_effects,
                "_trigger_dossier_sync",
                lambda *_args, **_kwargs: None,
            ),
            (mission_branch_context, "_utc_now_iso", lambda: "2026-08-23T00:00:00Z"),
        )
        for target, name, replacement in replacements:
            stack.enter_context(patch.object(target, name, replacement))
        stack.enter_context(patch("specify_cli.missions._substantive.is_substantive", _is_substantive))
        stack.enter_context(patch("specify_cli.missions._substantive.is_committed", _is_committed))
        stack.enter_context(patch.dict(os.environ, {"SPEC_KITTY_ENABLE_SAAS_SYNC": "0"}))
        exit_code = 0
        try:
            seam.setup_plan(feature="001-matrix", json_output=True)
        except typer.Exit as error:
            exit_code = error.exit_code

    assert len(emitted) == 1
    normalized = _normalize(emitted[0], root)
    assert isinstance(normalized, dict)
    return ReplayResult(
        exit_code=exit_code,
        payload=normalized,
    )


def main() -> None:
    source_root = Path(sys.argv[1]).resolve()
    loaded_module = Path(seam.__file__).resolve()
    if not loaded_module.is_relative_to(source_root / "src"):
        raise RuntimeError(f"replay imported outside pinned tree: {loaded_module}")
    print(
        json.dumps(
            {
                "loaded_module": str(loaded_module.relative_to(source_root)),
                "cases": {name: _invoke(case).model_dump(mode="json") for name, case in CASES.items()},
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
