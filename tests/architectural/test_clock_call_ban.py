"""Call-ban gate (FR-012(b) / SC-001 / C-008): repo-wide banned wall-clock CALLS.

Uses the NEW whole-module entry point
``tests._support.wall_clock_assertions.find_wall_clock_call_violations``
(paired with ``anchored_module_name``) -- deliberately NOT the existing
assert-scoped ``find_wall_clock_assertion_violations``. Widening that
assert-scoped visitor to flag every banned call anywhere in a module (not
only inside ``assert``) would turn the legitimate freshness-bounds idiom
(``before = datetime.now(UTC)`` / ... / ``assert before <= observed <=
after``) into a false positive and red-flag its own 124-test support suite
(``tests/_support/test_wall_clock_assertions.py``) -- see that module's
"Whole-module call-ban entry point" docstring for the full rationale. This is
the (b) leg of FR-012's dual gate; ``test_clock_import_ban.py`` is the (a)
leg.

THE CRITICAL FIX this gate depends on (per-source-root anchored module-name
resolution) lives in ``wall_clock_assertions.anchored_module_name`` -- see
its docstring. ``test_re_export_bypass_plant_fires_via_the_door`` below is
the committed, always-run proof that the fix is wired: it constructs the
exact ``from kernel.clock import datetime; datetime.now()`` bypass shape and
asserts it IS caught. Manually disabling the ``src/``-first anchor (see that
function's implementation) was verified during this WP's landing to make
this one test go red without touching any other test -- see the WP01b
report for the transcript.

HONEST LIMITS: see ``wall_clock_assertions.py``'s "Whole-module call-ban
entry point" section docstring -- cross-statement receiver binding is
resolved only within a function's (or the module's) own local alias map; a
``getattr(kernel.clock, "datetime").now()`` receiver is a disclosed,
accepted residual (it also carries no ``datetime`` import for the
import-ban to catch either).
"""

from __future__ import annotations

import ast
import re
from collections import Counter
from collections.abc import Iterable
from pathlib import Path

import pytest

from tests._support.wall_clock_assertions import (
    WallClockCallViolation,
    anchored_module_name,
    door_module_name,
    find_wall_clock_call_violations,
)
from tests.architectural import _clock_gate_scan as scan
from tests.architectural._content_identity import partition_findings, render_descriptor_line, resolve_allowlist
from tests.architectural._exemptions import load_call_exemptions
from tests.architectural._ratchet_keys import CompositeKey, ContentDescriptor, composite_key

pytestmark = [pytest.mark.architectural]

CallSite = tuple[str, WallClockCallViolation]


def _violations_for_file(path: Path) -> list[WallClockCallViolation]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    module_name = anchored_module_name(path) or ""
    return find_wall_clock_call_violations(tree, module_name)


def collect_call_ban_violations(paths: Iterable[Path]) -> list[CallSite]:
    """``(repo-relative path, violation)`` for every banned call across ``paths``."""
    violations: list[CallSite] = []
    for path in paths:
        relpath = scan.relpath(path)
        violations.extend((relpath, violation) for violation in _violations_for_file(path))
    return sorted(violations, key=lambda item: (item[0], item[1].line))


def test_scanned_file_floor_is_met() -> None:
    """NOTE-3: a detector silently scanning zero files must go red, not green."""
    scanned = scan.iter_python_files()

    assert len(scanned) > scan.MIN_SCANNED_FILES, (
        f"only {len(scanned)} files scanned under {[str(r) for r in scan.SCAN_ROOTS]} -- the call-ban gate would otherwise pass vacuously."
    )


def _source_under_repo(relpath: str) -> str:
    return (scan.REPO_ROOT / relpath).read_text(encoding="utf-8")


def _keyed_call_sites(call_sites: list[CallSite]) -> list[tuple[CompositeKey, CallSite]]:
    """Key each call site by content identity ``(relpath, qualname, token_line)``, reading each file once."""
    sources: dict[str, str] = {}
    keyed: list[tuple[CompositeKey, CallSite]] = []
    for relpath, violation in call_sites:
        if relpath not in sources:
            sources[relpath] = _source_under_repo(relpath)
        keyed.append(((relpath, *composite_key(sources[relpath], violation.line)), (relpath, violation)))
    return keyed


def _partition_call_sites(
    call_sites: list[CallSite], exemptions: frozenset[ContentDescriptor]
) -> tuple[list[CallSite], Counter[CompositeKey], list[tuple[ContentDescriptor, str]]]:
    """Split *call_sites* into ``(unexpected, unused, resolution errors)`` via ``_content_identity``."""
    allowed, errors = resolve_allowlist(exemptions, _source_under_repo)
    unexpected, unused = partition_findings(_keyed_call_sites(call_sites), allowed)
    return unexpected, unused, errors


def test_no_banned_wall_clock_call_outside_the_door() -> None:
    """FR-012(b)/SC-001: no ``.now``/``.utcnow``/``.today``/``time.time()`` call outside kernel.clock.

    Call sites are matched against the ``CALL:`` descriptors by content
    identity ``(relpath, qualname, token_line)`` through
    ``tests.architectural._content_identity.partition_findings``.

    Non-vacuity (C-009): ``test_stale_exemption_removal_reds_the_gate`` below
    proves this assertion is load-bearing by removing one live exemption
    entry and observing this same collection go red on the now-unexempted
    call site, then restoring it.
    """
    scanned = scan.iter_python_files()
    violations, _unused, _errors = _partition_call_sites(collect_call_ban_violations(scanned), load_call_exemptions())

    assert violations == [], (
        "Raw wall-clock reads (`.now`/`.utcnow`/`.today`/`time.time()`) are "
        "banned outside src/kernel/clock.py (the single door, FR-012(b)). Use "
        "the matching kernel.clock producer instead, or add "
        "CALL:<path>::<qualname>::<token_substring> to your package's "
        "tests/architectural/_exemptions/<owner>.txt if this is a currently-"
        "tracked, not-yet-remediated site.\nViolations:\n"
        + "\n".join(f"  {relpath}:{violation.line}: {violation.call} -- use {violation.suggestion}" for relpath, violation in violations)
    )


def test_every_call_exemption_entry_is_a_real_violation() -> None:
    """Anti-staleness (FR-007): every ``CALL:`` descriptor must suppress an actual violation today."""
    scanned = scan.iter_python_files()
    exemptions = load_call_exemptions()
    _violations, unused, errors = _partition_call_sites(collect_call_ban_violations(scanned), exemptions)

    stale = [f"  CALL:{render_descriptor_line(descriptor)} ({descriptor.rationale}): {reason}" for descriptor, reason in errors]
    stale += [f"  {key[0]} [{key[1]}] {key[2]!r} suppresses no live call" for key in sorted(unused)]
    assert not stale, (
        "The following tests/architectural/_exemptions/*.txt CALL entries no "
        "longer correspond to a real violation -- delete them (the site is "
        "already clean):\n" + "\n".join(stale)
    )


def test_stale_exemption_removal_reds_the_gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C-009 non-vacuity: removing a live exemption line makes the gate red, naming the call site.

    TREE-INDEPENDENT (WP15 terminal remediation): the real tree's exemption
    union is now empty (SC-003) -- WP05-WP14 shrank every ``_exemptions/*.txt``
    to nothing, so there is no live in-tree violation left to harvest via
    ``collect_call_ban_violations(scan.iter_python_files())`` the way the
    pre-terminal version of this test did. Instead plants a SYNTHETIC
    ``datetime.now(datetime.UTC)`` call in an unexempted ``tmp_path`` file,
    runs it through the REAL detector (``collect_call_ban_violations``), then
    proves the exemption mechanism is load-bearing via the exact same
    content-keyed partition ``test_no_banned_wall_clock_call_outside_the_door``
    runs: a ``CALL:offender.py::<module>::datetime . now (`` line, parsed by
    the real loader and resolved against the planted source, suppresses the
    call; emptying the file reds it again. ``scan.REPO_ROOT`` is
    monkeypatched to ``tmp_path`` for the duration of the ``scan.relpath``
    calls and the descriptor resolution, so the planted file -- which must
    physically live under ``tmp_path``, never the real scanned tree -- still
    resolves through the SAME ``relpath`` function the real gate uses. No
    write ever touches the real repo tree or a committed ``_exemptions/*.txt``
    file.
    """
    module = tmp_path / "offender.py"
    module.write_text("import datetime\n\ndatetime.now(datetime.UTC)\n", encoding="utf-8")
    monkeypatch.setattr(scan, "REPO_ROOT", tmp_path.resolve())

    all_violations = collect_call_ban_violations([module])
    assert len(all_violations) == 1, "the planted call-ban violation must be detected by the real detector"
    sample_relpath, sample_violation = all_violations[0]
    assert sample_relpath == "offender.py"
    assert (sample_violation.line, sample_violation.call) == (3, "datetime.now()")

    isolated_dir = tmp_path / "_exemptions"
    isolated_dir.mkdir()
    (isolated_dir / "isolated_owner.txt").write_text("CALL:offender.py::<module>::datetime . now (\n", encoding="utf-8")

    def _fake_iter_exemption_entries() -> list[tuple[str, str]]:
        entries: list[tuple[str, str]] = []
        for path in sorted(isolated_dir.glob("*.txt")):
            entries.extend((path.name, line.strip()) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
        return entries

    import tests.architectural._exemptions as exemptions_module

    monkeypatch.setattr(exemptions_module, "_iter_exemption_entries", _fake_iter_exemption_entries)
    with_exemption, _unused, errors = _partition_call_sites(all_violations, exemptions_module.load_call_exemptions())
    assert errors == []
    assert (sample_relpath, sample_violation) not in with_exemption

    isolated_dir.joinpath("isolated_owner.txt").write_text("", encoding="utf-8")
    without_exemption, _unused, _errors = _partition_call_sites(all_violations, exemptions_module.load_call_exemptions())

    assert (sample_relpath, sample_violation) in without_exemption


def test_door_file_itself_is_exempt() -> None:
    """The one sanctioned holder (`now_utc_iso`'s own `datetime.now(UTC)`) never fires."""
    violations = _violations_for_file(scan.DOOR_FILE)

    assert violations == []


def test_door_is_self_exempt_by_its_own_anchored_module_name() -> None:
    """The engine's self-exemption is keyed on the REAL anchored name, not a guess."""
    tree = ast.parse(scan.DOOR_FILE.read_text(encoding="utf-8"), filename=str(scan.DOOR_FILE))

    assert find_wall_clock_call_violations(tree, door_module_name()) == []


def test_planted_double_attr_call_fires(tmp_path: Path) -> None:
    """C-009 non-vacuity: a planted ``datetime.datetime.now()`` in an unexempted file IS caught."""
    module = tmp_path / "offender.py"
    module.write_text("import datetime\n\ndatetime.datetime.now()\n", encoding="utf-8")

    violations = _violations_for_file(module)

    assert [v.call for v in violations] == ["datetime.datetime.now()"]


def test_re_export_bypass_plant_fires_via_the_door(tmp_path: Path) -> None:
    """SC-001's re-export-bypass proof: ``from kernel.clock import datetime; datetime.now()`` fires.

    This is the committed proof that the plan's "CRITICAL FIX (verified
    real)" -- anchoring the door's own module name at ``src/`` so it resolves
    as ``kernel.clock``, never ``src.kernel.clock`` -- is wired. Without that
    fix this assertion is empty (the import silently falls through as an
    unrecognized module and the bare ``datetime`` name gets shadowed instead
    of aliased); this was verified manually during this WP's landing by
    temporarily removing the ``src/``-first anchor and watching this test go
    red, then restoring it.
    """
    module = tmp_path / "offender.py"
    module.write_text("from kernel.clock import datetime\n\ndatetime.now()\n", encoding="utf-8")

    violations = _violations_for_file(module)

    assert [v.call for v in violations] == ["datetime.now()"]


def test_re_export_bypass_via_module_alias_fires(tmp_path: Path) -> None:
    """The double-attribute re-export form: ``import kernel.clock as kc; kc.datetime.now()``."""
    module = tmp_path / "offender.py"
    module.write_text("import kernel.clock as kc\n\nkc.datetime.now()\n", encoding="utf-8")

    violations = _violations_for_file(module)

    assert [v.call for v in violations] == ["kc.datetime.now()"]


def test_variable_split_form_fires(tmp_path: Path) -> None:
    """The variable-split form (no fluent ``.now()`` chain at the call site) still fires."""
    module = tmp_path / "offender.py"
    module.write_text("import datetime\n\nd = datetime\nd.now()\n", encoding="utf-8")

    violations = _violations_for_file(module)

    assert [v.call for v in violations] == ["d.now()"]


def test_positional_now_call_fires(tmp_path: Path) -> None:
    """Plant-matrix (plan Sec 1.3): the plain positional form ``datetime.now(UTC)`` fires.

    C-009: non-vacuous by construction -- deleting ``("datetime", "now")``
    from ``_BANNED_CALLS`` (or the ``_normalize_alias``/``visit_Call`` check
    that consults it) reds this assertion.
    """
    module = tmp_path / "offender.py"
    module.write_text("from datetime import datetime, UTC\n\ndatetime.now(UTC)\n", encoding="utf-8")

    violations = _violations_for_file(module)

    assert [v.call for v in violations] == ["datetime.now()"]


def test_module_alias_now_call_fires(tmp_path: Path) -> None:
    """Plant-matrix: the module-alias form ``import datetime as dt; dt.now()`` fires.

    C-009: non-vacuous -- removing the ``import datetime as X`` alias-binding
    branch in ``_WholeModuleClockVisitor.visit_Import`` (the
    ``parts[0] in {"datetime", "time"}`` case) reds this assertion, since
    ``dt`` would then resolve to nothing and ``dt.now()`` would not match
    ``_BANNED_CALLS``.
    """
    module = tmp_path / "offender.py"
    module.write_text("import datetime as dt\n\ndt.now()\n", encoding="utf-8")

    violations = _violations_for_file(module)

    assert [v.call for v in violations] == ["dt.now()"]


def test_tz_keyword_form_fires(tmp_path: Path) -> None:
    """``datetime.now(tz=UTC)`` (keyword form) fires exactly like the positional form."""
    module = tmp_path / "offender.py"
    module.write_text("from datetime import datetime, UTC\n\ndatetime.now(tz=UTC)\n", encoding="utf-8")

    violations = _violations_for_file(module)

    assert [v.call for v in violations] == ["datetime.now()"]


def test_utcnow_date_today_and_epoch_time_fire(tmp_path: Path) -> None:
    """The remaining banned spellings: ``utcnow()``, ``date.today()``, ``time.time()``."""
    module = tmp_path / "offender.py"
    module.write_text(
        "import datetime\nimport time\n\ndatetime.datetime.utcnow()\ndatetime.date.today()\ntime.time()\n",
        encoding="utf-8",
    )

    violations = _violations_for_file(module)

    assert [v.call for v in violations] == [
        "datetime.datetime.utcnow()",
        "datetime.date.today()",
        "time.time()",
    ]


def test_allowed_producer_call_does_not_fire(tmp_path: Path) -> None:
    """Negative (C-009 over-fire boundary): the door's own producer is not a banned call."""
    module = tmp_path / "offender.py"
    module.write_text("from kernel.clock import now_utc_iso\n\nnow_utc_iso()\n", encoding="utf-8")

    assert _violations_for_file(module) == []


def test_allowed_timedelta_and_annotation_do_not_fire(tmp_path: Path) -> None:
    """Negative: ``timedelta(...)`` and a ``datetime`` type annotation are never banned calls."""
    module = tmp_path / "offender.py"
    module.write_text(
        "from kernel.clock import datetime, timedelta\n\ndef schedule(when: datetime) -> timedelta:\n    return timedelta(seconds=1)\n",
        encoding="utf-8",
    )

    assert _violations_for_file(module) == []


def test_allowed_parse_iso_does_not_fire(tmp_path: Path) -> None:
    """Negative: a hypothetical parse helper name is not confused with a banned call."""
    module = tmp_path / "offender.py"
    module.write_text(
        "from kernel.clock import datetime\n\ndatetime.fromisoformat('2024-01-01T00:00:00+00:00')\n",
        encoding="utf-8",
    )

    assert _violations_for_file(module) == []


def test_allowed_from_epoch_producer_does_not_fire(tmp_path: Path) -> None:
    """Negative (C-009 over-fire boundary): the door's ``from_epoch`` parse helper is not a banned call.

    Non-vacuous: this would go red under a mutation that widened
    ``_BANNED_CALLS``/``_ALIASABLE_CLOCK_PATHS`` to also flag arbitrary
    door-imported names, or that treated any door re-export as banned
    outright rather than only the clock-callable ones.
    """
    module = tmp_path / "offender.py"
    module.write_text("from kernel.clock import from_epoch\n\nfrom_epoch(0.0)\n", encoding="utf-8")

    assert _violations_for_file(module) == []


def test_duration_clock_calls_do_not_fire(tmp_path: Path) -> None:
    """NFR-006 (the over-fire boundary): ``import time; time.monotonic()``/``perf_counter()`` never ban."""
    module = tmp_path / "offender.py"
    module.write_text("import time\n\ntime.monotonic()\ntime.perf_counter()\n", encoding="utf-8")

    assert _violations_for_file(module) == []


def test_message_mapping_suggests_correct_producer(tmp_path: Path) -> None:
    """SC-001: the violation's ``suggestion`` names the correct producer for >=4 representative spellings.

    Non-vacuity (C-009): flipping ``_isoformat_producer_suggestion``'s /
    ``_strftime_producer_suggestion``'s branch logic (or the
    ``_NOW_FAMILY_CALLS``/``_DATE_TODAY_CALLS``/``_EPOCH_CALL`` membership
    checks in ``wall_clock_assertions._suggested_producer``) to always return
    the generic fallback reds this test -- verified during review by
    temporarily short-circuiting ``_suggested_producer`` to always return
    ``_UNKNOWN_CALL_SUGGESTION`` and observing every assertion below fail.
    """
    module = tmp_path / "offender.py"
    module.write_text(
        "import datetime\nimport time\n\n"
        "datetime.now(datetime.UTC).isoformat()\n"
        "datetime.now(datetime.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')\n"
        "datetime.now(datetime.UTC).strftime('%Y%m%dT%H%M%SZ')\n"
        "time.time()\n"
        "datetime.date.today()\n",
        encoding="utf-8",
    )

    violations = _violations_for_file(module)
    suggestion_by_line = {v.line: v.suggestion for v in violations}

    assert suggestion_by_line[4] == "kernel.clock.now_utc_iso()"
    assert suggestion_by_line[5] == "kernel.clock.now_utc_stamp()"
    assert suggestion_by_line[6] == "kernel.clock.now_utc_compact_stamp()"
    assert suggestion_by_line[7] == "kernel.clock.now_epoch()"
    assert suggestion_by_line[8] == "kernel.clock.now_utc().date() (or an adjudicated naive-local fix per FR-011)"


def test_message_mapping_falls_back_to_generic_now_suggestion(tmp_path: Path) -> None:
    """SC-001 negative: a bare, unchained ``.now()`` gets the generic (not over-specific) producer suggestion.

    C-009: non-vacuous -- if ``_chained_attribute_call`` were mutated to
    always report a (spurious) chain, this would incorrectly assert a
    specific stamp/iso producer instead of the generic fallback, and fail.
    """
    module = tmp_path / "offender.py"
    module.write_text("import datetime\n\ndatetime.now(datetime.UTC)\n", encoding="utf-8")

    violations = _violations_for_file(module)

    assert [v.suggestion for v in violations] == [
        "kernel.clock.now_utc() (or now_utc_iso()/now_utc_stamp()/now_utc_compact_stamp()/now_utc_seconds() for a specific serialization contract)"
    ]


def test_clock_call_loader_rejects_line_pinned_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    """D-OP-6: a ``CALL:path:line`` exemption line is refused with a ``ValueError`` naming it."""
    import tests.architectural._exemptions as exemptions_module

    monkeypatch.setattr(exemptions_module, "_iter_exemption_entries", lambda: [("x.txt", "CALL:src/x.py:12")])

    with pytest.raises(ValueError, match=re.escape("src/x.py:12")):
        exemptions_module.load_call_exemptions()
