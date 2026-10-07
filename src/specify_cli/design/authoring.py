"""Host-owned, revision-conditioned planning artifact materialization.

The service owns content handoff, not mission advancement. Native status,
placement, template, manifest and commit services remain authoritative.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from mission_runtime import MissionArtifactKind, placement_seam
from kernel.content_digest import sha256_digest
from pydantic import ValidationError

from specify_cli.coordination.commit_outcome import commit_outcome_payload
from specify_cli.coordination.commit_router import commit_for_mission
from specify_cli.core.atomic import atomic_write
from specify_cli.core.wps_manifest import WpsManifest, WpsManifestReadError, load_wps_manifest
from specify_cli.design.errors import DesignError
from .models import ABSENT, MAX_ACTOR_BYTES, MAX_ARTIFACT_BYTES, MAX_BATCH_BYTES, MAX_REQUEST_BYTES, ArtifactInput, Receipt, ReceiptSet, Submission
from specify_cli.design.receipts import authoring_lock, content_digest, enable_authoring, read_receipts, save_receipts
from specify_cli.git.protection_policy import ProtectionPolicy
from specify_cli.mission import get_mission_type
from specify_cli.runtime.resolver import ArtifactNameConfigurationError, resolve_configured_artifact_name

_KINDS = {
    "specification": MissionArtifactKind.SPEC,
    "plan": MissionArtifactKind.FINALIZED_EXECUTION_PLAN,
    "outline": MissionArtifactKind.TASKS_INDEX,
    "work_package": MissionArtifactKind.WORK_PACKAGE_TASK,
    "research": MissionArtifactKind.RESEARCH,
    "data_model": MissionArtifactKind.DATA_MODEL,
    "quickstart": MissionArtifactKind.CHECKLIST,
    "contract": MissionArtifactKind.CONTRACT,
}
_MANIFEST_KEYS = {
    "specification": "input.spec.main",
    "plan": "output.plan.main",
    "research": "evidence.research",
    "data_model": "evidence.data-model",
    "quickstart": "evidence.quickstart",
}
_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$", re.ASCII)


@dataclass(frozen=True)
class PreparedArtifact:
    """One validated host-selected target and its accepted request."""

    request: ArtifactInput
    path: Path
    sha256: str


def artifact_key(kind: str, artifact_id: str | None) -> str:
    """Stable provenance key independent of topology-selected physical paths."""
    return kind if artifact_id is None else f"{kind}:{artifact_id}"


def artifact_action(kind: str) -> str:
    """Canonical governance/interview action for a closed authored kind."""
    if kind in ("specification", "research"):
        return "specify"
    return "tasks" if kind in ("outline", "work_package") else "plan"


def _safe_filename(value: str) -> str:
    if not _SAFE_NAME.fullmatch(value) or ".." in value:
        raise DesignError("DESIGN_PATH_REFUSED", "Artifact identifiers must be a single safe basename")
    return value


def manifest_prompt_name(manifest: WpsManifest, wp_id: str) -> str:
    """Choose a WP prompt from its canonical manifest, never from request paths."""
    entries = [entry for entry in manifest.work_packages if entry.id == wp_id]
    if len(entries) != 1:
        raise DesignError("DESIGN_PREREQUISITES_FAILED", "The package is not uniquely declared in wps.yaml")
    name = entries[0].prompt_file or f"tasks/{wp_id}.md"
    parts = Path(name).parts
    if len(parts) != 2 or parts[0] != "tasks" or not parts[1].startswith(wp_id) or not parts[1].endswith(".md"):
        raise DesignError("DESIGN_PATH_REFUSED", "Manifest prompt_file must name its own tasks/WPnn*.md file")
    _safe_filename(parts[1])
    return name


def load_manifest(mission_dir: Path) -> WpsManifest | None:
    """Normalize canonical outline read/schema failures at the shared boundary."""
    try:
        return load_wps_manifest(mission_dir)
    except (WpsManifestReadError, ValidationError) as exc:
        raise DesignError("DESIGN_PREREQUISITES_FAILED", "The existing outline is invalid") from exc


def _filename(mission_dir: Path, kind: str, artifact_id: str | None, manifest: WpsManifest | None) -> str:
    if kind == "outline":
        if artifact_id is not None:
            raise DesignError("DESIGN_REQUEST_INVALID", "The outline has no selectable identifier")
        return "wps.yaml"  # canonical structured source owned by core.wps_manifest
    if kind == "work_package":
        if artifact_id is None or not re.fullmatch(r"WP[0-9]{2}", artifact_id, re.ASCII) or manifest is None:
            raise DesignError("DESIGN_PREREQUISITES_FAILED", "WP submission requires a declared WPnn and outline")
        return manifest_prompt_name(manifest, artifact_id)
    if kind == "contract":
        if artifact_id is None:
            raise DesignError("DESIGN_REQUEST_INVALID", "Contracts require an artifact_id basename")
        return f"contracts/{_safe_filename(artifact_id)}"
    if artifact_id is not None:
        raise DesignError("DESIGN_REQUEST_INVALID", "This artifact kind has no selectable identifier")
    try:
        configured = resolve_configured_artifact_name(_MANIFEST_KEYS[kind], get_mission_type(mission_dir))
        if not isinstance(configured, str):
            raise DesignError("DESIGN_ARTIFACT_UNSUPPORTED", "The configured artifact name is invalid")
        return configured
    except ArtifactNameConfigurationError as exc:
        raise DesignError("DESIGN_ARTIFACT_UNSUPPORTED", "The mission type does not declare this artifact") from exc


def artifact_path(repo_root: Path, mission_slug: str, kind: str, artifact_id: str | None = None, *, manifest: WpsManifest | None = None) -> Path:
    """Resolve a registered artifact and refuse symlink/traversal escape."""
    if kind not in _KINDS:
        raise DesignError("DESIGN_ARTIFACT_UNSUPPORTED", "The artifact kind is not an authoring capability")
    seam = placement_seam(repo_root, mission_slug)
    mission_dir = seam.read_dir(_KINDS[kind])
    if kind == "work_package" and manifest is None:
        manifest = load_manifest(seam.read_dir(MissionArtifactKind.TASKS_INDEX))
    relative = _filename(mission_dir, kind, artifact_id, manifest)
    path = mission_dir / relative
    if Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise DesignError("DESIGN_PATH_REFUSED", "The configured artifact location is unsafe")
    if not path.resolve().is_relative_to(mission_dir.resolve()):
        raise DesignError("DESIGN_PATH_REFUSED", "Artifact location escapes the mission")
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != mission_dir and parent.is_relative_to(mission_dir)):
        raise DesignError("DESIGN_PATH_REFUSED", "Authoring does not follow artifact symlinks")
    return path


def read_artifact(repo_root: Path, mission_slug: str, kind: str, artifact_id: str | None = None) -> dict[str, object]:
    """Return bounded authoring content, including absent first-submission state."""
    with authoring_lock(repo_root, mission_slug):
        path = artifact_path(repo_root, mission_slug, kind, artifact_id)
        content = None
        digest = ABSENT
        if path.exists():
            with path.open("rb") as handle:
                body = handle.read(MAX_ARTIFACT_BYTES + 1)
            if len(body) > MAX_ARTIFACT_BYTES:
                raise DesignError("DESIGN_BOUNDS_EXCEEDED", "Artifact content exceeds the inline read bound")
            content = body.decode("utf-8")
            digest = sha256_digest(body).removeprefix("sha256:")
        return {"kind": kind, "artifact_id": artifact_id, "sha256": digest, "content": content}


def parse_submission(raw: str) -> Submission:
    """Reject excess bytes, unknown fields and invalid revision tokens up front."""
    if len(raw.encode("utf-8")) > MAX_REQUEST_BYTES:
        raise DesignError("DESIGN_BOUNDS_EXCEEDED", "Request exceeds the JSON transport bound")
    try:
        request = Submission.model_validate_json(raw)
    except ValidationError as exc:
        raise DesignError("DESIGN_REQUEST_INVALID", "Invalid artifact submission schema") from exc
    if set(request.parents) - {"specification", "plan", "outline"}:
        raise DesignError("DESIGN_REQUEST_INVALID", "Unknown parent revision key")
    sizes = [len(item.content.encode("utf-8")) for item in request.artifacts]
    if any(size > MAX_ARTIFACT_BYTES for size in sizes) or sum(sizes) > MAX_BATCH_BYTES:
        raise DesignError("DESIGN_BOUNDS_EXCEEDED", "Artifact or batch exceeds the published byte bound")
    return request


def _prepare(repo_root: Path, mission_slug: str, request: Submission) -> list[PreparedArtifact]:
    from specify_cli.design.validation import validate_content, validated_manifest

    outline = next((item.content for item in request.artifacts if item.kind == "outline"), None)
    mission_dir = placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.SPEC)
    manifest = validated_manifest(outline, mission_dir) if outline is not None else load_manifest(mission_dir)
    prepared: list[PreparedArtifact] = []
    seen: set[Path] = set()
    for item in request.artifacts:
        path = artifact_path(repo_root, mission_slug, item.kind, item.artifact_id, manifest=manifest)
        if path in seen:
            raise DesignError("DESIGN_REQUEST_INVALID", "A batch cannot address a target twice")
        seen.add(path)
        if content_digest(path) != item.expected_sha256:
            raise DesignError("DESIGN_REVISION_CONFLICT", "Artifact revision changed", {"kind": item.kind, "current_sha256": content_digest(path)})
        validate_content(repo_root, mission_slug, item, manifest)
        prepared.append(PreparedArtifact(item, path, sha256_digest(item.content.encode("utf-8")).removeprefix("sha256:")))
    return prepared


def _check_context_and_parents(repo_root: Path, mission_slug: str, request: Submission, prepared: list[PreparedArtifact]) -> str:
    from specify_cli.design.context import planning_context_digest, resolved_interview_answers
    from specify_cli.design.validation import require_committed_content

    actions = {artifact_action(item.request.kind) for item in prepared}
    if len(actions) != 1:
        raise DesignError("DESIGN_REQUEST_INVALID", "A submission batch belongs to one design stage")
    action = actions.pop()
    seam = placement_seam(repo_root, mission_slug)
    if len({seam.read_dir(_KINDS[item.request.kind]) for item in prepared}) != 1:
        raise DesignError("DESIGN_REQUEST_INVALID", "A submission batch cannot span artifact placements")
    if planning_context_digest(repo_root, mission_slug, action) != request.context_sha256:
        raise DesignError("DESIGN_CONTEXT_STALE", "Resolved template or governance context changed")
    resolved_interview_answers(repo_root, mission_slug, action)
    required: set[str] = set()
    if action != "specify":
        required.add("specification")
    if action == "tasks":
        required.add("plan")
    if any(item.request.kind == "work_package" for item in prepared):
        required.add("outline")
    prospective = {item.request.kind: item.sha256 for item in prepared if item.request.kind == "outline"}
    for parent in required | request.parents.keys():
        current = prospective.get(parent) or content_digest(artifact_path(repo_root, mission_slug, parent))
        if current == ABSENT or request.parents.get(parent) != current:
            raise DesignError("DESIGN_PARENT_STALE", "Parent revision is missing or changed", {"parent": parent, "current_sha256": current})
        if parent != "outline" or parent not in prospective:
            require_committed_content(repo_root, mission_slug, parent)
    return action


def _record_batch(receipts: ReceiptSet, prepared: list[PreparedArtifact], request: Submission, action: str, actor: str) -> None:
    for item in prepared:
        receipts.artifacts[artifact_key(item.request.kind, item.request.artifact_id)] = Receipt(
            kind=item.request.kind,
            artifact_id=item.request.artifact_id,
            sha256=item.sha256,
            parents={parent: digest for parent, digest in request.parents.items() if parent != item.request.kind},
            context_sha256=request.context_sha256,
            context_action=action,
            actor=actor,
        )


def submit_artifacts(repo_root: Path, mission_slug: str, raw: str, actor: str) -> dict[str, object]:
    """Validate, materialize and commit one batch; never advance mission state."""
    from specify_cli.design.validation import require_unfinalized

    request = parse_submission(raw)
    if not actor.strip() or len(actor.encode("utf-8")) > MAX_ACTOR_BYTES:
        raise DesignError("DESIGN_REQUEST_INVALID", "An attributable bounded actor is required")
    with authoring_lock(repo_root, mission_slug):
        require_unfinalized(repo_root, mission_slug)
        receipts = read_receipts(repo_root, mission_slug) or ReceiptSet()
        prepared = _prepare(repo_root, mission_slug, request)
        action = _check_context_and_parents(repo_root, mission_slug, request, prepared)
        policy = ProtectionPolicy.resolve(repo_root)
        # Native/manual writers do not share this cooperative API lock. Check
        # revisions again after context resolution and immediately before effects.
        prepared = _prepare(repo_root, mission_slug, request)
        _check_context_and_parents(repo_root, mission_slug, request, prepared)
        enable_authoring(repo_root, mission_slug, receipts)
        try:
            for item in prepared:
                atomic_write(item.path, item.request.content, mkdir=True)
        except OSError as exc:
            raise DesignError("DESIGN_IO_FAILED", "Artifact materialization requires reconciliation", {"effect_state": "reconciliation_required"}) from exc
        result = commit_for_mission(
            repo_root=repo_root,
            mission_slug=mission_slug,
            files=tuple(item.path for item in prepared),
            message=f"Record governed {action} content for {mission_slug} by {actor}",
            policy=policy,
            kind=_KINDS[prepared[0].request.kind],
        )
        if result.status not in ("committed", "unchanged"):
            raise DesignError(
                "DESIGN_COMMIT_FAILED",
                "Authored content materialized but the host commit did not complete",
                {"effect_state": "reconciliation_required", "commit_status": result.status, **commit_outcome_payload(result)},
            )
        _record_batch(receipts, prepared, request, action, actor)
        save_receipts(repo_root, mission_slug, receipts)
        return {
            "artifacts": [{"kind": item.request.kind, "artifact_id": item.request.artifact_id, "sha256": item.sha256} for item in prepared],
            "commit_status": result.status,
            "commit_hash": result.commit_hash,
            "provenance": "host_local_nonportable",
            **commit_outcome_payload(result),
        }
