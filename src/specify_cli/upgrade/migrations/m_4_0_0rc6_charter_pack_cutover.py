"""Migration: the charter-pack cutover (FR-012, #3732).

One idempotent migration that rewrites a project's pre-cutover state into the
charter vocabulary. It runs **before every other pending migration**
(``runs_first``), so every later migration reads canonical state.

Contract: ``kitty-specs/charter-pack-cutover-01M491G6/contracts/upgrade-migration.md``.
Inventory: spec FR-012. ``apply()`` runs these steps in order, each its own
function so a later work package adds a step with a two-line wiring edit:

1. preflight: a path present under both the retired project layer and the
   project pack root with different content refuses the run, naming every
   colliding path; nothing is written;
2. move the retired project layer (``.kittify/doctrine/**``) into the project
   pack root, file by file, each source removed through the ownership guard
   only once a byte-identical copy exists (a locked file stops the run, naming
   the path; a re-run finishes the job);
3. path references: synthesis manifest ``artifacts[].path`` (manifest hash
   recomputed), provenance sidecars, ``.kittify/skills-manifest.json``
   ``source_ref`` and ``.gitignore`` rules;
4. config keys: ``doctrine.org`` (packs list and the single-pack form),
   ``organisation_packs``, ``governance.doctrine`` (``config.yaml``, the
   pointed ``charter.yaml`` and a standalone ``governance.yaml``),
   ``tracker.doctrine`` and the interview answers' top-level ``doctrine:``;
5. ``doctrine_pack_id`` -> ``charter_pack_id`` in project activation entries;
6. [WP12] stale-list, kind-gate and ``[]`` resets, on the first application
   only (:meth:`CharterPackCutoverMigration.is_first_application`);
7. [WP12] installed removed skills;
8. record: the report (``_charter_pack_cutover_report``) becomes the
   ``MigrationResult``.

Rules: the canonical key wins when both spellings are present (the legacy one is
dropped and named in the report); user-chosen path values are never rewritten
(only keys and values that start with the retired root move); the migration
reads raw files, never through the legacy-aware readers.

Selection: ``detect()`` is content-driven and **total** (it never raises; an
unreadable file selects the migration and ``apply()`` fails with a named
error). :meth:`CharterPackCutoverMigration.structural_detect` is the structural
part only (retired root, retired config keys, ``doctrine_pack_id``): the
registry re-selects the migration whenever it is true, even when
``metadata.yaml`` records it as applied, so a pulled checkout or a merge that
brings legacy state back is migrated again. The reset predicates WP12 adds to
``detect()`` are consulted only while the migration is not recorded as applied.

``runs_on_worktrees = False`` (contract; research §1.3 proposed True): integrating
lane and coordination worktrees are skipped by the runner anyway (#5457), and a
worktree picks the cutover up by merging the upgraded target branch.

This module spells the retired names by design; it is exempt by file from the
FR-016 and FR-018 gates.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.error import YAMLError

from kernel.atomic import atomic_write
from kernel.charter_pack_paths import KITTIFY_DIRNAME, PROJECT_PACK_ROOT, PROJECT_PACK_ROOT_POSIX
from specify_cli.asset_preservation import guard_destructive_removal
from specify_cli.asset_preservation.backup import write_file_verbatim
from specify_cli.gitignore_manager import GitignorePathError, read_gitignore_text, write_gitignore_text
from specify_cli.migration.legacy_charter_layout import (
    CONFIG_KEY_FINDINGS,
    LEGACY_PROJECT_ROOT_POSIX,
    LEGACY_PROJECT_ROOT_RELPATH,
    LEGACY_SELECTION_KEYWORD,
    ORGANISATION_PACKS_KEYWORD,
    UNREADABLE_CONFIG,
    UNREADABLE_GOVERNANCE_FILE,
    UNREADABLE_PROJECT_ROOT,
    detect_legacy_charter_layout,
    governance_file_path,
    is_convertible_organisation_pack,
    legacy_org_block,
)
from specify_cli.tool_surface.operations import OwnershipProof

from ..metadata import ProjectMetadata
from ..registry import MigrationRegistry
from ._charter_pack_cutover_report import CutoverReport
from .base import BaseMigration, MigrationResult, MigrationStateUnreadableError

__all__ = ["CharterPackCutoverMigration"]

MIGRATION_ID = "charter_pack_cutover"

# Canonical spellings.
_CHARTER_KEY = "charter"
_CHARTER_PACKS_KEY = "charter_packs"
_OWNERSHIP_KEY = "ownership"
_ORG_KEY = "org"
_PACKS_KEY = "packs"
_GOVERNANCE_KEY = "governance"
_TRACKER_KEY = "tracker"
_ACTIVATIONS_KEY = "activations"
_LEGACY_PACK_ID_KEY = "doctrine_pack_id"
_PACK_ID_KEY = "charter_pack_id"
_LOCAL_PATH_KEY = "local_path"
#: Fields of the single-pack legacy form, in canonical entry order.
_SINGLE_PACK_FIELDS = (_LOCAL_PATH_KEY, "subdir", "source_type", "url", "ref")
#: The preset name a single-pack legacy form must never take (it was auto-named so).
_RESERVED_PACK_NAME = "default"
_FALLBACK_PACK_NAME = "org"

_CONFIG_RELPATH = Path(KITTIFY_DIRNAME, "config.yaml")
_ANSWERS_RELPATH = Path(KITTIFY_DIRNAME, "charter", "interview", "answers.yaml")
_SKILLS_MANIFEST_RELPATH = Path(KITTIFY_DIRNAME, "skills-manifest.json")
_PROVENANCE_DIRNAME = ".provenance"
_GITIGNORE = ".gitignore"

_LEGACY_PREFIX = f"{LEGACY_PROJECT_ROOT_POSIX}/"
_LEGACY_PREFIX_WINDOWS = _LEGACY_PREFIX.replace("/", "\\")
#: A ``.gitignore`` rule naming the retired root (not a longer sibling such as ``doctrine-foo``).
_GITIGNORE_LEGACY_RULE = re.compile(re.escape(LEGACY_PROJECT_ROOT_POSIX) + r"(?=/|$|\s)")
#: Cheap prefilter for a key line that may be a retired key in a YAML file.
_LEGACY_KEY_LINE = re.compile(
    rf"^[ \t]*(?:-[ \t]+)?['\"]?(?:{LEGACY_SELECTION_KEYWORD}|{_LEGACY_PACK_ID_KEY})['\"]?[ \t]*:",
    re.MULTILINE,
)
_TOP_LEVEL_LEGACY_KEY_LINE = re.compile(rf"^['\"]?{LEGACY_SELECTION_KEYWORD}['\"]?[ \t]*:", re.MULTILINE)
_PACK_NAME_INVALID = re.compile(r"[^a-z0-9]+")

_UPGRADE_REMEDY = "fix the file, then run `spec-kitty upgrade` again"
#: Why a retired org key stays: the canonical home it would move into is not a mapping.
_NOT_A_MAPPING = f"{_CHARTER_PACKS_KEY} is not a mapping; make it one by hand, then run `spec-kitty upgrade` again"


# --------------------------------------------------------------------------- #
# Run state
# --------------------------------------------------------------------------- #


@dataclass
class _Run:
    """One ``apply()`` (or a dry run used by ``detect()``): paths, mode and report."""

    project: Path
    dry_run: bool
    report: CutoverReport = field(default_factory=CutoverReport)

    @property
    def legacy_root(self) -> Path:
        return self.project.joinpath(*LEGACY_PROJECT_ROOT_RELPATH.parts)

    @property
    def pack_root(self) -> Path:
        return self.project / Path(PROJECT_PACK_ROOT)

    def rel(self, path: Path) -> str:
        try:
            return path.relative_to(self.project).as_posix()
        except ValueError:
            return path.as_posix()

    def write_text(self, path: Path, text: str) -> None:
        if not self.dry_run:
            atomic_write(path, text)


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #


def _unreadable(path: Path, project: Path, exc: BaseException) -> MigrationStateUnreadableError:
    try:
        rel = path.relative_to(project).as_posix()
    except ValueError:
        rel = path.as_posix()
    return MigrationStateUnreadableError(f"{rel} could not be read ({exc}); {_UPGRADE_REMEDY}")


def _round_trip() -> YAML:
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096
    return yaml


def _dump(data: Any) -> str:
    stream = StringIO()
    _round_trip().dump(data, stream)
    return stream.getvalue()


def _read_text(path: Path, project: Path) -> str | None:
    """Return the text of *path*, ``None`` when absent; a read error is a named failure."""
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise _unreadable(path, project, exc) from exc


def _load_yaml(text: str, path: Path, project: Path) -> Any:
    try:
        return _round_trip().load(text)
    except YAMLError as exc:
        raise _unreadable(path, project, exc) from exc


def _rewrite_legacy_path(value: object) -> str | None:
    """Return *value* moved to the project pack root, or ``None`` when it is not under the retired root."""
    if not isinstance(value, str):
        return None
    normalised = value.replace("\\", "/") if value.startswith(_LEGACY_PREFIX_WINDOWS) else value
    if normalised.startswith(_LEGACY_PREFIX):
        return f"{PROJECT_PACK_ROOT_POSIX}/{normalised[len(_LEGACY_PREFIX) :]}"
    return None


def _mentions_legacy_root(text: str) -> bool:
    return _LEGACY_PREFIX in text or _LEGACY_PREFIX_WINDOWS in text


@dataclass(frozen=True)
class _KeyEdit:
    """Rename *old* to *new* in *mapping* (or drop *old* when *new* is already there)."""

    mapping: CommentedMap
    old: str
    new: str
    label: str
    """Dotted name of the legacy key for the report (for example ``governance.doctrine``)."""

    @property
    def drops(self) -> bool:
        return self.new in self.mapping

    def describe(self, rel: str) -> str:
        new_label = self.label.rsplit(".", 1)[0] + f".{self.new}" if "." in self.label else self.new
        if self.drops:
            return f"{rel}: dropped {self.label} ({new_label} is already present; the canonical value wins)"
        return f"{rel}: {self.label} -> {new_label}"


def _rename_in_mapping(edit: _KeyEdit) -> None:
    mapping = edit.mapping
    if edit.drops:
        del mapping[edit.old]
        return
    position = list(mapping.keys()).index(edit.old)
    value = mapping.pop(edit.old)
    mapping.insert(position, edit.new, value)


def _rename_in_text(text: str, edits: list[_KeyEdit]) -> str | None:
    """Rename each key on its own line (byte-minimal); ``None`` when a key cannot be located."""
    lines = text.splitlines(keepends=True)
    located: list[tuple[int, int, _KeyEdit]] = []
    for edit in edits:
        try:
            line, column = edit.mapping.lc.key(edit.old)
        except (AttributeError, KeyError, TypeError):
            return None
        located.append((line, column, edit))
    for line, column, edit in sorted(located, key=lambda item: (item[0], item[1]), reverse=True):
        if line >= len(lines):
            return None
        source = lines[line]
        for quote in ("", '"', "'"):
            token = f"{quote}{edit.old}{quote}"
            if source.startswith(token, column):
                lines[line] = f"{source[:column]}{quote}{edit.new}{quote}{source[column + len(token) :]}"
                break
        else:
            return None
    return "".join(lines)


def _apply_key_edits(run: _Run, path: Path, text: str, data: Any, edits: list[_KeyEdit]) -> None:
    """Apply *edits* to the file at *path*, line-level when only renames, else a round-trip dump."""
    if not edits:
        return
    edited = None if any(edit.drops for edit in edits) else _rename_in_text(text, edits)
    if edited is None:
        for edit in edits:
            _rename_in_mapping(edit)
        edited = _dump(data)
    rel = run.rel(path)
    run.report.rewritten.extend(edit.describe(rel) for edit in edits)
    run.write_text(path, edited)


def _mapping_edit(data: Any, section: str | None, old: str, new: str, label: str) -> list[_KeyEdit]:
    mapping = data.get(section) if section is not None and isinstance(data, Mapping) else data
    if isinstance(mapping, CommentedMap) and old in mapping:
        return [_KeyEdit(mapping, old, new, label)]
    return []


def _activation_entries(data: Any) -> Iterator[CommentedMap]:
    if not isinstance(data, Mapping):
        return
    governance = data.get(_GOVERNANCE_KEY)
    for holder in (data, governance):
        entries = holder.get(_ACTIVATIONS_KEY) if isinstance(holder, Mapping) else None
        if isinstance(entries, list):
            yield from (entry for entry in entries if isinstance(entry, CommentedMap))


# --------------------------------------------------------------------------- #
# Ownership provers for the move (routed through specify_cli.asset_preservation)
# --------------------------------------------------------------------------- #


def _same_entry(source: Path, copy: Path) -> bool:
    """True when *copy* holds exactly what *source* holds (bytes, or the same link target)."""
    if source.is_symlink():
        return copy.is_symlink() and os.readlink(source) == os.readlink(copy)
    if copy.is_symlink() or not copy.is_file() or not source.is_file():
        return False
    return source.read_bytes() == copy.read_bytes()


class _MovedCopyProver:
    """Proves a retired-root file removable once its byte-identical copy exists in the pack root."""

    def __init__(self, copy: Path) -> None:
        self._copy = copy

    def prove(self, path: Path, project_path: Path) -> OwnershipProof | None:
        try:
            if _same_entry(path, self._copy):
                return OwnershipProof("canonical_content", f"moved-copy:{path.relative_to(project_path).as_posix()}")
        except (OSError, ValueError):
            return None
        return None


class _EmptyTreeProver:
    """Proves the retired root removable once only empty directories remain in it."""

    def prove(self, path: Path, project_path: Path) -> OwnershipProof | None:
        if path.is_symlink() or not path.is_dir():
            return None
        for dirpath, dirnames, filenames in os.walk(path):
            if filenames or any((Path(dirpath) / name).is_symlink() for name in dirnames):
                return None
        return OwnershipProof("managed_path", f"emptied-legacy-root:{path.relative_to(project_path).as_posix()}")


# --------------------------------------------------------------------------- #
# Steps 1-2: preflight and move
# --------------------------------------------------------------------------- #


def _legacy_entries(legacy_root: Path) -> list[Path]:
    """Every file and symlink under *legacy_root*, relative, sorted (dot-directories included)."""
    entries: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(legacy_root):
        base = Path(dirpath)
        entries.extend(base / name for name in filenames)
        entries.extend(base / name for name in dirnames if (base / name).is_symlink())
    return sorted(entry.relative_to(legacy_root) for entry in entries)


def _preflight(run: _Run) -> None:
    legacy = run.legacy_root
    if legacy.is_symlink():
        run.report.errors.append(f"{run.rel(legacy)} is a symlink; replace it with the directory it points to, then run `spec-kitty upgrade` again")
        return
    if not legacy.is_dir():
        return
    for rel in _legacy_entries(legacy):
        target = run.pack_root / rel
        if (target.exists() or target.is_symlink()) and not _same_entry(legacy / rel, target):
            run.report.errors.append(
                f"{run.rel(legacy / rel)} collides with {run.rel(target)} (different content); reconcile the two, then run `spec-kitty upgrade` again"
            )


def _move_one(run: _Run, rel: Path) -> None:
    from specify_cli.upgrade.autocommit import record_upgrade_mutation

    source = run.legacy_root / rel
    target = run.pack_root / rel
    if not (target.exists() or target.is_symlink()):
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_symlink():
            target.symlink_to(os.readlink(source))
        else:
            write_file_verbatim(source, target)
    verdict = guard_destructive_removal(source, run.project, prover=_MovedCopyProver(target))
    if not verdict.owned:
        raise OSError(f"the copy at {run.rel(target)} does not match ({verdict.reason})")
    record_upgrade_mutation(source, target, is_move=True)


def _move_project_root(run: _Run) -> None:
    legacy = run.legacy_root
    if not legacy.is_dir() or legacy.is_symlink():
        return
    for rel in _legacy_entries(legacy):
        line = f"{run.rel(legacy / rel)} -> {run.rel(run.pack_root / rel)}"
        if not run.dry_run:
            try:
                _move_one(run, rel)
            except OSError as exc:
                run.report.errors.append(f"{run.rel(legacy / rel)} could not be moved ({exc}); close any program holding it, then run `spec-kitty upgrade` again")
                return
        run.report.moved.append(line)
    if run.dry_run:
        return
    try:
        verdict = guard_destructive_removal(legacy, run.project, prover=_EmptyTreeProver(), is_tree=True)
    except OSError as exc:
        run.report.errors.append(f"{run.rel(legacy)} could not be removed ({exc}); run `spec-kitty upgrade` again")
        return
    if not verdict.owned:
        run.report.errors.append(f"{run.rel(legacy)} still holds files; move them to {run.rel(run.pack_root)}, then run `spec-kitty upgrade` again")


# --------------------------------------------------------------------------- #
# Step 3: path references
# --------------------------------------------------------------------------- #


def _rewrite_synthesis_manifest(run: _Run) -> None:
    from charter.bundle import SYNTHESIS_MANIFEST_PATH

    path = run.project / SYNTHESIS_MANIFEST_PATH
    text = _read_text(path, run.project)
    if text is None or not _mentions_legacy_root(text):
        return
    from pydantic import ValidationError

    from charter.activation.synthesizer.manifest import finalize_manifest, load_yaml
    from charter.activation.synthesizer.synthesize_pipeline import canonical_yaml

    try:
        manifest = load_yaml(path)
    except (OSError, YAMLError, ValidationError) as exc:
        raise _unreadable(path, run.project, exc) from exc
    artifacts = []
    rel = run.rel(path)
    for entry in manifest.artifacts:
        moved = _rewrite_legacy_path(entry.path)
        if moved is None:
            artifacts.append(entry)
            continue
        artifacts.append(entry.model_copy(update={"path": moved}))
        run.report.rewritten.append(f"{rel}: artifacts[].path {entry.path} -> {moved}")
    if artifacts == list(manifest.artifacts):
        return
    updated = finalize_manifest(manifest.model_copy(update={"artifacts": artifacts}))
    run.write_text(path, canonical_yaml(updated.model_dump(mode="python")).decode("utf-8"))


def _rewrite_values(node: Any, rel: str, trail: str, lines: list[str]) -> None:
    """Rewrite, in place, every string value under *node* that starts with the retired root."""
    children: list[tuple[Any, str]]
    if isinstance(node, Mapping):
        children = [(key, f"{trail}.{key}" if trail else str(key)) for key in node]
    elif isinstance(node, list):
        children = [(index, f"{trail}[{index}]") for index in range(len(node))]
    else:
        return
    for key, child_trail in children:
        value = node[key]
        moved = _rewrite_legacy_path(value)
        if moved is not None:
            node[key] = moved
            lines.append(f"{rel}: {child_trail} {value} -> {moved}")
        else:
            _rewrite_values(value, rel, child_trail, lines)


def _provenance_sidecars(run: _Run) -> list[Path]:
    from charter.bundle import PROVENANCE_DIR

    sidecars = sorted((run.project / PROVENANCE_DIR).glob("*.yaml"))
    for root in (run.legacy_root, run.pack_root):
        if root.is_dir() and not root.is_symlink():
            sidecars.extend(sorted(p for p in root.rglob("*.yaml") if p.parent.name == _PROVENANCE_DIRNAME))
    return sidecars


def _rewrite_provenance_sidecars(run: _Run) -> None:
    for path in _provenance_sidecars(run):
        text = _read_text(path, run.project)
        if text is None or not _mentions_legacy_root(text):
            continue
        data = _load_yaml(text, path, run.project)
        lines: list[str] = []
        _rewrite_values(data, run.rel(path), "", lines)
        if lines:
            run.report.rewritten.extend(lines)
            run.write_text(path, _dump(data))


def _rewrite_skills_manifest(run: _Run) -> None:
    path = run.project / _SKILLS_MANIFEST_RELPATH
    text = _read_text(path, run.project)
    if text is None or not _mentions_legacy_root(text):
        return
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise _unreadable(path, run.project, exc) from exc
    entries = data.get("entries") if isinstance(data, dict) else None
    changed = False
    for entry in entries if isinstance(entries, list) else []:
        moved = _rewrite_legacy_path(entry.get("source_ref")) if isinstance(entry, dict) else None
        if moved is not None:
            run.report.rewritten.append(f"{run.rel(path)}: entries[].source_ref {entry['source_ref']} -> {moved}")
            entry["source_ref"] = moved
            changed = True
    if changed:
        run.write_text(path, json.dumps(data, indent=2) + "\n")


def _gitignore_rewrite(lines: list[str]) -> tuple[list[str], list[str]]:
    """Return the rewritten ``.gitignore`` lines and one report fragment per changed rule."""
    existing = {line.strip() for line in lines}
    output: list[str] = []
    changes: list[str] = []
    for line in lines:
        rule = line.strip()
        if not rule or rule.startswith("#") or not _GITIGNORE_LEGACY_RULE.search(rule):
            output.append(line)
            continue
        new_rule = _GITIGNORE_LEGACY_RULE.sub(PROJECT_PACK_ROOT_POSIX, rule)
        if new_rule in existing:
            changes.append(f"dropped rule {rule} ({new_rule} is already present)")
            continue
        output.append(line.replace(rule, new_rule))
        existing.add(new_rule)
        changes.append(f"rule {rule} -> {new_rule}")
    return output, changes


def _rewrite_gitignore(run: _Run) -> None:
    """Rewrite ``.gitignore`` rules naming the retired root.

    A ``.gitignore`` that cannot be read safely (a symlink, not UTF-8, a
    directory, no permission) is reported for review, never actionable: an
    otherwise canonical project must not be selected because of it, and the
    run must not fail on it. A readable one whose rewrite cannot be written is
    a named error (the rules are known to need the rewrite).
    """
    path = run.project / _GITIGNORE
    try:
        text = read_gitignore_text(path)
    except (GitignorePathError, OSError) as exc:
        run.report.kept_for_review.append(f"{_GITIGNORE} could not be read safely ({exc}); check it for {LEGACY_PROJECT_ROOT_POSIX} rules by hand")
        return
    if text is None or LEGACY_PROJECT_ROOT_POSIX not in text:
        return
    lines, changes = _gitignore_rewrite(text.splitlines(keepends=True))
    if not changes:
        return
    if not run.dry_run:
        try:
            write_gitignore_text(path, "".join(lines))
        except (GitignorePathError, OSError) as exc:
            run.report.errors.append(f"{_GITIGNORE} could not be written ({exc}); make it writable, then run `spec-kitty upgrade` again")
            return
    run.report.rewritten.extend(f"{_GITIGNORE}: {change}" for change in changes)


def _rewrite_path_references(run: _Run) -> None:
    _rewrite_synthesis_manifest(run)
    _rewrite_provenance_sidecars(run)
    _rewrite_skills_manifest(run)
    _rewrite_gitignore(run)


# --------------------------------------------------------------------------- #
# Step 4: config keys
# --------------------------------------------------------------------------- #


def _single_pack_name(local_path: object, taken: set[str]) -> str:
    base = Path(str(local_path).replace("\\", "/")).name if local_path else ""
    name = _PACK_NAME_INVALID.sub("-", base.lower()).strip("-")
    if not name or name == _RESERVED_PACK_NAME:
        name = _FALLBACK_PACK_NAME
    candidate, suffix = name, 2
    while candidate in taken:
        candidate, suffix = f"{name}-{suffix}", suffix + 1
    return candidate


def _canonical_org(config: CommentedMap) -> Mapping[str, Any] | None:
    section = config.get(_CHARTER_PACKS_KEY)
    org = section.get(_ORG_KEY) if isinstance(section, Mapping) else None
    return org if isinstance(org, Mapping) else None


def _place_canonical_org(config: CommentedMap, org: CommentedMap, anchor: str) -> bool:
    """Set ``charter_packs.org`` to *org*; ``False`` when ``charter_packs`` is not a mapping."""
    section = config.get(_CHARTER_PACKS_KEY)
    if section is None:
        position = list(config.keys()).index(anchor) if anchor in config else len(config)
        config.insert(position, _CHARTER_PACKS_KEY, CommentedMap({_ORG_KEY: org}))
        return True
    if not isinstance(section, CommentedMap):
        return False
    section[_ORG_KEY] = org
    return True


def _drop_empty_legacy_section(run: _Run, config: CommentedMap, rel: str) -> None:
    section = config.get(LEGACY_SELECTION_KEYWORD)
    if isinstance(section, Mapping) and not section:
        del config[LEGACY_SELECTION_KEYWORD]
    elif isinstance(section, Mapping):
        run.report.kept_for_review.append(f"{rel}: {LEGACY_SELECTION_KEYWORD}: keeps {', '.join(map(str, section))} (not a charter-pack key)")


def _single_pack_org(org: CommentedMap) -> tuple[CommentedMap, str]:
    """One named pack entry built from the single-pack legacy fields of *org* (not mutated)."""
    entry = CommentedMap()
    entry["name"] = _single_pack_name(org.get(_LOCAL_PATH_KEY), set())
    for key in _SINGLE_PACK_FIELDS:
        if key in org:
            entry[key] = org[key]
    return CommentedMap({_PACKS_KEY: [entry]}), str(entry["name"])


def _rewrite_legacy_org(run: _Run, config: CommentedMap, rel: str) -> bool:
    org = legacy_org_block(config)
    if not isinstance(org, CommentedMap):
        return False
    legacy_label = f"{LEGACY_SELECTION_KEYWORD}.{_ORG_KEY}.{_PACKS_KEY}" if _PACKS_KEY in org else f"{LEGACY_SELECTION_KEYWORD}.{_ORG_KEY} (single-pack form)"
    section = config[LEGACY_SELECTION_KEYWORD]
    if _canonical_org(config) is not None:
        del section[_ORG_KEY]
        run.report.rewritten.append(f"{rel}: dropped {legacy_label} ({_CHARTER_PACKS_KEY}.{_ORG_KEY} is already present; the canonical value wins)")
    elif _PACKS_KEY in org:
        if not _place_canonical_org(config, org, LEGACY_SELECTION_KEYWORD):
            run.report.kept_for_review.append(f"{rel}: {legacy_label} kept ({_NOT_A_MAPPING})")
            return False
        del section[_ORG_KEY]
        run.report.rewritten.append(f"{rel}: {legacy_label} -> {_CHARTER_PACKS_KEY}.{_ORG_KEY}.{_PACKS_KEY}")
    else:
        canonical, name = _single_pack_org(org)
        if not _place_canonical_org(config, canonical, LEGACY_SELECTION_KEYWORD):
            run.report.kept_for_review.append(f"{rel}: {legacy_label} kept ({_NOT_A_MAPPING})")
            return False
        for key in _SINGLE_PACK_FIELDS:
            org.pop(key, None)
        if not org:
            del section[_ORG_KEY]
        run.report.rewritten.append(f"{rel}: {legacy_label} -> {_CHARTER_PACKS_KEY}.{_ORG_KEY}.{_PACKS_KEY} entry named {name!r}")
    _drop_empty_legacy_section(run, config, rel)
    return True


def _rewrite_organisation_packs(run: _Run, config: CommentedMap, rel: str) -> bool:
    flat = config.get(ORGANISATION_PACKS_KEYWORD)
    if not isinstance(flat, list) or not any(is_convertible_organisation_pack(entry) for entry in flat):
        if ORGANISATION_PACKS_KEYWORD in config:
            run.report.kept_for_review.append(f"{rel}: {ORGANISATION_PACKS_KEYWORD} kept (no entry converts to a local_path pack)")
        return False
    if _canonical_org(config) is not None:
        del config[ORGANISATION_PACKS_KEYWORD]
        run.report.rewritten.append(f"{rel}: dropped {ORGANISATION_PACKS_KEYWORD} ({_CHARTER_PACKS_KEY}.{_ORG_KEY} is already present; the canonical value wins)")
        return True
    converted = [CommentedMap({"name": e["name"], _LOCAL_PATH_KEY: e["path"]}) for e in flat if is_convertible_organisation_pack(e)]
    kept = [e for e in flat if not is_convertible_organisation_pack(e)]
    if not _place_canonical_org(config, CommentedMap({_PACKS_KEY: converted}), ORGANISATION_PACKS_KEYWORD):
        run.report.kept_for_review.append(f"{rel}: {ORGANISATION_PACKS_KEYWORD} kept ({_NOT_A_MAPPING})")
        return False
    names = ", ".join(str(entry["name"]) for entry in converted)
    run.report.rewritten.append(f"{rel}: {ORGANISATION_PACKS_KEYWORD} -> {_CHARTER_PACKS_KEY}.{_ORG_KEY}.{_PACKS_KEY} ({names})")
    if kept:
        config[ORGANISATION_PACKS_KEYWORD] = kept
        count = f"{len(kept)} entr{'y' if len(kept) == 1 else 'ies'}"
        run.report.kept_for_review.append(f"{rel}: {ORGANISATION_PACKS_KEYWORD} keeps {count} with a source other than local_path")
    else:
        del config[ORGANISATION_PACKS_KEYWORD]
    return True


def _rewrite_config_yaml(run: _Run) -> None:
    path = run.project / _CONFIG_RELPATH
    text = _read_text(path, run.project)
    if text is None or (LEGACY_SELECTION_KEYWORD not in text and ORGANISATION_PACKS_KEYWORD not in text):
        return
    config = _load_yaml(text, path, run.project)
    if not isinstance(config, CommentedMap):
        return
    rel = run.rel(path)
    changed = _rewrite_legacy_org(run, config, rel)
    changed = _rewrite_organisation_packs(run, config, rel) or changed
    edits = _mapping_edit(config, _GOVERNANCE_KEY, LEGACY_SELECTION_KEYWORD, _CHARTER_KEY, f"{_GOVERNANCE_KEY}.{LEGACY_SELECTION_KEYWORD}")
    edits += _mapping_edit(config, _TRACKER_KEY, LEGACY_SELECTION_KEYWORD, _OWNERSHIP_KEY, f"{_TRACKER_KEY}.{LEGACY_SELECTION_KEYWORD}")
    if not changed:
        _apply_key_edits(run, path, text, config, edits)
        return
    for edit in edits:
        run.report.rewritten.append(edit.describe(rel))
        _rename_in_mapping(edit)
    run.write_text(path, _dump(config))


def _config_mapping(run: _Run) -> Mapping[str, Any]:
    text = _read_text(run.project / _CONFIG_RELPATH, run.project)
    if text is None:
        return {}
    data = _load_yaml(text, run.project / _CONFIG_RELPATH, run.project)
    return data if isinstance(data, Mapping) else {}


def _charter_yaml_path(run: _Run) -> Path:
    from charter.bundle import CHARTER_YAML

    pointer = _config_mapping(run).get(_CHARTER_KEY)
    if isinstance(pointer, str) and pointer.strip():
        pointed = Path(pointer)
        return pointed if pointed.is_absolute() else run.project / pointed
    return run.project / Path(CHARTER_YAML)


def _load_candidate(run: _Run, path: Path, prefilter: re.Pattern[str]) -> tuple[str, Any] | None:
    text = _read_text(path, run.project)
    if text is None or not prefilter.search(text):
        return None
    return text, _load_yaml(text, path, run.project)


def _rewrite_governance_selection(run: _Run) -> None:
    """``governance.doctrine`` in the pointed ``charter.yaml``; top-level ``doctrine:`` in ``governance.yaml``."""
    path = _charter_yaml_path(run)
    loaded = _load_candidate(run, path, _LEGACY_KEY_LINE)
    if loaded is not None:
        text, data = loaded
        label = f"{_GOVERNANCE_KEY}.{LEGACY_SELECTION_KEYWORD}"
        _apply_key_edits(run, path, text, data, _mapping_edit(data, _GOVERNANCE_KEY, LEGACY_SELECTION_KEYWORD, _CHARTER_KEY, label))
    path = governance_file_path(run.project)
    loaded = _load_candidate(run, path, _TOP_LEVEL_LEGACY_KEY_LINE)
    if loaded is not None:
        text, data = loaded
        _apply_key_edits(run, path, text, data, _mapping_edit(data, None, LEGACY_SELECTION_KEYWORD, _CHARTER_KEY, LEGACY_SELECTION_KEYWORD))


def _rewrite_answers(run: _Run) -> None:
    path = run.project / _ANSWERS_RELPATH
    loaded = _load_candidate(run, path, _TOP_LEVEL_LEGACY_KEY_LINE)
    if loaded is not None:
        text, data = loaded
        _apply_key_edits(run, path, text, data, _mapping_edit(data, None, LEGACY_SELECTION_KEYWORD, _CHARTER_KEY, LEGACY_SELECTION_KEYWORD))


def _rewrite_config_keys(run: _Run) -> None:
    _rewrite_config_yaml(run)
    _rewrite_governance_selection(run)
    _rewrite_answers(run)


# --------------------------------------------------------------------------- #
# Step 5: doctrine_pack_id -> charter_pack_id
# --------------------------------------------------------------------------- #


def _rewrite_activation_pack_ids(run: _Run) -> None:
    for path in (_charter_yaml_path(run), governance_file_path(run.project)):
        loaded = _load_candidate(run, path, _LEGACY_KEY_LINE)
        if loaded is None:
            continue
        text, data = loaded
        label = f"{_ACTIVATIONS_KEY}[].{_LEGACY_PACK_ID_KEY}"
        edits = [_KeyEdit(entry, _LEGACY_PACK_ID_KEY, _PACK_ID_KEY, label) for entry in _activation_entries(data) if _LEGACY_PACK_ID_KEY in entry]
        _apply_key_edits(run, path, text, data, edits)


# --------------------------------------------------------------------------- #
# The migration
# --------------------------------------------------------------------------- #

#: ``apply()`` steps in contract order; a step that records an error stops the run.
#: WP12 inserts its reset and skills steps after the pack-id rewrite.
_STEPS: tuple[Callable[[_Run], None], ...] = (
    _preflight,
    _move_project_root,
    _rewrite_path_references,
    _rewrite_config_keys,
    _rewrite_activation_pack_ids,
)

#: The dry run :meth:`CharterPackCutoverMigration.structural_detect` uses to confirm a retired config key.
_STRUCTURAL_KEY_STEPS: tuple[Callable[[_Run], None], ...] = (_rewrite_config_keys, _rewrite_activation_pack_ids)


def _require_readable_layout(project_path: Path) -> None:
    """Fail before writing anything when a file the predicate reads cannot be parsed."""
    findings = detect_legacy_charter_layout(project_path)
    if UNREADABLE_PROJECT_ROOT in findings:
        reason = "could not be inspected (permission or I/O error); check its permissions, then run `spec-kitty upgrade` again"
        raise MigrationStateUnreadableError(f"{LEGACY_PROJECT_ROOT_POSIX} {reason}")
    if UNREADABLE_CONFIG in findings:
        raise MigrationStateUnreadableError(f"{_CONFIG_RELPATH.as_posix()} is not readable YAML; {_UPGRADE_REMEDY}")
    if UNREADABLE_GOVERNANCE_FILE in findings:
        rel = governance_file_path(project_path).relative_to(project_path).as_posix()
        raise MigrationStateUnreadableError(f"{rel} is not readable YAML; {_UPGRADE_REMEDY}")


def _run_steps(project_path: Path, *, dry_run: bool, steps: tuple[Callable[[_Run], None], ...] = _STEPS) -> CutoverReport:
    _require_readable_layout(project_path)
    run = _Run(project_path, dry_run)
    for step in steps:
        step(run)
        if run.report.errors:
            break
    return run.report


@MigrationRegistry.register
class CharterPackCutoverMigration(BaseMigration):
    """Rewrite pre-cutover project state into the charter vocabulary (FR-012)."""

    migration_id = MIGRATION_ID
    description = "Charter-pack cutover: move .kittify/doctrine to .kittify/charter-packs and rename the retired keys"
    target_version = "4.0.0rc6"
    runs_first = True
    runs_on_worktrees = False

    def detect(self, project_path: Path) -> bool:
        """True when any FR-012 inventory item is present. Total: an unreadable file selects."""
        try:
            if detect_legacy_charter_layout(project_path):
                return True
            return bool(_run_steps(project_path, dry_run=True).is_actionable())
        except Exception:  # total by contract: any failure selects the migration; apply() names it
            return True

    def structural_detect(self, project_path: Path) -> bool:
        """True for the structural legacy state only: retired root, retired keys, ``doctrine_pack_id``.

        A retired ``config.yaml`` key re-selects the migration only when a dry
        run can act on it: one kept for review (``charter_packs`` is not a
        mapping) would otherwise re-select a recorded cutover on every upgrade.
        """
        try:
            findings = set(detect_legacy_charter_layout(project_path))
            if findings - CONFIG_KEY_FINDINGS:
                return True
            steps = _STRUCTURAL_KEY_STEPS if findings else (_rewrite_activation_pack_ids,)
            return bool(_run_steps(project_path, dry_run=True, steps=steps).is_actionable())
        except Exception:  # total by contract: any failure selects the migration; apply() names it
            return True

    def is_first_application(self, project_path: Path) -> bool:
        """True while ``metadata.yaml`` does not record this migration as applied.

        The WP12 resets run only then, so a structural re-run never resets a
        deliberate post-cutover ``activated_<kind>: []`` again.
        """
        try:
            metadata = ProjectMetadata.load(project_path / KITTIFY_DIRNAME)
        except Exception:  # unreadable metadata: treat the migration as never recorded
            return True
        return metadata is None or not metadata.has_migration(self.migration_id)

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        """Always applicable; the collision preflight runs inside ``apply()`` so a dry run reports it."""
        del project_path
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        """Run the cutover steps in contract order and report every change."""
        return _run_steps(project_path, dry_run=dry_run).to_migration_result(dry_run=dry_run)
