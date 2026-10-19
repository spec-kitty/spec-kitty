"""Converge a legacy ``mission-type-scope-directive`` onto ``project-intent-directive`` (#6443, FR-008).

The always-synthesized directive used to be keyed on the slug
``mission-type-scope-directive``. Synthesis now names it
``project-intent-directive`` and no longer links it to a mission type. One helper
moves an existing project over; the ``4.0.0rc8_project_intent_directive_rename``
upgrade migration and ``charter synthesize`` / ``resynthesize`` (before they
write, so a second ``PROJECT_00N`` file can never appear) both call it.

What moves, when present:

* the artifact file under the project charter pack and the harness input under
  ``.kittify/charter/generated/directives/`` (``NNN-<slug>.directive.yaml``);
* the provenance sidecar: its ``artifact_slug`` and file name, and any recorded
  path of the artifact (``source_input_ids`` / ``source_section``);
* the synthesis-manifest entry (``path``, ``slug``, ``provenance_path``), with
  ``manifest_hash`` recomputed through ``finalize_manifest``;
* the overlay node label, and the dead ``requires --> mission_type:*`` edge
  (dropped);
* stem tokens in the resolved activation write target;
* then the manifest's bundle hash is restamped once.

The declared ``PROJECT_00N`` id, its ``directive:PROJECT_00N`` URN, the interview
section label ``mission_type`` and the artifact body are never touched. The helper
is idempotent: every step acts only on legacy state, so a second run (or a re-run
after an interrupted one) finishes the job and then does nothing. It works in two
phases: a read-only preflight that refuses (changing nothing) on an unreadable
input or a target collision, then the writes.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from charter.offering.artifact_kinds import ArtifactKind
from kernel.atomic import atomic_write
from kernel.charter_pack_paths import PROJECT_GRAPH_FILENAME, project_pack_path

from .artifact_naming import artifact_filename, pack_kind_subdir
from .errors import LegacyRenameRefusedError
from .manifest import MANIFEST_PATH, finalize_manifest, load_yaml
from .provenance import provenance_path_for
from .synthesize_pipeline import canonical_yaml

__all__ = [
    "LegacyRenameRefusedError",
    "RenameReport",
    "rename_legacy_project_intent_directive",
]

_LEGACY_SLUG = "mission-type-scope-directive"
_NEW_SLUG = "project-intent-directive"
_NEW_LABEL = "Project Intent Directive"
#: Labels the legacy directive's overlay node carried (the generic fallback and the registered title).
_LEGACY_LABELS = frozenset({"Mission Type Directive", "Mission Type Scope Directive"})
_LEGACY_FILE_RE = re.compile(rf"(\d+)-{_LEGACY_SLUG}\.directive\.yaml")
_LEGACY_STEM_RE = re.compile(rf"(\d+)-{_LEGACY_SLUG}")
_FILE_GLOB = f"*-{_LEGACY_SLUG}.directive.yaml"
_DIRECTIVE_URN_PREFIX = "directive:PROJECT_"
_MISSION_TYPE_URN_PREFIX = "mission_type:"
_GENERATED_ROOT = Path(".kittify") / "charter" / "generated"
_READ_ERRORS = (OSError, YAMLError, ValueError, ValidationError)


@dataclass(frozen=True)
class RenameReport:
    """What the helper found (``dry_run``) or did: one human-readable line per change."""

    dry_run: bool
    actions: tuple[str, ...] = ()

    @property
    def pending(self) -> bool:
        """True when legacy state was found (and, unless ``dry_run``, converged)."""
        return bool(self.actions)


@dataclass
class _Finding:
    """One step's read-only preflight result."""

    actions: list[str] = field(default_factory=list)
    refusals: list[str] = field(default_factory=list)
    #: Refusals that only matter when legacy state exists elsewhere: an unreadable manifest, overlay or
    #: activation target is reported by the command that reads it, not by a project with nothing to rename.
    soft_refusals: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _Step:
    check: Callable[[Path], _Finding]
    apply: Callable[[Path], None]


# ---------------------------------------------------------------------------
# Naming
# ---------------------------------------------------------------------------


def _target_filename(number: str) -> str:
    name: str = artifact_filename("directive", _NEW_SLUG, f"PROJECT_{number}")
    return name


def _rename_text(text: str) -> str:
    """*text* with every legacy artifact file name replaced by its target name."""
    return _LEGACY_FILE_RE.sub(lambda m: _target_filename(m.group(1)), text)


def _rename_stem(token: str) -> str | None:
    """The target stem for a legacy stem token, or ``None`` when *token* is not one."""
    match = _LEGACY_STEM_RE.fullmatch(token)
    if match is None:
        return None
    return _target_filename(match.group(1)).removesuffix(".directive.yaml")


def _rel(repo_root: Path, path: Path) -> str:
    return path.relative_to(repo_root).as_posix()


def _read_mapping(path: Path) -> dict[str, Any]:
    """The YAML mapping at *path*; raises ``ValueError`` (via ``_READ_ERRORS``) when unreadable."""
    data = YAML(typ="safe").load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("top-level YAML document must be a mapping")
    return data


def _write_mapping(path: Path, data: dict[str, Any]) -> None:
    atomic_write(path, canonical_yaml(data))


def _unreadable(repo_root: Path, path: Path, exc: Exception) -> str:
    return f"{_rel(repo_root, path)} is unreadable ({exc})"


# ---------------------------------------------------------------------------
# Step: artifact file and harness input
# ---------------------------------------------------------------------------


def _file_dirs(repo_root: Path) -> tuple[Path, ...]:
    return (
        project_pack_path(repo_root, pack_kind_subdir("directive")),
        repo_root / _GENERATED_ROOT / ArtifactKind("directive").plural,
    )


def _file_moves(repo_root: Path) -> Iterator[tuple[Path, Path]]:
    for directory in _file_dirs(repo_root):
        if not directory.is_dir():
            continue
        for src in sorted(directory.glob(_FILE_GLOB)):
            match = _LEGACY_FILE_RE.fullmatch(src.name)
            if match is not None:
                yield src, directory / _target_filename(match.group(1))


def _check_files(repo_root: Path) -> _Finding:
    finding = _Finding()
    for src, dst in _file_moves(repo_root):
        if dst.exists():
            finding.refusals.append(f"{_rel(repo_root, dst)} already exists, so {_rel(repo_root, src)} cannot move onto it")
        else:
            finding.actions.append(f"move {_rel(repo_root, src)} -> {_rel(repo_root, dst)}")
    return finding


def _apply_files(repo_root: Path) -> None:
    for src, dst in list(_file_moves(repo_root)):
        src.replace(dst)


# ---------------------------------------------------------------------------
# Step: provenance sidecars
# ---------------------------------------------------------------------------


def _provenance_dir(repo_root: Path) -> Path:
    directory: Path = (repo_root / provenance_path_for("directive", _NEW_SLUG)).parent
    return directory


def _rewrite_provenance(data: dict[str, Any]) -> dict[str, Any]:
    """A copy of *data* naming the new slug and artifact file, or an equal one when nothing is legacy."""
    updated = dict(data)
    if updated.get("artifact_slug") == _LEGACY_SLUG:
        updated["artifact_slug"] = _NEW_SLUG
    section = updated.get("source_section")
    if isinstance(section, str):
        updated["source_section"] = _rename_text(section)
    inputs = updated.get("source_input_ids")
    if isinstance(inputs, list):
        updated["source_input_ids"] = [_rename_text(item) if isinstance(item, str) else item for item in inputs]
    return updated


def _provenance_plan(repo_root: Path) -> Iterator[tuple[Path, Path, dict[str, Any], str | None]]:
    """``(source, destination, rewritten data, error)`` for each legacy provenance sidecar."""
    directory = _provenance_dir(repo_root)
    if not directory.is_dir():
        return
    for path in sorted(directory.glob("directive-*.yaml")):
        try:
            data = _read_mapping(path)
        except _READ_ERRORS as exc:
            if _LEGACY_SLUG in path.name:
                yield path, path, {}, _unreadable(repo_root, path, exc)
            continue
        updated = _rewrite_provenance(data)
        if updated == data:
            continue
        dst = repo_root / provenance_path_for("directive", _NEW_SLUG) if data.get("artifact_slug") == _LEGACY_SLUG else path
        yield path, dst, updated, None


def _check_provenance(repo_root: Path) -> _Finding:
    finding = _Finding()
    for src, dst, _data, error in _provenance_plan(repo_root):
        if error is not None:
            finding.refusals.append(error)
        elif dst != src and dst.exists():
            finding.refusals.append(f"{_rel(repo_root, dst)} already exists, so {_rel(repo_root, src)} cannot move onto it")
        else:
            verb = "rewrite" if dst == src else "move and rewrite"
            finding.actions.append(f"{verb} provenance {_rel(repo_root, src)}" + ("" if dst == src else f" -> {_rel(repo_root, dst)}"))
    return finding


def _apply_provenance(repo_root: Path) -> None:
    for src, dst, data, _error in list(_provenance_plan(repo_root)):
        _write_mapping(dst, data)
        if dst != src:
            src.unlink()


# ---------------------------------------------------------------------------
# Step: synthesis manifest
# ---------------------------------------------------------------------------


def _renamed_entries(entries: list[Any]) -> list[Any]:
    renamed = []
    legacy_provenance = provenance_path_for("directive", _LEGACY_SLUG)
    for entry in entries:
        update: dict[str, str] = {}
        if entry.kind == "directive":
            if entry.slug == _LEGACY_SLUG:
                update["slug"] = _NEW_SLUG
            if _rename_text(entry.path) != entry.path:
                update["path"] = _rename_text(entry.path)
            if entry.provenance_path == legacy_provenance:
                update["provenance_path"] = provenance_path_for("directive", _NEW_SLUG)
        renamed.append(entry.model_copy(update=update) if update else entry)
    return renamed


def _manifest_collisions(entries: list[Any], renamed: list[Any]) -> list[str]:
    reasons: list[str] = []
    for field_name in ("slug", "path"):
        values = [getattr(entry, field_name) for entry in renamed if entry.kind == "directive"]
        if len(values) != len(set(values)):
            reasons.append(f"the synthesis manifest would list two directive entries with the same {field_name} after the rename")
    return reasons if renamed != entries else []


def _check_manifest(repo_root: Path) -> _Finding:
    finding = _Finding()
    path = repo_root / MANIFEST_PATH
    if not path.is_file():
        return finding
    try:
        manifest = load_yaml(path)
    except _READ_ERRORS as exc:
        finding.soft_refusals.append(_unreadable(repo_root, path, exc))
        return finding
    renamed = _renamed_entries(manifest.artifacts)
    if renamed != manifest.artifacts:
        finding.actions.append(f"rewrite {_rel(repo_root, path)} (path/slug/provenance_path, manifest_hash)")
        finding.refusals.extend(_manifest_collisions(manifest.artifacts, renamed))
    return finding


def _apply_manifest(repo_root: Path) -> None:
    path = repo_root / MANIFEST_PATH
    if not path.is_file():
        return
    manifest = load_yaml(path)
    renamed = _renamed_entries(manifest.artifacts)
    if renamed != manifest.artifacts:
        finalized = finalize_manifest(manifest.model_copy(update={"artifacts": renamed}))
        atomic_write(path, canonical_yaml(finalized.model_dump(mode="python")))


# ---------------------------------------------------------------------------
# Step: overlay graph
# ---------------------------------------------------------------------------


def _is_dead_edge(edge: Any) -> bool:
    return (
        isinstance(edge, dict)
        and edge.get("relation") == "requires"
        and str(edge.get("source", "")).startswith(_DIRECTIVE_URN_PREFIX)
        and str(edge.get("target", "")).startswith(_MISSION_TYPE_URN_PREFIX)
    )


def _is_legacy_node(node: Any) -> bool:
    return isinstance(node, dict) and node.get("kind") == "directive" and node.get("label") in _LEGACY_LABELS


def _rewrite_overlay(data: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """The overlay with legacy labels renamed and dead edges dropped, plus a line per change."""
    actions: list[str] = []
    nodes = data.get("nodes")
    edges = data.get("edges")
    updated = dict(data)
    if isinstance(nodes, list) and any(_is_legacy_node(n) for n in nodes):
        updated["nodes"] = [{**n, "label": _NEW_LABEL} if _is_legacy_node(n) else n for n in nodes]
        actions.append(f"relabel the directive overlay node as '{_NEW_LABEL}'")
    if isinstance(edges, list) and any(_is_dead_edge(e) for e in edges):
        updated["edges"] = [e for e in edges if not _is_dead_edge(e)]
        actions.append("drop the dead 'requires --> mission_type:*' overlay edge")
    return updated, actions


def _check_overlay(repo_root: Path) -> _Finding:
    finding = _Finding()
    path = project_pack_path(repo_root, PROJECT_GRAPH_FILENAME)
    if not path.is_file():
        return finding
    try:
        _updated, actions = _rewrite_overlay(_read_mapping(path))
    except _READ_ERRORS as exc:
        finding.soft_refusals.append(_unreadable(repo_root, path, exc))
        return finding
    finding.actions.extend(f"{action} in {_rel(repo_root, path)}" for action in actions)
    return finding


def _apply_overlay(repo_root: Path) -> None:
    path = project_pack_path(repo_root, PROJECT_GRAPH_FILENAME)
    if not path.is_file():
        return
    updated, actions = _rewrite_overlay(_read_mapping(path))
    if actions:
        _write_mapping(path, updated)


# ---------------------------------------------------------------------------
# Step: stem tokens in the activation write target
# ---------------------------------------------------------------------------


def _renamed_tokens(tokens: list[Any]) -> list[Any]:
    renamed: list[Any] = []
    for token in tokens:
        new = _rename_stem(token) if isinstance(token, str) else None
        value = token if new is None else new
        if value not in renamed:
            renamed.append(value)
    return renamed


def _legacy_token_keys(data: dict[str, Any]) -> list[str]:
    from charter.activation.pack_manager import ACTIVATION_YAML_KEYS  # deferred: import cycle: pack_manager imports synthesizer modules

    keys = []
    for key in ACTIVATION_YAML_KEYS:
        value = data.get(key)
        if isinstance(value, list) and any(isinstance(t, str) and _rename_stem(t) is not None for t in value):
            keys.append(key)
    return keys


def _check_tokens(repo_root: Path) -> _Finding:
    finding = _Finding()
    from charter.activation.pack_manager import resolve_activation_write_target  # deferred: import cycle

    try:
        target_path, data, _save = resolve_activation_write_target(repo_root)
    except (*_READ_ERRORS, RuntimeError) as exc:
        finding.soft_refusals.append(f"the activation write target is unreadable ({exc})")
        return finding
    for key in _legacy_token_keys(data):
        finding.actions.append(f"rewrite '{key}' stem token(s) in {_rel(repo_root, target_path)}")
    return finding


def _apply_tokens(repo_root: Path) -> None:
    from charter.activation.pack_manager import resolve_activation_write_target  # deferred: import cycle

    target_path, data, save = resolve_activation_write_target(repo_root)
    keys = _legacy_token_keys(data)
    for key in keys:
        data[key] = _renamed_tokens(list(data[key]))
    if keys:
        save(target_path, data)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

#: Write order: artifact/input files first; the manifest last of the synthesis state, so an interrupted
#: run leaves a state the next run recognises and finishes (every step acts only on legacy state).
_STEPS: tuple[_Step, ...] = (
    _Step(_check_files, _apply_files),
    _Step(_check_provenance, _apply_provenance),
    _Step(_check_manifest, _apply_manifest),
    _Step(_check_overlay, _apply_overlay),
    _Step(_check_tokens, _apply_tokens),
)


def _preflight(repo_root: Path) -> list[str]:
    """Phase 1: every action the rename would take; raises when it must refuse. Writes nothing."""
    actions: list[str] = []
    refusals: list[str] = []
    soft: list[str] = []
    for step in _STEPS:
        finding = step.check(repo_root)
        actions.extend(finding.actions)
        refusals.extend(finding.refusals)
        soft.extend(finding.soft_refusals)
    if actions:
        refusals.extend(soft)
    if refusals:
        raise LegacyRenameRefusedError(reasons=tuple(refusals))
    return actions


def rename_legacy_project_intent_directive(repo_root: Path, *, dry_run: bool = False) -> RenameReport:
    """Move a legacy ``mission-type-scope-directive`` onto ``project-intent-directive`` (FR-008).

    With *dry_run* only the preflight runs, so the report lists what would change. Raises
    :class:`LegacyRenameRefusedError` (nothing changed) on an unreadable input or a target collision.
    """
    actions = _preflight(repo_root)
    if dry_run or not actions:
        return RenameReport(dry_run=dry_run, actions=tuple(actions))
    for step in _STEPS:
        step.apply(repo_root)
    from charter.activation.bundle_restamp import restamp_bundle_hash  # deferred: import cycle

    restamp_bundle_hash(repo_root)
    return RenameReport(dry_run=False, actions=tuple(actions))
