"""ATDD acceptance tests for ``spec-kitty migrate --dry-run/--force/--verbose <sub>`` (#4964, WP07).

Issue #4964: the ``migrate`` group callback declared ``--dry-run``/``--verbose``/
``--force`` but, whenever a subcommand was invoked, returned immediately
(``if ctx.invoked_subcommand is not None: return``) without looking at them —
so ``spec-kitty migrate --dry-run backfill-runtime-state`` silently dropped
``--dry-run`` and ran the REAL migration, exit 0.

Design decision **D7** / research **R6**: the group callback now forwards a
group flag to the subcommand via ``ctx.default_map`` when the subcommand
declares the same flag name, or refuses with a usage error (exit 2) before
the subcommand runs — raised from the click universe typer actually uses
(real ``click`` on typer <=0.25, vendored ``typer._click`` on 0.26+).

Test strategy (two tiers, per the WP07 prompt's three endorsed proof methods —
"the ``(dry-run)`` output prefix, a ``dry_run: true`` JSON field, or a spy on
the backend function's ``dry_run`` kwarg"):

* **Tier 1 — generic, parametrised over the LIVE registry.** For every
  currently-registered ``migrate`` subcommand crossed with every group flag
  (``--dry-run``/``--verbose``/``-v``/``--force``), this asserts the seam's
  forward-or-refuse contract in isolation from each subcommand's own
  migration logic (owned by other WPs, out of this WP's authoritative
  surface ``cli/commands/migrate_cmd.py``): when the subcommand declares the
  flag, its own CLI entry-point function is spied and must receive the
  flag's value truthily (the "spy on the backend function's kwarg" method);
  when it does not, the group must refuse with exit 2 and a message naming
  the flag, the subcommand, and a ``--help`` next action (NFR-003). Because
  this discovers subcommands and their declared params from the live
  ``typer.Typer`` app rather than a hardcoded list, a future subcommand is
  covered automatically.
* **Tier 2 — one real, non-spied, end-to-end positive control** (the
  issue's own repro, ``backfill-runtime-state``, over the shared WP03
  legacy-mission fixture): ``--dry-run`` truly writes nothing, and the
  non-dry-run form on the SAME fixture DOES write — proving the fixture is
  migratable and Tier 1's spy-based proof is not masking a corpus that had
  nothing to migrate in the first place.
"""

from __future__ import annotations

import enum
import json
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
from tests.unit.migration._backfill_fixture import build_mission

pytestmark = [pytest.mark.integration]

runner = CliRunner()
click_runner = ClickCliRunner()

_LOCATE = "specify_cli.cli.commands.migrate_cmd.locate_project_root"

#: Unicode Box Drawing block — used only to strip the wrap-point borders a
#: Rich/Typer error Panel inserts mid sentence (see ``_flatten``).
_BOX_DRAWING_CHARS = re.compile(r"[─-╿]")


# ---------------------------------------------------------------------------
# Hard filesystem isolation (mandatory — post-incident hardening).
#
# An earlier version of this test file invoked the real CLI (the explicit
# refusal repro cases below) WITHOUT patching project-root resolution. Run
# against the then-unfixed source, the group callback's refusal did not fire,
# so the subcommand's REAL body ran, and ``locate_project_root()`` resolved
# to the ambient cwd's repository — which, from inside a git worktree, is
# the MAIN checkout (/home/user/spec-kitty), not this worktree — mutating 51
# real ``kitty-specs/*`` files there (additive ``status.events.jsonl`` /
# ``meta.json`` ``status_phase`` writes). That cleanup was escalated to the
# operator; it is NOT this test file's to fix.
#
# Every test in this module now runs with cwd inside a scratch directory
# under ``tmp_path`` (never inside /home/user/spec-kitty or any of its
# worktrees), and ``locate_project_root`` is poisoned by default to a
# callable that fails loudly unless a test explicitly overrides it with a
# path under its own ``tmp_path`` — so a future test that forgets to patch
# project-root resolution fails immediately instead of touching a real repo.
# ---------------------------------------------------------------------------


def _poisoned_locate_project_root(*_args: Any, **_kwargs: Any) -> Path:
    raise AssertionError(
        "locate_project_root() was called without an explicit test override. "
        "Every test in test_migrate_group_flags_4964.py must patch _LOCATE to "
        "a path under its own tmp_path before invoking the CLI (hard "
        "isolation rule, #4964 WP07 post-incident hardening) — never let the "
        "real resolver run, which would touch whatever real repository the "
        "process cwd happens to be inside."
    )


#: The real repository this test file must never touch, in either form —
#: the main checkout or any of its git worktrees.
_REAL_REPO_ROOT = Path("/home/user/spec-kitty").resolve()


@pytest.fixture(autouse=True)
def _hard_repo_isolation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    resolved_tmp = tmp_path.resolve()
    assert not resolved_tmp.is_relative_to(_REAL_REPO_ROOT), (
        f"pytest's own tmp_path ({resolved_tmp}) resolves inside the real "
        f"repository ({_REAL_REPO_ROOT}) — refusing to run any test in this "
        "module (hard isolation rule, #4964 WP07 post-incident hardening)."
    )
    scratch_cwd = tmp_path / "cwd"
    scratch_cwd.mkdir()
    monkeypatch.chdir(scratch_cwd)
    monkeypatch.setattr(_LOCATE, _poisoned_locate_project_root)
    yield


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


def _click_group() -> click.Group:
    group = get_command(migrate_app)
    assert isinstance(group, click.Group)
    return group


def _registered_subcommand_names() -> list[str]:
    return sorted(_click_group().commands)


def _declares_param(cmd: click.Command, param_name: str) -> bool:
    return any(param.name == param_name for param in cmd.params)


def _required_arg_values(cmd: click.Command) -> list[str]:
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
        if isinstance(param, click.Option) and param.required:
            args.extend([param.opts[0], f"dummy-{param.name}"])
    return args


@contextmanager
def _spy_on_subcommand(name: str) -> Iterator[tuple[click.Group, list[dict[str, Any]]]]:
    """Build a fresh click.Group from the live app and replace subcommand
    *name*'s ``click.Command.callback`` with a recorder.

    Deliberately does NOT patch ``CommandInfo.callback`` on
    ``migrate_app.registered_commands``: typer derives a subcommand's own
    Click params (``--dry-run`` etc.) from that same callback's *type
    signature* at group-build time (``get_command_from_info`` ->
    ``get_params_convertors_ctx_param_name_from_function``), so replacing it
    with a generic ``**kwargs`` recorder there would silently erase the very
    params under test. Instead this builds the group ONCE via
    ``typer.main.get_command`` (params derived from the REAL signature),
    then mutates the already-built ``click.Command.callback`` in place —
    Click invokes whatever object sits at ``.callback`` at dispatch time
    without re-deriving params from it. The caller must invoke this SAME
    returned group (not re-fetch one via ``typer.testing.CliRunner``, which
    rebuilds a fresh group from ``registered_commands`` — i.e. the
    unpatched originals — on every call).
    """
    group = get_command(migrate_app)
    assert isinstance(group, click.Group)
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
        # FR-020: forwarded — the subcommand's own entry point actually
        # receives the flag truthily (not merely "nothing crashed").
        assert result.exit_code == 0, result.output
        assert len(calls) == 1, f"expected exactly one call to {sub_name!r}, got {calls}"
        assert calls[0].get(param_name) is True, calls[0]
    else:
        # FR-021: refused before anything runs. NFR-003: message names the
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


def test_dry_run_declaring_census_matches_documented_set() -> None:
    """Guard against silent drift from the WP07 prompt's documented census.

    Not the source of truth (the live registry is) — a regression guard so a
    future subcommand addition/removal is a deliberate, reviewed change to
    this constant rather than a silent surprise.
    """
    declaring = {name for name in _registered_subcommand_names() if _declares_param(_click_group().commands[name], "dry_run")}
    assert declaring == {
        "backfill-identity",
        "backfill-merge-commit",
        "backfill-mission-type",
        "backfill-provenance",
        "backfill-runtime-state",
        "backfill-topology",
        "charter-encoding",
        "normalize-lifecycle",
        "rebaseline-dossier-hashes",
        "rewrite-opposed-by",
    }
    not_declaring = set(_registered_subcommand_names()) - declaring
    assert not_declaring == {"repin-hooks"}
    force_or_verbose = {
        name
        for name in _registered_subcommand_names()
        if _declares_param(_click_group().commands[name], "force") or _declares_param(_click_group().commands[name], "verbose")
    }
    assert force_or_verbose == set(), "census assumed no subcommand declares --force/--verbose"


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
# T038: ratchets — behaviour that must NOT change.
# ---------------------------------------------------------------------------


def test_trailing_dry_run_form_unchanged(tmp_path: Path) -> None:
    """``migrate <sub> --dry-run`` (trailing) is untouched by this WP."""
    feature_dir = build_mission(tmp_path)
    events_before = (feature_dir / "status.events.jsonl").read_bytes()

    with patch(_LOCATE, return_value=tmp_path):
        result = _invoke(["backfill-runtime-state", "--dry-run", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["dry_run"] is True
    assert (feature_dir / "status.events.jsonl").read_bytes() == events_before


@pytest.mark.skip(
    reason=(
        "T038 ratchet: 'trailing --no-dry-run wins over a forwarded group "
        "--dry-run' requires a subcommand declaring --dry-run/--no-dry-run. "
        "The live registry census (test_dry_run_declaring_census_matches_"
        "documented_set) confirms none of today's 10 --dry-run subcommands "
        "define --no-dry-run, so there is nothing to exercise; documented "
        "per the WP07 prompt's explicit skip-with-reason instruction."
    )
)
def test_trailing_no_dry_run_overrides_forwarded_group_dry_run() -> None:  # pragma: no cover
    raise AssertionError("no subcommand defines --no-dry-run to exercise this ratchet")


def test_no_subcommand_dry_run_preview_path_unchanged(tmp_path: Path) -> None:
    """``migrate --dry-run`` with no subcommand still runs its own body
    exactly as today (FR-022) — not routed through the forward-or-refuse
    helper at all (``ctx.invoked_subcommand is None``).
    """
    (tmp_path / ".kittify").mkdir()

    with patch(_LOCATE, return_value=tmp_path):
        result = _invoke(["--dry-run"])

    assert result.exit_code == 0, result.output
    assert "Step 1:" in result.output
    assert "no changes in dry-run" in result.output


# ---------------------------------------------------------------------------
# Explicit issue-repro cases named by the WP07 prompt.
# ---------------------------------------------------------------------------


def test_dry_run_before_repin_hooks_is_refused() -> None:
    result = _invoke(["--dry-run", "repin-hooks"])
    assert result.exit_code == 2, result.output
    flat_output = _flatten(result.output)
    assert "--dry-run" in flat_output
    assert "repin-hooks" in flat_output


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
    assert "--verbose" in flat_output
    assert "backfill-runtime-state" in flat_output


# ---------------------------------------------------------------------------
# Pre-PR fold B1: the helper must be click-universe agnostic.
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
    assert migrate_cmd._usage_error_class(object()) is click.UsageError


def test_usage_error_class_resolves_the_real_click_for_a_real_context() -> None:
    ctx = click.Context(_click_group())
    assert migrate_cmd._usage_error_class(ctx) is click.UsageError


def test_usage_error_class_skips_a_core_module_without_exceptions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delitem(sys.modules, f"{_FAKE_CLICK}.exceptions", raising=False)
    assert migrate_cmd._usage_error_class(_fake_ctx(None, [], given={})) is click.UsageError


def test_dry_run_before_undeclaring_subcommand_names_help_not_a_trailing_flag() -> None:
    result = _invoke(["--dry-run", "repin-hooks"])
    assert result.exit_code == 2, result.output
    flat_output = _flatten(result.output)
    assert "spec-kitty migrate repin-hooks --help" in flat_output
    assert "migrate repin-hooks --dry-run" not in flat_output


def test_short_verbose_refusal_names_the_short_form() -> None:
    result = _invoke(["-v", "backfill-runtime-state"])
    assert result.exit_code == 2, result.output
    assert "-v/--verbose" in _flatten(result.output)


# ---------------------------------------------------------------------------
# Pre-PR fold B1: the same contract through the real CLI entry point in the
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
