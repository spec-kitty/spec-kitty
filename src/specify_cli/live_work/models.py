"""Canonical Live Work capture records (spec-kitty#4268).

One :class:`Observation` is what every harness adapter produces and what the
publisher projects onto the relay's bounded ``event.publish`` wire. The
record's shape follows the shared ``WorkObservation`` contract
(events ``work_observation``, 10.1.0): identity dimensions stay distinct
(session, actor, repository, mission), an action carries exactly one typed
detail, pre-result observations never invent an outcome, and failure/skip
kinds require honest inline text.

Binding honesty rules (LIVE-WORK.md §3.1, glossary "Attribution"):

* a mission binding is set only when it is actually determinable from the
  repository's own mission metadata — never guessed from cwd, the last
  event, or an assignee;
* an unknown actor or binding stays :class:`UnknownActor` / ``None`` and is
  published as ``unknown`` on the wire, never fabricated;
* repository identity is the git-truth remote slug — the authenticated
  principal and the admitted-repository generation are server-derived at
  the relay, never asserted here.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .kinds import WorkEmissionKind

__all__ = [
    "ActivityBinding",
    "ActorBinding",
    "CoverageDetail",
    "FileDetail",
    "FileOperation",
    "MissionBinding",
    "Observation",
    "ObservationAction",
    "Provenance",
    "RepositoryBinding",
    "SessionBinding",
    "TestRunDetail",
    "ToolDetail",
    "ToolOutcome",
    "ToolState",
    "UnknownActor",
]


class ToolState(StrEnum):
    """Lifecycle state of an observed tool/test activity (LW-04/LW-09).

    The live dashboard shows work *while it happens*; the conclusion
    correlates to the same activity through a shared ``activity_id``.
    ``RESULT`` is the only state that may carry an outcome (and test
    counts); ``CANCELLED`` is an honest terminal state, never a missing
    result.
    """

    STARTED = "started"
    RUNNING = "running"
    RESULT = "result"
    CANCELLED = "cancelled"


class ToolOutcome(StrEnum):
    """Explicit outcome for a concluded action — failure/skip are first-class."""

    SUCCESS = "success"
    FAILURE = "failure"
    SKIPPED = "skipped"


class FileOperation(StrEnum):
    """The operation a file observation records (LW-04)."""

    READ = "read"
    EDIT = "edit"
    CREATE = "create"
    DELETE = "delete"
    RENAME = "rename"


class SessionBinding(BaseModel):
    """The stable logical harness session that produced the observation.

    ``session_id`` is the harness's own session identifier (Claude Code's
    ``session_id``, Codex's thread id). A delegated child session names its
    parent via ``parent_session_id`` — parent lineage is preserved, and a
    retry of a delegation is a *new* linked session, never a re-take of the
    same id (LW-01).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    session_id: Annotated[str, Field(min_length=1, max_length=128)]
    parent_session_id: Annotated[str | None, Field(min_length=1, max_length=128)] = None


class UnknownActor(BaseModel):
    """An actor the capture layer cannot attribute — stays visible as unknown.

    Per the glossary's *sampled observation* rule this is published as
    ``actor=unknown``, never guessed from cwd, the last event, or an
    assignee field.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    unknown: Literal[True] = True


class ActorBinding(BaseModel):
    """The acting logical agent, as producer-side attribution only.

    The authenticated principal is derived server-side from the credential;
    ``agent_label`` is a mutable display label, never identity.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    harness: Annotated[str, Field(min_length=1, max_length=32)]
    agent_label: Annotated[str | None, Field(min_length=1, max_length=128)] = None


class RepositoryBinding(BaseModel):
    """The git-truth repository the observation was made in."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: Literal["github"] = "github"
    slug: Annotated[str, Field(min_length=1, max_length=240)]
    branch: Annotated[str | None, Field(min_length=1, max_length=240)] = None


class MissionBinding(BaseModel):
    """A canonical mission binding, set only when actually determinable."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    mission_id: Annotated[str, Field(min_length=1, max_length=120)]
    display_label: Annotated[str | None, Field(min_length=1, max_length=240)] = None


class ActivityBinding(BaseModel):
    """Activity grouping: concurrent tool calls and subagents stay distinct
    inside one continuous mission; an activity may name its parent."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    activity_id: Annotated[str, Field(min_length=1, max_length=128)]
    parent_activity_id: Annotated[str | None, Field(min_length=1, max_length=128)] = None


class Provenance(BaseModel):
    """How the observation was captured, and the honest limitation when
    capture is partial (LW-04's capability matrix, machine-readable)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source: Literal["harness_hook", "cli_wrapper", "emitter", "manual", "factory"]
    capability: Annotated[str, Field(min_length=1, max_length=64)]
    limitation: Annotated[str | None, Field(min_length=1, max_length=240)] = None


class ToolDetail(BaseModel):
    """A tool invocation at any lifecycle state — tool *name*, state,
    outcome (terminal only), duration. Never the raw command environment or
    tool output: those are excluded by :mod:`live_work.redaction`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tool: Annotated[str, Field(min_length=1, max_length=64)]
    state: ToolState
    outcome: ToolOutcome | None = None
    duration_ms: Annotated[int | None, Field(ge=0)] = None

    @model_validator(mode="after")
    def _state_outcome_agreement(self) -> ToolDetail:
        if self.state == ToolState.RESULT and self.outcome is None:
            raise ValueError("state='result' requires an outcome")
        if self.state != ToolState.RESULT and self.outcome is not None:
            raise ValueError("outcome is only carried at state='result' — a started/running/cancelled observation must not invent a concluded outcome")
        return self


class FileDetail(BaseModel):
    """A file operation as metadata only: operation, repository-relative
    path (and rename destination), byte deltas. There is deliberately no
    contents field — file contents are never observable work."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    operation: FileOperation
    path: Annotated[str, Field(min_length=1, max_length=240)]
    destination_path: Annotated[str | None, Field(min_length=1, max_length=240)] = None
    bytes_added: Annotated[int, Field(ge=0)]
    bytes_removed: Annotated[int, Field(ge=0)]
    coalesced_edits: Annotated[int, Field(ge=1)] = 1
    coalesced_window_s: Annotated[float | None, Field(ge=0.0)] = None
    attribution: Literal["exact", "sampled"] = "exact"

    @model_validator(mode="after")
    def _rename_agreement(self) -> FileDetail:
        if self.operation == FileOperation.RENAME and self.destination_path is None:
            raise ValueError("operation='rename' requires destination_path")
        if self.operation != FileOperation.RENAME and self.destination_path is not None:
            raise ValueError("destination_path is only carried at operation='rename'")
        return self


class TestRunDetail(BaseModel):
    """A test/build/lint execution: selector plus explicit counts, carried
    only once the run concludes. Never raw output."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    # Not a pytest test class, despite the name (the shared contract calls
    # this shape a test action; the dunder keeps pytest from collecting it).
    __test__ = False

    selector: Annotated[str, Field(min_length=1, max_length=240)]
    state: ToolState
    passed: Annotated[int | None, Field(ge=0)] = None
    failed: Annotated[int | None, Field(ge=0)] = None
    skipped: Annotated[int | None, Field(ge=0)] = None
    outcome: ToolOutcome | None = None

    @model_validator(mode="after")
    def _state_terminal_agreement(self) -> TestRunDetail:
        if self.state == ToolState.RESULT:
            if self.outcome is None:
                raise ValueError("state='result' requires an outcome")
            if self.passed is None or self.failed is None or self.skipped is None:
                raise ValueError("state='result' requires the passed/failed/skipped counts")
        elif self.outcome is not None or self.passed is not None or self.failed is not None or self.skipped is not None:
            raise ValueError(
                "outcome and counts are only carried at state='result' — a started/running/cancelled test observation must not invent concluded results"
            )
        return self


class CoverageDetail(BaseModel):
    """An explicitly recorded capture gap (LW-08/LW-10): an area this
    producer could not observe, with the honest reason — gaps are recorded
    as data, never silently dropped."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    area: Annotated[str, Field(min_length=1, max_length=64)]
    reason: Annotated[str | None, Field(min_length=1, max_length=240)] = None


ObservationAction = ToolDetail | FileDetail | TestRunDetail
"""The typed action detail — exactly one per action-kind observation."""


class Observation(BaseModel):
    """One canonical Live Work capture record.

    ``actor`` is either an :class:`ActorBinding` (exact, hook-attributed) or
    :class:`UnknownActor` (sampled/unknown — stays visible as unknown).
    ``mission`` is ``None`` for repository-bound work: a producer never
    invents mission identity (LW-02).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: WorkEmissionKind
    session: SessionBinding
    actor: ActorBinding | UnknownActor
    repository: RepositoryBinding
    provenance: Provenance

    mission: MissionBinding | None = None
    activity: ActivityBinding | None = None
    action: ObservationAction | None = None
    coverage: CoverageDetail | None = None
    counterpart: Annotated[
        str | None,
        Field(
            min_length=1,
            max_length=128,
            description=(
                "The delegation counterpart — the delegated child session id "
                "when known, else the counterpart logical agent (subagent "
                "type). Required by the delegation kinds."
            ),
        ),
    ] = None
    extensions: Annotated[
        dict[str, str | int | float | bool] | None,
        Field(
            description=(
                "Safe optional live-wire metadata (e.g. a sanitized command "
                "summary). Keys MUST be x- prefixed, mirroring the shared "
                "contract's extension surface; unknown un-namespaced keys are "
                "rejected."
            )
        ),
    ] = None
    text: Annotated[
        str | None,
        Field(
            min_length=1,
            max_length=2000,
            description=(
                "Bounded honest inline text — required by the failure/skip lifecycle kinds and usable for a coverage reason; long content is never inlined."
            ),
        ),
    ] = None
    occurred_at: Annotated[
        str,
        Field(
            min_length=20,
            max_length=40,
            description=("Producer occurrence time, ISO-8601 UTC — presentation only, never an ordering authority."),
        ),
    ]

    @model_validator(mode="after")
    def _per_kind(self) -> Observation:
        # Action kinds bind to exactly one typed action detail.
        action_model_by_kind = {
            WorkEmissionKind.TOOL_INVOKED: ToolDetail,
            WorkEmissionKind.FILE_EDITED: FileDetail,
            WorkEmissionKind.TEST_EXECUTED: TestRunDetail,
        }
        expected = action_model_by_kind.get(self.kind)
        if expected is not None and not isinstance(self.action, expected):
            raise ValueError(f"kind {self.kind.value!r} requires a {expected.__name__} action detail")
        # Coverage kind carries a coverage detail; other kinds must not.
        if self.kind == WorkEmissionKind.COVERAGE_GAP and self.coverage is None:
            raise ValueError("kind 'coverage.gap_recorded' requires a coverage detail")
        if self.kind != WorkEmissionKind.COVERAGE_GAP and self.coverage is not None:
            raise ValueError("coverage detail is only carried at kind 'coverage.gap_recorded'")
        # Action kinds never carry inline text (shared contract rule: the
        # typed detail is the observation; prose never rides an action).
        action_kinds = {
            WorkEmissionKind.TOOL_INVOKED,
            WorkEmissionKind.FILE_EDITED,
            WorkEmissionKind.TEST_EXECUTED,
        }
        if self.kind in action_kinds and self.text is not None:
            raise ValueError(f"kind {self.kind.value!r} must not carry inline text — the typed action detail is the observation")
        # Failure/skip lifecycle kinds require honest inline text (LW-03).
        failed_or_skipped = {
            WorkEmissionKind.RETROSPECTIVE_FAILED,
            WorkEmissionKind.RETROSPECTIVE_SKIPPED,
        }
        if self.kind in failed_or_skipped and not self.text:
            raise ValueError(f"kind {self.kind.value!r} requires honest inline text — failure and skip are first-class, never laundered into silence")
        # Narrative/message kinds (#4269's authored surface) carry authored
        # prose: the text IS the observation, and a typed action detail can
        # never stand in for it — an authored message with no body is inert.
        narrative_kinds = {
            WorkEmissionKind.NARRATIVE_INTENT_DECLARED,
            WorkEmissionKind.NARRATIVE_PROGRESS_REPORTED,
            WorkEmissionKind.NARRATIVE_QUESTION_ASKED,
            WorkEmissionKind.NARRATIVE_QUESTION_ANSWERED,
            WorkEmissionKind.NARRATIVE_DECISION_RECORDED,
            WorkEmissionKind.NARRATIVE_HANDOFF_PERFORMED,
            WorkEmissionKind.NARRATIVE_BLOCKER_RAISED,
            WorkEmissionKind.NARRATIVE_BLOCKER_RESOLVED,
            WorkEmissionKind.NARRATIVE_NEXT_PROPOSED,
            WorkEmissionKind.MESSAGE_PEER_SENT,
        }
        if self.kind in narrative_kinds:
            if not self.text:
                raise ValueError(f"kind {self.kind.value!r} requires the authored text — the prose is the observation")
            if self.action is not None:
                raise ValueError(f"kind {self.kind.value!r} must not carry a typed action detail — authored prose is the observation")
        # Delegation kinds must name their counterpart (shared contract:
        # session.delegated_from or recipient — never neither).
        if (
            self.kind in (WorkEmissionKind.DELEGATION_STARTED, WorkEmissionKind.DELEGATION_ENDED)
            and self.session.parent_session_id is None
            and self.counterpart is None
        ):
            raise ValueError(f"kind {self.kind.value!r} requires session.parent_session_id or counterpart to name the delegation counterpart")
        # Extension keys are x- namespaced only (shared contract rule).
        if self.extensions:
            bad = sorted(key for key in self.extensions if not key.startswith("x-"))
            if bad:
                raise ValueError(f"extension keys must be x- prefixed (got {bad}); un-namespaced keys are not a safe extension surface")
        return self
