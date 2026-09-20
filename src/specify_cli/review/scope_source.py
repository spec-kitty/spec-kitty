"""``ScopeSource`` port + its portable implementation (WP02, mission
``doctrine-controlled-transition-gates-01KY51Z7``, epic #2535 half A).

``ScopeSource`` is the injectable seam that lets the pre-review gate become
layout-agnostic: everything that varies with a repo's *shape* — how to run
its tests, how a changed file maps to a test target, how a completed run's
output is parsed into per-failure identities — lives behind this
``typing.Protocol``, mirroring ``OrgDoctrineSource``
(:mod:`specify_cli.doctrine.sources.protocol`): ``@runtime_checkable``, and
methods that never raise for environmental problems (surfaced via return
value instead).

**``changed_files`` is deliberately absent from the port** (FR-001). It is
the shared canonical merge-base+diff SSOT
(``core.vcs.git.merge_base_changed_files``, surfaced via
``tasks_move_task.py``), passed *into* the gate rather than re-derived per
implementation, so implementations cannot diverge on "which
files changed". Do not "helpfully" add a ``changed_files`` method here — that
is the exact drift this port design forbids.

**Import-cycle guard.** WP03 makes ``pre_review_gate.py`` and ``baseline.py``
import ``ScopeSource`` back from this module — a two-way cycle if this
module imports them at module scope. ``BaselineFailure`` is therefore
referenced only under ``TYPE_CHECKING`` (annotations are lazy strings via
``from __future__ import annotations``, so this costs nothing at runtime and
never executes at import time); ``_parse_junit_xml``, ``_get_test_command``,
and ``GateAuthoritiesUnavailable`` are imported LAZILY inside the method
bodies that need them, never at module top. Those types stay in their
current home (``baseline.py`` / ``pre_review_gate.py``) — they are not
duplicated here.
"""

from __future__ import annotations

import shlex
import tempfile
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, TypeGuard, runtime_checkable

if TYPE_CHECKING:
    from specify_cli.review.baseline import BaselineFailure

# ``resolve_scope_source`` (FR-003/FR-014, WP02) is the selection-wiring
# authority: repos use their configured ``review.test_command`` when present.
# With no configured command, the source's ``test_command()`` returns ``None``
# and the gate emits the normal visible ``NO_COVERAGE`` warning. The former
# Spec-Kitty-only
# ``GateCoverageScopeSource`` path depended on deleted GitHub Actions workflow
# files and was retired by issue #380.
__all__ = [
    "UNKNOWN_SOURCE_IDENTITY",
    "DeclaredCommandScopeSource",
    "FileScopeBreakdown",
    "RawRunResult",
    "ScopeBreakdownSource",
    "ScopeSource",
    "empty_scope_is_coverage_gap",
    "exposes_scope_breakdown",
    "resolve_scope_source",
    "scope_source_identity",
]

#: Sentinel ``source_identity`` for a baseline artifact with no known capture
#: source — a straddling-upgrade artifact written before the field existed, or
#: a sentinel capture. The head-side ``SOURCE_MISMATCH`` check treats it as
#: "not comparable, but not a mismatch" and degrades to ``UNVERIFIED_BASELINE``.
#: One named constant so the writer (``baseline.py``) and the reader
#: (``pre_review_gate.py``) cannot drift on a bare string literal.
UNKNOWN_SOURCE_IDENTITY = "unknown"


@dataclass(frozen=True)
class RawRunResult:
    """The UNPARSED product of running :meth:`ScopeSource.test_command`.

    This is deliberately NOT ``pre_review_gate.HeadRunResult`` — that type is
    already-**parsed** (it carries ``current_failures`` and has no raw-output
    field), so feeding it to :meth:`ScopeSource.parse_results` would leave the
    portable implementation nothing to parse and it would collapse to
    ``NO_COVERAGE`` (the exact decorative-gate regression this mission
    kills). The engine builds a parsed result FROM ``parse_results(raw)``'s
    output, never the other way round.
    """

    returncode: int
    stdout: str
    stderr: str
    output_artifact_path: Path | None = None


@runtime_checkable
class ScopeSource(Protocol):
    """The repo-shape-varying concerns behind the pre-review gate.

    Covers ONLY what varies by repo shape. "Which files changed" is NOT on
    the port (FR-001) — see the module docstring.

    Port-wide invariant: implementations never raise for environmental
    problems — they surface them via return value (the ``OrgDoctrineSource``
    discipline). ``test_command() -> None`` is the no-config signal, not an
    exception.
    """

    def test_command(self) -> list[str] | None:
        """The runnable argv the gate executes at head.

        ``None`` means the repo declares no test command -> the gate is a
        visible ``NO_COVERAGE`` warn (FR-012), never a crash and never a
        silent green.
        """
        ...

    def file_to_scope(self, path: str) -> tuple[str, ...]:
        """Map ONE changed file to zero-or-more test targets.

        ``()`` means "contributes no scope" — not an error. Called once per
        element of the shared ``changed_files`` input (never invented here).
        """
        ...

    def parse_results(self, raw: RawRunResult) -> tuple[BaselineFailure, ...]:
        """Turn a completed (unparsed) head run into per-failure identities.

        Exit code alone is insufficient identity for a baseline diff — the
        parser MUST yield per-failure identities so the caller can classify
        pre-existing vs. new failures. A non-zero exit with unparseable
        output counts the whole run as failing (surfaced, never swallowed).
        """
        ...

    def parse_mode(self, raw: RawRunResult) -> str:
        """The parse-mode this source's OWN :meth:`parse_results` applied to ``raw``.

        The single source-owned authority (T007, FR-009) for "which branch did
        parse_results take" — :func:`scope_source_identity` calls this rather
        than re-inspecting ``raw`` a second time, so the decision has exactly
        one owner per source. Vocabulary: ``"junit_xml"`` / ``"text"`` /
        ``"none"``.
        """
        ...


@dataclass(frozen=True)
class FileScopeBreakdown:
    """One changed file's FULL census contribution, not just its flat targets.

    ``file_to_scope`` collapses this to ``test_targets`` alone; a
    census-narrowing source additionally exposes WHICH dorny shard groups /
    composite dirs a file landed in, so the inverted transition-gate hook can
    rebuild a :class:`~specify_cli.review.pre_review_gate.ScopeResult` whose
    ``matched_shard_groups`` / ``matched_composite_dirs`` /
    ``empty_cone_composite_dirs`` metadata is byte-identical to the incumbent
    ``derive_test_scope`` (NFR-001). ``contributes_scope`` is ``False`` when the
    file matched no *focused* (non-catch-all) group at all — the signal the
    engine folds into ``ScopeResult.excluded_scope_files``.
    """

    test_targets: tuple[str, ...] = ()
    matched_shard_groups: tuple[str, ...] = ()
    matched_composite_dirs: tuple[str, ...] = ()
    empty_cone_composite_dirs: tuple[str, ...] = ()
    contributes_scope: bool = True


@runtime_checkable
class ScopeBreakdownSource(Protocol):
    """Optional :class:`ScopeSource` refinement for narrowing implementations.

    The built-in source deliberately does not implement this. It runs the
    whole declared command instead of narrowing by changed file, so an empty
    per-file scope is not a coverage gap.
    """

    def scope_breakdown(self, path: str) -> FileScopeBreakdown:
        """Map ONE changed file to its full census breakdown (never raises)."""
        ...


# ---------------------------------------------------------------------------
# Two independent predicates (FR-005/FR-006, T008/T009)
# ---------------------------------------------------------------------------


def exposes_scope_breakdown(source: ScopeSource) -> TypeGuard[ScopeBreakdownSource]:
    """Capability signal: does ``source`` expose the breakdown refinement?

    Backs ``isinstance(source, ScopeBreakdownSource)`` — structural presence
    of :meth:`ScopeBreakdownSource.scope_breakdown`. DISTINCT from
    :func:`empty_scope_is_coverage_gap` (T008 un-weld, carla-2 guard): a
    source can implement ``scope_breakdown`` without opting into the
    empty-scope-is-a-gap policy, and vice versa.

    A :class:`~typing.TypeGuard` (not a bare ``bool``): the capability check IS
    a type refinement, so a caller that gates on it narrows ``source`` to
    :class:`ScopeBreakdownSource` and can reach :meth:`~ScopeBreakdownSource.scope_breakdown`
    without a cast — the un-weld from :func:`empty_scope_is_coverage_gap` is
    unaffected (that predicate stays a plain policy ``bool``).
    """
    return isinstance(source, ScopeBreakdownSource)


def empty_scope_is_coverage_gap(source: ScopeSource) -> bool:
    """Policy signal: does an EMPTY per-file scope from ``source`` mean a coverage gap?

    Backs the source's own ``treats_empty_scope_as_coverage_gap`` ``ClassVar``
    marker (default ``False`` when absent) — a signal DISTINCT from
    :func:`exposes_scope_breakdown` (T008 un-weld, carla-2 guard). Reading the
    same ``isinstance`` check for both predicates is the exact failure mode
    this un-weld retires.
    """
    return bool(getattr(source, "treats_empty_scope_as_coverage_gap", False))


# ---------------------------------------------------------------------------
# DeclaredCommandScopeSource — portable, baseline-relative (FR-003/FR-010)
# ---------------------------------------------------------------------------

_FAILURE_LINE_PREFIX = "FAIL "
_UNPARSEABLE_FAILURE_TEST_ID = "<declared-command>"
_FAILURE_MESSAGE_MAX_CHARS = 200


def _parse_declared_command_failure_lines(text: str) -> tuple[BaselineFailure, ...]:
    """Extract per-failure identities from a ``FAIL <test>[: <message>]``-shaped stream.

    A small, non-pytest, non-JUnit output convention: any line starting with
    ``FAIL `` is one failing test identity. This is the "genuinely
    non-pytest-shaped" parser NFR-004 requires — it never assumes pytest or
    JUnit.
    """
    from specify_cli.review.baseline import BaselineFailure

    failures: list[BaselineFailure] = []
    for line in text.splitlines():
        if not line.startswith(_FAILURE_LINE_PREFIX):
            continue
        remainder = line[len(_FAILURE_LINE_PREFIX) :]
        test_name, _, message = remainder.partition(":")
        error = (message.strip() or "failed")[:_FAILURE_MESSAGE_MAX_CHARS]
        failures.append(BaselineFailure(test=test_name.strip(), error=error, file="unknown"))
    return tuple(failures)


def _whole_run_failure(raw: RawRunResult) -> BaselineFailure:
    """A single synthetic identity representing "the whole run failed, unparseably".

    Exit code alone is insufficient identity for a baseline diff, but a
    non-zero exit with no parseable per-test failures must still be
    surfaced as failing — never silently swallowed into ``()``.
    """
    from specify_cli.review.baseline import BaselineFailure

    tail_source = raw.stderr or raw.stdout
    tail_lines = tail_source.strip().splitlines()
    summary = tail_lines[-1][:_FAILURE_MESSAGE_MAX_CHARS] if tail_lines else f"exit code {raw.returncode}"
    return BaselineFailure(test=_UNPARSEABLE_FAILURE_TEST_ID, error=summary, file="unknown")


@dataclass(frozen=True)
class DeclaredCommandScopeSource:
    """Gates a non-pytest / non-``src/specify_cli/`` repo by its own declared command.

    ``file_to_scope`` always returns ``()`` — no per-file narrowing; the
    declared command runs the whole suite (layout-agnostic). ``parse_results``
    yields per-failure identities so a failing suite is a blocking-capable
    ``NEW_FAILURES`` verdict, never a false ``ANY_FAILURES``-shaped collapse
    (forbidden by NFR-004): a ``returncode != 0`` alone is never treated as
    the verdict — pre-existing baseline failures must not block.
    """

    repo_root: Path

    @cached_property
    def _output_file(self) -> Path:
        """This instance's OWN artifact path for a configured ``{output_file}``
        placeholder (issue #3612 fix).

        Computed once per instance (cached) and used both by
        :meth:`test_command` (substituted into the rendered command) and by
        :meth:`_resolved_artifact_path` (read back after the run) — the SAME
        instance drives one capture-or-head run end to end, so there is no
        risk of the two disagreeing. Lives in a fresh private tempdir so a
        baseline capture and a concurrent head run (each its own
        ``DeclaredCommandScopeSource`` instance) never collide on the same
        path, regardless of which flag name the operator's command uses for
        its own output-file argument (``--junitxml=``, ``--report=``, ...) —
        unlike the prior argv-sniffing (:func:`_extract_junit_output_path`),
        which only ever recognized a literal ``--junitxml=`` prefix.

        Note: accessing this property creates the tempdir immediately (even
        if the run never writes into it) — a small, deliberately-accepted
        per-run leak rather than complicating this frozen dataclass with
        explicit teardown; the OS temp directory is reclaimed independently
        of this process. Known second caller: the #3821 declaration probe
        (``tasks_move_task._mt_pre_review_gate_declared``) builds a throwaway
        instance whose ``test_command()`` render pays this same cost once per
        ``for_review`` transition in a declared repo — accepted explicitly in
        that probe's docstring rather than re-deriving config semantics
        outside the single FR-011 authority.
        """
        return Path(tempfile.mkdtemp(prefix="spec-kitty-declared-cmd-")) / "output.xml"

    def test_command(self) -> list[str] | None:
        """The runnable, fully-substituted, shell-ready argv — or ``None`` when
        ``review.test_command`` is unset (FR-012) or malformed (unbalanced
        quoting).

        Reads the same config surface ``baseline._get_test_command`` reads
        (FR-011) — no new config key is invented.

        Issue #3612 fix: previously this returned a bare
        ``shlex.split(command_template)`` — a configured ``{output_file}``
        placeholder was never substituted (stayed a literal 8-character
        token), and ``$VAR``/``~`` in the template were never shell-expanded
        (no shell was ever involved in running it). Both are fixed together
        via :func:`build_shell_command_with_substitutions`, which renders
        ``{output_file}`` -> :attr:`_output_file` through the same
        quote-aware scanner ``run_configured_command_template`` uses
        (``configured_command.py``), then wraps the result in ``["sh",
        "-c", ...]`` so the configured command gets real POSIX shell
        semantics — matching what :func:`run_configured_command` already
        gives every OTHER configured-command consumer in this codebase.
        Falls back to ``None`` (visible ``NO_COVERAGE``, never a crash — the
        port's own invariant) when the template is malformed or the platform
        has no POSIX shell to hand this argv to.
        """
        from specify_cli.configured_command import (
            ConfiguredCommandUnsupported,
            build_shell_command_with_substitutions,
        )
        from specify_cli.review.baseline import _get_test_command

        command_template, _output_format = _get_test_command(self.repo_root)
        if not command_template:
            return None
        try:
            shlex.split(command_template)
            return build_shell_command_with_substitutions(command_template, {"output_file": self._output_file})
        except (ValueError, ConfiguredCommandUnsupported):
            return None

    def file_to_scope(self, _path: str) -> tuple[str, ...]:
        """Always ``()`` — no per-file narrowing (deliberately not #2330).

        The argument is unused by design: this implementation never narrows
        by file (the declared command runs the whole suite), so the
        parameter is intentionally underscore-prefixed rather than dropped —
        positional calls through the ``ScopeSource`` port are unaffected.
        """
        return ()

    def _resolved_artifact_path(self, raw: RawRunResult) -> Path | None:
        """The JUnit artifact for THIS run, or ``None`` (issue #3612).

        Prefers ``raw.output_artifact_path`` — the runner's own argv-sniffing
        (:func:`_extract_junit_output_path`), which still recognizes a
        literal ``--junitxml=<path>`` token, and is also how a caller
        (including existing direct-injection tests) can hand this source a
        precomputed artifact without going through :meth:`test_command` at
        all. Falls back to :attr:`_output_file` — THIS instance's own
        ``{output_file}`` substitution target — for the case the sniffing
        cannot see into: :meth:`test_command` now wraps the rendered command
        in ``["sh", "-c", ...]`` (issue #3612's shell-expansion fix), so no
        individual argv element starts with ``--junitxml=`` any more even
        when the rendered shell string contains it. Without this fallback, a
        real declared-command run that DID produce its artifact would
        misreport ``"text"`` mode purely because sniffing can no longer
        reach into the wrapped shell string.
        """
        if raw.output_artifact_path is not None and raw.output_artifact_path.exists():
            return raw.output_artifact_path
        if self._output_file.exists():
            return self._output_file
        return None

    def parse_mode(self, raw: RawRunResult) -> str:
        """The parse *strategy* this source uses — a STABLE, outcome-invariant
        identity component (T007 + FR-009).

        Two strategies only: a resolved JUnit artifact is parsed as JUnit XML
        (``"junit_xml"``); otherwise the declared command's textual output is
        parsed via the ``FAIL <test>`` convention (``"text"``). The label names
        HOW this source parses, NOT whether THIS run happened to find failures.

        A clean text-convention run is therefore still ``"text"`` (not a former
        third ``"none"`` value) — so :func:`scope_source_identity` stays
        IDENTICAL across a green baseline and a failing head of the same
        configured source. That stability is load-bearing: the ``SOURCE_MISMATCH``
        check (``pre_review_gate._evaluate_via_scope_source``) compares baseline
        vs head identity, and an outcome-dependent label made a green
        (``"none"``) baseline look "not comparable" to a failing (``"text"``)
        head — silently failing the gate open on the single case a regression
        gate exists to catch. The empty-vs-nonzero-exit distinction is a
        failure-EXTRACTION concern owned by :meth:`parse_results`, never the
        strategy label. (Mission scopesource-gate-followup landing fold.)
        """
        return "junit_xml" if self._resolved_artifact_path(raw) is not None else "text"

    def parse_results(self, raw: RawRunResult) -> tuple[BaselineFailure, ...]:
        """Parse the declared command's own output into per-failure identities.

        Dispatches through :meth:`parse_mode`'s strategy decision (T007
        single-authority): a JUnit artifact is parsed as JUnit XML; otherwise
        the text-convention (``FAIL <test>``) strategy runs. Within the text
        strategy, a run that yields no parseable ``FAIL`` line but still exited
        non-zero is surfaced as a whole-run failure (:func:`_whole_run_failure`,
        never swallowed); a clean zero-exit run yields ``()``. These
        empty-vs-nonzero sub-cases are extraction detail, not a strategy label,
        so they live here rather than in :meth:`parse_mode`.
        """
        if self.parse_mode(raw) == "junit_xml":
            from specify_cli.review.baseline import _parse_junit_xml

            artifact = self._resolved_artifact_path(raw)
            assert artifact is not None  # guaranteed by parse_mode's own "junit_xml" branch
            _total, _passed, _failed, _skipped, failures = _parse_junit_xml(artifact)
            return tuple(failures)

        text_failures = _parse_declared_command_failure_lines(raw.stdout) + _parse_declared_command_failure_lines(raw.stderr)
        if text_failures:
            return text_failures
        if raw.returncode != 0:
            return (_whole_run_failure(raw),)
        return ()


# ---------------------------------------------------------------------------
# Factory (FR-003/FR-014) + identity helper (FR-009/NFR-005) — T006/T007/T010
# ---------------------------------------------------------------------------


def resolve_scope_source(
    repo_root: Path,
    *,
    filter_groups_override: object | None = None,
    composite_routing_override: object | None = None,
) -> ScopeSource:
    """The ONE factory both baseline capture (WP03) and the head hook (WP04) call.

    The workflow-derived ``GateCoverageScopeSource`` path was retired after
    this programme deleted GitHub Actions workflows. The historical override
    parameters remain accepted for call-site compatibility, but they no
    longer affect source selection.
    """
    _ = (filter_groups_override, composite_routing_override)
    return DeclaredCommandScopeSource(repo_root=repo_root)


def scope_source_identity(scope_source: ScopeSource, raw: RawRunResult) -> str:
    """The SINGLE ``<SourceClass>/<parse-mode>`` token producer (FR-009/NFR-005).

    Both baseline capture (WP03, into ``BaselineTestResult.source_identity``)
    and head diff (WP04, ``pre_review_gate.py``'s ``SOURCE_MISMATCH`` check)
    call THIS function — never a second, independently-derived token.

    Delegates the parse-mode decision to the source's OWN
    :meth:`ScopeSource.parse_mode` and NEVER re-inspects ``raw`` itself
    (T007 anti-duplication guard, post-plan paula GAP): re-deriving the mode
    here a second time would re-create the exact lock-step-drift pattern this
    mission retires: the source's strategy decision and the parser actually
    used could disagree.

    The command is deliberately absent from the token — NFR-005 carries
    command equality separately (see the declared command's ``test_command()``
    contract, pinned in ``test_scope_source.py``).
    """
    return f"{type(scope_source).__name__}/{scope_source.parse_mode(raw)}"
