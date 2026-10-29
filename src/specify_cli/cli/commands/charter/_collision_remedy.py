"""Operator remedy for a synthesis URN collision, naming the colliding node's origin (#6510 / #4226, FR-007).

The core refusal (:class:`ProjectDRGValidationError`) is origin-neutral: the
synthesizer only sees one input graph. This CLI-side helper knows where the
project's directives live and which of them synthesis owns, so it says which
kind of node collided and how to recover:

* an activated project directive synthesis did not create (its ownership
  record does not list it): restore the record, or rename a hand-authored id;
* a project directive synthesis did create (should not collide; reported as such);
* a built-in or org node: synthesis never overwrites that doctrine;
* an unreadable ownership record or project directive file: named, never guessed.

No remedy ever advises deactivating the directive: that stops its delivery.
:func:`collision_remedy` only reads files; :func:`print_remedy_hint` is the one
console writer, so neither command function gains a branch for it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rich.markup import escape

from charter.activation.api import (
    MANIFEST_PATH,
    PROJECT_KIND_DIRS,
    ManifestIntegrityError,
    ProjectDirectiveScanError,
    ProjectDRGValidationError,
    SynthesisError,
    project_directive_ids,
    synthesis_owned_directive_ids,
)
from charter.drg import ArtifactKind
from kernel.charter_pack_paths import PROJECT_PACK_ROOT_POSIX

__all__ = ["collision_remedy", "print_remedy_hint", "remedy_lines"]

_DIRECTIVE = ArtifactKind.DIRECTIVE
_PROJECT_DIRECTIVE_DIR = PROJECT_KIND_DIRS[_DIRECTIVE]
_PROJECT_DIRECTIVE_LABEL = f"{PROJECT_PACK_ROOT_POSIX}/{_PROJECT_DIRECTIVE_DIR}/"
_KEEP_ACTIVE = "Do not deactivate it to get past this refusal; that stops agents receiving it."


def collision_remedy(repo_root: Path, error: SynthesisError) -> str | None:
    """Operator remedy for a synthesis URN collision, naming the colliding node's origin (FR-007).

    Returns ``None`` unless *error* is a :class:`ProjectDRGValidationError`
    that carries a ``colliding_urn``. The project pack is scanned at most once.
    """
    if not isinstance(error, ProjectDRGValidationError) or error.colliding_urn is None:
        return None
    urn = error.colliding_urn
    kind, _, directive_id = urn.partition(":")
    project_ids: frozenset[str] = frozenset()
    if kind == _DIRECTIVE.value:
        try:
            project_ids = project_directive_ids(repo_root)
        except ProjectDirectiveScanError as exc:
            # A scan failure (a malformed file, or an unlistable directory) must not
            # mask the caller's SynthesisError: report it as unreadable instead.
            return (
                f"'{urn}' collided, and the project directives under {_PROJECT_DIRECTIVE_LABEL} "
                f"could not be read to tell where it comes from ({exc.reason}). Repair them or make them readable, then re-run."
            )
    if directive_id not in project_ids:
        return (
            f"'{urn}' comes from the built-in or org doctrine layer. Synthesis never overwrites "
            "built-in or org doctrine; report the clash so the colliding synthesis id can change."
        )
    return _project_directive_remedy(repo_root, urn, directive_id, project_ids)


def _project_directive_remedy(repo_root: Path, urn: str, directive_id: str, project_ids: frozenset[str]) -> str:
    manifest = MANIFEST_PATH.as_posix()
    try:
        owned = bool(synthesis_owned_directive_ids(repo_root, [directive_id], project_ids=project_ids))
    except ManifestIntegrityError as exc:
        return (
            f"'{urn}' is an activated project directive, and the synthesis ownership record is unreadable "
            f"({exc.offending_artifact}, listed by {manifest}), so its origin cannot be told. "
            f"Restore {manifest} and its provenance sidecars from version control and re-run. {_KEEP_ACTIVE}"
        )
    if owned:
        return (
            f"'{urn}' is a project directive synthesis created ({manifest} records it) and should not "
            f"collide with its own target; report this as a defect. {_KEEP_ACTIVE}"
        )
    return (
        f"'{urn}' is an activated project directive that synthesis did not create: {manifest} does not record it. "
        f"If synthesis created it, restore {manifest} and its provenance sidecar from version control and re-run. "
        f"If you authored it by hand, give it an id synthesis does not generate. {_KEEP_ACTIVE}"
    )


def remedy_lines(remedy: str | None) -> list[str]:
    """The remedy as zero or one ``--json`` warning line."""
    return [remedy] if remedy else []


def print_remedy_hint(console: Any, remedy: str | None, *, json_output: bool) -> None:
    """Print the remedy as a human ``Hint:`` line; ``--json`` output carries it in the envelope instead."""
    if remedy and not json_output:
        console.print(f"[yellow]Hint:[/yellow] {escape(remedy)}", highlight=False)
