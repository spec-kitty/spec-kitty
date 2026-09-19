"""Workflow registry (FR-012, FR-015).

Loads project-authored and shipped workflow YAML files and returns validated
``WorkflowSequence`` instances.

Search precedence
-----------------
1. ``<project_root>/.kittify/overrides/workflows/<workflow_id>.workflow.yaml``
2. ``<project_root>/.kittify/overrides/workflows/<workflow_id>.yaml``
3. ``src/charter/offering/workflows/<workflow_id>.workflow.yaml`` (built-in defaults)
4. ``src/charter/offering/workflows/_fixtures/<workflow_id>.workflow.yaml`` (test fixtures)

Layer rule (C-001 / NFR-003)
-----------------------------
This module lives inside the runtime package
(``runtime.next._internal_runtime``).  It MUST NOT import from ``charter``
or ``doctrine`` (Python modules).  Doctrine YAML files are loaded
as raw data from disk; they are not imported as Python modules.

``kernel.clock`` is the one sanctioned exception (mission
``kernel-clock-single-door``, D-1): this invariant is about runtime
re-extractability -- not depending on doctrine-family internals -- not
about general purity. ``kernel`` is the stdlib-only layer floor every
package may import and carries no doctrine-family coupling, so a
``kernel.clock`` import does not violate the re-extractability rationale
this rule protects.

FR-015 — no silent fallback
----------------------------
If *workflow_id* does not match any file in the search roots,
``UnknownWorkflowError`` is raised with a message that names the unknown id
AND lists all currently available workflows.  Callers MUST NOT silently
fall back to ``software-dev-default``; fall-back logic belongs in the
caller (currently WP11's ``planner.plan_next``).
"""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import ValidationError
import yaml

from kernel.errors import GuardedReadError
from kernel.guarded_read import read_guarded

from .workflow_schema import WorkflowSequence

__all__ = [
    "UnknownWorkflowError",
    "WorkflowFileError",
    "get_workflow",
    "list_available_workflows",
    "load_workflow_file",
    "resolve_workflow_path",
]


class UnknownWorkflowError(GuardedReadError):
    """Raised when *workflow_id* cannot be resolved to a workflow YAML file.

    FR-015 binding: this exception MUST name the unknown id AND list the
    currently available workflow ids.  The caller MUST NOT silently fall back
    to ``software-dev-default``.

    Also raised by the slug validator (MEDIUM-4 / post-merge remediation
    cycle 1) when *workflow_id* does not match ``[a-z0-9][a-z0-9-]*``.
    In that case the message begins with "Invalid workflow_id" to distinguish
    validation rejection from a normal lookup miss.

    Re-parented onto :class:`kernel.errors.GuardedReadError` (mission
    ``cli-error-surface-seam-01M2WJD2``, WP02, binding squad amendment #1) so
    the global CLI error-presentation hook renders it instead of letting it
    traceback. Raise sites here pass a single positional message and leave
    ``path``/``reason`` unset (``None``); the hook's fallback ``str(exc)``
    reproduces the exact pre-existing wording, so this is presentation-only
    churn, not a behavior change (spec.md Edge Cases).
    """


class WorkflowFileError(GuardedReadError):
    """A workflow YAML file could not be read or failed schema validation.

    Raised by :func:`load_workflow_file` (via
    :func:`kernel.guarded_read.read_guarded`) for an unreadable file, a
    malformed-YAML file, or a file that fails :class:`WorkflowSequence`
    validation (including a wrong top-level type, e.g. a YAML list instead of
    a mapping — pydantic raises ``ValidationError`` for that shape too).
    Co-located with :func:`load_workflow_file`, the function it guards
    (mission ``cli-error-surface-seam-01M2WJD2``, WP02, C-002: single
    canonical authority for this failure mode).

    Overrides ``__str__`` to name the offending file (``contracts/
    error-envelope.md``'s worked example: ``"workflow file 'bad.yaml' is not
    valid: while parsing a block mapping ..."``) — ``read_guarded`` always
    constructs this error with ``path``/``reason`` set from the collapsed
    exception, so both the stderr line and the ``--json`` envelope's
    ``error`` field (both render via ``str(exc)``) name the file.
    """

    def __str__(self) -> str:
        if self.path is not None and self.reason is not None:
            return f"workflow file {self.path!r} is not valid: {self.reason}"
        return super().__str__()


# Defense-in-depth validator (MEDIUM-4, post-merge remediation cycle 1,
# 2026-05-19). workflow_id originates from operator-authored meta.json; an
# adversarial value such as "../../evil" must be rejected before the string
# is interpolated into a filesystem path. The .workflow.yaml suffix alone
# is insufficient protection for all traversal patterns.
# Pattern: must start with [a-z0-9] and contain only [a-z0-9-] characters.
_WORKFLOW_ID_PATTERN: re.Pattern[str] = re.compile(r"[a-z0-9][a-z0-9-]*")


# ---------------------------------------------------------------------------
# Search roots — resolved relative to this file so the registry works both
# in a source-checkout and after installation via pip / uv.
#
# Path(__file__).resolve() is e.g.:
#   <repo>/src/runtime/next/_internal_runtime/workflow_registry.py
# parents[4] is <repo>/  (src/ is parents[3], runtime is parents[2],
#   next is parents[1], _internal_runtime is parents[0] — count:
#   0: _internal_runtime/
#   1: next/
#   2: runtime/
#   3: src/
#   4: <repo root>
# So parents[3] / "charter" / "offering" / "workflows" is the canonical root
# (mission charter-code-topology-01M152G1 relocated src/charter/offering/ to
# src/charter/offering/).
# ---------------------------------------------------------------------------
_RUNTIME_FILE = Path(__file__).resolve()
_SRC_ROOT = _RUNTIME_FILE.parents[3]  # …/src/
_WORKFLOWS_ROOT = _SRC_ROOT / "charter" / "offering" / "workflows"

_SEARCH_ROOTS: tuple[Path, ...] = (
    _WORKFLOWS_ROOT,
    _WORKFLOWS_ROOT / "_fixtures",
)


def get_workflow(workflow_id: str, project_root: Path | None = None) -> WorkflowSequence:
    """Return the validated ``WorkflowSequence`` for *workflow_id*.

    Search order: project overrides first when *project_root* is provided,
    then built-in defaults, then test fixtures (see module docstring for the
    full precedence list).

    Raises
    ------
    UnknownWorkflowError
        If *workflow_id* fails the slug validator or cannot be resolved to
        any file in the search roots. The exception message begins with
        "Invalid workflow_id" for validator failures and "Unknown workflow_id"
        for lookup misses (FR-015 binding, MEDIUM-4).
    pydantic.ValidationError
        If the resolved YAML file fails ``WorkflowSequence`` validation.
    """
    candidate = resolve_workflow_path(workflow_id, project_root=project_root)
    return load_workflow_file(candidate, requested_workflow_id=workflow_id)


def resolve_workflow_path(workflow_id: str, project_root: Path | None = None) -> Path:
    """Return the source YAML path for *workflow_id* using registry precedence."""
    validate_workflow_id(workflow_id)
    for candidate in _candidate_paths(workflow_id, project_root):
        if candidate.exists():
            return candidate

    available = list_available_workflows(project_root=project_root)
    raise UnknownWorkflowError(
        f"Unknown workflow_id={workflow_id!r}. Available: {available}. Searched: {[str(p) for p in _candidate_paths(workflow_id, project_root)]}."
    )


def load_workflow_file(
    path: Path,
    requested_workflow_id: str | None = None,
) -> WorkflowSequence:
    """Load and validate a workflow YAML file.

    Raises
    ------
    WorkflowFileError
        If *path* cannot be read (``OSError``), is not valid YAML
        (``yaml.YAMLError``), or fails ``WorkflowSequence`` validation
        (``pydantic.ValidationError`` — this also covers a wrong top-level
        type, e.g. a YAML list instead of a mapping). Collapsed via
        :func:`kernel.guarded_read.read_guarded` (mission
        ``cli-error-surface-seam-01M2WJD2``, WP02) so the global CLI
        error-presentation hook renders a clean message instead of a
        traceback.
    UnknownWorkflowError
        If *workflow_id* fails the slug validator, or *requested_workflow_id*
        is given and does not match the file's declared ``workflow_id``.
    """
    workflow = read_guarded(
        path,
        _parse_workflow,
        errors=(yaml.YAMLError, ValidationError),
        error_cls=WorkflowFileError,
    )
    validate_workflow_id(workflow.workflow_id)
    if requested_workflow_id is not None and workflow.workflow_id != requested_workflow_id:
        raise UnknownWorkflowError(f"Workflow file {path} declares workflow_id={workflow.workflow_id!r} but was requested as {requested_workflow_id!r}.")
    return workflow


def _parse_workflow(content: bytes | str) -> WorkflowSequence:
    """Decode YAML *content* and validate it against ``WorkflowSequence``.

    The ``parse`` callable :func:`load_workflow_file` hands to
    :func:`kernel.guarded_read.read_guarded`; kept as a module-level function
    (rather than a closure) so its two declared failure modes
    (``yaml.YAMLError``, ``pydantic.ValidationError``) are easy to trace back
    to this single call site. Typed ``bytes | str`` to match
    :func:`read_guarded`'s ``parse`` signature even though ``load_workflow_file``
    always calls it in ``mode="text"`` (``str``).
    """
    raw = yaml.safe_load(content)
    return WorkflowSequence.model_validate(raw)


def validate_workflow_id(workflow_id: str) -> None:
    """Reject workflow ids that cannot be safely interpolated into paths."""
    if not _WORKFLOW_ID_PATTERN.fullmatch(workflow_id):
        raise UnknownWorkflowError(
            f"Invalid workflow_id {workflow_id!r}: must match [a-z0-9][a-z0-9-]*. "
            f"Path-traversal sequences, uppercase letters, spaces, and special "
            f"characters are not permitted in workflow identifiers."
        )


def list_available_workflows(project_root: Path | None = None) -> list[str]:
    """Return a sorted list of validated workflow ids resolvable from the search roots."""
    available: list[str] = []
    for root in _search_roots(project_root):
        if root.exists():
            for p in sorted(root.glob("*.yaml")):
                workflow_id = _workflow_id_from_path(p)
                try:
                    validate_workflow_id(workflow_id)
                    load_workflow_file(p, requested_workflow_id=workflow_id)
                except (WorkflowFileError, UnknownWorkflowError):
                    # Swallow-to-skip (deliberate, distinct from the WP02
                    # presentation guard): an unreadable/malformed/wrong-schema
                    # file is simply "not listed", never a presentation error.
                    # Since load_workflow_file (WP02) now collapses the raw
                    # OSError/pydantic.ValidationError/yaml.YAMLError it used
                    # to raise directly into WorkflowFileError, this tuple
                    # names WorkflowFileError (a superset of the old trio) to
                    # keep that swallow contract behaviorally unchanged.
                    continue
                available.append(workflow_id)
    return sorted(set(available))


def _search_roots(project_root: Path | None) -> tuple[Path, ...]:
    project_roots: tuple[Path, ...] = ()
    if project_root is not None:
        project_roots = (Path(project_root) / ".kittify" / "overrides" / "workflows",)
    return project_roots + _SEARCH_ROOTS


def _candidate_paths(workflow_id: str, project_root: Path | None) -> tuple[Path, ...]:
    project_paths: tuple[Path, ...] = ()
    if project_root is not None:
        override_root = Path(project_root) / ".kittify" / "overrides" / "workflows"
        project_paths = (
            override_root / f"{workflow_id}.workflow.yaml",
            override_root / f"{workflow_id}.yaml",
        )
    shipped_paths = tuple(root / f"{workflow_id}.workflow.yaml" for root in _SEARCH_ROOTS)
    return project_paths + shipped_paths


def _workflow_id_from_path(path: Path) -> str:
    name = path.name
    if name.endswith(".workflow.yaml"):
        return name[: -len(".workflow.yaml")]
    return path.stem


def _clear_noop_cache() -> None:
    """Compatibility no-op for tests and callers that cleared the old cache."""


get_workflow.cache_clear = _clear_noop_cache  # type: ignore[attr-defined]
