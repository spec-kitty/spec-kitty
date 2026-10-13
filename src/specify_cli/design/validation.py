"""Authoring prerequisites composed from canonical validators and provenance."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Literal

from kernel.git import GitCommandError, run_git
from kernel.git_topology import GitTopologyError, NotAGitRepositoryError
from kernel.paths import repo_tree_path
from mission_runtime import MissionArtifactKind, placement_seam
from pydantic import ValidationError

from specify_cli.core.dependency_graph import detect_cycles
from specify_cli.core.wps_manifest import WpsManifest, WpsManifestReadError, load_wps_manifest
from specify_cli.decisions.models import DecisionStatus
from specify_cli.decisions.store import load_index
from specify_cli.design.errors import DesignError
from specify_cli.design.models import ArtifactInput, ReceiptSet
from specify_cli.design.receipts import api_authoring_enabled, authoring_lock, content_digest, read_receipts, save_receipts
from specify_cli.frontmatter import FrontmatterError, read_frontmatter
from specify_cli.mission import get_mission_type
from specify_cli.missions._substantive import is_committed, is_substantive
from specify_cli.requirement_mapping import parse_requirement_ids_from_spec_md
from specify_cli.requirement_mapping.lint import lint_spec_requirement_ids
from specify_cli.runtime.resolver import resolve_configured_artifact_name
from specify_cli.status import StoreError, tasks_are_finalized

if TYPE_CHECKING:
    from mission_runtime import OwnedCheckout


def _tasks_finalized(repo_root: Path, mission_slug: str) -> bool:
    status_dir = placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.STATUS_STATE)
    try:
        return bool(tasks_are_finalized(status_dir))
    except StoreError as exc:
        raise DesignError("DESIGN_STATUS_EVENT_LOG_UNREADABLE", "Canonical mission status cannot be trusted") from exc


def require_unfinalized(repo_root: Path, mission_slug: str) -> None:
    """Any native finalized WP freezes all design writes through this surface."""
    if _tasks_finalized(repo_root, mission_slug):
        raise DesignError("DESIGN_FINALIZED", "Finalized planning content requires the native reconciliation workflow")


@contextmanager
def _marker_gated_lock(repo_root: Path, mission_slug: str) -> Iterator[bool]:
    """Yield whether API authoring is enabled, holding the authoring lock only if it is.

    Double-checked: the marker is read WITHOUT the lock first, so a Mission that
    is not API-authored never takes the lock. A marked Mission takes the lock and
    re-reads the marker inside it, so a concurrent API writer cannot change
    content between the proof and the guarded completion. A path with no git
    repository cannot carry the marker (it lives in the git common dir): skip.
    If git is present but unusable, the marker cannot be read and the Mission
    cannot be proved not API-authored, so refuse instead of failing open.
    """
    if not _marker_present(repo_root, mission_slug):
        yield False
        return
    with authoring_lock(repo_root, mission_slug):
        yield api_authoring_enabled(repo_root, mission_slug)


def _marker_present(repo_root: Path, mission_slug: str) -> bool:
    try:
        return bool(api_authoring_enabled(repo_root, mission_slug))
    except NotAGitRepositoryError:
        return False
    except GitTopologyError as exc:
        raise DesignError("DESIGN_IO_FAILED", "Git topology is unavailable, so API-authored content cannot be verified") from exc


@contextmanager
def api_authoring_completion_gate(repo_root: Path, mission_slug: str, *, owned: OwnedCheckout | None = None) -> Iterator[None]:
    """Native-completion gate for an API-authored Mission (#5879): prove, then complete.

    Holds the authoring lock across the read-only stale/unfinished-content proof
    of the natively issued stage AND the caller's completion, so an API writer
    cannot change content in between. Raises ``DesignError`` before the body runs
    (no mutation on refusal). A Mission without the marker, or whose tasks are
    already finalized (later native edits are the reconciliation workflow's), is
    not re-proved.
    """
    from runtime.next.runtime_bridge_query import MissionNotFoundError, issued_step_id_for_mission

    with _marker_gated_lock(repo_root, mission_slug) as enabled:
        if enabled and not _tasks_finalized(repo_root, mission_slug):
            try:
                issued_stage = issued_step_id_for_mission(mission_slug, repo_root, owned=owned)
            except MissionNotFoundError as exc:
                raise DesignError("DESIGN_PREREQUISITES_FAILED", "Native issued state is unavailable") from exc
            if issued_stage in ("specify", "plan", "tasks"):
                validate_stage(repo_root, mission_slug, issued_stage)
        yield


def _validate_manifest_graph(manifest: WpsManifest, mission_dir: Path) -> None:
    from specify_cli.design.authoring import manifest_prompt_name

    packages = manifest.work_packages
    ids = {entry.id for entry in packages}
    if not packages or len(packages) > 64 or len(ids) != len(packages):
        raise DesignError("DESIGN_PREREQUISITES_FAILED", "The outline requires 1–64 unique package keys")
    specification = resolve_configured_artifact_name("input.spec.main", get_mission_type(mission_dir))
    declared = set(parse_requirement_ids_from_spec_md((mission_dir / specification).read_text(encoding="utf-8"))["all"])
    for entry in packages:
        manifest_prompt_name(manifest, entry.id)
        if len(entry.dependencies) > 64 or set(entry.dependencies) - ids:
            raise DesignError("DESIGN_PREREQUISITES_FAILED", "Package dependencies must identify declared bounded packages")
        if not entry.title.strip() or not entry.requirement_refs or set(entry.requirement_refs) - declared:
            raise DesignError("DESIGN_PREREQUISITES_FAILED", "Packages require objectives and declared requirement references")
    if detect_cycles({entry.id: entry.dependencies for entry in packages}):
        raise DesignError("DESIGN_PREREQUISITES_FAILED", "The package graph contains a dependency cycle")


def validated_manifest(content: str, mission_dir: Path) -> WpsManifest:
    """Use the canonical YAML/Pydantic reader before touching mission files."""
    try:
        with TemporaryDirectory(prefix="spec-kitty-outline-") as temporary:
            root = Path(temporary)
            (root / "wps.yaml").write_text(content, encoding="utf-8")
            manifest = load_wps_manifest(root)
    except (WpsManifestReadError, ValidationError) as exc:
        raise DesignError("DESIGN_PREREQUISITES_FAILED", "The outline does not satisfy the canonical manifest schema") from exc
    if manifest is None:
        raise DesignError("DESIGN_PREREQUISITES_FAILED", "No work-package manifest was supplied")
    _validate_manifest_graph(manifest, mission_dir)
    return manifest


def _validate_source(repo_root: Path, mission_dir: Path, item: ArtifactInput) -> None:
    kind: Literal["spec", "plan"] = "spec" if item.kind == "specification" else "plan"
    with TemporaryDirectory(prefix="spec-kitty-design-") as temporary:
        path = Path(temporary) / f"{kind}.md"
        path.write_text(item.content, encoding="utf-8")
        substantive = is_substantive(path, kind, mission_type=get_mission_type(mission_dir), project_dir=repo_root)
    if not substantive:
        raise DesignError("DESIGN_PREREQUISITES_FAILED", "The authored source is still a placeholder scaffold")
    if kind == "spec" and lint_spec_requirement_ids(item.content).blocking:
        raise DesignError("DESIGN_PREREQUISITES_FAILED", "The specification declares invalid requirement identifiers")


def _validate_prompt(item: ArtifactInput, manifest: WpsManifest | None) -> None:
    if manifest is None:
        raise DesignError("DESIGN_PREREQUISITES_FAILED", "Package prompts require an outline")
    try:
        with TemporaryDirectory(prefix="spec-kitty-package-") as temporary:
            path = Path(temporary) / "prompt.md"
            path.write_text(item.content, encoding="utf-8")
            frontmatter, body = read_frontmatter(path)
    except FrontmatterError as exc:
        raise DesignError("DESIGN_PREREQUISITES_FAILED", "Package frontmatter is invalid") from exc
    entries = [entry for entry in manifest.work_packages if entry.id == item.artifact_id]
    if len(entries) != 1 or frontmatter.get("work_package_id") != item.artifact_id or not body.strip():
        raise DesignError("DESIGN_PREREQUISITES_FAILED", "Prompt identity/content does not match its declared package")
    entry = entries[0]
    for field in ("dependencies", "requirement_refs", "owned_files", "subtasks"):
        if frontmatter.get(field, []) != getattr(entry, field):
            raise DesignError("DESIGN_PREREQUISITES_FAILED", "Prompt definition disagrees with its manifest", {"field": field, "wp_id": entry.id})
    forbidden = {"lane", "review_status", "reviewed_by", "review_feedback", "tracker_refs", "shell_pid", "shell_pid_created_at"}
    if forbidden.intersection(frontmatter):
        raise DesignError("DESIGN_REQUEST_INVALID", "Authored prompts cannot supply runtime/status authority")


def validate_content(repo_root: Path, mission_slug: str, item: ArtifactInput, manifest: WpsManifest | None) -> None:
    """Validate a draft using existing source/frontmatter/manifest authorities."""
    if not item.content.strip():
        raise DesignError("DESIGN_PREREQUISITES_FAILED", "An authored artifact cannot be empty")
    mission_dir = placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.SPEC)
    if item.kind in ("specification", "plan"):
        _validate_source(repo_root, mission_dir, item)
    elif item.kind == "work_package":
        _validate_prompt(item, manifest)


def require_committed_content(repo_root: Path, mission_slug: str, kind: str) -> None:
    """Reuse substantive/committed predicates, also reject a dirty parent body."""
    from specify_cli.design.authoring import artifact_path

    path = artifact_path(repo_root, mission_slug, kind)
    if not path.exists() or not is_committed(path, repo_root):
        raise DesignError("DESIGN_PREREQUISITES_FAILED", "The parent artifact must be committed", {"kind": kind})
    git_root, relative = repo_tree_path(path, repo_root)
    try:
        committed = run_git(git_root, "show", f"HEAD:{relative}", timeout=10).stdout
    except GitCommandError as exc:
        raise DesignError("DESIGN_PREREQUISITES_FAILED", "The committed parent could not be read") from exc
    if committed != path.read_bytes():
        raise DesignError("DESIGN_PREREQUISITES_FAILED", "The parent has materialized changes that are not committed", {"kind": kind})
    if kind in ("specification", "plan"):
        content = ArtifactInput(kind=kind, content=path.read_text(encoding="utf-8"), expected_sha256=content_digest(path))
        validate_content(repo_root, mission_slug, content, None)


def _check_receipt_lineage(repo_root: Path, mission_slug: str, stage: str, receipts: ReceiptSet) -> None:
    from specify_cli.design.authoring import artifact_action, artifact_path
    from specify_cli.design.context import planning_context_digest

    for receipt in receipts.artifacts.values():
        if stage == "specify" and artifact_action(receipt.kind) != "specify":
            continue
        if stage == "plan" and artifact_action(receipt.kind) == "tasks":
            continue
        if content_digest(artifact_path(repo_root, mission_slug, receipt.kind, receipt.artifact_id)) != receipt.sha256:
            raise DesignError("DESIGN_PARENT_STALE", "Accepted content changed outside its authoring receipt", {"kind": receipt.kind})
        for parent, expected in receipt.parents.items():
            if content_digest(artifact_path(repo_root, mission_slug, parent)) != expected:
                raise DesignError("DESIGN_PARENT_STALE", "Accepted content has stale parent provenance", {"kind": receipt.kind, "parent": parent})
        if planning_context_digest(repo_root, mission_slug, receipt.context_action) != receipt.context_sha256:
            raise DesignError("DESIGN_CONTEXT_STALE", "Accepted content was authored against old governance/templates")


def _required_receipts(repo_root: Path, mission_slug: str, stage: str, receipts: ReceiptSet) -> None:
    from specify_cli.design.authoring import artifact_key, artifact_path, load_manifest

    required = ["specification"]
    if stage in ("plan", "tasks"):
        required.append("plan")
    if stage == "tasks":
        required.append("outline")
        manifest = load_manifest(artifact_path(repo_root, mission_slug, "outline").parent)
        if manifest is None:
            raise DesignError("DESIGN_PREREQUISITES_FAILED", "Task validation requires an outline")
        _validate_manifest_graph(manifest, artifact_path(repo_root, mission_slug, "specification").parent)
        required.extend(artifact_key("work_package", entry.id) for entry in manifest.work_packages)
    missing = sorted(set(required) - receipts.artifacts.keys())
    if missing:
        raise DesignError("DESIGN_PREREQUISITES_FAILED", "API-authored stage lacks accepted provenance", {"missing": missing})


def validate_stage(repo_root: Path, mission_slug: str, stage: str) -> dict[str, object]:
    """Read-only prerequisite proof, never an alternate lifecycle completion."""
    from specify_cli.design.context import resolved_interview_answers

    if stage not in ("specify", "plan", "tasks"):
        raise DesignError("DESIGN_REQUEST_INVALID", "Unknown design stage")
    resolved_interview_answers(repo_root, mission_slug, stage)
    decision_dir = placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.DECISION_LEDGER)
    if any(entry.status == DecisionStatus.OPEN for entry in load_index(decision_dir).entries):
        raise DesignError("DESIGN_PREREQUISITES_FAILED", "Open design decisions must be resolved before completion")
    require_committed_content(repo_root, mission_slug, "specification")
    if stage in ("plan", "tasks"):
        require_committed_content(repo_root, mission_slug, "plan")
    receipts = read_receipts(repo_root, mission_slug)
    if receipts is not None:
        _required_receipts(repo_root, mission_slug, stage, receipts)
        _check_receipt_lineage(repo_root, mission_slug, stage, receipts)
    return {"stage": stage, "prerequisites_satisfied": True, "validation_only": True}


class FinalizationScope:
    """Handle yielded by ``finalization_scope``; re-stamping needs ``confirm``."""

    def __init__(self) -> None:
        self.confirmed = False

    def confirm(self, payload: dict[str, object] | None) -> bool:
        """Accept only a native success payload; anything else leaves receipts untouched."""
        self.confirmed = payload is not None and payload.get("result") == "success" and not payload.get("error") and payload.get("success") is not False
        return self.confirmed


@contextmanager
def finalization_scope(repo_root: Path, mission_slug: str) -> Iterator[FinalizationScope]:
    """Hold cooperative lock across provenance checks AND native finalization.

    Receipts are re-stamped to native finalization's resulting bytes only after
    the caller confirmed a success payload; a failed or unconfirmed delegate
    never re-blesses whatever is on disk.
    """
    with authoring_lock(repo_root, mission_slug):
        receipts = read_receipts(repo_root, mission_slug)
        if receipts is not None:
            validate_stage(repo_root, mission_slug, "tasks")
        scope = FinalizationScope()
        yield scope
        if receipts is not None and scope.confirmed:
            # Native finalization owns generated prompt frontmatter. Accept its
            # resulting bytes under the same lock without allowing a new draft.
            from specify_cli.design.authoring import artifact_path

            for receipt in receipts.artifacts.values():
                if receipt.kind == "work_package":
                    receipt.sha256 = content_digest(artifact_path(repo_root, mission_slug, receipt.kind, receipt.artifact_id))
            save_receipts(repo_root, mission_slug, receipts)


@contextmanager
def native_finalization_scope(repo_root: Path, mission_slug: str) -> Iterator[FinalizationScope | None]:
    """Run native ``finalize-tasks`` of an API-authored Mission inside ``finalization_scope`` (#5879).

    Yields ``None`` (nothing enforced, nothing re-stamped) for a Mission without
    the API-authoring marker or whose tasks are already finalized. Otherwise the
    stale-content proof runs before any mutation, the lock is held across the
    finalize, and the caller's ``confirm`` on success re-stamps the work-package
    receipts to the bytes finalization wrote. The lock is reentrant, so the
    orchestrator-api ``tasks`` verb may nest its own scope around this one.
    """
    with _marker_gated_lock(repo_root, mission_slug) as enabled:
        if not enabled or _tasks_finalized(repo_root, mission_slug):
            yield None
            return
        with finalization_scope(repo_root, mission_slug) as scope:
            yield scope
