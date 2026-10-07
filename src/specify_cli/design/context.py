"""Read-only resolved design inputs and canonical interview decisions.

Content provenance is independent of runtime phase state. These helpers serve
both authoring guards and the external transport, without a transport import.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from charter.activation.action_doctrine_bundle import _resolve_action_bundle
from charter.activation.context_renderers.artifact_bodies import _jsonable_artifact_value
from charter.activation.mission_type_profiles import existing_mission_types, resolve_mission_type_context
from charter.activation.progressive_disclosure import build_disclosure_payload
from charter.bundle import CHARTER_YAML
from kernel.content_digest import sha256_digest
from mission_runtime import MissionArtifactKind, placement_seam
from specify_cli.decisions import service, store
from specify_cli.decisions.models import DecisionStatus, OriginFlow
from specify_cli.runtime.resolver import resolve_configured_template

__all__ = [
    "DesignContextError",
    "build_design_context",
    "planning_context_digest",
    "resolved_interview_answers",
    "record_interview_answers",
    "bounded_content",
]

ARTIFACT_BYTES = 262144
CONTEXT_BYTES = 1048576
ENTRY_LIMIT = 64
ANSWER_BYTES = 16384
ACTOR_BYTES = 1024
_STAGES = frozenset({"specify", "plan", "tasks"})


class DesignContextError(ValueError):
    """Typed refusal shared by authoring services and adapters."""

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def _stage(stage: str) -> str:
    if stage not in _STAGES:
        raise DesignContextError("DESIGN_CONTEXT_FAILED", "Undeclared design stage", {"stage": stage})
    return stage


def bounded_content(path: Path, maximum: int = ARTIFACT_BYTES) -> dict[str, Any]:
    """Read a host-selected UTF-8 resource within the published byte bound."""
    with path.open("rb") as handle:
        body = handle.read(maximum + 1)
    if len(body) > maximum:
        raise DesignContextError("DESIGN_CONTEXT_FAILED", "Host content exceeds the inline byte limit", {"maximum_bytes": maximum})
    return {"content": body.decode("utf-8"), "sha256": sha256_digest(body).removeprefix("sha256:"), "bytes": len(body)}


def _read_template(path: Path) -> str:
    return str(bounded_content(path)["content"])


def _questions(stage: str) -> list[tuple[str, str]]:
    from specify_cli.missions.plan.interview_questions import PLAN_WIDEN_QUESTIONS, SPECIFY_WIDEN_QUESTIONS

    _stage(stage)
    return list(SPECIFY_WIDEN_QUESTIONS if stage == "specify" else PLAN_WIDEN_QUESTIONS if stage == "plan" else [])


def _mission_home(repo_root: Path, mission_slug: str, kind: MissionArtifactKind) -> Path:
    return placement_seam(repo_root, mission_slug).read_dir(kind)


def _governance(repo_root: Path, mission_dir: Path | None, mission_type: str, stage: str) -> dict[str, object]:
    # Use the same resolved bundle and disclosure renderer as charter context,
    # without that CLI's refresh/mark-loaded effects during a read-only query.
    bundle = _resolve_action_bundle(repo_root, action=stage, effective_depth=0, org_root=None, mission_type=mission_type, feature_dir=mission_dir)
    authority = bundle.service
    payload = build_disclosure_payload(
        repos_by_kind={
            "directive": (authority.directives, bundle.directive_ids),
            "tactic": (authority.tactics, bundle.tactic_ids),
            "styleguide": (authority.styleguides, bundle.styleguide_ids),
            "toolguide": (authority.toolguides, bundle.toolguide_ids),
            "procedure": (authority.procedures, bundle.procedure_ids),
        },
        extra_delivered={"asset": bundle.asset_ids, "glossary_pack": bundle.glossary_pack_ids},
        merged=bundle.merged,
        roots=bundle.roots,
        bridge_urns=bundle.bridge_urns,
        include_all=True,
        body_of=_jsonable_artifact_value,
    )
    return dict(payload)


def _templates(repo_root: Path, bundle: Any) -> dict[str, dict[str, object]]:
    mapping = bundle.template_set
    if mapping is None:
        raise DesignContextError("DESIGN_CONTEXT_FAILED", "Activated mission has no template mapping")
    if len(mapping) > ENTRY_LIMIT:
        raise DesignContextError("DESIGN_CONTEXT_FAILED", "Template count exceeds the inline entry limit")
    templates: dict[str, dict[str, object]] = {}
    for kind in sorted(mapping):
        result = resolve_configured_template(kind, repo_root, bundle)
        content = _read_template(result.path)
        digest = sha256_digest(content.encode("utf-8")).removeprefix("sha256:")
        templates[kind] = {"name": result.path.name, "content": content, "sha256": digest, "digest": digest}
    return templates


def _stable(value: Any) -> Any:
    """Remove presentation/location/session fields from the semantic snapshot."""
    if isinstance(value, dict):
        return {key: _stable(item) for key, item in value.items() if key not in {"path", "source_path", "first_load", "references_count"}}
    if isinstance(value, (list, tuple)):
        return [_stable(item) for item in value]
    return value


def _semantic_context(repo_root: Path, mission_slug: str | None, stage: str, mission_type: str | None) -> dict[str, Any]:
    _stage(stage)
    mission_dir = _mission_home(repo_root, mission_slug, MissionArtifactKind.PRIMARY_METADATA) if mission_slug else None
    bundle = resolve_mission_type_context(repo_root, mission_type=None if mission_dir else mission_type, feature_dir=mission_dir)
    if mission_dir is not None and mission_type is not None and mission_type != bundle.mission_type:
        raise DesignContextError("DESIGN_CONTEXT_FAILED", "The mission type is immutable; --mission-type selects only pre-creation context")
    selected = bundle.mission_type
    if selected is None:
        raise DesignContextError("DESIGN_CONTEXT_FAILED", "Choose an activated mission type before discovery")
    charter = repo_root / CHARTER_YAML
    charter_digest = sha256_digest(charter.read_bytes()).removeprefix("sha256:") if charter.exists() else None
    questions = [{"question_id": key, "id": key, "question": question} for key, question in _questions(stage)]
    return {
        "mission_type": selected,
        "stage": stage,
        "mission_types": existing_mission_types(repo_root),
        "action_sequence": bundle.action_sequence,
        "templates": _templates(repo_root, bundle),
        "questions": questions,
        "governance": _governance(repo_root, mission_dir, selected, stage),
        "required_artifacts": bundle.expected_artifacts,
        "charter_sha256": charter_digest,
    }


def build_design_context(repo_root: Path, mission_slug: str | None, stage: str, mission_type: str | None = None) -> dict[str, Any]:
    """Discover canonical authoring inputs; never initialize a run or interview."""
    try:
        context = _semantic_context(repo_root, mission_slug, stage, mission_type)
        semantic = json.dumps(_stable(context), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        if len(semantic) > CONTEXT_BYTES:
            raise DesignContextError("DESIGN_CONTEXT_FAILED", "Resolved context exceeds the inline batch limit", {"maximum_bytes": CONTEXT_BYTES})
        context["context_sha256"] = sha256_digest(semantic).removeprefix("sha256:")
        context["mission_slug"] = mission_slug
        context["limits"] = {
            "artifact_bytes": ARTIFACT_BYTES,
            "batch_bytes": CONTEXT_BYTES,
            "entries": ENTRY_LIMIT,
            "answer_bytes": ANSWER_BYTES,
            "actor_bytes": ACTOR_BYTES,
        }
        context["interview"] = (
            interview_status(repo_root, mission_slug, stage)
            if mission_slug
            else {"questions": context["questions"], "complete": False, "incomplete": [q["id"] for q in context["questions"]], "decision_ids": {}}
        )
        _check_response_bound(context)
        return context
    except DesignContextError:
        raise
    except (OSError, ValueError, RuntimeError) as exc:
        raise DesignContextError("DESIGN_CONTEXT_FAILED", str(exc)) from exc


def _check_response_bound(payload: dict[str, Any]) -> None:
    if len(json.dumps(payload).encode("utf-8")) > CONTEXT_BYTES:
        raise DesignContextError("DESIGN_CONTEXT_FAILED", "Resolved response including interviews exceeds the inline batch limit", {"maximum_bytes": CONTEXT_BYTES})


def planning_context_digest(repo_root: Path, mission_slug: str, action: str) -> str:
    """Hash fresh resolved semantic inputs, excluding answers and presentation."""
    return str(build_design_context(repo_root, mission_slug, action)["context_sha256"])


def _stage_slots(stage: str) -> list[tuple[str, str, str]]:
    _stage(stage)
    stages = ("specify", "plan") if stage == "tasks" else (stage,)
    return [(flow, key, question) for flow in stages for key, question in _questions(flow)]


def interview_status(repo_root: Path, mission_slug: str, stage: str) -> dict[str, Any]:
    """Read required logical slots from the canonical decision ledger."""
    ledger = _mission_home(repo_root, mission_slug, MissionArtifactKind.DECISION_LEDGER)
    try:
        index = store.load_index(ledger)
    except (store.DecisionIndexReadError, OSError) as exc:
        raise DesignContextError("DESIGN_INTERVIEW_FAILED", str(exc)) from exc
    incomplete: list[str] = []
    answers: dict[str, str] = {}
    decision_ids: dict[str, str] = {}
    questions: list[dict[str, str]] = []
    for flow, key, question in _stage_slots(stage):
        answer_key = f"{flow}.{key}" if stage == "tasks" else key
        entry = store.find_by_logical_key(index, OriginFlow(flow), f"{flow}.{key}", None, key)
        questions.append({"question_id": answer_key, "id": answer_key, "question": question})
        if entry is not None:
            decision_ids[answer_key] = entry.decision_id
        if entry is None or entry.status != DecisionStatus.RESOLVED or not (entry.final_answer or "").strip():
            incomplete.append(answer_key)
        else:
            answers[answer_key] = str(entry.final_answer)
    return {"questions": questions, "complete": not incomplete, "incomplete": incomplete, "answers": answers, "decision_ids": decision_ids}


def resolved_interview_answers(repo_root: Path, mission_slug: str, stage: str) -> dict[str, str]:
    """Refuse absent, pending, deferred, canceled or empty required answers."""
    status = interview_status(repo_root, mission_slug, stage)
    if not status["complete"]:
        raise DesignContextError("DESIGN_INTERVIEW_INCOMPLETE", "Required interview answers are not resolved", {"incomplete": status["incomplete"], "stage": stage})
    return dict(status["answers"])


def _validate_answers(stage: str, answers: object, actor: str) -> dict[str, str]:
    keys = {key for key, _ in _questions(stage)}
    if not actor.strip() or not isinstance(answers, dict) or not answers:
        raise DesignContextError("DESIGN_INTERVIEW_INVALID", "Actor and a nonempty answer mapping are required")
    if set(answers) - keys or any(not isinstance(value, str) or not value.strip() for value in answers.values()):
        raise DesignContextError("DESIGN_INTERVIEW_INVALID", "Answers must name canonical questions and contain nonempty strings")
    if len(actor.encode("utf-8")) > ACTOR_BYTES or any(len(value.encode("utf-8")) > ANSWER_BYTES for value in answers.values()):
        raise DesignContextError("DESIGN_INTERVIEW_INVALID", "Actor or answer exceeds its published byte limit")
    if len(json.dumps(answers, ensure_ascii=False).encode("utf-8")) > ARTIFACT_BYTES:
        raise DesignContextError("DESIGN_INTERVIEW_INVALID", "Interview answers exceed the inline byte limit")
    return dict(answers)


def _record_one(repo_root: Path, mission_slug: str, stage: str, key: str, question: str, answer: str, actor: str) -> str:
    ledger = _mission_home(repo_root, mission_slug, MissionArtifactKind.DECISION_LEDGER)
    existing = store.find_by_logical_key(store.load_index(ledger), OriginFlow(stage), f"{stage}.{key}", None, key)
    if existing is not None:
        decision_id = existing.decision_id
    else:
        decision_id = service.open_decision(
            repo_root, mission_slug, origin_flow=OriginFlow(stage), input_key=key, step_id=f"{stage}.{key}", question=question, options=(), actor=actor
        ).decision_id
    # Canonical terminal service owns exact-retry and conflict/deferred behavior.
    service.resolve_decision(repo_root, mission_slug, decision_id, final_answer=answer, actor=actor)
    return str(decision_id)


def record_interview_answers(repo_root: Path, mission_slug: str, stage: str, answers: object, actor: str) -> dict[str, Any]:
    """Validate the complete request, then resolve canonical stable question slots."""
    validated = _validate_answers(stage, answers, actor)
    ids: dict[str, str] = {}
    try:
        for key, question in _questions(stage):
            if key in validated:
                ids[key] = _record_one(repo_root, mission_slug, stage, key, question, validated[key], actor)
        payload = {"mission_slug": mission_slug, "stage": stage, "decision_ids": ids, "interview": interview_status(repo_root, mission_slug, stage)}
        _check_response_bound(payload)
        return payload
    except (service.DecisionError, OSError, ValueError, RuntimeError) as exc:
        code = exc.code.value if isinstance(exc, service.DecisionError) else type(exc).__name__
        raise DesignContextError(
            "DESIGN_INTERVIEW_FAILED", str(exc), {"reason": code, "mission_slug": mission_slug, "decision_ids": ids, "effect_state": "reconciliation_required"}
        ) from exc
