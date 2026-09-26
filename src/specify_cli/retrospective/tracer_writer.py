"""Tracer finding writer (FR-006 / WP10 -- the mission's one genuine must-build).

Appends a dated, actor-attributed finding to a ``traces/<category>.md`` file,
routed to the COORD surface through the WP03 seam
(:func:`~specify_cli.coordination.write_seam.write_artifact`, which composes
:meth:`~mission_runtime.PlacementSeam.write_target` +
:func:`~specify_cli.coordination.commit_router.commit_for_mission`) -- never a
bespoke compute-and-commit path (data-model.md "Tracer finding entry").

**Ledger-M16 (I-T4):** this module calls the WRITE leaf
(``write_target(TRACER_FILE)``, via ``write_artifact``) directly. It never
routes through ``placement_seam(...).read_dir(MissionArtifactKind.RETROSPECTIVE)``
-- that short-circuit belongs to :mod:`specify_cli.retrospective.writer` /
:mod:`specify_cli.retrospective.generator` and reaching it from a TRACER_FILE
write would recurse into unrelated retrospective-home resolution. Reading the
CURRENT tracer content (below, to merge-not-clobber the coord-authoritative
file) uses ``read_dir(MissionArtifactKind.TRACER_FILE)`` instead -- a
different kind, not the forbidden RETROSPECTIVE short-circuit, and a plain
read of the artifact this module owns.

**Why a read-before-write at all:** :func:`~specify_cli.coordination.
commit_router._materialise_coord_worktree`'s staging step
(``shutil.copy2``) unconditionally OVERWRITES the coord worktree's copy of
the staged file with the local one this module writes. Staging a
locally-composed category file that omits entries another agent already
landed on the coord branch would silently clobber them. So this module reads
the CURRENT coord-resolved content first, appends the new entry only if it is
not already present, and stages the MERGED result -- never a fresh,
from-scratch file.

**Idempotence (I-T3 / FR-012):** when the formatted entry line is already
present in the current coord content, the merged content is byte-identical to
what commit_for_mission would stage, so its own git-level "nothing to
commit" detection reports ``"unchanged"`` -- no bespoke short-circuit is
implemented here; the mission's existing idempotence contract is inherited
verbatim (mirrors the write_seam module docstring).

**Attribution guard (#2960 / I-T2):** ``actor`` is required and must not be
blank -- :class:`TracerAttributionError` guards this so a finding can never be
persisted with a blanked/empty attribution.
"""

from __future__ import annotations

import hashlib
from kernel.clock import date, now_utc
from pathlib import Path

from mission_runtime import ActionContextError, MissionArtifactKind, placement_seam

from specify_cli.coordination.surface_resolver import CoordinationWorktreeUnmaterialized
from specify_cli.coordination.write_seam import (
    ProtectionPolicyLike,
    WriteSeamResult,
    write_artifact,
)
from specify_cli.missions._read_path_resolver import (
    StatusReadPathNotFound,
    candidate_feature_dir_for_mission,
)

__all__ = [
    "TRACER_CATEGORIES",
    "TracerAttributionError",
    "TracerCategoryError",
    "append_tracer_finding",
]

_TRACES_DIRNAME = "traces"
_ENTRY_SEPARATOR = " · "  # middle dot, matching the seeded traces/*.md format

# The three category files the tracer domain recognises (data-model.md "Tracer
# finding entry" / contracts/commands.md `tracer-append`). ONE spelling of the
# vocabulary -- the CLI layer's ``--category`` choices are drawn from this same
# mapping rather than restating the three literals.
TRACER_CATEGORIES: dict[str, str] = {
    "tooling-friction": "tooling-friction.md",
    "approach": "approach.md",
    "design-decisions": "design-decisions.md",
}

# Read-side resolution failures that mean "no coord surface materialised yet" --
# the SAME caught set write_seam.py's own FR-011 probe uses (mirrored, not
# imported, since it is that module's private detail): a genuine mission-
# resolution failure here degrades to an empty base (write_artifact's own
# probe is the canonical refusal authority for the ACTUAL write).
#
# #4959 (WP02 / T007) carve-out: ``CoordinationWorktreeUnmaterialized`` IS a
# ``StatusReadPathNotFound`` subclass, so it would otherwise be caught by this
# same tuple and degraded to "" -- exactly the #4959 bug (the writer then
# clobbers a real, already coord-committed ``traces/<cat>.md`` with a
# from-scratch header). It is excluded here and given its own, earlier
# ``except`` arm in ``_read_current_coord_content`` that re-raises instead:
# the coordination branch is NOT lost (unlike a genuinely absent/unroutable
# mission), only not yet materialised on disk, so the read must fail closed
# rather than silently substitute emptiness for the real document.
_NO_EXISTING_CONTENT_EXCEPTIONS: tuple[type[Exception], ...] = (
    ActionContextError,
    StatusReadPathNotFound,
    FileNotFoundError,
)


class TracerAttributionError(ValueError):
    """Raised when ``actor`` is missing or blank (#2960 attribution guard)."""


class TracerCategoryError(ValueError):
    """Raised when ``category`` is not a recognised tracer category."""


def _require_actor(actor: str) -> str:
    """Guard non-blank attribution (#2960 / I-T2). Returns the stripped actor."""
    stripped = actor.strip() if actor else ""
    if not stripped:
        raise TracerAttributionError(
            "tracer-append requires a non-empty --actor; a blank actor would "
            "silently blank attribution on the persisted finding (#2960)."
        )
    return stripped


def _category_filename(category: str) -> str:
    try:
        return TRACER_CATEGORIES[category]
    except KeyError:
        raise TracerCategoryError(
            f"Unknown tracer category {category!r}; expected one of "
            f"{sorted(TRACER_CATEGORIES)}"
        ) from None


def _default_header(category: str) -> str:
    return (
        f"# Tracer: {category}\n\n"
        "One entry per finding: `YYYY-MM-DD · actor · <text>`.\n\n"
        "---\n"
    )


def _format_entry_line(*, entry_date: date, actor: str, entry: str) -> str:
    body = entry.strip()
    return _ENTRY_SEPARATOR.join([entry_date.isoformat(), actor, body])


def _entry_present(content: str, entry_line: str) -> bool:
    return entry_line in content.splitlines()


def _append_entry(content: str, entry_line: str) -> str:
    trimmed = content.rstrip("\n")
    return f"{trimmed}\n\n{entry_line}\n"


def _read_current_coord_content(
    repo_root: Path, mission_slug: str, filename: str
) -> str:
    """Read the CURRENT coord-resolved category file, or "" when absent.

    Routes through ``read_dir(MissionArtifactKind.TRACER_FILE)`` -- a plain
    read of this module's own artifact kind, NOT the forbidden
    ``read_dir(RETROSPECTIVE)`` short-circuit (Ledger-M16 / I-T4 concerns only
    the latter). A resolution failure that means "no coord surface concept
    applies at all" (no mission, an unresolvable handle) degrades to an empty
    base: the subsequent write still goes through
    :func:`~specify_cli.coordination.write_seam.write_artifact`, whose own
    FR-011 probe is the canonical authority for reporting an unroutable
    target as a structured refusal.

    Fails closed instead of degrading (#4959 / WP02 / T007) on:

    * :class:`~specify_cli.coordination.surface_resolver.
      CoordinationWorktreeUnmaterialized` -- the coordination branch exists
      and is NOT lost, only not yet materialised on disk. Degrading this to
      ``""`` would make the caller believe there is no existing content,
      and the writer would then clobber the real, already coord-committed
      file with a from-scratch header (module docstring "Why a
      read-before-write at all").
    * ``UnicodeDecodeError`` on an EXISTING category file -- corruption is
      not "no content"; refusing (propagating) is the only safe response.
    """
    try:
        traces_dir = placement_seam(repo_root, mission_slug).read_dir(
            MissionArtifactKind.TRACER_FILE
        )
    except CoordinationWorktreeUnmaterialized:
        raise
    except _NO_EXISTING_CONTENT_EXCEPTIONS:
        return ""
    category_path = traces_dir / _TRACES_DIRNAME / filename
    if not category_path.is_file():
        return ""
    try:
        return category_path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _local_staging_path(repo_root: Path, mission_slug: str, filename: str) -> Path:
    # Routes through the canonical topology-aware read primitive (C-005/FR-002,
    # test_single_mission_surface_resolver.py) instead of a raw mission-spec-dir
    # join built by hand -- matching the sibling ``retrospective/summary.py``
    # staging-path pattern (same package, same "candidate dir + local subpath"
    # shape). This primitive never requires the
    # dir to exist yet -- it returns the best-known candidate -- so it resolves
    # even before the mission's ``traces/`` subdir exists locally; the caller
    # creates ``parent`` before writing.
    # Explicit ``Path`` annotation: under the project's ``follow_imports = "skip"``
    # mypy config, ``candidate_feature_dir_for_mission`` (cross-module) is seen
    # as returning ``Any`` when this file is type-checked in isolation; the
    # annotation re-narrows it back to ``Path`` (matching the sibling
    # ``mission_repair.py``/former-``KITTY_SPECS_DIR`` join convention here).
    feature_dir: Path = candidate_feature_dir_for_mission(repo_root, mission_slug)
    return feature_dir / _TRACES_DIRNAME / filename


def _entry_id(category: str, entry_line: str) -> str:
    # Non-charter use (TID251): a short, stable content-addressed identifier for
    # the WriteSeamResult.entry_id row/entry reference -- not a charter
    # freshness/staleness hash, so charter.hasher.hash_content() (which prefixes
    # "sha256:" and normalises charter-specific BOM/CRLF concerns) is the wrong
    # tool here.
    digest = hashlib.sha256(entry_line.encode("utf-8")).hexdigest()[:12]  # noqa: TID251 - content-addressed entry id, not a charter hash
    return f"{category}-{digest}"


def append_tracer_finding(
    *,
    repo_root: Path,
    mission_slug: str,
    category: str,
    entry: str,
    actor: str,
    policy: ProtectionPolicyLike,
    target_branch: str | None = None,
    entry_date: date | None = None,
) -> WriteSeamResult:
    """Append a dated, attributed finding to ``traces/<category>.md`` (FR-006).

    Merges the new entry into the CURRENT coord-resolved content (never a
    from-scratch file -- see module docstring), stages the merged result at
    the primary checkout's ``kitty-specs/<mission_slug>/traces/<file>``, and
    commits it through the WP03 seam. Residue cleanup is requested via
    ``primary_paths_created_this_invocation`` so the staged local copy does not
    linger as an untracked file on the primary checkout once the coord commit
    lands.

    Args:
        repo_root: Primary checkout root (NOT a lane worktree -- callers
            resolve this via ``get_main_repo_root`` first, the same pattern
            every other coord-partition writer uses).
        mission_slug: Mission handle.
        category: One of :data:`TRACER_CATEGORIES` (``tooling-friction`` /
            ``approach`` / ``design-decisions``).
        entry: The free-text finding body.
        actor: Attribution -- REQUIRED, non-blank (#2960 guard, raises
            :class:`TracerAttributionError` otherwise).
        policy: Duck-typed ``is_protected(ref) -> bool`` policy, threaded
            straight through to the seam.
        target_branch: Optional short primary-branch name for the seam's
            post-commit ff-advance.
        entry_date: Overrides the entry's date (UTC today when ``None`` --
            exposed for deterministic tests, not a CLI-facing knob).

    Returns:
        A :class:`~specify_cli.coordination.write_seam.WriteSeamResult`.

    Raises:
        TracerAttributionError: ``actor`` is blank.
        TracerCategoryError: ``category`` is not recognised.
    """
    actor = _require_actor(actor)
    filename = _category_filename(category)
    resolved_date = entry_date if entry_date is not None else now_utc().date()
    entry_line = _format_entry_line(entry_date=resolved_date, actor=actor, entry=entry)

    current_content = _read_current_coord_content(repo_root, mission_slug, filename)
    base_content = current_content or _default_header(category)
    merged_content = (
        base_content
        if _entry_present(base_content, entry_line)
        else _append_entry(base_content, entry_line)
    )

    local_path = _local_staging_path(repo_root, mission_slug, filename)

    def _stage() -> tuple[Path, ...]:
        # T015 (WP04 / #3073 / FR-005): the mkdir+write_text moves INTO the
        # thunk -- write_artifact's single locus invokes this ONLY after the
        # routability probe succeeds, so a refused write (e.g. FR-006
        # off-checkout, or a genuinely unroutable mission) never touches disk
        # and leaves zero untracked residue. Previously this ran eagerly,
        # before the probe -- the #3073 defect this migration closes.
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_text(merged_content, encoding="utf-8")
        return (local_path,)

    return write_artifact(
        repo_root=repo_root,
        mission_slug=mission_slug,
        kind=MissionArtifactKind.TRACER_FILE,
        stage=_stage,
        message=f"chore(tracer): append {category} finding for {mission_slug}",
        policy=policy,
        entry_id=_entry_id(category, entry_line),
        target_branch=target_branch,
        primary_paths_created_this_invocation=frozenset({local_path}),
    )
