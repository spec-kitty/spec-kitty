"""Schema-validating reader for retrospective.yaml.

Raises typed exceptions so callers can distinguish missing-file,
corrupt-YAML, and schema-invalid cases without catching broad exceptions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import ValidationError
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from charter.activation.api import read_mission_type
from specify_cli.retrospective.schema import (
    GenActor,
    GenEvidenceRef,
    GenFinding,
    GenProposal,
    GenProvenance,
    GenRetrospectiveRecord,
    RecordValidationError,
    RetrospectiveRecord,
    validate_record,
)


class YAMLParseError(Exception):
    """The file exists but contains invalid YAML syntax."""


class SchemaError(Exception):
    """The file contains valid YAML but fails schema validation."""


_GEN_TOP_LEVEL_KEYS = frozenset({
    "schema_version",
    "mission_id",
    "mission_slug",
    "mission_number",
    "friendly_name",
    "mission_type",
    "target_branch",
    "created_at",
    "created_by",
    "provenance",
    "policy_source",
    "findings_status",
    "helped",
    "not_helpful",
    "gaps",
    "proposals",
    "evidence_refs",
    "generator_version",
    "provenance_history",
})
_GEN_REQUIRED_KEYS = frozenset({
    "schema_version",
    "mission_id",
    "mission_slug",
    "mission_number",
    "friendly_name",
    "mission_type",
    "target_branch",
    "created_at",
    "created_by",
    "provenance",
    "policy_source",
    "findings_status",
    "helped",
    "not_helpful",
    "gaps",
    "proposals",
    "evidence_refs",
    "generator_version",
})
_ACTOR_KEYS = frozenset({"kind", "id", "display"})
_PROVENANCE_KEYS = frozenset({"kind", "invoked_at", "policy_resolved_from", "command"})
_EVIDENCE_KEYS = frozenset({"id", "kind", "path", "range", "url"})
_FINDING_KEYS = frozenset({"id", "category", "summary", "evidence_refs", "details"})
_PROPOSAL_KEYS = frozenset({
    "id",
    "category",
    "risk_class",
    "summary",
    "evidence_refs",
    "suggested_action",
    "auto_applicable",
    "details",
})
_ACTOR_KINDS = frozenset({"human", "agent", "runtime"})
_PROVENANCE_KINDS = frozenset({
    "runtime_post_completion",
    "runtime_strict_gate",
    "runtime_abandoned",
    "explicit_create",
    "backfill",
    "synthesize_fabricate",
})
FINDING_CATEGORIES = frozenset({
    "process",
    "tooling",
    "spec_quality",
    "review_loop",
    "design",
    "implementation",
    "doc",
    "other",
})
PROPOSAL_CATEGORIES = frozenset({"glossary", "drg", "doctrine", "tooling", "process", "other"})
_EVIDENCE_KINDS = frozenset({"file", "event_range", "external"})
_FINDINGS_STATUSES = frozenset({"has_findings", "ran_no_findings"})

YamlMapping = dict[str, Any]


def _load_yaml_mapping(path: Path) -> YamlMapping:
    raw_text = path.read_text(encoding="utf-8")
    yaml = YAML(typ="safe")
    try:
        data = yaml.load(raw_text)
    except YAMLError as exc:
        raise YAMLParseError(f"Failed to parse YAML from {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise SchemaError(f"Expected a YAML mapping at the top level of {path}, got {type(data).__name__}")
    return data


def _coerce_legacy_schema_versions(data: YamlMapping) -> YamlMapping:
    """Accept legacy YAML scalar versions while keeping the model schema strict."""
    normalized = dict(data)

    schema_version = normalized.get("schema_version")
    if type(schema_version) is int:
        normalized["schema_version"] = str(schema_version)

    provenance = normalized.get("provenance")
    if isinstance(provenance, dict):
        provenance_schema_version = provenance.get("schema_version")
        if type(provenance_schema_version) is int:
            normalized["provenance"] = {
                **provenance,
                "schema_version": str(provenance_schema_version),
            }

    return normalized


def _validate_keys(raw: YamlMapping, allowed: frozenset[str], *, label: str) -> None:
    extra = sorted(set(raw) - allowed)
    if extra:
        raise ValueError(f"{label} has unsupported field(s): {', '.join(extra)}")


def _validate_mapping(raw: object, *, label: str) -> YamlMapping:
    if not isinstance(raw, dict):
        raise ValueError(f"{label} must be a mapping")
    return raw


def _validate_string_list(raw: object, *, label: str) -> None:
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        raise ValueError(f"{label} must be a list of strings")


def _validate_gen_actor(raw: object, *, label: str) -> None:
    actor = _validate_mapping(raw, label=label)
    _validate_keys(actor, _ACTOR_KEYS, label=label)
    if actor.get("kind") not in _ACTOR_KINDS:
        raise ValueError(f"{label}.kind is invalid")
    if not isinstance(actor.get("id"), str) or not actor.get("id"):
        raise ValueError(f"{label}.id must be a non-empty string")


def _validate_gen_provenance(raw: object, *, label: str) -> None:
    provenance = _validate_mapping(raw, label=label)
    _validate_keys(provenance, _PROVENANCE_KEYS, label=label)
    if provenance.get("kind") not in _PROVENANCE_KINDS:
        raise ValueError(f"{label}.kind is invalid")
    if not isinstance(provenance.get("invoked_at"), str):
        raise ValueError(f"{label}.invoked_at must be a string")
    if not isinstance(provenance.get("policy_resolved_from", {}), dict):
        raise ValueError(f"{label}.policy_resolved_from must be a mapping")


def _validate_gen_evidence_ref(raw: object, *, label: str) -> None:
    evidence_ref = _validate_mapping(raw, label=label)
    _validate_keys(evidence_ref, _EVIDENCE_KEYS, label=label)
    if evidence_ref.get("kind") not in _EVIDENCE_KINDS:
        raise ValueError(f"{label}.kind is invalid")


def _validate_gen_finding(raw: object, *, label: str) -> None:
    finding = _validate_mapping(raw, label=label)
    _validate_keys(finding, _FINDING_KEYS, label=label)
    if finding.get("category") not in FINDING_CATEGORIES:
        raise ValueError(f"{label}.category is invalid")
    _validate_string_list(finding.get("evidence_refs", []), label=f"{label}.evidence_refs")


def _validate_gen_proposal(raw: object, *, label: str) -> None:
    proposal = _validate_mapping(raw, label=label)
    _validate_keys(proposal, _PROPOSAL_KEYS, label=label)
    if proposal.get("category") not in PROPOSAL_CATEGORIES:
        raise ValueError(f"{label}.category is invalid")
    if proposal.get("risk_class") not in {"low", "structural"}:
        raise ValueError(f"{label}.risk_class is invalid")
    if not isinstance(proposal.get("auto_applicable"), bool):
        raise ValueError(f"{label}.auto_applicable must be boolean")
    _validate_string_list(proposal.get("evidence_refs", []), label=f"{label}.evidence_refs")


def _validate_gen_header(data: YamlMapping) -> None:
    _validate_keys(data, _GEN_TOP_LEVEL_KEYS, label="record")
    missing = sorted(_GEN_REQUIRED_KEYS - set(data))
    if missing:
        raise ValueError(f"Missing required generator record field(s): {', '.join(missing)}")
    if data.get("schema_version") != 1:
        raise ValueError("schema_version must be 1")
    if data.get("findings_status") not in _FINDINGS_STATUSES:
        raise ValueError("findings_status must be has_findings or ran_no_findings")


def _validate_gen_mapping(data: YamlMapping) -> None:
    _validate_gen_header(data)

    _validate_gen_actor(data.get("created_by"), label="created_by")
    _validate_gen_provenance(data.get("provenance"), label="provenance")
    if not isinstance(data.get("policy_source", {}), dict):
        raise ValueError("policy_source must be a mapping")
    for collection in ("helped", "not_helpful", "gaps", "proposals", "evidence_refs", "provenance_history"):
        if not isinstance(data.get(collection, []), list):
            raise ValueError(f"{collection} must be a list")
    for name in ("helped", "not_helpful", "gaps"):
        for idx, item in enumerate(data.get(name, [])):
            _validate_gen_finding(item, label=f"{name}[{idx}]")
    for idx, item in enumerate(data.get("proposals", [])):
        _validate_gen_proposal(item, label=f"proposals[{idx}]")
    for idx, item in enumerate(data.get("evidence_refs", [])):
        _validate_gen_evidence_ref(item, label=f"evidence_refs[{idx}]")
    for idx, item in enumerate(data.get("provenance_history", [])):
        _validate_gen_provenance(item, label=f"provenance_history[{idx}]")


def _gen_record_from_mapping(data: YamlMapping) -> GenRetrospectiveRecord:
    # FR-008 / #2139 triage note (OUT): the `target_branch=data.get("target_branch", "")`
    # below is a dataclass-hydration default for a PERSISTED retrospective
    # RECORD field, not a meta.json reader -- it mirrors GenRetrospectiveRecord's
    # own schema-wide "" default (schema.py) applied identically to every other
    # legacy-optional string field on this same dataclass (mission_id,
    # mission_slug, friendly_name, mission_type, created_at, ...). No
    # feature_dir/repo_root is available at this deserialization boundary, and
    # resolving it against LIVE meta.json here would silently substitute a
    # historical record's field with the mission's CURRENT branch. Different
    # contract by design; not routed through read_target_branch_from_meta.
    def _actor(raw: object) -> GenActor:
        if not isinstance(raw, dict):
            raw = {}
        return GenActor(
            kind=raw.get("kind", "runtime"),
            id=raw.get("id", "unknown"),
            display=raw.get("display"),
        )

    def _provenance(raw: object) -> GenProvenance:
        if not isinstance(raw, dict):
            raw = {}
        return GenProvenance(
            kind=raw.get("kind", "runtime_post_completion"),
            invoked_at=raw.get("invoked_at", ""),
            policy_resolved_from=dict(raw.get("policy_resolved_from", {})),
            command=raw.get("command"),
        )

    def _evidence_ref(raw: YamlMapping) -> GenEvidenceRef:
        return GenEvidenceRef(
            id=raw["id"],
            kind=raw["kind"],
            path=raw.get("path"),
            range=raw.get("range"),
            url=raw.get("url"),
        )

    def _finding(raw: YamlMapping) -> GenFinding:
        return GenFinding(
            id=raw["id"],
            category=raw["category"],
            summary=raw["summary"],
            evidence_refs=list(raw.get("evidence_refs", [])),
            details=raw.get("details"),
        )

    def _proposal(raw: YamlMapping) -> GenProposal:
        return GenProposal(
            id=raw["id"],
            category=raw["category"],
            risk_class=raw["risk_class"],
            summary=raw["summary"],
            evidence_refs=list(raw.get("evidence_refs", [])),
            suggested_action=raw["suggested_action"],
            auto_applicable=raw["auto_applicable"],
            details=raw.get("details"),
        )

    return GenRetrospectiveRecord(
        schema_version=data.get("schema_version", 1),
        mission_id=data.get("mission_id", ""),
        mission_slug=data.get("mission_slug", ""),
        mission_number=data.get("mission_number"),
        friendly_name=data.get("friendly_name", ""),
        mission_type=read_mission_type(data) or "",  # rc3 M5 (FR-001): shared reader parity
        target_branch=data.get("target_branch", ""),
        created_at=data.get("created_at", ""),
        created_by=_actor(data.get("created_by")),
        provenance=_provenance(data.get("provenance")),
        policy_source=dict(data.get("policy_source", {})),
        findings_status=data.get("findings_status", "ran_no_findings"),
        helped=[_finding(f) for f in data.get("helped", [])],
        not_helpful=[_finding(f) for f in data.get("not_helpful", [])],
        gaps=[_finding(f) for f in data.get("gaps", [])],
        proposals=[_proposal(p) for p in data.get("proposals", [])],
        evidence_refs=[_evidence_ref(e) for e in data.get("evidence_refs", [])],
        generator_version=data.get("generator_version", ""),
        provenance_history=[_provenance(p) for p in data.get("provenance_history", [])],
    )


def read_gen_record(path: Path) -> GenRetrospectiveRecord:
    """Load the generator-shape retrospective record written by ``retrospect create``."""
    data = _load_yaml_mapping(path)
    try:
        _validate_gen_mapping(data)
        record = _gen_record_from_mapping(data)
        validate_record(record)
    except (KeyError, TypeError, ValueError, RecordValidationError) as exc:
        raise SchemaError(
            f"Generator schema validation failed for {path}:\n{exc}"
        ) from exc
    return record


def read_record(path: Path, *, verify_evidence: bool = False) -> RetrospectiveRecord:
    """Load a retrospective record from disk, schema-validated.

    Args:
        path: Absolute path to the retrospective.yaml file.
        verify_evidence: When True, perform a soft check that evidence event ids
            referenced by findings/proposals exist in the mission event log.
            # TODO: WP03 wires the actual event log lookup; for now this is a no-op.

    Returns:
        A fully-validated :class:`RetrospectiveRecord`.

    Raises:
        FileNotFoundError: The file does not exist.
        YAMLParseError: The file exists but cannot be parsed as YAML.
        SchemaError: The file parses as YAML but fails schema validation,
            or the record has status='pending' (not persistable).
    """
    data = _load_yaml_mapping(path)

    # Schema validation via Pydantic.
    try:
        record = RetrospectiveRecord.model_validate(_coerce_legacy_schema_versions(data))
    except ValidationError as exc:
        raise SchemaError(
            f"Schema validation failed for {path}:\n{exc}"
        ) from exc

    # status='pending' is explicitly refused at the read boundary too.
    # (The model validator already raises for pending, but guard explicitly
    # in case the validator is bypassed via model_construct in future.)
    if record.status == "pending":
        raise SchemaError(
            f"Refused to return a record with status='pending' from {path}. "
            "Pending records must not be persisted."
        )

    # Evidence verification (stub; WP03 wires the actual event log lookup).
    if verify_evidence:
        # TODO: WP03 wires the actual event log lookup.
        pass

    return record
