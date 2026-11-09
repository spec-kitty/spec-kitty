"""Seeded-mutation harness: every check the reconciliation split moves is guarded by a corpus cell (NFR-008, SC-005, C-008, DIRECTIVE_043).

A characterization corpus that cannot fail proves nothing. Each row of :data:`MUTATIONS` seeds ONE
deterministic mutation of one check, installed in THIS process (where
``characterization_support.compute_cells`` computes the verdicts) through the reconciliation-family
helpers, and recomputes only the corpus cells the row names. Every named cell must now differ from
its golden value; :func:`test_unmutated_cells_match_golden` recomputes the same cells without a
mutation and shows they equal the golden value, so the mutation, not the fixture, moved them.

The tables below are the reviewable form of :data:`MUTATIONS`; ``test_docstring_table_matches_mutations``
keeps them in agreement (check id, target and expected red cells).

======================== ================================================ =============================================
check                    target                                           mutation
======================== ================================================ =============================================
kernel-bookkeeping       ``_is_bookkeeping``                              every path is bookkeeping (never content)
kernel-anchors           ``_closed_world_anchors``                        no anchor exempts anything
closed-world             ``_collect_excluded``                            nothing is excluded as canceled content
external-dependency-refs ``resolve_external_dependency_refs``             declared refs exempt no commit
approved-bound           ``_approved_bound_verdict``                      the stamp bound never refuses
write-branch             ``_write_branch_verdict``                        the Mission-branch bound never refuses
lane-tip-recheck         ``lane_tips_moved_refusal``                      the gate re-check never refuses
mixed-lane               ``_resolve_mixed_lane``                          a mixed lane resolves clean
canceled-dependency      ``_resolve_canceled_dependency_lanes``           no canceled dependency content is carried
authorship               ``_final_authored_walk``                         no authored blob survives the walk
presence                 ``unmet_approved_content``                       no approved content is ever missing
verifier-squash-axis     ``MergeOutcomeVerifier._unattributable_content_squash``  no path is unattributable
verifier-presence-axis   ``MergeOutcomeVerifier._approved_content_divergence``    no presence divergence
verifier-canceled-axis   ``MergeOutcomeVerifier._canceled_content_divergence``    no canceled-content divergence
rendering                ``_describe_approved_content_missing``           the divergence clause renders empty
claim-orchestration      ``build_approved_wp_set``                        the claim's refusal is removed
======================== ================================================ =============================================

Expected red cells (full corpus keys; each differs from its golden value under the row's mutation)::

    kernel-bookkeeping        ``fresh|single_lane|unattributable_squash_path``
                              ``fresh|single_lane|stamp=present|window=recorded|history_read_error``
    kernel-anchors            ``resume|mixed_lane_canceled_wp|stamp=present|window=recorded|dependency_lane_advanced``
                              ``resume|dependency_chain|stamp=present|window=recorded|dependency_lane_advanced_and_merged``
    closed-world              ``fresh|mixed_lane_canceled_wp|stamp=present|window=recorded``
                              ``fresh|fully_canceled_dependency|stamp=present|window=recorded``
    external-dependency-refs  ``fresh|single_lane|dependency_ref``
    approved-bound            ``fresh|single_lane|stamp=missing|window=any``
                              ``forecast|single_lane|post_approval_commit``
    write-branch              ``fresh|single_branch|stamp=missing|window=any``
    lane-tip-recheck          ``fresh|single_lane|lane_commit_during_run``
    mixed-lane                ``fresh|mixed_lane_canceled_wp|stamp=present|window=recorded``
    canceled-dependency       ``fresh|fully_canceled_dependency|stamp=present|window=recorded``
                              ``fresh|dependency_chain|stamp=present|window=recorded``
    authorship                ``fresh|single_lane|stamp=present|window=recorded``
                              ``fresh|two_wp_lane|stamp=present|window=recorded``
    presence                  ``fresh|single_lane|approved_content_missing_released``
    verifier-squash-axis      ``fresh|single_lane|unattributable_squash_path``
    verifier-presence-axis    ``fresh|single_lane|approved_content_missing_released``
    verifier-canceled-axis    ``fresh|mixed_lane_canceled_wp|stamp=present|window=recorded``
                              ``fresh|fully_canceled_dependency|stamp=present|window=recorded``
    rendering                 ``fresh|single_lane|approved_content_missing_released``
    claim-orchestration       ``fresh|single_lane|stamp=missing|window=any``
                              ``forecast|single_lane|post_approval_commit``


Rows that are reach or polarity mutations rather than weakenings (``closed-world``, ``mixed-lane``,
``canceled-dependency``, ``verifier-canceled-axis``): the corpus holds no cell in which canceled
content leaks, and under the default squash strategy no verdict reads the excluded sets, so a
WEAKENED check turns no cell red. Their mutations make the check refuse (or, for ``closed-world``,
raise), which proves a corpus cell reaches the check through the patched binding; they do not prove
that weakening the check would be caught. A leaking-content cell and a ``--strategy merge`` cell
(WP02's domain) would turn them into weakening guards.

Patching rules (WP04 guard): a function target is patched with
:func:`~tests.consolidation.reconciliation_family.setattr_reconciliation_family`, which patches every
family module that binds the name AND the by-name consumers (``phase_claim``, ``phase_gate``,
``forecast``); that is how ``build_approved_wp_set`` and ``lane_tips_moved_refusal`` reach their
callers. A method target patches the class attribute of ``MergeOutcomeVerifier``, whose class object
is identical before and after the split. No row patches a facade string target. Fakes that must keep
a result's type wrap the real function (looked up through the family helper, never through the
facade) and strip one field with :func:`dataclasses.replace`.
"""

from __future__ import annotations

import ast
import dataclasses
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn

import pytest

from specify_cli.consolidation.reconciliation import MergeOutcomeVerifier
from tests.consolidation import characterization_support as cs
from tests.consolidation.reconciliation_family import family_modules_binding, setattr_reconciliation_family

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


@dataclass(frozen=True)
class Mutation:
    """One seeded mutation: the check it guards, where it is installed, and the cells that must turn red."""

    check: str
    target: str
    mutation: str
    apply: Callable[[pytest.MonkeyPatch], None]
    expected_red_cells: tuple[str, ...]


# ---- helpers

_SEEDED_REFUSAL = "seeded mutation: this check refuses"


class _SeededMutationReached(Exception):
    """Raised by a fake whose check no default-strategy verdict can observe: the cell turns red because the check RAN."""


def _real(name: str) -> Callable[..., Any]:
    """The un-mutated function bound to *name* in the reconciliation family (the facade is never asked)."""
    real: Callable[..., Any] = getattr(family_modules_binding(name)[0], name)
    return real


def _patch_function(monkeypatch: pytest.MonkeyPatch, name: str, fake: Callable[..., Any]) -> None:
    setattr_reconciliation_family(monkeypatch, name, fake)


def _patch_verifier_method(monkeypatch: pytest.MonkeyPatch, name: str, fake: Callable[..., Any]) -> None:
    monkeypatch.setattr(MergeOutcomeVerifier, name, fake)


def _wrapping(name: str, edit: Callable[[Any], Any]) -> Callable[..., Any]:
    """A fake that calls the real *name* and returns ``edit(result)``."""
    real = _real(name)

    def _fake(*args: Any, **kwargs: Any) -> Any:
        return edit(real(*args, **kwargs))

    return _fake


# ---- the mutations (one named function per row)


def _mutate_kernel_bookkeeping(monkeypatch: pytest.MonkeyPatch) -> None:
    def _everything_is_bookkeeping(path: str, mission_slug: str | None = None, planning_prefix: str | None = None) -> bool:
        return True

    _patch_function(monkeypatch, "_is_bookkeeping", _everything_is_bookkeeping)


def _mutate_kernel_anchors(monkeypatch: pytest.MonkeyPatch) -> None:
    def _no_anchors(*_args: object, **_kwargs: object) -> list[str]:
        return []

    _patch_function(monkeypatch, "_closed_world_anchors", _no_anchors)


def _mutate_closed_world(monkeypatch: pytest.MonkeyPatch) -> None:
    def _excluded_collection_ran(*_args: object, **_kwargs: object) -> NoReturn:
        raise _SeededMutationReached(_SEEDED_REFUSAL)

    _patch_function(monkeypatch, "_collect_excluded", _excluded_collection_ran)


def _mutate_external_dependency_refs(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_function(monkeypatch, "resolve_external_dependency_refs", _wrapping("resolve_external_dependency_refs", _exempt_nothing))


def _exempt_nothing(attribution: Any) -> Any:
    return dataclasses.replace(attribution, shas=frozenset(), blobs=frozenset(), deletions=frozenset())


def _mutate_approved_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_function(monkeypatch, "_approved_bound_verdict", _wrapping("_approved_bound_verdict", _without_refusal))


def _without_refusal(result: Any) -> Any:
    return dataclasses.replace(result, refusal=None)


def _mutate_write_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_function(monkeypatch, "_write_branch_verdict", _wrapping("_write_branch_verdict", _without_refusal))


def _mutate_lane_tip_recheck(monkeypatch: pytest.MonkeyPatch) -> None:
    def _never_moved(*_args: object, **_kwargs: object) -> None:
        return None

    _patch_function(monkeypatch, "lane_tips_moved_refusal", _never_moved)


def _mutate_mixed_lane(monkeypatch: pytest.MonkeyPatch) -> None:
    def _always_refuses(*_args: object, **_kwargs: object) -> tuple[set[Any], list[str]]:
        return set(), [_SEEDED_REFUSAL]

    _patch_function(monkeypatch, "_resolve_mixed_lane", _always_refuses)


def _mutate_canceled_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    def _always_refuses(resolution: Any) -> Any:
        return dataclasses.replace(resolution, refusal=_SEEDED_REFUSAL)

    _patch_function(monkeypatch, "_resolve_canceled_dependency_lanes", _wrapping("_resolve_canceled_dependency_lanes", _always_refuses))


def _mutate_authorship(monkeypatch: pytest.MonkeyPatch) -> None:
    def _no_authored_blobs(walk: tuple[set[tuple[str, str]], set[str]]) -> tuple[set[tuple[str, str]], set[str]]:
        _blobs, deletions = walk
        return set(), deletions

    _patch_function(monkeypatch, "_final_authored_walk", _wrapping("_final_authored_walk", _no_authored_blobs))


def _mutate_presence(monkeypatch: pytest.MonkeyPatch) -> None:
    def _nothing_missing(*_args: object, **_kwargs: object) -> list[Any]:
        return []

    _patch_function(monkeypatch, "unmet_approved_content", _nothing_missing)


def _mutate_verifier_squash_axis(monkeypatch: pytest.MonkeyPatch) -> None:
    def _nothing_unattributable(self: object, *_args: object, **_kwargs: object) -> tuple[list[tuple[str, str]], list[str]]:
        return [], []

    _patch_verifier_method(monkeypatch, "_unattributable_content_squash", _nothing_unattributable)


def _mutate_verifier_presence_axis(monkeypatch: pytest.MonkeyPatch) -> None:
    def _no_divergence(self: object, *_args: object, **_kwargs: object) -> tuple[list[Any], None]:
        return [], None

    _patch_verifier_method(monkeypatch, "_approved_content_divergence", _no_divergence)


def _mutate_verifier_canceled_axis(monkeypatch: pytest.MonkeyPatch) -> None:
    def _always_refuses(self: object, *_args: object, **_kwargs: object) -> tuple[list[Any], str]:
        return [], _SEEDED_REFUSAL

    _patch_verifier_method(monkeypatch, "_canceled_content_divergence", _always_refuses)


def _mutate_rendering(monkeypatch: pytest.MonkeyPatch) -> None:
    def _renders_nothing(*_args: object, **_kwargs: object) -> str:
        return ""

    _patch_function(monkeypatch, "_describe_approved_content_missing", _renders_nothing)


def _mutate_claim_orchestration(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_function(monkeypatch, "build_approved_wp_set", _wrapping("build_approved_wp_set", _without_refusal))


# ---- the table


def _key(mode: str, shape: str, *rest: str) -> str:
    return "|".join((mode, shape, *rest))


_STAMP_MISSING = _key("fresh", "single_lane", "stamp=missing", "window=any")
_SINGLE_LANE_RECORDED = _key("fresh", "single_lane", "stamp=present", "window=recorded")
_TWO_WP_RECORDED = _key("fresh", "two_wp_lane", "stamp=present", "window=recorded")
_MIXED_RECORDED = _key("fresh", "mixed_lane_canceled_wp", "stamp=present", "window=recorded")
_FULLY_CANCELED_RECORDED = _key("fresh", "fully_canceled_dependency", "stamp=present", "window=recorded")
_CHAIN_RECORDED = _key("fresh", "dependency_chain", "stamp=present", "window=recorded")
_SQUASH_PATH = cs.NAMED_KEYS["mut_unattributable_squash_path"]
_PRESENCE_RELEASED = cs.NAMED_KEYS["mut_approved_content_missing_released"]
_LANE_COMMIT_DURING_RUN = cs.NAMED_KEYS["mut_lane_commit_during_run"]
_DEPENDENCY_REF = cs.NAMED_KEYS["mut_dependency_ref"]
_R09_FORECAST = cs.NAMED_KEYS["r09_post_approval_forecast"]
_HISTORY_READ_ERROR = cs.NAMED_KEYS["d_history_read_error"]
_RESUME_CLOSED_WORLD = cs.NAMED_KEYS["e_resume_closed_world"]
_RESUME_APPROVED_BOUND = cs.NAMED_KEYS["f_resume_approved_bound"]
_SINGLE_BRANCH_STAMP_MISSING = _key("fresh", "single_branch", "stamp=missing", "window=any")

MUTATIONS: tuple[Mutation, ...] = (
    Mutation(
        "kernel-bookkeeping",
        "_is_bookkeeping",
        "every path is bookkeeping, so no path is ever content",
        _mutate_kernel_bookkeeping,
        (_SQUASH_PATH, _HISTORY_READ_ERROR),
    ),
    Mutation(
        "kernel-anchors",
        "_closed_world_anchors",
        "no dependency-lane tip or target tip exempts a commit",
        _mutate_kernel_anchors,
        (_RESUME_CLOSED_WORLD, _RESUME_APPROVED_BOUND),
    ),
    Mutation(
        "closed-world",
        "_collect_excluded",
        "the excluded-content collection raises (reach only: the default squash verdict never reads its sets)",
        _mutate_closed_world,
        (_MIXED_RECORDED, _FULLY_CANCELED_RECORDED),
    ),
    Mutation(
        "external-dependency-refs",
        "resolve_external_dependency_refs",
        "a declared ref is honoured but exempts no commit, blob or deletion",
        _mutate_external_dependency_refs,
        (_DEPENDENCY_REF,),
    ),
    Mutation(
        "approved-bound",
        "_approved_bound_verdict",
        "the approval-stamp bound never refuses",
        _mutate_approved_bound,
        (_STAMP_MISSING, _R09_FORECAST),
    ),
    Mutation(
        "write-branch",
        "_write_branch_verdict",
        "the single_branch Mission-branch bound never refuses",
        _mutate_write_branch,
        (_SINGLE_BRANCH_STAMP_MISSING,),
    ),
    Mutation(
        "lane-tip-recheck",
        "lane_tips_moved_refusal",
        "the gate re-check never finds a lane that moved",
        _mutate_lane_tip_recheck,
        (_LANE_COMMIT_DURING_RUN,),
    ),
    Mutation(
        "mixed-lane",
        "_resolve_mixed_lane",
        "every mixed lane refuses (polarity flip: the corpus holds no leaking mixed lane)",
        _mutate_mixed_lane,
        (_MIXED_RECORDED,),
    ),
    Mutation(
        "canceled-dependency",
        "_resolve_canceled_dependency_lanes",
        "the canceled-dependency resolution always refuses (polarity flip: the corpus holds no leaking dependency)",
        _mutate_canceled_dependency,
        (_FULLY_CANCELED_RECORDED, _CHAIN_RECORDED),
    ),
    Mutation(
        "authorship",
        "_final_authored_walk",
        "no authored blob survives the spine walk",
        _mutate_authorship,
        (_SINGLE_LANE_RECORDED, _TWO_WP_RECORDED),
    ),
    Mutation(
        "presence",
        "unmet_approved_content",
        "no approved content is ever missing from the target",
        _mutate_presence,
        (_PRESENCE_RELEASED,),
    ),
    Mutation(
        "verifier-squash-axis",
        "MergeOutcomeVerifier._unattributable_content_squash",
        "no path of the squashed diff is unattributable",
        _mutate_verifier_squash_axis,
        (_SQUASH_PATH,),
    ),
    Mutation(
        "verifier-presence-axis",
        "MergeOutcomeVerifier._approved_content_divergence",
        "the presence axis reports no divergence",
        _mutate_verifier_presence_axis,
        (_PRESENCE_RELEASED,),
    ),
    Mutation(
        "verifier-canceled-axis",
        "MergeOutcomeVerifier._canceled_content_divergence",
        "the canceled-content axis always refuses (polarity flip: the corpus holds no leaking canceled content)",
        _mutate_verifier_canceled_axis,
        (_MIXED_RECORDED, _FULLY_CANCELED_RECORDED),
    ),
    Mutation(
        "rendering",
        "_describe_approved_content_missing",
        "the presence divergence clause renders empty, so its refusal code leaves the output",
        _mutate_rendering,
        (_PRESENCE_RELEASED,),
    ),
    Mutation(
        "claim-orchestration",
        "build_approved_wp_set",
        "the claim's refusal is removed after the checks ran",
        _mutate_claim_orchestration,
        (_STAMP_MISSING, _R09_FORECAST),
    ),
)

#: Every check the split moves (plan IC-10 / IC-11): one id each, 16 in all.
PHASE3_CHECKS = frozenset(
    {
        "kernel-bookkeeping",
        "kernel-anchors",
        "closed-world",
        "external-dependency-refs",
        "approved-bound",
        "write-branch",
        "lane-tip-recheck",
        "mixed-lane",
        "canceled-dependency",
        "authorship",
        "presence",
        "verifier-squash-axis",
        "verifier-presence-axis",
        "verifier-canceled-axis",
        "rendering",
        "claim-orchestration",
    }
)

#: Forked workers inherit a patch applied in this process, so a row may compute its cells in parallel.
_ROW_WORKERS = 4


def _recompute(cells: Iterable[str], workdir: Path, *, workers: int = 1) -> dict[str, Any]:
    names = sorted(set(cells))
    return cs.compute_cells(names, workdir, workers=min(workers, len(names)))


def _row_id(mutation: Mutation) -> str:
    return mutation.check


@pytest.mark.timeout(300)
@pytest.mark.parametrize("mutation", MUTATIONS, ids=_row_id)
def test_seeded_mutation_turns_cells_red(mutation: Mutation, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Install the row's mutation, recompute only its cells, and require every one to differ from the golden value."""
    golden = cs.load_golden()
    missing = [cell for cell in mutation.expected_red_cells if cell not in golden]
    assert not missing, f"{mutation.check}: cells absent from the golden file: {missing}"
    mutation.apply(monkeypatch)

    recomputed = _recompute(mutation.expected_red_cells, tmp_path, workers=_ROW_WORKERS)

    still_green = [cell for cell in mutation.expected_red_cells if recomputed[cell] == golden[cell]]
    header = f"{mutation.check} ({mutation.target}: {mutation.mutation})"
    assert not still_green, "\n".join(
        f"{header} left cell {cell} at its golden value:\n  golden:     {golden[cell]}\n  recomputed: {recomputed[cell]}" for cell in still_green
    )


@pytest.mark.timeout(600)
def test_unmutated_cells_match_golden(tmp_path: Path) -> None:
    """Control: the union of every row's cells, recomputed with NO mutation, equals the golden file (the mutation caused the red)."""
    cells = sorted({cell for mutation in MUTATIONS for cell in mutation.expected_red_cells})
    cs.assert_cells_match(_recompute(cells, tmp_path, workers=_ROW_WORKERS))


def test_every_moved_check_has_a_mutation() -> None:
    checks = [mutation.check for mutation in MUTATIONS]
    assert len(checks) == len(set(checks)), "one row per check"
    assert set(checks) >= PHASE3_CHECKS, f"checks without a mutation row: {sorted(PHASE3_CHECKS - set(checks))}"
    assert len(PHASE3_CHECKS) == 16


def test_every_row_has_a_real_target_and_cells() -> None:
    """A typo in a target or a cell key must fail here, not silently pin nothing."""
    golden = cs.load_golden()
    for mutation in MUTATIONS:
        assert mutation.expected_red_cells, f"{mutation.check}: no expected red cell"
        assert all(cell in golden for cell in mutation.expected_red_cells), mutation.check
        owner, _, method = mutation.target.rpartition(".")
        if owner:
            assert owner == "MergeOutcomeVerifier" and hasattr(MergeOutcomeVerifier, method), f"{mutation.check}: {mutation.target} is not a verifier method"
        else:
            assert family_modules_binding(mutation.target), mutation.check


_TABLE_ROW = re.compile(r"^([a-z]+(?:-[a-z]+)*)\s+``([^`]+)``")
_CELLS_ROW = re.compile(r"^([a-z]+(?:-[a-z]+)*)\s+``")
_CELL_KEY = re.compile(r"``([^`]+)``")


def _docstring_targets_and_cells() -> tuple[dict[str, str], dict[str, tuple[str, ...]]]:
    doc = __doc__ or ""
    table, _, cells = doc.partition("Expected red cells")
    targets = {m.group(1): m.group(2) for line in table.splitlines() if (m := _TABLE_ROW.match(line))}
    expected: dict[str, list[str]] = {}
    current = ""
    for line in cells.splitlines():
        if not line.strip():
            current = ""  # a blank line ends a row block
            continue
        row = _CELLS_ROW.match(line.strip())
        if row:
            current = row.group(1)
            expected[current] = []
        if current:
            expected[current].extend(_CELL_KEY.findall(line))
    return targets, {check: tuple(keys) for check, keys in expected.items()}


def test_docstring_table_matches_mutations() -> None:
    targets, cells = _docstring_targets_and_cells()
    assert targets == {mutation.check: mutation.target for mutation in MUTATIONS}
    assert cells == {mutation.check: mutation.expected_red_cells for mutation in MUTATIONS}


def test_no_row_patches_a_facade_string_target() -> None:
    """The WP04 guard covers string patches across the corpus; this file also never spells one (it patches through the family helper)."""
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    string_targets = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"setattr", "patch"}
        and node.args
        and isinstance(node.args[0], ast.Constant)
    ]
    assert not string_targets, f"string patch targets at lines {string_targets}"
