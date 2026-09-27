"""T024 — Static + behavioral audit: no legacy Windows-unsafe path literals
reach user-facing output.

Three complementary checks:

1. **Static grep over CLI command tree**: any ``~/.kittify`` / ``~/.spec-kitty``
   literal in ``src/specify_cli/cli/`` (non-comment lines) is flagged.  The
   CLI command tree is where user-facing ``console.print`` / ``typer.echo``
   lives, so a static check is sufficient there.

2. **Behavioral test of resolver nudges**: the ``_emit_migrate_nudge`` helpers
   in ``src/specify_cli/runtime/resolver.py`` and ``src/charter/offering/resolver.py``
   print a one-time stderr message.  DRIFT-6 from the mission review showed
   the nudge was hardcoded to ``~/.kittify/`` regardless of platform.  These
   behavioral tests invoke the helpers under a mocked ``SPEC_KITTY_HOME`` that
   masquerades as the unified Windows root and assert the output contains the
   mocked real path (no tilde literal).

3. **Static scan for hand-rolled global-state home literals** (T021 / FR-010):
   issue #2171 was caused by global sync/auth/tracker/daemon modules
   independently computing ``Path.home() / ".spec-kitty"`` instead of deriving
   from the single authoritative resolver ``specify_cli.paths.get_runtime_root``.
   :func:`test_no_handrolled_spec_kitty_home_in_global_state_modules` fails the
   build if any non-allowlisted module under ``src/specify_cli`` / ``src/kernel``
   reintroduces that literal, so ``SPEC_KITTY_HOME`` cannot silently stop
   isolating part of the state again.

Internal modules (``runtime/bootstrap.py``, ``sync/queue.py``, ``state_contract.py``,
migration scripts, etc.) reference ``~/.kittify`` / ``~/.spec-kitty`` freely in
docstrings, inline comments, and string-literal ``path_pattern`` metadata.
None of that is user-facing runtime output.  A textual tree-wide grep produces
too many false positives, so the audit is scoped to the files that actually
emit to users.

No ``windows_ci`` marker — these checks run on every platform.

Spec IDs: FR-010 (T021), FR-013, SC-002 (second-pass remediation)
"""

from __future__ import annotations

import importlib
import io
import os
import pathlib
import re
import sys
from contextlib import ExitStack, redirect_stderr
from unittest import mock

# Match the bare tilde-path anywhere on a line.

import pytest

pytestmark = [pytest.mark.integration]

LITERAL = re.compile(r"~/\.(kittify|spec-kitty)")
# Comment detector: line starts with optional whitespace then '#'.
COMMENT = re.compile(r"^\s*#")


def test_no_legacy_path_literals_in_cli_commands() -> None:
    """Assert zero ~/.(kittify|spec-kitty) literals in CLI command tree (non-comment lines)."""
    root = pathlib.Path(__file__).resolve().parents[2] / "src" / "specify_cli" / "cli"
    violations: list[str] = []
    for py in root.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), start=1):
            if COMMENT.match(line):
                continue  # skip pure comments; they are not user-facing output
            if LITERAL.search(line):
                violations.append(f"{py.relative_to(root.parents[2])}:{i}: {line.strip()}")
    assert not violations, "Legacy Windows-unsafe path literals reintroduced in CLI command tree:\n  " + "\n  ".join(violations)


def _capture_nudge(
    module_name: str,
    runtime_home: pathlib.Path,
    *,
    argv: list[str] | None = None,
) -> str:
    """Import the named module, reset its nudge flag, and capture stderr on call.

    Uses ``SPEC_KITTY_HOME`` to pin the runtime home to a tmp path so the
    rendered message is deterministic and does not depend on the real user's
    home directory.  Returns whatever the nudge printed to stderr.
    """
    with ExitStack() as stack:
        # mock.patch.dict snapshots/restores the whole environment at exit,
        # regardless of how entries change inside the block -- so the raw
        # SPEC_KITTY_HOME write below (kept verbatim: this helper must stay
        # monkeypatch-free per test_home_pin_scan_limbs.py's FR-010 limb
        # assertion on its def chain) still gets undone automatically.
        stack.enter_context(mock.patch.dict(os.environ))
        os.environ["SPEC_KITTY_HOME"] = str(runtime_home)
        if argv is not None:
            stack.enter_context(mock.patch.object(sys, "argv", argv[:]))
        # Fresh import so module-level state is clean
        if module_name in sys.modules:
            importlib.reload(sys.modules[module_name])
        module = importlib.import_module(module_name)
        module._reset_migrate_nudge()
        buf = io.StringIO()
        with redirect_stderr(buf):
            module._emit_migrate_nudge()
        return buf.getvalue()


def test_runtime_resolver_nudge_renders_real_runtime_path(tmp_path: pathlib.Path) -> None:
    """Assert specify_cli.runtime.resolver nudge prints the actual runtime path.

    DRIFT-6 remediation: the nudge must render via ``render_runtime_path`` so
    Windows users see the real ``%LOCALAPPDATA%\\spec-kitty\\`` path, not a
    hard-coded ``~/.kittify/`` literal.  We pin ``SPEC_KITTY_HOME`` to a tmp
    path and assert the captured stderr contains that path verbatim (or its
    tilde-compressed form on POSIX when under $HOME — tmp_path here is outside
    $HOME so we get the absolute form).
    """
    fake_home = tmp_path / "runtime-home"
    output = _capture_nudge("specify_cli.runtime.resolver", fake_home)
    assert str(fake_home) in output, f"Resolver nudge did not render the real runtime path.\nExpected substring: {fake_home}\nGot: {output!r}"
    assert "~/.kittify/" not in output, f"Resolver nudge still contains a legacy tilde literal:\n{output!r}"


def test_doctrine_resolver_nudge_renders_real_runtime_path(tmp_path: pathlib.Path) -> None:
    """Mirror assertion for the doctrine package's resolver nudge."""
    fake_home = tmp_path / "doctrine-runtime-home"
    output = _capture_nudge("charter.offering.resolver", fake_home)
    assert str(fake_home) in output, f"Doctrine resolver nudge did not render the real runtime path.\nExpected substring: {fake_home}\nGot: {output!r}"
    assert "~/.kittify/" not in output, f"Doctrine resolver nudge still contains a legacy tilde literal:\n{output!r}"


@pytest.mark.parametrize(
    "module_name",
    ["specify_cli.runtime.resolver", "charter.offering.resolver"],
)
def test_resolver_nudge_is_suppressed_for_json_invocations(
    tmp_path: pathlib.Path,
    module_name: str,
) -> None:
    """Legacy migration nudges must not corrupt a merged ``--json 2>&1`` stream."""
    fake_home = tmp_path / "runtime-home"

    output = _capture_nudge(
        module_name,
        fake_home,
        argv=["spec-kitty", "agent", "mission", "finalize-tasks", "--json"],
    )

    assert output == ""


# --- T021 / FR-010: no hand-rolled global-state home recompute ---------------
#
# Issue #2171 was caused by global-state modules independently computing
# ``Path.home() / ".spec-kitty"`` instead of deriving from the single
# authoritative resolver ``specify_cli.paths.get_runtime_root``.  FR-010 forbids
# any such recompute.  The primary offenders lived under
# ``src/specify_cli/{sync,auth,tracker,state}``; this guard scans the whole
# global-state surface (``src/specify_cli`` + ``src/kernel``) so a re-scatter
# *anywhere* is caught, and exempts the keystone resolver plus the files that
# legitimately use the literal for a *different* purpose.

# Two scan roots that together cover the four primary dirs AND every allowlisted
# surface (the keystone + asset-home + migration + worktree-lock).
_GLOBAL_STATE_SCAN_ROOTS = ("src/specify_cli", "src/kernel")

# Files that may legitimately contain a ``.spec-kitty`` (or asset-home) literal:
#   * the keystone resolver itself — the ONE place the default home is computed,
#   * asset-home modules (``.kittify`` — a different root, never ``.spec-kitty``),
#   * Windows migration code (moves legacy data; must name the legacy dir),
#   * the worktree-local review lock (``worktree / ".spec-kitty"`` — NOT home).
_HOME_LITERAL_ALLOWLIST = frozenset(
    {
        "src/specify_cli/paths/windows_paths.py",
        "src/specify_cli/runtime/home.py",
        "src/kernel/paths.py",
        "src/specify_cli/paths/windows_migrate.py",
        "src/specify_cli/review/lock.py",
    }
)

# Exact bare ``".spec-kitty"`` / ``'.spec-kitty'`` string literal — a single
# path segment used as a home child.  Deliberately does NOT match documentation
# patterns like ``"~/.spec-kitty/config.toml"`` (state-contract ``path_pattern``
# metadata), which carry a ``~/`` prefix and a trailing ``/...`` and are stripped
# at runtime by the authoritative resolver.
_BARE_SPEC_KITTY_LITERAL = re.compile(r"""['"]\.spec-kitty['"]""")


def _line_has_bare_spec_kitty_literal(line: str) -> bool:
    """True when a non-comment line hand-rolls the bare ``.spec-kitty`` segment.

    Catches both ``Path.home() / ".spec-kitty"`` (the issue #2171 shape) and a
    standalone ``".spec-kitty"`` constant used as a home child.  Pure comment
    lines are skipped (mirrors the CLI-tree check above).
    """
    if COMMENT.match(line):
        return False
    return bool(_BARE_SPEC_KITTY_LITERAL.search(line))


def _scan_global_state_for_home_literal(repo_root: pathlib.Path, allowlist: frozenset[str]) -> list[str]:
    """Return ``rel:line: text`` for every hand-rolled ``.spec-kitty`` literal.

    Scans the global-state surface (:data:`_GLOBAL_STATE_SCAN_ROOTS`) for the
    bare literal, skipping files in *allowlist* (matched by repo-relative POSIX
    path).
    """
    violations: list[str] = []
    for pkg in _GLOBAL_STATE_SCAN_ROOTS:
        base = repo_root / pkg
        if not base.exists():
            continue
        for py in sorted(base.rglob("*.py")):
            rel = py.relative_to(repo_root).as_posix()
            if rel in allowlist:
                continue
            text = py.read_text(encoding="utf-8")
            for i, line in enumerate(text.splitlines(), start=1):
                if _line_has_bare_spec_kitty_literal(line):
                    violations.append(f"{rel}:{i}: {line.strip()}")
    return violations


def test_no_handrolled_spec_kitty_home_in_global_state_modules() -> None:
    """FR-010: no global-state module recomputes ``Path.home() / ".spec-kitty"``.

    Global sync/auth/tracker/daemon state must derive from the single
    authoritative ``get_runtime_root()`` resolver so ``SPEC_KITTY_HOME`` isolates
    all of it (issue #2171).  Any hand-rolled ``.spec-kitty`` home child outside
    the allowlist fails the build.
    """
    repo_root = pathlib.Path(__file__).resolve().parents[2]
    violations = _scan_global_state_for_home_literal(repo_root, _HOME_LITERAL_ALLOWLIST)
    assert not violations, (
        "Hand-rolled `.spec-kitty` home literal reintroduced in global-state "
        "modules (FR-010). Derive the path from "
        "`specify_cli.paths.get_runtime_root().base` instead:\n  " + "\n  ".join(violations)
    )


def test_home_literal_guard_is_non_vacuous() -> None:
    """The guard bites: without the allowlist, the keystone literal IS detected.

    Proves the regex matches the exact shape of the issue #2171 bug
    (``Path.home() / ".spec-kitty"`` lives in the keystone resolver) rather than
    passing vacuously — so a real re-scatter into a global-state module would be
    caught, not silently missed.
    """
    repo_root = pathlib.Path(__file__).resolve().parents[2]
    detected = _scan_global_state_for_home_literal(repo_root, frozenset())
    keystone = "src/specify_cli/paths/windows_paths.py"
    assert any(v.startswith(keystone + ":") for v in detected), (
        'Guard no longer detects the keystone\'s `Path.home() / ".spec-kitty"` '
        "literal — it would pass vacuously and miss a real re-scatter.\n"
        f"Detected: {detected!r}"
    )


def test_bare_spec_kitty_literal_matcher_precision() -> None:
    """The line matcher flags real recomputes but not docs/asset-home/comments."""
    assert _line_has_bare_spec_kitty_literal('base = Path.home() / ".spec-kitty"')
    assert _line_has_bare_spec_kitty_literal("LOCK_DIR = '.spec-kitty'")
    # Documentation ``path_pattern`` metadata carries a ~/ prefix + trailing path.
    assert not _line_has_bare_spec_kitty_literal('path_pattern="~/.spec-kitty/config.toml"')
    # Asset-home uses a different root (.kittify), never .spec-kitty.
    assert not _line_has_bare_spec_kitty_literal('return Path.home() / ".kittify"')
    # Pure comment lines are not user-facing recomputes.
    assert not _line_has_bare_spec_kitty_literal('    # Path.home() / ".spec-kitty"')
