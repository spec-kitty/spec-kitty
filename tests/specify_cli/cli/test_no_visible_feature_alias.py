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

import pytest
from click.testing import CliRunner

# The tests and helpers shared with this suite's always-on lift live once, in
# ``tests/architectural/_lifted_cli_no_visible_feature_alias.py`` (#5015); importing a test is what makes pytest collect it here.
from tests.architectural._lifted_cli_no_visible_feature_alias import (
    cli,
    _walk_leaf_commands,
)
from tests.architectural._lifted_cli_no_visible_feature_alias import test_every_feature_flag_is_hidden as test_every_feature_flag_is_hidden
from tests.architectural._lifted_cli_no_visible_feature_alias import test_zero_feature_flags_exist_cli_wide as test_zero_feature_flags_exist_cli_wide

pytestmark = [pytest.mark.unit, pytest.mark.fast]


FEATURE_TOKEN_RE = re.compile(r"--feature\b")


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
    the ``tracker`` group's rollout-gate callback
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
