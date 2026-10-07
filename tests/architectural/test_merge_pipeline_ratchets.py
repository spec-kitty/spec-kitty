"""WP03 — merge-pipeline ratchets (#1826 / #1736 residuals).

Recurrence guards for mission ``coordination-merge-stabilization-01KTXRVR``:

* **AC-B3** — no raw ``git update-ref`` subprocess invocation exists in
  ``src/specify_cli`` outside ``git/ref_advance.py``. Any new ref-advance
  site re-inherits #1826 (a checked-out worktree left behind its own HEAD)
  unless it goes through :func:`specify_cli.git.ref_advance.advance_branch_ref`.
* **AC-F1** — every subprocess call site in ``lanes/consolidation.py`` routes its
  environment through ``_make_merge_env()`` (FR-008b): no bare ``os.environ``
  copies outside the helper, and no subprocess call without an ``env=``
  keyword. Widened repo-wide for ``rebase``/``cherry-pick`` argv sites by
  #266, since #106 and #87 both slipped through the file-scoped version of
  this ratchet.
* **AC-F3** — the GENESIS fallback in
  ``coordination/status_transition.py`` catches exactly the two documented
  expected failures (``ValueError``, ``FileNotFoundError``); anything else
  propagates (FR-008d).
"""

from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

import pytest

import specify_cli
from specify_cli.status import Lane

pytestmark = [pytest.mark.architectural]

SRC_ROOT = Path(specify_cli.__file__).resolve().parent
LANES_MERGE = SRC_ROOT / "lanes" / "consolidation.py"
WORKTREE_ALLOCATOR = SRC_ROOT / "lanes" / "worktree_allocator.py"
REF_ADVANCE_RELPATH = Path("git") / "ref_advance.py"


def _python_sources() -> list[Path]:
    return sorted(SRC_ROOT.rglob("*.py"))


# ---------------------------------------------------------------------------
# AC-B3 — no raw update-ref outside git/ref_advance.py
# ---------------------------------------------------------------------------


def _update_ref_string_constants(tree: ast.AST) -> list[int]:
    """Line numbers of ``"update-ref"`` string constants (argv elements)."""
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value == "update-ref"
    ]


def test_no_raw_update_ref_outside_ref_advance_helper() -> None:
    """AC-B3 (#1826): ``advance_branch_ref`` is the only sanctioned way to
    advance a branch ref. A raw ``git update-ref`` bypasses the
    checked-out-worktree resync and re-introduces the defect class."""
    offenders: list[str] = []
    for source in _python_sources():
        relpath = source.relative_to(SRC_ROOT)
        if relpath == REF_ADVANCE_RELPATH:
            continue
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        offenders.extend(
            f"{relpath}:{lineno}" for lineno in _update_ref_string_constants(tree)
        )
    assert not offenders, (
        "Raw `git update-ref` invocation(s) found outside "
        "specify_cli/git/ref_advance.py — route them through "
        f"advance_branch_ref() (#1826 / AC-B3): {offenders}"
    )


# ---------------------------------------------------------------------------
# AC-F1 — single environment authority in the lane-merge pipeline
# ---------------------------------------------------------------------------


def _subprocess_run_names(tree: ast.AST) -> tuple[frozenset[str], frozenset[str]]:
    """Names a module's own imports bind to ``subprocess`` and to
    ``subprocess.run`` directly — ``import subprocess`` / ``import subprocess
    as X`` bind the module name; ``from subprocess import run`` / ``run as X``
    bind the function name straight through, bypassing the attribute form
    entirely (#296)."""
    module_names: set[str] = set()
    direct_run_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "subprocess":
                    module_names.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module == "subprocess":
            for alias in node.names:
                if alias.name == "run":
                    direct_run_names.add(alias.asname or alias.name)
    return frozenset(module_names), frozenset(direct_run_names)


def _is_subprocess_run_call(
    node: ast.Call,
    module_names: frozenset[str] = frozenset({"subprocess"}),
    direct_run_names: frozenset[str] = frozenset(),
) -> bool:
    """Match ``subprocess.run(...)`` under any import the call site actually
    used: the plain/aliased attribute form (``subprocess.run`` / ``_subprocess
    .run``) or a name bound directly to ``run`` via ``from subprocess import
    run``. ``module_names``/``direct_run_names`` should come from
    :func:`_subprocess_run_names` on the same module's tree — the default
    ``module_names`` of just ``"subprocess"`` only covers the unaliased case
    (#296)."""
    func = node.func
    if (
        isinstance(func, ast.Attribute)
        and func.attr == "run"
        and isinstance(func.value, ast.Name)
        and func.value.id in module_names
    ):
        return True
    return isinstance(func, ast.Name) and func.id in direct_run_names


def _single_call(tree: ast.AST) -> ast.Call:
    return next(node for node in ast.walk(tree) if isinstance(node, ast.Call))


def test_is_subprocess_run_call_matches_plain_attribute_form() -> None:
    """The un-aliased form every existing ratchet already relied on."""
    tree = ast.parse("import subprocess\nsubprocess.run(['git'], env=None)\n")
    module_names, direct_run_names = _subprocess_run_names(tree)
    assert _is_subprocess_run_call(_single_call(tree), module_names, direct_run_names)


def test_is_subprocess_run_call_matches_aliased_module_import() -> None:
    """#296: ``import subprocess as _subprocess`` (already live in
    ``invocation/executor.py``) presents as ``ast.Name(id="_subprocess")``,
    not ``ast.Name(id="subprocess")`` — the pre-#296 matcher missed it."""
    tree = ast.parse(
        "import subprocess as _subprocess\n_subprocess.run(['git', 'rebase'])\n"
    )
    module_names, direct_run_names = _subprocess_run_names(tree)
    assert _is_subprocess_run_call(_single_call(tree), module_names, direct_run_names)


def test_is_subprocess_run_call_matches_direct_run_import() -> None:
    """#296: ``from subprocess import run`` presents the call as a bare
    ``ast.Name(id="run")`` with no attribute access at all."""
    tree = ast.parse("from subprocess import run\nrun(['git', 'rebase'])\n")
    module_names, direct_run_names = _subprocess_run_names(tree)
    assert _is_subprocess_run_call(_single_call(tree), module_names, direct_run_names)


def test_is_subprocess_run_call_does_not_match_unrelated_name_call() -> None:
    """A call to some other ``run`` (e.g. a local function) must not be
    mistaken for ``subprocess.run`` just because no subprocess import binds
    that name in this module."""
    tree = ast.parse("def run(argv):\n    pass\nrun(['git'])\n")
    module_names, direct_run_names = _subprocess_run_names(tree)
    assert not _is_subprocess_run_call(_single_call(tree), module_names, direct_run_names)


def test_lanes_merge_subprocess_calls_route_env_through_helper() -> None:
    """AC-F1 (FR-008b): every ``subprocess.run`` in ``lanes/consolidation.py`` carries
    an explicit ``env=`` keyword (sourced from ``_make_merge_env``), so the
    pipeline has exactly one environment authority."""
    tree = ast.parse(LANES_MERGE.read_text(encoding="utf-8"), filename=str(LANES_MERGE))
    module_names, direct_run_names = _subprocess_run_names(tree)
    missing_env = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and _is_subprocess_run_call(node, module_names, direct_run_names)
        and not any(kw.arg == "env" for kw in node.keywords)
    ]
    assert not missing_env, (
        "subprocess.run call(s) in lanes/consolidation.py without an env= keyword "
        f"(must route through _make_merge_env, AC-F1): lines {missing_env}"
    )


def test_lanes_merge_no_bare_os_environ_outside_helper() -> None:
    """AC-F1 (FR-008b): no ``os.environ`` access in ``lanes/consolidation.py`` outside
    the ``_make_merge_env`` helper — no ad-hoc PATH/GIT_* mutations."""
    tree = ast.parse(LANES_MERGE.read_text(encoding="utf-8"), filename=str(LANES_MERGE))
    helper_spans: list[tuple[int, int]] = [
        (node.lineno, node.end_lineno or node.lineno)
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "_make_merge_env"
    ]
    assert helper_spans, "_make_merge_env must exist in lanes/consolidation.py (AC-F1)"

    offenders = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and node.attr == "environ"
        and isinstance(node.value, ast.Name)
        and node.value.id == "os"
        and not any(start <= node.lineno <= end for start, end in helper_spans)
    ]
    assert not offenders, (
        "bare os.environ access in lanes/consolidation.py outside _make_merge_env "
        f"(AC-F1): lines {offenders}"
    )


def test_make_merge_env_matches_historical_inline_construction() -> None:
    """T015 is refactor-only: the helper's env is byte-identical to the inline
    construction it replaced (venv-bin PATH prepend over ``os.environ``), apart
    from dropping an exported meta-driver two-way opt-out (#5460)."""
    from specify_cli.consolidation.drivers import META_DRIVER_TWO_WAY_ENV
    from specify_cli.lanes.consolidation import _make_merge_env

    expected = os.environ.copy()
    expected.pop(META_DRIVER_TWO_WAY_ENV, None)
    expected["PATH"] = (
        str(Path(sys.executable).parent) + os.pathsep + expected.get("PATH", "")
    )
    assert _make_merge_env() == expected


def _argv_includes_git_merge(node: ast.Call) -> bool:
    """True when the call's first positional arg is a list literal whose
    elements include the bare ``"merge"`` argv constant (a git-merge run)."""
    if not node.args:
        return False
    argv = node.args[0]
    if not isinstance(argv, ast.List):
        return False
    return any(
        isinstance(elt, ast.Constant) and elt.value == "merge" for elt in argv.elts
    )


_REBASE_CHERRY_PICK_ARGV = frozenset({"rebase", "cherry-pick"})


def _argv_includes_rebase_or_cherry_pick(node: ast.Call) -> bool:
    """True when the call's first positional arg is a list literal whose
    elements include the bare ``"rebase"`` or ``"cherry-pick"`` argv
    constant (a subprocess invocation that replays commits through git's
    three-way merge machinery, and so honors the registered merge drivers)."""
    if not node.args:
        return False
    argv = node.args[0]
    if not isinstance(argv, ast.List):
        return False
    return any(
        isinstance(elt, ast.Constant) and elt.value in _REBASE_CHERRY_PICK_ARGV
        for elt in argv.elts
    )


def test_rebase_and_cherry_pick_calls_route_env_through_helper_repo_wide() -> None:
    """#266 (follow-up from #106 / #87): every ``subprocess.run`` anywhere in
    ``src/specify_cli`` whose argv contains ``"rebase"`` or ``"cherry-pick"``
    carries an explicit ``env=`` keyword.

    #106's AC-F1 ratchets above only scanned ``lanes/consolidation.py``, so a bare
    rebase/cherry-pick call anywhere else in the package could (and did,
    twice: #106 in ``core/vcs/git.py``, #87 in
    ``lanes/worktree_allocator.py``) resolve ``spec-kitty`` through the
    ambient PATH instead of the routed merge-driver env, and fail whenever
    the CLI is not on that PATH. This widens the guard repo-wide so the
    defect class stays closed file-by-file no longer.
    """
    offenders: list[str] = []
    for source in _python_sources():
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        module_names, direct_run_names = _subprocess_run_names(tree)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and _is_subprocess_run_call(node, module_names, direct_run_names)
                and _argv_includes_rebase_or_cherry_pick(node)
                and not any(kw.arg == "env" for kw in node.keywords)
            ):
                offenders.append(f"{source.relative_to(SRC_ROOT)}:{node.lineno}")
    assert not offenders, (
        "subprocess.run call(s) with 'rebase'/'cherry-pick' in argv without "
        "an env= keyword (must route through _make_merge_env so the "
        f"registered merge drivers resolve the running CLI, #266): {offenders}"
    )


def test_worktree_allocator_git_merges_route_env_through_helper() -> None:
    """#87: every ``git merge`` subprocess call in ``lanes/worktree_allocator.py``
    carries an explicit ``env=`` keyword sourced from ``_make_merge_env``.

    The drivers registered by ``_ensure_merge_driver_git_config`` invoke bare
    ``spec-kitty ...``, so a merge run without that env resolves ``spec-kitty``
    through the ambient PATH and fails whenever the CLI is not on it (invoked
    by absolute path, through a wrapper, or from a harness with a stripped
    PATH) — a merge that would have succeeded reports a conflict instead.
    """
    tree = ast.parse(
        WORKTREE_ALLOCATOR.read_text(encoding="utf-8"),
        filename=str(WORKTREE_ALLOCATOR),
    )
    module_names, direct_run_names = _subprocess_run_names(tree)
    missing_env = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and _is_subprocess_run_call(node, module_names, direct_run_names)
        and _argv_includes_git_merge(node)
        and not any(kw.arg == "env" for kw in node.keywords)
    ]
    assert not missing_env, (
        "git merge subprocess.run call(s) in lanes/worktree_allocator.py "
        "without an env= keyword (must route through _make_merge_env so the "
        f"registered merge drivers resolve the running CLI, #87): {missing_env}"
    )


# ---------------------------------------------------------------------------
# AC-F3 — narrow GENESIS-fallback exception mask (FR-008d)
# ---------------------------------------------------------------------------


def _read_state(tmp_path: Path) -> tuple[Lane, str | None]:
    from specify_cli.coordination.status_transition import (
        read_current_wp_state_transactional,
    )

    feature_dir = tmp_path / "kitty-specs" / "099-mask-test"
    feature_dir.mkdir(parents=True, exist_ok=True)
    current = read_current_wp_state_transactional(
        feature_dir=feature_dir,
        mission_slug="099-mask-test",
        wp_id="WP01",
        repo_root=tmp_path,  # not a git repo → transaction topology unavailable
    )
    return current.lane, current.actor


def _absent_log_error() -> Exception:
    from specify_cli.status.lane_reader import CanonicalStatusNotFoundError

    return CanonicalStatusNotFoundError("expected miss")


@pytest.mark.parametrize(
    "expected_exc",
    [
        ValueError("expected miss"),
        FileNotFoundError("expected miss"),
        # The codebase's concrete "absent log" signal — the failure shape the
        # contract (R7) denotes by FileNotFoundError.
        _absent_log_error(),
    ],
    ids=["pre-schema-value", "absent-file", "absent-canonical-log"],
)
def test_genesis_fallback_catches_documented_expected_types(
    tmp_path: Path, expected_exc: Exception
) -> None:
    """AC-F3: the two documented expected failure shapes (pre-schema lane
    value, absent log/WP file) fall back to GENESIS."""
    from unittest.mock import patch

    with patch(
        "specify_cli.status.lane_reader.get_wp_lane",
        side_effect=expected_exc,
    ):
        lane, actor = _read_state(tmp_path)
    assert lane == Lane.GENESIS
    assert actor is None


def test_genesis_fallback_propagates_unexpected_exceptions(tmp_path: Path) -> None:
    """AC-F3: a non-expected exception (e.g. ``PermissionError``) is a real
    error signal and MUST propagate — the former broad ``except Exception``
    silently converted it into "unseeded WP" (#1736 dormant mask 1)."""
    from unittest.mock import patch

    with patch(
        "specify_cli.status.lane_reader.get_wp_lane",
        side_effect=PermissionError("events log unreadable"),
    ), pytest.raises(PermissionError):
        _read_state(tmp_path)
