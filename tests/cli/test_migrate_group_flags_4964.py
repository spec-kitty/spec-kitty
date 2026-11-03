"""Acceptance tests for ``spec-kitty migrate --dry-run/--force/--verbose <sub>`` (#4964).

Issue #4964: the ``migrate`` group callback declared ``--dry-run``/``--verbose``/
``--force`` but, whenever a subcommand was invoked, returned immediately
(``if ctx.invoked_subcommand is not None: return``) without looking at them —
so ``spec-kitty migrate --dry-run backfill-runtime-state`` silently dropped
``--dry-run`` and ran the REAL migration, exit 0.

The group callback now forwards a
group flag to the subcommand via ``ctx.default_map`` when the subcommand
declares the same flag name, or refuses with a usage error (exit 2) before
the subcommand runs — raised from the click universe typer actually uses
(real ``click`` on typer <=0.25, vendored ``typer._click`` on 0.26+).

Test strategy (two tiers):

* **Tier 1 — generic, parametrised over the LIVE registry.** For every
  currently-registered ``migrate`` subcommand crossed with every group flag
  (``--dry-run``/``--verbose``/``-v``/``--force``), this asserts the seam's
  forward-or-refuse contract in isolation from each subcommand's own
  migration logic: when the subcommand declares the flag, its own CLI
  entry-point function is spied and must receive the flag's value truthily;
  when it does not, the group must refuse with exit 2 and a message naming
  the flag, the subcommand, and a ``--help`` next action. Because
  this discovers subcommands and their declared params from the live
  ``typer.Typer`` app rather than a hardcoded list, a future subcommand is
  covered automatically.
* **Tier 2 — one real, non-spied, end-to-end positive control** (the
  issue's own repro, ``backfill-runtime-state``, over the shared
  legacy-mission fixture): ``--dry-run`` truly writes nothing, and the
  non-dry-run form on the SAME fixture DOES write — proving the fixture is
  migratable and Tier 1's spy-based proof is not masking a corpus that had
  nothing to migrate in the first place.
"""

from __future__ import annotations

import enum
import json
import os
import re
import subprocess
import sys
import types
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import patch

import click
import pytest
from click.testing import CliRunner as ClickCliRunner
from click.testing import Result
from typer.main import get_command
from typer.testing import CliRunner

from specify_cli.cli.commands import migrate_cmd
from specify_cli.cli.commands.migrate_cmd import app as migrate_app
from specify_cli.core.paths import WorkspaceRootNotFound, git_ceiling_dirs, resolve_canonical_root
from tests import _click_universe as typer_click
from tests.unit.migration._backfill_fixture import build_mission

pytestmark = [pytest.mark.integration]

runner = CliRunner()
click_runner = ClickCliRunner()

_LOCATE = "specify_cli.cli.commands.migrate_cmd.locate_project_root"

#: Unicode Box Drawing block — used only to strip the wrap-point borders a
#: Rich/Typer error Panel inserts mid sentence (see ``_flatten``).
_BOX_DRAWING_CHARS = re.compile(r"[─-╿]")


# ---------------------------------------------------------------------------
# Hard filesystem isolation.
#
# On unfixed source the group callback's refusal does not fire, so a refusal
# case runs the subcommand's REAL body, and an unpatched
# ``locate_project_root()`` resolves to whatever repository the process cwd
# is inside — from a git worktree, the main checkout — and mutates its real
# ``kitty-specs/*`` files.
#
# Every test in this module therefore runs with cwd inside a scratch
# directory under ``tmp_path``, and ``locate_project_root`` is poisoned by
# default to a callable that fails loudly unless a test explicitly overrides
# it with a path under its own ``tmp_path`` — so a test that forgets to patch
# project-root resolution fails immediately instead of touching a real repo.
# ---------------------------------------------------------------------------


def _poisoned_locate_project_root(*_args: Any, **_kwargs: Any) -> Path:
    raise AssertionError(
        "locate_project_root() was called without an explicit test override. "
        "Every test in test_migrate_group_flags_4964.py must patch _LOCATE to "
        "a path under its own tmp_path before invoking the CLI (hard "
        "isolation rule) — never let the "
        "real resolver run, which would touch whatever real repository the "
        "process cwd happens to be inside."
    )


#: The repository checkout this test file lives in, which it must never touch.
_REAL_REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _hard_repo_isolation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    resolved_tmp = tmp_path.resolve()
    assert not resolved_tmp.is_relative_to(_REAL_REPO_ROOT), (
        f"pytest's own tmp_path ({resolved_tmp}) resolves inside the real "
        f"repository ({_REAL_REPO_ROOT}) — refusing to run any test in this "
        "module (hard isolation rule)."
    )
    scratch_cwd = tmp_path / "cwd"
    scratch_cwd.mkdir()
    monkeypatch.chdir(scratch_cwd)
    monkeypatch.setattr(_LOCATE, _poisoned_locate_project_root)
    # Pin the root walk too (#6957): the cutover's PRIMARY-home resolution reads
    # ``core.paths.resolve_canonical_root``, not ``locate_project_root``, so an
    # ambient repository enclosing the platform temp root would capture it.
    monkeypatch.setenv(
        "GIT_CEILING_DIRECTORIES",
        _append_ceiling(os.environ.get("GIT_CEILING_DIRECTORIES", ""), resolved_tmp),
    )
    yield


# ---------------------------------------------------------------------------
# Root-walk isolation (#6957).
#
# Poisoning ``locate_project_root`` covers the CLI's project resolution but not
# the *root walk* the migration cutover uses: ``runtime_state_cutover.
# _resolve_primary_home_or_degrade`` calls ``core.paths.resolve_canonical_root``,
# which ascends from the fixture to the first ancestor holding ``.git``. On a host
# whose platform temp root sits inside a repository (a stray ``/tmp/.git``), that
# ancestor is the foreign repository, so ``resolve_artifact_surface`` reports
# ``<repo>/kitty-specs/<slug>`` and ``_flip_phase`` fails closed against the real
# write target — the red in #6957.
#
# The harness already installs a process-wide ``GIT_CEILING_DIRECTORIES`` from the
# run basetemp (#7022, tests/_support/git_ceiling.py), which bounds that walk; a
# test that does not inherit it "sets the variable itself". This module therefore
# pins its OWN root as a ceiling in the autouse fixture above, so it is hermetic
# on every runner rather than only where the harness is installed.
# ---------------------------------------------------------------------------


def _append_ceiling(existing: str, entry: Path) -> str:
    """Return *existing* with *entry* appended as an absolute discovery ceiling.

    Policy, so the harness is never disturbed: the value already there is kept
    verbatim — a leading empty entry is meaningful to git — and the new absolute
    entry is appended to it. Idempotency is checked against *absolute* entries
    only, because that is what :func:`specify_cli.core.paths.git_ceiling_dirs`
    reads: it ignores relative entries and resolves every absolute one. A
    relative ``.`` that happens to resolve here is therefore not a ceiling for
    the root walks, and must not suppress the absolute one this module needs.

    Note the two readers: git does not resolve entries that follow a leading
    empty entry, while ``git_ceiling_dirs`` resolves every absolute entry and
    stops a walk at a listed directory even when that directory holds no ``.git``.
    Both agree on the entry appended here, because it is already absolute and
    already resolved.
    """
    resolved = str(entry.resolve())
    listed = {str(Path(part).resolve()) for part in existing.split(os.pathsep) if part and Path(part).is_absolute()}
    if resolved in listed:
        return existing
    return f"{existing}{os.pathsep}{resolved}" if existing else resolved


def test_module_pins_git_discovery_to_its_own_test_root(tmp_path: Path) -> None:
    """The module owns its ceiling: discovery can never leave this test's root.

    Host-independent standing invariant — it fails on every host without the
    fixture's ceiling append (#6957), so it is the always-on half of the guard.
    """
    ceilings = git_ceiling_dirs()
    assert tmp_path.resolve() in ceilings, f"this module must pin its own root as a git discovery ceiling; ceilings={sorted(ceilings)}"

    # Positive control on the same fixture (FR-005): a repository the test
    # creates *inside* its own root sits below the ceiling and must stay
    # discoverable, so the pin cannot break fixtures that root a project here.
    nested = tmp_path / "nested"
    (nested / ".git").mkdir(parents=True)
    mission = nested / "kitty-specs" / "042-demo"
    mission.mkdir(parents=True)
    assert resolve_canonical_root(mission) == nested.resolve()


def test_append_ceiling_is_append_only_and_idempotent(tmp_path: Path) -> None:
    """An existing value is kept verbatim and an already-listed entry is not repeated."""
    tmp = tmp_path.resolve()
    assert _append_ceiling("", tmp) == str(tmp)
    assert _append_ceiling(f"{os.pathsep}/elsewhere", tmp) == f"{os.pathsep}/elsewhere{os.pathsep}{tmp}"
    once = _append_ceiling("/elsewhere", tmp)
    assert _append_ceiling(once, tmp) == once


def test_append_ceiling_ignores_relative_entries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A relative entry is not a ceiling for the root walks, so it cannot stand in for one.

    ``git_ceiling_dirs`` drops relative entries. The regression this pins: with cwd
    at the ceiling, ``.`` *resolves* to this test root, so a helper that dedupes
    against resolved relative entries returns ``"."`` unchanged and leaves the walk
    unbounded while claiming a ceiling exists.
    """
    tmp = tmp_path.resolve()
    monkeypatch.chdir(tmp)  # make "." resolve to the very root we are asking for
    assert Path(".").resolve() == tmp
    assert _append_ceiling(".", tmp) == f".{os.pathsep}{tmp}"
    mixed = f"{tmp}{os.pathsep}.."
    assert _append_ceiling(mixed, tmp) == mixed  # the absolute entry already listed; the relative one is not a ceiling


def test_append_ceiling_dedupes_an_equivalent_symlinked_entry(tmp_path: Path) -> None:
    """A symlinked alias of the ceiling already listed is not appended twice."""
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    assert _append_ceiling(str(link), real) == str(link)


def test_a_repository_above_the_ceiling_cannot_capture_the_walk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The ceiling mechanism itself, on a shape every host can build (#6957).

    ``test_positive_control_survives_a_temp_root_inside_a_repository`` needs a host whose
    platform temp root sits inside a repository to observe the leak, so it skips on CI. This
    guard builds that shape instead: an enclosing repository above a ceiling and a Mission
    directory below it. With the ceiling in force the walk must stop below the repository and
    fail; with the ceiling removed the same walk is captured by the enclosing repository --
    exactly the leak the ceiling exists to prevent.
    """
    base = tmp_path / "base"
    (base / ".git").mkdir(parents=True)  # an enclosing repository, as a stray /tmp/.git would be
    deep = base / "deep"
    mission = deep / "inner" / "kitty-specs" / "042-demo"
    mission.mkdir(parents=True)

    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(deep))
    with pytest.raises(WorkspaceRootNotFound):
        resolve_canonical_root(mission)

    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", "")
    assert resolve_canonical_root(mission) == base.resolve()


def test_positive_control_survives_a_temp_root_inside_a_repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#6957's host shape: the platform temp root sits inside a repository.

    The harness's process-wide ceiling is deliberately absent here — only the pin
    this module's autouse fixture installed is in force — so the probe runs the
    production CLI seam as it would on a runner that installs nothing.

    Half-by-half: this test takes the pinned entry *from the fixture's own
    environment* and fails if the fixture never installed one, so reverting the
    fixture wiring reds it independently of Guard A. Where no repository encloses
    the temp root the leak cannot be observed, so the probe skips with a reason
    instead of passing vacuously (acceptance-criteria-non-vacuity).
    """
    feature_dir = build_mission(tmp_path)
    # What the autouse fixture installed, captured before the ambient value is cleared.
    installed_value = os.environ.get("GIT_CEILING_DIRECTORIES", "")

    # Non-vacuity, same fixture: with no ceiling at all, the production resolver
    # escapes into whichever repository encloses the temp root (the leak).
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", "")
    try:
        enclosing = resolve_canonical_root(feature_dir)
    except WorkspaceRootNotFound:
        pytest.skip(
            "no repository encloses the platform temp root: #6957's host shape is absent, so this probe cannot observe the leak (Guard A still pins the invariant)"
        )
    if enclosing.is_relative_to(tmp_path.resolve()):
        pytest.skip(
            f"the enclosing repository ({enclosing}) is inside this test's root, so the module ceiling cannot mask the leak (Guard A still pins the invariant)"
        )

    # The pin must come from the module fixture, never from this test. Only an
    # absolute entry is a ceiling for ``git_ceiling_dirs``, so a relative entry
    # that happens to resolve here must not be mistaken for the fixture's pin.
    installed = [part for part in installed_value.split(os.pathsep) if part and Path(part).is_absolute() and Path(part).resolve() == tmp_path.resolve()]
    assert installed, f"the autouse fixture did not pin this test's own root as a git discovery ceiling; GIT_CEILING_DIRECTORIES={installed_value!r}"

    # With only that pin in force the same walk stops at the test root, which is
    # what degrades the PRIMARY-home resolution back to the fixture's target.
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", installed[-1])
    with pytest.raises(WorkspaceRootNotFound):
        resolve_canonical_root(feature_dir)

    # Production path: the real non-dry-run control still flips the fixture.
    with patch(_LOCATE, return_value=tmp_path):
        result = _invoke(["backfill-runtime-state", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["dry_run"] is False
    assert payload["summary"]["flipped"] == 1, payload
    assert json.loads((feature_dir / "meta.json").read_text())["status_phase"] == "1"


def test_hard_isolation_guard_is_non_vacuous() -> None:
    """Proves the ``_hard_repo_isolation`` poison actually fires (per
    DIRECTIVE_043 / charter Standing Order #5: a gate that cannot fail is
    not a gate) — a subcommand that calls ``locate_project_root()`` without
    a test-local override must blow up immediately rather than silently
    falling through to the real resolver."""
    result = _invoke(["backfill-identity"])
    assert result.exit_code != 0
    assert isinstance(result.exception, AssertionError)
    assert "locate_project_root() was called without an explicit test override" in str(result.exception)


# ---------------------------------------------------------------------------
# Live-registry introspection helpers (no hardcoded subcommand list).
# ---------------------------------------------------------------------------


def _click_group() -> typer_click.Group:
    group = get_command(migrate_app)
    assert isinstance(group, typer_click.Group)
    return group


def _registered_subcommand_names() -> list[str]:
    return sorted(_click_group().commands)


def _declares_param(cmd: typer_click.Command, param_name: str) -> bool:
    return any(param.name == param_name for param in cmd.params)


def _required_arg_values(cmd: typer_click.Command) -> list[str]:
    """Minimal CLI tokens satisfying *cmd*'s REQUIRED options.

    Click parses (and enforces required-ness on) a subcommand's own params
    before its callback ever runs — including a spied-out callback (Tier 1)
    — so a required option must be supplied regardless of which callback is
    installed. Values are dummy placeholders; a spied callback never reads
    them, and a real one (Tier 2) supplies its own real values instead of
    calling this helper.
    """
    args: list[str] = []
    for param in cmd.params:
        if isinstance(param, typer_click.Option) and param.required:
            args.extend([param.opts[0], f"dummy-{param.name}"])
    return args


@contextmanager
def _spy_on_subcommand(name: str) -> Iterator[tuple[typer_click.Group, list[dict[str, Any]]]]:
    """Build a fresh typer_click.Group from the live app and replace subcommand
    *name*'s ``typer_click.Command.callback`` with a recorder.

    Deliberately does NOT patch ``CommandInfo.callback`` on
    ``migrate_app.registered_commands``: typer derives a subcommand's own
    Click params (``--dry-run`` etc.) from that same callback's *type
    signature* at group-build time (``get_command_from_info`` ->
    ``get_params_convertors_ctx_param_name_from_function``), so replacing it
    with a generic ``**kwargs`` recorder there would silently erase the very
    params under test. Instead this builds the group ONCE via
    ``typer.main.get_command`` (params derived from the REAL signature),
    then mutates the already-built ``typer_click.Command.callback`` in place —
    Click invokes whatever object sits at ``.callback`` at dispatch time
    without re-deriving params from it. The caller must invoke this SAME
    returned group (not re-fetch one via ``typer.testing.CliRunner``, which
    rebuilds a fresh group from ``registered_commands`` — i.e. the
    unpatched originals — on every call).
    """
    group = get_command(migrate_app)
    assert isinstance(group, typer_click.Group)
    command = group.commands[name]
    original = command.callback
    calls: list[dict[str, Any]] = []

    def _spy(**kwargs: Any) -> None:
        calls.append(kwargs)

    command.callback = _spy
    try:
        yield group, calls
    finally:
        command.callback = original


def _invoke(args: list[str]) -> Result:
    return runner.invoke(migrate_app, args)


def _flatten(text: str) -> str:
    """Collapse whitespace/newlines and strip box-drawing glyphs so a wrapped
    rich error panel's message can still be matched as one contiguous
    phrase. Typer/rich wraps its ``UsageError`` panel at the console width,
    inserting a right border + newline + left border (``… migrate │\\n│
    backfill-identity …``) mid sentence — collapsing whitespace alone still
    leaves the ``│`` glyph as a token between the wrapped words."""
    return " ".join(_BOX_DRAWING_CHARS.sub(" ", text).split())


# ---------------------------------------------------------------------------
# Tier 1: generic (subcommand x group flag) forward-or-refuse matrix.
# ---------------------------------------------------------------------------

#: (CLI token to pass, canonical option string used in the refusal message,
#: the param name it binds to on both the group and a declaring subcommand).
_GROUP_FLAG_CASES: tuple[tuple[str, str, str], ...] = (
    ("--dry-run", "--dry-run", "dry_run"),
    ("--verbose", "-v/--verbose", "verbose"),
    ("-v", "-v/--verbose", "verbose"),
    ("--force", "--force", "force"),
)


def _matrix_ids() -> list[str]:
    ids = []
    for sub_name in _registered_subcommand_names():
        for cli_token, _canonical, param_name in _GROUP_FLAG_CASES:
            ids.append(f"{sub_name}-{cli_token}-{param_name}")
    return ids


def _matrix_params() -> list[tuple[str, str, str, str]]:
    params = []
    for sub_name in _registered_subcommand_names():
        for cli_token, canonical, param_name in _GROUP_FLAG_CASES:
            params.append((sub_name, cli_token, canonical, param_name))
    return params


@pytest.mark.parametrize(
    "sub_name,cli_token,canonical_flag,param_name",
    _matrix_params(),
    ids=_matrix_ids(),
)
def test_group_flag_forwarded_or_refused(sub_name: str, cli_token: str, canonical_flag: str, param_name: str) -> None:
    cmd = _click_group().commands[sub_name]
    extra_args = _required_arg_values(cmd)
    declares = _declares_param(cmd, param_name)

    with _spy_on_subcommand(sub_name) as (group, calls):
        result = click_runner.invoke(group, [cli_token, sub_name, *extra_args])

    if declares:
        # Forwarded — the subcommand's own entry point actually
        # receives the flag truthily (not merely "nothing crashed").
        assert result.exit_code == 0, result.output
        assert len(calls) == 1, f"expected exactly one call to {sub_name!r}, got {calls}"
        assert calls[0].get(param_name) is True, calls[0]
    else:
        # Refused before anything runs. The message names the
        # flag (every spelling, so the one typed is present), the subcommand,
        # and a concrete next action — never a trailing form the subcommand
        # does not declare (it cannot: this is the refusal branch).
        assert result.exit_code == 2, result.output
        assert calls == [], f"{sub_name!r} must not run when a group flag it does not declare is refused"
        flat_output = _flatten(result.output)
        assert f"'{canonical_flag}'" in flat_output, result.output
        assert cli_token in flat_output, result.output
        assert sub_name in flat_output, result.output
        assert f"spec-kitty migrate {sub_name} --help" in flat_output, result.output
        assert f"migrate {sub_name} {cli_token}" not in flat_output, result.output


# ---------------------------------------------------------------------------
# Tier 2: one real, non-spied, end-to-end positive control.
# ---------------------------------------------------------------------------


def test_dry_run_forwarding_writes_nothing_on_real_legacy_fixture(tmp_path: Path) -> None:
    feature_dir = build_mission(tmp_path)
    events_before = (feature_dir / "status.events.jsonl").read_bytes()
    meta_before = (feature_dir / "meta.json").read_bytes()

    with patch(_LOCATE, return_value=tmp_path):
        result = _invoke(["--dry-run", "backfill-runtime-state", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["dry_run"] is True
    assert payload["summary"]["would_seed"] == 1
    assert payload["summary"]["flipped"] == 0
    assert (feature_dir / "status.events.jsonl").read_bytes() == events_before
    assert (feature_dir / "meta.json").read_bytes() == meta_before
    assert "status_phase" not in json.loads(meta_before)


def test_non_dry_run_positive_control_writes_on_same_fixture(tmp_path: Path) -> None:
    """Proves the Tier-2 fixture is genuinely migratable — a dry-run alone
    leaving the tree untouched is vacuous evidence for a fixture with
    nothing to migrate; this is the non-dry-run control on the SAME corpus.
    """
    feature_dir = build_mission(tmp_path)

    with patch(_LOCATE, return_value=tmp_path):
        result = _invoke(["backfill-runtime-state", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["dry_run"] is False
    assert payload["summary"]["flipped"] == 1
    assert json.loads((feature_dir / "meta.json").read_text())["status_phase"] == "1"


# ---------------------------------------------------------------------------
# Ratchets — pre-existing forms whose behaviour must NOT change.
#
# No subcommand declares ``--no-dry-run`` today, so "a trailing
# ``--no-dry-run`` wins over a forwarded group ``--dry-run``" has nothing to
# exercise; add that ratchet when a subcommand gains the negative form.
# ---------------------------------------------------------------------------


def test_trailing_dry_run_form_unchanged(tmp_path: Path) -> None:
    """``migrate <sub> --dry-run`` (trailing) is unaffected by group-flag forwarding."""
    feature_dir = build_mission(tmp_path)
    events_before = (feature_dir / "status.events.jsonl").read_bytes()

    with patch(_LOCATE, return_value=tmp_path):
        result = _invoke(["backfill-runtime-state", "--dry-run", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["dry_run"] is True
    assert (feature_dir / "status.events.jsonl").read_bytes() == events_before


def test_no_subcommand_dry_run_preview_path_unchanged(tmp_path: Path) -> None:
    """``migrate --dry-run`` with no subcommand still runs its own preview
    body — not routed through the forward-or-refuse helper at all
    (``ctx.invoked_subcommand is None``).
    """
    (tmp_path / ".kittify").mkdir()

    with patch(_LOCATE, return_value=tmp_path):
        result = _invoke(["--dry-run"])

    assert result.exit_code == 0, result.output
    assert "Step 1:" in result.output
    assert "no changes in dry-run" in result.output


# ---------------------------------------------------------------------------
# Issue-repro refusals through the typer app (rich error panel rendering).
# ---------------------------------------------------------------------------


def test_dry_run_before_repin_hooks_is_refused() -> None:
    result = _invoke(["--dry-run", "repin-hooks"])
    assert result.exit_code == 2, result.output
    flat_output = _flatten(result.output)
    assert "--dry-run" in flat_output
    assert "repin-hooks" in flat_output
    # The next action is the subcommand's --help, never a trailing form the
    # subcommand does not declare.
    assert "spec-kitty migrate repin-hooks --help" in flat_output
    assert "migrate repin-hooks --dry-run" not in flat_output


def test_force_before_backfill_runtime_state_is_refused() -> None:
    result = _invoke(["--force", "backfill-runtime-state"])
    assert result.exit_code == 2, result.output
    flat_output = _flatten(result.output)
    assert "--force" in flat_output
    assert "backfill-runtime-state" in flat_output


def test_verbose_short_flag_before_backfill_runtime_state_is_refused() -> None:
    result = _invoke(["-v", "backfill-runtime-state"])
    assert result.exit_code == 2, result.output
    flat_output = _flatten(result.output)
    # Reported with its short form too, so the spelling typed is recognisable.
    assert "-v/--verbose" in flat_output
    assert "backfill-runtime-state" in flat_output


# ---------------------------------------------------------------------------
# The helper must be click-universe agnostic.
#
# ``pyproject`` allows ``typer>=0.24.1,<0.28``; typer 0.26+ vendors its own
# click (``typer._click``), whose ``Group``/``ParameterSource``/``UsageError``
# share no classes with the real ``click`` package. A helper that checks
# ``isinstance(ctx.command, click.Group)`` or compares against
# ``click.core.ParameterSource.COMMANDLINE`` silently no-ops under a vendored
# click, so ``migrate --dry-run <sub>`` ran the REAL migration with exit 0.
# The fakes below are deliberately NOT real-click objects: they stand in for
# a vendored click universe, proving the duck-typed path offline.
# ---------------------------------------------------------------------------

_FAKE_CLICK = "fakevendoredclick"


class _FakeParameterSource(enum.Enum):
    COMMANDLINE = enum.auto()
    DEFAULT = enum.auto()


class _FakeUsageError(Exception):
    def __init__(self, message: str, ctx: Any = None) -> None:
        super().__init__(message)
        self.ctx = ctx


class _FakeClickContext:
    """Stand-in for ``typer._click.core.Context`` (a non-real-click base)."""


_FakeUsageError.__module__ = f"{_FAKE_CLICK}.exceptions"
_FakeClickContext.__module__ = f"{_FAKE_CLICK}.core"
_FakeClickContext.__name__ = "Context"
_FakeClickContext.__qualname__ = "Context"


class _FakeParam:
    def __init__(self, name: str, opts: list[str]) -> None:
        self.name = name
        self.opts = opts


class _FakeCommand:
    def __init__(self, params: list[_FakeParam], subcommands: dict[str, _FakeCommand] | None = None) -> None:
        self.params = params
        self._subcommands = subcommands or {}

    def get_command(self, _ctx: Any, name: str) -> _FakeCommand | None:
        return self._subcommands.get(name)


class _FakeTyperContext(_FakeClickContext):
    def __init__(
        self,
        *,
        sub_name: str | None,
        command: Any,
        params: dict[str, Any],
        sources: dict[str, _FakeParameterSource | None],
    ) -> None:
        self.invoked_subcommand = sub_name
        self.command = command
        self.params = params
        self._sources = sources
        self.default_map: dict[str, Any] | None = None

    def get_parameter_source(self, name: str) -> _FakeParameterSource | None:
        return self._sources.get(name)


_GROUP_PARAMS = [
    _FakeParam("dry_run", ["--dry-run"]),
    _FakeParam("verbose", ["--verbose", "-v"]),
    _FakeParam("force", ["--force"]),
]


@pytest.fixture()
def fake_vendored_click(monkeypatch: pytest.MonkeyPatch) -> None:
    exceptions_module = types.ModuleType(f"{_FAKE_CLICK}.exceptions")
    exceptions_module.__dict__["UsageError"] = _FakeUsageError
    monkeypatch.setitem(sys.modules, f"{_FAKE_CLICK}.exceptions", exceptions_module)


def _fake_ctx(
    sub_name: str | None,
    sub_params: list[_FakeParam],
    *,
    given: dict[str, Any],
    source: _FakeParameterSource | None = _FakeParameterSource.COMMANDLINE,
) -> _FakeTyperContext:
    subs = {} if sub_name is None else {sub_name: _FakeCommand(sub_params)}
    group = _FakeCommand(_GROUP_PARAMS, subs)
    params = {"dry_run": False, "verbose": False, "force": False, **given}
    sources = {name: (source if name in given else _FakeParameterSource.DEFAULT) for name in params}
    return _FakeTyperContext(sub_name=sub_name, command=group, params=params, sources=sources)


def _forward(ctx: Any) -> None:
    """Call the helper with a deliberately non-real-click context."""
    migrate_cmd._forward_or_refuse_group_flags(ctx)


@pytest.mark.usefixtures("fake_vendored_click")
def test_vendored_click_dry_run_is_forwarded_to_declaring_subcommand() -> None:
    ctx = _fake_ctx("backfill-identity", [_FakeParam("dry_run", ["--dry-run"])], given={"dry_run": True})
    _forward(ctx)
    assert ctx.default_map == {"backfill-identity": {"dry_run": True}}


@pytest.mark.usefixtures("fake_vendored_click")
def test_vendored_click_undeclared_flag_raises_the_vendored_usage_error() -> None:
    ctx = _fake_ctx("repin-hooks", [], given={"dry_run": True})
    with pytest.raises(_FakeUsageError) as excinfo:
        _forward(ctx)
    assert excinfo.value.ctx is ctx
    message = str(excinfo.value)
    assert "'--dry-run'" in message
    assert "migrate repin-hooks" in message
    assert "spec-kitty migrate repin-hooks --help" in message
    assert "migrate repin-hooks --dry-run" not in message
    assert ctx.default_map is None


@pytest.mark.usefixtures("fake_vendored_click")
def test_vendored_click_short_verbose_is_reported_with_its_short_form() -> None:
    ctx = _fake_ctx("repin-hooks", [], given={"verbose": True})
    with pytest.raises(_FakeUsageError) as excinfo:
        _forward(ctx)
    assert "'-v/--verbose'" in str(excinfo.value)


@pytest.mark.usefixtures("fake_vendored_click")
def test_vendored_click_non_commandline_sources_are_ignored() -> None:
    for source in (_FakeParameterSource.DEFAULT, None):
        ctx = _fake_ctx("repin-hooks", [], given={"dry_run": True}, source=source)
        _forward(ctx)
        assert ctx.default_map is None


def test_no_subcommand_is_a_no_op() -> None:
    ctx = _fake_ctx(None, [], given={"dry_run": True})
    _forward(ctx)
    assert ctx.default_map is None


def test_command_without_get_command_is_a_no_op() -> None:
    ctx = _fake_ctx("repin-hooks", [], given={"dry_run": True})
    ctx.command = object()
    _forward(ctx)
    assert ctx.default_map is None


def test_unknown_subcommand_is_a_no_op() -> None:
    ctx = _fake_ctx("repin-hooks", [], given={"dry_run": True})
    ctx.invoked_subcommand = "not-registered"
    _forward(ctx)
    assert ctx.default_map is None


def test_usage_error_class_falls_back_to_real_click_without_a_click_context() -> None:
    assert migrate_cmd._usage_error_class(object()) is click.UsageError  # noqa: TID251 — test names the click universe of the command it built itself, or deliberately the standalone-click spelling


def test_usage_error_class_resolves_the_commands_own_click_for_a_real_context() -> None:
    ctx = typer_click.Context(_click_group())
    assert migrate_cmd._usage_error_class(ctx) is typer_click.UsageError


def test_usage_error_class_skips_a_core_module_without_exceptions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delitem(sys.modules, f"{_FAKE_CLICK}.exceptions", raising=False)
    assert migrate_cmd._usage_error_class(_fake_ctx(None, [], given={})) is click.UsageError  # noqa: TID251 — test names the click universe of the command it built itself, or deliberately the standalone-click spelling


# ---------------------------------------------------------------------------
# The same contract through the real CLI entry point in the
# session test venv. ``tests/conftest.py::test_venv`` builds that venv with
# ``pip install -e`` — i.e. the freshest typer the declared range admits
# (0.27.x, vendored ``typer._click``) whenever the index is reachable, and an
# offline shim over the host interpreter's packages otherwise. The in-process
# tests above run under the locked typer; this subprocess pair is what
# exercises the vendored-click era whenever that venv has it.
# ---------------------------------------------------------------------------


@pytest.mark.non_sandbox
def test_real_cli_refuses_group_dry_run_before_repin_hooks(tmp_path: Path, run_cli: Any) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    subprocess.run(["git", "init", "-q", str(project)], check=True)
    (project / ".kittify").mkdir()
    hook = project / ".git" / "hooks" / "pre-commit"

    result = run_cli(project, "migrate", "--dry-run", "repin-hooks")

    assert result.returncode == 2, result.stdout + result.stderr
    assert "repin-hooks" in _flatten(result.stdout + result.stderr)
    assert not hook.exists(), "a refused group --dry-run must write nothing"


@pytest.mark.non_sandbox
def test_real_cli_forwards_group_dry_run_to_backfill_runtime_state(tmp_path: Path, run_cli: Any) -> None:
    feature_dir = build_mission(tmp_path)
    (tmp_path / ".kittify").mkdir(exist_ok=True)
    meta_before = (feature_dir / "meta.json").read_bytes()

    result = run_cli(tmp_path, "migrate", "--dry-run", "backfill-runtime-state", "--json")

    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["dry_run"] is True
    assert (feature_dir / "meta.json").read_bytes() == meta_before
