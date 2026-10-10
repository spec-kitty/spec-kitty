"""SC-008 gate: a scripted walk of the software-dev step prompts and contracts.

This gate extends :mod:`tests.charter_offering.test_builtin_cli_command_references`
(which checks only command *paths*) into a four-axis walk of the CLI-driven
software-dev step prompts -- ``implement``, ``review``, ``accept`` and
``tasks-finalize`` -- plus the shipped step contracts. Over that corpus it
asserts (SC-008, FR-022):

1. **Commands and options** -- every ``spec-kitty <path>`` in a code context
   resolves against the real Click command tree, and every ``--option`` in the
   same shell clause exists on the resolved leaf command.
2. **Rendered step-contract commands** -- every ``command:`` a shipped
   software-dev step contract declares, rendered through the executor's own
   ``_render_declared_command`` (command + declared inputs), parses against the
   CLI that must accept it.
3. **"next advances to X" claims** -- every claim that ``spec-kitty next``
   advances to a named workflow step matches the runtime template's successor
   order (``mission-runtime.yaml``); a claim that it advances to a non-step
   action (e.g. ``consolidate``) or to the wrong step is a violation.
4. **Consumer paths** -- every spec-kitty-owned project path the prompts name
   (``.kittify/...``, ``kitty-specs/...``) resolves against a real
   ``spec-kitty init`` fixture or an EXPLICIT allowlist of placeholder forms,
   and no prompt leaks a ``src/specify_cli/...`` internal path.

The gate is pointable: ``SPEC_KITTY_PROMPT_WALK_PACK_ROOT`` overrides the pack
root scanned, so the red-first reproduction can aim it at a pre-cleanup tree.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.main import get_command

from charter.offering.missions.step_contracts import (
    MissionStepContract,
    MissionStepContractRepository,
    MissionStepContractStep,
)
from specify_cli.mission_step_contracts.executor import StepContractExecutor
from tests import _click_universe as typer_click
from tests.charter_offering.conftest import REPO_ROOT

pytestmark = [pytest.mark.doctrine, pytest.mark.corpus]

_PACK_ROOT_ENV = "SPEC_KITTY_PROMPT_WALK_PACK_ROOT"

#: The CLI-driven software-dev prompts this gate walks (C12).
_WALKED_PROMPTS: tuple[str, ...] = ("implement", "review", "accept", "tasks-finalize")

#: The software-dev actions whose shipped step contracts declare CLI commands.
_WALKED_CONTRACT_ACTIONS: frozenset[str] = frozenset({"implement", "review", "tasks"})

# --- segment / token extraction -------------------------------------------

_FENCE = re.compile(r"^\s*(```|~~~)")
_INLINE_CODE = re.compile(r"`([^`\n]+)`")
_COMMAND_PATTERN = re.compile(r"(?<![\w./-])spec-kitty((?:[ \t]+[a-z][a-z0-9_-]*)+)")
_SHELL_BREAK = re.compile(r"[|;&]| &&| \|\|")
_LONG_OPTION = re.compile(r"(?<![\w-])(--[a-z][a-z0-9-]*)")


def _pack_root() -> Path:
    """Return the ``packs/built-in`` root scanned, honoring the pointable env."""
    override = os.environ.get(_PACK_ROOT_ENV)
    if override:
        return Path(override)
    return REPO_ROOT / "packs" / "built-in"


def _software_dev_steps() -> Path:
    return _pack_root() / "missions" / "mission-steps" / "software-dev"


def _code_segments(text: str) -> Iterator[tuple[int, str]]:
    """Yield ``(line_number, segment)`` for every code-context segment.

    Mirrors :mod:`tests.charter_offering.test_builtin_cli_command_references`: fenced
    blocks yield each line; outside a fence, every inline code span yields.
    """
    in_fence = False
    for line_number, line in enumerate(text.splitlines(), start=1):
        if _FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            yield line_number, line
            continue
        for match in _INLINE_CODE.finditer(line):
            yield line_number, match.group(1)


def _commands_with_options(segment: str) -> Iterator[tuple[list[str], list[str]]]:
    """Yield ``(command_path_tokens, long_options)`` for each spec-kitty clause.

    Options are scoped to the shell clause the command opens -- everything from
    the command up to the next shell operator (``|``, ``;``, ``&&``, ``||``) --
    so a trailing ``| grep ...`` or a second command's flags are never
    misattributed to the spec-kitty command.
    """
    for match in _COMMAND_PATTERN.finditer(segment):
        tokens = match.group(1).split()
        tail = segment[match.end() :]
        break_match = _SHELL_BREAK.search(tail)
        clause = tail[: break_match.start()] if break_match else tail
        options: list[str] = _LONG_OPTION.findall(clause)
        yield tokens, options


def _resolve_leaf(root: typer_click.Group, tokens: list[str]) -> tuple[typer_click.Command | None, str | None]:
    """Walk ``tokens`` to a leaf command.

    Returns ``(leaf, None)`` when the path resolves (a leaf reached, remaining
    tokens being arguments), or ``(None, unresolved_prefix)`` when a group token
    does not resolve.
    """
    command: typer_click.Command = root
    walked: list[str] = []
    for token in tokens:
        if not isinstance(command, typer_click.Group):
            return command, None
        sub = command.get_command(typer_click.Context(command), token)
        if sub is None:
            return None, " ".join([*walked, token])
        walked.append(token)
        command = sub
    return command, None


def _command_option_strings(command: typer_click.Command) -> set[str]:
    """Return every long/short option string the command accepts."""
    accepted: set[str] = set()
    for param in command.params:
        accepted.update(param.opts)
        accepted.update(getattr(param, "secondary_opts", []))
    return accepted


def _unknown_options(command: typer_click.Command, options: list[str]) -> list[str]:
    """Return the options not accepted by ``command`` (``--opt=value`` tolerated)."""
    accepted = _command_option_strings(command)
    return [opt for opt in options if opt.split("=", 1)[0] not in accepted]


@pytest.fixture(scope="module")
def cli_root() -> typer_click.Group:
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(sys, "argv", ["spec-kitty"])
        from specify_cli import _get_app

        root = get_command(_get_app())
    assert isinstance(root, typer_click.Group)
    return root


# === Check 1: command paths AND options resolve ============================

#: Floor so a broken regex or an emptied pack cannot pass this axis vacuously.
_MINIMUM_PROMPT_COMMANDS = 10


def _collect_command_violations(root: typer_click.Group) -> tuple[list[str], int]:
    violations: list[str] = []
    checked = 0
    for prompt in _WALKED_PROMPTS:
        path = _software_dev_steps() / prompt / "prompt.md"
        text = path.read_text(encoding="utf-8")
        for line_number, segment in _code_segments(text):
            for tokens, options in _commands_with_options(segment):
                checked += 1
                leaf, unresolved = _resolve_leaf(root, tokens)
                where = f"{prompt}/prompt.md:{line_number}"
                if leaf is None:
                    violations.append(f"{where}: unresolved command `spec-kitty {unresolved}`")
                    continue
                for bad in _unknown_options(leaf, options):
                    violations.append(f"{where}: `spec-kitty {' '.join(tokens)}` has no option {bad!r}")
    return violations, checked


def test_prompt_commands_and_options_resolve(cli_root: typer_click.Group) -> None:
    violations, checked = _collect_command_violations(cli_root)
    assert checked >= _MINIMUM_PROMPT_COMMANDS, (
        f"Only checked {checked} spec-kitty commands across the walked prompts (expected >= {_MINIMUM_PROMPT_COMMANDS}); the collector or pack root may be broken."
    )
    assert violations == [], "Software-dev prompts name CLI commands/options that do not exist:\n" + "\n".join(violations)


# === Check 2: rendered step-contract commands parse ========================


def _software_dev_command_steps() -> list[tuple[str, MissionStepContractStep]]:
    """Return ``(contract_id, step)`` for each walked software-dev command step."""
    repo = MissionStepContractRepository(built_in_dir=_pack_root() / "missions" / "built_in_step_contracts")
    found: list[tuple[str, MissionStepContractStep]] = []
    contracts: list[MissionStepContract] = list(repo.all())
    for contract in contracts:
        if contract.mission != "software-dev" or contract.action not in _WALKED_CONTRACT_ACTIONS:
            continue
        for step in contract.steps:
            if (step.command or "").strip().startswith("spec-kitty "):
                found.append((contract.id, step))
    return found


def _render_declared_command(step: MissionStepContractStep) -> str:
    """Render ``step`` through the executor's own renderer (command + inputs)."""
    executor = object.__new__(StepContractExecutor)
    rendered: str = executor._render_declared_command(step)
    return rendered


def _collect_contract_violations(root: typer_click.Group) -> tuple[list[str], int]:
    violations: list[str] = []
    steps = _software_dev_command_steps()
    for contract_id, step in steps:
        rendered = _render_declared_command(step)
        argv = shlex.split(rendered)
        assert argv and argv[0] == "spec-kitty"
        leaf, unresolved = _resolve_leaf(root, argv[1:])
        where = f"{contract_id}:{step.id}"
        if leaf is None:
            violations.append(f"{where}: unresolved command `spec-kitty {unresolved}`")
            continue
        options = [tok for tok in argv[1:] if tok.startswith("--")]
        for bad in _unknown_options(leaf, options):
            violations.append(f"{where}: rendered `{rendered}` has no option {bad!r}")
    return violations, len(steps)


def test_rendered_step_contract_commands_parse(cli_root: typer_click.Group) -> None:
    violations, checked = _collect_contract_violations(cli_root)
    assert checked >= 1, "discovered no software-dev step-contract commands to render"
    assert violations == [], "Rendered software-dev step-contract commands do not parse:\n" + "\n".join(violations)


# === Check 3: "next advances to X" claims match runtime order ==============

#: Workflow nouns that normalize to a runtime template step id.
_RUNTIME_STEP_ALIASES: dict[str, str] = {
    "discovery": "discovery",
    "research": "discovery",
    "specify": "specify",
    "specification": "specify",
    "plan": "plan",
    "planning": "plan",
    "tasks": "tasks",
    "analyze": "analyze",
    "analysis": "analyze",
    "implement": "implement",
    "implementation": "implement",
    "review": "review",
    "accept": "accept",
    "acceptance": "accept",
}

#: Concrete workflow actions that are deliberately NOT runtime `next` steps;
#: a claim that `next` advances to one of these is always a violation (FR-022).
_NON_STEP_TARGETS: frozenset[str] = frozenset({"consolidate", "consolidation", "merge"})

#: The prompt directory that is a sub-step of a runtime step (not its own step).
_PROMPT_TO_RUNTIME_STEP: dict[str, str] = {
    "implement": "implement",
    "review": "review",
    "accept": "accept",
    "tasks-finalize": "tasks",
}

_NEXT_ADVANCE = re.compile(
    r"spec-kitty\s+next\b[^.\n]*?\badvances?\s+to\s+(?:the\s+)?([a-z][\w-]*)",
    re.IGNORECASE,
)


def _runtime_step_order() -> list[str]:
    """Return the ordered runtime step ids from ``mission-runtime.yaml``."""
    from ruamel.yaml import YAML

    path = _pack_root() / "missions" / "software-dev" / "mission-runtime.yaml"
    data = YAML(typ="safe").load(path.read_text(encoding="utf-8"))
    return [str(step["id"]) for step in data["steps"]]


def _runtime_successor(order: list[str], step_id: str) -> str | None:
    """Return the step that runs after ``step_id``, or ``None`` if it is last."""
    if step_id not in order:
        return None
    index = order.index(step_id)
    return order[index + 1] if index + 1 < len(order) else None


def _classify_next_target(target_word: str, successor: str | None) -> str | None:
    """Return a violation reason for a ``next`` target word, or ``None`` if valid.

    A target that names a runtime step must equal the successor; a target that
    names a non-step action is always invalid; any other word is generic prose.
    """
    lowered = target_word.lower()
    canonical = _RUNTIME_STEP_ALIASES.get(lowered)
    if canonical is not None:
        if canonical == successor:
            return None
        return f"claims `next` advances to {target_word!r}, but the runtime successor is {successor!r}"
    if lowered in _NON_STEP_TARGETS:
        return f"claims `next` advances to {target_word!r}, which is not a runtime step"
    return None


def _collect_next_claim_violations() -> list[str]:
    order = _runtime_step_order()
    violations: list[str] = []
    for prompt in _WALKED_PROMPTS:
        text = (_software_dev_steps() / prompt / "prompt.md").read_text(encoding="utf-8")
        successor = _runtime_successor(order, _PROMPT_TO_RUNTIME_STEP[prompt])
        for line_number, line in enumerate(text.splitlines(), start=1):
            for match in _NEXT_ADVANCE.finditer(line):
                reason = _classify_next_target(match.group(1), successor)
                if reason is not None:
                    violations.append(f"{prompt}/prompt.md:{line_number}: {reason}")
    return violations


def test_next_advance_claims_match_runtime_order() -> None:
    violations = _collect_next_claim_violations()
    assert violations == [], "Software-dev prompts misstate the runtime `next` order:\n" + "\n".join(violations)


# === Check 4: consumer paths resolve against a `spec-kitty init` fixture ====

#: The project roots spec-kitty itself owns and creates in a consumer project;
#: a path under one of these must resolve (in the init fixture) or match the
#: explicit placeholder allowlist below.
_OWNED_ROOTS: tuple[str, ...] = (".kittify/", "kitty-specs/")

#: EXPLICIT allowlist of placeholder/post-init consumer-path forms (C-003/C12).
#: ``kitty-specs/<mission>/...`` is a per-mission placeholder (no mission dir
#: exists at init); the compiled charter is produced by the charter interview,
#: not by ``init``.
_CONSUMER_PATH_ALLOWLIST: frozenset[str] = frozenset(
    {
        "kitty-specs/<mission>",
        ".kittify/charter/charter.md",
    }
)

_INTERNAL_PATH = re.compile(r"(?<![\w-])src/specify_cli(?:/|\b)")
_PATH_TOKEN = re.compile(r"(?<![\w.`])((?:\.kittify|kitty-specs)/[\w./<>{}\-]+)")
_PLACEHOLDER_SEGMENT = re.compile(r"^(?:<[^>]+>|\{[^}]+\}|WP[\w-]+|\*)$")


def _path_is_allowlisted(token: str) -> bool:
    """True when ``token`` matches an explicit placeholder/post-init form."""
    if token in _CONSUMER_PATH_ALLOWLIST:
        return True
    segments = token.split("/")
    # ``kitty-specs/<mission>/...`` -- a mission-scoped placeholder path.
    return len(segments) >= 2 and segments[0] == "kitty-specs" and _PLACEHOLDER_SEGMENT.match(segments[1]) is not None


def _path_resolves(token: str, init_root: Path) -> bool:
    """True when ``token`` exists in the init fixture (ignoring placeholder tails)."""
    probe = init_root
    for segment in token.split("/"):
        if _PLACEHOLDER_SEGMENT.match(segment):
            return probe.exists()
        probe = probe / segment
    return probe.exists()


def _collect_consumer_path_violations(init_root: Path) -> list[str]:
    violations: list[str] = []
    for prompt in _WALKED_PROMPTS:
        text = (_software_dev_steps() / prompt / "prompt.md").read_text(encoding="utf-8")
        for line_number, segment in _code_segments(text):
            where = f"{prompt}/prompt.md:{line_number}"
            if _INTERNAL_PATH.search(segment):
                violations.append(f"{where}: leaks an internal `src/specify_cli/...` path")
            for match in _PATH_TOKEN.finditer(segment):
                token = match.group(1).rstrip("/.,);:")
                if token.startswith(_OWNED_ROOTS):
                    if _path_is_allowlisted(token) or _path_resolves(token, init_root):
                        continue
                    violations.append(f"{where}: consumer path `{token}` does not resolve")
    return violations


@pytest.fixture(scope="module")
def init_fixture(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A real ``spec-kitty init`` project tree, scaffolded once for this module."""
    project = tmp_path_factory.mktemp("prompt-walk-init") / "consumer"
    result = subprocess.run(
        [sys.executable, "-m", "specify_cli.__init__", "init", "--ai", "claude", "--non-interactive", str(project)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert project.exists(), f"spec-kitty init did not scaffold a project:\n{result.stdout}\n{result.stderr}"
    return project


def test_consumer_paths_resolve_against_init_fixture(init_fixture: Path) -> None:
    violations = _collect_consumer_path_violations(init_fixture)
    assert violations == [], "Software-dev prompts name consumer paths that do not resolve:\n" + "\n".join(violations)


# === Helper self-tests (every new branch/helper has a focused test) =========


def test_commands_with_options_scopes_to_shell_clause() -> None:
    segment = "spec-kitty agent profile list --json | grep reviewer"
    ((tokens, options),) = list(_commands_with_options(segment))
    assert tokens == ["agent", "profile", "list"]
    assert options == ["--json"]  # the piped `grep` contributes nothing


def test_commands_with_options_ignores_non_spec_kitty() -> None:
    assert list(_commands_with_options("git diff --name-only HEAD")) == []


def test_resolve_leaf_reports_unresolved_prefix(cli_root: typer_click.Group) -> None:
    leaf, unresolved = _resolve_leaf(cli_root, ["agent", "tasks", "transition", "wp01"])
    assert leaf is None
    assert unresolved == "agent tasks transition"


def test_unknown_options_flags_missing_and_tolerates_equals(cli_root: typer_click.Group) -> None:
    leaf, _ = _resolve_leaf(cli_root, ["accept"])
    assert leaf is not None
    assert _unknown_options(leaf, ["--mission=x"]) == []
    assert _unknown_options(leaf, ["--no-such-flag"]) == ["--no-such-flag"]


def test_runtime_successor_order() -> None:
    order = _runtime_step_order()
    assert _runtime_successor(order, "implement") == "review"
    assert _runtime_successor(order, "tasks") == "analyze"
    assert _runtime_successor(order, "accept") is None


def test_classify_next_target_cases() -> None:
    # correct successor
    assert _classify_next_target("review", "review") is None
    # generic prose ("advance to the next phase" -> captured "next")
    assert _classify_next_target("next", "accept") is None
    # wrong named step (tasks -> analyze, not implementation)
    assert _classify_next_target("implementation", "analyze") is not None
    # non-step action is never a valid `next` target
    assert _classify_next_target("consolidate", None) is not None


def test_path_allowlist_and_resolution(init_fixture: Path) -> None:
    assert _path_is_allowlisted("kitty-specs/<mission>/reasons-canvas.md")
    assert _path_is_allowlisted(".kittify/charter/charter.md")
    assert not _path_is_allowlisted(".kittify/charter-packs/bogus.yaml")
    assert _path_resolves(".kittify/config.yaml", init_fixture)
    assert not _path_resolves(".kittify/charter/charter.md", init_fixture)
