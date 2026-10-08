"""Interview answer model for charter generation."""

from __future__ import annotations

import importlib.resources
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from ruamel.yaml import YAML

from charter.activation._io import load_charter_file
from charter.activation.catalog import OfferingCatalog, load_offering_catalog
from charter.activation.resolver import DEFAULT_TOOL_REGISTRY

__all__ = [
    "CharterInterview",
    "InterviewAnswersRegressionError",
    "LocalSupportDeclaration",
    "MINIMAL_QUESTION_ORDER",
    "QUESTION_ORDER",
    "QUESTION_PROMPTS",
    "apply_answer_overrides",
    "apply_org_charter_pre_fill_to_answers",
    "default_interview",
    "packaged_default_answer",
    "read_interview_answers",
    "validate_local_support_declarations",
    "write_interview_answers",
]


# Glob characters that indicate a path pattern rather than an explicit file.
_GLOB_CHARS: tuple[str, ...] = ("*", "?", "[", "]")


@dataclass(frozen=True)
class LocalSupportDeclaration:
    """One project-local doctrine support file declared in interview answers."""

    path: str
    action: str | None = None
    target_kind: str | None = None
    target_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        d: dict[str, object] = {"path": self.path}
        if self.action is not None:
            d["action"] = self.action
        if self.target_kind is not None:
            d["target_kind"] = self.target_kind
        if self.target_id is not None:
            d["target_id"] = self.target_id
        return d

    @classmethod
    def from_dict(cls, data: object) -> LocalSupportDeclaration | None:
        """Parse a single declaration dict, returning None for invalid entries."""
        if not isinstance(data, dict):
            return None
        raw_path = data.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            return None
        path = raw_path.strip()
        action = _normalize_optional_string(data.get("action"))
        target_kind = _normalize_optional_string(data.get("target_kind"))
        target_id = _normalize_optional_string(data.get("target_id"))
        return cls(path=path, action=action, target_kind=target_kind, target_id=target_id)


def _declared_action_labels(repo_root: Path) -> frozenset[str]:
    """FR-008 (#3596, ADR 2026-08-21-1-charter-gate-predicate-inversion).

    Type-agnostic declared-node source: every action-step label reachable on
    ANY ``action:<type>/<step>`` DRG node (across every mission type, not just
    ``software-dev``), consulted ALONGSIDE the fast-path
    :data:`~charter.activation.context.BOOTSTRAP_ACTIONS` constant so the fast-path set
    never becomes the closed acceptance allowlist (squad note S6) -- a
    declared node outside the four fast-path tokens (e.g. ``tasks``,
    ``retrospect``) is accepted, not warn-dropped.

    Best-effort: any DRG load failure degrades to an empty set (the fast-path
    set alone still governs acceptance), mirroring
    ``_load_action_doctrine_bundle``'s WARNING-and-degrade posture for the
    same failure mode -- interview validation must not hard-fail on a
    charter-less or malformed project. ``FileNotFoundError``/``OSError`` are
    caught alongside ``DRGLoadError`` -- the shipped-graph-missing case
    (e.g. a broken install) surfaces as a raw ``OSError``, not a translated
    ``DRGLoadError``, matching the established idiom at
    ``charter.reference_resolver``'s own ``load_validated_graph`` call site.
    """
    from charter.offering.drg.loader import DRGLoadError  # noqa: PLC0415 -- leaf import, no cycle risk
    from charter.offering.drg.validator import DRGValidationError  # noqa: PLC0415 -- leaf import, no cycle risk

    from charter.activation._drg_helpers import load_validated_graph  # noqa: PLC0415 -- see cycle note below

    try:
        merged = load_validated_graph(repo_root)
    except (DRGLoadError, DRGValidationError, OSError):
        return frozenset()
    return frozenset(
        urn.split("/", 1)[1]
        for urn in merged.node_urns()
        if urn.startswith("action:") and "/" in urn
    )


def validate_local_support_declarations(
    declarations: list[LocalSupportDeclaration],
    *,
    repo_root: Path | None = None,
) -> tuple[list[LocalSupportDeclaration], list[str]]:
    """Validate and normalize a list of declarations.

    Returns (valid_declarations, error_messages).
    Rejects directory paths (trailing slash or no extension when a glob char present)
    and paths containing glob characters.

    *repo_root*, when supplied, feeds :func:`_declared_action_labels` -- FR-008's
    second acceptance input (a declared DRG action node), alongside the
    fast-path :data:`~charter.activation.context.BOOTSTRAP_ACTIONS` constant. Omitting it
    (existing callers, existing tests) degrades to fast-path-only acceptance,
    the pre-fix behaviour -- backward compatible, not a new hard requirement.
    """
    valid: list[LocalSupportDeclaration] = []
    errors: list[str] = []

    # Cycle note: `charter.activation.context` sits above this module in the
    # existing import graph, so a module-level import of
    # ``BOOTSTRAP_ACTIONS`` could import a partially initialized module back
    # through that chain.
    # Function-local import breaks the cycle (established pattern -- see
    # `charter.resolver`'s lazy `CharterInterview` import).
    from charter.activation.context import BOOTSTRAP_ACTIONS  # noqa: PLC0415

    declared_labels = _declared_action_labels(repo_root) if repo_root is not None else frozenset()
    known_actions = BOOTSTRAP_ACTIONS | declared_labels

    for decl in declarations:
        path = decl.path
        # Reject glob patterns
        if any(c in path for c in _GLOB_CHARS):
            errors.append(
                f"local_supporting_files path '{path}' contains glob characters; "
                "explicit file paths only."
            )
            continue
        # Reject paths that look like directories (trailing slash)
        if path.endswith(("/", "\\")):
            errors.append(
                f"local_supporting_files path '{path}' looks like a directory; "
                "explicit file paths only."
            )
            continue
        # Normalize action: unknown values are silently dropped (set to None)
        normalized_action: str | None = None
        if decl.action is not None:
            if decl.action in known_actions:
                normalized_action = decl.action
            else:
                errors.append(
                    f"local_supporting_files path '{path}': unknown action "
                    f"'{decl.action}' (expected one of {sorted(known_actions)}); "
                    "treating as global."
                )
                # Still include the declaration but with action=None
        normalized = LocalSupportDeclaration(
            path=path,
            action=normalized_action,
            target_kind=decl.target_kind,
            target_id=decl.target_id,
        )
        valid.append(normalized)

    return valid, errors


QUESTION_ORDER: tuple[str, ...] = (
    "project_intent",
    "languages_frameworks",
    "testing_requirements",
    "quality_gates",
    "review_policy",
    "performance_targets",
    "deployment_constraints",
    "documentation_policy",
    "risk_boundaries",
    "amendment_process",
    "exception_policy",
)

MINIMAL_QUESTION_ORDER: tuple[str, ...] = (
    "project_intent",
    "languages_frameworks",
    "testing_requirements",
    "quality_gates",
    "review_policy",
    "performance_targets",
    "deployment_constraints",
)


QUESTION_PROMPTS: dict[str, str] = {
    "project_intent": "What is the core user outcome this project optimizes for?",
    "languages_frameworks": "What languages/frameworks are expected?",
    "testing_requirements": "What testing and coverage expectations apply?",
    "quality_gates": "What quality gates must pass before merge?",
    "review_policy": "What review/approval policy should contributors follow?",
    "performance_targets": "What performance targets matter most (or N/A)?",
    "deployment_constraints": "What deployment/platform constraints apply?",
    "documentation_policy": "What documentation standards should be enforced?",
    "risk_boundaries": "What safety, privacy, or reliability boundaries are non-negotiable?",
    "amendment_process": "How should charter changes be proposed and approved?",
    "exception_policy": "How should exceptions to the charter be handled?",
}

_DEFAULT_MISSION_PARADIGMS: dict[str, tuple[str, ...]] = {}

_DEFAULT_MISSION_DIRECTIVES: dict[str, tuple[str, ...]] = {}


_UNSET = object()
_LYNN_COLE_DIRECTIVE = "DIRECTIVE_039"
_LYNN_COLE_PARADIGM = "deep-module-design"
_LYNN_COLE_EXPLICIT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\blynn\s+cole\b"),
)
_LYNN_COLE_CONCERN_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bagents?\s+(?:write|produce|generate|create)\s+too\s+much\s+code\b"),
    re.compile(r"\b(?:ai|llm|agentic|generated)\s+code\s+(?:is\s+)?(?:bloated|sprawling|too\s+long)\b"),
    re.compile(r"\b(?:code|implementation)\s+bloat\b"),
    re.compile(r"\b(?:avoid|stop|prevent|reduce)\s+(?:agentic\s+)?(?:code\s+)?bloat\b"),
    re.compile(r"\bover[- ]?abstract(?:ion|ed|ing)?\b"),
    re.compile(r"\bsprawling\s+(?:helpers?|functions?|code|implementation)\b"),
    re.compile(r"\btoo\s+many\s+(?:helpers?|abstractions?|files?|layers?)\b"),
)


@dataclass(frozen=True)
class CharterInterview:
    """Persisted interview answers used to compile charter artifacts."""

    mission: str
    profile: str
    answers: dict[str, str]
    selected_paradigms: list[str]
    selected_directives: list[str]
    available_tools: list[str]
    agent_profile: str | None = None
    agent_role: str | None = None
    local_supporting_files: list[LocalSupportDeclaration] | None = None
    selected_tactics: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        # Normalize None to empty list for local_supporting_files (frozen dataclass workaround)
        if self.local_supporting_files is None:
            object.__setattr__(self, "local_supporting_files", [])

    def to_dict(self) -> dict[str, object]:
        d: dict[str, object] = {
            "schema_version": "1.0.0",
            "mission": self.mission,
            "profile": self.profile,
            "answers": dict(self.answers),
            "selected_paradigms": list(self.selected_paradigms),
            "selected_directives": list(self.selected_directives),
            "selected_tactics": list(self.selected_tactics),
            "available_tools": list(self.available_tools),
            "agent_profile": self.agent_profile,
            "agent_role": self.agent_role,
        }
        if self.local_supporting_files:
            d["local_supporting_files"] = [decl.to_dict() for decl in self.local_supporting_files]
        return d

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> CharterInterview:
        mission = str(data.get("mission", "software-dev")).strip() or "software-dev"
        profile = str(data.get("profile", "minimal")).strip() or "minimal"
        raw_answers = data.get("answers")
        answers: dict[str, str] = (
            {str(k): str(v) for k, v in raw_answers.items()} if isinstance(raw_answers, dict) else {}
        )

        raw_local = data.get("local_supporting_files")
        local_supporting_files: list[LocalSupportDeclaration] = []
        if isinstance(raw_local, list):
            for item in raw_local:
                parsed = LocalSupportDeclaration.from_dict(item)
                if parsed is not None:
                    local_supporting_files.append(parsed)

        return apply_doctrine_intent_aliases(cls(
            mission=mission,
            profile=profile,
            answers=answers,
            selected_paradigms=_normalize_list(data.get("selected_paradigms")),
            selected_directives=_normalize_list(data.get("selected_directives")),
            available_tools=_normalize_list(data.get("available_tools")),
            agent_profile=_normalize_optional_string(data.get("agent_profile")),
            agent_role=_normalize_optional_string(data.get("agent_role")),
            local_supporting_files=local_supporting_files,
            selected_tactics=_normalize_list(data.get("selected_tactics")),
        ))


def default_interview(
    *,
    mission: str,
    profile: str = "minimal",
    offering_catalog: OfferingCatalog | None = None,
) -> CharterInterview:
    """Return deterministic default interview answers."""
    catalog = offering_catalog or load_offering_catalog()
    defaults = _load_packaged_defaults()
    raw_default_answers = defaults.get("answers", {})
    answers: dict[str, str] = (
        dict(cast(dict[str, str], raw_default_answers))
        if isinstance(raw_default_answers, dict)
        else {}
    )

    if profile == "minimal":
        answers = {key: answers[key] for key in MINIMAL_QUESTION_ORDER}

    default_paradigms = _resolve_default_selection(
        mission=mission,
        configured=_DEFAULT_MISSION_PARADIGMS,
        available=catalog.paradigms,
    )
    default_directives = _resolve_default_selection(
        mission=mission,
        configured=_DEFAULT_MISSION_DIRECTIVES,
        available=catalog.directives,
    )

    return apply_doctrine_intent_aliases(CharterInterview(
        mission=mission,
        profile=profile,
        answers=answers,
        selected_paradigms=_normalize_iterable(
            cast(Iterable[str] | None, defaults.get("selected_paradigms")),
            fallback=default_paradigms,
        ),
        selected_directives=_normalize_iterable(
            cast(Iterable[str] | None, defaults.get("selected_directives")),
            fallback=default_directives,
        ),
        available_tools=_normalize_iterable(
            cast(Iterable[str] | None, defaults.get("available_tools")),
            fallback=sorted(DEFAULT_TOOL_REGISTRY),
        ),
        selected_tactics=_normalize_iterable(
            cast(Iterable[str] | None, defaults.get("selected_tactics")),
            fallback=[],
        ),
    ))


def read_interview_answers(path: Path, *, unsafe: bool = False) -> CharterInterview | None:
    """Read interview answers from YAML, returning None when missing/invalid.

    Encoding-consistency failures (:class:`CharterEncodingError`, a subclass
    of :class:`kernel.errors.KittyInternalConsistencyError`) propagate to the
    caller so the operator sees the diagnostic with remediation guidance.
    Other failure modes (missing file, malformed YAML structure on a
    successfully-decoded file, wrong top-level type) continue to degrade to
    ``None`` per the pre-existing contract.

    Args:
        path: filesystem path to the interview YAML file.
        unsafe: when True, bypass CHARTER_ENCODING_AMBIGUOUS by accepting the
            highest-confidence decode candidate and logging bypass_used=True in
            provenance.  Use only when you have inspected the file and accept
            the operational risk; the bypass is recorded in
            ``.encoding-provenance.jsonl``.
    """
    if not path.exists():
        return None

    yaml = YAML(typ="safe")
    text = load_charter_file(path, unsafe=unsafe).text
    try:
        data = yaml.load(text) or {}
    except Exception:  # noqa: BLE001 — YAML parse failures degrade to None
        # Pre-existing resilience contract: a syntactically-broken YAML file
        # whose encoding decoded cleanly is treated as "no usable answers"
        # rather than halting the interview command. Encoding errors are NOT
        # caught here — they raise above in load_charter_file().
        return None

    if not isinstance(data, dict):
        return None

    return CharterInterview.from_dict(data)


#: Top-level list fields ``CharterInterview.to_dict()`` emits directly --
#: and therefore the only fields a write can silently reset to empty. Every
#: OTHER list-shaped key that may exist on disk (e.g. ``selected_
#: styleguides``, added by a schema generation this dataclass has not
#: caught up with) is not modeled here at all, so :func:`write_interview_
#: answers`'s merge carries it forward untouched and it can never regress
#: through this writer.
_KNOWN_REGRESSION_GUARDED_LIST_FIELDS: tuple[str, ...] = (
    "selected_paradigms",
    "selected_directives",
    "selected_tactics",
    "available_tools",
)


class InterviewAnswersRegressionError(RuntimeError):
    """Raised by :func:`write_interview_answers` (``fail_closed_on_regression=
    True``) when persisting ``interview`` would silently drop or reset data
    already recorded on disk at ``path``.

    ``CharterInterview`` models only a subset of ``answers.yaml``'s keys --
    schema growth over time (e.g. ``selected_styleguides``/``template_set``)
    has outpaced the dataclass. The writer therefore merges onto whatever is
    already on disk rather than overwriting it wholesale, so those unmodeled
    keys always survive untouched regardless of this flag. This exception is
    the other half of that data-integrity contract, for callers (e.g. the
    answers-migration tooling) that additionally want a hard failure rather
    than a silent write when a *modeled* selection or answer would be wiped
    out -- see :func:`_guard_against_regression`.
    """


def _read_raw_answers_dict(path: Path) -> dict[str, Any]:
    """Load ``path`` as a plain dict, tolerating a missing/malformed file.

    Mirrors :func:`read_interview_answers`'s resilience contract: a missing
    file, or one that fails to parse or does not decode to a mapping,
    degrades to ``{}`` rather than raising -- the writer treats "nothing on
    disk yet" the same as "empty answers".
    """
    if not path.exists():
        return {}
    yaml = YAML(typ="safe")
    try:
        data = yaml.load(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 -- degrade to empty, mirrors read_interview_answers
        return {}
    return data if isinstance(data, dict) else {}


def _guard_against_regression(existing: dict[str, Any], new: dict[str, Any]) -> None:
    """Fail closed if ``new`` would drop or reset data recorded in ``existing``.

    Two mutation shapes are rejected:

    * **Default-reset** -- a known selection list (:data:`_KNOWN_
      REGRESSION_GUARDED_LIST_FIELDS`, e.g. ``selected_tactics``) that was
      previously non-empty and would become empty/absent.
    * **Deletion** -- an ``answers`` entry that previously carried a real
      value and would become missing or empty.
    """
    for field_name in _KNOWN_REGRESSION_GUARDED_LIST_FIELDS:
        old_value = existing.get(field_name)
        new_value = new.get(field_name)
        if isinstance(old_value, list) and old_value and not new_value:
            raise InterviewAnswersRegressionError(
                f"Refusing to write '{field_name}': would drop "
                f"{len(old_value)} existing selection(s) with no replacement."
            )

    existing_answers = existing.get("answers")
    if not isinstance(existing_answers, dict):
        return
    new_answers = new.get("answers")
    new_answers_dict = new_answers if isinstance(new_answers, dict) else {}
    for key, old_answer in existing_answers.items():
        if old_answer and not new_answers_dict.get(key):
            raise InterviewAnswersRegressionError(
                f"Refusing to write answers: existing answer {key!r} would "
                "be dropped or emptied."
            )


def write_interview_answers(
    path: Path,
    interview: CharterInterview,
    *,
    fail_closed_on_regression: bool = False,
) -> None:
    """Persist interview answers to YAML.

    Merges onto whatever is already at ``path`` rather than overwriting it
    wholesale: ``CharterInterview`` models only a subset of the file's keys
    (e.g. ``selected_styleguides``/``template_set`` have no dataclass
    field), so a naive re-serialize would silently drop them on every write
    that round-trips through :func:`read_interview_answers`. This merge is
    unconditional and always on.

    ``fail_closed_on_regression`` additionally raises :class:`
    InterviewAnswersRegressionError` instead of persisting a change that
    would drop or reset a previously-recorded *modeled* selection or answer
    (see :func:`_guard_against_regression`). It defaults to ``False``
    because the interactive interview flow legitimately starts each session
    from :func:`default_interview` and may intentionally narrow a prior
    selection (e.g. a user deselecting a tactic) -- callers that want the
    stricter round-trip contract (the answers-migration tooling, in
    particular) opt in explicitly.
    """
    new_data = interview.to_dict()
    existing_data = _read_raw_answers_dict(path)
    if fail_closed_on_regression:
        _guard_against_regression(existing_data, new_data)

    merged: dict[str, Any] = {**existing_data, **new_data}

    path.parent.mkdir(parents=True, exist_ok=True)
    yaml = YAML()
    yaml.default_flow_style = False
    with path.open("w", encoding="utf-8") as handle:
        yaml.dump(merged, handle)


def apply_org_charter_pre_fill_to_answers(
    *,
    answers_path: Path,
    interview_defaults: dict[str, str | bool],
    required_directives: list[str],
) -> list[str]:
    """Pure data side-effect: non-destructively pre-fill ``answers.yaml``.

    The org-layer caller (``charter.activation.org_charter``) loads and
    merges org-pack policies and passes the resulting interview defaults
    and required directives into this helper as plain Python data.  This
    keeps the ``charter`` layer free of ``specify_cli`` imports
    (ADR 2026-03-27-1) while letting the YAML side-effect live next to
    the rest of the interview answer machinery.

    Semantics:

    * For each key in ``interview_defaults``, set the value in
      ``answers.yaml`` **only when the key is missing**.  Existing values
      are preserved so re-running the interview never reverts
      project-specific choices to org defaults.
    * For ``required_directives``, append entries that are not already
      present in ``selected_directives`` (set-like union, order preserved).
    * When nothing changes, ``answers.yaml`` is not written.

    Returns a list of human-readable messages describing what was applied.
    Returns an empty list when no changes were needed.
    """
    if not interview_defaults and not required_directives:
        return []

    yaml = YAML()
    yaml.default_flow_style = False

    existing = _load_existing_answers(answers_path, yaml)

    prefilled = _prefill_answer_defaults(existing, interview_defaults)
    new_required = _merge_required_directives(existing, required_directives)

    messages: list[str] = []
    if new_required:
        messages.append(
            f"Pre-selected {len(new_required)} directives from org charter "
            "required_directives."
        )

    if prefilled:
        messages.append(
            f"Pre-filled {prefilled} interview defaults from org charter."
        )

    if messages:
        answers_path.parent.mkdir(parents=True, exist_ok=True)
        with answers_path.open("w", encoding="utf-8") as handle:
            yaml.dump(existing, handle)

    return messages


def _load_existing_answers(answers_path: Path, yaml: YAML) -> dict[str, Any]:
    """Load ``answers_path`` as a dict, tolerating a missing or malformed file.

    Mirrors the pre-existing resilience contract: a missing file or a file
    that fails to parse (or does not decode to a mapping) degrades to an
    empty dict rather than raising.
    """
    if not answers_path.exists():
        return {}
    try:
        with answers_path.open("r", encoding="utf-8") as handle:
            loaded = yaml.load(handle)
    except Exception:  # noqa: BLE001 — malformed YAML treated as empty
        loaded = None
    return loaded if isinstance(loaded, dict) else {}


def _prefill_answer_defaults(
    existing: dict[str, Any], interview_defaults: dict[str, str | bool]
) -> int:
    """Set each default whose key is missing from ``existing`` in place.

    Returns the count of keys that were prefilled.
    """
    prefilled = 0
    for key, value in interview_defaults.items():
        if key not in existing:
            existing[key] = value
            prefilled += 1
    return prefilled


def _existing_directives_from(existing: dict[str, Any]) -> list[str]:
    """Normalize ``existing["selected_directives"]`` to a list of strings."""
    raw = existing.get("selected_directives")
    if isinstance(raw, list):
        return [str(d) for d in raw]
    if isinstance(raw, str):
        return _normalize_csv(raw)
    return []


def _merge_required_directives(
    existing: dict[str, Any], required_directives: list[str]
) -> list[str]:
    """Append any missing ``required_directives`` to ``existing`` in place.

    Returns the subset of ``required_directives`` that was newly added
    (order preserved), or an empty list when nothing was missing.
    """
    existing_directives = _existing_directives_from(existing)
    new_required = [d for d in required_directives if d not in existing_directives]
    if new_required:
        existing["selected_directives"] = existing_directives + new_required
    return new_required


def apply_answer_overrides(
    interview: CharterInterview,
    *,
    answers: dict[str, str] | None = None,
    selected_paradigms: Iterable[str] | None = None,
    selected_directives: Iterable[str] | None = None,
    selected_tactics: Iterable[str] | None = None,
    available_tools: Iterable[str] | None = None,
    agent_profile: str | None | object = _UNSET,
    agent_role: str | None | object = _UNSET,
    local_supporting_files: list[LocalSupportDeclaration] | None | object = _UNSET,
) -> CharterInterview:
    """Return an updated interview with selected fields overridden."""
    merged_answers = dict(interview.answers)
    if answers:
        for key, value in answers.items():
            if value is None:
                continue
            merged_answers[str(key)] = str(value)

    resolved_local: list[LocalSupportDeclaration]
    if local_supporting_files is _UNSET:
        resolved_local = list(interview.local_supporting_files or [])
    elif local_supporting_files is None:
        resolved_local = []
    else:
        resolved_local = list(cast(list[LocalSupportDeclaration], local_supporting_files))

    return apply_doctrine_intent_aliases(CharterInterview(
        mission=interview.mission,
        profile=interview.profile,
        answers=merged_answers,
        selected_paradigms=_normalize_iterable(
            selected_paradigms,
            fallback=interview.selected_paradigms,
        ),
        selected_directives=_normalize_iterable(
            selected_directives,
            fallback=interview.selected_directives,
        ),
        available_tools=_normalize_iterable(
            available_tools,
            fallback=interview.available_tools,
        ),
        agent_profile=interview.agent_profile if agent_profile is _UNSET else _normalize_optional_string(agent_profile),
        agent_role=interview.agent_role if agent_role is _UNSET else _normalize_optional_string(agent_role),
        local_supporting_files=resolved_local,
        selected_tactics=_normalize_iterable(
            selected_tactics,
            fallback=interview.selected_tactics,
        ),
    ))


def apply_doctrine_intent_aliases(interview: CharterInterview) -> CharterInterview:
    """Select doctrine implied by well-known user shorthand in interview text."""
    if not _matches_lynn_cole_alias(interview):
        return interview

    selected_directives = _append_unique(interview.selected_directives, _LYNN_COLE_DIRECTIVE)
    selected_paradigms = _append_unique(interview.selected_paradigms, _LYNN_COLE_PARADIGM)
    if (
        selected_directives == interview.selected_directives
        and selected_paradigms == interview.selected_paradigms
    ):
        return interview

    return CharterInterview(
        mission=interview.mission,
        profile=interview.profile,
        answers=dict(interview.answers),
        selected_paradigms=selected_paradigms,
        selected_directives=selected_directives,
        available_tools=list(interview.available_tools),
        agent_profile=interview.agent_profile,
        agent_role=interview.agent_role,
        local_supporting_files=list(interview.local_supporting_files or []),
        selected_tactics=list(interview.selected_tactics),
    )


def _matches_lynn_cole_alias(interview: CharterInterview) -> bool:
    haystack = " ".join(str(value).lower() for value in interview.answers.values())
    if not haystack.strip():
        return False
    return any(pattern.search(haystack) for pattern in _LYNN_COLE_EXPLICIT_PATTERNS) or any(
        pattern.search(haystack) for pattern in _LYNN_COLE_CONCERN_PATTERNS
    )


def _append_unique(values: list[str], item: str) -> list[str]:
    result = list(values)
    if item not in result:
        result.append(item)
    return result


def _normalize_iterable(values: Iterable[str] | None, *, fallback: list[str]) -> list[str]:
    if values is None:
        return list(fallback)
    normalized: list[str] = []
    for value in values:
        item = str(value).strip()
        if item and item not in normalized:
            normalized.append(item)
    return normalized


def _normalize_list(raw: object) -> list[str]:
    if isinstance(raw, str):
        return _normalize_csv(raw)
    if isinstance(raw, list):
        return _normalize_iterable(raw, fallback=[])
    return []


def _normalize_csv(raw: str) -> list[str]:
    parts = [part.strip() for part in raw.split(",")]
    return [part for part in parts if part]


def _normalize_optional_string(raw: object) -> str | None:
    if raw is None:
        return None
    value = str(raw).strip()
    return value or None


def packaged_default_answer(key: str) -> str | None:
    """Return the shipped ``defaults.yaml`` answer text for *key* (``None`` when absent).

    Lightweight alternative to :func:`default_interview`, which also loads the
    doctrine catalog; callers that only need to recognise the shipped default
    text (e.g. language resolution, #3292) use this.
    """
    answers = _load_packaged_defaults().get("answers")
    if not isinstance(answers, dict):
        return None
    value = answers.get(key)
    return str(value) if value is not None else None


def _load_packaged_defaults() -> dict[str, object]:
    """Load authoritative default interview content from ``defaults.yaml``."""
    empty: dict[str, object] = {
        "answers": {},
        "selected_paradigms": [],
        "selected_directives": [],
        "selected_tactics": [],
        "available_tools": [],
    }
    try:
        defaults_path = importlib.resources.files("charter").joinpath("defaults.yaml")
        content = defaults_path.read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError, TypeError):
        return empty

    yaml = YAML(typ="safe")
    try:
        data = yaml.load(content) or {}
    except Exception:
        return empty

    if not isinstance(data, dict):
        return empty

    answers = data.get("answers")
    normalized_answers = (
        {str(key): str(value) for key, value in answers.items()}
        if isinstance(answers, dict)
        else {}
    )
    return {
        "answers": normalized_answers,
        "selected_paradigms": _normalize_list(data.get("selected_paradigms")),
        "selected_directives": _normalize_list(data.get("selected_directives")),
        "selected_tactics": _normalize_list(data.get("selected_tactics")),
        "available_tools": _normalize_list(data.get("available_tools")),
    }


def _resolve_default_selection(
    *,
    mission: str,
    configured: dict[str, tuple[str, ...]],
    available: frozenset[str],
) -> list[str]:
    selected: list[str] = []
    for candidate in configured.get(mission, ()):
        if candidate in available and candidate not in selected:
            selected.append(candidate)
    return selected
