"""Conservative declarative dependency closure for report-only analysis.

Runtime/status/cache outputs are deliberately not inputs. Explicit authority
references are included even when absent; directory membership is represented
by the set of entries, so adding a new authority also invalidates a report.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, NamedTuple, cast

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from charter.activation.context_renderers.authority_paths import DEFAULT_AUTHORITY_PATHS
from charter.activation.pack_context import resolve_charter_yaml_pointer
from charter.bundle import CHARTER_MD, CHARTER_YAML
from charter.drg import load_pack_registry
from charter.pack_paths import PackRootNotFound, built_in_root
from kernel.charter_pack_paths import project_pack_root
from kernel.pack_tiers import pin_filename
from kernel.paths import get_package_asset_root


class MaterialInputError(ValueError):
    """The declared dependency closure cannot be safely represented."""


#: The mission metadata file whose VCS lock the first claim writes (#7106).
META_FILENAME = "meta.json"


def _mapping(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = YAML(typ="safe").load(path.read_text(encoding="utf-8"))
    except YAMLError as exc:
        raise MaterialInputError(f"Malformed material input: {path.name}") from exc
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise MaterialInputError(f"Expected mapping in {path.name}")
    return value


def _safe_path(root: Path, path: Path) -> Path:
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise MaterialInputError("External mutable analysis authority is unsupported") from exc
    cursor = root
    for part in relative.parts:
        if part == "..":
            raise MaterialInputError("Analysis authority escapes repository")
        cursor /= part
        if cursor.is_symlink():
            raise MaterialInputError("Analysis authority contains a symlink")
    return path


def _declared_paths(charter: dict[str, Any], *, source: Path) -> list[str]:
    from charter.activation.sync import require_canonical_governance

    governance = charter.get("governance", {})
    charter_cfg = require_canonical_governance(governance, source=source).get("charter", {}) if isinstance(governance, dict) else {}
    if not isinstance(charter_cfg, dict):
        raise MaterialInputError("governance.charter must be a mapping")
    paths = list(DEFAULT_AUTHORITY_PATHS)
    for key in ("authority_paths", "governance_references"):
        declared = charter_cfg.get(key, [])
        if not isinstance(declared, list) or not all(isinstance(value, str) for value in declared):
            raise MaterialInputError(f"{key} must be a list of paths")
        paths.extend(declared)
    return paths


def _references(value: Any, field: str) -> list[str]:
    paths = []
    if isinstance(value, dict):
        for key, nested in value.items():
            if key == field and isinstance(nested, str) and nested:
                paths.append(nested)
            else:
                paths.extend(_references(nested, field))
    elif isinstance(value, list):
        for nested in value:
            paths.extend(_references(nested, field))
    return paths


def _entry(path: Path, root: Path, feature_dir: Path) -> dict[str, str | None]:
    from specify_cli.analysis_report import _artifact_hash_entry

    relative = path.relative_to(root).as_posix()
    if path.is_dir():
        return {"path": relative, "sha256": "directory"}
    if not path.exists():
        return {"path": relative, "sha256": None}
    if path.parent == feature_dir / "tasks" and path.suffix == ".md" and path.name.startswith("WP"):
        return _wp_prompt_fingerprint(path, relative)
    if path == feature_dir / META_FILENAME:
        return _meta_fingerprint(path, relative)
    return cast(dict[str, str | None], _artifact_hash_entry(path, root))


def _wp_prompt_fingerprint(path: Path, relative: str) -> dict[str, str | None]:
    """Fingerprint a work-package prompt's planning content, never its runtime churn.

    ``MUTABLE_FIELDS`` covers the lane/review state older spines wrote; the claim's
    own workspace provenance (:data:`~specify_cli.frontmatter.WP_CLAIM_PROVENANCE_FIELDS`)
    is what ``agent action implement`` stamps into a freshly allocated lane's prompt.
    Neither is planning input, so neither may stale a recorded analysis (#7106).
    Everything else -- every authored planning field, unknown legacy keys included,
    and the body -- still gates freshness.

    A prompt the old code hashed is never rejected here: the read stays the tolerant
    ``FrontmatterManager`` read, and the exclusion is a key filter over the raw
    mapping (never a strict ``WPMetadata`` re-parse, whose ``extra="forbid"`` would
    turn retired keys into a new refusal).
    """
    from specify_cli.analysis_report import _sha256_text
    from specify_cli.frontmatter import WP_CLAIM_PROVENANCE_FIELDS, FrontmatterError, FrontmatterManager
    from specify_cli.migration.strip_frontmatter import MUTABLE_FIELDS

    try:
        metadata, body = FrontmatterManager().read(path)
    except FrontmatterError as exc:
        raise MaterialInputError(f"Invalid WP definition: {path.name}") from exc
    excluded = MUTABLE_FIELDS | set(WP_CLAIM_PROVENANCE_FIELDS)
    static = {key: value for key, value in metadata.items() if key not in excluded}
    return {"path": relative, "sha256": _sha256_text(json.dumps(static, sort_keys=True, default=str) + "\n" + body)}


def _meta_mapping(path: Path) -> dict[str, Any]:
    """Read ``meta.json`` through the canonical decoder, failing closed as material input.

    ``mission_metadata.parse_meta_file`` is the path-holding L2 reader over the kernel
    L1 decoder, and the tree runs exactly one meta decoder
    (``tests/architectural/test_inline_meta_read_gate.py``), so this module never
    hand-rolls one. Its ``ValueError`` (malformed JSON, non-object top level, an empty
    document) becomes a :class:`MaterialInputError`: metadata that cannot be read
    cannot be certified as unchanged planning input. The missing-file sentinel is
    decided before this call, so an absent ``meta.json`` is never an error.
    """
    from specify_cli.mission_metadata import parse_meta_file

    try:
        metadata = parse_meta_file(path)
    except (OSError, ValueError) as exc:
        raise MaterialInputError(f"Invalid mission metadata: {path.name}") from exc
    if not isinstance(metadata, dict):
        raise MaterialInputError(f"Expected mapping in {path.name}")
    return metadata


def _meta_fingerprint(path: Path, relative: str) -> dict[str, str | None]:
    """Fingerprint a mission's ``meta.json`` with its runtime VCS lock normalised away.

    A mission's first claim locks the VCS backend in ``meta.json``
    (``implement_support.ensure_vcs_locked``). That lock is runtime bookkeeping, not
    planning input, so it must not stale a recorded analysis (#7106). The lock's
    names and its normalisation stay in their single home: this module calls
    :func:`kernel.vcs_lock.project_metadata_without_vcs_lock` rather than reading the
    field set, because the tree-wide singleton gate forbids a second inspector.

    Every key the projection keeps -- ``target_branch``, ``topology``, ``mission_id``,
    ``status_phase``, and any lock value a claim would never write -- still gates
    freshness.
    """
    from kernel.vcs_lock import project_metadata_without_vcs_lock

    from specify_cli.analysis_report import _sha256_text

    planning = project_metadata_without_vcs_lock(_meta_mapping(path))
    return {"path": relative, "sha256": _sha256_text(json.dumps(planning, sort_keys=True, default=str) + "\n")}


def _source_paths(charter: dict[str, Any], root: Path) -> list[Path]:
    paths = []
    for value in _references(charter, "source_path"):
        # Bundled provenance is covered by its digest; URL provenance is
        # declarative charter text, not a filesystem dependency.
        if value.startswith("${SPEC_KITTY_PACKS_ROOT}/") or "://" in value:
            continue
        if "$" in value:
            raise MaterialInputError("Unresolved external authority source is unsupported")
        paths.append(root / value)
    return paths


def _package_inputs() -> dict[str, dict[str, str | None]]:
    """Content-pin bundled authority without embedding machine-local paths."""
    from specify_cli.analysis_report import _sha256_file, _sha256_text

    if os.environ.get("SPEC_KITTY_PACKS_ROOT") or os.environ.get("SPEC_KITTY_TEMPLATE_ROOT"):
        raise MaterialInputError("Environment-selected mutable package authority is unsupported")
    result = {}
    try:
        roots = (("built-in", built_in_root()), ("mission-assets", get_package_asset_root()))
    except (PackRootNotFound, OSError) as exc:
        raise MaterialInputError("Bundled analysis authority unavailable") from exc
    for label, root in roots:
        rows = []
        for path in sorted(root.rglob("*")):
            if path.is_symlink():
                raise MaterialInputError("Bundled analysis authority contains a symlink")
            if path.is_file() and "__pycache__" not in path.parts:
                rows.append(f"{path.relative_to(root).as_posix()}:{_sha256_file(path)}")
        result[f"package:{label}"] = {"path": None, "sha256": _sha256_text("\n".join(rows))}
    return result


def _global_template_mirror(path: Path, *, mission: str, tier: str) -> str:
    """Admit only regular, canonically addressed copies of the packaged template."""
    from charter.activation.resolver import ActiveCharterService
    from specify_cli.runtime.resolver import get_kittify_home

    home = get_kittify_home().absolute()
    if any(parent.is_symlink() for parent in (home, *home.parents)):
        raise MaterialInputError("Global template authority contains a symlink")
    _safe_path(home, path)
    relative = path.relative_to(home).as_posix()
    expected = Path("missions") / mission / "templates" / path.name if tier == "GLOBAL_MISSION" else Path("templates") / path.name
    package = ActiveCharterService.resolve_package_default_asset_path(
        missions_root=get_package_asset_root(),
        mission=mission,
        subdir="templates",
        name=path.name,
    )
    if relative != expected.as_posix() or package is None or not path.is_file():
        raise MaterialInputError("External mutable global template authority is unsupported")
    _safe_path(get_package_asset_root(), package)
    if not package.is_file() or path.read_bytes() != package.read_bytes():
        raise MaterialInputError("External mutable global template authority is unsupported")
    return relative


def _resolved_template_paths(root: Path, feature_dir: Path) -> tuple[list[Path], dict[str, dict[str, str | None]]]:
    from charter.activation.mission_type_profiles import resolve_mission_type_context
    from charter.activation.pack_context import ActiveCharterConfigError
    from specify_cli.analysis_report import _sha256_file, _sha256_text
    from specify_cli.runtime.resolver import ResolutionTier, resolve_configured_template

    metadata = _mapping(feature_dir / "meta.json")
    mission_type = metadata.get("mission_type")
    if mission_type is None:
        return [], {}
    try:
        context = resolve_mission_type_context(root, mission_type=mission_type)
    except ActiveCharterConfigError as exc:
        raise MaterialInputError("Configured charter activation is invalid") from exc
    paths = []
    selections = {}
    for kind in context.template_set or {}:
        resolved = resolve_configured_template(kind, root, context)
        if resolved.tier in (ResolutionTier.GLOBAL, ResolutionTier.GLOBAL_MISSION):
            address = _global_template_mirror(resolved.path, mission=mission_type, tier=resolved.tier.name)
        elif resolved.tier is ResolutionTier.PACKAGE_DEFAULT:
            address = resolved.path.relative_to(get_package_asset_root()).as_posix()
        else:
            address = _safe_path(root, resolved.path).relative_to(root).as_posix()
            paths.append(resolved.path)
        identity = {
            "mission": mission_type,
            "kind": kind,
            "tier": resolved.tier.name,
            "address": address,
            "selected_path": str(resolved.path.absolute()),
            "sha256": _sha256_file(resolved.path),
        }
        selections[f"template-selection:{kind}"] = {"path": None, "sha256": _sha256_text(json.dumps(identity, sort_keys=True))}
    return paths, selections


def _registry_pack_roots(repo_root: Path) -> dict[str, Path]:
    """Repo-relative root -> absolute path, for every registry pack that resolves inside the repo."""
    root = repo_root.absolute()
    try:
        packs = load_pack_registry(root).packs
    except (OSError, ValueError):  # defensive: today's lenient loader returns an empty registry
        return {}
    candidates: dict[str, Path] = {}
    for pack in packs:
        try:
            pack_root = pack.effective_root(root)
        except ValueError:  # OrgPackEnvVarUnsetError / OrgPackSubdirEscapeError: not addressable here
            continue
        try:
            relative = pack_root.relative_to(root).as_posix()
        except ValueError:
            continue
        if pack_root.is_dir():
            candidates[relative] = pack_root
    return candidates


def _contains_symlink(root: Path, relative: str) -> bool:
    """Does any component of *relative* under *root* name a symlink?

    A symlinked pin is the one way a *tracked, clean* path could still carry
    authority bytes from outside the repository, so it must grant nothing. The
    walk mirrors :func:`_safe_path`, the same rule material inputs are held to.
    """
    cursor = root
    for part in Path(relative).parts:
        cursor /= part
        if cursor.is_symlink():
            return True
    return False


def _pin_states(repo_root: Path, pin_paths: tuple[str, ...]) -> tuple[set[str], set[str]]:
    """Tracked and dirty sets for the candidate pin lockfiles, in one git listing each."""
    from kernel.git import status_entries, tracked_paths

    if not pin_paths:
        return set(), set()
    root = repo_root.absolute()
    tracked = {str(path) for path in tracked_paths(root, pathspecs=pin_paths)}
    dirty = {str(entry.path) for entry in status_entries(root, pathspecs=pin_paths, untracked="all")}
    return tracked, dirty


class PackPinState(NamedTuple):
    """What the committed pack pins establish about the fetched trees on disk (#7128).

    ``verified_roots`` are repo-relative roots a committed pin content-verifies: a
    tree there is a material input with committed state, so the report
    transaction must not refuse it as an input with no committed state.
    ``refused_pins`` are the sibling lockfiles that exist on disk but could not
    establish committed state (untracked, dirty, or a symlink), so a refusal can
    also name that cause beside any uncommitted pack files.

    The tuples contain repo-relative POSIX roots and pin paths, never a boolean verdict: a caller
    subtracting ``verified_roots`` cannot degrade the rule into "ignored paths
    are clean", because every other untracked or ignored material input keeps
    refusing exactly as before.
    """

    verified_roots: tuple[str, ...] = ()
    refused_pins: tuple[str, ...] = ()


def pack_pin_state(repo_root: Path) -> PackPinState:
    """Resolve ``PACK_ROOT -> committed pin`` for every fetched, registry-declared pack tree.

    ``packs/<name>/`` is gitignored because ``make sync-packs`` *fetches* it from
    the commit recorded in the tracked ``packs/<name>.source.yaml``
    (``charter.offering.packs.pack_fetch``); the tree's committed state is that
    pin -- ``commit``, ``subtree``, ``tree_digest`` and ``snapshot_sha256`` --
    not a blob in this repository.

    Pack/pin defects fail closed: a missing, dirty, untracked or symlinked pin,
    a non-mirroring ``subtree``, unverifiable digests, an in-tree symlink, or an
    unreadable/unparseable ``pack.yaml`` yields no verified root. Git probe failures
    propagate to the transaction's fail-closed exception handler. Its whole-index
    guard also rejects unsupported index flags before any report write.

    This deliberately supports the sibling pin of the resolved root and a subtree
    matching that repo-relative root, including the documented ``make sync-packs``
    layout. It does not infer a pin location from a registry alias or upstream path.
    The check is offline/read-only; it proves equality to committed pin digests,
    not the existence or contents of a remote commit.
    """
    from charter.packs import PackSyncError, PackTreeStatus, check_pack, load_pack_pin

    root = repo_root.absolute()
    candidates = _registry_pack_roots(root)
    if not candidates:
        return PackPinState()
    # Preserve the sibling-root binding; the filename spelling has one kernel owner.
    pin_paths = {relative: (Path(relative).parent / pin_filename(Path(relative).name)).as_posix() for relative in sorted(candidates)}
    tracked, dirty = _pin_states(root, tuple(pin_paths.values()))
    verified: list[str] = []
    refused: list[str] = []
    for relative in sorted(candidates):
        pin_relative = pin_paths[relative]
        # Committed authority only: a dirty pin is not the pin the tree was fetched
        # against, and a symlinked pin carries bytes from outside this repository.
        # A symlinked *tree* needs no check here: ``effective_root`` resolves, so a
        # root whose real path escapes the repository never becomes a candidate at
        # all. The canonical offline check below explicitly refuses in-tree links.
        if pin_relative not in tracked or pin_relative in dirty or _contains_symlink(root, pin_relative):
            # Only a pin that exists is worth naming: a *missing* lockfile means the
            # tree is not pin-managed at all, and pointing at a path that is not there
            # would misdirect the operator.
            if (root / pin_relative).exists() or (root / pin_relative).is_symlink():
                refused.append(pin_relative)
            continue
        try:
            pin = load_pack_pin(root / pin_relative)
            if pin.subtree != relative or check_pack(pin, candidates[relative]) is not PackTreeStatus.OK:
                continue
        except (OSError, ValueError, YAMLError, PackSyncError):
            # PackPinError / pydantic ValidationError (both ValueError), an
            # unreadable file, or a pack.yaml that does not parse: not verified.
            continue
        verified.append(relative)
    return PackPinState(tuple(verified), tuple(refused))
def _include(root: Path, paths: set[Path], path: Path, *, recurse: bool = True) -> None:
    """Add *path* (recursively by default) to a material closure, refusing escapes."""
    path = _safe_path(root, path)
    if path.is_dir():
        paths.add(path)
        if not recurse:
            return
        for child in sorted(path.iterdir()):
            _include(root, paths, child)
        return
    if path.exists() and not path.is_file():
        raise MaterialInputError("Non-regular analysis authority is unsupported")
    paths.add(path)


def _include_work_package_tasks(root: Path, paths: set[Path], feature_dir: Path) -> None:
    """Include the flat ``tasks/`` planning surface, never its per-WP runtime dirs.

    Planning content under ``tasks/`` is flat (one ``WP##-*.md`` prompt per work
    package; sub-directories there are explicitly not the planning layout).
    ``tasks/<wp>/`` instead holds generated runtime artifacts a review cycle rewrites --
    ``review-cycle-N.md``, ``review-feedback-N.md``, ``baseline-tests.json`` -- and those
    must not stale a recorded analysis when a rejected work package is re-claimed
    (#7106). The directory sentinel plus every non-directory entry stay in, so an
    added, removed or renamed prompt still counts.
    """
    tasks_dir = feature_dir / "tasks"
    _include(root, paths, tasks_dir, recurse=False)
    if not tasks_dir.is_dir():
        return
    for child in sorted(tasks_dir.iterdir()):
        if not child.is_dir():
            _include(root, paths, child)


def collect_material_inputs(feature_dir: Path, repo_root: Path) -> dict[str, dict[str, str | None]]:
    """Collect project-owned material inputs, using canonical path authorities.

    This mode rejects external mutable org packs rather than pretending that a
    project Git transaction can establish their committed state.
    """
    from specify_cli.analysis_report import _hash_inputs

    root = repo_root.absolute()
    paths: set[Path] = set()

    def include(path: Path, *, recurse: bool = True) -> None:
        _include(root, paths, path, recurse=recurse)

    config_path = root / ".kittify/config.yaml"
    include(config_path)
    config = _mapping(config_path)
    charter_path = resolve_charter_yaml_pointer(root, config) or root / CHARTER_YAML
    include(charter_path)
    charter = _mapping(charter_path)
    for name in (*_hash_inputs(), META_FILENAME, "wps.yaml"):
        include(feature_dir / name)
    _include_work_package_tasks(root, paths, feature_dir)
    # Only declarative subtrees: no charter context-state, synthesis manifest,
    # operation logs, runtime cache, status streams or generated task state.
    for name in ("missions", "overrides", "templates", "command-templates"):
        include(root / ".kittify" / name)
    include(project_pack_root(root))
    for name in (CHARTER_MD.name, "interview/answers.yaml", "_LIBRARY"):
        include(charter_path.parent / name)
    for value in _declared_paths(charter, source=charter_path):
        include(root / value)
    for pack in load_pack_registry(root).packs:
        include(pack.effective_root(root))

    for value in _references(charter, "local_path"):
        include(charter_path.parent / value)
    for path in _source_paths(charter, root):
        include(path)
    template_paths, selections = _resolved_template_paths(root, feature_dir)
    for path in template_paths:
        include(path)

    result: dict[str, dict[str, str | None]] = {}
    for path in sorted(paths):
        relative = path.relative_to(root).as_posix()
        # Directory sentinels and missing-file sentinels are distinct. The
        # complete key set detects additions/removals without hashing outputs.
        result[f"material:{relative}"] = _entry(path, root, feature_dir)
    result.update(_package_inputs())
    result.update(selections)
    return result
