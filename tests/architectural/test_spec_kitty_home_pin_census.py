"""The frozen census, its baseline, and the ONE assertion that proves the class is frozen (WP05).

Read this before skimming
-------------------------
Plan §10: *"the parallelism in plan §4 is bought by moving the real-tree
``discovered == census u E`` assertion out of WP04 and into this package. It is the right trade,
but it has a cost invisible from the dependency graph: WP05 now looks like a generated data file,
and generated data files get skimmed."* The assertion that carries that load is
:func:`test_t024_the_real_tree_is_set_equal_to_the_census_union_e`, and it is set equality, never
containment.

**AND IT IS WEAKER THAN ITS NAME SUGGESTS. Read this before relying on it.** ``E`` is subtracted
from the census by the generator, and the equality only does work *because* it is:
``discovered == census u E`` is **satisfied by construction** whenever ``E ⊆ census``, since the
union is then a no-op and the statement degenerates to ``discovered == census``. That is not a
hypothesis. It was the shipped state of ``_home_pin_scan.main()`` until ``1759e836e``, and
replaying all 25 tests against the 42-row census it produced gives **10 red, 15 green — with this
test GREEN**, verdict ``unexpected=[] stale=[] census_hash_ok=True exempt_hash_ok=False``: *both*
of T024's accounting limbs hold on a census that had absorbed the canonical owner.

**What actually catches that** is
:func:`test_t022_neither_exempt_entry_is_a_census_row` and
:func:`test_t023_the_census_equals_the_c011_anchor`. A reviewer who finds the famous assertion
first and stops will conclude this package is stronger than it is — which is precisely the hazard
plan §10 names, so the caveat is stated here, at the claim, and not 200 lines below it.

Why this module imports the verdict seam rather than comparing anything itself
------------------------------------------------------------------------------
``_home_pin_verdict.evaluate`` is the **single** home of the census/hash/tombstone comparison.
WP04 extracted it precisely so this package would not become its second copy, and
``test_home_pin_verdict_seam.py`` mechanises that: a module importing ``_home_pin_scan`` that
reads a census artefact, hand-rolls a digest, or relates two of ``census``/``baseline``/
``discovered``/``exempt`` by equality **or containment** is an offender unless it imports the
seam. This module trips all three signals by construction and is **not** on that guard's
``EXEMPT`` list — the import below is what clears it, which is the intended mechanism and not an
accident. Every hash here comes from :func:`_home_pin_verdict.hash_of_key_set` via
:func:`~tests.architectural._home_pin_verdict.evaluate`; there is no ``hashlib`` in this file.

The three anchors, and which of them this Mission wrote
-------------------------------------------------------
1. **C-011's ``members.json``** — authored by the post-spec gate's independent third lens from the
   specification's predicate text alone, never compared against the spec author's classifier
   before publication. It is checked in **verbatim** and is the one artefact that must never be
   edited to make a test pass: its entire evidential value is that the party it checks did not
   write it. It supplies *which* sites are members; the key **encoding** is then applied by the
   repository primitive ``composite_key_from_file``, so the anchor never passes through the
   instrument under test.
2. **M4's ``TABLES.md``** — a second external anchor, authored by a different actor, consumed by
   :func:`test_t026_home_partition_agrees_with_m4_on_the_named_join_key`. It is an anchor, **not
   an oracle**: it cannot say whether M4's labels are right.
3. The census and baseline themselves, which this package **generates and never hand-edits**.

Counting, and why there is none
--------------------------------
C-002 forbids a counted definition of done, and **the literal 40 appears in no assertion in this
file**. Every comparison is against a key **SET**, which is the stronger contract: adding,
removing or renaming a key forces a *content* edit rather than silently passing at an unchanged
count. (The golden-count ceiling gate that used to enforce this repo-wide was retired by #4315 —
the set-equality discipline here is independent of it and stays.)

The two published distributions — the partition split and the M4 intersection — are **measured
content** that FR-003 publishes, reported in failure messages rather than used as thresholds; the
membership claims beside them are set equalities.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path

import pytest
import yaml

from tests.architectural import _home_pin_anchor as anchor_artefact
from tests.architectural import _home_pin_scan as scan
from tests.architectural import _home_pin_synthetic as synthetic
from tests.architectural import _home_pin_verdict as verdict
from tests.architectural._home_pin_exempt import E, OWNER_KEY, RETAINED_PIN_PROBE_KEY

pytestmark = pytest.mark.architectural

#: The real walk root, spelled as every other module in this package spells it.
TESTS_ROOT = Path("tests")

#: The artefacts, named through the seam's own constants rather than re-typed here.
CENSUS_PATH = Path(scan.CENSUS_PATH)
BASELINE_PATH = Path(scan.BASELINE_PATH)

#: The module the documented command must pass to ``--exempt-module``. Running the regeneration
#: **without** it is named in this WP's ``Not Done If``, and WP01's ``main()`` previously ignored
#: it for the census entirely — a defect this package's block cycle found and WP01 fixed at
#: ``1759e836e``. :func:`test_t022_the_shipped_regeneration_command_subtracts_e` is what keeps it
#: fixed: it PARSES the header's own command rather than eyeballing the string.
EXEMPT_MODULE = "tests.architectural._home_pin_exempt"

#: C-011's evidence artefact. **Checked in verbatim; never imported by, merged into, or tidied
#: against ``_home_pin_scan``.** ``discover()`` is compared *against* it, never derived *from* it.
EVIDENCE_MEMBERS = Path(
    "kitty-specs/isolated-home-pin-guard-r1a-01KZNMA3/research/spec_kitty_home_pin_evidence/members.json"
)

#: M4's per-member labels — the second external anchor (FR-003).
M4_TABLES = Path("kitty-specs/isolated-home-pin-guard-r1a-01KZNMA3/research/m4_ablation_evidence/TABLES.md")

#: The census header's key set. Asserted **by equality**, so ``reason`` cannot hide in the header
#: any more than it can hide in a row.
CENSUS_HEADER_KEYS: frozenset[str] = frozenset(
    {"generated_by", "regeneration_command", "frozen_at_sha", "owed_to", "fragility_note"}
)

#: The census row column names. Asserted **by equality**, which is what makes ``reason``,
#: ``frozen_at_sha`` and ``owed_to`` absent from rows BY CONSTRUCTION rather than by inspection.
CENSUS_ROW_COLUMNS: frozenset[str] = frozenset({"key", "lineno", "kind", "home_partition"})

#: The baseline's key set. ``tombstones`` is named here because this file is its **home** — the
#: census header could not carry it without colliding with :data:`CENSUS_HEADER_KEYS`.
BASELINE_KEYS: frozenset[str] = frozenset(
    {"generated_by", "regeneration_command", "census_key_set_sha256", "exempt_set_sha256", "tombstones"}
)

#: FR-003's ``owed_to`` shape — and nothing else. The struck second disjunct permitted
#: ``SK-12-also-pins-home``, which is a reason column in kebab case.
OWED_TO_PATTERN = re.compile(r"^#[0-9]+$")

# FRAGILE_ROW_KEY (the :1165 row,
# ``tests/sync/tracker/test_tracker_egress_refusal_3108.py::
# test_bind_counter_wrapper_changes_no_outcome_committed_red._run_once``) was REMOVED at
# issue-5-delete-sync-transport: its file died with the sync transport, the real-tree
# fragility register measures empty, and t025 now asserts that emptiness directly.

#: The two diagnoses a stale row gets. **Two messages, not one**, because when the known-fragile
#: row goes stale the cheapest green for a confused contributor is a tombstone — recording an
#: adjudication that never happened. The first message closes that path by name.
SITE_PRESENT_MESSAGE = (
    "site still present, silhouette no longer satisfied — this is NOT an adjudication: "
    "the repair is neither a tombstone nor a predicate change, it is an R1b adjudication"
)
SITE_ABSENT_MESSAGE = "site absent — deleted"

#: One M4 per-member row: ``| # | Partition | `File` | `Fixture (qualified)` | …``.
_M4_ROW = re.compile(r"^\|\s*\d+\s*\|\s*(A|B1|B2|other)\s*\|\s*`([^`]+)`\s*\|\s*`([^`]+)`\s*\|")

#: The synthetic mutation that makes a def declare a silhouette parameter it never references —
#: ``canonical_home`` normalises to ``tmp_path`` under FR-010, so it contributes to the silhouette
#: while going unused. This models ``:1165``'s shape without writing a pin literal into this file,
#: which would make this module the 41st member of the class it is guarding.
_SILHOUETTE_SIGNATURE = "(tmp_path, monkeypatch)"
_UNUSED_SILHOUETTE_SIGNATURE = "(tmp_path, monkeypatch, canonical_home)"
_BROKEN_SILHOUETTE_SIGNATURE = "(tmp_path)"


# ---------------------------------------------------------------------------
# Artefact readers. Every comparison below runs through `_home_pin_verdict`.
# ---------------------------------------------------------------------------


def census_text() -> str:
    """The checked-in census, as generated."""
    return CENSUS_PATH.read_text(encoding="utf-8")


def baseline_text() -> str:
    """The checked-in baseline — a **different file** from the census, so the pin is never
    editable in the same hunk as its subject."""
    return BASELINE_PATH.read_text(encoding="utf-8")


def census_header() -> dict[str, str]:
    """The census's header scalars."""
    document = yaml.safe_load(census_text())
    return {str(name): str(value) for name, value in document["header"].items()}


def exempt_keys() -> frozenset[scan.MemberKey]:
    """``E``'s key set — the owner and the single retained-pin probe."""
    return frozenset(entry.key for entry in E)


def discovered_keys() -> frozenset[scan.MemberKey]:
    """The real tree's member keys. Uncached on purpose: a stale walk is a fake green."""
    return frozenset(member.key for member in scan.discover(TESTS_ROOT))


# ---------------------------------------------------------------------------
# The C-011 anchor. `members.json` supplies WHICH sites are members; the repository
# primitive supplies the key ENCODING. The anchor never passes through `_home_pin_scan`.
# ---------------------------------------------------------------------------


def anchor_join_keys() -> dict[scan.MemberKey, tuple[str, str]]:
    """C-011's key set, each key mapped to its ``(rel_path, keyed-def qualname)`` join key.

    Both come from the external artefact: ``sites`` says which write sites are members and
    ``qual`` is the **keyed def**'s qualname. The join key is deliberately **not**
    ``MemberKey[0:2]`` — ``MemberKey[1]`` is the **innermost** enclosing qualname and differs from
    ``qual`` at ``:1165``, which is the one row this Mission has already flagged as fragile.

    Keys land in the **repo-root-relative** space ``members.json`` stores
    (``tests/cli/commands/foo.py``). ``Member.relpath`` is relative to the **walk root**, so
    ``discover(Path("tests"))`` yields ``cli/commands/foo.py`` — see :func:`repo_rooted`, which
    prefixes the *other* side at comparison time. The cheapest wrong repair is to edit
    ``members.json``; it is the one artefact here that must never be touched to green a test.

    **The resolution is frozen, not live.** ``members.json``'s ``sites`` are line numbers, and a
    line number only means anything in the tree it was read from — see
    ``tests/architectural/_home_pin_anchor.py`` for the upstream edit that proved it, and for why
    ``composite_key``'s former "content-addressed, not line-number-addressed" docstring claim
    (narrowed by #3369 to match the reality) holds for insertions below the site and not above
    it. ``members.json`` still decides membership; the
    frozen artefact supplies only the encoding.
    """
    return dict(anchor_artefact.load())


def anchor() -> frozenset[scan.MemberKey]:
    """C-011's evidence set — the Mission's only comparand it did not write."""
    return frozenset(anchor_join_keys())


def repo_rooted(keys: Iterable[scan.MemberKey]) -> frozenset[scan.MemberKey]:
    """Lift walk-root-relative keys into the repo-root-relative space the anchor lives in."""
    return frozenset((f"{TESTS_ROOT.as_posix()}/{key[0]}", key[1], key[2]) for key in keys)


def tombstoned_keys() -> frozenset[scan.MemberKey]:
    """The baseline's tombstoned members, lifted into the anchor's repo-root space.

    R1b (#3121) adjudicates a member away by removing its pin from the tree **and** recording a
    tombstone; the anchor target for the two t023 equalities is then ``anchor - tombstoned``. This
    is what lets the "shrink-only" ratchet actually shrink — without it, converging any member reds
    t023 against the frozen 40-row anchor even with a correct tombstone (the tombstone limb reached
    only t024's hash). Read through the **same** seam the verdict module uses
    (:func:`~tests.architectural._home_pin_verdict.tombstone_keys`), keyed on the frozen 3-tuple
    (relpath, keyed-def qualname, normalized token-line), never a live line number. Empty in the
    R1a state (``tombstones: []``), so ``anchor - {} == anchor`` and the equalities are unchanged
    until a real adjudication lands. The removal is only legitimate once the pin is GONE from the
    tree — proved by :func:`test_t023_a_tombstone_over_a_live_pin_still_reds_the_discovered_class`,
    the t023 mirror of t024's ``:477`` anti-abuse guarantee.
    """
    return repo_rooted(verdict.tombstone_keys(baseline_text()))


# ---------------------------------------------------------------------------
# T022 — generated by ONE documented command, and by nothing else
# ---------------------------------------------------------------------------


def test_t022_both_artefacts_are_reproduced_byte_identically_by_the_documented_command(
    tmp_path: Path,
) -> None:
    """A re-run of the shipped command reproduces both artefacts **byte for byte**.

    This is what makes "neither is hand-edited" a mechanism rather than a promise: a hand-written
    census, a re-typed header, or a row nudged by hand all fail here. The SHA and the creditor are
    read back **out of the census's own header** rather than re-typed, so this test cannot drift
    from the artefact it checks.
    """
    header = census_header()
    census_out = tmp_path / "census.yaml"
    baseline_out = tmp_path / "baseline.yaml"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "tests.architectural._home_pin_scan",
            "--root",
            str(TESTS_ROOT),
            "--frozen-at-sha",
            header["frozen_at_sha"],
            "--owed-to",
            header["owed_to"],
            "--exempt-module",
            EXEMPT_MODULE,
            "--census-out",
            str(census_out),
            "--baseline-out",
            str(baseline_out),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, f"the documented command failed:\n{completed.stderr}"
    assert (census_out.read_bytes(), baseline_out.read_bytes()) == (
        CENSUS_PATH.read_bytes(),
        BASELINE_PATH.read_bytes(),
    ), "the checked-in artefacts are not what the documented command produces — was one hand-edited?"


def test_t022_the_shipped_regeneration_command_subtracts_e() -> None:
    """Both headers name the **same** command, and that command passes ``--exempt-module``.

    Checked by **parsing** the header's own string through the parser ``main()`` uses, never by a
    substring match: an invented flag would sail through ``"--exempt-module" in text`` and send a
    maintainer nowhere. Without this argument nothing subtracts the owner and the retained-pin
    probe, which **are** in ``discover(root=tests)`` — and a census regenerated that way puts the
    canonical owner in a row, at which point ``census u E`` is a no-op union and
    ``discovered == census u E`` degenerates to ``discovered == census``: green while checking
    nothing. That is not hypothetical. It is the state this package was blocked on.
    """
    documented = census_header()["regeneration_command"]
    assert yaml.safe_load(baseline_text())["regeneration_command"] == documented
    assert documented == scan.REGENERATION_COMMAND

    argv = [word.strip("'") for word in documented.split()[3:]]
    parsed = scan.build_parser().parse_args(argv)
    assert parsed.exempt_module == EXEMPT_MODULE


def test_t022_the_census_header_and_row_columns_are_both_set_equalities() -> None:
    """Header key set and row column set, each **by equality**.

    Equality rather than containment is the whole point: it is what makes ``reason``,
    ``frozen_at_sha`` and ``owed_to`` absent from rows **by construction**, and what stops a
    ``reason`` relocating one level up into the header. A `frozen_at_sha` promoted to a row fails
    here.

    Issue-5-delete-sync-transport: every non-exempt member's file was deleted with the transport,
    so the real census holds ZERO rows and the row-column check is stated in universal form (every
    row, if any, carries exactly ``CENSUS_ROW_COLUMNS``). The column set itself stays pinned by
    equality against a rendered row from :func:`scan.render_census`, so a generator that grew or
    shrank the row schema still reds here even with an empty population; byte-identity (t022's
    first test) pins the checked-in artefact against all other drift.
    """
    assert frozenset(census_header()) == CENSUS_HEADER_KEYS
    rows = verdict.census_rows(census_text())
    assert all(frozenset(row) == CENSUS_ROW_COLUMNS for row in rows)
    synthetic_member = scan.Member(
        key=("synthetic/test_member.py", "a_home_fixture", "monkeypatch . setenv ( , str ( home ) )"),
        relpath="synthetic/test_member.py",
        lineno=7,
        kind="fixture",
        home_partition="B1",
        params=frozenset({"home"}),
        resolved_value="str(home)",
    )
    rendered = verdict.census_rows(scan.render_census([synthetic_member], sha="0" * 40, owed_to="#3121", fragility=()))
    assert {frozenset(row) for row in rendered} == {CENSUS_ROW_COLUMNS}


def test_t022_owed_to_is_a_tracker_reference_and_not_prose() -> None:
    """``^#[0-9]+$`` and nothing else. A row whose creditor is prose has no creditor."""
    assert OWED_TO_PATTERN.match(census_header()["owed_to"]) is not None


def test_t022_rows_are_sorted_by_key() -> None:
    """Sorted rows keep a regeneration diff readable, so a real delta cannot hide in a reshuffle."""
    keys = [verdict.as_key(row["key"]) for row in verdict.census_rows(census_text())]
    assert keys == sorted(keys)


def test_t022_neither_exempt_entry_is_a_census_row() -> None:
    """The canonical owner is a **named singleton**, never a row (FR-005/C-007).

    A census row is owed an adjudication and the census is monotonically non-increasing; the owner
    must exist forever, so the two are incompatible. Both ``E`` entries are named individually
    rather than checked as a bag, so a failure says *which*.
    """
    rows = verdict.census_keys(census_text())
    assert rows & frozenset({OWNER_KEY}) == frozenset()
    assert rows & frozenset({RETAINED_PIN_PROBE_KEY}) == frozenset()
    assert rows & exempt_keys() == frozenset()


def test_t022_the_baseline_key_set_names_tombstones_as_its_home() -> None:
    """``tombstones`` lives in the baseline because FR-004(1) is *paths, named, not described*.

    Putting it in the census header would collide with that header's asserted key set — which is
    the mechanical reason the two artefacts are separate files, restated as an assertion.
    """
    assert frozenset(yaml.safe_load(baseline_text())) == BASELINE_KEYS


# ---------------------------------------------------------------------------
# T023 — SC-001 / SC-003: three assertions against the external anchor
# ---------------------------------------------------------------------------


def test_t023_the_discovered_class_minus_e_equals_the_c011_anchor() -> None:
    """``discover(tests) - E == anchor - tombstoned``.

    The anchor was measured at ``5d49d31ed``, **before the owner and the probe existed**, so a
    bare ``discovered == anchor`` is simply FALSE today — and an implementer facing that red would
    relax it to containment, in the package whose own ``Not Done If`` names containment as a
    failure. Subtracting ``E`` is what makes the assertion true and keeps it an equality.

    Subtracting the **tombstoned** set from the anchor is what lets R1b (#3121) shrink the class:
    a member converged onto the canonical owner has its pin removed from the tree (so it leaves
    ``discover``) and a tombstone recorded (so the anchor target drops it too), and the equality
    holds at the smaller size. This is the ratchet's *anti-abuse* limb — the tombstone is only
    honoured once the pin is actually gone, because a live pin keeps the member in ``discover - E``
    while ``anchor - tombstoned`` shrank (see
    :func:`test_t023_a_tombstone_over_a_live_pin_still_reds_the_discovered_class`). Empty tombstones
    (the R1a state) leave this identical to ``== anchor``.
    """
    assert repo_rooted(discovered_keys()) - repo_rooted(exempt_keys()) == anchor() - tombstoned_keys()


def test_t023_the_census_equals_the_c011_anchor() -> None:
    """``census == anchor``, over C-012's path-qualified 3-tuple.

    Under the **bare 2-tuple** the anchor collapses to 19 elements and a classifier finding one
    member per collision class produces the same 19-element set, green. The path qualification is
    what restores this criterion's power, and the key is formed at the **write site**.

    The anchor target is ``anchor - tombstoned`` for the same reason as the discovered-class
    equality above: an R1b-adjudicated member is dropped from the census **and** tombstoned, so
    both sides shrink together. Empty tombstones (R1a) leave this identical to ``== anchor``. Note
    the census side alone cannot be bought off by a tombstone — the discovered-class equality is
    the limb that still sees a live pin.
    """
    assert repo_rooted(verdict.census_keys(census_text())) == anchor() - tombstoned_keys()


# test_t023_a_tombstone_over_a_live_pin_still_reds_the_discovered_class was REMOVED at
# issue-5-delete-sync-transport: it needed one real, still-present non-exempt member to
# tombstone synthetically (`min(discovered_keys() - exempt_keys())`), and the transport
# deletion removed every such member -- the discovered class is now exactly E. The
# polarity it demonstrated (a tombstone without a real removal cannot green t023) is held
# by the discovered-class equality itself for any FUTURE pin (a new key is not in
# `anchor`, so it lands in the equality's left side whatever the manifest says), and by
# test_spec_kitty_home_pin_guard.py's synthetic proofs of the same arithmetic
# (test_transition_5_a_removed_row_with_the_definition_still_present_reds,
# test_e_co_edit_has_no_tombstone_escape).


def non_anchor_tombstones(
    tombstones: frozenset[scan.MemberKey], anchored: frozenset[scan.MemberKey]
) -> frozenset[scan.MemberKey]:
    """Tombstones that are **not** members of the frozen C-011 anchor — the excuse-authority leak."""
    return tombstones - anchored


def test_t023_every_tombstone_is_a_frozen_c011_anchor_member() -> None:
    """A tombstone may only excuse a member of the frozen 40-key C-011 anchor (#3510 landing fold).

    ``anchor - tombstoned`` (the two t023 equalities) and limb (g) of the ``_home_pin_gate`` verdict
    oracle both grant *excuse authority* to the tombstone manifest — a tombstoned key is dropped
    from the anchor target / excused from the end-SHA recompute. But subtraction is a no-op for a
    NON-member, so without this limb a fabricated tombstone key (a real file, a fake
    ``(qualname, token_line)``, ``∉ anchor``) slips every other guard: ``anchor - {real ∪ fake} ==
    anchor - real``, ``main()`` only reds a tombstone over a *live* member, and ``census ∪
    tombstones`` silently grows past the frozen 40. This is the one invariant the excuse needs and
    the rest of the ratchet does not enforce — **every tombstone is one of the frozen 40** — closing
    the buy-off an adversarial review of #3510 demonstrated (``census ∪ tombstones`` = 41 > 40).

    Read from the **manifest** (``load_tombstone_keys`` — the auditable source limb (g) consults
    directly), lifted into the anchor's repo-root space. The second assertion binds the manifest to
    the **baseline** the census reads (``tombstoned_keys``), so the two tombstone consumers cannot
    diverge silently (t022 only catches an un-regenerated baseline, not a manifest edit).
    """
    manifest = repo_rooted(scan.load_tombstone_keys())
    assert non_anchor_tombstones(manifest, anchor()) == frozenset(), (
        "a tombstone names a key outside the frozen C-011 anchor — an excuse must trace to a "
        "frozen-evidence member, never fabricate one"
    )
    assert manifest == tombstoned_keys(), (
        "the tombstone manifest (limb g's source) and the baseline (the census's source) disagree — "
        "regenerate the baseline from the manifest so the two consumers of 'tombstoned' stay in sync"
    )


def test_t023_a_non_anchor_tombstone_is_rejected() -> None:
    """The positive control for the limb above: a fabricated non-anchor tombstone is caught.

    Without this run, ``non_anchor_tombstones == set()`` over the real (forgery-free) manifest is
    indistinguishable from a check that never fires. The fabricated key names a real file with a
    qualname/token that occurs nowhere — exactly the shape the adversarial review used to grow
    ``census ∪ tombstones`` past the frozen 40.
    """
    fake = (
        f"{TESTS_ROOT.as_posix()}/architectural/_home_pin_scan.py",
        "totally_fake_qualname",
        "no . such ( token )",
    )
    assert fake not in anchor()
    assert non_anchor_tombstones(anchor() | {fake}, anchor()) == frozenset({fake})


def test_t023_the_anchor_and_e_are_disjoint() -> None:
    """``anchor ∩ E == set()`` — stated **explicitly**, not relied upon.

    The two assertions above only *imply* this. A reviewer must see disjointness **proved**: if
    they ever intersected, the census would be double-counting an exempt entry and the union in
    ``discovered == census u E`` would stop doing work while every other test stayed green.
    """
    assert anchor() & repo_rooted(exempt_keys()) == frozenset()


def test_t023_the_frozen_anchor_re_encodes_members_json_and_never_re_decides_it() -> None:
    """The frozen artefact may re-encode ``members.json``; it may not re-decide membership.

    Freezing the anchor's resolution (see ``_home_pin_anchor``) turned a live derivation into a
    checked-in file — precisely the shape that can later be regenerated into agreement with a
    census it was supposed to be independent of. This is what makes that impossible without
    editing ``members.json`` itself: every ``(path, lineno, keyed-def qualname)`` the artefact
    carries must be one the evidence records, and every one the evidence records must be present.
    A row added, dropped, or re-pointed fails here, whatever the key encoding says.

    Deliberately compared on the evidence's OWN fields — path, site line, ``qual`` — and not on
    the composite key, because the composite key is the very thing the artefact is allowed to
    supply. Checking it against itself would prove nothing.
    """
    entries = json.loads(EVIDENCE_MEMBERS.read_text(encoding="utf-8"))
    evidence = {
        (str(entry["path"]), int(site), str(entry["qual"]))
        for entry in entries
        for site in entry["sites"]
    }
    doc = yaml.safe_load(Path(anchor_artefact.ANCHOR_PATH).read_text(encoding="utf-8"))
    frozen = {(str(row["join"][0]), int(row["lineno"]), str(row["join"][1])) for row in doc["rows"]}

    assert frozen == evidence, (
        "the frozen anchor no longer mirrors members.json — regenerate it from the evidence with "
        "the header's own regeneration_command; never hand-edit it to match a census"
    )


def test_t023_the_frozen_anchor_records_the_sha_its_line_numbers_index() -> None:
    """A resolution frozen at an unnamed SHA is not reproducible, and not evidence.

    ``members.json``'s ``sites`` are line numbers; the artefact is only checkable by someone who
    can be told which tree to read them in. The header must name it, and it must be a full SHA —
    an abbreviation is ambiguous across the repository's lifetime.
    """
    header = yaml.safe_load(Path(anchor_artefact.ANCHOR_PATH).read_text(encoding="utf-8"))["header"]
    assert re.fullmatch(r"[0-9a-f]{40}", str(header["resolved_at_sha"]))
    assert str(header["source"]) == EVIDENCE_MEMBERS.as_posix()


# ---------------------------------------------------------------------------
# T024 — the real-tree ratchet. THIS is the assertion that proves the class is frozen.
# ---------------------------------------------------------------------------


def guard_report(root: Path, result: verdict.GuardVerdict) -> str:
    """The verdict, with **every stale row diagnosed** — the guard's actual failure message.

    This is where :func:`diagnose_stale_row` earns its place. Shipped without it, the two messages
    existed only inside their own tests: a real stale row produced
    ``unexpected=[] stale=[(…)] census_hash_ok=False`` and **neither message appeared anywhere a
    maintainer would see it**, which made T026(1)'s repair instruction reachable through neither
    the census header nor the diagnostic. Assertion messages are lazy, so the extra parse happens
    only on a red.
    """
    lines = [str(result)]
    for key in sorted(result.stale):
        lines.append(f"  stale row {key}: {diagnose_stale_row(root, key)}")
    return "\n".join(lines)


def test_t024_the_real_tree_is_set_equal_to_the_census_union_e() -> None:
    """``discover(tests) == census u E`` — **SET EQUALITY, never containment.**

    A subset-only ratchet (``discovered <= census | exempt``) passes every WP04 synthetic tree
    except SC-004's and would pass here too; it is the failure ``spec.md`` §0.4 spends a page
    refusing. Both directions are asserted through the seam, whose ``unexpected``/``stale`` fields
    say **which** limb spoke, and then again as a plain equality so the shape is unmistakable.
    """
    result = verdict.evaluate(TESTS_ROOT, census_text(), baseline_text(), E)
    assert (result.unexpected, result.stale) == (frozenset(), frozenset()), guard_report(
        TESTS_ROOT, result
    )
    assert discovered_keys() == verdict.census_keys(census_text()) | exempt_keys()


def test_t024_both_hashes_are_recomputed_from_content_and_match_the_baseline() -> None:
    """Both pins recomputed **from content** — the census key set and the real ``E`` — never from
    file bytes.

    ``sha256(path.read_bytes())`` passes any "a hash exists" review and fails on day thirty: it
    moves under an ``owed_to`` re-point and under a header edit, neither of which touches the key
    set the ratchet compares. The recomputation runs inside
    :func:`~tests.architectural._home_pin_verdict.evaluate`, through the seam's single hasher.
    """
    result = verdict.evaluate(TESTS_ROOT, census_text(), baseline_text(), E)
    assert (result.census_hash_ok, result.exempt_hash_ok) == (True, True), guard_report(
        TESTS_ROOT, result
    )
    assert result.ok, guard_report(TESTS_ROOT, result)


# test_t024_a_real_row_removal_reds_even_with_a_tombstone_covering_the_hash was REMOVED at
# issue-5-delete-sync-transport: its victim was `min(verdict.census_keys(census))`, and the
# real census is empty since every non-exempt member's file was deleted with the transport.
# The two arms it demonstrated live on over synthetic trees in
# tests/architectural/test_spec_kitty_home_pin_guard.py:
# test_hash_placement_a_row_removal_without_a_tombstone_reds (arm 1 -- accounting plus hash),
# test_hash_placement_a_row_removal_with_a_matching_tombstone_passes and
# test_e_co_edit_has_no_tombstone_escape (arm 2 -- the restored hash still does not green the
# run while the definition remains). The real-tree exact-accounting limb itself survives in
# test_t024_the_real_tree_is_set_equal_to_the_census_union_e above.


def test_t024_sc005_mypy_strict_over_the_real_exempt_module() -> None:
    """SC-005's arity limb, discharged on the artefact that **ships**.

    WP04/T018 proves the *mechanism* over a materialised module — that a third entry is a type
    error. This limb type-checks the real ``E``, and it is the only place that happens: **CI will
    not do it**, because mypy there covers ``src/`` only and runs with ``continue-on-error``.
    Invoked as ``[sys.executable, "-m", "mypy"]`` so it is this interpreter's mypy, never whatever
    a ``PATH`` lookup finds.
    """
    completed = subprocess.run(
        [sys.executable, "-m", "mypy", "--strict", "tests/architectural/_home_pin_exempt.py"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout or completed.stderr


# ---------------------------------------------------------------------------
# T025 — the stale-row diagnosis, and the fragility register as a SET
# ---------------------------------------------------------------------------


def effect_limb_sites(root: Path, relpath: str) -> frozenset[int]:
    """The **effect limb alone**: does a site in this file still pin the key to ``tmp_path/"home"``?

    Deliberately silhouette-free. That is the whole diagnostic value — it separates *the member's
    shape changed* from *the member is gone*, which are the two ways a row goes stale and which
    have opposite repairs.
    """
    path = root / relpath
    if not path.exists():
        return frozenset()
    tree = scan.parse_module(path)
    module_bindings = scan.module_level_bindings(tree)
    return frozenset(
        site.lineno
        for site in scan.find_write_sites(tree, key=scan.NEEDLE)
        if scan.resolve_value(site.value, scan.bindings_for_site(tree, site, module_bindings))
        == scan.TMP_PATH_HOME
    )


def diagnose_stale_row(root: Path, key: scan.MemberKey) -> str:
    """One of exactly two messages for a stale census row.

    The polarity is a **spurious red on a behaviour-preserving edit**, which is correct and needs
    no change: dropping an unused parameter preserves behaviour and removes a member, and the
    guard should say so loudly rather than let it pass.
    """
    return SITE_PRESENT_MESSAGE if effect_limb_sites(root, key[0]) else SITE_ABSENT_MESSAGE


def _stale_keys(root: Path, before: frozenset[scan.MemberKey]) -> frozenset[scan.MemberKey]:
    """Keys that were members before an edit and are not members after it."""
    return before - frozenset(member.key for member in scan.discover(root))


def test_t025_a_stale_row_whose_site_survives_is_not_an_adjudication(tmp_path: Path) -> None:
    """Silhouette broken, pin still there → the message that refuses the tombstone.

    Exercised over a materialised tree (WP04's ``_home_pin_synthetic``, imported and never
    edited), by removing ``monkeypatch`` from a member's signature — the behaviour-preserving
    cleanup that ``ruff``'s relaxed ``ARG`` for ``tests/**`` will not defend, and the exact way
    ``:1165`` would go stale.
    """
    root = tmp_path / "silhouette_broken"
    synthetic.census_frozen_tree(root)
    before = frozenset(member.key for member in scan.discover(root))
    target = root / "test_alpha.py"
    target.write_text(
        target.read_text(encoding="utf-8").replace(
            _SILHOUETTE_SIGNATURE, _BROKEN_SILHOUETTE_SIGNATURE
        ),
        encoding="utf-8",
    )
    stale = _stale_keys(root, before)
    assert stale != frozenset(), "the edit was supposed to make a row stale"
    assert {diagnose_stale_row(root, key) for key in stale} == {SITE_PRESENT_MESSAGE}


def test_t025_a_stale_row_whose_site_is_gone_is_a_deletion(tmp_path: Path) -> None:
    """Definition deleted → the other message. Both branches ship exercised; neither is dead code."""
    root = tmp_path / "definition_deleted"
    synthetic.census_frozen_tree(root)
    before = frozenset(member.key for member in scan.discover(root))
    (root / "test_alpha.py").unlink()
    stale = _stale_keys(root, before)
    assert stale != frozenset(), "the deletion was supposed to make a row stale"
    assert {diagnose_stale_row(root, key) for key in stale} == {SITE_ABSENT_MESSAGE}


def test_t025_the_effect_limb_is_not_an_exists_only_matcher(tmp_path: Path) -> None:
    """NEGATIVE CONTROL: the limb reads the resolved **value**, not merely whether the file is there.

    The two branch tests above discriminate *file present* from *file deleted*, and a matcher that
    only checked ``path.exists()`` passes **both** of them — verified by substitution. So the
    discriminating case has to be built: a file that still exists, is still a byte-prefilter hit,
    and still holds a real ``SPEC_KITTY_HOME`` write — whose value simply no longer resolves to
    ``tmp_path/"home"``. The limb must go **silent** on it. An exists-only matcher reds on the last
    assertion here, which is the only place in this module where it would.

    The corpus does not already contain this case: ``_NON_MEMBER_HELPER`` holds no
    ``SPEC_KITTY_HOME`` at all, so it is not even a byte-hit file and could never distinguish the
    two matchers.
    """
    root = tmp_path / "value_no_longer_home"
    synthetic.census_frozen_tree(root)
    relpath = "test_alpha.py"
    target = root / relpath
    assert effect_limb_sites(root, relpath) != frozenset(), "the limb should fire before the edit"

    target.write_text(
        target.read_text(encoding="utf-8").replace('"home"', '"elsewhere"'), encoding="utf-8"
    )

    survived = target.read_text(encoding="utf-8")
    assert scan.NEEDLE in survived, "the file must stay a byte-prefilter hit"
    assert scan.find_write_sites(scan.parse_module(target), key=scan.NEEDLE) != [], (
        "the write site itself must survive — otherwise this control proves nothing"
    )
    assert effect_limb_sites(root, relpath) == frozenset()


def test_t025_the_stale_diagnosis_reaches_the_guard_report(tmp_path: Path) -> None:
    """The diagnosis is wired into the **guard's own failure path**, not just into its own tests.

    End to end: freeze a census and baseline over a materialised tree, break one member's
    silhouette so its row goes stale, run the **real** verdict, and require the message to appear
    in :func:`guard_report`. Without this the diagnosis is a function nobody calls — which is
    exactly the state the first revision shipped in, while a docstring claimed otherwise.
    """
    root = tmp_path / "stale_row_reaches_the_report"
    synthetic.census_frozen_tree(root)
    frozen = frozenset(member.key for member in scan.discover(root))
    members = scan.discover(root)
    census = scan.render_census(members, sha="0" * 40, owed_to="#3121", fragility=())
    baseline = scan.render_baseline(members, exempt=())

    target = root / "test_alpha.py"
    target.write_text(
        target.read_text(encoding="utf-8").replace(
            _SILHOUETTE_SIGNATURE, _BROKEN_SILHOUETTE_SIGNATURE
        ),
        encoding="utf-8",
    )

    result = verdict.evaluate(root, census, baseline, ())
    assert result.stale == _stale_keys(root, frozen), "the edit was supposed to strand a row"
    assert result.stale != frozenset()
    assert SITE_PRESENT_MESSAGE in guard_report(root, result)


def test_t025_the_fragility_register_over_the_real_tree_is_empty_since_issue_5() -> None:
    """The register is a **SET**, asserted equal to the measured real-tree register.

    It used to pin ``{the :1165 key}`` -- ``tests/sync/tracker/
    test_tracker_egress_refusal_3108.py``, whose ``_run_once`` helper held its ``monkeypatch``
    without referencing it. Issue #5 deleted that file with the sync transport, so the real-tree
    register measures EMPTY: no member is held in the class by an unused silhouette parameter
    today. The detector itself stays proven by
    :func:`test_t025_the_fragility_register_can_see_a_second_member` (synthetic second member)
    and by ``test_home_pin_scan_limbs.py``'s fragile-tree bite; if a future edit reintroduces the
    shape, this equality reds until the artefacts are regenerated with the row named.
    """
    assert {row.key for row in scan.fragility_register(TESTS_ROOT)} == set()


def test_t025_the_fragility_register_can_see_a_second_member(tmp_path: Path) -> None:
    """POSITIVE CONTROL: a register that returned one row forever would satisfy the assertion above.

    Two members are given a silhouette parameter their def declares and never references
    (``canonical_home``, which FR-010 normalises to ``tmp_path``), and the register must return
    **both**. Without this, "exactly one fragile row" is indistinguishable from a matcher that can
    only ever see the row it was written against.
    """
    root = tmp_path / "two_fragile"
    synthetic.census_frozen_tree(root)
    mutated = ("test_alpha.py", "pkg/test_gamma.py")
    for relpath in mutated:
        target = root / relpath
        target.write_text(
            target.read_text(encoding="utf-8").replace(
                _SILHOUETTE_SIGNATURE, _UNUSED_SILHOUETTE_SIGNATURE
            ),
            encoding="utf-8",
        )
    register = scan.fragility_register(root)
    assert {row.relpath for row in register} == set(mutated)
    assert {name for row in register for name in row.unused_silhouette_params} == {"canonical_home"}


# ---------------------------------------------------------------------------
# T026 — the census header's load-bearing prose, and M4 recomputed on a named join key
# ---------------------------------------------------------------------------


def m4_labels() -> dict[tuple[str, str], str]:
    """M4's per-member partition labels, keyed ``(file, fixture_qualname)``.

    M4's rows carry **no lineno**, which is what fixes the join key. A second external anchor,
    authored by a different actor — and an anchor, **not an oracle**: nothing here can say whether
    M4's labels are right.
    """
    labels: dict[tuple[str, str], str] = {}
    for line in M4_TABLES.read_text(encoding="utf-8").splitlines():
        matched = _M4_ROW.match(line)
        if matched is not None:
            labels[(matched.group(2), matched.group(3))] = matched.group(1)
    return labels


def disagreeing_keys(
    partitions: Mapping[scan.MemberKey, str],
    labels: Mapping[tuple[str, str], str],
    join: Mapping[scan.MemberKey, tuple[str, str]],
) -> frozenset[scan.MemberKey]:
    """Census keys whose recomputed ``home_partition`` contradicts M4's label for the same member.

    A pure comparator, so the positive controls below can feed it a deliberately mislabelled row
    and prove it reds — an always-agreeing comparator produces exactly the same empty set on the
    real data.
    """
    return frozenset(
        key
        for key, partition in partitions.items()
        if key in join and join[key] in labels and labels[join[key]] != partition
    )


def census_partitions() -> dict[scan.MemberKey, str]:
    """``MemberKey -> home_partition``, read off the census rows."""
    return {
        verdict.as_key(row["key"]): str(row["home_partition"])
        for row in verdict.census_rows(census_text())
    }


def _repo_rooted_partitions() -> dict[scan.MemberKey, str]:
    """Census partitions lifted into the anchor's key space, ready to join."""
    return {
        (f"{TESTS_ROOT.as_posix()}/{key[0]}", key[1], key[2]): partition
        for key, partition in census_partitions().items()
    }


def test_t026_the_join_key_is_injective_over_the_census() -> None:
    """``(rel_path, keyed-def qualname)`` separates every census member from every other.

    Asserted **before** the set comparison it enables, because a join key that collapsed two
    members would silently drop one side of the comparison and the disagreement set would come
    back empty for the wrong reason. Nothing here joins on ``MemberKey[0:2]``: ``MemberKey[1]`` is
    the **innermost** qualname and differs from ``qual`` at ``:1165``.
    """
    join = anchor_join_keys()
    grouped: dict[tuple[str, str], set[scan.MemberKey]] = {}
    for key in _repo_rooted_partitions():
        grouped.setdefault(join[key], set()).add(key)
    assert {join_key for join_key, keys in grouped.items() if len(keys) > 1} == set()


def test_t026_home_partition_agrees_with_m4_on_the_named_join_key() -> None:
    """The M4 agreement is **RECOMPUTED**, never quoted.

    Copying *"28 agreements"* out of the plan into a comment satisfies any prose-shaped criterion.
    Recomputation on a named join key, with an empty disagreement set and the intersection
    published, is the only form that reds when the classifier drifts. Every M4 row is required to
    find a member, so a shrunken join is a red rather than a smaller silent intersection.
    """
    join = anchor_join_keys()
    partitions = _repo_rooted_partitions()
    labels = m4_labels()
    # R1b (#3121): a tombstoned member is adjudicated away — legitimately absent from the census
    # partitions but still in the anchor and in M4. Its M4 label must not read as "matched no member",
    # so exclude the converged-away members' labels from the expected set (they left the live class).
    tombstoned_labels = {join[key] for key in tombstoned_keys() if key in join}
    matched = {key for key in partitions if join[key] in labels}
    unmatched = set(labels) - {join[key] for key in partitions} - tombstoned_labels

    assert unmatched == set(), f"M4 rows matched no census member: {sorted(unmatched)}"
    assert disagreeing_keys(partitions, labels, join) == frozenset(), (
        f"intersection {len(matched)} of {len(labels)} M4 rows; "
        f"disagreements {sorted(disagreeing_keys(partitions, labels, join))}"
    )


def test_t026_the_comparator_sees_a_deliberately_mislabelled_row() -> None:
    """POSITIVE CONTROL, both sides. A comparator that always agreed would pass the test above.

    One member's label is flipped on the census side and, separately, on the M4 side; each time
    the comparator must return **exactly** that key. This is the ``INERT_LIMBS`` discipline — an
    empty-set assertion without a run that returns a non-empty set is its own proof — applied to
    the one criterion in this package whose headline result is an emptiness.

    Issue-5-delete-sync-transport drained the real census to zero rows (every non-exempt
    member's file was deleted with the transport), so there is no real member left to flip a
    label for. :func:`disagreeing_keys` is a pure comparator, so the control runs on one synthetic
    member and demonstrates the same both-sided red it always did.
    """
    victim = scan.MemberKey(
        ("synthetic/test_member.py", "a_home_fixture", "monkeypatch . setenv ( , str ( home ) )")
    )
    join = {victim: ("synthetic/test_member.py", "a_home_fixture")}
    labels = {join[victim]: "A"}
    partitions: dict[scan.MemberKey, str] = {victim: "A"}
    wrong = "B2"

    assert disagreeing_keys({**partitions, victim: wrong}, labels, join) == frozenset({victim})
    assert disagreeing_keys(partitions, {**labels, join[victim]: wrong}, join) == frozenset({victim})


def test_t026_every_census_partition_is_recomputed_per_member() -> None:
    """Each row's ``home_partition`` **recomputed per member** against a live walk.

    **This replaces a distribution assertion, and the reason is worth stating.** The first
    revision asserted ``Counter(partitions.values()) == {"A": 27, "B1": 11, "B2": 2}``. That
    evaded ``test_golden_count_ban`` (retired by #4315) only because its matcher was an ``ast.Compare`` over a literal
    ``len(...)`` — it matched the ban's *shape* and not its *purpose*, and it was defective three
    ways: it is **blind to an A↔B1 swap between two members** (the totals are unchanged, which is
    exactly the drift a per-member check exists to see); it has **zero unique detection power**,
    because T022's byte-identity already pins every row's ``home_partition`` per row with a better
    message; and it **reds on R1b's first legitimate adjudication**, where the cheapest green is a
    numeric hand-edit — a counted definition of done, which C-002 forbids.

    The per-key form covers all **forty** rows, where M4 reaches only the twenty-eight it labelled,
    names the offending row when it reds, and survives R1b unchanged. The published split is
    reported rather than asserted: it is measured content, never a threshold.

    ``other`` keeps its own **empty key set** assertion, which is what FR-007's asserted-inert rule
    asks for — a limb matching nothing must be *known* to match nothing or it reads as enforcement.
    """
    census_label = census_partitions()
    discovered_label = {member.key: member.home_partition for member in scan.discover(TESTS_ROOT)}
    disagreeing = {
        key for key, label in census_label.items() if discovered_label.get(key) != label
    }
    assert disagreeing == set(), (
        f"census rows whose home_partition no longer recomputes: {sorted(disagreeing)}; "
        f"census split {dict(sorted(Counter(census_label.values()).items()))}"
    )
    assert {key for key, label in census_label.items() if label == "other"} == set()


def test_t026_the_census_header_stays_in_step_with_the_fragility_register() -> None:
    """FR-003's rationale goes in the **header**, following ``census/verdict_seam_IC01.yaml``.

    It survives the reviewer test: it entitles the definition to **nothing** and changes no
    check's outcome — which is exactly why the mechanised claim beside it,
    :func:`test_t025_the_fragility_register_over_the_real_tree_is_empty_since_issue_5`, is what
    actually holds the register. The note is **derived by the generator** from
    ``fragility_register(root)``, so it cannot fall out of step with the register: a hand-typed
    constant naming ``:1165`` would keep saying so after the row was gone.

    Issue-5-delete-sync-transport drained the real-tree register to empty (the one fragile row's
    file died with the transport), so the shipped header must carry the generator's EMPTY branch —
    which deliberately makes **no claim** about the population rather than asserting "none" — and
    the named-row branch is proven against synthetic rows over in
    ``test_home_pin_scan_limbs.py::test_the_census_fragility_note_names_the_fragile_rows_via_the_
    generator``.

    **Where the repair instruction lives, and a claim this docstring previously got wrong.**
    T026(1) asks that the census also instruct *"if this row goes stale with the site still
    present, the repair is neither a tombstone nor a predicate change — it is an R1b
    adjudication."* The generated note names the row and its fragility but stops short of the
    instruction, and adding it would mean editing ``_home_pin_scan``'s ``FRAGILITY_NOTE_BASE``,
    which this package does not own. That is recorded rather than worked around, and the
    instruction ships in :data:`SITE_PRESENT_MESSAGE` instead.

    The first revision justified that placement by asserting the diagnostic *"fires at the moment
    of the red"*. **That was false as shipped**: :func:`diagnose_stale_row` had no consumer outside
    its own two tests, so a real stale row printed the raw verdict and the instruction reached a
    maintainer through **neither** route. It is true now only because
    :func:`guard_report` puts it on T024's assertion message, and
    :func:`test_t025_the_stale_diagnosis_reaches_the_guard_report` is what holds that wiring in
    place. Both halves are asserted here so the pair cannot drift apart.
    """
    note = census_header()["fragility_note"]
    assert scan.fragility_register(TESTS_ROOT) == ()
    assert "KNOWN-FRAGILE ROWS: not supplied" in note
    # The empty branch makes no population claim either way.
    assert "none" not in note.lower()
    assert "NOT an adjudication" in SITE_PRESENT_MESSAGE
    assert "R1b adjudication" in SITE_PRESENT_MESSAGE


def test_t026_home_partition_holds_no_key_no_hash_and_no_equality() -> None:
    """OPERATOR RULING, made executable: **if this column blocks the freeze, the column yields.**

    Every row's ``home_partition`` is rewritten to a different value and the guard is re-run: it
    must still be **green**, because the baseline hashes ``MemberKey`` triples and the ratchet
    compares those. That is what "regenerable in a follow-up under FR-004(2)" means, and it is
    asserted here rather than promised, so a future edit that quietly made the column load-bearing
    reds in the package that gates the rest of the Mission.
    """
    rows = verdict.census_rows(census_text())
    relabelled = verdict.with_rows(
        census_text(), [{**row, "home_partition": "other"} for row in rows]
    )
    assert verdict.evaluate(TESTS_ROOT, relabelled, baseline_text(), E).ok


def test_t026_the_evidence_artefacts_are_read_and_never_written() -> None:
    """C-011's anchor and M4's tables are consumed **verbatim**.

    A cheap standing check that the two external anchors still parse into the shapes every
    assertion above depends on. If either ever comes back empty, every emptiness assertion in this
    module would pass for the wrong reason — the population-0 hazard this Mission names fifteen
    times in ``INERT_LIMBS``, applied to the anchors themselves.
    """
    assert anchor() != frozenset()
    assert m4_labels() != {}
    assert frozenset(anchor_join_keys().values()) != frozenset()
