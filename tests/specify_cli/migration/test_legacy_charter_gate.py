"""The CLI-root ``LEGACY_CHARTER_STATE`` gate (FR-011, #3732, T072).

Unit tests drive :mod:`specify_cli.migration.legacy_charter_gate` directly; the
CLI tests invoke the real ``spec-kitty`` app in-process on small projects, one
per finding kind, and check the exemptions on the same legacy project.
"""

from __future__ import annotations

import ast
import contextlib
import json
import os
import statistics
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

import click
import pytest
from typer.testing import CliRunner, Result

from specify_cli.migration import legacy_charter_gate as gate
from specify_cli.migration.legacy_charter_gate import (
    EXEMPT_COMMANDS,
    LEGACY_CHARTER_STATE,
    check_legacy_charter_layout,
    current_checkout_root,
    find_checkout_root,
    first_legacy_finding,
    render_legacy_charter_message,
    usage_errors_first,
)
from tests.acceptance.charter_pack_cutover.legacy_fixtures import stamp_metadata

pytestmark = [pytest.mark.unit]

RUNBOOK = "docs/migrations/charter-pack-cutover.md"
WORKTREE_WORDS = ("merge the target into this lane", "do not rebase")

#: One project per finding kind the predicate reports: (relative path, text).
LEGACY_LAYOUTS: dict[str, tuple[str, str]] = {
    "legacy_project_root": (".kittify/doctrine/directive/x.directive.yaml", "id: X\n"),
    "legacy_governance_file": (".kittify/charter/governance.yaml", "doctrine:\n  selected_directives: [X]\n"),
    "legacy_org_packs_key": (".kittify/config.yaml", "doctrine:\n  org:\n    packs:\n    - name: acme\n      local_path: packs/acme\n"),
    "legacy_organisation_packs_key": (".kittify/config.yaml", "organisation_packs:\n- name: acme\n  path: packs/acme\n"),
    "legacy_governance_selection_key": (".kittify/config.yaml", "governance:\n  doctrine:\n    selected_directives: [X]\n"),
    "legacy_tracker_ownership_key": (".kittify/config.yaml", "tracker:\n  provider: beads\n  doctrine:\n    mode: external_authoritative\n"),
}


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _project(root: Path, *, layout: str | None = None, config: str = "vcs:\n  type: git\n") -> Path:
    """A stamped project; *layout* names a :data:`LEGACY_LAYOUTS` entry to plant."""
    _write(root / ".kittify" / "config.yaml", config)
    stamp_metadata(root)
    if layout is not None:
        rel, text = LEGACY_LAYOUTS[layout]
        target = root / rel
        if target.name == "config.yaml":
            text = config + text
        _write(target, text)
    return root


def _run(args: list[str], cwd: Path) -> Result:
    from specify_cli import app

    with contextlib.chdir(cwd):
        return CliRunner().invoke(app, args, catch_exceptions=True)


def _refused(result: Result) -> bool:
    return LEGACY_CHARTER_STATE in result.output


# --------------------------------------------------------------------------- #
# Message
# --------------------------------------------------------------------------- #


def test_message_names_the_code_the_finding_the_remedy_and_the_runbook() -> None:
    text = render_legacy_charter_message("legacy_project_root", in_checkout=False)

    assert text.startswith(f"Error ({LEGACY_CHARTER_STATE}): This project uses the retired doctrine layout (legacy_project_root).")
    assert "Run `spec-kitty upgrade` to migrate it." in text
    assert text.endswith(f"See {RUNBOOK}.")
    assert not any(word in text for word in WORKTREE_WORDS)


def test_message_adds_the_worktree_sentence_for_a_checkout_finding() -> None:
    text = render_legacy_charter_message("legacy_project_root", in_checkout=True)

    assert all(word in text for word in WORKTREE_WORDS)
    assert "upgrade the\nrepository root" in text


# --------------------------------------------------------------------------- #
# Checkout root
# --------------------------------------------------------------------------- #


def test_find_checkout_root_finds_a_git_directory(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)

    assert find_checkout_root(nested) == tmp_path


def test_find_checkout_root_finds_a_worktree_git_file(tmp_path: Path) -> None:
    _write(tmp_path / "lane" / ".git", "gitdir: /elsewhere\n")

    assert find_checkout_root(tmp_path / "lane") == tmp_path / "lane"


def test_find_checkout_root_outside_git_is_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gate.os.path, "lexists", lambda _path: False)

    assert find_checkout_root(tmp_path) is None


def test_current_checkout_root_of_an_unreadable_cwd_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    def _gone() -> Path:
        raise FileNotFoundError("cwd removed")

    monkeypatch.setattr(gate.Path, "cwd", staticmethod(_gone))

    assert current_checkout_root() is None


def test_current_checkout_root_reads_the_cwd(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    with contextlib.chdir(tmp_path):
        assert current_checkout_root() == tmp_path


# --------------------------------------------------------------------------- #
# First finding
# --------------------------------------------------------------------------- #


def test_clean_project_has_no_finding(tmp_path: Path) -> None:
    assert first_legacy_finding(_project(tmp_path), tmp_path) is None


@pytest.mark.parametrize("layout", sorted(LEGACY_LAYOUTS))
def test_every_finding_kind_is_found_in_the_project(tmp_path: Path, layout: str) -> None:
    assert first_legacy_finding(_project(tmp_path, layout=layout), None) == (layout, False)


def test_a_finding_in_a_different_checkout_is_marked_as_such(tmp_path: Path) -> None:
    project = _project(tmp_path / "root")
    lane = _project(tmp_path / "lane", layout="legacy_project_root")

    assert first_legacy_finding(project, lane) == ("legacy_project_root", True)


def test_the_checkout_is_not_checked_twice_when_it_is_the_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = _project(tmp_path)
    calls: list[Path] = []
    monkeypatch.setattr(gate, "detect_legacy_charter_layout", lambda root: calls.append(root) or ())

    assert first_legacy_finding(project, project) is None
    assert calls == [project]


def test_roots_without_a_kittify_directory_are_not_checked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[Path] = []
    monkeypatch.setattr(gate, "detect_legacy_charter_layout", lambda root: calls.append(root) or ("x",))
    (tmp_path / "lane").mkdir()
    _write(tmp_path / "file-kittify" / ".kittify", "a file, not a directory\n")

    assert first_legacy_finding(tmp_path, tmp_path / "lane") is None
    assert first_legacy_finding(tmp_path / "file-kittify", None) is None
    assert calls == []


def test_unresolvable_roots_compare_by_path(tmp_path: Path) -> None:
    missing = tmp_path / "missing"

    assert gate._same_directory(missing, missing)
    assert not gate._same_directory(missing, tmp_path / "other")


# --------------------------------------------------------------------------- #
# The check
# --------------------------------------------------------------------------- #


def _check(project: Path, *, sub: str | None = "charter", argv: tuple[str, ...] = ("charter", "list"), hook: Callable[[], None] | None = None) -> None:
    check_legacy_charter_layout(project, None, invoked_subcommand=sub, argv=argv, before_refusal=hook)


def test_refusal_exits_1_and_writes_the_message_to_stderr(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    project = _project(tmp_path, layout="legacy_org_packs_key")
    hook_calls: list[str] = []

    with pytest.raises(SystemExit) as caught:
        _check(project, hook=lambda: hook_calls.append("probed"))

    assert caught.value.code == 1
    err = capsys.readouterr().err
    assert f"({LEGACY_CHARTER_STATE})" in err and "(legacy_org_packs_key)" in err and RUNBOOK in err
    assert hook_calls == ["probed"]


def test_clean_project_passes_without_running_the_hook(tmp_path: Path) -> None:
    hook_calls: list[str] = []

    _check(_project(tmp_path), hook=lambda: hook_calls.append("probed"))

    assert hook_calls == []


@pytest.mark.parametrize(
    ("sub", "argv"),
    [
        *((name, (name,)) for name in sorted(EXEMPT_COMMANDS)),
        ("merge-driver-meta", ("merge-driver-meta", "b", "o", "t")),
        ("live-work", ("live-work", "hook", "claude")),
        ("charter", ("charter", "list", "--help")),
        ("charter", ("charter", "-h")),
        (None, ("--version",)),
        (None, ("-v",)),
    ],
)
def test_exempt_invocations_pass_on_a_legacy_project(tmp_path: Path, sub: str | None, argv: tuple[str, ...]) -> None:
    _check(_project(tmp_path, layout="legacy_project_root"), sub=sub, argv=argv)


@pytest.mark.parametrize("argv", [("live-work", "matrix"), ("live-work", "install", "claude"), ("live-work",)], ids=["matrix", "install", "bare"])
def test_only_the_live_work_hook_is_exempt(tmp_path: Path, argv: tuple[str, ...]) -> None:
    """AR-S3 exempts the hook entry point, not the whole ``live-work`` group."""
    with pytest.raises(SystemExit):
        _check(_project(tmp_path, layout="legacy_project_root"), sub="live-work", argv=argv)


def test_a_late_version_flag_is_not_an_exemption(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        _check(_project(tmp_path, layout="legacy_project_root"), argv=("charter", "list", "-v"))


# --------------------------------------------------------------------------- #
# Usage errors first
# --------------------------------------------------------------------------- #


@click.group()
@click.option("--root-flag", is_flag=True)
def _probe_cli(root_flag: bool) -> None:
    """A tiny CLI for the usage probe."""


@_probe_cli.group()
def tracker() -> None:
    """A nested group."""


@tracker.command()
@click.argument("wp_id")
@click.option("--json", "as_json", is_flag=True)
def status(wp_id: str, as_json: bool) -> None:
    """A leaf with a required argument."""


def _probe(args: list[str]) -> Callable[[], None]:
    return usage_errors_first(click.Context(_probe_cli, info_name="spec-kitty"), args)


def test_an_unknown_leaf_option_raises_the_usage_error() -> None:
    with pytest.raises(click.UsageError, match="--doctrine-mode"):  # noqa: TID251 — test names the click universe of the command it built itself, or deliberately the standalone-click spelling
        _probe(["tracker", "status", "WP01", "--doctrine-mode", "x"])()


def test_an_unknown_group_option_raises_the_usage_error() -> None:
    with pytest.raises(click.UsageError, match="--nope"):  # noqa: TID251 — test names the click universe of the command it built itself, or deliberately the standalone-click spelling
        _probe(["tracker", "--nope", "status"])()


@pytest.mark.parametrize(
    "args",
    [["tracker", "status", "WP01", "--json"], ["--root-flag", "tracker", "status"], ["tracker", "no-such-command"], ["tracker"], ["no-such-group", "x"]],
    ids=["valid", "missing-argument", "unknown-subcommand", "bare-group", "unknown-top-level"],
)
def test_other_invocations_leave_the_refusal_to_proceed(args: list[str]) -> None:
    _probe(args)()


def test_a_failing_probe_leaves_the_refusal_to_proceed() -> None:
    usage_errors_first(object(), ["tracker"])()


def test_a_non_usage_error_from_resolution_propagates_to_the_probe_guard() -> None:
    class _Broken:
        def resolve_command(self, _ctx: object, _args: list[str]) -> None:
            raise RuntimeError("broken group")

    with pytest.raises(RuntimeError, match="broken group"):
        gate._resolve(_Broken(), None, ["x"])


# --------------------------------------------------------------------------- #
# The real CLI root
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("layout", sorted(LEGACY_LAYOUTS))
def test_cli_refuses_every_finding_kind(tmp_path: Path, layout: str) -> None:
    result = _run(["charter", "list"], _project(tmp_path, layout=layout))

    assert result.exit_code == 1, result.output
    assert _refused(result) and f"({layout})" in result.output and RUNBOOK in result.output
    assert "spec-kitty upgrade" in result.output


@pytest.mark.parametrize(
    "args",
    [["--help"], ["--version"], ["init", "--help"], ["charter", "list", "--help"], ["merge-driver-meta", "--help"], ["session-stop"], ["session-start"]],
    ids=["help", "version", "init-help", "leaf-help", "merge-driver-help", "session-stop", "session-start"],
)
def test_cli_exempt_invocations_are_not_refused(tmp_path: Path, args: list[str]) -> None:
    result = _run(args, _project(tmp_path, layout="legacy_project_root"))

    assert not _refused(result), result.output
    assert result.exit_code == 0, result.output


def test_cli_merge_driver_runs_on_a_legacy_project(tmp_path: Path) -> None:
    """Git runs a merge driver inside the checkout being merged; it is never refused."""
    project = _project(tmp_path / "p", layout="legacy_project_root")
    blobs = {name: _write(tmp_path / name, json.dumps({"mission_slug": "m", "field": name}) + "\n") for name in ("base", "ours", "theirs")}

    result = _run(["merge-driver-meta", str(blobs["base"]), str(blobs["ours"]), str(blobs["theirs"])], project)

    assert not _refused(result), result.output


def test_cli_commit_guard_hook_is_not_refused(tmp_path: Path) -> None:
    result = _run(["commit-guard-hook"], _project(tmp_path, layout="legacy_project_root"))

    assert not _refused(result), result.output


def test_cli_unknown_option_on_a_legacy_project_is_a_usage_error(tmp_path: Path) -> None:
    result = _run(["tracker", "status", "--doctrine-mode", "x"], _project(tmp_path, layout="legacy_tracker_ownership_key"))

    assert result.exit_code == 2, result.output
    assert not _refused(result)


def test_cli_passes_a_migrated_project(tmp_path: Path) -> None:
    result = _run(["charter", "list", "--json"], _project(tmp_path))

    assert not _refused(result), result.output


def test_cli_passes_a_config_with_the_word_only_in_a_comment(tmp_path: Path) -> None:
    project = _project(tmp_path, config="# migrated from the doctrine layout\nvcs:\n  type: git\n")

    assert not _refused(_run(["charter", "list"], project))


def test_cli_outside_a_project_is_a_no_op(tmp_path: Path) -> None:
    result = _run(["charter", "list"], tmp_path)

    assert not _refused(result), result.output


def test_cli_refuses_a_stale_lane_worktree_of_a_migrated_root(tmp_path: Path) -> None:
    root = _project(tmp_path / "root")
    for args in (["init", "-q"], ["add", "-A"], ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"]):
        subprocess.run(["git", *args], cwd=root, check=True)
    lane = tmp_path / "lane"
    subprocess.run(["git", "worktree", "add", "-q", "-b", "lane", str(lane)], cwd=root, check=True)
    _write(lane / ".kittify" / "doctrine" / "directive" / "x.directive.yaml", "id: X\n")

    assert not _refused(_run(["charter", "list"], root))
    stale = _run(["charter", "list"], lane)

    assert stale.exit_code == 1, stale.output
    assert all(word in stale.output for word in WORKTREE_WORDS)


def test_cli_refuses_migrate_too(tmp_path: Path) -> None:
    """``migrate`` defers the root bootstrap, not the legacy gate."""
    result = _run(["migrate"], _project(tmp_path, layout="legacy_project_root"))

    assert result.exit_code == 1, result.output
    assert _refused(result)


# --------------------------------------------------------------------------- #
# Layering and cost
# --------------------------------------------------------------------------- #


def test_gate_module_imports_nothing_from_charter() -> None:
    tree = ast.parse(Path(gate.__file__).read_text(encoding="utf-8"))
    modules = {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    modules |= {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}

    assert not {m for m in modules if m == "charter" or m.startswith("charter.")}, modules


def test_gate_parses_no_yaml_on_a_clean_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import yaml

    project = _project(tmp_path)

    def _no_parse(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("YAML parsed on the common path")

    monkeypatch.setattr(yaml, "safe_load", _no_parse)
    _check(project)


def test_gate_latency_on_a_clean_project(tmp_path: Path) -> None:
    """Evidence, not a budget: the gate's own time on a clean project (median of 5)."""
    project = _project(tmp_path)
    (tmp_path / ".git").mkdir()
    samples = []
    for _ in range(5):
        started = time.perf_counter()
        _check(project)
        samples.append(time.perf_counter() - started)

    median_ms = statistics.median(samples) * 1000
    print(f"legacy charter gate, clean project: median {median_ms:.3f} ms over 5 runs ({os.name})")
    assert median_ms >= 0
