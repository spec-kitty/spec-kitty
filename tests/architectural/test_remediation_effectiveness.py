"""FR-003 remediation-effectiveness enforcement (WP01).

Binding contract:
``kitty-specs/charter-preflight-remediation-01KYG9WK/contracts/remediation-effectiveness.md``
(C-EFF-1..6). Research census: ``research.md`` R-005 / R-006. Fixture shapes:
``data-model.md`` F1..F4.

The rule this module enforces, stated once (C-EFF-1):

    For every preflight check that emits a remediation, executing that
    remediation in a project exhibiting the check's non-passing state MUST
    change that check's state.

------------------------------------------------------------------------
THIS MODULE IS EXPECTED TO BE RED (NFR-002 red-first evidence / ADR
2026-07-17-1) until WP02 lands the corrective change to
``charter_runtime/freshness/computer.py``. It fails on the four
``spec-kitty charter sync`` states (lines 309, 318, 348, 357) because
``charter.sync.sync()`` is documented (``src/charter/sync.py:18``) as a pure
staleness reporter that never writes ``charter.yaml`` — the operator follows
the instruction, nothing changes, the gate refuses identically. Do not
silence, exempt, or weaken these assertions to make this module pass; WP02
is the change that turns it green.
------------------------------------------------------------------------

WP03 addendum: WP02 landed and turned all four ``charter sync`` cases
green. Two of the original seven parametrized cases (``charter_source``'s
``invalid`` state and ``synced_bundle``'s cascading ``stale`` state) then
surfaced a *second*, genuinely unfixable defect: WP02's own exhaustive
census proved no write path in the codebase can repair an unparseable
``charter.yaml`` (every one merges via a round-trip YAML parse — see
``computer.py``'s docstrings on those two branches). WP03 declared both a
member of ``_EXEMPT_STATES`` (C-EFF-2), made ``computer.py`` emit
``remediation=None`` for them, and closed the runner's matching backfill
(R-006, ``preflight/runner.py``) so an exempt check is shown no command
instead of a fabricated one. This is why ``_REMEDIATION_STATE_FLOOR`` and
``_CASES`` shrank from 7/7 to 5/5 while ``_EXEMPTION_FLOOR`` grew 0 -> 2 —
see ``test_exempt_check_output_names_check_with_no_command`` and
``test_backfill_cannot_return`` for the coverage that replaced the two
removed parametrized cases.

H3 addendum (#2831 HIGH finding, landed alongside H5/H1/H2 in the same
mission): ``_compute_charter_source``'s and ``_compute_synced_bundle``'s
``missing`` branches each split from one call site into two — an F1 ("no
charter at all") site keeping ``spec-kitty charter generate
--no-from-interview`` and a distinct F2 (legacy bundle present) site now
naming ``spec-kitty upgrade --yes`` instead. Both F1 and F2 used to share
the F1 command, so an operator whose project actually carried a legacy
``governance.yaml``/``directives.yaml``/``metadata.yaml``/``references.yaml``
bundle was told to run a command that generates a DEFAULT charter and
silently discards their governance content. ``_REMEDIATION_STATE_FLOOR``
grew 5 -> 7 and the floor-sum invariant 7 -> 9 to match (a genuine new-call-
site addition, not a state moving between the floor and the exemption set —
see the comment on that assertion below).

WP03 cycle-2 addendum: review cycle 1 found two gaps in this module's own
bookkeeping, neither touching ``computer.py``/``runner.py``:

1. The two floors were pinned independently but their SUM was not — a
   demonstrated exploit turned a real remediation-emitting state's
   ``remediation`` to ``None`` in ``computer.py`` without declaring it in
   ``_EXEMPT_STATES``, then dropped ``_REMEDIATION_STATE_FLOOR`` to match
   the smaller discovered count. Both individual floor assertions stayed
   green while a state silently lost all effectiveness coverage. Fixed at
   the time by pinning ``_REMEDIATION_STATE_FLOOR + _EXEMPTION_FLOOR == 7``
   — a state may legally MOVE between the two floors, but the total must
   never shrink unnoticed. WP08 later retired that floor-sum pin in favor
   of the stronger per-site partition check, ``test_every_construction_site_is_partitioned``
   (see its own docstring); ``test_exemption_set_meets_floor`` now asserts
   only its own ``>= _EXEMPTION_FLOOR`` non-vacuity floor.
2. ``_EXEMPT_STATES`` was keyed on ``(layer, lineno)`` — the one property
   this WP already proved unstable. A non-uniform line shift (e.g.
   reordering producer functions) could land a *different*, still
   remediation-emitting state on an exempt lineno and have it silently
   inherit the exemption. Fixed by re-keying on
   ``(producer_function_name, state_value)``, both AST-derived from the
   same ``FreshnessSubState(...)`` call ``_discover_remediation_emitting_states``
   already inspects (see ``_discover_remediation_emitting_states_full``) —
   an identity that survives arbitrary code movement. ``_CASES`` was
   deliberately left lineno-keyed: unlike ``_EXEMPT_STATES``, its lineno is
   never used to *compute* required coverage (that's ``case.layer``, used
   to look up the runner's composed output by name); a stale lineno there
   only shows up as a cosmetic parametrize-id / a loud mismatch in
   ``test_case_table_matches_ast_derived_states``, never a silent exclusion.

Registry enumeration (the set of check producers and the set of
remediation-emitting states) is derived from ``computer.py``'s own AST, not
hand-copied (DIRECTIVE_043 applied to this test itself) — see
``_discover_producers`` / ``_discover_remediation_emitting_states``. This is
what makes ``test_case_table_matches_ast_derived_states`` a real
non-vacuity guard: deleting a remediation-emitting branch, or a call to a
producer, shrinks the AST-derived set and turns the coverage-parity
assertion red — a check cannot silently drop out of scope.
"""

from __future__ import annotations

import ast
import inspect
import re
import shlex
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent

import pytest

from specify_cli.charter_runtime.freshness import computer as _computer_module
from specify_cli.charter_runtime.freshness.computer import compute_freshness
from specify_cli.charter_runtime.preflight.runner import _PASS_STATES, run_charter_preflight

from tests.specify_cli.charter_preflight._fixtures import (
    build_f1_no_charter,
    build_f2_legacy_bundle_no_charter_yaml,
    build_f4_invalid_charter_yaml,
    init_git_repo,
    seed_charter_yaml,
    seed_graph,
    seed_manifest,
)

# Whole-codebase AST walk (``_discover_remediation_emitting_states``) +
# subprocess CLI invocation (``run_cli``) — structurally incompatible with
# mutmut's forked sandbox (ADR 2026-04-20-1), same shape as
# ``tests/test_isolation_helpers.py``.
pytestmark = [pytest.mark.architectural, pytest.mark.git_repo, pytest.mark.non_sandbox]


# ---------------------------------------------------------------------------
# T002 — registry enumeration, derived from computer.py's own AST
# ---------------------------------------------------------------------------


def _discover_producers() -> tuple[str, ...]:
    """Return the check-producer function names ``compute_freshness`` calls.

    Derived from ``compute_freshness``'s own AST body — not a hand-copied
    list that can silently drift (T002). Removing a producer call from
    ``compute_freshness`` shrinks this tuple and turns
    ``test_producer_meets_floor`` red.
    """
    source = inspect.getsource(_computer_module.compute_freshness)
    tree = ast.parse(source)
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id.startswith("_compute_"):
            names.append(node.func.id)
    return tuple(dict.fromkeys(names))  # de-duplicated, first-seen order


def _classify_freshness_substate_call(
    node: ast.Call,
    function_name: str,
    module_string_constants: dict[str, str],
) -> tuple[int, str, str, bool]:
    """Classify ONE ``FreshnessSubState(...)`` call site as ``(lineno,
    function_name, state_value, has_remediation)``.

    Extracted from :func:`_discover_freshness_substate_sites` to keep that
    walker's own cyclomatic complexity down (NFR-005) — this is the per-call
    decision, the walker is only the module-wide traversal that finds calls.

    Fails closed: a construction whose ``state=`` value cannot be read as a
    string literal raises rather than silently skipping the site — a walker
    that skips an unreadable site would silently shrink the per-site
    partition (FR-007 F11) it exists to make exhaustive.
    """
    state_value: str | None = None
    has_remediation = False
    remediation_lineno: int | None = None
    for kw in node.keywords:
        if kw.arg == "state" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
            state_value = kw.value.value
        elif kw.arg == "remediation" and (
            (isinstance(kw.value, ast.Constant) and kw.value.value is not None) or (isinstance(kw.value, ast.Name) and kw.value.id in module_string_constants)
        ):
            # ``kw.value.lineno`` (not ``node.lineno``, which is the call's
            # opening line) so the reported line matches where
            # ``remediation=...`` actually reads in a multi-line call — this
            # is what makes the contract's cited line numbers (:309, :318,
            # ...) line up with what this discovers.
            has_remediation = True
            remediation_lineno = kw.value.lineno
    if state_value is None:
        raise AssertionError(
            f"FreshnessSubState(...) construction at line {node.lineno} in "
            f"{function_name} has no readable state= string literal — the "
            "per-site partition (FR-007 F11) must fail closed rather than "
            "silently skip an unclassifiable site"
        )
    lineno = remediation_lineno if remediation_lineno is not None else node.lineno
    return lineno, function_name, state_value, has_remediation


def _discover_freshness_substate_sites() -> tuple[tuple[int, str, str, bool], ...]:
    """Return ``(lineno, producer_function_name, state_value,
    has_remediation)`` for EVERY ``FreshnessSubState(...)`` construction site
    in ``computer.py`` — not only the remediation-emitting ones.

    This is the single AST walker (DIRECTIVE_043: one walk, not duplicated)
    the per-site partition (``test_every_construction_site_is_partitioned``)
    and the emitting-only views below
    (:func:`_discover_remediation_emitting_states_full`,
    :func:`_discover_remediation_emitting_states`) both derive from.

    AST-derived over the whole module (producers call helper functions —
    e.g. ``_synthesized_drg_graph_state`` — that are not textually nested
    inside the producer, so this must scan module-wide, not per-function —
    each top-level ``def`` is walked independently so a call is always
    attributed to the function that lexically contains it, never to a
    caller that merely delegates to it).

    ``producer_function_name`` and ``state_value`` are read from the
    ``state=``/``remediation=`` keywords, always siblings on the same call
    (confirmed by inspection of every branch in ``computer.py``). This pair
    is the semantically stable identity WP03 cycle 2 uses to key
    ``_EXEMPT_STATES`` — see the module docstring's cycle-2 addendum for
    why the lineno alone is not a safe key across an arbitrary code reorder.
    """
    source = inspect.getsource(_computer_module)
    tree = ast.parse(source)
    # Module-level ``NAME = "literal"`` bindings, so a remediation command that
    # has been hoisted to a named constant stays visible to this enforcement.
    #
    # This is not hypothetical tidiness. ``computer.py`` carries an S1192
    # de-duplication constant (``_REMEDIATE_CHARTER_SYNTHESIZE``) for the
    # command its three ``synthesized_drg`` branches share. A literal-only
    # walk does not see an ``ast.Name``, so those three states vanish from
    # discovery -- and a guard that silently stops covering three of five
    # states while still reporting green is the exact shape of defect this
    # module exists to prevent. Resolving the constant keeps enforcement
    # keyed on the emitted *command*, not on how it happens to be spelled.
    module_string_constants: dict[str, str] = {
        target.id: node.value.value
        for node in tree.body
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    results: list[tuple[int, str, str, bool]] = []
    for func_node in tree.body:
        if not isinstance(func_node, ast.FunctionDef):
            continue
        for node in ast.walk(func_node):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
                continue
            if node.func.id != "FreshnessSubState":
                continue
            results.append(_classify_freshness_substate_call(node, func_node.name, module_string_constants))
    return tuple(sorted(results))


def _discover_remediation_emitting_states_full() -> tuple[tuple[int, str, str], ...]:
    """Thin emitting-only projection of
    :func:`_discover_freshness_substate_sites` (same AST walk, not
    duplicated) — ``(lineno, producer_function_name, state_value)`` for
    every remediation-emitting site.
    """
    return tuple((lineno, function, state) for lineno, function, state, has_remediation in _discover_freshness_substate_sites() if has_remediation)


def _discover_remediation_emitting_states() -> tuple[int, ...]:
    """Return the source line numbers of every ``FreshnessSubState(...)``
    construction in ``computer.py`` whose ``remediation=`` keyword is a
    non-``None`` literal.

    Thin lineno projection of :func:`_discover_remediation_emitting_states_full`
    (same AST walk, not duplicated). Deleting or neutering a
    remediation-emitting branch shrinks this tuple and turns
    ``test_remediation_state_meets_floor`` red (C-EFF-4).
    """
    return tuple(lineno for lineno, _function, _state in _discover_remediation_emitting_states_full())


def _check_name_for_producer(producer_function_name: str) -> str:
    """Map an AST-derived producer function name (e.g.
    ``_compute_charter_source``) to the check/layer name used everywhere
    else in this module and in the runner's operator-visible output (e.g.
    ``charter_source``).

    The ``_compute_`` prefix is the only difference — see
    :class:`FreshnessResult`'s field names (``computer.py``) and
    ``_discover_producers``'s naming convention above. Asserts the prefix is
    present rather than silently returning the raw name, so a future
    producer that breaks this naming convention fails loudly here instead
    of silently mismatching a check name downstream.
    """
    prefix = "_compute_"
    assert producer_function_name.startswith(prefix), (
        f"producer function {producer_function_name!r} does not follow the {prefix!r} naming convention _check_name_for_producer relies on"
    )
    return producer_function_name.removeprefix(prefix)


# C-EFF-2: exemption is explicit and enumerable — membership is declared as
# data, never inferred from a ``None`` remediation. Keyed on
# ``(producer_function_name, state_value)`` — the same AST-derived pair
# ``_discover_remediation_emitting_states_full`` reads off the sibling
# ``state=``/``remediation=`` keywords of the exempted ``FreshnessSubState``
# call — rather than on line number (WP03 cycle-2 fix, review cycle 1
# required change 2). Line number was proven unsafe by this WP's own
# history: cycle-1 docstring edits moved these two sites from :318/:357 to
# :331/:377 with no functional change, and the reviewer additionally showed
# an out-of-order code edit could land an unrelated, still remediation-
# emitting state on a stale exempt lineno and have it silently inherit the
# exemption. Producer-function + state-value cannot alias that way and
# survives arbitrary code movement.
#
# WP03 populated this with the two states WP02 proved have no effective
# self-service remediation: `_compute_charter_source`'s `invalid` state and
# `_compute_synced_bundle`'s cascading `stale` state. Every write path in
# the codebase (`charter generate` bare/`--force`/`--no-from-interview`,
# `spec-kitty upgrade --yes`, `charter synthesize`, `charter resynthesize`,
# `charter interview --defaults` then generate) merges into the existing
# `charter.yaml` via a round-trip YAML parse
# (`charter_yaml_io.update_charter_yaml_section`, the sole writer path —
# INV-9), so all of them require the file to already parse first. None
# repairs broken YAML — an architectural gap, not a search failure. Both
# sites now emit `remediation=None` in `computer.py`, so they no longer
# appear in `_discover_remediation_emitting_states()`'s output either (see
# `_REMEDIATION_STATE_FLOOR` below).
_EXEMPT_STATES: frozenset[tuple[str, str]] = frozenset(
    {
        ("_compute_charter_source", "invalid"),
        ("_compute_synced_bundle", "stale"),
    }
)


# ---------------------------------------------------------------------------
# T005 — pinned floors (NFR-001 / C-EFF-4)
# ---------------------------------------------------------------------------

# R-005 census, as amended by WP03 then by the H3 fix (#2831 HIGH finding):
# `_compute_charter_source`'s and `_compute_synced_bundle`'s `missing`
# branches each SPLIT into two call sites (F1 "no charter at all" ->
# `spec-kitty charter generate --no-from-interview`; F2 "legacy bundle
# present" -> `spec-kitty upgrade --yes`) -- both used to share the F1
# command, silently discarding a legacy bundle's content (H3). That is
# 2 + 2 = 4 `missing`-state sites (was 2) + 3 `spec-kitty charter synthesize`
# sites (synthesized_drg) = 7. The :318/:357-equivalent sites (`invalid` /
# cascading `stale`) still emit `remediation=None` and are declared exempt
# above rather than counted here — WP03, a deliberate reviewed change (was
# 7, then 5).
#
# WP08 (FR-007 F11): a floor over SITES (non-vacuity), not a pin — the
# actual coverage guarantee is the per-site partition
# (`test_every_construction_site_is_partitioned`), which cannot be defeated
# by dropping this floor to match a shrunk count (the old `== 9` sum's own
# exploit). Update deliberately, in the same change, when a state is
# legitimately added — never to nudge a red run green.
_REMEDIATION_STATE_FLOOR = 7

# `_compute_charter_source`, `_compute_synced_bundle`, `_compute_synthesized_drg`
# (R-005). WP08 (FR-007 F11): a floor over sites (non-vacuity), not a pin.
# Update deliberately, in the same change, if a producer is added.
_PRODUCER_FLOOR = 3

# WP08 (FR-007 F11): a floor over sites (non-vacuity), not a pin — the
# per-site partition (`test_every_construction_site_is_partitioned`) is the
# actual coverage guarantee; a check failing C-EFF-1 being moved into
# `_EXEMPT_STATES` to dodge a red run now fails that partition's
# disjointness check directly, not only this floor.
#
# WP03: 0 -> 2, a deliberate reviewed change. WP02 proved exhaustively that
# `_compute_charter_source`'s `invalid` state and `_compute_synced_bundle`'s
# cascading `stale` state have no effective self-service remediation (see
# `_EXEMPT_STATES` above) — this is not a check being reclassified to dodge
# a red run, it is the two genuinely unfixable states the mechanism itself
# proved unfixable via `test_remediation_changes_check_state`.
_EXEMPTION_FLOOR = 2


def test_remediation_state_meets_floor() -> None:
    discovered = _discover_remediation_emitting_states()
    assert len(discovered) >= _REMEDIATION_STATE_FLOOR, (
        f"NFR-001: remediation-emitting site count dropped below the non-vacuity floor ({_REMEDIATION_STATE_FLOOR}); found {len(discovered)} at lines {discovered}."
    )


def test_producer_meets_floor() -> None:
    producers = _discover_producers()
    assert len(producers) >= _PRODUCER_FLOOR, (
        f"NFR-001: check-producer count dropped below the non-vacuity floor ({_PRODUCER_FLOOR}); found {len(producers)}: {producers}."
    )


def test_exemption_set_meets_floor() -> None:
    assert len(_EXEMPT_STATES) >= _EXEMPTION_FLOOR, (
        f"C-EFF-4: exemption-set size dropped below the non-vacuity floor ({_EXEMPTION_FLOOR}); found {len(_EXEMPT_STATES)}: {sorted(_EXEMPT_STATES)}."
    )
    # WP03 cycle 3 (review finding): a state's COUNT alone does not pin its
    # IDENTITY. Both currently-exempt states already emit `remediation=None`
    # in `computer.py`, so neither ever appears in
    # `_discover_remediation_emitting_states_full()` — which means
    # `_EXEMPT_STATES`' *values* are inert with respect to every other
    # assertion here. A reviewer demonstrated the exploit: swap one
    # legitimate member for a real, still-effective `(function, state)`
    # pair, drop the matching `_CASES` entry, and the module goes green
    # with real coverage silently gone. Pinning the exact set closes it:
    # changing WHICH states are exempt is now, like changing how many, a
    # deliberate act this assertion forces into the diff.
    expected_exempt = frozenset(
        {
            ("_compute_charter_source", "invalid"),
            ("_compute_synced_bundle", "stale"),
        }
    )
    assert expected_exempt == _EXEMPT_STATES, (
        "C-EFF-2: _EXEMPT_STATES membership drifted from the two states WP02 "
        f"proved unfixable; got {sorted(_EXEMPT_STATES)}. Exemption is a "
        "DECLARED, reviewed property — a state may only be added here with the "
        "same standard of proof WP02 applied (every write path exhausted), and "
        "swapping a member silently redirects the exemption onto a state that "
        "does have a working remediation, excluding it from C-EFF-1 testing."
    )


def test_every_construction_site_is_partitioned() -> None:
    """FR-007 F11 (WP08) — per-site partition, replacing the pinned
    floor-sum (`_REMEDIATION_STATE_FLOOR + _EXEMPTION_FLOOR == 9`) this WP
    retires.

    Every ``FreshnessSubState(...)`` construction site in ``computer.py``
    must fall into exactly one of three buckets: it emits a remediation, it
    is a documented passing state (``_PASS_STATES``), or it is a declared,
    reviewed exemption (``_EXEMPT_STATES``).

    A pair-level check (grouping two call sites that happen to share one
    ``(function, state)`` identity) can be defeated by neutering only ONE of
    the two sites while the pair as a whole still looks "emitting" — e.g.
    ``_compute_charter_source``'s two ``missing`` sites (:522, :528) share
    the pair ``("_compute_charter_source", "missing")``; neutering only one
    of them would still show that pair as emitting overall. This partition
    checks every SITE independently, so neutering either one fails on that
    site alone (WP08 B2, the split-site exploit the old ``== 9`` sum caught
    only by accident, and only at the aggregate level).
    """
    sites = _discover_freshness_substate_sites()
    for lineno, function, state, has_remediation in sites:
        assert has_remediation or state in _PASS_STATES or (function, state) in _EXEMPT_STATES, (
            f"construction site not covered by the partition: line {lineno} "
            f"in {function} (state={state!r}) neither emits a remediation, "
            "is a documented passing state, nor is declared exempt "
            f"(lineno={lineno}, function={function}, state={state})"
        )

    emitting_pairs = {(function, state) for _lineno, function, state, has_remediation in sites if has_remediation}
    disjointness_violations = emitting_pairs & _EXEMPT_STATES
    assert not disjointness_violations, f"disjointness violated: {sorted(disjointness_violations)} are declared exempt but also emit a remediation at some site"


# ---------------------------------------------------------------------------
# T003/T004 — the effectiveness driver, bound to the operator-visible surface
# ---------------------------------------------------------------------------

# Matches ``runner.py:245``'s composed line exactly:
#   f"{check.name} {check.state}; run `{check.remediation or '...'}`"
_BLOCKED_LINE_RE = re.compile(r"^(?P<name>\S+) (?P<state>\S+); run `(?P<command>.+)`$")


def _composed_command_for_layer(repo_root: Path, layer: str) -> str:
    """Return the exact remediation command the operator is shown for
    ``layer`` — extracted from the runner's COMPOSED ``blocked_reason``
    (C-EFF-3), never from ``check.remediation`` directly.

    Binding the field alone would report green while the operator was still
    shown ``spec-kitty charter status`` whenever a check emits ``None``
    (``runner.py:245``'s fallback, R-006) — a reporter that cannot change
    anything. T015 (WP03) extends coverage to that fallback branch; this
    helper's contract already binds the surface it lives on.
    """
    result = run_charter_preflight(repo_root, auto_refresh=False)
    assert result.blocked_reason is not None, f"expected a blocked_reason naming {layer!r}; preflight passed unexpectedly (checks={result.checks!r})"
    for line in result.blocked_reason.splitlines():
        match = _BLOCKED_LINE_RE.match(line)
        if match and match.group("name") == layer:
            return match.group("command")
    raise AssertionError(f"no blocked_reason line named layer {layer!r}: {result.blocked_reason!r}")


def _layer_state(repo_root: Path, layer: str) -> str:
    freshness = compute_freshness(repo_root)
    return str(getattr(freshness, layer).state)


def _assert_remediation_effective(
    repo_root: Path,
    layer: str,
    command: str,
    run_cli: Callable[..., subprocess.CompletedProcess[str]],
) -> None:
    """Execute ``command`` — exactly as shown to the operator — against the
    isolated fixture at ``repo_root`` and assert it was genuinely EFFECTIVE
    (C-EFF-1/C-EFF-7): the process exited 0 AND ``layer`` reached a
    documented passing state (``fresh``, or ``built_in_only`` where that is
    the documented pass — the same :data:`_PASS_STATES` the runner itself
    uses to decide ``passed``).

    H2 (#2831 HIGH finding): before this strengthening, only ``after !=
    before`` was checked — so a remediation that writes malformed YAML and
    returns exit code 17 PASSED, because ``missing -> invalid`` is a change
    even though ``invalid`` solves nothing and the process itself reported
    failure. See ``test_h2_...`` below for the non-vacuity proof that this
    strengthening actually catches that shape (a fake ``run_cli`` that
    changes state to a non-passing one, and a separate one that reports a
    non-zero exit despite reaching a passing state).

    C-EFF-5: ``repo_root`` must be an isolated fixture directory. Every
    caller in this module passes a ``tmp_path``-rooted fixture — never the
    developer's or CI's own repository checkout. ``run_cli`` (from
    ``tests/conftest.py``) invokes the CLI via ``python -m specify_cli`` with
    ``PYTHONPATH`` pinned to this checkout's own ``src/`` (not whatever
    ``spec-kitty`` happens to be installed on PATH), so the remediation under
    test is this worktree's code, not a stale global install.
    """
    before = _layer_state(repo_root, layer)
    args = shlex.split(command)
    assert args[:1] == ["spec-kitty"], f"unexpected remediation shape: {command!r}"
    completed = run_cli(repo_root, *args[1:])
    after = _layer_state(repo_root, layer)
    assert after != before, (
        f"`{command}` did not change {layer}'s state (stayed {before!r}); "
        f"exit={completed.returncode} "
        f"stdout={completed.stdout.strip()!r} stderr={completed.stderr.strip()!r}"
    )
    assert completed.returncode == 0, (
        f"`{command}` changed {layer} from {before!r} to {after!r} but the "
        f"process exited {completed.returncode} (non-zero) — a remediation "
        f"the operator ran and watched fail is not effective just because "
        f"some state moved; "
        f"stdout={completed.stdout.strip()!r} stderr={completed.stderr.strip()!r}"
    )
    assert after in _PASS_STATES, (
        f"`{command}` exited 0 and changed {layer} from {before!r} to "
        f"{after!r}, but {after!r} is not a documented passing state "
        f"({sorted(_PASS_STATES)}) — moving from one non-passing state to "
        f"another (e.g. missing -> invalid) is not effective (C-EFF-1/C-EFF-7)."
    )


# --- fixture builders feeding the driver table -----------------------------
#
# T001 provides the four named data-model.md shapes (F1..F4). The three
# ``synthesized_drg`` states aren't top-level data-model shapes — they are
# check-specific combinations built by composing T001's lower-level helpers
# directly (``init_git_repo`` / ``seed_charter_yaml`` / ``seed_manifest`` /
# ``seed_graph``), per DIRECTIVE_044: reuse the existing fixture primitives,
# never author a parallel mechanism.


def _fixture_charter_source_missing(root: Path) -> Path:
    """F2 — drives ``charter_source: missing`` and ``synced_bundle: missing``
    simultaneously: both read the same absent ``charter.yaml``."""
    return build_f2_legacy_bundle_no_charter_yaml(root)


def _fixture_charter_source_missing_f1(root: Path) -> Path:
    """F1 (H3, #2831 HIGH finding) — drives the SAME ``missing`` state as
    :func:`_fixture_charter_source_missing`, but with no legacy bundle on
    disk at all: "no charter, never initialised", distinct from F2's
    "legacy bundle present, not yet folded in". Exercises the OTHER of the
    two ``missing``-state call sites ``computer.py`` now emits — F1 keeps
    ``spec-kitty charter generate --no-from-interview`` (there is no legacy
    content to preserve), while F2 moved to ``spec-kitty upgrade --yes``."""
    return build_f1_no_charter(root)


def _fixture_exempt_pair(root: Path) -> Path:
    """F4 — drives the two exempt states (``charter_source: invalid`` and
    the cascading ``synced_bundle: stale``) simultaneously: ``synced_bundle``
    reads ``charter_source``'s ``invalid``. WP03: no longer a
    ``test_remediation_changes_check_state`` case (both sites emit
    ``remediation=None`` and are declared in ``_EXEMPT_STATES``) — retained
    for the T015 "no command in the composed output" coverage below."""
    return build_f4_invalid_charter_yaml(root)


def _fixture_drg_missing(root: Path) -> Path:
    """charter.yaml valid; no manifest, no graph.yaml. Isolates the
    synthesized_drg ``missing`` state — charter_source/synced_bundle both
    fresh."""
    init_git_repo(root)
    seed_charter_yaml(root)
    return root


def _fixture_drg_stale_bundle_not_fresh(root: Path) -> Path:
    """charter.yaml invalid + graph.yaml + manifest present (not
    built_in_only). Isolates the synthesized_drg ``stale`` state reached via
    the synced_bundle-not-fresh branch, before any hash comparison."""
    init_git_repo(root)
    seed_charter_yaml(root, valid=False)
    seed_manifest(root, built_in_only=False, bundle_content_hash=None)
    seed_graph(root)
    return root


def _fixture_drg_stale_hash_mismatch(root: Path) -> Path:
    """charter.yaml valid + graph.yaml + manifest with no stored hash.
    Isolates the synthesized_drg ``stale`` state reached via content-hash
    mismatch — charter_source/synced_bundle both fresh, only the DRG layer
    disagrees."""
    init_git_repo(root)
    seed_charter_yaml(root)
    seed_graph(root)
    seed_manifest(root, built_in_only=False, bundle_content_hash=None)
    return root


@dataclass(frozen=True)
class _EffectivenessCase:
    layer: str
    lineno: int
    build_fixture: Callable[[Path], Path]


# The 5-entry table (R-005 census, as amended by WP03). Kept in sync with
# the AST-derived enumeration by ``test_case_table_matches_ast_derived_states``
# below — the table cannot silently drop a discovered state without that
# test going red. WP03 removed the two entries for the states now declared
# in ``_EXEMPT_STATES`` (they emit ``remediation=None`` and no longer appear
# in the AST-derived discovery); see ``test_exempt_states_...`` below for
# their coverage.
#: Line numbers re-pinned by charter-preflight-remediation WP05 (out-of-map,
#: narrow edit to this WP01-owned table — anticipated and sanctioned by this
#: module's own cycle-2 addendum above: "a stale lineno there only shows up
#: as a cosmetic parametrize-id / a loud mismatch ..., never a silent
#: exclusion"). WP05 added a ``detail=`` distinguishing F1 from F2 to the
#: ``charter_source``/``synced_bundle`` ``missing`` branches in
#: ``computer.py``, shifting every subsequent ``remediation=`` keyword's
#: line down. Re-derived by running
#: ``_discover_remediation_emitting_states_full()`` against the current
#: file, not by hand-counting.
#: Re-pinned four times during the #2831 landing: first by upstream's own
#: edits to ``computer.py`` (411 -> 422, 464 -> 475, 569 -> 580, 600 -> 611,
#: 613 -> 624), then by this mission's charter.md F1/F2 fix (422 -> 445,
#: 475 -> 498, 580 -> 603, 611 -> 634, 624 -> 647), then by the H5 fix
#: (#2831 HIGH finding) that inserted ``_is_supported_charter_bundle`` ahead
#: of ``_compute_charter_source`` (445 -> 492, 498 -> 566, 603 -> 671,
#: 634 -> 702, 647 -> 715), then by the H3 fix (#2831 HIGH finding) that
#: split ``_compute_charter_source``'s and ``_compute_synced_bundle``'s
#: ``missing`` branches into distinct F1/F2 call sites: this GREW the table
#: from 5 to 7 rows (492 -> {525, 531}, 566 -> {612, 618}, 671 -> 723,
#: 702 -> 754, 715 -> 767) — not a pure re-pin, a genuine new-coverage
#: addition (see ``_REMEDIATION_STATE_FLOOR``'s comment). Multiple re-pins
#: in one landing are the cost of a positional key; it is tolerable only
#: because a stale lineno here fails LOUDLY in the parity test below rather
#: than silently dropping a state. Re-derived by running
#: ``_discover_remediation_emitting_states_full()`` against the current file,
#: never by hand-counting. The producer/state identities are unchanged
#: (`missing` remains `missing` — only the number of DISTINCT remediation
#: commands the state can emit changed, from 1 to 2, per producer).
_CASES: tuple[_EffectivenessCase, ...] = (
    _EffectivenessCase("charter_source", 525, _fixture_charter_source_missing),
    _EffectivenessCase("charter_source", 531, _fixture_charter_source_missing_f1),
    _EffectivenessCase("synced_bundle", 612, _fixture_charter_source_missing),
    _EffectivenessCase("synced_bundle", 618, _fixture_charter_source_missing_f1),
    _EffectivenessCase("synthesized_drg", 723, _fixture_drg_missing),
    _EffectivenessCase("synthesized_drg", 754, _fixture_drg_stale_bundle_not_fresh),
    _EffectivenessCase("synthesized_drg", 767, _fixture_drg_stale_hash_mismatch),
)


def test_case_table_matches_ast_derived_states() -> None:
    """The driver table must cover every AST-derived remediation-emitting
    state, minus declared exemptions — no silent narrowing (T005).

    Exemption membership is resolved via the semantically-stable
    ``(producer_function_name, state_value)`` identity (WP03 cycle-2 fix,
    review cycle 1 required change 2), never by directly comparing line
    numbers — a lineno is only used here as the resulting *set element* for
    the coverage-parity comparison against ``_CASES``, after exemption
    membership has already been decided semantically.
    """
    discovered_full = _discover_remediation_emitting_states_full()
    exempt_linenos = {lineno for lineno, function, state in discovered_full if (function, state) in _EXEMPT_STATES}
    discovered = {lineno for lineno, _function, _state in discovered_full}
    covered = {c.lineno for c in _CASES}
    expected = discovered - exempt_linenos
    assert covered == expected, (
        f"driver table must cover every non-exempt AST-derived remediation-emitting state; missing={expected - covered} extra={covered - expected}"
    )


@pytest.mark.parametrize("case", _CASES, ids=lambda c: f"{c.layer}_{c.lineno}")
def test_remediation_changes_check_state(
    case: _EffectivenessCase,
    tmp_path: Path,
    run_cli: Callable[..., subprocess.CompletedProcess[str]],
) -> None:
    """C-EFF-1: executing a check's remediation must change that check's
    state, evaluated against the composed operator-visible output (C-EFF-3).

    RED-FIRST (NFR-002): expected to fail for the four `charter sync` cases
    (309, 348, 318, 357) until WP02 lands — see module docstring.
    """
    repo_root = tmp_path
    case.build_fixture(repo_root)
    command = _composed_command_for_layer(repo_root, case.layer)
    _assert_remediation_effective(repo_root, case.layer, command, run_cli)


# ---------------------------------------------------------------------------
# T006 — non-vacuity: the mechanism can be shown to fail (C-EFF-6 / SC-005)
# ---------------------------------------------------------------------------


def test_mechanism_detects_an_ineffective_remediation(
    tmp_path: Path,
    run_cli: Callable[..., subprocess.CompletedProcess[str]],
) -> None:
    """A mechanism that cannot be shown to fail has not been shown to work.

    ``spec-kitty charter status`` is a pure reporter by construction (see the
    contract's "Known-ineffective remediations" table, and R-006 — it is the
    exact command ``runner.py`` used to backfill for a ``None``-remediation
    check, before WP03 closed that defect class). Substituting it in place
    of the real remediation for an otherwise-real fixture (F2) proves
    ``_assert_remediation_effective`` genuinely detects an ineffective
    command rather than passing vacuously.

    No source file is mutated by this test — only an isolated ``tmp_path``
    fixture and a genuinely-no-op real command are used — so no revert /
    teardown is required (sidesteps the mutation-injection pitfall called
    out in the WP prompt).
    """
    build_f2_legacy_bundle_no_charter_yaml(tmp_path)
    with pytest.raises(AssertionError, match="did not change"):
        _assert_remediation_effective(tmp_path, "charter_source", "spec-kitty charter status", run_cli)


# ---------------------------------------------------------------------------
# H2 (#2831 HIGH finding) — non-vacuity for the STRENGTHENED assertion:
# state-changed-but-not-effective must now fail where it used to pass
# ---------------------------------------------------------------------------


def test_h2_strengthened_assertion_catches_state_change_to_non_passing_state(
    tmp_path: Path,
) -> None:
    """H2 non-vacuity proof, primary case (the finding's own example).

    Before H2, ``_assert_remediation_effective`` asserted only ``after !=
    before`` — so a remediation that writes malformed YAML over a missing
    ``charter.yaml`` (moving ``charter_source`` from ``missing`` straight to
    ``invalid`` — a real state change, and a state ``computer.py`` itself
    treats as a genuine inconsistency with no effective remediation, C-EFF-2)
    would have PASSED this helper, because ``missing != invalid`` IS a
    change, even though ``invalid`` solves nothing for the operator.

    This is demonstrated with a fake ``run_cli``-shaped callable — not the
    real CLI — deliberately: it lets this test show the EXACT shape H2
    fixes (state moved to a documented non-passing value) without depending
    on finding or fabricating a real spec-kitty command that behaves this
    badly. The fake reports ``returncode=0`` (a "successful" run by the
    process's own account) so this specifically exercises the NEW
    passing-state check, not the exit-code check (see the sibling test
    below for that one). ``test_mechanism_detects_an_ineffective_remediation``
    above already covers the OTHER failure mode (state does not change at
    all) — this test covers the gap alongside it, not a replacement for it.
    """
    repo_root = tmp_path
    build_f1_no_charter(repo_root)
    before = _layer_state(repo_root, "charter_source")
    assert before == "missing"

    charter_yaml_path = repo_root / ".kittify" / "charter" / "charter.yaml"

    def fake_run_cli(project_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
        # Simulate a remediation that "ran successfully" (exit 0) but wrote
        # genuinely malformed YAML instead of a real charter bundle.
        charter_dir = project_path / ".kittify" / "charter"
        charter_dir.mkdir(parents=True, exist_ok=True)
        (charter_dir / "charter.yaml").write_text("not: [valid: yaml: at: all", encoding="utf-8")
        return subprocess.CompletedProcess(args=["spec-kitty", *args], returncode=0, stdout="", stderr="")

    with pytest.raises(AssertionError, match="not a documented passing state"):
        _assert_remediation_effective(
            repo_root,
            "charter_source",
            "spec-kitty charter generate --no-from-interview",
            fake_run_cli,
        )

    after = _layer_state(repo_root, "charter_source")
    assert after == "invalid", (
        f"fixture invariant: the fake remediation must have genuinely moved the state to "
        f"'invalid' (proving the OLD `after != before` check alone would have passed this "
        f"as 'effective'); got {after!r}"
    )
    assert charter_yaml_path.exists()


def test_h2_strengthened_assertion_catches_nonzero_exit_despite_state_change(
    tmp_path: Path,
) -> None:
    """H2 non-vacuity proof, exit-code half: a remediation that reaches a
    documented passing state must ALSO have exited 0 to count as effective.

    A remediation an operator watches fail (non-zero exit) is not
    "effective" merely because the on-disk state happens to have moved to a
    value this module treats as passing — the process's own report of
    failure must not be silently ignored. The fake ``run_cli`` here writes a
    genuinely valid, fresh charter bundle (so the OLD `after != before`
    check AND a state-only passing check would both have passed) but
    reports ``returncode=17``, isolating the exit-code half of the H2
    strengthening from the passing-state half proven by the sibling test
    above.
    """
    repo_root = tmp_path
    build_f1_no_charter(repo_root)
    before = _layer_state(repo_root, "charter_source")
    assert before == "missing"

    def fake_run_cli(project_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
        seed_charter_yaml(project_path)  # writes a genuinely valid, fresh charter.yaml
        return subprocess.CompletedProcess(args=["spec-kitty", *args], returncode=17, stdout="", stderr="boom failure\n")

    with pytest.raises(AssertionError, match="non-zero"):
        _assert_remediation_effective(
            repo_root,
            "charter_source",
            "spec-kitty charter generate --no-from-interview",
            fake_run_cli,
        )

    after = _layer_state(repo_root, "charter_source")
    assert after == "fresh", (
        f"fixture invariant: the fake remediation must have genuinely reached a passing "
        f"state (proving a state-only check would have passed this as 'effective' — only "
        f"the exit-code check catches it); got {after!r}"
    )


# ---------------------------------------------------------------------------
# T007 — C-EFF-7: the mechanism must also be shown to go GREEN
# ---------------------------------------------------------------------------


def test_assert_remediation_effective_recognizes_a_genuinely_effective_remediation(
    tmp_path: Path,
    run_cli: Callable[..., subprocess.CompletedProcess[str]],
) -> None:
    """C-EFF-7: a genuinely effective remediation must turn the affected case green.

    Added after WP01 review cycle 1, which found C-EFF-6 alone insufficient: a driver that
    fails on *every* remediation — including a correct one — satisfies C-EFF-6 (it can be
    shown to fail) while being useless as a gate. Worse, it makes WP02 impossible to complete
    honestly, since WP02 must turn ``test_remediation_changes_check_state`` green by correcting
    ``computer.py``'s remediation strings only, and WP02's reviewer is instructed to reject any
    edit to this file.

    This proves the opposite failure mode is absent, without touching ``computer.py`` (WP02's
    file — editing it here would destroy the red-first evidence the four failing parametrized
    cases above provide) and without mutating any source file that would need a revert: it
    invokes ``_assert_remediation_effective`` directly with ``spec-kitty upgrade --yes`` — a
    command ``computer.py`` does **not** currently emit for this state (it emits
    ``spec-kitty charter sync``, proven ineffective by the four red cases and the contract's
    "Known-ineffective remediations" table) — against the F2 fixture. ``spec-kitty upgrade
    --yes`` reaches ``ConsolidateCharterBundleMigration``, which composes ``charter.yaml`` from
    the legacy bundle, exactly as review cycle 1's flip test verified by direct migration-object
    invocation. This only reaches that migration because the F2 fixture now carries
    :func:`~tests.specify_cli.charter_preflight._fixtures.seed_realistic_agent_scaffolding`
    (added to ``build_f2_legacy_bundle_no_charter_yaml`` for this exact reason) — without it,
    the migration runner halts on the unrelated ``0.10.1_populate_slash_commands`` precondition
    before ever reaching the fix, which is precisely the false negative review cycle 1 flagged.
    """
    repo_root = tmp_path
    _fixture_charter_source_missing(repo_root)
    before = _layer_state(repo_root, "charter_source")
    assert before == "missing", f"fixture invariant violated: expected charter_source to start 'missing', got {before!r}"

    # Does not raise == the driver detected the state change (green). If this fixture were
    # still artificially minimal (pre review-cycle-1), this call would raise "did not change",
    # the same false negative review cycle 1 found.
    _assert_remediation_effective(repo_root, "charter_source", "spec-kitty upgrade --yes", run_cli)

    after = _layer_state(repo_root, "charter_source")
    assert after == "fresh", f"expected `spec-kitty upgrade --yes` to fully resolve charter_source to 'fresh' against a realistic F2 fixture; got {after!r}"


# ---------------------------------------------------------------------------
# H3 (#2831 HIGH finding) — the F2 remediation must be CONTENT-PRESERVING,
# not merely state-changing
# ---------------------------------------------------------------------------


def test_f2_remediation_composes_upgrade_yes_and_preserves_legacy_content(
    tmp_path: Path,
    run_cli: Callable[..., subprocess.CompletedProcess[str]],
) -> None:
    """H3 acceptance test: the composed remediation the operator is shown
    for an F2 (legacy-bundle) project must be ``spec-kitty upgrade --yes``
    — never the shared F1 command — AND running it must fold the legacy
    bundle's actual content into ``charter.yaml``, not overwrite it with a
    blank default.

    Before H3, ``_compute_charter_source``/``_compute_synced_bundle`` named
    ``spec-kitty charter generate --no-from-interview`` for F2 exactly as
    for F1. That command generates a DEFAULT charter and never reads
    ``governance.yaml``/``directives.yaml`` at all — an operator's real
    governance content (a distinctive, hand-authored directive here) would
    be silently discarded even though the gate reported success.
    ``ConsolidateCharterBundleMigration`` (reached via ``spec-kitty upgrade
    --yes``) is the only remediation that actually reads the legacy bundle
    (``m_unify_charter_activation_finalize.py::_compose_charter_yaml_document``),
    so this test seeds a marker no default-generated charter could produce
    by coincidence and asserts it survives verbatim into the written
    ``charter.yaml``.
    """
    repo_root = tmp_path
    build_f2_legacy_bundle_no_charter_yaml(repo_root)

    distinctive_directive_id = "DIRECTIVE_2831_CANARY"
    distinctive_title = "H3 canary: legacy governance content must survive remediation"
    (repo_root / ".kittify" / "charter" / "directives.yaml").write_text(
        dedent(
            f"""\
            directives:
              - id: {distinctive_directive_id}
                title: "{distinctive_title}"
                description: Marker directive proving the F2 remediation is content-preserving.
            """
        ),
        encoding="utf-8",
    )

    command = _composed_command_for_layer(repo_root, "charter_source")
    assert command == "spec-kitty upgrade --yes", (
        "expected the composed remediation for an F2 (legacy-bundle) project to be "
        f"`spec-kitty upgrade --yes`, not the content-discarding F1 command; got {command!r}"
    )

    _assert_remediation_effective(repo_root, "charter_source", command, run_cli)

    charter_yaml_path = repo_root / ".kittify" / "charter" / "charter.yaml"
    assert charter_yaml_path.exists(), "remediation must have written charter.yaml"
    written = charter_yaml_path.read_text(encoding="utf-8")
    assert distinctive_directive_id in written, (
        "the legacy directive's id must survive the F2 remediation into charter.yaml — "
        f"a content-discarding remediation would produce a default charter with no such "
        f"marker. Written charter.yaml:\n{written}"
    )
    assert distinctive_title in written, "the legacy directive's title must survive the F2 remediation into charter.yaml"


# ---------------------------------------------------------------------------
# T015 (WP03) — the runner's composed output for exempt checks, and a pin
# against the R-006 backfill returning
# ---------------------------------------------------------------------------


def test_exempt_check_output_names_check_with_no_command(tmp_path: Path) -> None:
    """C-EFF-2 / C-EFF-3: an exempt check's line in the composed
    ``blocked_reason`` must name the check and its state, and must not
    contain a ``run `...``` clause or any command (spec US1 Acceptance
    Scenario 3). "Nothing" is not the target — the diagnosis stays, only
    the fabricated command goes (WP03 task prompt).
    """
    repo_root = tmp_path
    _fixture_exempt_pair(repo_root)

    result = run_charter_preflight(repo_root, auto_refresh=False)
    assert result.blocked_reason is not None

    lines_by_name = {line.split(" ", 1)[0]: line for line in result.blocked_reason.splitlines()}
    states_by_name = {c.name: c.state for c in result.checks}
    exempt_names = {_check_name_for_producer(function) for function, _state in _EXEMPT_STATES}
    assert exempt_names <= lines_by_name.keys(), f"expected a blocked_reason line for every exempt check {sorted(exempt_names)!r}: {result.blocked_reason!r}"

    for name in exempt_names:
        line = lines_by_name[name]
        # No fabricated instruction (R-006) — `; run \`...\`` is the exact
        # shape a real remediation line takes. Prose that merely mentions a
        # command while explaining why it cannot help (e.g. the retained
        # `charter_source` detail text) is not bound by this — see C-EFF-2's
        # "prose that reads like escalation" carve-out; only an imperative
        # `run \`...\`` clause counts as a remediation.
        assert "run `" not in line, f"exempt check {name!r} still names a command: {line!r}"
        # Informative, not silent: something beyond "<name> <state>" is present.
        name_and_state_prefix_len = len(f"{name} {states_by_name[name]}")
        assert len(line) > name_and_state_prefix_len, f"exempt line reads as empty/uninformative: {line!r}"

    source_line = lines_by_name["charter_source"]
    bundle_line = lines_by_name["synced_bundle"]
    assert "invalid" in source_line
    assert "stale" in bundle_line
    assert "parse" in source_line.lower(), source_line
    assert "charter_source" in bundle_line.lower() or "parse" in bundle_line.lower(), bundle_line


def test_backfill_cannot_return(tmp_path: Path) -> None:
    """Regression pin for R-006: the fabricated ``spec-kitty charter status``
    fallback must never appear in the composed ``blocked_reason`` — for an
    exempt (``None``-remediation) check or otherwise. If ``runner.py`` ever
    reintroduces ``check.remediation or 'spec-kitty charter status'`` (or
    any other default-command backfill), this goes red.
    """
    repo_root = tmp_path
    _fixture_exempt_pair(repo_root)

    result = run_charter_preflight(repo_root, auto_refresh=False)
    assert result.blocked_reason is not None
    assert "charter status" not in result.blocked_reason, f"the runner backfilled a command for a check with no remediation: {result.blocked_reason!r}"
