"""Static model of the CI test-selection matrix (Issue #2034 / #1933).

CI selects tests **by marker** (``fast`` / ``integration`` / ``git_repo`` /
``slow`` / ``architectural`` / ``windows_ci`` / ``quarantine`` / ``timing`` /
``distribution``) combined with **path** arguments, sharded across many jobs.
The authoring taxonomy (``pytest.ini`` documents ``unit`` as "the category
default for module-scoped tests"; ``contract`` for contract tests) diverges
from that *selection* taxonomy: **no gate selects ``-m unit`` or
``-m contract``**, and several test directories are touched by no gate at all.
Historically, that mismatch left tests selected by **zero** gates —
"untested-but-green". This model now keeps that orphan surface at zero.

This module is the *enforcement substrate* for that gap. It does not re-tier or
re-shard CI (that is the maintainer's migration, against this guardrail). It
statically:

1. Parses every ``pytest`` invocation across the suite-running workflows
   (:data:`WORKFLOW_FILES`), expanding shard matrices when present. An
   invocation counts whether it is directly anchored (``pytest ...``) or
   reached through an indirection — a ``make`` target or a shell script —
   which is resolved by reading the Makefile / script itself (mission
   ``sonar-per-pr-coverage-reuse`` WP03, NFR-007; see the
   "Indirect suite invocations" section below for why).
2. Models each invocation as a :class:`Gate` = ``(paths, ignores, marker_expr)``.
3. Evaluates every collected test against every gate, using pytest's own
   marker-expression evaluator, to count how many gates select it.

A test selected by **0** gates is an *orphan* (coverage hole); a test selected
by **>=2** gates is a *duplicate* (intentional overlap is allowed — reported,
not enforced).

The companion end-to-end oracle
(``test_ci_collection_completeness.py``) requires zero primary-push orphans.
It runs in the PR operator path through ``arch-adversarial`` → ``quality-gate``
and has an independent ``fast-tests-core-misc`` owner for route-affecting
changes. GitHub branch protection wires no required context in this
experimental programme (see repo ``CLAUDE.md``); this module does not
misrepresent any workflow as a required check.

Run directly to refresh/verify the topology census or the separate retained E3
job-selection baselines::

    uv run python -m tests.architectural._gate_coverage --emit-census
    uv run python -m tests.architectural._gate_coverage --verify-census
    uv run python -m tests.architectural._gate_coverage --freeze-baselines
"""

from __future__ import annotations

import ast
import configparser
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pytest
import yaml

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

# pytest's own marker-expression evaluator — guarantees identical semantics to a
# real ``-m`` selection. This is a *private* pytest API and ``pytest`` is floored
# (``>=9.0.3``), NOT upper-pinned, so a breaking move of this import fails loudly
# at import time rather than silently mis-modelling selection. The import contract
# is pinned by ``test_pytest_marker_expression_import_contract`` in the companion
# test module; ``uv.lock`` pins the exact resolved version for reproducible runs.
from _pytest.mark.expression import Expression

# One collected test: its nodeid, repo-relative path, and applied marker names.
TestRecord = dict[str, Any]

# ``(workflow file name, job name)`` — the identity of one CI job. Job names are
# only unique WITHIN a workflow (``changes`` exists in both ci-quality and
# ci-windows), so the pair, never the bare job name, is the key.
JobKey = tuple[str, str]

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

# Every workflow that runs the suite, directly or through an indirection. The
# set is kept in lockstep with what :func:`discover_pytest_workflows` finds on
# disk — enforced by
# ``test_workflow_coherence::test_pytest_workflow_set_equals_model_allowlist_live``,
# which fails closed when a new suite-running workflow appears outside it.
#
# Mission ``sonar-per-pr-coverage-reuse`` WP03 grew this tuple by three, all of
# them workflows that were ALREADY running the suite while the model reported
# they were not (NFR-007):
#
#   * ``ci-quality.yml`` — its non-blocking ``sonarcloud`` reporter
#     (spec-kitty#3993) ran a full test tier through a make target. The model
#     read only directly-anchored ``pytest`` commands, so a whole duplicate
#     suite execution sat in the file, unseen. **WP06 then retired that job**
#     (#4334) and the file left this tuple again: it now runs no suite, and a
#     membership claim for a workflow with no gates would be an allowlist entry
#     asserting something that is not there. The make-indirection resolution
#     below STAYS — it is what made the duplicate visible in the first place,
#     and the next one will not announce itself either.
#   * ``ci-router.yml`` / ``packs.yml`` — directly-anchored, but written as
#     ``uv run --frozen pytest ...``, a form the runner-prefix pattern
#     mis-parsed (it let the ``--frozen`` flag's optional ARGUMENT swallow the
#     ``pytest`` command word), so every one of their gates was dropped.
#
# The factory ``ci.yml`` delegates suite execution to the planning CI scripts
# rather than embedding a pytest command; the other restored producers do not
# run tests.
WORKFLOW_FILES: tuple[str, ...] = (
    "ci-windows.yml",
    "release.yml",
    # Net-new pytest-running workflows reinstated by the ci-pipeline-reinstatement
    # mission.
    "ci-modules.yml",
    "ci-nightly.yml",
    "module-tests.yml",
    # Added by mission sonar-per-pr-coverage-reuse WP03 (see above) — present
    # and running tests all along, merely invisible to the parser. WP06 removed
    # ``ci-quality.yml`` again when it retired the duplicate reporter.
    "ci-router.yml",
    "packs.yml",
)

_COLLECT_PLUGIN = "tests.architectural._gate_collect_plugin"
_TESTS_ROOT = "tests"

# A healthy collect-only run with the marker-dump plugin clears every item, so
# pytest reports NO_TESTS_COLLECTED (5). A collection-time error in a test file
# (bad import / syntax) instead increments testsfailed and yields a failure code.
# Trusting the partial dump in that case would silently DROP the broken file's
# tests — exactly the new tests the ratchet must scrutinize — so any other exit
# code must fail loudly (Issue #2034 Codex review: P2).
_COLLECT_OK_CODES: frozenset[int] = frozenset(
    {int(pytest.ExitCode.OK), int(pytest.ExitCode.NO_TESTS_COLLECTED)},
)

# Reported (not enforced) selection-overlap threshold: >=2 gates = duplicate.
_DUPLICATE_GATE_THRESHOLD = 2

# Quoted ``-m 'a and b'`` OR unquoted single-token ``-m windows_ci``.
_MARKER_Q_RE = re.compile(r"-m\s+(?P<q>['\"])(?P<expr>.*?)(?P=q)")
_MARKER_U_RE = re.compile(r"-m\s+(?P<expr>[A-Za-z_]\w*)")
_IGNORE_RE = re.compile(r"--ignore=(\S+)")
# ``--deselect <nodeid>`` excludes exactly like ``--ignore=``, but takes its
# value as a SEPARATE token — so it must be stripped before positional-path
# extraction, or the deselected target is recorded as a selected path and the
# gate claims coverage of the very tests it excludes.
_DESELECT_RE = re.compile(r"--deselect[=\s]+(\S+)")
_ENV_ASSIGN_RE = re.compile(r"^[A-Za-z_]\w*=(?:'[^']*'|\"[^\"]*\"|\S+)\s+")
_PYTEST_HEAD_RE = re.compile(r"^pytest\b")
_GHA_EXPR_RE = re.compile(r"\$\{\{(.*?)\}\}")
_SEGMENT_SPLIT_RE = re.compile(r"&&|;|\|\|?|\bthen\b|\bdo\b")

# The two operator-facing "full CI block" labels: a PR explicitly labeled
# ``pr:deferred`` / ``pr:skip-ci`` blocks ALL PR-triggered workflows (added in
# ``ddac71ebc``). An always-on job may carry ONLY these two label guards and
# still count as "runs unconditionally"; ANY other conjunct (a
# ``needs.changes.outputs`` path filter, a status/draft/event-name check) would
# silently mask the job and is rejected -- that is the mask the arch pole and
# the residual gate exist to forbid.
FULL_CI_BLOCK_LABELS: tuple[str, ...] = ("pr:deferred", "pr:skip-ci")


def _normalize_conjunct(text: str) -> str:
    """Collapse all whitespace so gate conjuncts compare canonically."""
    return "".join(text.split())


def _full_ci_block_conjuncts() -> frozenset[str]:
    return frozenset(
        f"!contains(github.event.pull_request.labels.*.name,'{label}')"
        for label in FULL_CI_BLOCK_LABELS
    )


def gate_is_always_on_modulo_full_ci_block(
    if_value: str | None, *, require_always: bool
) -> bool:
    """Whether a job runs unconditionally EXCEPT for the full-CI-block labels.

    Accepts either an absent ``if:`` (truly unconditional) or an ``if:`` whose
    only conjuncts are ``always()`` (optional in general, mandatory when
    *require_always* -- e.g. the arch pole must run even when upstream jobs
    fail) plus BOTH ``pr:deferred`` / ``pr:skip-ci`` label guards. Any other
    conjunct -- a path/status/needs/draft/event filter -- returns ``False``,
    because it could silently mask the job (the pre-WP03 mask this forbids).
    """
    if if_value is None:
        # No gate at all is unconditional, but a job that must survive upstream
        # failure needs an explicit ``always()`` -- absence is a regression there.
        return not require_always
    expr_match = _GHA_EXPR_RE.search(if_value)
    inner = expr_match.group(1) if expr_match else if_value
    conjuncts = [c for c in inner.split("&&") if c.strip()]
    if not conjuncts:
        return False
    has_always = False
    label_conjuncts = _full_ci_block_conjuncts()
    seen_labels: set[str] = set()
    for conjunct in conjuncts:
        normalized = _normalize_conjunct(conjunct)
        if normalized in ("always()", "(always())"):
            has_always = True
        elif normalized in label_conjuncts:
            seen_labels.add(normalized)
        else:
            return False  # a masking condition -- reject
    # Labels are all-or-nothing: a bare ``always()`` (no labels) is the original,
    # strictest form; ``always()`` + BOTH labels is the sanctioned full-CI-block
    # form. A single label (asymmetric) is a malformed gate and is rejected.
    labels_ok = seen_labels in (frozenset(), label_conjuncts)
    return labels_ok and (has_always or not require_always)

# Runner prefixes that may precede the literal ``pytest`` command token. After
# stripping leading env-assignments and these, a real pytest *command* segment
# begins with ``pytest`` — so ``pipx inject ... pytest`` and ``git grep ...
# pytest`` (where pytest is an argument, not the command) are correctly skipped.
_PREFIX_RE = re.compile(
    r"^(?:"
    # ``uv run [--with '...'] [--frozen]`` — the optional flag ARGUMENT must
    # not be allowed to swallow the ``pytest`` command word itself, or
    # ``uv run --frozen pytest tests/...`` (the Makefile's own form) parses as
    # "no pytest command here" and the whole invocation goes unseen.
    r"uv\s+run(?:\s+--\S+(?:\s+'[^']*'|\s+\"[^\"]*\"|\s+(?!pytest\b)\S+)?)*"
    # ``env [-i] [-u NAME]... [NAME=value]...`` — the form the Makefile's own
    # recipes use (``env -u FORCE_COLOR NO_COLOR=1 ... uv run pytest``). Only
    # these three token shapes are consumed, so ``env`` can never swallow the
    # real command word that follows it.
    r"|env(?:\s+-i\b|\s+-u\s+[A-Za-z_]\w*|\s+[A-Za-z_]\w*=(?:'[^']*'|\"[^\"]*\"|\S+))*"
    r"|python\d?(?:\s+-m)?"
    r"|\"?\$?\{?[A-Za-z_]\w*\}?\"?\s+-m"  # "$VENV_PYTHON" -m / $VAR -m
    r"|pipx\s+run"
    r"|-m"
    r")\s+",
)


@dataclass
class Gate:
    """One CI test-selection: positional ``paths``, ``--ignore`` globs, ``-m`` expr.

    ``via`` records HOW the step reached pytest: ``None`` for a
    directly-anchored ``pytest`` command, otherwise the indirection it was
    resolved through (``"make <target>"`` / ``"script <path>"``). A gate is a
    gate either way — the field exists so a consumer can *report* the
    provenance, never so it can filter indirect invocations back out.
    """

    workflow: str
    job: str
    shard: str | None
    paths: list[str] = field(default_factory=list)
    ignores: list[str] = field(default_factory=list)
    marker_expr: str | None = None
    via: str | None = None

    def label(self) -> str:
        suffix = f" ({self.shard})" if self.shard else ""
        return f"{self.workflow}::{self.job}{suffix}"


# ---------------------------------------------------------------------------
# Workflow parsing
# ---------------------------------------------------------------------------


def _iter_run_steps(
    data: dict[str, Any],
) -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    """Return ``(job_name, job, step)`` for every step carrying a ``run`` script."""
    steps: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    for job_name, job in (data.get("jobs") or {}).items():
        for step in job.get("steps") or []:
            if isinstance(step, dict) and "run" in step:
                steps.append((job_name, job, step))
    return steps


def _matrix_includes(job: dict[str, Any]) -> list[dict[str, Any]] | None:
    matrix = (job.get("strategy") or {}).get("matrix") or {}
    include = matrix.get("include")
    return include if isinstance(include, list) else None


def substitute_matrix(text: str, mvars: dict[str, Any]) -> str:
    """Expand ``${{ matrix.X }}`` (blanking other ``${{ ... }}`` expressions)."""

    def repl(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        if key.startswith("matrix."):
            return str(mvars.get(key.split(".", 1)[1], ""))
        return ""

    return _GHA_EXPR_RE.sub(repl, text)


def join_continuations(script: str) -> list[str]:
    """Join backslash-continued shell lines into single logical lines."""
    out: list[str] = []
    buf = ""
    for raw in script.splitlines():
        line = raw.rstrip()
        if line.endswith("\\"):
            buf += line[:-1] + " "
        else:
            out.append(buf + line)
            buf = ""
    if buf:
        out.append(buf)
    return out


def strip_to_command(segment: str) -> str:
    """Strip env-assignments and runner prefixes; stop at the ``pytest`` token."""
    s = segment.strip()
    while True:
        m = _ENV_ASSIGN_RE.match(s)
        if not m:
            break
        s = s[m.end() :]
    while not _PYTEST_HEAD_RE.match(s):
        m = _PREFIX_RE.match(s)
        if not m:
            break
        s = s[m.end() :]
    return s


def _extract_marker(tail: str) -> str | None:
    mq = _MARKER_Q_RE.search(tail)
    if mq:
        return mq.group("expr").strip()
    mu = _MARKER_U_RE.search(tail)
    return mu.group("expr").strip() if mu else None


def _extract_paths(tail: str) -> list[str]:
    cleaned = _MARKER_U_RE.sub(" ", _MARKER_Q_RE.sub(" ", tail))
    paths: list[str] = []
    for token in cleaned.split():
        candidate = token.strip("'\"").replace("\\", "/")
        if candidate == _TESTS_ROOT or candidate.startswith(f"{_TESTS_ROOT}/"):
            paths.append(candidate)
    return paths


def parse_pytest_invocation(
    logical_line: str,
) -> tuple[list[str], list[str], str | None] | None:
    """Return ``(paths, ignores, marker)`` for a real pytest command, else None."""
    if logical_line.lstrip().startswith("#"):
        return None
    for segment in _SEGMENT_SPLIT_RE.split(logical_line):
        command = strip_to_command(segment)
        if not command.startswith("pytest"):
            continue
        tail = command[len("pytest") :]
        deselected = _DESELECT_RE.findall(tail)
        positional = _DESELECT_RE.sub(" ", tail)
        return (
            _extract_paths(positional),
            _IGNORE_RE.findall(tail) + deselected,
            _extract_marker(tail),
        )
    return None


# ---------------------------------------------------------------------------
# Indirect suite invocations (mission sonar-per-pr-coverage-reuse WP03,
# NFR-007/FR-010).
#
# A ``run:`` step reaches pytest in two shapes: a directly-anchored ``pytest``
# command, and an *indirection* — ``make <target>``, or a shell script — whose
# body carries the real command. Modelling only the first form left a whole
# suite execution structurally invisible: ``ci-quality.yml``'s ``sonarcloud``
# reporter ran a full test tier through a make target, and every invariant
# built on this substrate reported "no pytest jobs in ci-quality.yml" while
# that duplicate execution sat in the file.
#
# The make target is resolved by READING THE MAKEFILE — parsing its variable
# table and the target's recipe, then re-using :func:`parse_pytest_invocation`
# on the expanded recipe lines. It is deliberately NOT a match on the literal
# string ``make test-fast``: renaming the target must not restore the
# blindness, and the companion fault-injection test asserts exactly that.
#
# Relation to ``_fast_tier_gate`` (DIR-044, canonical sources): that module
# also reads the Makefile, but answers a different question — it pulls the
# VALUES of two specifically-named variables (``FAST_TIER_DIRS`` /
# ``FAST_TIER_MARKERS``) by literal regex. It cannot answer "which pytest
# command does target X run", which is the question the gate model must ask,
# and its literal variable names are precisely the evasion shape this section
# avoids. :func:`parse_makefile` below is the general model; folding
# ``_fast_tier_gate`` onto it would be a sound follow-up, but that module is
# outside this mission's ownership.
# ---------------------------------------------------------------------------

_MAKEFILE_NAME = "Makefile"
# ``$(NAME)`` / ``${NAME}`` references inside a Makefile value or recipe.
_MAKE_VAR_REF_RE = re.compile(r"\$[({]([A-Za-z_][\w.-]*)[)}]")
# ``NAME = v`` / ``NAME := v`` / ``NAME ?= v`` / ``NAME += v``.
_MAKE_ASSIGN_RE = re.compile(
    r"^(?P<name>[A-Za-z_.][\w.]*)\s*(?P<op>[:?+]?=)\s*(?P<value>.*)$",
)
# ``target [target...]: [prerequisites]`` — the ``(?!=)`` keeps ``:=``
# assignments (already consumed above) from reading as a rule.
_MAKE_RULE_RE = re.compile(r"^(?P<targets>[^\s#:=][^:=]*?):(?!=)(?P<prereqs>[^=]*)$")
# Recipe-line silencing / error-ignoring / sub-make prefixes.
_RECIPE_PREFIX_RE = re.compile(r"^[@+-]+\s*")
# ``$$`` is a literal ``$`` handed to the shell, NOT a make expansion — it is
# protected through expansion so ``$$(tr ...)`` is never read as ``$(tr ...)``.
_MAKE_ESCAPED_DOLLAR = "\x00MAKE_DOLLAR\x00"
_MAKE_EXPANSION_PASSES = 16
# ``make`` options that consume the following token as their argument.
_MAKE_OPTS_WITH_ARG: frozenset[str] = frozenset(
    {"-C", "-f", "-j", "-l", "-o", "-W", "--directory", "--file", "--makefile", "--jobs"},
)
_MAKE_COMMAND = "make"
# ``bash x.sh`` / ``sh -e x.sh`` / ``./scripts/x.sh``.
_SCRIPT_CALL_RE = re.compile(
    r"^(?:(?:ba|da|k|z)?sh\s+(?:-\S+\s+)*)?(?P<path>\.{0,2}/?[\w./-]+\.(?:sh|bash))(?:\s|$)",
)
_VIA_MAKE = "make {target}"
_VIA_SCRIPT = "script {path}"


@dataclass(frozen=True)
class SuiteInvocation:
    """One pytest execution a ``run:`` step performs, direct or indirect.

    ``via`` is ``None`` for a directly-anchored command and otherwise names the
    indirection it was recovered through (see :class:`Gate`).
    """

    paths: tuple[str, ...]
    ignores: tuple[str, ...]
    marker_expr: str | None
    via: str | None = None


@dataclass(frozen=True)
class MakefileModel:
    """A Makefile's variable table and target → recipe / prerequisite maps."""

    path: Path
    variables: dict[str, str]
    recipes: dict[str, tuple[str, ...]]
    prerequisites: dict[str, tuple[str, ...]]


def _strip_make_comment(line: str) -> str:
    """Drop a trailing ``#`` comment from a non-recipe Makefile line."""
    index = line.find("#")
    return line if index < 0 else line[:index]


def iter_makefile_lines(text: str) -> list[tuple[bool, str]]:
    """``(is_recipe, text)`` per logical line, backslash continuations joined.

    ``is_recipe`` is taken from the FIRST physical line of the logical line —
    a continued recipe stays a recipe even though its continuation lines are
    indented the same way.
    """
    out: list[tuple[bool, str]] = []
    buffer = ""
    is_recipe = False
    for raw in text.splitlines():
        if not buffer:
            is_recipe = raw.startswith("\t")
        stripped = raw.rstrip()
        if stripped.endswith("\\"):
            buffer += stripped[:-1] + " "
            continue
        out.append((is_recipe, buffer + stripped))
        buffer = ""
    if buffer:
        out.append((is_recipe, buffer))
    return out


def _apply_make_assignment(variables: dict[str, str], match: re.Match[str]) -> None:
    """Record one ``NAME <op>= value`` assignment in *variables*."""
    name = match.group("name")
    operator = match.group("op")
    value = match.group("value").strip()
    if operator == "+=" and name in variables:
        variables[name] = f"{variables[name]} {value}"
    elif operator == "?=" and name in variables:
        return
    else:
        variables[name] = value


def parse_makefile(path: Path) -> MakefileModel:
    """Parse *path* into its variable table and target → recipe/prereq maps.

    A deliberately small subset of GNU make: assignments, explicit rules, and
    recipe bodies. It is enough to answer "which pytest command does this
    target run", which is the only question the gate model asks — and it asks
    it of the real file, so a target rename or a variable indirection cannot
    hide the invocation.
    """
    variables: dict[str, str] = {}
    recipes: dict[str, list[str]] = {}
    prerequisites: dict[str, tuple[str, ...]] = {}
    current: list[str] = []
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    for is_recipe, line in iter_makefile_lines(text):
        if is_recipe:
            for target in current:
                recipes.setdefault(target, []).append(line.lstrip("\t").strip())
            continue
        stripped = _strip_make_comment(line).strip()
        if not stripped:
            continue
        current = []
        assignment = _MAKE_ASSIGN_RE.match(stripped)
        if assignment:
            _apply_make_assignment(variables, assignment)
            continue
        rule = _MAKE_RULE_RE.match(stripped)
        if rule:
            # ``.PHONY`` and friends declare nothing executable — skip them so
            # their "prerequisites" are not mistaken for real targets.
            current = [t for t in rule.group("targets").split() if not t.startswith(".")]
            for target in current:
                prerequisites[target] = tuple(rule.group("prereqs").split())
    return MakefileModel(
        path=path,
        variables=variables,
        recipes={target: tuple(lines) for target, lines in recipes.items()},
        prerequisites=prerequisites,
    )


def expand_make_value(text: str, variables: dict[str, str]) -> str:
    """Expand ``$(VAR)``/``${VAR}`` to a fixed point (unknown names → empty).

    Empty-for-unknown is make's own rule, and it is the safe direction here: an
    unresolvable ``$(SOMETHING)`` drops a token rather than inventing one.
    """
    protected = text.replace("$$", _MAKE_ESCAPED_DOLLAR)
    for _ in range(_MAKE_EXPANSION_PASSES):
        expanded = _MAKE_VAR_REF_RE.sub(lambda m: variables.get(m.group(1), ""), protected)
        if expanded == protected:
            break
        protected = expanded
    return protected.replace(_MAKE_ESCAPED_DOLLAR, "$")


def make_targets_in_command(command: str) -> list[str]:
    """Target names in a ``make ...`` command (options and ``VAR=value`` dropped)."""
    tokens = command.split()
    if not tokens or tokens[0] != _MAKE_COMMAND:
        return []
    targets: list[str] = []
    skip_next = False
    for token in tokens[1:]:
        if skip_next:
            skip_next = False
        elif token in _MAKE_OPTS_WITH_ARG:
            skip_next = True
        elif not token.startswith("-") and "=" not in token:
            targets.append(token)
    return targets


def makefile_target_invocations(
    target: str,
    model: MakefileModel,
    seen: frozenset[str] = frozenset(),
) -> list[SuiteInvocation]:
    """Every pytest invocation reachable from *target* (prerequisites included).

    Prerequisites and recipe-level ``make <other>`` delegation are followed so
    that inserting one more hop of indirection is not an escape hatch; *seen*
    keeps a cyclic Makefile from recursing forever.
    """
    if target in seen:
        return []
    reached = seen | {target}
    found: list[SuiteInvocation] = []
    for prerequisite in model.prerequisites.get(target, ()):
        found.extend(makefile_target_invocations(prerequisite, model, reached))
    for raw in model.recipes.get(target, ()):
        line = _RECIPE_PREFIX_RE.sub("", expand_make_value(raw, model.variables).strip())
        direct = parse_pytest_invocation(line)
        if direct is not None:
            found.append(_as_invocation(direct, via=_VIA_MAKE.format(target=target)))
            continue
        for nested in make_targets_in_command(strip_to_command(line).strip()):
            found.extend(makefile_target_invocations(nested, model, reached))
    return found


def _as_invocation(
    parsed: tuple[list[str], list[str], str | None],
    *,
    via: str | None,
) -> SuiteInvocation:
    paths, ignores, marker = parsed
    return SuiteInvocation(tuple(paths), tuple(ignores), marker, via=via)


def _load_makefile(makefile: Path | None) -> MakefileModel | None:
    path = makefile if makefile is not None else REPO_ROOT / _MAKEFILE_NAME
    return parse_makefile(path) if path.is_file() else None


def _make_indirection(command: str, makefile: Path | None) -> list[SuiteInvocation]:
    targets = make_targets_in_command(command)
    if not targets:
        return []
    model = _load_makefile(makefile)
    if model is None:
        return []
    found: list[SuiteInvocation] = []
    for target in targets:
        found.extend(makefile_target_invocations(target, model))
    return found


def _resolve_script_path(command: str, repo_root: Path) -> Path | None:
    """The in-repo script file *command* invokes, if it invokes one."""
    match = _SCRIPT_CALL_RE.match(command)
    if not match:
        return None
    candidate = (repo_root / match.group("path")).resolve()
    if not candidate.is_file() or not candidate.is_relative_to(repo_root.resolve()):
        return None
    return candidate


def _script_indirection(
    command: str,
    *,
    makefile: Path | None,
    repo_root: Path,
    seen: frozenset[Path],
) -> list[SuiteInvocation]:
    script = _resolve_script_path(command, repo_root)
    if script is None or script in seen:
        return []
    label = _VIA_SCRIPT.format(path=script.relative_to(repo_root.resolve()).as_posix())
    found: list[SuiteInvocation] = []
    for logical in join_continuations(script.read_text(encoding="utf-8")):
        for invocation in suite_invocations(
            logical,
            makefile=makefile,
            repo_root=repo_root,
            _scripts_seen=seen | {script},
        ):
            found.append(
                SuiteInvocation(
                    invocation.paths,
                    invocation.ignores,
                    invocation.marker_expr,
                    via=invocation.via or label,
                ),
            )
    return found


def suite_invocations(
    logical_line: str,
    *,
    makefile: Path | None = None,
    repo_root: Path | None = None,
    _scripts_seen: frozenset[Path] = frozenset(),
) -> list[SuiteInvocation]:
    """Every suite execution one logical shell line performs.

    A directly-anchored ``pytest`` command wins outright; otherwise each shell
    segment is checked for a make target or an in-repo script that reaches the
    suite. Returns ``[]`` for a line that runs no tests — ``make lint`` is not
    a suite invocation, and the companion negative control pins that.
    """
    direct = parse_pytest_invocation(logical_line)
    if direct is not None:
        return [_as_invocation(direct, via=None)]
    root = repo_root if repo_root is not None else REPO_ROOT
    found: list[SuiteInvocation] = []
    for segment in _SEGMENT_SPLIT_RE.split(logical_line):
        command = strip_to_command(segment).strip()
        found.extend(_make_indirection(command, makefile))
        found.extend(
            _script_indirection(
                command, makefile=makefile, repo_root=root, seen=_scripts_seen,
            ),
        )
    return found


def parse_workflow(path: Path, *, makefile: Path | None = None) -> list[Gate]:
    """Parse one workflow file into the gates it defines.

    *makefile* overrides the Makefile consulted for ``make``-target
    indirection (default: the repository's own). It exists for fixture
    workflows, which must be resolvable against a fixture Makefile rather than
    the live one.
    """
    data = load_spliced_workflow(path)
    gates: list[Gate] = []
    for job_name, job, step in _iter_run_steps(data):
        includes = _matrix_includes(job)
        variants: Sequence[dict[str, Any] | None] = includes or (None,)
        for mvars in variants:
            script = substitute_matrix(step["run"], mvars or {})
            for logical in join_continuations(script):
                for invocation in suite_invocations(logical, makefile=makefile):
                    gates.append(
                        Gate(
                            workflow=path.name,
                            job=job_name,
                            shard=(mvars or {}).get("shard") if mvars else None,
                            paths=list(invocation.paths),
                            ignores=list(invocation.ignores),
                            marker_expr=invocation.marker_expr,
                            via=invocation.via,
                        ),
                    )
    return gates


def load_gates() -> list[Gate]:
    """Parse every restored suite-running workflow into the full gate list."""
    gates: list[Gate] = []
    for name in WORKFLOW_FILES:
        gates.extend(parse_workflow(WORKFLOWS_DIR / name))
    return gates


# ---------------------------------------------------------------------------
# Workflow relation model (mission ci-suite-map-bind WP01 — additive substrate
# for the FR-001/FR-003/FR-005/FR-008/FR-010..FR-013 invariant suites).
# Pure parsing only: the invariants over these relations live in the consumer
# test modules, never here.
# ---------------------------------------------------------------------------

_PYTEST_INI_PATH = REPO_ROOT / "pytest.ini"
_DORNY_FILTER_ACTION = "dorny/paths-filter"

# ``needs.<job>.result`` reads inside run scripts (FR-003a / FR-003d).
_NEEDS_RESULT_RE = re.compile(r"needs\.([A-Za-z0-9_-]+)\.result")
# ``needs.<job>.outputs.<group>`` references inside job-level ``if:`` gates
# (FR-003b / FR-010 / FR-011 job→group gating map).
_FILTER_OUTPUT_RE = re.compile(r"needs\.[A-Za-z0-9_-]+\.outputs\.([A-Za-z0-9_]+)")
# ``--cov=<target>`` emitters inside run scripts (FR-005).
_COV_TARGET_RE = re.compile(r"--cov=([^\s\\'\"]+)")
# Jobs that *consume* coverage XML rather than emit real pytest --cov data.
# ``_COV_TARGET_RE`` has no way to distinguish a documentation mention of
# ``--cov=...`` from a real flag, so such a job is excluded wholesale rather
# than the regex taught to parse comments. Any consumer of ``cov_targets`` that
# means "jobs that actually run pytest --cov" (not "jobs whose script mentions
# --cov") must exclude this set.
#
# ``sonarcloud`` was a member until mission sonar-per-pr-coverage-reuse WP06
# (#4334): it carried prose ``--cov=...`` examples in its own step comments.
# The job is retired and its successor -- ci-aggregate.yml's ``sonar-pr`` --
# needs no entry here: it mentions ``--cov`` nowhere, and ci-aggregate.yml is
# not a member of ``WORKFLOW_FILES`` (it runs no suite), so it is never parsed
# for gates at all. Adding it would be an exclusion for a job this model never
# sees.
NON_EMITTER_JOBS: frozenset[str] = frozenset({"diff-coverage", "mutation-testing"})
# Top-level packages declared in [build-system].packages (pyproject.toml) --
# the only names a bare/dotted (no "/") --cov target can legitimately resolve
# to under src/ (#2975's cov_target_repo_path normalizer).
_TOP_LEVEL_SRC_PACKAGES: frozenset[str] = frozenset(
    {
        "kernel",
        "glossary",
        "mission_runtime",
        "runtime",
        "specify_cli",
        "doctrine",
        "charter",
    }
)
# The diff-coverage job's ``critical_paths=( ... )`` shell array (FR-005).
_CRITICAL_PATHS_RE = re.compile(r"critical_paths=\((.*?)\)", re.DOTALL)
_SHELL_QUOTED_RE = re.compile(r"'([^']*)'|\"([^\"]*)\"")
# Leading identifier of one ``markers =`` registry line in pytest.ini.
_MARKER_NAME_RE = re.compile(r"[A-Za-z_]\w*")


def positive_marker_tokens(marker_expr: str | None) -> frozenset[str]:
    """Marker names *positively* referenced by a ``-m`` expression (FR-001 (i)).

    Negation-aware: ``not windows_ci`` does NOT reference ``windows_ci``
    positively (the spec's pinned edge case — every Linux gate negates it),
    while ``not not fast`` does reference ``fast``. A name is positive iff it
    occurs under an even number of ``not`` operators.

    The expression is first compiled with pytest's own
    :class:`~_pytest.mark.expression.Expression` (identical grammar/semantics
    to a real ``-m`` selection — an invalid expression fails loudly there,
    and a breaking move of the private API fails at import time, see the
    module-top import note). The sign walk itself uses the stdlib ``ast``
    parse of the same text: for the identifier-and-boolean-operator
    expressions the workflows use, pytest's expression grammar is a strict
    subset of Python's.
    """
    if not marker_expr:
        return frozenset()
    Expression.compile(marker_expr)  # loud fail on an invalid expression
    try:
        tree = ast.parse(marker_expr, mode="eval")
    except SyntaxError as exc:  # pragma: no cover — Expression accepts a superset
        raise RuntimeError(
            f"marker expression {marker_expr!r} compiles under pytest's grammar "
            "but not under stdlib ast — a gate started using a marker name that "
            "is not a Python identifier; extend positive_marker_tokens' walker.",
        ) from exc
    positive: set[str] = set()
    _walk_marker_ast(tree.body, negated=False, positive=positive)
    return frozenset(positive)


def _walk_marker_ast(node: ast.expr, *, negated: bool, positive: set[str]) -> None:
    """Recursive sign-tracking walk backing :func:`positive_marker_tokens`."""
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        _walk_marker_ast(node.operand, negated=not negated, positive=positive)
    elif isinstance(node, ast.BoolOp):
        for value in node.values:
            _walk_marker_ast(value, negated=negated, positive=positive)
    elif isinstance(node, ast.Name):
        if not negated:
            positive.add(node.id)
    else:
        raise RuntimeError(
            f"unsupported marker-expression node {ast.dump(node)} — a gate "
            "started using pytest kwarg selection (mark(arg=...)); extend "
            "positive_marker_tokens before trusting its output.",
        )


def routed_marker_names(gates: Sequence[Gate]) -> frozenset[str]:
    """Union of positively-referenced marker names across ``gates`` (FR-001 (i)).

    This is the live ROUTED-BY-MARKER set the marker-completeness invariant
    classifies against.
    """
    routed: set[str] = set()
    for gate in gates:
        routed |= positive_marker_tokens(gate.marker_expr)
    return frozenset(routed)


@dataclass(frozen=True)
class WorkflowModel:
    """Parsed relation surfaces of one workflow file (WP01 substrate).

    Every field is a *parsed source relation* (Adjudicated Decision 8: the
    dorny filter block and the job ``if:`` gates are the only two path-topology
    authorities; consumers assert against these, never against hand-maintained
    copies).

    - ``job_needs``: job → declared ``needs:`` list (FR-003a/d).
    - ``needs_result_reads``: job → job names read via ``needs.<job>.result``
      in that job's run scripts (FR-003a). The quality-gate aggregator's
      result-loop membership (FR-003d) is ``needs_result_reads["quality-gate"]``.
    - ``job_gating_groups``: job → dorny filter outputs referenced in the
      job-level ``if:`` expression (FR-003b; FR-011's job→group gating map).
    - ``filter_groups``: dorny filter group → glob list (FR-003c / FR-010).
    - ``cov_targets``: job → ``--cov=`` targets emitted in run scripts (FR-005).
    - ``diff_cover_critical_paths``: the diff-coverage job's shell
      ``critical_paths`` array entries, in declaration order (FR-005).
    - ``pull_request_types`` / ``pull_request_paths`` / ``push_paths``: outer
      ``on:`` trigger types and paths lists (FR-013 / FR-012 two-layer reads).
    - ``job_if``: job -> the RAW ``if:`` scalar (``None`` when absent, ``bool``
      for the YAML-literal ``if: false`` form). ``job_gating_groups`` records
      only *which* filter outputs an ``if:`` mentions; this keeps the whole
      condition so :func:`job_runs_under` can decide whether the job actually
      runs under a given trigger state — the distinction between "references
      the ``cli`` group" and "runs on a push regardless of the ``cli`` group"
      (mission doctrine-silence-guards WP10, FR-013).
    - ``push_branches``: ``on.push.branches``, so the collection-completeness
      model can tell which workflows a push to a given branch even starts.

    ``uses:`` reusable-workflow delegation (#3447) is resolved BEFORE this model
    is built, by :func:`load_spliced_workflow` — a caller job is seen with its
    delegate's steps inlined — so there is no per-job delegation field here.
    """

    path: Path
    job_needs: dict[str, tuple[str, ...]]
    needs_result_reads: dict[str, frozenset[str]]
    job_gating_groups: dict[str, frozenset[str]]
    filter_groups: dict[str, tuple[str, ...]]
    cov_targets: dict[str, frozenset[str]]
    diff_cover_critical_paths: tuple[str, ...]
    pull_request_types: tuple[str, ...]
    pull_request_paths: tuple[str, ...]
    push_paths: tuple[str, ...]
    job_if: dict[str, str | bool | None]
    push_branches: tuple[str, ...]


def _job_needs_tuple(job: dict[str, Any]) -> tuple[str, ...]:
    """A job's declared ``needs:`` as a tuple (GitHub allows str or list)."""
    needs = job.get("needs")
    if needs is None:
        return ()
    if isinstance(needs, str):
        return (needs,)
    return tuple(str(entry) for entry in needs)


def _job_run_text(job: dict[str, Any]) -> str:
    """All raw ``run:`` script text of a job.

    Un-substituted: ``${{ }}`` expressions are kept, because the relation
    reads (``needs.<job>.result``, ...) live inside them.
    """
    return "\n".join(
        str(step["run"])
        for step in job.get("steps") or []
        if isinstance(step, dict) and "run" in step
    )


def _parse_filter_groups(jobs: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    """Dorny paths-filter group → glob tuple.

    Read from any ``dorny/paths-filter`` step's inline ``filters:`` YAML
    (FR-003c / FR-010 source authority).
    """
    groups: dict[str, tuple[str, ...]] = {}
    for job in jobs.values():
        for step in job.get("steps") or []:
            if not isinstance(step, dict):
                continue
            if not str(step.get("uses", "")).startswith(_DORNY_FILTER_ACTION):
                continue
            filters_raw = (step.get("with") or {}).get("filters")
            if not isinstance(filters_raw, str):
                continue
            parsed = yaml.safe_load(filters_raw) or {}
            for name, globs in parsed.items():
                groups[str(name)] = tuple(str(g) for g in globs or [])
    return groups


def _diff_cover_critical_paths(run_text: str) -> tuple[str, ...]:
    """Quoted entries of every ``critical_paths=( ... )`` shell array.

    Declaration order preserved, de-duplicated (FR-005).
    """
    entries: list[str] = []
    for block in _CRITICAL_PATHS_RE.findall(run_text):
        for single, double in _SHELL_QUOTED_RE.findall(block):
            entry = single or double
            if entry and entry not in entries:
                entries.append(entry)
    return tuple(entries)


def _on_section(data: dict[Any, Any]) -> dict[str, Any]:
    """The workflow's ``on:`` mapping (``{}`` for shorthand ``on: push``).

    Typed ``dict[Any, Any]`` because the key is genuinely non-str in the
    common case: YAML 1.1 parses the bare ``on`` key as boolean ``True``.
    """
    section = data.get("on", data.get(True))
    return section if isinstance(section, dict) else {}


def _job_if_scalar(job: dict[str, Any]) -> str | bool | None:
    """One job's raw ``if:`` scalar, preserving the YAML-literal boolean form.

    ``if: false`` (used to park a job) parses as a real ``bool``; coercing it to
    the string ``"False"`` would make it indistinguishable from an unparseable
    condition, so the bool is kept and handled explicitly by
    :func:`job_runs_under`.
    """
    value = job.get("if")
    if value is None or isinstance(value, bool):
        return value
    return str(value)


_LOCAL_REUSABLE_PREFIX = "./.github/workflows/"


def _job_uses_local(job: dict[str, Any]) -> str | None:
    """The local reusable-workflow file a ``uses:`` job delegates to, if any.

    Only ``./.github/workflows/<file>`` refs resolve to a workflow in this model
    (a same-repo reusable workflow, mission #3447); an external
    ``org/repo/.github/workflows/x@ref`` ref returns ``None`` because its jobs
    are not modeled here.
    """
    uses = job.get("uses")
    if isinstance(uses, str) and uses.startswith(_LOCAL_REUSABLE_PREFIX):
        return uses.rsplit("/", 1)[-1]
    return None


def _splice_local_uses(data: dict[str, Any], workflows_dir: Path) -> dict[str, Any]:
    """Inline a local ``uses:`` caller job's delegate steps (mission #3447).

    A reusable-workflow caller job (``uses: ./.github/workflows/<file>``) carries
    no ``steps:`` of its own — its ``--cov`` emitters, test paths and markers
    live in the called workflow. This resolver returns a copy of ``data`` where
    each such caller job gains the called workflow's job steps, so every model
    consumer sees the caller as if it ran the delegate inline (its own
    ``if``/``needs``/name are preserved). The called reusable workflow is
    therefore NOT an independent suite runner — it is excluded from
    :func:`discover_pytest_workflows` and absent from :data:`WORKFLOW_FILES` —
    which avoids double-counting its gate. One level is resolved (module
    workflows are single-purpose, non-nested — enforced below).
    """
    jobs = data.get("jobs")
    if not isinstance(jobs, dict):
        return data
    spliced: dict[str, Any] = {}
    for name, job in jobs.items():
        called = _job_uses_local(job) if isinstance(job, dict) else None
        target_path = workflows_dir / called if called else None
        if target_path is None or not target_path.exists():
            spliced[name] = job
            continue
        target = yaml.safe_load(target_path.read_text(encoding="utf-8")) or {}
        target_jobs = target.get("jobs") or {}
        # Single-purpose assumption made load-bearing: flattening multiple
        # delegate jobs into one caller key would conflate their markers/coverage.
        assert len(target_jobs) == 1, (
            f"reusable workflow {called} must define exactly one job to splice "
            f"into caller {name!r}; found {sorted(target_jobs)}"
        )
        delegate_steps: list[Any] = []
        for delegate_job in target_jobs.values():
            if isinstance(delegate_job, dict):
                delegate_steps.extend(delegate_job.get("steps") or [])
        merged = dict(job)
        merged["steps"] = list(job.get("steps") or []) + delegate_steps
        spliced[name] = merged
    resolved = dict(data)
    resolved["jobs"] = spliced
    return resolved


def load_spliced_workflow(path: Path) -> dict[str, Any]:
    """Parse a workflow file with local ``uses:`` delegation resolved (#3447).

    EVERY reader of a workflow that may contain reusable-workflow caller jobs
    must load through this — not a raw ``yaml.safe_load`` — so a ``uses:`` caller
    job is seen with its delegate's steps inlined. Raw readers that bypass this
    see the caller with no ``steps:`` and mis-model it (missing timeouts,
    ``KeyError: 'steps'``, dropped gates).
    """
    return _splice_local_uses(
        yaml.safe_load(path.read_text(encoding="utf-8")), path.parent
    )


def _trigger_tuple(on_section: dict[str, Any], event: str, key: str) -> tuple[str, ...]:
    """``on.<event>.<key>`` as a string tuple; ``()`` when absent."""
    event_section = on_section.get(event)
    if not isinstance(event_section, dict):
        return ()
    return tuple(str(value) for value in event_section.get(key) or [])


def load_workflow_model(path: Path) -> WorkflowModel:
    """Parse one workflow file into its :class:`WorkflowModel` relations."""
    data = load_spliced_workflow(path)
    jobs: dict[str, Any] = data.get("jobs") or {}
    run_texts = {name: _job_run_text(job) for name, job in jobs.items()}
    on_section = _on_section(data)
    return WorkflowModel(
        path=path,
        job_needs={name: _job_needs_tuple(job) for name, job in jobs.items()},
        needs_result_reads={
            name: frozenset(_NEEDS_RESULT_RE.findall(text))
            for name, text in run_texts.items()
        },
        job_gating_groups={
            name: frozenset(_FILTER_OUTPUT_RE.findall(str(job.get("if") or "")))
            for name, job in jobs.items()
        },
        filter_groups=_parse_filter_groups(jobs),
        cov_targets={
            name: frozenset(_COV_TARGET_RE.findall(text))
            for name, text in run_texts.items()
        },
        diff_cover_critical_paths=_diff_cover_critical_paths(
            "\n".join(run_texts.values()),
        ),
        pull_request_types=_trigger_tuple(on_section, "pull_request", "types"),
        pull_request_paths=_trigger_tuple(on_section, "pull_request", "paths"),
        push_paths=_trigger_tuple(on_section, "push", "paths"),
        job_if={name: _job_if_scalar(job) for name, job in jobs.items()},
        push_branches=_trigger_tuple(on_section, "push", "branches"),
    )


def cov_target_repo_path(target: str) -> str:
    """Normalize a ``--cov`` target to its ``src/``-relative repo path.

    ``--cov`` targets come in two shapes (#2975): a ``src/``-relative path
    (single-root invocations, e.g. ``src/kernel``) or a dotted importable
    module (multi-root invocations, converted to dotted form so
    coverage.py's ``XmlReporter.source_paths`` stays empty and same-basename
    files across roots cannot collide, e.g. ``specify_cli.charter_runtime``).
    Both name the same on-disk location; every consumer of ``cov_targets``
    that compares against a filesystem path (FR-005's critical-path backing,
    the src-coverage-emitter set) must go through this normalizer instead of
    assuming one shape, or a dotted target silently stops matching.
    """
    if "/" in target:
        return target.rstrip("/")
    return "/".join(("src", *target.split(".")))


def is_src_cov_target(target: str) -> bool:
    """Whether a ``--cov`` target measures a ``src/`` package (dotted or path).

    True for both shapes as long as the top-level segment is one of the
    packages declared in ``[build-system].packages`` (pyproject.toml) -- the
    only names coverage.py can resolve a bare/dotted target against. False
    for non-src targets like ``scripts/docs``.
    """
    path = cov_target_repo_path(target)
    if not path.startswith("src/"):
        return False
    top_level = path.split("/", 2)[1]
    return top_level in _TOP_LEVEL_SRC_PACKAGES


def discover_pytest_workflows(workflows_dir: Path | None = None) -> frozenset[str]:
    """Workflow file names under ``workflows_dir`` that invoke pytest (FR-008).

    Content probe with the *same* detection semantics as the gate model
    (:func:`parse_workflow`), so the probe and :data:`WORKFLOW_FILES` cannot
    diverge in what "runs the suite" means. The consumer invariant asserts
    this set equals the allowlist, failing closed when a fifth suite-running
    workflow appears without entering the model.

    Reusable ``on: workflow_call``-only workflows are excluded (mission #3447):
    they are not independent suite runners — their steps are spliced into the
    caller job (:func:`_splice_local_uses`) and modeled there, so counting them
    separately would break the ``discover == WORKFLOW_FILES`` invariant.
    """
    directory = workflows_dir or WORKFLOWS_DIR
    candidates = sorted(directory.glob("*.yml")) + sorted(directory.glob("*.yaml"))
    return frozenset(
        path.name
        for path in candidates
        if parse_workflow(path) and not _is_reusable_only(path)
    )


def _is_reusable_only(path: Path) -> bool:
    """Whether a workflow's only trigger is ``workflow_call`` (a reusable module)."""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    on_section = data.get("on", data.get(True))
    if isinstance(on_section, dict):
        return set(on_section) == {"workflow_call"}
    return False


def registered_markers(pytest_ini: Path | None = None) -> tuple[str, ...]:
    """Marker names registered in pytest.ini's ``markers =`` block.

    ``pytest.ini`` is the single marker-registry authority (C-006, guarded by
    ``test_marker_registry_single_source.py``) — this READS it, adding no
    second surface. pytest's own ini handling is line-based (each non-empty
    block line registers one marker, its name the leading identifier before
    the ``:`` description), mirrored here without importing pytest's config
    machinery.
    """
    path = pytest_ini or _PYTEST_INI_PATH
    parser = configparser.ConfigParser(interpolation=None)
    parser.read_string(path.read_text(encoding="utf-8"))
    names: list[str] = []
    for line in parser.get("pytest", "markers", fallback="").splitlines():
        match = _MARKER_NAME_RE.match(line.strip())
        if match:
            names.append(match.group())
    return tuple(names)


# ---------------------------------------------------------------------------
# Selection model
# ---------------------------------------------------------------------------


def _is_file_entry(entry: str) -> bool:
    return entry.endswith(".py") or ".py::" in entry


def path_matches(relpath: str, nodeid: str, entry: str) -> bool:
    entry = entry.replace("\\", "/")
    if "::" in entry:
        return nodeid == entry or nodeid.startswith(entry)
    if _is_file_entry(entry):
        return relpath == entry
    prefix = entry if entry.endswith("/") else entry + "/"
    return relpath.startswith(prefix)


class CompiledGate:
    """A :class:`Gate` with its marker expression pre-compiled for evaluation."""

    def __init__(self, gate: Gate) -> None:
        self.gate = gate
        # A gate whose positional paths could not be parsed (e.g. ci-windows.yml
        # builds its test list dynamically via ``git grep``) falls back to the
        # whole tree. That fallback is coverage-SAFE only when a marker expression
        # narrows it: ci-windows runs ``-m windows_ci``, so it claims coverage of
        # exactly the windows-only tests, not the whole suite.
        #
        # #2967 (zero-producer / inert-slot bare-name false-pass): a gate with
        # NEITHER parsed positional paths NOR a marker is a *bare name that
        # resolves to no real producer*. Letting it fall back to the whole tree
        # (with no marker to narrow it) makes it silently claim coverage of EVERY
        # test — an inert slot that "covers" the whole suite. Such a gate must
        # instead select NOTHING (fail closed): a producer that produces no real
        # selection covers no test.
        self._zero_producer = not gate.paths and gate.marker_expr is None
        self.paths = gate.paths or [_TESTS_ROOT]
        self.expr = Expression.compile(gate.marker_expr) if gate.marker_expr else None

    def selects(self, relpath: str, nodeid: str, markers: set[str]) -> bool:
        if self._zero_producer:
            # A zero-producer / inert-slot gate resolves to no real producer and
            # therefore covers nothing (#2967) — never the whole-tree fallback.
            return False
        if not any(path_matches(relpath, nodeid, p) for p in self.paths):
            return False
        if any(path_matches(relpath, nodeid, ig) for ig in self.gate.ignores):
            return False
        if self.expr is None:
            return True
        # pytest's matcher protocol is callable(name, /, **kw) -> bool; a plain
        # membership test is structurally compatible (cast silences the Protocol).
        matcher = cast("Any", lambda name: name in markers)
        return bool(self.expr.evaluate(matcher))


@dataclass
class CoverageReport:
    total: int
    orphan_nodeids: list[str]
    orphan_files: list[str]
    duplicate_nodeids: list[str]

    @property
    def orphan_count(self) -> int:
        return len(self.orphan_nodeids)


def analyze(
    gates: list[Gate],
    universe: list[TestRecord],
    active_jobs: frozenset[JobKey] | None = None,
) -> CoverageReport:
    """Count gate selections per test; collect orphans (0) and duplicates (>=2).

    ``active_jobs`` restricts the model to the jobs that actually RUN under some
    trigger state (:func:`active_job_keys`). Default ``None`` keeps the historic
    "every job runs" model every existing caller relies on — which is why the
    committed ratchet baseline records ``orphan_test_count: 0``: true in that
    model, and vacuous against a real CI run where most jobs are filter-gated
    away. Passing an active set is what makes the count non-vacuous; the
    selection evaluator itself (:class:`CompiledGate`) is unchanged and shared,
    so there is exactly one selection engine (D-044).
    """
    selected = (
        gates
        if active_jobs is None
        else [g for g in gates if (g.workflow, g.job) in active_jobs]
    )
    compiled = [CompiledGate(g) for g in selected]
    orphan_nodeids: list[str] = []
    orphan_files: set[str] = set()
    duplicate_nodeids: list[str] = []
    for test in universe:
        relpath, nodeid = test["relpath"], test["nodeid"]
        markers = set(test["markers"])
        hits = sum(1 for cg in compiled if cg.selects(relpath, nodeid, markers))
        if hits == 0:
            orphan_nodeids.append(nodeid)
            orphan_files.add(relpath)
        elif hits >= _DUPLICATE_GATE_THRESHOLD:
            duplicate_nodeids.append(nodeid)
    return CoverageReport(
        total=len(universe),
        orphan_nodeids=sorted(orphan_nodeids),
        orphan_files=sorted(orphan_files),
        duplicate_nodeids=sorted(duplicate_nodeids),
    )


# ---------------------------------------------------------------------------
# Trigger-state job activation (mission doctrine-silence-guards WP10, FR-013 /
# SC-013 / issue #2957).
#
# WHY THIS EXISTS. :func:`analyze` counts a test as covered when ANY parsed gate
# selects it — a model in which every job always runs. Real CI does not work
# that way: 40 of the 50 suite-running jobs are gated on a ``dorny/paths-filter``
# output, so on a push whose diff misses those globs the job never starts and
# every test it uniquely owns runs nowhere. That is the same defect as WP01's
# inert schema slot, one layer up: a frozen-contract test no job collects is
# exactly as inert as a schema slot nothing produces.
#
# WHAT IS MODELED. The two path-topology authorities the module already parses
# (Adjudicated Decision 8: the dorny filter block and the job ``if:`` gates),
# plus the ``on:`` trigger block. Nothing new is parsed from the workflow — the
# only new capability is DECIDING a parsed ``if:`` against a named trigger
# state, which no existing surface does.
#
# FAIL-CLOSED BY CONSTRUCTION. :func:`job_runs_under` returns ``True`` only for
# conditions it positively recognizes as satisfied; anything it does not model
# is treated as "does not run". The consequence of a mis-read is therefore an
# over-report of uncollected tests (a loud red someone must look at), never a
# silent claim of coverage that does not exist.
#
# ONE DELIBERATE EXCEPTION, AND WHAT IT COSTS THE CLAIM. Exactly one conjunct
# fails OPEN: ``needs.<job>.result == 'success'`` decides ``True``
# (:data:`_NEEDS_RESULT_RE_CONJUNCT`). It has to — reading it as unsatisfiable
# would declare every downstream job dead and leave nothing to reason about. The
# property this module can therefore state is "collected on a push to ``main``
# ON THE GREEN PATH": when an upstream job fails, GitHub skips its dependents and
# a real run collects less than modelled. So an uncollected count from here is
# exact on a green run and a LOWER BOUND on a red one — the error direction is
# "the hole is at least this big", never "there is no hole".
# ---------------------------------------------------------------------------

# The branch whose push state the completeness invariant is evaluated against.
PRIMARY_BRANCH = "main"
PUSH_EVENT = "push"
PULL_REQUEST_EVENT = "pull_request"

_ALWAYS = "always()"
# ``!contains(github.event.pull_request.labels.*.name, '<label>')`` — the two
# full-CI-block guards. On any non-``pull_request`` event there is no pull
# request, so ``contains`` over an absent label list is false and the negation
# holds.
_PR_LABEL_GUARD_RE = re.compile(
    r"^!\s*contains\(\s*github\.event\.pull_request\.labels\.\*\.name\s*,\s*"
    r"'[^']*'\s*\)$",
)
# ``needs.<job>.result == 'success'`` / ``!= 'failure'`` — an ORDERING conjunct,
# not a masking one: it says "run me after that job, if it went well", and it is
# satisfied on the green path this invariant reasons about. Treating it as
# unsatisfiable would declare every downstream job dead and make the model
# useless; treating it as satisfied is the standard "assume upstream green"
# reading, stated here so a reviewer can see the assumption rather than infer it.
_NEEDS_RESULT_RE_CONJUNCT = re.compile(
    r"^needs\.[A-Za-z0-9_-]+\.result\s*[!=]=\s*'[A-Za-z_]+'$",
)
_GROUP_OUTPUT_RE = re.compile(
    r"^needs\.[A-Za-z0-9_-]+\.outputs\.([A-Za-z0-9_]+)\s*==\s*'true'$",
)
_EVENT_NAME_RE = re.compile(r"^github\.event_name\s*(==|!=)\s*'([A-Za-z_]+)'$")
_EXPRESSION_WRAPPER_RE = re.compile(r"^\$\{\{(?P<inner>.*)\}\}$", re.DOTALL)

_AND = "&&"
_OR = "||"


def _is_balanced(text: str) -> bool:
    """Whether ``text`` has no unmatched ``(`` / ``)``."""
    depth = 0
    for char in text:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def split_top_level(expr: str, operator: str) -> list[str]:
    """Split ``expr`` on ``operator`` occurrences OUTSIDE any parentheses.

    The workflow's conditions are plain boolean expressions over identifiers,
    quoted literals and calls, so paren depth is the only nesting that matters.
    """
    parts: list[str] = []
    buffer: list[str] = []
    depth = 0
    index = 0
    while index < len(expr):
        char = expr[index]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        if depth == 0 and expr.startswith(operator, index):
            parts.append("".join(buffer))
            buffer = []
            index += len(operator)
            continue
        buffer.append(char)
        index += 1
    parts.append("".join(buffer))
    return [part.strip() for part in parts if part.strip()]


def normalize_condition(text: str) -> str:
    """Strip the ``${{ }}`` wrapper and any redundant outer parentheses."""
    condition = " ".join(text.split())
    match = _EXPRESSION_WRAPPER_RE.match(condition)
    if match:
        condition = match.group("inner").strip()
    while (
        condition.startswith("(")
        and condition.endswith(")")
        and _is_balanced(condition[1:-1])
    ):
        condition = condition[1:-1].strip()
    return condition


def _atom_runs_under(atom: str, *, event_name: str, active_groups: frozenset[str]) -> bool:
    """Decide a single (non-composite) condition term. Unknown terms -> False."""
    if atom == _ALWAYS:
        return True
    if _PR_LABEL_GUARD_RE.match(atom):
        return event_name != PULL_REQUEST_EVENT
    if _NEEDS_RESULT_RE_CONJUNCT.match(atom):
        return True
    group_match = _GROUP_OUTPUT_RE.match(atom)
    if group_match:
        return group_match.group(1) in active_groups
    event_match = _EVENT_NAME_RE.match(atom)
    if event_match:
        operator, expected = event_match.groups()
        return (expected == event_name) if operator == "==" else (expected != event_name)
    return False


def job_runs_under(
    if_value: str | bool | None,
    *,
    event_name: str,
    active_groups: frozenset[str],
) -> bool:
    """Whether a job with this ``if:`` starts, given an event and filter state.

    ``None`` (no condition) runs; a YAML-literal ``if: false`` never does.
    Otherwise the condition is decomposed by precedence — ``||`` then ``&&``,
    parentheses respected — down to terms :func:`_atom_runs_under` decides.
    Anything unrecognized decides ``False`` (see the fail-closed note above).
    """
    if if_value is None:
        return True
    if isinstance(if_value, bool):
        return if_value
    condition = normalize_condition(if_value)
    if not condition:
        return True
    disjuncts = split_top_level(condition, _OR)
    if len(disjuncts) > 1:
        return any(
            job_runs_under(part, event_name=event_name, active_groups=active_groups)
            for part in disjuncts
        )
    conjuncts = split_top_level(condition, _AND)
    if len(conjuncts) > 1:
        return all(
            job_runs_under(part, event_name=event_name, active_groups=active_groups)
            for part in conjuncts
        )
    if condition.startswith("(") and condition.endswith(")") and _is_balanced(condition[1:-1]):
        return job_runs_under(
            condition[1:-1], event_name=event_name, active_groups=active_groups,
        )
    return _atom_runs_under(condition, event_name=event_name, active_groups=active_groups)


def workflow_runs_on_push(model: WorkflowModel, branch: str = PRIMARY_BRANCH) -> bool:
    """Whether a push to ``branch`` starts this workflow at all (``on.push.branches``).

    A workflow that triggers only on tags is a live negative: its tests are not
    collected by a push to ``main`` — a real hole this predicate surfaces
    rather than hides.
    """
    return branch in model.push_branches


def active_job_keys(
    models: dict[str, WorkflowModel],
    *,
    event_name: str,
    active_groups: frozenset[str],
    branch: str = PRIMARY_BRANCH,
) -> frozenset[JobKey]:
    """Every ``(workflow, job)`` that runs under one trigger state."""
    active: set[JobKey] = set()
    for name, model in models.items():
        if event_name == PUSH_EVENT and not workflow_runs_on_push(model, branch):
            continue
        for job, if_value in model.job_if.items():
            if job_runs_under(
                if_value, event_name=event_name, active_groups=active_groups,
            ):
                active.add((name, job))
    # NOTE: ``uses:`` reusable-workflow delegation needs no resolution here — the
    # caller job already carries its delegate's steps/gates (load_spliced_workflow),
    # so it is emitted with the right paths/markers by the normal loop above (#3447).
    return frozenset(active)


def main_push_active_jobs(
    models: dict[str, WorkflowModel] | None = None,
) -> frozenset[JobKey]:
    """Jobs that run on a push to ``main`` in the WORST reachable filter state.

    The worst state is "no dorny group matched", and it is reachable rather than
    hypothetical: the ``changes`` job's fail-open catch-all only forces a full
    run when ``any_src`` is true (a ``src/**`` change no named group claimed), so
    a push touching only an unclaimed ``tests/**`` directory — which
    ``on.push.paths`` explicitly admits — hits every named group false with the
    catch-all silent. Because a job's ``if:`` is monotone in the active-group set
    (groups only ever appear as ``== 'true'`` disjuncts), completeness in this
    state implies completeness in every richer one, so one evaluation settles the
    whole family instead of 2**N of them.
    """
    resolved = models if models is not None else load_workflow_models()
    return active_job_keys(
        resolved, event_name=PUSH_EVENT, active_groups=frozenset(),
    )


def main_push_uncollected(
    universe: list[TestRecord],
    gates: list[Gate] | None = None,
    models: dict[str, WorkflowModel] | None = None,
) -> CoverageReport:
    """SC-013: the tests no job collects on a push to ``main``, on the green path.

    ``orphan_nodeids`` here means "collected by zero RUNNING jobs" — node-level,
    not file-level. The distinction is load-bearing: a file holding one ``slow``
    test and twenty ``fast`` ones satisfies any file-level reading while the
    twenty never execute, and that is the exact shape of most of #2957's list.

    "On the green path" because of the single fail-open conjunct documented in
    the section header: the count is exact when every upstream job succeeds and a
    lower bound when one does not.
    """
    return analyze(
        gates if gates is not None else load_gates(),
        universe,
        main_push_active_jobs(models),
    )


# ---------------------------------------------------------------------------
# Collection (subprocess --collect-only with the marker-dumping plugin)
# ---------------------------------------------------------------------------


def collect_universe(repo_root: Path | None = None) -> list[TestRecord]:
    """Collect every test with its marker set via a one-pass ``--collect-only``.

    Runs pytest in a subprocess with an isolated ``HOME`` (WP04 home isolation)
    and the :data:`_COLLECT_PLUGIN` plugin, which dumps
    ``{nodeid, relpath, markers}`` for each item and suppresses execution.
    """
    repo = repo_root or REPO_ROOT
    with tempfile.TemporaryDirectory() as tmp:
        dump = Path(tmp) / "universe.json"
        env = dict(os.environ)
        env.update(
            HOME=tempfile.mkdtemp(prefix="sk-gatecov-home-"),
            SK_GATE_DUMP=str(dump),
            SK_GATE_REPO=str(repo),
        )
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "--collect-only",
                "-q",
                "-p",
                "no:cacheprovider",
                "-p",
                _COLLECT_PLUGIN,
                "-o",
                "addopts=",
                _TESTS_ROOT,
            ],
            cwd=repo,
            env=env,
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
        )
        if result.returncode not in _COLLECT_OK_CODES or not dump.exists():
            raise RuntimeError(
                "gate-coverage collection did not complete cleanly — refusing to "
                "trust a partial/empty test universe. A collection-time import or "
                "syntax error in a test file would otherwise be silently dropped, "
                "letting the orphan ratchet pass against an incomplete suite.\n"
                f"pytest exit={result.returncode} "
                f"(expected one of {sorted(_COLLECT_OK_CODES)}); "
                f"dump_present={dump.exists()}\n"
                f"--- stdout (tail) ---\n{result.stdout[-2000:]}\n"
                f"--- stderr (tail) ---\n{result.stderr[-2000:]}",
            )
        universe: list[TestRecord] = json.loads(dump.read_text(encoding="utf-8"))
        # Portability (#2607): normalize the worktree-root prefix out of node-ids
        # so the modeled-current side matches the repo-relative baseline (see
        # collect_job_nodeids). Absolute-path parametrize ids (e.g.
        # test_tasks_prompt_ownership_metadata) would otherwise diverge from the
        # normalized baseline on pure checkout-path noise.
        repo_prefix = f"{repo}{os.sep}"
        for rec in universe:
            rec["nodeid"] = rec["nodeid"].replace(repo_prefix, "")
        return universe


# A ``-q --collect-only`` node-id line contains a ``.py::`` selector; the
# trailing summary line ("39/72 tests collected (33 deselected) in 25.04s")
# and warning/error lines do not, so this pattern isolates the real selection.
_NODEID_LINE_RE = re.compile(r"^\S+\.py::")


def collect_job_nodeids(gate: Gate, repo_root: Path | None = None) -> list[str]:
    """Real, scoped ``pytest --collect-only -q`` node-ids for one job's exact CLI.

    Restricted to ``gate.paths``/``gate.ignores``/``gate.marker_expr`` — the
    exact CLI the suite-running workflow uses for this job. Parses pytest's OWN
    ``-q --collect-only`` stdout (one selected node-id per line) rather than the
    marker-dumping :data:`_COLLECT_PLUGIN`: that plugin clears the item list in
    ``pytest_collection_modifyitems`` and so records items BEFORE pytest's own
    ``-m`` deselection runs — capturing the UNFILTERED path set, not the real
    ``-m``-narrowed selection. Native ``-q`` output reflects the true
    marker-and-ignore deselection, giving a genuinely independent real
    collection: the E3 baseline authority (:func:`freeze_baselines`) that the
    GC-2b guard compares the modeled-current selection against, and the
    fidelity anchor's fresh real reference (:class:`CompiledGate` over the
    universe must equal THIS for every baselined job).
    """
    repo = repo_root or REPO_ROOT
    env = dict(os.environ)
    env["HOME"] = tempfile.mkdtemp(prefix="sk-gatecov-home-")
    args = [
        sys.executable,
        "-m",
        "pytest",
        "--collect-only",
        "-q",
        "-p",
        "no:cacheprovider",
        "-o",
        "addopts=",
        *(gate.paths or [_TESTS_ROOT]),
        *(f"--ignore={ig}" for ig in gate.ignores),
    ]
    if gate.marker_expr:
        args += ["-m", gate.marker_expr]
    result = subprocess.run(
        args, cwd=repo, env=env, capture_output=True, text=True, timeout=900, check=False,
    )
    if result.returncode not in _COLLECT_OK_CODES:
        raise RuntimeError(
            f"scoped gate collection for job {gate.job!r} did not complete cleanly "
            f"(exit {result.returncode}, expected one of {sorted(_COLLECT_OK_CODES)}) "
            "— refusing to freeze/compare a partial selection.\n"
            f"--- stdout (tail) ---\n{result.stdout[-2000:]}\n"
            f"--- stderr (tail) ---\n{result.stderr[-2000:]}",
        )
    # Portability (#2607): some tests parametrize on ABSOLUTE paths (e.g.
    # tests/prompts/test_tasks_prompt_ownership_metadata.py embeds the worktree
    # root in its parametrize ids). Frozen from one worktree (`…-lane-f`) those
    # ids would never match a different checkout (the primary tree, another
    # lane, or CI's `/home/runner/work/…`), reddening GC-2b on pure path noise.
    # Strip the collecting worktree-root prefix so node-ids are repo-relative
    # and checkout-portable. Applied identically in freeze and compare (both go
    # through this function), so the two sides stay consistent.
    repo_prefix = f"{repo}{os.sep}"
    return sorted(
        line.strip().replace(repo_prefix, "")
        for line in result.stdout.splitlines()
        if _NODEID_LINE_RE.match(line.strip())
    )


# ---------------------------------------------------------------------------
# CI-topology census + architectural-completeness relations
# (mission ci-topology-shrink-01KWQAVX WP01 — additive substrate for the
# NFR-002/NFR-003/NFR-006 invariant suites authored in WP02/WP03. PURE
# parsing/derivation only: the invariants over these relations live in the
# consumer test modules, never here. C-001 additive; NFR-007 — no existing
# surface's behavior is changed.)
# ---------------------------------------------------------------------------

# Single-literal census path (Sonar S1192): the committed construction-derived
# worklist authority WP02's SC-001 test iterates.
CENSUS_PATH = Path(__file__).with_name("ci_topology_census.json")

# Committed LOC floor for worklist membership (NFR-006). This is the plan-time
# constant; it lives in the census artifact and is NEVER inlined into a test —
# the SC-001 test reads it from the census so the metric measures coverage, not
# the implementer's constant.
T_LOC = 500

_SRC_PACKAGE_PREFIX = "src/specify_cli/"
_WHOLE_DIR_SUFFIX = "/**"
# The catch-all group (``src/**``) is src-backed but maps no *specific* dir: a
# touch matching only it still trips ``unmatched`` (data-model: "Src-backed
# groups (minus any_src)"), so it never removes a dir from the worklist.
_ANY_SRC_GROUP = "any_src"
# Marker name whose positive presence identifies an architectural-suite gate.
_ARCH_MARKER = "architectural"
# Gate-tier prefixes for the same-tier uniqueness relation (NFR-003).
_FAST_TIER_PREFIX = "fast-tests"
_INTEGRATION_TIER_PREFIX = "integration-tests"

# NFR-001 wallclock baseline (live CI run 28705381819, research §2.2). Probe
# measurements, not tree-derivable — committed so the SC-003/NFR-001 ceiling is
# anchored to a cited run rather than re-measured per invocation.
_TIMINGS_BASELINE: dict[str, float] = {
    "fast_core_misc_min": 17.0,
    "arch_shard_min": 12.3,
    "critical_path_min": 29.4,
    "next_lane_min": 13.6,
    "source_run_id": 28705381819,
}

_WORKLIST_RULE = (
    "D in worklist iff D is a direct child directory of src/specify_cli/ AND "
    "sum(LOC of *.py under D) >= t_loc AND no src-backed dorny filter group "
    "(excluding any_src) globs src/specify_cli/<D>/."
)

# Frozen pre-mission mapped baseline (NFR-006; review cycle 1). The FR-001
# worklist is the set of hot dirs the mission is chartered to *shrink to zero*
# by mapping them into src-backed dorny groups. Deriving the worklist against
# the LIVE ``mapped_src_dirs`` would make the mission's own success empty the
# worklist (worklist would shrink to nothing the moment WP03 globs the dirs),
# making WP02's routing / non-empty / freshness assertions mutually
# unsatisfiable. So membership subtracts this *committed snapshot* of the dirs
# already mapped before the mission began — identical to the census
# ``mapped_dirs`` field, disjoint from the 32-dir worklist. It is frozen: it
# does NOT re-read the live model (nor the census JSON it validates), so
# post-WP03 mapping leaves it at these 23 dirs, keeping the worklist stable at
# 32. Teeth are preserved and strengthened — a hand-trim of the census still
# reds, a dir crossing the LOC floor changes membership, and a *new* hot dir
# (>= t_loc, not in this baseline) grows the live derivation beyond the
# committed census and reds.
_PRE_MISSION_MAPPED_SRC_DIRS: frozenset[str] = frozenset(
    {
        "acceptance",
        "agent_utils",
        "charter_runtime",
        "cli",
        "coordination",
        "core",
        "dashboard",
        "delivery",
        "doctrine_synthesizer",
        "event_journal",
        "lanes",
        "merge",
        "missions",
        "post_merge",
        "release",
        "review",
        "runtime",
        "saas",
        "state",
        "status",
        "sync",
        "tool_surface",
        "upgrade",
    },
)

# One committed composite-routing plan entry: (target_group, target_shard,
# cone_roots). ``target_shard`` is the existing integration shard family the dir
# already lands in (research §1.4A/§3), the stable anchor SC-001 checks.
_CompositeRoute = tuple[str | None, str | None, tuple[str, ...]]
_EMPTY_ROUTING: _CompositeRoute = (None, None, ())

# Committed composite-routing plan (FR-001 / FR-010, research §3): the named
# group + focused integration shard family each worklist dir must map to, plus
# its test cone roots. This is the *design overlay* joined onto the tree-derived
# ``{dir, loc}`` membership — tree membership + LOC are re-derived live
# (:func:`live_derived_worklist`); this table is the committed plan authority
# SC-001 (WP03) asserts the live workflow conforms to, not a derived fact.
_COMPOSITE_ROUTING: dict[str, _CompositeRoute] = {
    # auth_audit_git -> existing ``auth-audit-git`` integration shard.
    "auth": ("auth_audit_git", "auth-audit-git", ("tests/auth",)),
    "audit": (
        "auth_audit_git", "auth-audit-git",
        ("tests/audit", "tests/specify_cli/audit"),
    ),
    "git": (
        "auth_audit_git", "auth-audit-git",
        ("tests/git", "tests/git_ops", "tests/specify_cli/git"),
    ),
    # lifecycle -> ``specify-cli-heavy`` (heavy marker adds ``and not slow``).
    "migration": (
        "lifecycle", "specify-cli-heavy",
        ("tests/migration", "tests/specify_cli/migration"),
    ),
    "invocation": (
        "lifecycle", "specify-cli-heavy",
        ("tests/invocation", "tests/specify_cli/invocation"),
    ),
    "compat": ("lifecycle", "specify-cli-heavy", ("tests/specify_cli/compat",)),
    "distribution": (
        "lifecycle", "specify-cli-heavy", ("tests/specify_cli/distribution",),
    ),
    "template": ("lifecycle", "specify-cli-heavy", ("tests/test_template",)),
    # agent_surface -> ``specify-cli-rest``.
    "orchestrator_api": (
        "agent_surface", "specify-cli-rest", ("tests/specify_cli/orchestrator_api",),
    ),
    "tracker": ("agent_surface", "specify-cli-rest", ("tests/tracker",)),
    "dossier": (
        "agent_surface", "specify-cli-rest",
        ("tests/dossier", "tests/specify_cli/dossier"),
    ),
    "bulk_edit": ("agent_surface", "specify-cli-rest", ("tests/specify_cli/bulk_edit",)),
    "skills": ("agent_surface", "specify-cli-rest", ("tests/specify_cli/skills",)),
    # closeout -> ``misc``.
    "retrospective": (
        "closeout", "misc",
        (
            "tests/retrospective",
            "tests/specify_cli/retrospect",
            "tests/specify_cli/retrospective",
        ),
    ),
    "readiness": (
        "closeout", "misc", ("tests/readiness", "tests/specify_cli/readiness"),
    ),
    "decisions": ("closeout", "misc", ("tests/specify_cli/decisions",)),
    "doc_analysis": ("closeout", "misc", ()),
    "widen": ("closeout", "misc", ("tests/specify_cli/widen",)),
    # write-side-seam-matrix-tracer-01KYP3MH: issue-matrix.json read/write +
    # bulk-migration domain (issue_matrix.py, issue_matrix_migration.py,
    # issue_reference_discovery.py) -- closest to the closeout group's existing
    # "decisions" member (a structured record-tracking surface), and its tests
    # already run under the misc shard (tests/tasks -> shard: misc, ci-quality.yml).
    "tasks": ("closeout", "misc", ("tests/tasks",)),
    # governance -> ``misc``.
    "doctrine": ("governance", "misc", ("tests/specify_cli/doctrine",)),
    "policy": ("governance", "misc", ("tests/policy",)),
    "ownership": ("governance", "misc", ("tests/specify_cli/ownership",)),
    "contracts": ("governance", "misc", ("tests/specify_cli/contracts",)),
    "validators": ("governance", "misc", ()),
    "calibration": ("governance", "misc", ("tests/calibration",)),
    "context": ("governance", "misc", ("tests/context", "tests/specify_cli/context")),
    # platform -> ``specify-cli-rest``.
    "workspace": ("platform", "specify-cli-rest", ("tests/specify_cli/workspace",)),
    "session_presence": (
        "platform", "specify-cli-rest", ("tests/specify_cli/session_presence",),
    ),
    "mission_v1": ("platform", "specify-cli-rest", ("tests/specify_cli/mission_v1",)),
    "mission_loader": ("platform", "specify-cli-rest", ("tests/unit/mission_loader",)),
    "events": ("platform", "specify-cli-rest", ("tests/specify_cli/events",)),
    "paths": ("platform", "specify-cli-rest", ("tests/paths",)),
    "saas_client": ("platform", "specify-cli-rest", ("tests/specify_cli/saas_client",)),
    "identity": ("platform", "specify-cli-rest", ("tests/specify_cli/identity",)),
    "task_utils": ("platform", "specify-cli-rest", ()),
    "intake": ("platform", "specify-cli-rest", ()),
}


def load_workflow_models() -> dict[str, WorkflowModel]:
    """Parse every restored suite-running workflow into ``name -> WorkflowModel``."""
    return {
        name: load_workflow_model(WORKFLOWS_DIR / name) for name in WORKFLOW_FILES
    }


def _group_is_src_backed(globs: Sequence[str]) -> bool:
    """A filter group is src-backed iff >=1 glob targets ``src/`` (data-model)."""
    return any(str(g).startswith("src/") for g in globs)


def aggregate_filter_groups(
    models: dict[str, WorkflowModel],
) -> dict[str, tuple[str, ...]]:
    """Union of every workflow's dorny filter groups: ``group -> sorted globs``."""
    merged: dict[str, set[str]] = {}
    for model in models.values():
        for name, globs in model.filter_groups.items():
            merged.setdefault(name, set()).update(globs)
    return {name: tuple(sorted(globs)) for name, globs in merged.items()}


def _src_dir_of_glob(glob: str) -> str | None:
    """First ``src/specify_cli/<dir>`` segment a glob targets, else ``None``.

    ``src/**`` (the ``any_src`` catch-all), non-package globs, and top-level
    ``src/specify_cli/<file>.py`` globs return ``None`` — they map no *specific*
    package dir.
    """
    normalized = glob.replace("\\", "/")
    if not normalized.startswith(_SRC_PACKAGE_PREFIX):
        return None
    segment = normalized[len(_SRC_PACKAGE_PREFIX) :].split("/", 1)[0].split("*", 1)[0]
    if not segment or segment.endswith(".py"):
        return None
    return segment


def mapped_src_dirs(models: dict[str, WorkflowModel]) -> frozenset[str]:
    """``src/specify_cli`` dirs claimed by >=1 src-backed named group != any_src.

    A dir here does NOT fall to ``unmatched->run_all`` on a confined touch
    (research §1.2 mapping oracle); the FR-001 worklist is exactly the
    complement (``>= t_loc`` LOC, unmapped).
    """
    mapped: set[str] = set()
    for name, globs in aggregate_filter_groups(models).items():
        if name == _ANY_SRC_GROUP or not _group_is_src_backed(globs):
            continue
        for glob in globs:
            dir_name = _src_dir_of_glob(glob)
            if dir_name is not None:
                mapped.add(dir_name)
    return frozenset(mapped)


def _newline_count(path: Path) -> int:
    """``wc -l`` semantics: the number of newline bytes in a file."""
    return path.read_bytes().count(b"\n")


def src_package_loc(repo_root: Path = REPO_ROOT) -> dict[str, int]:
    """Direct-child dir of ``src/specify_cli/`` -> recursive ``*.py`` line count.

    Mirrors the research §1.1 shell census (``find <d> -name '*.py' | xargs
    wc -l``): the count is the total number of newline characters across every
    ``*.py`` file under the dir, so a construction-derived worklist matches a
    hand-run census exactly.
    """
    package_dir = repo_root / "src" / "specify_cli"
    loc_by_dir: dict[str, int] = {}
    for child in sorted(package_dir.iterdir()):
        if not child.is_dir():
            continue
        loc_by_dir[child.name] = sum(_newline_count(py) for py in child.rglob("*.py"))
    return loc_by_dir


def live_derived_worklist(
    t_loc: int = T_LOC,
    repo_root: Path = REPO_ROOT,
) -> list[dict[str, Any]]:
    """Re-derive the FR-001 worklist from the LIVE tree (NFR-006 freshness guard).

    Pure and side-effect-free: reads only the source tree, never writes. A dir
    qualifies iff it is a direct child of ``src/specify_cli/``, its recursive
    ``*.py`` LOC ``>= t_loc``, and it is NOT in the frozen pre-mission mapped
    baseline :data:`_PRE_MISSION_MAPPED_SRC_DIRS` — the committed
    :data:`_WORKLIST_RULE`. The subtraction is against the *frozen* baseline,
    not the live ``mapped_src_dirs``, so the mission's own success (WP03 mapping
    the worklist dirs) does not empty the worklist: the derivation stays at the
    32 hot-but-unmapped-at-mission-start dirs (review cycle 1 fix). Each
    qualifying dir is annotated with its committed :data:`_COMPOSITE_ROUTING`
    plan (group / focused shard / cone roots); tree membership + LOC are the
    *derived* facts, the annotation is the committed plan overlay (an unrouted
    qualifying dir carries ``None`` group/shard).

    WP02's ``test_ci_topology_worklist.py`` asserts census/live agreement on
    membership + routing via :func:`worklist_routing_index` — so a stale or
    hand-trimmed census still reds in CI (NFR-006). Exact per-dir ``loc`` is NOT
    emitted (issue #2416): it was a noisy freshness proxy that red unrelated PRs on
    any line-count churn, while every anti-tamper tooth (hand-trim, floor-crossing,
    new hot dir) is a *membership* change the routing index already captures.
    ``loc`` is still read internally to gate membership on the floor. The drop is
    applied here at the single shared derivation, so the ``--verify-census`` CLI
    (which consumes this function) is LOC-insensitive by construction too. Entries
    are sorted by ``dir`` name (LOC-independent) for a stable, diff-friendly order.
    """
    worklist: list[dict[str, Any]] = []
    for dir_name, loc in src_package_loc(repo_root).items():
        if loc < t_loc or dir_name in _PRE_MISSION_MAPPED_SRC_DIRS:
            continue
        group, shard, cones = _COMPOSITE_ROUTING.get(dir_name, _EMPTY_ROUTING)
        worklist.append(
            {
                "dir": dir_name,
                "cone_roots": list(cones),
                "target_group": group,
                "target_shard": shard,
            },
        )
    worklist.sort(key=lambda entry: str(entry["dir"]))
    return worklist


def worklist_routing_index(
    entries: Sequence[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Dir-keyed routing index for the freshness guard (order/LOC-insensitive, #2416).

    Only membership (the dir keys) and the committed routing plan (cone roots /
    target group / target shard) participate, so a pure line-count change or a LOC
    rank-swap between two members does not red the freshness gate. Exact LOC and list
    order are deliberately excluded — every anti-tamper tooth is a membership or
    routing change, which this index still captures.
    """
    return {
        str(entry["dir"]): {
            "cone_roots": list(entry.get("cone_roots", [])),
            "target_group": entry.get("target_group"),
            "target_shard": entry.get("target_shard"),
        }
        for entry in entries
    }


# --- Differential arch-completeness matrix (NFR-002) -----------------------


def _gate_is_arch(gate: Gate) -> bool:
    """True iff the gate positively selects the ``architectural`` marker family."""
    return _ARCH_MARKER in positive_marker_tokens(gate.marker_expr)


def _job_gating_index(models: dict[str, WorkflowModel]) -> dict[str, frozenset[str]]:
    """Merged ``job -> filter groups referenced in its ``if:`` across workflows."""
    gating: dict[str, frozenset[str]] = {}
    for model in models.values():
        gating.update(model.job_gating_groups)
    return gating


def group_less_suite_jobs(
    gates: Sequence[Gate],
    models: dict[str, WorkflowModel],
) -> frozenset[str]:
    """Suite-running jobs with NO dorny filter-group ``if:`` gate (always-on).

    Such a job (``lint``, ``slow-tests``, ``unit-contract-residual`` today; the
    future always-on ``arch-adversarial``) references no filter output, so it is
    legitimately absent from ``JOB_GROUPS`` / ``src_backed_groups`` and does not
    perturb the FR-010/FR-011 relations (research §4.2). Recognizing it lets the
    differential matrix credit an always-on arch pole that carries no filter
    gate.
    """
    gating = _job_gating_index(models)
    return frozenset(gate.job for gate in gates if not gating.get(gate.job))


def always_on_arch_present(
    gates: Sequence[Gate],
    models: dict[str, WorkflowModel],
) -> bool:
    """True iff an always-on (group-less) job runs the architectural suite.

    When present, the arch suite fires on every PR regardless of which src dir
    changed, so every dir is arch-selected by construction (NFR-002 target
    state). Today no group-less job runs arch -> ``False`` -> 13 arch-blind dirs.
    """
    group_less = group_less_suite_jobs(gates, models)
    return any(_gate_is_arch(gate) and gate.job in group_less for gate in gates)


def arch_trigger_groups(
    gates: Sequence[Gate],
    models: dict[str, WorkflowModel],
) -> frozenset[str]:
    """Filter groups whose touch fires the (group-gated) architectural suite.

    Union of the ``if:`` filter outputs of every group-gated arch-running job
    (today ``integration-tests-core-misc`` -> ``{acceptance, core_misc,
    execution_context}``). A dir whole-dir covered by one of these is
    arch-covered even without an always-on pole.
    """
    group_less = group_less_suite_jobs(gates, models)
    gating = _job_gating_index(models)
    triggers: set[str] = set()
    for gate in gates:
        if _gate_is_arch(gate) and gate.job not in group_less:
            triggers |= set(gating.get(gate.job, frozenset()))
    return frozenset(triggers)


def _whole_dir_glob(dir_name: str) -> str:
    """The dorny glob that covers the whole of ``src/specify_cli/<dir_name>``."""
    return f"{_SRC_PACKAGE_PREFIX}{dir_name}{_WHOLE_DIR_SUFFIX}"


def _arch_covered_src_dirs(
    gates: Sequence[Gate],
    models: dict[str, WorkflowModel],
) -> frozenset[str]:
    """Dirs whole-dir covered by an arch-trigger group (every touch fires arch).

    Only a whole-dir glob (``src/specify_cli/<D>/**``) counts: a deeper glob
    like ``execution_context``'s ``src/specify_cli/cli/commands/agent/**`` leaves
    a confined ``cli`` touch arch-blind, so ``cli`` is NOT arch-covered.
    """
    triggers = arch_trigger_groups(gates, models)
    groups = aggregate_filter_groups(models)
    covered: set[str] = set()
    for group in triggers:
        for glob in groups.get(group, ()):
            dir_name = _src_dir_of_glob(glob)
            if dir_name is not None and _whole_dir_glob(dir_name) == glob:
                covered.add(dir_name)
    return frozenset(covered)


def arch_selected_for_dir(
    dir_name: str,
    *,
    mapped: frozenset[str],
    arch_covered: frozenset[str],
    always_on_arch: bool,
) -> bool:
    """Pure predicate: does a touch confined to ``dir_name`` run the arch suite?

    ``True`` iff (a) an always-on arch job exists (fires unconditionally), or
    (b) the dir is unmapped (a confined touch trips ``unmatched->run_all``,
    which runs everything incl. arch), or (c) the dir is whole-dir covered by an
    arch-trigger filter group. ``False`` (arch-blind) only for a mapped dir no
    arch-trigger group covers (Mode B) — the un-blind target.
    """
    if always_on_arch:
        return True
    if dir_name not in mapped:
        return True
    return dir_name in arch_covered


def differential_arch_matrix(
    gates: Sequence[Gate] | None = None,
    models: dict[str, WorkflowModel] | None = None,
    repo_root: Path = REPO_ROOT,
) -> dict[str, bool]:
    """``src/specify_cli/*`` dir -> arch-selected bool (NFR-002 differential matrix).

    The mechanized proof that the architectural + adversarial guards execute on
    100% of src dirs. Today 13 dirs are arch-blind (the pre-WP03 red baseline);
    WP03's always-on arch job flips every dir to ``True`` by construction, and a
    regression re-adding a filter-group gate to that job reds this relation.
    """
    resolved_models = models if models is not None else load_workflow_models()
    resolved_gates = list(gates) if gates is not None else load_gates()
    mapped = mapped_src_dirs(resolved_models)
    arch_covered = _arch_covered_src_dirs(resolved_gates, resolved_models)
    always_on = always_on_arch_present(resolved_gates, resolved_models)
    return {
        dir_name: arch_selected_for_dir(
            dir_name,
            mapped=mapped,
            arch_covered=arch_covered,
            always_on_arch=always_on,
        )
        for dir_name in src_package_loc(repo_root)
    }


def arch_blind_src_dirs(
    gates: Sequence[Gate] | None = None,
    models: dict[str, WorkflowModel] | None = None,
    repo_root: Path = REPO_ROOT,
) -> tuple[str, ...]:
    """Sorted ``src/specify_cli/*`` dirs the arch suite never fires on (Mode B)."""
    matrix = differential_arch_matrix(gates, models, repo_root)
    return tuple(sorted(d for d, selected in matrix.items() if not selected))


# --- Same-tier shard-uniqueness relation (NFR-003) -------------------------


def _gate_tier(gate: Gate) -> str | None:
    """Tier of a gate for same-tier uniqueness: ``fast`` / ``integration`` / None."""
    if gate.job.startswith(_FAST_TIER_PREFIX):
        return "fast"
    if gate.job.startswith(_INTEGRATION_TIER_PREFIX):
        return "integration"
    return None


def shard_counts_for_test(
    test: TestRecord,
    tiered_gates: Sequence[tuple[CompiledGate, str]],
) -> dict[str, int]:
    """Count fast-tier / integration-tier shards that select one test (NFR-003).

    ``tiered_gates`` is a pre-built ``[(CompiledGate, tier), ...]``. Same-tier
    uniqueness means each count should be ``<= 1``; a test selected by two fast
    shards (or two integration shards) is a same-tier double-run.
    """
    relpath, nodeid, markers = test["relpath"], test["nodeid"], set(test["markers"])
    fast = integration = 0
    for compiled, tier in tiered_gates:
        if not compiled.selects(relpath, nodeid, markers):
            continue
        if tier == "fast":
            fast += 1
        else:
            integration += 1
    return {"count_fast_shards": fast, "count_integration_shards": integration}


def same_tier_shard_counts(
    gates: Sequence[Gate],
    universe: Sequence[TestRecord],
) -> dict[str, dict[str, int]]:
    """``nodeid -> {count_fast_shards, count_integration_shards}`` (NFR-003).

    Pure over its inputs (the caller supplies the collected ``universe`` via
    :func:`collect_universe`), so this module performs no collection side effect.
    Distinct from the report-only cross-tier duplicate count in :func:`analyze`:
    this counts *within* a tier, where the invariant is uniqueness (``<= 1``),
    not intentional overlap.
    """
    tiered_gates: list[tuple[CompiledGate, str]] = [
        (CompiledGate(gate), tier)
        for gate in gates
        if (tier := _gate_tier(gate)) is not None
    ]
    return {
        test["nodeid"]: shard_counts_for_test(test, tiered_gates)
        for test in universe
    }


def _selected_nodeids(gates: Sequence[Gate], universe: Sequence[TestRecord]) -> frozenset[str]:
    """Node-ids any of ``gates`` selects, evaluated over ``universe``."""
    compiled = [CompiledGate(g) for g in gates]
    return frozenset(
        test["nodeid"]
        for test in universe
        if any(
            cg.selects(test["relpath"], test["nodeid"], set(test["markers"]))
            for cg in compiled
        )
    )


def cross_job_disjoint_selection(
    job_a_gates: Sequence[Gate],
    job_b_gates: Sequence[Gate],
    universe: Sequence[TestRecord],
) -> frozenset[str]:
    """Intersection of node-ids two gate groups select (GC-2 cross-job disjointness).

    Empty == the two jobs' selections never double-run the same test — the
    invariant for e.g. the serial ``-n0`` orphan-sweep job's selection vs. the
    parallel sync pool's selection. Pure over its inputs (``universe`` supplied
    by the caller via :func:`collect_universe`) and reuses
    :class:`CompiledGate`/``selects()`` — the same evaluator
    :func:`shard_counts_for_test` uses — rather than a second selection engine
    (D-044/C-003).
    """
    return _selected_nodeids(job_a_gates, universe) & _selected_nodeids(job_b_gates, universe)


# --- Census assembly + regeneration CLI (NFR-006) --------------------------


def _primary_group_for_dir(
    dir_name: str,
    groups: dict[str, tuple[str, ...]],
) -> str | None:
    """The named group whose whole-dir glob claims ``dir_name`` (skip any_src)."""
    whole = _whole_dir_glob(dir_name)
    for name, globs in sorted(groups.items()):
        if name != _ANY_SRC_GROUP and whole in globs:
            return name
    return None


def _arch_blind_group_rows(
    gates: Sequence[Gate],
    models: dict[str, WorkflowModel],
    loc_by_dir: dict[str, int],
) -> list[dict[str, Any]]:
    """The 13 Mode-B arch-blind groups as ``{group, dir, loc}`` rows (data-model)."""
    groups = aggregate_filter_groups(models)
    rows: list[dict[str, Any]] = [
        {
            "group": _primary_group_for_dir(dir_name, groups),
            "dir": dir_name,
            "loc": loc_by_dir.get(dir_name, 0),
        }
        for dir_name in arch_blind_src_dirs(gates, models)
    ]
    rows.sort(key=lambda row: (-int(row["loc"]), str(row["dir"])))
    return rows


_CENSUS_COMMENT = (
    "Construction-derived CI-topology census (mission ci-topology-shrink, "
    "NFR-006). 'worklist' is the FR-001 authority: every src/specify_cli/* dir "
    "with >= t_loc LOC that no src-backed dorny filter group claims. Re-derived "
    "live by tests.architectural._gate_coverage.live_derived_worklist(); WP02's "
    "test_ci_topology_worklist.py asserts census.worklist == "
    "live_derived_worklist(), so a stale/hand-trimmed census reds. Regenerate "
    "with: uv run python -m tests.architectural._gate_coverage --emit-census"
)


def build_census(t_loc: int = T_LOC, repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Assemble the full census dict from the LIVE tree + parsed model (NFR-006)."""
    models = load_workflow_models()
    gates = load_gates()
    loc_by_dir = src_package_loc(repo_root)
    return {
        "_comment": _CENSUS_COMMENT,
        "t_loc": t_loc,
        "rule": _WORKLIST_RULE,
        "worklist": live_derived_worklist(t_loc, repo_root),
        "mapped_dirs": sorted(mapped_src_dirs(models)),
        "arch_blind_groups": _arch_blind_group_rows(gates, models, loc_by_dir),
        "timings_baseline": dict(_TIMINGS_BASELINE),
    }


def _emit_census() -> int:
    census = build_census()
    CENSUS_PATH.write_text(
        json.dumps(census, indent=2) + "\n", encoding="utf-8",
    )
    print(
        f"census written: {len(census['worklist'])} worklist dirs, "
        f"{len(census['arch_blind_groups'])} arch-blind groups -> {CENSUS_PATH}",
    )
    return 0


_CENSUS_DERIVED_FIELDS = ("worklist", "mapped_dirs", "arch_blind_groups")


def _verify_census() -> int:
    census: dict[str, Any] = json.loads(CENSUS_PATH.read_text(encoding="utf-8"))
    live = build_census()
    stale = [f for f in _CENSUS_DERIVED_FIELDS if census.get(f) != live[f]]
    if stale:
        print(f"census is STALE in {stale} — re-run --emit-census")
        return 1
    print(
        f"census fresh: {len(live['worklist'])} worklist dirs, "
        f"{len(live['mapped_dirs'])} mapped dirs, "
        f"{len(live['arch_blind_groups'])} arch-blind groups",
    )
    return 0


# ---------------------------------------------------------------------------
# E3 baseline node-id manifests + GC-2b diff guard (mission
# ci-test-topology-performance-01KXBJRT WP02, FR-007/NFR-005 — this mission's
# load-bearing invariant).
#
# SCOPE (corrected after a first cut baselined all 22 suite-running jobs and
# compared a MODELED-current selection against a REAL baseline): WP06 only
# CHANGES the SELECTED test set for three jobs —
#   - integration-tests-next: sharded into a next_shard_1/2/3 matrix (E1).
#   - slow-tests: path-narrowed (risk of a dropped directory).
#   - fast-tests-core-misc: shard-rebalanced (already 2 legs today).
# Everything else WP06 touches (WP-G's ``-n auto``, the fast-tests-charter
# job split, ...) is parallelization-only — the selected test set is
# unchanged — so baselining it adds cost with no coverage-preservation
# signal. GC-2b therefore guards exactly these three jobs.
#
# COMPARISON SHAPE (modeled-current vs real-baseline): the committed
# ``baseline`` side is REAL — a scoped ``pytest --collect-only -q`` per job leg
# (:func:`collect_real_union_for_target` / :func:`collect_job_nodeids`), frozen
# once by ``--freeze-baselines``. The day-to-day ``current`` side is the MODEL
# (:class:`CompiledGate` via :func:`_selected_nodeids`) evaluated over ONE shared
# :func:`collect_universe`, so the parametrized cases reuse a single collection
# instead of spawning a real ``--collect-only`` per case (a CI-speed mission must
# not add ~10min to its own arch shard). Because the baseline is real and
# model-independent, a ``selects()`` that mis-parsed a job's ``-m`` expression or
# positional path DIVERGES from the real baseline and GC-2b reds — the real
# baseline IS the fidelity check for these three jobs. A separate scoped
# model-fidelity anchor (modeled == a FRESH real collect) is kept for the
# sharded ``next`` tier in ``test_ci_collection_completeness.py`` to catch a
# mis-model on the job most at risk of one.
# ---------------------------------------------------------------------------

BASELINES_DIR = Path(__file__).with_name("baselines")


@dataclass(frozen=True)
class BaselineTarget:
    """One selection-changing job this WP freezes a REAL E3 baseline for.

    Matched against parsed :class:`Gate` entries by ``(workflow, job)``
    alone — not by shard — so a target transparently covers however many
    shard legs the job has TODAY (a single command, e.g.
    ``integration-tests-next`` pre-WP06) or GROWS to under WP06 (a matrix):
    :func:`collect_real_union_for_target` unions every matching leg's real
    selection, so a shard split alone (same total coverage, more legs) cannot
    false-red GC-2b.
    """

    slug: str
    workflow: str
    job: str


# The former slow-tests authoring baseline was retired with the reduced interim
# CI producer; no restored workflow currently owns an E3 selection baseline.
BASELINE_TARGETS: tuple[BaselineTarget, ...] = ()


def gates_for_target(gates: Sequence[Gate], target: BaselineTarget) -> list[Gate]:
    """Every parsed :class:`Gate` leg belonging to one guarded job.

    Raises loudly (rather than silently baselining zero legs) if the
    workflow was restructured and the target's job no longer parses to any
    gate — a stale ``BASELINE_TARGETS`` entry must be fixed, not ignored.
    """
    matches = [
        g for g in gates if g.workflow == target.workflow and g.job == target.job
    ]
    if not matches:
        raise RuntimeError(
            f"baseline target {target.slug!r} resolved to 0 gates for "
            f"workflow={target.workflow!r} job={target.job!r} — the workflow "
            "was restructured or the job renamed; update BASELINE_TARGETS to "
            "match.",
        )
    return matches


def _baseline_path(target: BaselineTarget) -> Path:
    return BASELINES_DIR / f"{target.slug}-nodeids.txt"


def _baseline_header(target: BaselineTarget) -> str:
    return (
        f"# E3 baseline (mission ci-test-topology-performance-01KXBJRT WP02). "
        f"REAL `pytest --collect-only` node-id UNION across every leg of "
        f"job={target.job!r} (workflow={target.workflow!r}), refrozen by "
        "mission runtime-state-corpus-cutover-01KXZ0AX WP06 (#2816): the "
        "flag-OFF dual-write twin (test_move_task_rollback_clears_claim_flag_off) "
        "was deleted and the flag-ON/flag-OFF split suite reconciled to the "
        "single post-cutover snapshot-authority end-state, changing this job's "
        "collected node-id set. Regenerate ONLY with an explicit provenance "
        "comment (data-model E3) when a WP legitimately changes this job's "
        "selection: uv run python -m tests.architectural._gate_coverage "
        "--freeze-baselines"
    )


def write_baseline_nodeids(target: BaselineTarget, nodeids: Iterable[str]) -> None:
    """Commit one target's E3 baseline file (sorted, provenance-commented)."""
    BASELINES_DIR.mkdir(parents=True, exist_ok=True)
    body = "\n".join(sorted(nodeids))
    _baseline_path(target).write_text(
        _baseline_header(target) + "\n" + body + "\n", encoding="utf-8",
    )


def collect_real_union_for_target(
    target: BaselineTarget,
    gates: Sequence[Gate],
    repo_root: Path | None = None,
) -> frozenset[str]:
    """REAL current selection for one guarded job (GC-2b's ``current`` side).

    Union of every leg's real ``pytest --collect-only`` selection
    (:func:`collect_job_nodeids`) — no modeled (``CompiledGate.selects()``)
    step anywhere. Both :func:`freeze_baselines` (the ``baseline`` side) and
    the day-to-day GC-2b test (the ``current`` side) call this SAME function,
    so the two sides of the comparison are captured by the identical method
    (data-model E3) and cannot drift apart via a modeling difference.
    """
    union: set[str] = set()
    for gate in gates_for_target(gates, target):
        union.update(collect_job_nodeids(gate, repo_root))
    return frozenset(union)


def freeze_baselines(repo_root: Path | None = None) -> dict[str, int]:
    """Capture every :data:`BASELINE_TARGETS` job's REAL current selection to disk.

    One-time (or deliberate-regeneration) authoring entry point — day-to-day
    GC-2b comparisons read the committed files this writes, they never call
    this.
    """
    gates = load_gates()
    counts: dict[str, int] = {}
    for target in BASELINE_TARGETS:
        nodeids = collect_real_union_for_target(target, gates, repo_root)
        write_baseline_nodeids(target, nodeids)
        counts[target.slug] = len(nodeids)
    return counts


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if "--emit-census" in args:
        return _emit_census()
    if "--verify-census" in args:
        return _verify_census()
    if "--freeze-baselines" in args:
        counts = freeze_baselines()
        for slug, count in counts.items():
            print(f"  {slug}: {count} node-ids -> {BASELINES_DIR / f'{slug}-nodeids.txt'}")
        print(f"froze {len(counts)} E3 baseline(s) under {BASELINES_DIR}")
        return 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
