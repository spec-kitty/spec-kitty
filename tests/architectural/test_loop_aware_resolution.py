"""Loop-aware resolution gate (#3189, WP04): close hand-rolled loop-error translation by construction.

Modelled on ``tests/architectural/test_no_follow_symlinks_apply_ban.py`` +
``_no_follow_symlinks_apply_scan.py`` for the detector shape, and on
``tests/architectural/test_os_detection_ban.py`` /
``tests/architectural/test_lock_primitive_ban.py`` for the **allowlist**
shape: findings are matched against a content-addressed allowlist through
the D-OP-9 matching authority (``tests.architectural._content_identity``),
never a hand-rolled comparator and never a raw ``(path, function, N)``
tuple key -- ``tests/architectural/test_ratchet_positional_anchor_ban.py``
bans exactly that positional-anchor shape. See
``tests.architectural._loop_aware_resolution_scan`` for the full detector
rationale, the stated scope limit (FR-005: hand-rolled ``RuntimeError``/
``ELOOP`` translation only, not the wider resolve-then-contain shape), and
the excluded primitive module (``src/kernel/resolution.py``).

The single sanctioned door is
``kernel.resolution.resolve_rejecting_loops`` (WP01); WP02 and WP03 migrated
their owned call sites onto it. WP04 owns only this gate, not the remaining
call sites -- every hit left in the tree after WP02/WP03 is allowlisted here
with a one-line reason, never migrated (ownership).

Allowlist mechanics
--------------------
Each ``ALLOWLIST`` entry is a
:class:`~tests.architectural._ratchet_keys.ContentDescriptor`
(``rel_path``, ``qualname``, ``token_substring``, ``occurrence``,
``rationale``). A finding's own composite key is built the same way the
sibling gates build theirs: ``(relpath, *composite_key(source, lineno))``,
where ``lineno`` is the offending ``try`` statement's own line (so the
normalized token line is always literally ``"try :"`` -- the ``try:``
keyword itself, not its body). Descriptors are resolved with
:func:`~tests.architectural._content_identity.resolve_allowlist` and
findings are split with
:func:`~tests.architectural._content_identity.partition_findings` --
never a bespoke matcher (D-OP-9). Findings are keyed by **qualname**
(``StaticHandler.handle_static``, ``FixMemoryStructureMigration.detect``,
...), the same dotted enclosing-scope identity every other content-keyed
gate uses -- not the bare function name a positional ``(path, name, N)``
tuple would have used. A function with more than one ``try:`` statement
(offending or not) needs an explicit ``occurrence`` ordinal to disambiguate,
because every ``try:`` line normalizes to the same token text.
"""

from __future__ import annotations

import ast
import errno
from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path

import pytest

from tests.architectural import _loop_aware_resolution_scan as scan
from tests.architectural._content_identity import (
    partition_findings,
    render_descriptor_line,
    resolve_allowlist,
    with_blank_line_at_top,
    with_probe_above_statement,
)
from tests.architectural._loop_aware_resolution_scan import Violation
from tests.architectural._ratchet_keys import CompositeKey, ContentDescriptor, composite_key

pytestmark = [pytest.mark.architectural, pytest.mark.fast]

#: T017 (re-expressed, fold #3189): the allowlist, keyed by CONTENT through
#: :class:`ContentDescriptor` -- (rel_path, qualname, token_substring,
#: occurrence, rationale), resolved through the shared D-OP-9 matcher rather
#: than a hand-rolled comparator or a raw ``(path, name, N)`` tuple (banned by
#: ``test_ratchet_positional_anchor_ban.py``). Every entry below was read at
#: its actual call site before its rationale was written. Migrating a site
#: onto ``resolve_rejecting_loops`` removes its entry and lowers
#: ``_ALLOWLIST_CEILING``.
ALLOWLIST: tuple[ContentDescriptor, ...] = (
    # (Fold #3189: `safe_commit_command`'s entry lived here. Its file
    # arguments now resolve through `_resolve_file_argument` /
    # `kernel.resolution.resolve_rejecting_loops` instead of a bare
    # `.resolve()`, so its `try:` body no longer calls `resolve`/`realpath`
    # at all -- the site is structurally clean, not merely allowlisted, and
    # the entry was removed. `_ALLOWLIST_CEILING` dropped from 9 to 8
    # alongside this removal. The same happened for `spec_commit_command`
    # and `record_report_transaction`: `ProtectionPolicy.resolve()` (policy
    # resolution, not path resolution) no longer sits in a `try:` whose
    # handler names `RuntimeError`, so both entries were removed and the
    # ceiling dropped again, from 8 to 6. `_commit_analysis_report` was
    # kept clean the same way, by resolving the policy outside its commit
    # `try:`.)
    #
    # The `os.readlink` fallback in `get_active_mission` is only reached
    # after `active_mission_link.exists()` returned True, and `exists()`
    # reports a symlink loop as absent on every interpreter. A looping
    # active-mission link therefore takes the software-dev default before
    # this try runs, so its `RuntimeError` arm never sees a loop.
    # `get_active_mission` has two `try:` statements; `occurrence=1` (source
    # order) selects this one.
    ContentDescriptor(
        "src/specify_cli/mission.py",
        "get_active_mission",
        "try :",
        1,
        "Unreachable for a loop: the enclosing `active_mission_link.exists()` check reports a "
        "looping link as absent on every interpreter, so the software-dev default is chosen first.",
    ),
    # `detect()`'s two symlink-health probes (`.kittify/memory`, then
    # `.kittify/AGENTS.md`) treat any `(OSError, RuntimeError)` from
    # `.resolve()` as "broken symlink, migration needed". On 3.11/3.12 a loop
    # raises `RuntimeError` into that arm; on 3.13+ `resolve()` returns a path
    # still inside the loop, and the following `not resolved.exists()` check
    # (a loop never exists) reaches the same verdict. `detect()` has exactly
    # two `try:` statements, one per probe -- `occurrence=0`/`1` select them
    # in source order.
    ContentDescriptor(
        "src/specify_cli/upgrade/migrations/m_0_10_8_fix_memory_structure.py",
        "FixMemoryStructureMigration.detect",
        "try :",
        0,
        "3.11/12 loop raises RuntimeError (caught here); on 3.13+ resolve() returns a path still "
        "inside the loop and the next `not resolved.exists()` check treats it as broken -- both "
        "interpreters converge on the same 'needs migrating' verdict (kittify_memory probe).",
    ),
    ContentDescriptor(
        "src/specify_cli/upgrade/migrations/m_0_10_8_fix_memory_structure.py",
        "FixMemoryStructureMigration.detect",
        "try :",
        1,
        "Same convergent-verdict reasoning as the kittify_memory probe above, applied to the "
        ".kittify/AGENTS.md symlink-health probe: both interpreters converge on 'needs migrating'.",
    ),
    # `apply()`'s worktree cleanup mirrors `detect()` exactly: a loop is
    # either caught (3.11/12 `RuntimeError`) or fails the following
    # `not resolved.exists()` check (3.13+), so both interpreters converge on
    # "remove the broken worktree symlink". `apply()` has six `try:`
    # statements in total (most are unrelated shutil.move/copytree fallback
    # handling); the two symlink-health probes are `occurrence=2` and
    # `occurrence=4` in source order.
    ContentDescriptor(
        "src/specify_cli/upgrade/migrations/m_0_10_8_fix_memory_structure.py",
        "FixMemoryStructureMigration.apply",
        "try :",
        2,
        "Same convergent-verdict reasoning as detect() above, applied to the worktree memory "
        "symlink cleanup in apply(): both interpreters converge on 'remove the broken worktree "
        "symlink'.",
    ),
    ContentDescriptor(
        "src/specify_cli/upgrade/migrations/m_0_10_8_fix_memory_structure.py",
        "FixMemoryStructureMigration.apply",
        "try :",
        4,
        "Same convergent-verdict reasoning as detect() above, applied to the worktree AGENTS.md "
        "symlink cleanup in apply(): both interpreters converge on 'remove the broken worktree "
        "symlink'.",
    ),
)

#: T018.2 floor: observed via `count_resolution_call_sites` on the real tree
#: at T016/T017 landing time was 503 (`resolve`/`realpath` bare-name
#: matches -- this over-broadly also counts non-path `.resolve()` calls such
#: as `ProtectionPolicy.resolve`, hence the 90% floor rather than an exact
#: count). 90% of 503 is 452.7; the floor below is 452, i.e. just below the
#: observed count so ordinary file churn does not flake the gate while an
#: accidental mass-deletion of resolution call sites still trips it.
MIN_RESOLUTION_CALL_SITES = 452

#: T018.2 floor: observed via `count_resolve_rejecting_loops_call_sites` on
#: the real tree at T016/T017 landing time was 14 call sites. The floor is
#: the observed count minus one, per the WP04 prompt's stated floor rule.
MIN_RESOLVE_REJECTING_LOOPS_CALL_SITES = 13

#: Lower this when an entry is migrated; never raise it without an ownership decision.
_ALLOWLIST_CEILING = 6


def _parse(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _violations_for_file(path: Path) -> list[Violation]:
    return scan.find_violations(_parse(path), scan.relpath(path))


def collect_violations(paths: Iterable[Path]) -> list[Violation]:
    """Every offending ``try`` block across ``paths``, in scan order."""
    violations: list[Violation] = []
    for path in paths:
        violations.extend(_violations_for_file(path))
    return violations


# ---------------------------------------------------------------------------
# Content-keyed findings (D-OP-9): (relpath, qualname, token_line) per finding.
# ---------------------------------------------------------------------------


def _scanned_sources() -> dict[str, str]:
    """``{repo-relative path: source}`` for every scanned file."""
    return {scan.relpath(path): path.read_text(encoding="utf-8") for path in scan.iter_python_files()}


def _findings(sources: Mapping[str, str]) -> list[tuple[CompositeKey, Violation]]:
    """Every offending ``try`` in ``sources``, keyed by ``(relpath, qualname, token_line)``.

    The key is built the same way every sibling content-keyed gate builds
    theirs: ``composite_key(source, lineno)`` at the violation's own line
    (the ``try:`` statement itself), qualified with its file's relpath.
    """
    findings: list[tuple[CompositeKey, Violation]] = []
    for relpath, source in sorted(sources.items()):
        tree = ast.parse(source, filename=relpath)
        for violation in scan.find_violations(tree, relpath):
            key = (relpath, *composite_key(source, violation.lineno))
            findings.append((key, violation))
    return findings


def _source_under_repo(relpath: str) -> str:
    return (scan.REPO_ROOT / relpath).read_text(encoding="utf-8")


def _resolved_allowlist(source_for: Mapping[str, str] | None = None) -> tuple[Counter[CompositeKey], list[tuple[ContentDescriptor, str]]]:
    """Resolve :data:`ALLOWLIST` against ``source_for`` (default: the real tree)."""
    lookup = source_for.__getitem__ if source_for is not None else _source_under_repo
    return resolve_allowlist(ALLOWLIST, lookup)


def _split_findings(sources: Mapping[str, str], allowed: Counter[CompositeKey]) -> tuple[list[Violation], list[Violation], Counter[CompositeKey]]:
    """``(unexpected, suppressed, unused)`` via :func:`partition_findings` -- never a hand-rolled matcher."""
    findings = _findings(sources)
    unexpected, unused = partition_findings(findings, allowed)
    unexpected_ids = {id(v) for v in unexpected}
    suppressed = [v for _key, v in findings if id(v) not in unexpected_ids]
    return unexpected, suppressed, unused


def test_scanned_file_floor_is_met() -> None:
    """A detector silently scanning zero (or near-zero) files must go red, not green."""
    scanned = scan.iter_python_files()

    assert len(scanned) > scan.MIN_SCANNED_FILES, (
        f"only {len(scanned)} files scanned under {scan.SRC_ROOT} -- the loop-aware resolution gate would otherwise pass vacuously."
    )


def test_no_unallowlisted_hand_rolled_loop_translation() -> None:
    """T018.1: the real tree has zero unallowlisted offenders.

    Findings are matched against the content-addressed allowlist through
    :func:`~tests.architectural._content_identity.partition_findings`
    (D-OP-9) -- never a hand-rolled comparator.

    Non-vacuity (T018.4 below) proves this assertion is load-bearing by
    planting synthetic offenders and observing the same detector go red.
    """
    allowed, errors = _resolved_allowlist()
    assert errors == [], f"unresolvable ALLOWLIST descriptor(s): {errors}"
    unexpected, _suppressed, _unused = _split_findings(_scanned_sources(), allowed)

    assert unexpected == [], (
        "A try-block that calls resolve()/realpath() and hand-translates a "
        "RuntimeError/ELOOP is banned (#3189/FR-005): route through "
        "kernel.resolution.resolve_rejecting_loops instead, or add a "
        "ContentDescriptor entry with a one-line reason to "
        "tests/architectural/test_loop_aware_resolution.py ALLOWLIST if this "
        "is a currently-tracked, not-yet-remediated site.\n"
        "Violations:\n" + "\n".join(f"  {v.relpath}::{v.enclosing_function}#{v.ordinal} (line {v.lineno})" for v in unexpected)
    )


def test_every_allowlist_entry_is_a_real_violation() -> None:
    """T018.3: anti-staleness -- every allowlist entry must resolve to, and suppress, a real hit today."""
    allowed, errors = _resolved_allowlist()
    _unexpected, _suppressed, unused = _split_findings(_scanned_sources(), allowed)

    stale = [f"  {render_descriptor_line(descriptor)} ({descriptor.rationale}): {reason}" for descriptor, reason in errors]
    stale += [f"  {key} suppresses no live violation" for key in sorted(unused.elements())]
    assert not stale, (
        "The following ALLOWLIST entries in test_loop_aware_resolution.py no "
        "longer correspond to a real violation -- delete them (the site is "
        "already clean, or was renamed/moved and needs a new descriptor):\n" + "\n".join(stale)
    )


def test_allowlist_never_grows_past_its_landing_size() -> None:
    """T018.3 (shrink-only): the allowlist holds at most the 6 hits this fold left behind.

    This is a floor on the allowlist itself, distinct from the zero-offender
    assertion above: the allowlist may only ever SHRINK (a future WP
    migrating one of these onto `resolve_rejecting_loops` removes its
    entry), never grow silently. A grown allowlist without a corresponding
    ownership decision is itself a regression this test catches.
    """
    assert len(ALLOWLIST) <= _ALLOWLIST_CEILING, (
        f"expected at most {_ALLOWLIST_CEILING} allowlisted hits (mission landing state), found {len(ALLOWLIST)} "
        "-- growth requires an explicit ownership decision, not a silent addition."
    )


def test_resolve_rejecting_loops_adoption_floor_is_met() -> None:
    """T018.2: the migrated primitive's call-site count must not have regressed."""
    total = sum(scan.count_resolve_rejecting_loops_call_sites(_parse(path)) for path in scan.iter_python_files())

    assert total >= MIN_RESOLVE_REJECTING_LOOPS_CALL_SITES, (
        f"resolve_rejecting_loops call sites dropped to {total}, below the floor of "
        f"{MIN_RESOLVE_REJECTING_LOOPS_CALL_SITES} (observed 14 at T016/T017 landing time) -- "
        "a WP02/WP03 migration may have been reverted."
    )


def test_resolution_call_site_floor_is_met() -> None:
    """T018.2: the raw resolve()/realpath() call-site count must not have collapsed.

    This is a coarse floor, not a semantic one: `count_resolution_call_sites`
    matches on the bare `resolve`/`realpath` name, which also counts
    non-path `.resolve()` calls (e.g. `ProtectionPolicy.resolve`), so an
    exact count is not meaningful -- 90% of the observed count is.
    """
    total = sum(scan.count_resolution_call_sites(_parse(path)) for path in scan.iter_python_files())

    assert total >= MIN_RESOLUTION_CALL_SITES, (
        f"resolve()/realpath() call sites dropped to {total}, below the 90% floor of {MIN_RESOLUTION_CALL_SITES} (observed 503 at T016/T017 landing time)."
    )


# ---------------------------------------------------------------------------
# Drift tolerance (mirrors test_os_detection_ban.py / test_lock_primitive_ban.py).
# ---------------------------------------------------------------------------


#: The distinct files ALLOWLIST names -- the drift proof's parameters.
_DRIFT_FILES: tuple[str, ...] = tuple(sorted({descriptor.rel_path for descriptor in ALLOWLIST}))

#: Floor on ``_DRIFT_FILES`` so the drift proof cannot pass over a shrunken set.
_DRIFT_FILES_FLOOR = 2


def _exemption_count_for(relpath: str) -> int:
    return sum(1 for descriptor in ALLOWLIST if descriptor.rel_path == relpath)


def _probe_every_site(source: str, linenos: list[int]) -> str:
    """Insert a drift probe above each site's statement, bottom-up so lines stay valid."""
    for lineno in sorted(set(linenos), reverse=True):
        source = with_probe_above_statement(source, lineno)
    return source


def test_loop_aware_drift_files_meet_floor() -> None:
    """NFR-002: the drift parameter set is non-trivial and every file in it is live."""
    assert len(_DRIFT_FILES) >= _DRIFT_FILES_FLOOR
    sources = _scanned_sources()
    allowed, errors = _resolved_allowlist(sources)
    assert errors == []
    _unexpected, suppressed, _unused = _split_findings(sources, allowed)
    suppressed_relpaths = Counter(v.relpath for v in suppressed)
    empty = [relpath for relpath in _DRIFT_FILES if suppressed_relpaths[relpath] < 1]
    assert not empty, f"Drift files with no suppressed finding on the unmutated tree: {empty}"


@pytest.mark.parametrize("relpath", _DRIFT_FILES)
def test_loop_aware_allowlist_survives_line_drift(relpath: str) -> None:
    """NFR-001: line drift above or around the allowlisted sites changes nothing the gate sees.

    Two mutations of ``relpath``, each rescanned: (i) a blank line at the top
    of the file, (ii) a ``# drift-probe`` / ``pass`` pair above every
    allowlisted site's statement. The ``(unexpected, suppressed)`` counts must
    be unchanged and the per-file suppressed count must equal the per-file
    allowlist-entry count.
    """
    sources = _scanned_sources()
    baseline_allowed, baseline_errors = _resolved_allowlist(sources)
    assert baseline_errors == []
    baseline_unexpected, baseline_suppressed, _unused = _split_findings(sources, baseline_allowed)
    expected = _exemption_count_for(relpath)
    site_lines = [v.lineno for v in baseline_suppressed if v.relpath == relpath]

    mutations = {
        "blank line at top": with_blank_line_at_top(sources[relpath]),
        "probe above each site": _probe_every_site(sources[relpath], site_lines),
    }
    for label, mutated_source in mutations.items():
        mutated = dict(sources)
        mutated[relpath] = mutated_source
        allowed, errors = _resolved_allowlist(mutated)
        assert errors == [], f"{relpath} ({label}): an allowlist descriptor stopped resolving: {errors}"
        unexpected, suppressed, _unused = _split_findings(mutated, allowed)
        assert len(unexpected) == len(baseline_unexpected), f"{relpath} ({label}): drift changed the unexpected-finding count"
        drifted_count = sum(1 for v in suppressed if v.relpath == relpath)
        assert drifted_count == expected, f"{relpath} ({label}): {drifted_count} suppressed finding(s), expected {expected}"


# --- T018.4: self-mutation (non-vacuity) ------------------------------------


def test_self_mutation_runtime_error_handler_fires(tmp_path: Path) -> None:
    """A planted ``try: p.resolve() / except RuntimeError`` is caught."""
    module = tmp_path / "offender.py"
    module.write_text(
        "def load(p):\n    try:\n        return p.resolve()\n    except RuntimeError:\n        return None\n",
        encoding="utf-8",
    )

    violations = scan.find_violations(_parse(module), "offender.py")

    assert [v.key for v in violations] == [("offender.py", "load", 1)]


def test_self_mutation_eloop_handler_fires(tmp_path: Path) -> None:
    """A planted ``try: p.resolve() / except OSError`` referencing ``errno.ELOOP`` is caught."""
    module = tmp_path / "offender.py"
    module.write_text(
        "import errno\n\n"
        "def load(p):\n"
        "    try:\n"
        "        return p.resolve()\n"
        "    except OSError as exc:\n"
        "        if exc.errno == errno.ELOOP:\n"
        "            raise\n"
        "        return None\n",
        encoding="utf-8",
    )

    violations = scan.find_violations(_parse(module), "offender.py")

    assert [v.key for v in violations] == [("offender.py", "load", 1)]


def test_o_nofollow_negative_does_not_fire(tmp_path: Path) -> None:
    """Negative (over-fire boundary): the O_NOFOLLOW ``ELOOP`` sense on ``open`` is not path resolution.

    ``try: os.open(path, os.O_NOFOLLOW) / except OSError as e: if e.errno ==
    errno.ELOOP`` never calls ``resolve``/``realpath`` in its try body, so
    it must give zero hits even though it references ``ELOOP`` in a handler
    -- this is the concrete over-fire boundary the WP04 prompt calls out.
    """
    module = tmp_path / "offender.py"
    module.write_text(
        "import errno\n"
        "import os\n\n"
        "def open_no_follow(path):\n"
        "    try:\n"
        "        return os.open(path, os.O_NOFOLLOW)\n"
        "    except OSError as exc:\n"
        "        if exc.errno == errno.ELOOP:\n"
        "            raise\n"
        "        raise\n",
        encoding="utf-8",
    )

    violations = scan.find_violations(_parse(module), "offender.py")

    assert violations == []
    # Sanity: errno.ELOOP really is referenced in this synthetic module, so
    # the zero-violations result above is because of the missing
    # resolve()/realpath() call, not because the ELOOP detection itself is
    # broken.
    assert errno.ELOOP > 0


def test_ordinal_distinguishes_multiple_offenders_in_one_function(tmp_path: Path) -> None:
    """Two offending try-blocks in the same function get distinct ordinals 1 and 2."""
    module = tmp_path / "offender.py"
    module.write_text(
        "def cleanup(a, b):\n"
        "    try:\n"
        "        ra = a.resolve()\n"
        "    except RuntimeError:\n"
        "        ra = None\n"
        "    try:\n"
        "        rb = b.resolve()\n"
        "    except RuntimeError:\n"
        "        rb = None\n"
        "    return ra, rb\n",
        encoding="utf-8",
    )

    violations = scan.find_violations(_parse(module), "offender.py")

    assert [v.key for v in violations] == [
        ("offender.py", "cleanup", 1),
        ("offender.py", "cleanup", 2),
    ]


def test_nested_helper_resolve_call_is_not_attributed_to_outer_try(tmp_path: Path) -> None:
    """A resolve() call inside a nested def is that def's own concern, not the outer try's body."""
    module = tmp_path / "offender.py"
    module.write_text(
        "def outer(p):\n    try:\n        def inner():\n            return p.resolve()\n        return 1\n    except RuntimeError:\n        return 0\n",
        encoding="utf-8",
    )

    violations = scan.find_violations(_parse(module), "offender.py")

    assert violations == []


def test_bare_runtime_error_without_resolve_call_does_not_fire(tmp_path: Path) -> None:
    """Negative: a RuntimeError handler with no resolve()/realpath() call in the try body is not a loop-shape hit."""
    module = tmp_path / "offender.py"
    module.write_text(
        "def compute():\n    try:\n        return 1 / 0\n    except RuntimeError:\n        return None\n",
        encoding="utf-8",
    )

    violations = scan.find_violations(_parse(module), "offender.py")

    assert violations == []
