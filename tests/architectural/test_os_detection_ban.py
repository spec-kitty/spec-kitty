"""OS-detection ban gate (FR-012 / DIRECTIVE_043): repo-wide banned Windows-detection idioms.

Modelled on ``tests/architectural/test_clock_call_ban.py`` (the sibling
``kernel.clock`` dual gate), adapted for a single-idiom-family ban rather
than a call-suggestion engine. See ``tests.architectural._os_detection_scan``
for the full rationale behind this gate's two deliberate divergences from
that template:

1. **Scan corpus = ``src/`` ONLY** (post-tasks squad MF-1), not the clock
   gate's ``src/`` + ``tests/`` + ``scripts/``. ``tests/`` and ``scripts/``
   legitimately use raw platform checks (the Windows/POSIX lock-parity
   harness must simulate ``msvcrt``/``fcntl`` directly; test doubles force a
   platform via ``monkeypatch``). This gate bans re-forking OS-detection in
   *production* code only.
2. **All four idioms banned** (post-tasks squad S-1): ``os.name == "nt"``,
   ``sys.platform == "win32"``, ``platform.system() == "Windows"``, and
   ``sys.platform.startswith("win")``. FR-005 explicitly enumerates
   ``platform.system()``; a gate that misses it leaves the recurrence
   half-closed.

The one sanctioned door is ``src/kernel/paths.py::is_windows`` (the seam
landed by this same WP -- T001). Every other occurrence is either routed
through it or named in a per-owner exemption file under
``tests/architectural/_exemptions/os-detect-ban-*.txt`` (unioned by
``tests.architectural._os_detection_exemptions.load_os_detection_exemptions``).
Each exemption line is a content descriptor
(``<path>::<qualname>::<token_substring>[::<occurrence>]``), resolved and
matched through ``tests.architectural._content_identity`` -- never a
``<path>:<line>`` pin, which the loader refuses.
"""

from __future__ import annotations

import ast
import functools
import re
from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import NamedTuple

import pytest

from tests.architectural import _os_detection_scan as scan
from tests.architectural._content_identity import (
    partition_findings,
    render_descriptor_line,
    resolve_allowlist,
    with_blank_line_at_top,
    with_probe_above_statement,
)
from tests.architectural._os_detection_exemptions import load_os_detection_exemptions
from tests.architectural._ratchet_keys import CompositeKey, ContentDescriptor, composite_key

pytestmark = [pytest.mark.architectural]

Violation = tuple[str, int]


def _violations_for_file(path: Path) -> list[int]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return scan.find_os_detection_violations(tree)


def collect_violations(paths: Iterable[Path]) -> list[Violation]:
    """``(repo-relative path, line)`` for every banned OS-detection idiom across ``paths``."""
    violations: list[Violation] = []
    for path in paths:
        relpath = scan.relpath(path)
        violations.extend((relpath, lineno) for lineno in _violations_for_file(path))
    return sorted(violations)


def test_scanned_file_floor_is_met() -> None:
    """NOTE-3: a detector silently scanning zero files must go red, not green."""
    scanned = scan.iter_python_files()

    assert len(scanned) > scan.MIN_SCANNED_FILES, (
        f"only {len(scanned)} files scanned under {[str(r) for r in scan.SCAN_ROOTS]} -- the OS-detection ban gate would otherwise pass vacuously."
    )


def test_door_file_contains_the_concrete_check() -> None:
    """Concrete floor (FR-012): the canonical seam must actually HOLD the check.

    Non-vacuity: deleting the door's own ``os.name == "nt"`` body (e.g.
    hollowing ``is_windows()`` out to ``return False``) must fail this
    assertion, not silently pass -- a gate whose door can be emptied out
    while the gate stays green is not a floor at all.
    """
    violations = _violations_for_file(scan.DOOR_FILE)

    assert violations, f"{scan.relpath(scan.DOOR_FILE)} no longer contains a recognizable OS-detection check -- the seam's own body has been hollowed out."


def test_no_banned_os_detection_outside_the_door() -> None:
    """FR-012/SC-002: no banned Windows-detection idiom outside kernel/paths.py.

    Findings are matched against the exemption descriptors by content identity
    ``(relpath, qualname, token_line)`` through
    :func:`tests.architectural._content_identity.partition_findings`
    (multiset: one descriptor suppresses at most one finding).

    Non-vacuity (C-009): ``test_stale_exemption_removal_reds_the_gate`` below
    proves this assertion is load-bearing by removing a planted exemption
    entry and observing the same collection-and-filter logic go red on the
    now-unexempted call site.
    """
    unexpected, _suppressed, _unused = _split_os_findings(_scanned_sources(), _resolved_os_allowlist()[0])
    door = scan.relpath(scan.DOOR_FILE)

    assert unexpected == [], (
        'Raw Windows-detection checks (`os.name == "nt"` / '
        '`sys.platform == "win32"` / `platform.system() == "Windows"` / '
        '`sys.platform.startswith("win")`) are banned outside '
        f"{door} (the single door, FR-012). Route through "
        "`from kernel.paths import is_windows` and call `is_windows()`, or, "
        "if this is a currently-tracked, not-yet-remediated site, add the "
        "content line shown (`<path>::<qualname>::<token_substring>`) to the "
        "owning WP's tests/architectural/_exemptions/os-detect-ban-<owner>.txt."
        "\nViolations:\n" + "\n".join(f"  {finding.key[0]}:{finding.lineno}  ->  {_content_line_for(finding)}" for finding in unexpected)
    )


def test_every_exemption_entry_is_a_real_violation() -> None:
    """Anti-staleness (FR-007): every exemption descriptor must suppress a live violation today.

    A descriptor that no longer resolves to exactly one site, or resolves to a
    site holding no banned idiom, is stale -- delete its line.
    """
    exemptions = load_os_detection_exemptions()
    allowed, errors = _resolved_os_allowlist()
    _unexpected, _suppressed, unused = _split_os_findings(_scanned_sources(), allowed)
    checked = len(errors) + sum(allowed.values())

    stale = [f"  {render_descriptor_line(descriptor)} ({descriptor.rationale}): {reason}" for descriptor, reason in errors]
    stale += [f"  {key[0]} [{key[1]}] {key[2]!r} suppresses no live violation" for key in sorted(unused)]
    assert not stale, (
        "The following tests/architectural/_exemptions/os-detect-ban-*.txt "
        "entries no longer correspond to a real violation -- delete them "
        "(the site is already clean):\n" + "\n".join(stale)
    )
    assert checked == len(exemptions) >= _OS_EXEMPTION_FLOOR


def test_stale_exemption_removal_reds_the_gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C-009 non-vacuity: removing a live exemption line makes the gate red, naming the call site.

    Plants a SYNTHETIC ``sys.platform == "win32"`` check in an unexempted
    ``tmp_path`` file, runs it through the REAL detector
    (``collect_violations``), then proves the exemption mechanism is
    load-bearing: a content-form exemption line, parsed by the real loader and
    resolved against the planted source, suppresses the finding; emptying the
    exemption file reds it again. ``scan.REPO_ROOT`` is monkeypatched to
    ``tmp_path`` so the planted file -- which must physically live under
    ``tmp_path``, never the real scanned tree -- still resolves through the
    SAME ``relpath`` function the real gate uses. No write ever touches the
    real repo tree or a committed exemption file.
    """
    module = tmp_path / "offender.py"
    module.write_text('import sys\n\nif sys.platform == "win32":\n    pass\n', encoding="utf-8")
    monkeypatch.setattr(scan, "REPO_ROOT", tmp_path.resolve())

    all_violations = collect_violations([module])
    assert all_violations == [("offender.py", 3)], "the planted violation must be detected by the real detector"
    sources = {"offender.py": module.read_text(encoding="utf-8")}

    isolated_dir = tmp_path / "_exemptions"
    isolated_dir.mkdir()
    (isolated_dir / "os-detect-ban-isolated.txt").write_text("offender.py::<module>::if sys . platform ==\n", encoding="utf-8")

    def _fake_iter_exemption_entries() -> list[tuple[str, str]]:
        entries: list[tuple[str, str]] = []
        for path in sorted(isolated_dir.glob("os-detect-ban-*.txt")):
            entries.extend((path.name, line.strip()) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
        return entries

    import tests.architectural._os_detection_exemptions as exemptions_module

    monkeypatch.setattr(exemptions_module, "_iter_exemption_entries", _fake_iter_exemption_entries)

    def _unexpected_with_current_exemptions() -> list[_OsFinding]:
        allowed, errors = resolve_allowlist(exemptions_module.load_os_detection_exemptions(), lambda rel: (scan.REPO_ROOT / rel).read_text(encoding="utf-8"))
        assert errors == []
        return _split_os_findings(sources, allowed)[0]

    assert _unexpected_with_current_exemptions() == [], "the content-form exemption must suppress the planted finding"

    isolated_dir.joinpath("os-detect-ban-isolated.txt").write_text("", encoding="utf-8")
    without_exemption = _unexpected_with_current_exemptions()

    assert [(finding.key[0], finding.lineno) for finding in without_exemption] == [("offender.py", 3)]


def test_planted_os_name_nt_fires(tmp_path: Path) -> None:
    """C-009 non-vacuity: a planted ``os.name == "nt"`` in an unexempted file IS caught."""
    module = tmp_path / "offender.py"
    module.write_text('import os\n\nif os.name == "nt":\n    pass\n', encoding="utf-8")

    assert _violations_for_file(module) == [3]


def test_planted_sys_platform_win32_fires(tmp_path: Path) -> None:
    """A planted ``sys.platform == "win32"`` is caught."""
    module = tmp_path / "offender.py"
    module.write_text('import sys\n\nif sys.platform == "win32":\n    pass\n', encoding="utf-8")

    assert _violations_for_file(module) == [3]


def test_planted_platform_system_windows_fires(tmp_path: Path) -> None:
    """FR-005: a planted ``platform.system() == "Windows"`` is caught -- the idiom the census flagged."""
    module = tmp_path / "offender.py"
    module.write_text('import platform\n\nkey = "ps" if platform.system() == "Windows" else "sh"\n', encoding="utf-8")

    assert _violations_for_file(module) == [3]


def test_planted_sys_platform_startswith_win_fires(tmp_path: Path) -> None:
    """A planted ``sys.platform.startswith("win")`` is caught."""
    module = tmp_path / "offender.py"
    module.write_text('import sys\n\nif sys.platform.startswith("win"):\n    pass\n', encoding="utf-8")

    assert _violations_for_file(module) == [3]


def test_in_function_check_is_caught(tmp_path: Path) -> None:
    """Full-AST walk (not module-level-only): an in-function check is still caught."""
    module = tmp_path / "offender.py"
    module.write_text(
        'import os\n\ndef helper():\n    return os.name == "nt"\n',
        encoding="utf-8",
    )

    assert _violations_for_file(module) == [4]


def test_door_file_itself_is_exempt_by_construction() -> None:
    """The door is scanned but excluded from the ban assertion by its own relpath, not a text exemption."""
    door_relpath = scan.relpath(scan.DOOR_FILE)
    exemptions = load_os_detection_exemptions()

    # The door earns its exemption by BEING the door (see
    # test_no_banned_os_detection_outside_the_door's `relpath != door` guard),
    # never by an entry in an exemption file -- confirm no such entry exists,
    # so a future edit cannot silently swap the mechanism for a weaker one.
    assert not any(descriptor.rel_path == door_relpath for descriptor in exemptions)


def test_negated_comparison_is_not_banned(tmp_path: Path) -> None:
    """Negative (over-fire boundary): ``sys.platform != "win32"`` is a different, unbanned idiom.

    ``paths/windows_migrate.py`` uses this negated form as a "not Windows"
    guard; it is materially different from (and much rarer than) the four
    banned equality/``startswith`` idioms the mission's census found being
    re-forked, so this gate leaves it alone.
    """
    module = tmp_path / "offender.py"
    module.write_text('import sys\n\nif sys.platform != "win32":\n    pass\n', encoding="utf-8")

    assert _violations_for_file(module) == []


def test_unrelated_string_equality_does_not_fire(tmp_path: Path) -> None:
    """Negative (over-fire boundary): an unrelated ``=="nt"``/``=="win32"`` comparison never fires."""
    module = tmp_path / "offender.py"
    module.write_text(
        'country_code = "nt"\nif country_code == "nt":\n    pass\nlabel = "win32"\nif label == "win32":\n    pass\n',
        encoding="utf-8",
    )

    assert _violations_for_file(module) == []


def test_darwin_and_posix_checks_do_not_fire(tmp_path: Path) -> None:
    """Negative: macOS (``darwin``) and other non-Windows platform checks are untouched."""
    module = tmp_path / "offender.py"
    module.write_text(
        'import sys\n\nif sys.platform == "darwin":\n    pass\nif sys.platform.startswith("linux"):\n    pass\n',
        encoding="utf-8",
    )

    assert _violations_for_file(module) == []


def test_platform_system_call_with_args_does_not_fire(tmp_path: Path) -> None:
    """Negative (over-fire boundary): ``platform.system(alias=True)`` (hypothetical) never matches.

    Non-vacuous: this pins the ``not call.args and not call.keywords`` guard
    in ``_is_platform_system_windows`` -- removing that guard would let this
    assertion fail once ``platform.system`` gained a call argument anywhere.
    """
    module = tmp_path / "offender.py"
    module.write_text('import platform\n\nplatform.system(True) == "Windows"\n', encoding="utf-8")

    assert _violations_for_file(module) == []


# ---------------------------------------------------------------------------
# Line-drift tolerance (NFR-001) and the loader's sanctioned shape
# ---------------------------------------------------------------------------


#: The door's repo-relative path, fixed at import (before any test monkeypatches ``scan.REPO_ROOT``).
_DOOR_RELPATH = scan.relpath(scan.DOOR_FILE)


class _OsFinding(NamedTuple):
    """One banned-idiom finding: its content identity plus its current line."""

    key: CompositeKey
    lineno: int


@functools.cache
def _violation_lines(source: str) -> tuple[int, ...]:
    """Banned-idiom lines in *source*, parsed once per distinct text."""
    return tuple(scan.find_os_detection_violations(ast.parse(source)))


def _scanned_sources() -> dict[str, str]:
    """``{repo-relative path: source}`` for every scanned file."""
    return {scan.relpath(path): path.read_text(encoding="utf-8") for path in scan.iter_python_files()}


def _os_findings(sources: Mapping[str, str]) -> list[_OsFinding]:
    """Every banned-idiom finding outside the door, keyed by ``(relpath, qualname, token_line)``."""
    findings: list[_OsFinding] = []
    for relpath, source in sorted(sources.items()):
        if relpath == _DOOR_RELPATH:
            continue
        for lineno in _violation_lines(source):
            findings.append(_OsFinding((relpath, *composite_key(source, lineno)), lineno))
    return findings


def _source_under_repo(relpath: str) -> str:
    return (scan.REPO_ROOT / relpath).read_text(encoding="utf-8")


@functools.cache
def _resolved_os_allowlist() -> tuple[Counter[CompositeKey], list[tuple[ContentDescriptor, str]]]:
    """The exemption descriptors resolved against the real tree (standing gate + stale test)."""
    return resolve_allowlist(load_os_detection_exemptions(), _source_under_repo)


def _resolve_from(sources: Mapping[str, str]) -> tuple[Counter[CompositeKey], list[tuple[ContentDescriptor, str]]]:
    """Resolve the exemption descriptors against *sources* (possibly mutated), not the disk."""
    return resolve_allowlist(load_os_detection_exemptions(), sources.__getitem__)


def _split_os_findings(sources: Mapping[str, str], allowed: Counter[CompositeKey]) -> tuple[list[_OsFinding], list[_OsFinding], Counter[CompositeKey]]:
    """Split the findings in *sources* into ``(unexpected, suppressed, unused)`` via :func:`partition_findings`."""
    findings = _os_findings(sources)
    unexpected, unused = partition_findings(((finding.key, finding) for finding in findings), allowed)
    reported = set(unexpected)
    return unexpected, [finding for finding in findings if finding not in reported], unused


def _os_detection_partition(sources: Mapping[str, str]) -> tuple[Counter[CompositeKey], Counter[CompositeKey]]:
    """The gate's detection path as content identities (line numbers dropped).

    The descriptors are resolved from the SAME *sources* mapping the scan
    reads, so a drift mutation that stops a descriptor resolving shows up as a
    changed partition rather than being masked by the cached real-tree result.
    """
    unexpected, suppressed, _unused = _split_os_findings(sources, _resolve_from(sources)[0])
    return Counter(f.key for f in unexpected), Counter(f.key for f in suppressed)


def _content_line_for(finding: _OsFinding) -> str:
    """The exemption line that would suppress *finding* (its full normalized token line as the substring)."""
    relpath, qualname, token_line = finding.key
    return render_descriptor_line(ContentDescriptor(relpath, qualname, token_line, None, ""))


#: The distinct files the os-detect exemptions name -- the drift test's parameters.
def _exemptions_for_collection() -> frozenset[ContentDescriptor]:
    """The exemptions, or none if a row is malformed.

    Keeps a malformed row from turning into a module-wide collection error:
    the gate, the stale test and ``test_os_detection_exemption_files_hold_no_line_pin``
    still call the real loader and report the row by file name, and the floor
    test reds on the emptied parameter set.
    """
    try:
        return load_os_detection_exemptions()
    except ValueError:
        return frozenset()


_DRIFT_FILES: tuple[str, ...] = tuple(sorted({descriptor.rel_path for descriptor in _exemptions_for_collection()}))

#: Floor on ``_DRIFT_FILES`` so the drift proof cannot pass over a shrunken set.
_DRIFT_FILES_FLOOR = 3

#: The six content-addressed os-detect sites (SC-001); floor for the stale and no-line-pin tests.
_OS_EXEMPTION_FLOOR = 6


def _exemption_count_for(relpath: str) -> int:
    return sum(1 for descriptor in load_os_detection_exemptions() if descriptor.rel_path == relpath)


def _count_for(keys: Counter[CompositeKey], relpath: str) -> int:
    return sum(count for key, count in keys.items() if key[0] == relpath)


def _probe_every_site(source: str, linenos: list[int]) -> str:
    """Insert a drift probe above each site's statement, bottom-up so lines stay valid."""
    for lineno in sorted(set(linenos), reverse=True):
        source = with_probe_above_statement(source, lineno)
    return source


def test_os_detection_drift_files_meet_floor() -> None:
    """NFR-002: the drift parameter set is non-trivial and every file in it is live."""
    assert len(_DRIFT_FILES) >= _DRIFT_FILES_FLOOR
    _, suppressed = _os_detection_partition(_scanned_sources())
    empty = [relpath for relpath in _DRIFT_FILES if _count_for(suppressed, relpath) < 1]
    assert not empty, f"Drift files with no suppressed finding on the unmutated tree: {empty}"


@pytest.mark.parametrize("relpath", _DRIFT_FILES)
def test_os_detection_exemptions_survive_line_drift(relpath: str) -> None:
    """NFR-001: line drift above or around the exempted sites changes nothing the gate sees.

    Two mutations of *relpath*, each rescanned: (i) a blank line at the top of
    the file, (ii) a ``# drift-probe`` / ``pass`` pair above every exempted
    site's statement. The ``(unexpected, suppressed)`` identities must be
    unchanged and the per-file suppressed count must equal the per-file
    exemption count.
    """
    sources = _scanned_sources()
    baseline = _os_detection_partition(sources)
    expected = _exemption_count_for(relpath)
    assert _count_for(baseline[1], relpath) == expected, f"{relpath}: {_count_for(baseline[1], relpath)} suppressed finding(s) unmutated, expected {expected}"

    site_lines = [f.lineno for f in _split_os_findings(sources, _resolve_from(sources)[0])[1] if f.key[0] == relpath]
    mutations = {
        "blank line at top": with_blank_line_at_top(sources[relpath]),
        "probe above each site": _probe_every_site(sources[relpath], site_lines),
    }
    for label, mutated_source in mutations.items():
        mutated = dict(sources)
        mutated[relpath] = mutated_source
        assert _resolve_from(mutated)[1] == [], f"{relpath} ({label}): an exemption descriptor stopped resolving"
        drifted = _os_detection_partition(mutated)
        assert drifted == baseline, f"{relpath} ({label}): drift changed the gate's partition.\nbefore: {baseline}\nafter:  {drifted}"
        assert _count_for(drifted[1], relpath) == expected


def test_os_detection_loader_rejects_line_pinned_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    """D-OP-6: a ``path:line`` exemption line is refused with a ``ValueError`` naming it."""
    import tests.architectural._os_detection_exemptions as exemptions_module

    monkeypatch.setattr(exemptions_module, "_iter_exemption_entries", lambda: [("os-detect-ban-x.txt", "src/x.py:12")])

    with pytest.raises(ValueError, match=re.escape("src/x.py:12")):
        exemptions_module.load_os_detection_exemptions()


def test_os_detection_exemption_files_hold_no_line_pin() -> None:
    """Guard: the real ``os-detect-ban-*.txt`` files parse as exactly the six content descriptors.

    The loader refuses a ``path:line`` row (see
    ``test_os_detection_loader_rejects_line_pinned_entry``), so a line pin
    creeping back into any committed file reds this test with the file named.
    """
    exemptions = load_os_detection_exemptions()

    assert len(exemptions) == _OS_EXEMPTION_FLOOR, sorted(render_descriptor_line(descriptor) for descriptor in exemptions)
