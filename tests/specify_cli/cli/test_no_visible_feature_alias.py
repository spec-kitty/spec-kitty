"""Regression tests for FR-006 (#790): the legacy ``--feature`` alias must
stay hidden from every leaf command's ``--help`` output.

These tests lock down two complementary invariants that are already correct
on ``main`` (verified during planning of mission
``release-3-2-0a5-tranche-1``, research note R5):

1. **Introspection invariant**: every parameter whose CLI flag is
   ``--feature`` must carry ``hidden=True`` so Click/Typer suppresses it
   from rendered help.

2. **Surface invariant**: the rendered ``--help`` text of every leaf
   command must NOT contain the substring ``--feature``. This catches
   help text drift even if Click ever changes how it formats hidden
   parameters.

If either assertion fails, the alias has leaked back into the user-visible
surface — the exact regression #790 closed.
"""

from __future__ import annotations

import re

import click
from click.testing import CliRunner
from typer.main import get_command

from specify_cli import app as _typer_app


# ---------------------------------------------------------------------------
# Resolve the underlying Click command tree.
# ---------------------------------------------------------------------------
# ``specify_cli`` exposes a Typer app. Sibling tests (e.g.
# ``test_doctrine_cli_removed.py``) import that Typer app directly and let
# Typer's CliRunner handle the conversion. For introspection we want the
# Click command tree, which Typer can give us via ``get_command``.

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

cli: click.Group = get_command(_typer_app)  # type: ignore[assignment]


FEATURE_TOKEN_RE = re.compile(r"--feature\b")


def _walk_leaf_commands(group: click.Group, prefix: tuple[str, ...] = ()):
    """Yield (path_tuple, command) for every leaf command under ``group``."""
    for name, cmd in group.commands.items():
        path = prefix + (name,)
        if isinstance(cmd, click.Group):
            yield from _walk_leaf_commands(cmd, path)
        else:
            yield path, cmd


def _param_declares_feature_flag(param: click.Parameter) -> bool:
    """Return True iff the param's CLI surface declares ``--feature``.

    We deliberately match on declared option strings (``param.opts`` and
    ``param.secondary_opts``) rather than ``param.name``. The Python-side
    parameter happens to be named ``feature`` on several mission commands
    that bind it exclusively to ``--mission`` — those are not what FR-006
    is policing.
    """
    declared = list(getattr(param, "opts", []) or []) + list(
        getattr(param, "secondary_opts", []) or []
    )
    return "--feature" in declared


def test_every_feature_flag_is_hidden() -> None:
    """Every ``--feature`` flag on every leaf command must carry hidden=True.

    Defensively reads ``hidden`` via ``getattr`` so a future Click/Typer
    upgrade that renames or restructures the attribute fails loudly here
    rather than silently letting an alias re-surface.

    NOTE (FR-009 / mission feature-alias-removal-01KW0N87): After WP01–WP03
    all ``--feature`` flags were hard-removed from user-facing commands.  This
    test now passes trivially because there are no ``--feature`` parameters at
    all — see ``test_zero_feature_flags_exist_cli_wide`` for the stronger
    zero-presence assertion.
    """
    offenders: list[str] = []
    for path, cmd in _walk_leaf_commands(cli):
        for param in cmd.params:
            if _param_declares_feature_flag(param) and not getattr(
                param, "hidden", False
            ):
                offenders.append(" ".join(path))
    assert not offenders, (
        "FR-006 regression: --feature flag is visible on these commands "
        "(must be hidden=True):\n  " + "\n  ".join(offenders)
    )


def test_zero_feature_flags_exist_cli_wide() -> None:
    """After alias removal, no ``--feature`` Typer option should exist anywhere in the CLI.

    Stronger companion to ``test_every_feature_flag_is_hidden``: asserts that
    the CLI tree contains ZERO ``--feature`` parameters (hidden or visible),
    not merely that any remaining ones are hidden.

    Authority: spec.md FR-009 / mission feature-alias-removal-01KW0N87 WP04.
    """
    feature_options: list[str] = []
    for path, cmd in _walk_leaf_commands(cli):
        for param in cmd.params:
            if _param_declares_feature_flag(param):
                feature_options.append(" ".join(path))
    assert feature_options == [], (
        f"Found {len(feature_options)} '--feature' option(s) in CLI tree on "
        f"command(s): {feature_options}.  All --feature aliases must be removed "
        "(FR-009 / mission feature-alias-removal-01KW0N87)."
    )


def test_help_output_never_mentions_feature_alias() -> None:
    """``--help`` text for every leaf command must not contain ``--feature``.

    This is the user-visible contract: regardless of Click's internal
    representation, the alias must never appear in rendered help.

    Each leaf is invoked DIRECTLY, not through the assembled root app:
    routing ~268 ``--help`` invocations through the root callback chain
    (``main_callback`` → ``root_callback`` → ``ensure_runtime`` /
    ``ensure_global_agent_skills`` / ``ensure_global_agent_commands`` /
    startup gates) made this single ``fast``+``unit`` test run for 30+
    minutes (#4636). The ``--help`` option short-circuits in
    ``parse_args`` before any command callback runs, so a direct leaf
    invoke renders the leaf's own help text without paying the root
    bootstrap once per leaf. Two classes of output differ from a
    root-routed invoke, and both are intentionally out of scope for this
    invariant: the usage line's prog name (the leaf name instead of the
    full command path), and ancestor group-callback side output — e.g.
    the deprecated ``doctrine`` group's CR-02 deprecation banner
    (``cli/commands/doctrine.py::_deprecation_warning``) and the
    ``tracker`` group's rollout-gate callback
    (``cli/commands/tracker.py::tracker_callback``). Neither can mask a
    ``--feature`` regression: the prog name is not an option flag, the
    group-callback text is static side output, and the leaf's Options
    section renders byte-identically either way.

    The direct form is also strictly stronger for gated groups: with the
    ``tracker`` rollout gate closed, a root-routed invoke exited 1 before
    the leaf's help ever rendered, and with no exit-code assert the old
    test would have scanned the gate's error text and silently passed
    those leaves. Direct invoke plus the ``exit_code == 0`` assert below
    closes that hole — any future leaf whose ``--help`` stops rendering
    fails loudly instead of being skipped.
    """
    runner = CliRunner()
    offenders: list[tuple[str, str]] = []
    for path, cmd in _walk_leaf_commands(cli):
        result = runner.invoke(cmd, ["--help"], catch_exceptions=False)
        # A leaf whose --help fails to render cannot be checked — fail
        # loudly instead of silently skipping its surface invariant.
        assert result.exit_code == 0, (
            f"--help did not render cleanly for leaf {' '.join(path)} "
            f"(exit {result.exit_code}): {result.output}"
        )
        if FEATURE_TOKEN_RE.search(result.output):
            offenders.append((" ".join(path), result.output))
    assert not offenders, (
        "FR-006 regression: '--feature' token appears in --help output of:\n  "
        + "\n  ".join(name for name, _ in offenders)
    )
