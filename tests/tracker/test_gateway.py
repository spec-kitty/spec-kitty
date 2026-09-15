"""Tests for the local Beads program gateway (TRK-M1-04).

TRK-M1-04 node criteria (docs/BEADS_PROGRAM_GRAPH.json): "Host adapter maps
Tracker calls through token-valid program gateway, preserves mission/task/
team/repository scope, exposes authority/freshness/conflicts, and cannot
assign/close/approve/release Beads or bypass self-claim/review/publication."

``specify_cli.tracker.gateway`` is the host-owned adapter that satisfies
this: a ``TrackerGatewayToken`` (a validated, scope-bound capability minted
by the host, never by ``spec_kitty_tracker`` or by Beads) and a
``GatewayCommandRunner`` implementing the
``spec_kitty_tracker.connectors.cli_runner.CommandRunner`` protocol
(TRK-M1-02 A4) that a ``BeadsConnector`` is wired through instead of the
package's default ``SubprocessCommandRunner``.

This first group covers ``TrackerGatewayToken`` in isolation: construction
validation, TTL-based freshness, and scope coverage (``covers``). No
``spec_kitty_tracker`` import is required for these -- ``covers`` only does
attribute access on its ``context`` argument, so a plain duck-typed stand-in
exercises it without depending on the installed tracker package version.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from specify_cli.tracker.gateway import (
    GatewayAuthorizationError,
    GatewayCommandRunner,
    GatewayForbiddenOperationError,
    GatewayScopeViolationError,
    TrackerGatewayToken,
    TrackerGatewayUnavailableError,
    build_gateway_beads_connector,
    _canonicalize_argv,
    _extract_subcommand_path,
    _try_import_scope_violation_error,
)

#: A scope violation raises spec_kitty_tracker.errors.ScopeViolationError when
#: the installed tracker package exposes it (0.5.x+, always true in this dev
#: venv per Pattern A -- docs/development/how-to/local-overrides.md), else
#: falls back to GatewayScopeViolationError. Both share the same
#: expected_scope/actual_scope attribute contract, so tests that only need
#: "some scope-violation error was raised, with the right attributes" assert
#: against whichever type is actually live rather than assuming one.
_SCOPE_VIOLATION_TYPE = _try_import_scope_violation_error() or GatewayScopeViolationError

pytestmark = [pytest.mark.unit, pytest.mark.fast]


@dataclass(frozen=True, slots=True)
class _FakeContext:
    """Duck-typed stand-in for ``spec_kitty_tracker.context.LocalExecutionContext``."""

    actor: str
    repository: str
    team: str | None = None
    mission_id: str | None = None
    task_id: str | None = None


# ---------------------------------------------------------------------------
# Construction validation
# ---------------------------------------------------------------------------


def test_token_minimal_construction() -> None:
    token = TrackerGatewayToken(token="tok-1", actor="ivan", repository="spec-kitty")

    assert token.actor == "ivan"
    assert token.repository == "spec-kitty"
    assert token.team is None
    assert token.mission_id is None
    assert token.task_id is None


def test_token_is_frozen() -> None:
    token = TrackerGatewayToken(token="tok-1", actor="ivan", repository="spec-kitty")

    with pytest.raises(AttributeError):
        token.actor = "someone-else"  # type: ignore[misc]


@pytest.mark.parametrize("value", ["", "   "])
def test_token_rejects_empty_token(value: str) -> None:
    with pytest.raises(ValueError):
        TrackerGatewayToken(token=value, actor="ivan", repository="spec-kitty")


@pytest.mark.parametrize("value", ["", "   "])
def test_token_rejects_empty_actor(value: str) -> None:
    with pytest.raises(ValueError):
        TrackerGatewayToken(token="tok-1", actor=value, repository="spec-kitty")


@pytest.mark.parametrize("value", ["", "   "])
def test_token_rejects_empty_repository(value: str) -> None:
    with pytest.raises(ValueError):
        TrackerGatewayToken(token="tok-1", actor="ivan", repository=value)


@pytest.mark.parametrize("ttl", [0, -1, -300.0])
def test_token_rejects_non_positive_ttl(ttl: float) -> None:
    with pytest.raises(ValueError):
        TrackerGatewayToken(token="tok-1", actor="ivan", repository="spec-kitty", ttl_seconds=ttl)


# ---------------------------------------------------------------------------
# Freshness (TTL)
# ---------------------------------------------------------------------------


def test_token_is_fresh_before_expiry() -> None:
    token = TrackerGatewayToken(token="tok-1", actor="ivan", repository="spec-kitty", issued_at=1000.0, ttl_seconds=60.0)

    assert token.expires_at == 1060.0
    assert token.is_fresh(now=1059.999) is True


def test_token_is_not_fresh_at_or_after_expiry() -> None:
    token = TrackerGatewayToken(token="tok-1", actor="ivan", repository="spec-kitty", issued_at=1000.0, ttl_seconds=60.0)

    assert token.is_fresh(now=1060.0) is False
    assert token.is_fresh(now=1200.0) is False


# ---------------------------------------------------------------------------
# Scope coverage
# ---------------------------------------------------------------------------


def test_broad_token_covers_matching_actor_and_repository_regardless_of_mission_task() -> None:
    token = TrackerGatewayToken(token="tok-1", actor="ivan", repository="spec-kitty")

    assert token.covers(_FakeContext(actor="ivan", repository="spec-kitty")) is True
    assert token.covers(_FakeContext(actor="ivan", repository="spec-kitty", mission_id="m1", task_id="TRK-M1-04")) is True


@pytest.mark.parametrize(
    "context",
    [
        _FakeContext(actor="debbie", repository="spec-kitty"),
        _FakeContext(actor="ivan", repository="spec-kitty-tracker"),
        _FakeContext(actor="debbie", repository="spec-kitty-tracker"),
    ],
)
def test_token_never_covers_mismatched_actor_or_repository(context: _FakeContext) -> None:
    token = TrackerGatewayToken(token="tok-1", actor="ivan", repository="spec-kitty")

    assert token.covers(context) is False


def test_narrow_token_requires_matching_mission_id() -> None:
    token = TrackerGatewayToken(token="tok-1", actor="ivan", repository="spec-kitty", mission_id="m1")

    assert token.covers(_FakeContext(actor="ivan", repository="spec-kitty", mission_id="m1")) is True
    assert token.covers(_FakeContext(actor="ivan", repository="spec-kitty", mission_id="m2")) is False
    assert token.covers(_FakeContext(actor="ivan", repository="spec-kitty", mission_id=None)) is False


def test_narrow_token_requires_matching_task_id() -> None:
    token = TrackerGatewayToken(token="tok-1", actor="ivan", repository="spec-kitty", mission_id="m1", task_id="TRK-M1-04")

    assert token.covers(_FakeContext(actor="ivan", repository="spec-kitty", mission_id="m1", task_id="TRK-M1-04")) is True
    assert token.covers(_FakeContext(actor="ivan", repository="spec-kitty", mission_id="m1", task_id="TRK-M1-05")) is False


# ---------------------------------------------------------------------------
# GatewayCommandRunner
# ---------------------------------------------------------------------------


@dataclass
class _FakeInnerRunner:
    """Records every delegated call; returns a canned string."""

    output: str = "ok"
    calls: list[tuple[tuple[str, ...], str | None, _FakeContext | None]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.calls = []

    def run(self, command, *, cwd=None, context=None) -> str:
        self.calls.append((tuple(command), cwd, context))
        return self.output


def _token(**overrides) -> TrackerGatewayToken:
    defaults = {"token": "tok-1", "actor": "ivan", "repository": "spec-kitty", "issued_at": 1000.0, "ttl_seconds": 60.0}
    defaults.update(overrides)
    return TrackerGatewayToken(**defaults)


def _ctx(**overrides) -> _FakeContext:
    defaults = {"actor": "ivan", "repository": "spec-kitty"}
    defaults.update(overrides)
    return _FakeContext(**defaults)


def test_runner_delegates_an_allowed_command_to_the_inner_runner() -> None:
    inner = _FakeInnerRunner(output="bd-output")
    runner = GatewayCommandRunner(_token(), inner=inner, clock=lambda: 1001.0)
    ctx = _ctx()

    result = runner.run(["bd", "--json", "list"], cwd="/repo", context=ctx)

    assert result == "bd-output"
    assert inner.calls == [(("bd", "--json", "list"), "/repo", ctx)]


def test_runner_denies_when_token_is_expired() -> None:
    inner = _FakeInnerRunner()
    runner = GatewayCommandRunner(_token(ttl_seconds=60.0), inner=inner, clock=lambda: 1060.0)

    with pytest.raises(GatewayAuthorizationError):
        runner.run(["bd", "--json", "list"], context=_ctx())

    assert inner.calls == []


def test_runner_denies_when_context_is_missing() -> None:
    inner = _FakeInnerRunner()
    runner = GatewayCommandRunner(_token(), inner=inner, clock=lambda: 1001.0)

    with pytest.raises(GatewayAuthorizationError):
        runner.run(["bd", "--json", "list"], context=None)

    assert inner.calls == []


def test_runner_raises_scope_violation_for_mismatched_context() -> None:
    inner = _FakeInnerRunner()
    runner = GatewayCommandRunner(_token(), inner=inner, clock=lambda: 1001.0)

    with pytest.raises(_SCOPE_VIOLATION_TYPE) as exc_info:
        runner.run(["bd", "--json", "list"], context=_ctx(actor="debbie"))

    assert "ivan" in exc_info.value.expected_scope
    assert "debbie" in exc_info.value.actual_scope
    assert inner.calls == []


def test_scope_violation_falls_back_to_local_error_type_when_tracker_package_lacks_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the installed spec_kitty_tracker predates ScopeViolationError (0.4.x),
    the gateway still fails closed with its own equivalent error type instead of
    raising an unrelated ImportError."""
    import specify_cli.tracker.gateway as gateway_module

    monkeypatch.setattr(gateway_module, "_try_import_scope_violation_error", lambda: None)
    inner = _FakeInnerRunner()
    runner = GatewayCommandRunner(_token(), inner=inner, clock=lambda: 1001.0)

    with pytest.raises(gateway_module.GatewayScopeViolationError):
        runner.run(["bd", "--json", "list"], context=_ctx(repository="other-repo"))


# ---------------------------------------------------------------------------
# _canonicalize_argv -- surface-syntax normalization (Renata REJECT fix)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        # Split two-token form is already canonical -- a no-op.
        (["update", "BD-1", "--status", "closed"], ["update", "BD-1", "--status", "closed"]),
        # Glued long-flag equals form splits into the two-token shape.
        (["update", "BD-1", "--status=closed"], ["update", "BD-1", "--status", "closed"]),
        # Glued short-flag equals form splits too -- generically, for ANY
        # single-character short flag, not just a hardcoded "known" set.
        (["update", "BD-1", "-s=closed"], ["update", "BD-1", "-s", "closed"]),
        (["update", "BD-1", "-a=ivan"], ["update", "BD-1", "-a", "ivan"]),
        (["update", "BD-1", "--assignee=ivan"], ["update", "BD-1", "--assignee", "ivan"]),
        # Split short-flag form is already canonical -- a no-op (no alias
        # rewrite: the deny check names both spellings explicitly instead).
        (["update", "BD-1", "-s", "closed"], ["update", "BD-1", "-s", "closed"]),
        (["update", "BD-1", "-a", "ivan"], ["update", "BD-1", "-a", "ivan"]),
        # An unrelated flag/value with '=' in the value is left alone apart
        # from the split -- canonicalization never touches value content.
        (["update", "BD-1", "--notes=a=b"], ["update", "BD-1", "--notes", "a=b"]),
        # Bare tokens with no '=' pass through untouched.
        (["bd", "--json", "list"], ["bd", "--json", "list"]),
    ],
)
def test_canonicalize_argv(argv: list[str], expected: list[str]) -> None:
    assert _canonicalize_argv(argv) == expected


# ---------------------------------------------------------------------------
# _extract_subcommand_path -- allow-list matching surface (TRK-M1-04 redesign)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        # No global flags: subcommand is the first token after the executable.
        (["bd", "list"], ("list",)),
        (["bd", "close", "BD-1"], ("close",)),
        # A single boolean global flag is skipped.
        (["bd", "--json", "list"], ("list",)),
        # A value-taking global flag consumes its value token too.
        (["bd", "--actor", "ivan", "list"], ("list",)),
        (["bd", "-C", "/some/repo", "list"], ("list",)),
        (["bd", "--db", "/x.db", "--json", "list"], ("list",)),
        # Multiple global flags stack in any mix of boolean/value-taking.
        (["bd", "--json", "--actor", "ivan", "-q", "close", "BD-1"], ("close",)),
        # A compound parent's second token extends the path...
        (["bd", "dep", "add", "BD-1", "BD-2"], ("dep", "add")),
        (["bd", "--json", "comments", "add", "BD-1", "hi"], ("comments", "add")),
        # ...but only when a non-flag second token is actually present.
        (["bd", "dep", "--blocks", "BD-2"], ("dep",)),
        (["bd", "dep"], ("dep",)),
        # A non-compound parent never gets a second token, regardless of it.
        (["bd", "gate", "resolve", "GATE-1"], ("gate",)),
        # `--` stops flag-skipping immediately, so a subcommand cannot hide
        # behind it as if it were a global flag's value.
        (["bd", "--", "close", "BD-1"], ("close",)),
        # No subcommand token at all.
        (["bd", "--json"], ()),
        (["bd"], ()),
    ],
)
def test_extract_subcommand_path(argv: list[str], expected: tuple[str, ...]) -> None:
    assert _extract_subcommand_path(argv) == expected


@pytest.mark.parametrize(
    "command",
    [
        # Direct close-equivalents (previously a deny-list entry; now
        # simply not on the allow-list).
        ["bd", "--json", "close", "BD-1"],
        ["bd", "--json", "done", "BD-1"],  # bd close --help: "Aliases: close, done"
        ["bd", "--json", "assign", "BD-1", "ivan"],
        ["bd", "--json", "reopen", "BD-1"],
        ["bd", "--json", "delete", "BD-1", "--force"],
        # bd 1.2.2 has no top-level `approve`/`release` subcommand -- denied
        # anyway by default-deny, forward-compatible against a future bd
        # release that adds one, with no enumeration required.
        ["bd", "--json", "approve", "BD-1"],
        ["bd", "--json", "release", "BD-1"],
        # Close-equivalents discovered via `bd --help`/`bd <cmd> --help`
        # (Renata REJECT, TRK-M1-04): `bd gate resolve --help` documents
        # itself verbatim as "equivalent to 'bd close <gate-id>'";
        # `bd epic close-eligible` bulk-closes epics; `bd supersede --with`/
        # `bd duplicate --of`/`bd duplicates --auto-merge` auto-close their
        # target; `bd merge-slot release` releases a lifecycle primitive;
        # `bd config set` can rewrite the very status vocabulary a value
        # blacklist would have needed to enumerate.
        ["bd", "--json", "gate", "resolve", "GATE-1"],
        ["bd", "--json", "epic", "close-eligible"],
        ["bd", "--json", "supersede", "BD-1", "--with", "BD-2"],
        ["bd", "--json", "duplicate", "BD-1", "--of", "BD-2"],
        ["bd", "--json", "duplicates", "--auto-merge"],
        ["bd", "--json", "merge-slot", "release"],
        ["bd", "--json", "config", "set", "status.custom", "merged"],
        # A bare `bd dep --blocks` (no explicit `add`/`remove` sub-token) is
        # a write shorthand the tracker adapter never issues -- the
        # one-token path `("dep",)` alone is not allow-listed.
        ["bd", "--json", "dep", "BD-1", "--blocks", "BD-2"],
        # Deny-by-default on a subcommand this module has never heard of --
        # the whole point of an allow-list over a deny-list.
        ["bd", "--json", "flurbnicate", "BD-1"],
        # Self-claim (sets assignee AND status atomically).
        ["bd", "--json", "update", "BD-1", "--claim"],
        # `create --assignee`: BeadsConnector.create_issue never emits this
        # itself, but the invariant holds even for a raw-argv bypass.
        ["bd", "--json", "create", "title", "--assignee", "ivan"],
        ["bd", "--json", "create", "title", "-a", "ivan"],
        # `update --status`/`--assignee`: banned as bare flag names,
        # regardless of value -- including a value that looks non-terminal.
        # `bd`'s done-category statuses are user-configurable
        # (`bd config set status.custom ...`), so no finite status-*value*
        # list could ever be complete; only banning the flag itself can be.
        ["bd", "--json", "update", "BD-1", "--status", "closed"],
        ["bd", "--json", "update", "BD-1", "--status", "in_progress"],
        ["bd", "--json", "update", "BD-1", "--status", "merged"],  # hypothetical custom status
        ["bd", "--json", "update", "BD-1", "--status=closed"],  # glued long flag
        ["bd", "--json", "update", "BD-1", "-s", "closed"],  # short flag, split form
        ["bd", "--json", "update", "BD-1", "-s=closed"],  # short flag, glued form
        ["bd", "--json", "update", "BD-1", "-a", "ivan"],  # short flag, split form
        ["bd", "--json", "update", "BD-1", "--assignee=ivan"],  # glued long flag
        ["bd", "--json", "update", "BD-1", "-a=ivan"],  # short flag, glued form
        # Global flags before the subcommand must not shift a forbidden
        # subcommand token out of view.
        ["bd", "--actor", "ivan", "--json", "close", "BD-1"],
        ["bd", "-C", "/some/repo", "close", "BD-1"],
    ],
)
def test_runner_refuses_operations_not_on_the_allow_list(command: list[str]) -> None:
    inner = _FakeInnerRunner()
    runner = GatewayCommandRunner(_token(), inner=inner, clock=lambda: 1001.0)

    with pytest.raises(GatewayForbiddenOperationError):
        runner.run(command, context=_ctx())

    assert inner.calls == []


@pytest.mark.parametrize(
    "command",
    [
        ["bd", "--json", "list"],
        ["bd", "--json", "list", "--status", "open"],
        ["bd", "--json", "show", "BD-1"],
        ["bd", "--json", "create", "New issue", "--type", "task", "--priority", "2"],
        ["bd", "--json", "update", "BD-1", "--title", "Renamed"],
        ["bd", "--json", "update", "BD-1", "--priority", "1", "--parent", "BD-0"],
        ["bd", "--json", "dep", "add", "BD-1", "BD-2", "--type", "blocks"],
        ["bd", "--json", "comments", "add", "BD-1", "note text"],
        # Global flags preceding an allowed subcommand are skipped correctly.
        ["bd", "--actor", "ivan", "--json", "list"],
        ["bd", "-C", "/some/repo", "show", "BD-1"],
    ],
)
def test_runner_allows_operations_on_the_allow_list(command: list[str]) -> None:
    inner = _FakeInnerRunner()
    runner = GatewayCommandRunner(_token(), inner=inner, clock=lambda: 1001.0)

    result = runner.run(command, context=_ctx())

    assert result == "ok"
    assert len(inner.calls) == 1


def test_runner_denies_the_forbidden_command_every_time_it_is_attempted() -> None:
    """Idempotency/race requirement: denial is a pure function of the command,
    never a one-shot gate that a retried/duplicate attempt could slip past."""
    inner = _FakeInnerRunner()
    runner = GatewayCommandRunner(_token(), inner=inner, clock=lambda: 1001.0)
    command = ["bd", "--json", "close", "BD-1"]

    for _ in range(3):
        with pytest.raises(GatewayForbiddenOperationError):
            runner.run(command, context=_ctx())

    assert inner.calls == []


def test_runner_reevaluates_scope_independently_per_call() -> None:
    """No cross-call caching: a runner that permits one context must still
    independently deny the next call whose context is out of scope."""
    inner = _FakeInnerRunner()
    runner = GatewayCommandRunner(_token(), inner=inner, clock=lambda: 1001.0)

    runner.run(["bd", "--json", "list"], context=_ctx())
    with pytest.raises(_SCOPE_VIOLATION_TYPE):
        runner.run(["bd", "--json", "list"], context=_ctx(repository="other-repo"))

    assert len(inner.calls) == 1


# ---------------------------------------------------------------------------
# authority_report / record_conflicts -- "exposes authority/freshness/conflicts"
# ---------------------------------------------------------------------------


def test_authority_report_reflects_a_fresh_authorized_token() -> None:
    runner = GatewayCommandRunner(_token(mission_id="m1", task_id="TRK-M1-04"), inner=_FakeInnerRunner(), clock=lambda: 1001.0)

    report = runner.authority_report(_ctx(mission_id="m1", task_id="TRK-M1-04"))

    assert report.authorized is True
    assert report.fresh is True
    assert report.actor == "ivan"
    assert report.repository == "spec-kitty"
    assert report.mission_id == "m1"
    assert report.task_id == "TRK-M1-04"
    assert report.denied_operations == ()
    assert report.conflicts == ()


def test_authority_report_reflects_an_expired_token_as_unauthorized() -> None:
    runner = GatewayCommandRunner(_token(ttl_seconds=60.0), inner=_FakeInnerRunner(), clock=lambda: 1060.0)

    report = runner.authority_report()

    assert report.fresh is False
    assert report.authorized is False


def test_authority_report_reflects_an_out_of_scope_context_as_unauthorized_but_fresh() -> None:
    runner = GatewayCommandRunner(_token(), inner=_FakeInnerRunner(), clock=lambda: 1001.0)

    report = runner.authority_report(_ctx(repository="other-repo"))

    assert report.fresh is True
    assert report.authorized is False


def test_authority_report_with_no_context_reports_token_authority_alone() -> None:
    runner = GatewayCommandRunner(_token(), inner=_FakeInnerRunner(), clock=lambda: 1001.0)

    report = runner.authority_report()

    assert report.authorized is True
    assert report.fresh is True


def test_authority_report_accumulates_denied_operations_up_to_the_history_limit() -> None:
    runner = GatewayCommandRunner(_token(), inner=_FakeInnerRunner(), clock=lambda: 1001.0, history_limit=2)

    for command in (
        ["bd", "--json", "close", "BD-1"],
        ["bd", "--json", "assign", "BD-1", "ivan"],
        ["bd", "--json", "approve", "BD-1"],
    ):
        with pytest.raises(GatewayForbiddenOperationError):
            runner.run(command, context=_ctx())

    report = runner.authority_report()

    # Verifies truncation to history_limit=2 despite 3 denials; the exact denial
    # content is asserted separately below.
    assert len(report.denied_operations) == 2
    assert "subcommand 'assign' is not on the tracker gateway allow-list" in report.denied_operations[0]
    assert "subcommand 'approve' is not on the tracker gateway allow-list" in report.denied_operations[1]


def test_record_conflicts_is_surfaced_by_authority_report() -> None:
    runner = GatewayCommandRunner(_token(), inner=_FakeInnerRunner(), clock=lambda: 1001.0)

    runner.record_conflicts(["title conflict on BD-1", "status conflict on BD-2"])
    report = runner.authority_report()

    assert report.conflicts == ("title conflict on BD-1", "status conflict on BD-2")


def test_record_conflicts_replaces_rather_than_accumulates() -> None:
    runner = GatewayCommandRunner(_token(), inner=_FakeInnerRunner(), clock=lambda: 1001.0)

    runner.record_conflicts(["first sync's conflict"])
    runner.record_conflicts(["second sync's conflict"])
    report = runner.authority_report()

    assert report.conflicts == ("second sync's conflict",)


def test_token_property_returns_the_configured_token() -> None:
    token = _token()
    runner = GatewayCommandRunner(token, inner=_FakeInnerRunner(), clock=lambda: 1001.0)

    assert runner.token is token


# ---------------------------------------------------------------------------
# build_gateway_beads_connector -- real BeadsConnector wiring
#
# Requires spec_kitty_tracker>=0.5 (spec_kitty_tracker.context.LocalExecutionContext,
# landed by TRK-M1-02/03 but not yet published to PyPI at the time this WP
# was written -- see docs/development/how-to/local-overrides.md Pattern A).
# Each test that actually needs the real symbol calls
# ``_require_gateway_tracker()`` first and skips cleanly (rather than
# failing) against the currently-published 0.4.x line, so the rest of this
# file's tests -- and this file's collection itself -- stay green in a
# clean-install (``uv sync --frozen``) environment.
# ---------------------------------------------------------------------------


def _require_gateway_tracker() -> None:
    pytest.importorskip("spec_kitty_tracker.context", reason="TRK-M1-04 gateway wiring needs spec-kitty-tracker>=0.5")


def test_build_gateway_beads_connector_wires_token_scope_into_the_execution_context() -> None:
    _require_gateway_tracker()
    from spec_kitty_tracker import BeadsConnector

    token = _token(team="team-kitty", mission_id="m1", task_id="TRK-M1-04")
    connector, gateway_runner = build_gateway_beads_connector(token=token, workspace="beads")

    assert isinstance(connector, BeadsConnector)
    assert gateway_runner.token is token
    context = connector.config.context
    assert context is not None
    assert context.actor == "ivan"
    assert context.repository == "spec-kitty"
    assert context.team == "team-kitty"
    assert context.mission_id == "m1"
    assert context.task_id == "TRK-M1-04"


async def test_build_gateway_beads_connector_round_trips_list_issues_through_the_gateway() -> None:
    _require_gateway_tracker()
    import json

    inner = _FakeInnerRunner(output=json.dumps([{"id": "BD-1", "title": "Do the thing", "status": "open", "issue_type": "task", "priority": 2}]))
    token = _token()
    connector, gateway_runner = build_gateway_beads_connector(token=token, workspace="beads", runner=GatewayCommandRunner(token, inner=inner, clock=lambda: 1001.0))

    page = await connector.list_issues(updated_since=None, cursor=None, limit=10, filters=None)

    assert [issue.ref.id for issue in page.items] == ["BD-1"]
    # the gateway attributed the call to the token's scope, not an unscoped default:
    ((_command, _cwd, call_context),) = inner.calls
    assert call_context.actor == "ivan"
    assert call_context.repository == "spec-kitty"
    assert gateway_runner is connector._runner


async def test_build_gateway_beads_connector_still_denies_a_terminal_transition_at_the_connector_layer() -> None:
    """BeadsConnector's own A5 guard (landed TRK-M1-03) fires before the gateway
    ever sees a command -- the two enforcement layers compose, they don't race."""
    _require_gateway_tracker()
    from spec_kitty_tracker import CapabilityNotSupportedError, CanonicalStatus
    from spec_kitty_tracker.models import ExternalRef

    inner = _FakeInnerRunner()
    token = _token()
    connector, _gateway_runner = build_gateway_beads_connector(
        token=token, workspace="beads", runner=GatewayCommandRunner(token, inner=inner, clock=lambda: 1001.0)
    )
    ref = ExternalRef(system="beads", workspace="beads", id="BD-1")

    with pytest.raises(CapabilityNotSupportedError):
        await connector.update_issue(ref, {"status": CanonicalStatus.DONE}, idempotency_key=None)

    assert inner.calls == []


async def test_build_gateway_beads_connector_gateway_still_denies_a_raw_bypass_of_the_connector() -> None:
    """Independent of BeadsConnector's own A5 guard: a caller that skips the
    connector and hands the gateway raw argv directly is still refused."""
    _require_gateway_tracker()
    inner = _FakeInnerRunner()
    token = _token()
    _connector, gateway_runner = build_gateway_beads_connector(
        token=token, workspace="beads", runner=GatewayCommandRunner(token, inner=inner, clock=lambda: 1001.0)
    )

    with pytest.raises(GatewayForbiddenOperationError):
        gateway_runner.run(["bd", "--json", "close", "BD-1"], context=_connector_context(token))

    assert inner.calls == []


def _connector_context(token: TrackerGatewayToken):
    from spec_kitty_tracker.context import LocalExecutionContext

    return LocalExecutionContext(actor=token.actor, repository=token.repository)


def test_build_gateway_beads_connector_raises_when_tracker_predates_local_execution_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import specify_cli.tracker.gateway as gateway_module

    monkeypatch.setattr(gateway_module, "_try_import_gateway_beads_types", lambda: None)

    with pytest.raises(TrackerGatewayUnavailableError):
        build_gateway_beads_connector(token=_token(), workspace="beads")
