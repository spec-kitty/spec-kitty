"""Path convention validation helpers for Spec Kitty missions."""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from collections.abc import Iterable, Sequence

from specify_cli.config.path_conventions import ARTIFACT_ROUTED_KEYS
from specify_cli.mission import Mission

__all__ = [
    "PathValidationError",
    "PathValidationResult",
    "artifact_tokens_for_mission",
    "normalize_path_token",
    "suggest_directory_creation",
    "validate_mission_paths",
]


class PathValidationError(Exception):
    """Raised when required mission paths are missing in strict mode."""

    def __init__(self, result: PathValidationResult) -> None:
        self.result = result
        message = result.format_errors() or "Path convention validation failed."
        super().__init__(message)


@dataclass
class PathValidationResult:
    """Result of validating mission-declared paths against the workspace."""

    mission_name: str
    required_paths: dict[str, str]
    existing_paths: list[str] = field(default_factory=list)
    missing_paths: list[str] = field(default_factory=list)
    #: Normalized artifact tokens (via ``normalize_path_token``) for every
    #: missing path that is ALSO a declared mission artifact (resolved on the
    #: mission's primary surface, see ``is_artifact_tagged`` below) — the FR-002
    #: dedup input consumed by ``summary_core.evaluate_path_conventions``. A
    #: missing build/repo-root path is never an artifact, so it is never added
    #: here: the sole consumer filters by ``artifact_tokens`` membership, and a
    #: non-artifact token could never survive that filter, so populating one
    #: for it would be dead weight the field name (``*_feature_relative``) also
    #: mis-described (it never held a feature-relative *path*, only a token).
    missing_artifact_tokens: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    #: #4254: declared path -> the candidate source root that satisfied it,
    #: for a build path that exists only in the tree being accepted and not
    #: yet in ``project_root``. Empty for every path found at ``project_root``
    #: itself, so a reader can tell "already integrated" from "present in the
    #: approved lane".
    satisfied_by: dict[str, str] = field(default_factory=dict)
    #: #6633: path-convention keys that are missing from the workspace AND can
    #: be remapped by a ``project.path_conventions`` override (``.kittify/config.yaml``,
    #: #3016) -- every missing key EXCEPT the artifact-routed ones, which the
    #: override vocabulary excludes (C-010). Drives the copy-pasteable remap
    #: example in ``format_errors``; empty when nothing missing is remappable,
    #: so hand-built results keep rendering the historical two-lever text.
    remappable_missing_keys: list[str] = field(default_factory=list)
    #: #6633: the mission-type slug (``<...>/missions/<type>``'s last segment,
    #: e.g. ``software-dev``) used to name the project mission-override route
    #: (``.kittify/overrides/missions/<type>/mission.yaml``, #4088) in the
    #: failure text. ``None`` when the slug cannot be derived from the
    #: mission's resolver path -- ``format_errors`` then renders a generic
    #: ``<mission-type>`` placeholder rather than guessing.
    mission_type: str | None = None

    @property
    def is_valid(self) -> bool:
        """True when every required path exists."""
        return not self.missing_paths

    def format_warnings(self) -> str:
        """Return human-readable warning text."""
        if not self.warnings:
            return ""

        lines = ["Path Convention Warnings:"]
        for warning in self.warnings:
            lines.append(f"  - {warning}")

        if self.suggestions:
            lines.append("")
            lines.append("Suggestions:")
            for suggestion in self.suggestions:
                lines.append(f"  - {suggestion}")

        return "\n".join(lines)

    def format_errors(self) -> str:
        """Return human-readable error text for strict enforcement."""
        if self.is_valid:
            return ""

        lines = ["Path Convention Errors:"]
        for warning in self.warnings:
            lines.append(f"  - {warning}")

        lines.append("")
        if self.suggestions:
            lines.append(
                "Run `accept --lenient` to treat these as warnings instead of blocking "
                "errors for this mission run - or, if you want to adopt the convention, "
                "see the commands below:"
            )
        else:
            lines.append(
                "Run `accept --lenient` to treat these as warnings instead of blocking "
                "errors for this mission run."
            )

        # #6633: name the honest project-level levers #3016/#4088 added, so a
        # repo whose real layout is not ``src/``/``tests/``/``docs/`` can
        # self-serve instead of fabricating directories or paying the
        # ``--lenient`` metadata-check cost. Rendered only when at least one
        # missing key is remappable: an artifact-routed key (``deliverables``)
        # is excluded from the override vocabulary (C-010) and governed by the
        # #5298 ``contracts: none`` waiver instead. Placed AFTER the
        # ``--lenient`` sentence and BEFORE the ``mkdir -p`` suggestions so the
        # #3783 ordering contract (``--lenient`` first) is preserved.
        if self.remappable_missing_keys:
            lines.append("")
            lines.append(
                "If this project's real layout differs from these conventions, remap "
                "them in `.kittify/config.yaml` via `project.path_conventions` (see ADR "
                "project-path-convention-override-precedes-doctrine):"
            )
            lines.append("")
            lines.append("  project:")
            lines.append("    path_conventions:")
            for key in self.remappable_missing_keys:
                lines.append(f"      {key}: <real-directory>/  # where this project keeps its {key}")
            lines.append("")
            lines.append(
                "A key this project has no directory for can instead be dropped by "
                "copying the packaged mission.yaml to "
                f"`.kittify/overrides/missions/{self.mission_type or '<mission-type>'}/mission.yaml` "
                "and removing that key's line."
            )

        if self.suggestions:
            lines.append("")
            lines.append("Required Actions:")
            for suggestion in self.suggestions:
                lines.append(f"  - {suggestion}")

        return "\n".join(lines)


def suggest_directory_creation(missing_paths: Iterable[str]) -> list[str]:
    """Generate shell-friendly suggestions for fixing missing paths."""

    missing = list(missing_paths)
    suggestions: list[str] = []

    for path_str in missing:
        path = Path(path_str)
        if path_str.endswith("/"):
            suggestions.append(f"mkdir -p {path_str}")
        elif "." in path.name:
            parent = path.parent
            if parent and str(parent) not in {"", "."}:
                suggestions.append(f"mkdir -p {parent} && touch {path_str}")
            else:
                suggestions.append(f"touch {path_str}")
        else:
            suggestions.append(f"mkdir -p {path_str}")

    dir_paths = [p for p in missing if p.endswith("/")]
    if len(dir_paths) > 1:
        joined = " ".join(dir_paths)
        suggestions.insert(0, f"Create directories in one go: mkdir -p {joined}")

    return suggestions


def _prefix_required_path(path_prefix: str | Path | None, relative_path: str) -> str:
    """Return ``relative_path`` under ``path_prefix`` while preserving dir hints."""

    if not path_prefix:
        return relative_path
    candidate = Path(relative_path)
    if candidate.is_absolute():
        return relative_path

    prefix = str(path_prefix).strip().strip("/")
    if not prefix:
        return relative_path

    relative = relative_path.strip("/")
    joined = PurePosixPath(prefix) / relative
    if relative_path.endswith("/"):
        return joined.as_posix() + "/"
    return joined.as_posix()


def normalize_path_token(token: str) -> str:
    """Normalise a path/artifact token for membership comparison (strip slashes)."""
    return str(token).strip().strip("/")


def artifact_tokens_for_mission(mission: Mission) -> set[str]:
    """Return the normalized set of a mission's declared artifact tokens.

    Defensive: a real ``MissionConfig`` always carries ``artifacts``, but a
    partial mock/config may not — treat its absence as "no artifact paths"
    (the same fallback ``validate_mission_paths`` already applies).
    """
    artifacts = getattr(mission.config, "artifacts", None)
    required = getattr(artifacts, "required", ()) or ()
    optional = getattr(artifacts, "optional", ()) or ()
    return {normalize_path_token(name) for name in (*required, *optional)}


def _remap_declared_paths(
    declared: dict[str, str], path_overrides: dict[str, str] | None
) -> dict[str, str]:
    """Apply a remap-only project ``path_conventions`` override to declared paths (C-008 / C-010).

    Only keys the mission already declares are remapped; an override for a key the mission does not
    declare is ignored (never adds a new required path). Artifact-routed keys (``ARTIFACT_ROUTED_KEYS``)
    are excluded here too, as defense-in-depth: the reader (:mod:`specify_cli.config.path_conventions`)
    already strips them from a config-file-sourced mapping, but this merge site must not blindly trust
    an override dict constructed some other way to leave ``deliverables``-style artifact routing intact.
    Returns a new dict; the input is untouched.
    """
    if not path_overrides:
        return declared
    remapped = dict(declared)
    for key in declared:
        if key in ARTIFACT_ROUTED_KEYS:
            continue
        override = path_overrides.get(key)
        if override is not None:
            remapped[key] = override
    return remapped


def _drop_overrides_colliding_with_artifacts(
    path_overrides: dict[str, str] | None,
    declared: dict[str, str],
    artifact_tokens: set[str],
) -> dict[str, str] | None:
    """Drop (with a warning) an override whose VALUE collides with a mission artifact token.

    e.g. ``{"workspace": "contracts"}`` where ``contracts`` is a declared mission artifact: applying it
    would flip ``workspace``'s resolution onto ``feature_dir`` (the artifact surface, see
    ``validate_mission_paths``'s ``is_artifact_tagged`` branch) and let a real mission-artifact directory
    spuriously satisfy a check that should test the project's actual workspace location. Only meaningful
    when artifact-token routing is active (``artifact_tokens`` non-empty, i.e. a ``feature_dir`` was
    supplied and this is not research's ``path_prefix`` mode) — a no-op otherwise.
    """
    if not path_overrides or not artifact_tokens:
        return path_overrides
    safe_overrides = dict(path_overrides)
    for key, value in path_overrides.items():
        if key not in declared:
            continue
        if normalize_path_token(value) in artifact_tokens:
            warnings.warn(
                f"project.path_conventions override for {key!r} ({value!r}) collides with a mission "
                "artifact token and was ignored to avoid flipping path-resolution routing.",
                stacklevel=2,
            )
            del safe_overrides[key]
    return safe_overrides


def _mission_type_slug(mission: Mission) -> str | None:
    """Return the mission-type slug from a resolver-style mission path (#6633).

    ``Mission.path`` is ``<...>/missions/<type>`` on every resolver tier
    (package, global, legacy project, org, override), so its last segment is
    the type slug the project mission-override route is keyed by. Derive it
    ONLY when the path genuinely sits inside a ``missions`` directory -- a
    descriptive marker path elsewhere (a feature directory, a hand-built stub
    with no path at all) yields ``None``, and the failure text renders a
    generic ``<mission-type>`` placeholder instead of guessing.
    """
    mission_path = getattr(mission, "path", None)
    if not isinstance(mission_path, Path):
        return None
    if mission_path.parent.name != "missions":
        return None
    slug = mission_path.name
    return slug or None


def _record_missing_path(
    result: PathValidationResult,
    *,
    mission_name: str,
    key: str,
    resolved: str,
    relative_path: str,
    is_artifact_tagged: bool,
) -> None:
    """Record one missing required path on ``result`` (#6633: split out of
    ``validate_mission_paths`` to keep its cyclomatic complexity under the C901
    limit -- behaviour is unchanged).

    Also records the render input the strict failure text's project-level
    guidance needs: a missing key outside ``ARTIFACT_ROUTED_KEYS`` is remappable
    via ``project.path_conventions`` (#3016); artifact-routed keys are excluded
    from the override vocabulary (C-010) and governed by the #5298 waiver.
    """
    result.missing_paths.append(resolved)
    result.warnings.append(f"{mission_name} expects {key} path: {resolved} (not found)")
    if key not in ARTIFACT_ROUTED_KEYS:
        result.remappable_missing_keys.append(key)
    if is_artifact_tagged:
        # Real feature_dir-relative token, straight from the declared path —
        # `resolved` above is project_root-relative and can't recover this.
        # A build/repo-root path is never appended here: it can never be a
        # declared mission artifact, so the sole consumer's artifact_tokens
        # membership filter could never let it through (see the field's
        # docstring above).
        result.missing_artifact_tokens.append(normalize_path_token(relative_path))


def validate_mission_paths(
    mission: Mission,
    project_root: Path,
    *,
    strict: bool = False,
    path_prefix: str | Path | None = None,
    feature_dir: Path | None = None,
    path_overrides: dict[str, str] | None = None,
    candidate_source_roots: Sequence[Path] = (),
    waived_artifact_tokens: frozenset[str] = frozenset(),
) -> PathValidationResult:
    """Validate that project directories follow mission-defined conventions.

    Args:
        mission: Mission containing declared path conventions.
        project_root: Root of the active workspace/worktree.
        strict: When True, raise PathValidationError if paths are missing.
        path_prefix: Optional project-relative prefix to apply before checking
            mission-declared paths. Research missions use this to validate
            configured deliverable directories instead of fixed repository-root
            directories.
        feature_dir: The mission's PRIMARY-surface directory
            (``kitty-specs/<mission>/``). When supplied, a declared path that is
            also a mission artifact (a member of ``mission.config.artifacts``,
            e.g. ``contracts/``) is resolved against ``feature_dir`` — those live
            with the mission, NOT at the repo root. Build/repo paths
            (``src/``/``tests/``/``docs/``) keep resolving against ``project_root``.
            There is no repo-root fallback for an artifact path (#2115 / #1716
            residual of the "no resolution to the repo primary" rule — it mirrors
            the #2113 ``_planning_read_dir`` seam). Research's ``path_prefix``
            routing is unaffected.
        candidate_source_roots: Additional trees a BUILD/source path may live in
            (#4254). Acceptance runs before the approved lane's source is
            integrated, so a lane that introduces the first ``tests/`` or
            ``docs/`` has those directories only in its own worktree — checking
            ``project_root`` alone reported them missing and blocked acceptance
            of reviewed work. A path found in one of these roots is recorded as
            existing, with the satisfying root noted in ``satisfied_by``. The
            caller decides which trees qualify (the acceptance caller passes
            only APPROVED lanes, so an unapproved or foreign checkout cannot
            satisfy a path); artifact-tagged paths never consult them — mission
            artifacts stay on the primary surface.
        waived_artifact_tokens: Normalized mission-artifact tokens the Mission
            explicitly waived (#5298: ``meta.json`` ``"contracts": "none"``,
            read by ``core.paths.read_contracts_waiver_from_meta``). A declared
            path whose token is waived is not required. Only ARTIFACT-tagged
            paths can be waived -- a build/repo path (``src/``, ``tests/``,
            ``docs/``) is never skipped, whatever this set holds.

    Returns:
        PathValidationResult summarising the state of each required path.
    """

    # Mission-artifact path tokens (e.g. ``contracts/``) — resolved against the
    # mission's feature_dir rather than the repo root. Only consulted when a
    # feature_dir is supplied and we are not in research's path_prefix mode.
    # Computed BEFORE the override remap below so an override VALUE colliding with an
    # artifact token can be guarded against (_drop_overrides_colliding_with_artifacts).
    artifact_tokens: set[str] = set()
    if feature_dir is not None and not path_prefix:
        artifact_tokens = artifact_tokens_for_mission(mission)

    # Merge the project-level override into ``declared`` BEFORE the prefix comprehension and the
    # artifact-token membership check below, so overridden keys are prefixed for research missions and
    # never bypass artifact routing (C-008). Remap-only: no new key is introduced (C-010).
    mission_paths = dict(mission.config.paths or {})
    safe_overrides = _drop_overrides_colliding_with_artifacts(path_overrides, mission_paths, artifact_tokens)
    declared = _remap_declared_paths(mission_paths, safe_overrides)
    required_paths = {
        key: _prefix_required_path(path_prefix, relative_path)
        for key, relative_path in declared.items()
    }
    result = PathValidationResult(
        mission_name=mission.name,
        required_paths=required_paths,
        mission_type=_mission_type_slug(mission),
    )

    if not required_paths:
        return result

    for key, relative_path in required_paths.items():
        candidate = Path(relative_path)
        is_artifact_tagged = False
        if candidate.is_absolute():
            full_path = candidate
        elif normalize_path_token(declared[key]) in artifact_tokens:
            if normalize_path_token(declared[key]) in waived_artifact_tokens:
                # #5298: the Mission declared it has no such artifact.
                continue
            # Mission artifact → resolve on the mission's primary surface.
            full_path = feature_dir / candidate  # type: ignore[operator]
            is_artifact_tagged = True
        else:
            full_path = project_root / candidate
        if full_path.exists():
            result.existing_paths.append(relative_path)
            continue

        # #4254: a build/source path may legitimately exist only in the
        # candidate tree being accepted, which is not yet integrated into
        # ``project_root``. Artifact paths are deliberately excluded — they
        # belong to the mission's primary surface.
        if not is_artifact_tagged and candidate_source_roots and not candidate.is_absolute():
            satisfying = next(
                (root for root in candidate_source_roots if (root / candidate).exists()),
                None,
            )
            if satisfying is not None:
                result.existing_paths.append(relative_path)
                result.satisfied_by[relative_path] = str(satisfying)
                continue

        # Report the resolved location actually tested above, not the bare
        # declared token (#3085a) — otherwise remediation names a different,
        # untested directory (e.g. the repo root instead of feature_dir).
        try:
            resolved = full_path.relative_to(project_root).as_posix()
        except ValueError:
            resolved = str(full_path)
        if relative_path.endswith("/") and not resolved.endswith("/"):
            resolved += "/"

        _record_missing_path(
            result,
            mission_name=mission.name,
            key=key,
            resolved=resolved,
            relative_path=relative_path,
            is_artifact_tagged=is_artifact_tagged,
        )

    if result.missing_paths:
        result.suggestions = suggest_directory_creation(result.missing_paths)
        if strict:
            raise PathValidationError(result)

    return result
