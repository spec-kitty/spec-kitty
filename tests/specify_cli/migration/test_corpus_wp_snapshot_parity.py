"""Corpus gate: every committed Mission's WP files and status snapshot agree (#5579, FR-009).

The reduced status snapshot (``materialize_snapshot(dir).work_packages``) omits
every WP that has no *lane* event, while read surfaces that list WPs from
``tasks/WP*.md`` do not. Before the #5579 drain, 51 committed Missions disagreed:
44 were repaired by ``spec-kitty migrate backfill-wp-status`` and 7 are PERMANENT
carve-outs (their WP files were never committed, or were deleted on purpose).
This gate keeps the gap from regrowing, comparing the two WP-id **sets** for every
committed ``kitty-specs/<slug>/`` that has WP files *or* a snapshot WP:

* ``files_only`` (a WP file the snapshot lacks) is **never** exemptable. The fix is
  more seed events (``spec-kitty migrate backfill-wp-status``), never a waiver.
* ``snapshot_only`` (a snapshot WP with no WP file) is reported by the repair CLI but
  cannot be repaired: files are not invented and events are not deleted. Each such
  Mission is a PERMANENT carve-out in :data:`SNAPSHOT_ONLY_EXEMPTIONS`, not drainable
  debt: the WP file was never committed, so nothing can ever shrink the entry. The
  entry names the exact WP ids and why the file is absent, and the stale check keeps
  the list exact: it fails when an entry no longer equals the live ``snapshot_only``
  set, or when its Mission is gone, so no carve-out can silently outlive its gap
  and no new one can be added without a reason.
* A Mission whose status authority is a **live coordination surface** is *skipped*,
  not exempted: its PRIMARY-partition log is not the authority, so a comparison
  against it proves nothing, and the repair CLI refuses it (``COORD_SURFACE_LIVE``)
  for the same reason. It uses the repair CLI's own detector
  (``wp_status_backfill.coordination_surface_is_live``) and is always listed in the
  gate's failure and diagnostic output so it cannot hide. The skip is BOUNDED: every
  skipped Mission must appear in :data:`LIVE_COORDINATION_SKIPS` with a reason (empty
  today -- no committed Mission has a live coordination surface), and a listed Mission
  that is no longer skipped fails as stale. The detector fails closed (an unprovable
  surface reads as live), so without the bound a detector fault would silently turn the
  gate into a pass for exactly the Missions it cannot verify.

Read-only: the snapshot comes from ``materialize_snapshot`` (never ``materialize``,
which rewrites ``status.json``). The corpus is this test file's own checkout, not the
ambient project root (same rationale as ``test_dogfood_corpus_backfilled.py``).

Non-vacuity: a positive census floor, a self-mutation test that injects an unseeded WP
file into a tmp copy of a real Mission, and direct tests of every pure helper.
"""

from __future__ import annotations

import shutil
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path

import pytest
from pydantic import ValidationError

from specify_cli.frontmatter import FrontmatterError
from specify_cli.migration.wp_status_backfill import coordination_surface_is_live
from specify_cli.status import wp_task_files
from specify_cli.status.reducer import materialize_snapshot
from specify_cli.status.store import StoreError
from specify_cli.status.wp_metadata import read_authored_wp_frontmatter

pytestmark = [pytest.mark.integration, pytest.mark.corpus]

#: Non-vacuous floor on scanned Missions (WP files or snapshot WPs). The corpus carried
#: ~530 at the drain; a mis-rooted or emptied scan collapses toward zero, while ordinary
#: archival cannot plausibly drop below this.
_MIN_SCANNED_MISSIONS = 400

_BACKFILL_COMMAND = "spec-kitty migrate backfill-wp-status"
_WHY = "test reason"
_SLUG = "m"
_WP01 = "WP01"
_TASKS = "tasks"
_GITKEEP_ONLY_REASON = "tasks/ holds only a tracked .gitkeep (no WP files were ever committed); tasks.md names the WPs"

#: PERMANENT carve-outs for ``snapshot_only`` WPs: ``{slug: (WP ids, reason)}`` (#5579, FR-009).
#: These 7 Missions' WP files were never committed (or were deleted on purpose), so this is
#: not drainable debt and has no drain date. Each entry must equal the Mission's live
#: ``snapshot_only`` set exactly; adding one needs a reason a reviewer can check.
SNAPSHOT_ONLY_EXEMPTIONS: dict[str, tuple[frozenset[str], str]] = {
    "023-documentation-sprint-agent-management-cleanup": (
        frozenset({"WP07"}),
        "tasks/WP07-jujutsu-reference-cleanup.md was deleted in c2b10ce05d (2026-03-20, 'Remove Jujutsu (jj) VCS implementation entirely', #314)",
    ),
    "035-frontmatter-history-to-canonical-jsonl": (
        frozenset({f"WP{n:02d}" for n in range(1, 7)}),
        f"spec-only dossier (4a6c947691); {_GITKEEP_ONLY_REASON}",
    ),
    "036-kittify-runtime-centralization": (
        frozenset({f"WP{n:02d}" for n in range(1, 9)}),
        "the Mission has no tasks/ dir at all (tasks.md names the WPs); the repair CLI does not count it as snapshot_only because it has no WP files at all",
    ),
    "037-mission-dsl-foundation": (
        frozenset({f"WP{n:02d}" for n in range(1, 10)}),
        f"spec-only dossier (c725036d21); {_GITKEEP_ONLY_REASON}",
    ),
    "journal-project-consent-3030-01KYKWQS": (
        frozenset({"WP03"}),
        "the WP03 file was never committed to main (no git history on the path; tasks/ has WP01, WP02, WP04-WP12)",
    ),
    "single-planning-surface-authority-01KVPR00": (
        frozenset({"WP08", "WP09", "WP10"}),
        "the WP08-WP10 files were never committed to main (tasks/ stops at WP07; tasks.md has no WP08-WP10)",
    ),
    "synthesized-drg-stale-refresh-01KXN8KZ": (
        frozenset({"WP05"}),
        "the WP05 file was never committed to main (tasks/ has WP01-WP04)",
    ),
}


@dataclass(frozen=True)
class MissionParity:
    """WP-file ids versus snapshot ids for one Mission directory."""

    slug: str
    files_only: frozenset[str]
    snapshot_only: frozenset[str]
    #: ``tasks/`` file names with no readable ``work_package_id`` (never guessed).
    malformed: tuple[str, ...] = ()
    #: Set when the event log could not be reduced; the Mission is then unverifiable.
    unreadable: str | None = None
    #: The status authority is a live coordination surface, so the PRIMARY-partition
    #: comparison is meaningless: the Mission is skipped (never exempted) and listed.
    #: Only probed for a Mission that disagrees (see :func:`inspect_mission`).
    coordination_live: bool = False


#: The exact set of Missions the gate may skip because their status authority is a live
#: coordination surface: ``{slug: reason}``. EMPTY today (verified over the whole
#: committed corpus when the gate landed): the corpus is committed on the primary branch
#: and none of its Missions keeps a live coordination branch. A Mission added here needs
#: a reason a reviewer can check and leaves the list when it is consolidated; an
#: unlisted skip fails the gate rather than passing it.
LIVE_COORDINATION_SKIPS: dict[str, str] = {}


def _test_checkout_root() -> Path:
    """Return the checkout containing this gate (not the ambient project root)."""
    return Path(__file__).resolve().parents[3]


def _kitty_specs() -> Path:
    corpus = _test_checkout_root() / "kitty-specs"
    if corpus.is_dir():
        return corpus
    raise AssertionError(f"no kitty-specs corpus in this test checkout: {corpus}")


def collect_wp_file_ids(tasks_dir: Path) -> tuple[frozenset[str], tuple[str, ...]]:
    """Return ``(WP ids from tasks/WP*.md frontmatter, malformed file names)``.

    A missing ``tasks/`` dir yields no ids (the Mission may still carry snapshot WPs). A
    file with unreadable frontmatter or no ``work_package_id`` is reported as malformed,
    never guessed. Uses the canonical authored-frontmatter reader (the same identity source
    as the repair CLI's planner), not a second parser.
    """
    ids: set[str] = set()
    malformed: list[str] = []
    for wp_file in wp_task_files(tasks_dir):
        try:
            meta, _body = read_authored_wp_frontmatter(wp_file)
        except (FrontmatterError, ValidationError, UnicodeDecodeError, OSError):
            malformed.append(wp_file.name)
            continue
        if meta.work_package_id:
            ids.add(meta.work_package_id)
        else:
            malformed.append(wp_file.name)
    return frozenset(ids), tuple(malformed)


def _has_disagreement(parity: MissionParity) -> bool:
    return bool(parity.files_only or parity.snapshot_only or parity.malformed or parity.unreadable)


def inspect_mission(mission_dir: Path) -> MissionParity | None:
    """Compare one Mission's WP files with its reduced snapshot; ``None`` when out of scope.

    Out of scope means no WP files and no snapshot WPs (nothing to disagree about).
    """
    file_ids, malformed = collect_wp_file_ids(mission_dir / _TASKS)
    unreadable: str | None = None
    try:
        snapshot_ids = frozenset(materialize_snapshot(mission_dir).work_packages)
    except StoreError as exc:
        snapshot_ids = frozenset()
        unreadable = f"{type(exc).__name__}: {exc}"
    if not (file_ids or snapshot_ids or malformed or unreadable):
        return None
    parity = MissionParity(
        slug=mission_dir.name,
        files_only=file_ids - snapshot_ids,
        snapshot_only=snapshot_ids - file_ids,
        malformed=malformed,
        unreadable=unreadable,
    )
    # The probe can cost a remote lookup per Mission, so it only runs for a Mission
    # the comparison would otherwise fail; an agreeing Mission has nothing to skip.
    if _has_disagreement(parity) and coordination_surface_is_live(mission_dir):
        return replace(parity, coordination_live=True)
    return parity


def scan_corpus(corpus: Path) -> dict[str, MissionParity]:
    """Inspect every Mission directory under ``corpus``; returns only in-scope Missions."""
    scanned: dict[str, MissionParity] = {}
    for mission_dir in sorted(corpus.iterdir()):
        if not mission_dir.is_dir():
            continue
        parity = inspect_mission(mission_dir)
        if parity is not None:
            scanned[parity.slug] = parity
    return scanned


def _fmt(ids: frozenset[str]) -> str:
    return ", ".join(sorted(ids))


def _parity_violation(parity: MissionParity, exempt_ids: frozenset[str]) -> list[str]:
    """Violations for one Mission; ``exempt_ids`` only ever waives ``snapshot_only`` WPs."""
    found: list[str] = []
    if parity.unreadable:
        found.append(f"{parity.slug}: event log unreadable ({parity.unreadable})")
    if parity.malformed:
        found.append(f"{parity.slug}: WP files without a readable work_package_id: {', '.join(parity.malformed)}")
    if parity.files_only:
        found.append(f"{parity.slug}: WP files the snapshot lacks (files_only, never exemptable): {_fmt(parity.files_only)} -> run `{_BACKFILL_COMMAND}`")
    unexempted = parity.snapshot_only - exempt_ids
    if unexempted:
        found.append(f"{parity.slug}: snapshot WPs with no WP file (snapshot_only, not exempted): {_fmt(unexempted)}")
    return found


def parity_violations(
    scanned: Mapping[str, MissionParity],
    exemptions: Mapping[str, tuple[frozenset[str], str]],
) -> list[str]:
    """Every disagreement between WP files and snapshot not waived by an exemption."""
    violations: list[str] = []
    for slug, parity in scanned.items():
        if parity.coordination_live:
            continue  # skipped, never exempted; listed by skipped_live_coordination
        exempt_ids = exemptions[slug][0] if slug in exemptions else frozenset()
        violations.extend(_parity_violation(parity, exempt_ids))
    return violations


def skipped_live_coordination(scanned: Mapping[str, MissionParity]) -> list[str]:
    """Slugs the gate could not verify because their status authority is a live coordination surface."""
    return sorted(slug for slug, parity in scanned.items() if parity.coordination_live)


def skipped_note(scanned: Mapping[str, MissionParity]) -> str:
    """Diagnostic naming every skipped Mission (empty string when none), appended to gate output."""
    skipped = skipped_live_coordination(scanned)
    if not skipped:
        return ""
    return (
        f"\n  Skipped {len(skipped)} Mission(s) with a live coordination surface (their PRIMARY-partition log is not "
        f"the authority; consolidate them, then rerun the repair or this gate; they are NOT exempted): {', '.join(skipped)}"
    )


def live_skip_violations(scanned: Mapping[str, MissionParity], allowed: Mapping[str, str]) -> list[str]:
    """A live-coordination skip must be in the exact, reasoned *allowed* set; the set must not go stale."""
    skipped = set(skipped_live_coordination(scanned))
    violations = [
        f"{slug}: skipped as a live coordination surface but not in LIVE_COORDINATION_SKIPS "
        "(the detector fails closed, so an unprovable surface also lands here): verify it, then list it with a reason"
        for slug in sorted(skipped - allowed.keys())
    ]
    violations.extend(f"stale live-coordination skip: {slug} is no longer skipped; remove the entry" for slug in sorted(allowed.keys() - skipped))
    violations.extend(f"malformed live-coordination skip for {slug}: needs a reason" for slug, reason in sorted(allowed.items()) if not reason.strip())
    return violations


def stale_exemption_violations(
    corpus: Path,
    scanned: Mapping[str, MissionParity],
    exemptions: Mapping[str, tuple[frozenset[str], str]],
) -> list[str]:
    """Exemptions must match the live ``snapshot_only`` set exactly and name a real Mission."""
    violations: list[str] = []
    for slug, (exempt_ids, reason) in sorted(exemptions.items()):
        if not (corpus / slug).is_dir():
            violations.append(f"stale exemption: Mission {slug} does not exist; remove the entry")
            continue
        if not exempt_ids or not reason.strip():
            violations.append(f"malformed exemption for {slug}: needs WP ids and a reason")
        live = scanned[slug].snapshot_only if slug in scanned else frozenset()
        if live != exempt_ids:
            violations.append(
                f"stale exemption for {slug}: exempts [{_fmt(exempt_ids)}] but live snapshot_only is [{_fmt(live)}]; "
                "shrink the entry to the live set (or remove it)"
            )
    return violations


@pytest.fixture(scope="module")
def corpus_scan() -> dict[str, MissionParity]:
    """One scan of the committed corpus, shared by the gate and the census."""
    return scan_corpus(_kitty_specs())


def test_corpus_wp_files_and_snapshot_agree(corpus_scan: dict[str, MissionParity]) -> None:
    """THE GATE: no Mission's WP-file id set differs from its snapshot id set, bar the permanent carve-outs."""
    violations = parity_violations(corpus_scan, SNAPSHOT_ONLY_EXEMPTIONS) + live_skip_violations(corpus_scan, LIVE_COORDINATION_SKIPS)
    note = skipped_note(corpus_scan)
    if note:
        print(note.strip())  # diagnostic on a passing run too (shown with -rP / on failure)
    assert not violations, "WP files and status snapshot disagree (#5579):\n  " + "\n  ".join(violations) + note


def test_snapshot_only_exemptions_are_exact_and_not_stale(corpus_scan: dict[str, MissionParity]) -> None:
    """Exact carve-outs: each equals the live snapshot_only set; no dead entries."""
    violations = stale_exemption_violations(_kitty_specs(), corpus_scan, SNAPSHOT_ONLY_EXEMPTIONS)
    assert not violations, "\n  ".join(violations)


def test_corpus_census_is_non_vacuous(corpus_scan: dict[str, MissionParity]) -> None:
    """The scan covers a substantial corpus, including the snapshot-only Missions with no WP files."""
    assert len(corpus_scan) >= _MIN_SCANNED_MISSIONS, (
        f"only {len(corpus_scan)} Missions scanned (expected >= {_MIN_SCANNED_MISSIONS}); the gate is mis-rooted or the corpus was emptied"
    )
    no_wp_files = {slug for slug in SNAPSHOT_ONLY_EXEMPTIONS if not wp_task_files(_kitty_specs() / slug / _TASKS)}
    assert no_wp_files, "control: at least one exempted Mission has no WP files (035/036/037)"
    assert no_wp_files <= corpus_scan.keys(), f"snapshot-only Missions without WP files were skipped: {sorted(no_wp_files - corpus_scan.keys())}"


def _agreeing_mission_with_wp_files(scanned: Mapping[str, MissionParity], corpus: Path) -> Path:
    """First scanned Mission whose files and snapshot agree and that has WP files."""
    for slug, parity in scanned.items():
        has_files = bool(wp_task_files(corpus / slug / _TASKS))
        if has_files and not (parity.files_only or parity.snapshot_only or parity.malformed or parity.unreadable):
            return corpus / slug
    raise AssertionError("no agreeing Mission with WP files to mutate; the corpus census is broken")


def test_self_mutation_unseeded_wp_file_is_reported_files_only(corpus_scan: dict[str, MissionParity], tmp_path: Path) -> None:
    """Injecting a WP file with no lane event into a tmp copy must be reported and fail the gate."""
    source = _agreeing_mission_with_wp_files(corpus_scan, _kitty_specs())
    corpus = tmp_path / "kitty-specs"
    victim = corpus / source.name
    shutil.copytree(source, victim)
    assert not parity_violations(scan_corpus(corpus), {}), "control: the unmutated copy must agree"

    template = wp_task_files(victim / _TASKS)[0]
    wp_id = "WP98"
    (victim / _TASKS / f"{wp_id}-injected.md").write_text(_retarget_work_package_id(template.read_text(encoding="utf-8"), wp_id), encoding="utf-8")

    mutated = scan_corpus(corpus)
    assert mutated[victim.name].files_only == frozenset({wp_id})
    # Even an exemption naming the injected id cannot waive a files_only gap.
    sneaky = {victim.name: (frozenset({wp_id}), "attempt to waive a files_only gap")}
    assert any("files_only, never exemptable" in line for line in parity_violations(mutated, sneaky))


def test_self_mutation_deleted_wp_file_is_reported_snapshot_only(corpus_scan: dict[str, MissionParity], tmp_path: Path) -> None:
    """Removing a seeded WP file in a tmp copy surfaces as snapshot_only and fails without an exemption."""
    source = _agreeing_mission_with_wp_files(corpus_scan, _kitty_specs())
    corpus = tmp_path / "kitty-specs"
    victim = corpus / source.name
    shutil.copytree(source, victim)
    before = collect_wp_file_ids(victim / _TASKS)[0]
    wp_task_files(victim / _TASKS)[0].unlink()
    doomed_id = before - collect_wp_file_ids(victim / _TASKS)[0]
    assert len(doomed_id) == 1

    mutated = scan_corpus(corpus)
    assert mutated[victim.name].snapshot_only == doomed_id
    assert parity_violations(mutated, {})
    assert not parity_violations(mutated, {victim.name: (doomed_id, "deliberate gap")})


def _retarget_work_package_id(frontmatter_text: str, new_id: str) -> str:
    lines = frontmatter_text.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("work_package_id:"):
            lines[index] = f"work_package_id: {new_id}"
            break
    else:
        raise AssertionError("template WP file has no work_package_id line to retarget")
    return "\n".join(lines) + "\n"


def _parity(
    slug: str = _SLUG,
    *,
    files_only: frozenset[str] = frozenset(),
    snapshot_only: frozenset[str] = frozenset(),
    malformed: tuple[str, ...] = (),
    unreadable: str | None = None,
    coordination_live: bool = False,
) -> MissionParity:
    return MissionParity(
        slug=slug,
        files_only=files_only,
        snapshot_only=snapshot_only,
        malformed=malformed,
        unreadable=unreadable,
        coordination_live=coordination_live,
    )


def test_parity_violations_helper_branches() -> None:
    """Direct coverage of each violation class and of the exemption's narrow reach."""
    ids = frozenset({_WP01})
    assert parity_violations({}, {}) == []
    assert parity_violations({_SLUG: _parity()}, {}) == []
    assert "files_only" in parity_violations({_SLUG: _parity(files_only=ids)}, {})[0]
    assert "not exempted" in parity_violations({_SLUG: _parity(snapshot_only=ids)}, {})[0]
    assert parity_violations({_SLUG: _parity(snapshot_only=ids)}, {_SLUG: (ids, _WHY)}) == []
    # An exemption covering only part of the gap leaves the rest reported.
    partial = parity_violations({_SLUG: _parity(snapshot_only=frozenset({_WP01, "WP02"}))}, {_SLUG: (ids, _WHY)})
    assert partial and "WP02" in partial[0] and _WP01 not in partial[0]
    assert "without a readable work_package_id" in parity_violations({_SLUG: _parity(malformed=("WP01-x.md",))}, {})[0]
    assert "unreadable" in parity_violations({_SLUG: _parity(unreadable="StoreError: boom")}, {})[0]


def test_stale_exemption_helper_branches(tmp_path: Path) -> None:
    """A stale exemption is reported for: absent Mission, agreeing Mission, wider set, empty reason."""
    (tmp_path / "live").mkdir()
    (tmp_path / "agrees").mkdir()
    ids = frozenset({_WP01})
    scanned = {"live": _parity("live", snapshot_only=ids)}

    assert stale_exemption_violations(tmp_path, scanned, {"live": (ids, _WHY)}) == []
    assert "does not exist" in stale_exemption_violations(tmp_path, scanned, {"gone": (ids, _WHY)})[0]
    assert "stale exemption for agrees" in stale_exemption_violations(tmp_path, scanned, {"agrees": (ids, _WHY)})[0]
    wider = frozenset({_WP01, "WP02"})
    assert "stale exemption for live" in stale_exemption_violations(tmp_path, scanned, {"live": (wider, _WHY)})[0]
    assert "malformed exemption" in stale_exemption_violations(tmp_path, scanned, {"live": (ids, "  ")})[0]


def test_inspect_mission_out_of_scope_and_unreadable(tmp_path: Path) -> None:
    """A Mission with no WP files and no snapshot is skipped; a corrupt log is surfaced, not skipped."""
    empty = tmp_path / "empty-mission"
    empty.mkdir()
    assert inspect_mission(empty) is None
    assert scan_corpus(tmp_path) == {}

    broken = tmp_path / "broken-mission"
    broken.mkdir()
    (broken / "status.events.jsonl").write_text("{not json\n", encoding="utf-8")
    parity = inspect_mission(broken)
    assert parity is not None and parity.unreadable is not None


def test_collect_wp_file_ids_reports_malformed_files(tmp_path: Path) -> None:
    """Valid frontmatter yields its id; unparseable or id-less files are reported, never guessed."""
    tasks = tmp_path / _TASKS
    tasks.mkdir()
    (tasks / "WP01-ok.md").write_text("---\nwork_package_id: WP01\ntitle: ok\n---\n\nbody\n", encoding="utf-8")
    (tasks / "WP02-no-id.md").write_text("---\ntitle: no id\n---\n\nbody\n", encoding="utf-8")
    (tasks / "WP03-no-frontmatter.md").write_text("just prose\n", encoding="utf-8")

    ids, malformed = collect_wp_file_ids(tasks)

    assert ids == frozenset({_WP01})
    assert set(malformed) == {"WP02-no-id.md", "WP03-no-frontmatter.md"}
    assert collect_wp_file_ids(tmp_path / "absent") == (frozenset(), ())


def test_live_coordination_missions_are_skipped_listed_and_never_exempted() -> None:
    """A live-coordination Mission is not judged against its PRIMARY-partition log, but is always named."""
    ids = frozenset({_WP01})
    live = _parity("live", files_only=ids, snapshot_only=frozenset({"WP09"}), malformed=("WP02-x.md",), unreadable="boom", coordination_live=True)
    plain = _parity("plain", files_only=ids)
    scanned = {"live": live, "plain": plain}

    violations = parity_violations(scanned, {})

    assert violations and all(line.startswith("plain:") for line in violations), "the live Mission is skipped; the plain one still fails"
    assert skipped_live_coordination(scanned) == ["live"]
    note = skipped_note(scanned)
    assert "live" in note and "NOT exempted" in note and "1 Mission(s)" in note
    assert skipped_note({"plain": plain}) == ""
    # A skip is not an exemption: nothing about it can waive the plain Mission's files_only gap.
    assert parity_violations({"plain": plain}, {"plain": (ids, _WHY)})


def test_inspect_mission_marks_a_live_coordination_mission(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``inspect_mission`` takes the verdict from the repair CLI's detector, so the two cannot drift."""
    mission = tmp_path / "live-mission"
    (mission / _TASKS).mkdir(parents=True)
    (mission / _TASKS / "WP01-a.md").write_text("---\nwork_package_id: WP01\ntitle: a\n---\n", encoding="utf-8")

    probed: list[Path] = []

    def _live(directory: Path) -> bool:
        probed.append(directory)
        return True

    monkeypatch.setattr(f"{__name__}.coordination_surface_is_live", _live)

    # An agreeing Mission is never probed (the probe can cost a remote lookup).
    (mission / "status.events.jsonl").write_text(
        '{"event_id":"01AAAAAAAAAAAAAAAAAAAAAAB1","mission_slug":"live-mission","wp_id":"WP01","from_lane":"genesis",'
        '"to_lane":"planned","at":"2026-01-02T03:04:05+00:00","actor":"t","force":false,"execution_mode":"worktree"}\n',
        encoding="utf-8",
    )
    agreeing = inspect_mission(mission)
    assert agreeing is not None and agreeing.coordination_live is False and probed == []

    (mission / "status.events.jsonl").unlink()  # now WP01 is files_only
    live = inspect_mission(mission)
    assert live is not None and live.coordination_live is True and probed == [mission]
    assert parity_violations({live.slug: live}, {}) == []


def test_wp_file_filter_is_case_sensitive_and_prefix_exact(tmp_path: Path) -> None:
    """``wp01.md`` / ``XWP01.md`` / ``WP01.txt`` are not WP files; a missing dir has none."""
    tasks = tmp_path / _TASKS
    tasks.mkdir()
    for name in ("WP01-a.md", "WP02.md", "wp03.md", "Wp04.md", "XWP05.md", "WP06.txt", "README.md"):
        (tasks / name).write_text("---\nwork_package_id: WP01\n---\n", encoding="utf-8")

    assert [p.name for p in wp_task_files(tasks)] == ["WP01-a.md", "WP02.md"]
    assert wp_task_files(tmp_path / "absent") == []


def test_live_coordination_skips_are_bounded_by_an_exact_reasoned_allowlist() -> None:
    """An unlisted skip fails (a fail-closed detector fault cannot become a pass); a stale or reasonless entry fails (#5579 L5)."""
    ids = frozenset({_WP01})
    live = MissionParity(slug="live", files_only=ids, snapshot_only=frozenset(), coordination_live=True)
    plain = MissionParity(slug="plain", files_only=ids, snapshot_only=frozenset())

    assert live_skip_violations({"plain": plain}, {}) == []
    assert live_skip_violations({"live": live}, {"live": _WHY}) == []
    unlisted = live_skip_violations({"live": live}, {})
    assert len(unlisted) == 1 and unlisted[0].startswith("live:") and "LIVE_COORDINATION_SKIPS" in unlisted[0]
    stale = live_skip_violations({"plain": plain}, {"plain": _WHY})
    assert len(stale) == 1 and stale[0].startswith("stale live-coordination skip: plain")
    reasonless = live_skip_violations({"live": live}, {"live": "  "})
    assert len(reasonless) == 1 and "needs a reason" in reasonless[0]
