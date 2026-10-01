"""P1 machine proofs — planted negatives that actually fail (WP15).

Contract: ``kitty-specs/ci-pipeline-reinstatement-01M1X35E/contracts/p1-census-oracle.md``
(FR-013 census / C-006 / SC-005 / NFR-006). This module is the non-vacuity teeth for
P1: it proves *by planted negatives that actually fail* that P1 is enforced by
construction (DIR-043), never by a prose promise.

The load-bearing distinction (why this file is FAKEABLE-CRITICAL):

* This WP's base already has the exclusion gate wired (WP02 census, WP05 scrub, WP09
  live shards merged in). A plain "plant a dead shard, assert the exclusion fires" is
  therefore **green on base** — a co-landing tautology, not a red-first proof.
* So the C-011 anchor (:func:`test_denominator_exclusion_depends_on_the_retirement_guard`)
  is an **automated self-mutation**: it programmatically neutralizes the exclusion guard
  *in-process* (via the ``monkeypatch`` fixture, restored at teardown — never a committed
  source edit) and asserts that with the guard gone the planted dead shard is **no longer
  excluded**. A guard-absent path that still excluded the shard would be a tautology; the
  machine-driven red is the genuine anti-laziness proof.

Every helper here reuses the canonical dependency surfaces — the census oracle
(:mod:`tests.architectural._p1_census_oracle`), the retirement gate
(:mod:`tests.architectural.test_no_retired_subsystems`), and the dead-symbol gate
(:mod:`tests.architectural.test_no_dead_symbols`) — so a planted negative is driven
through the *exact* production path, never a re-implemented shadow of it (SO#6).
"""

from __future__ import annotations

import ast
from pathlib import Path
from types import ModuleType

import pytest

from tests.architectural import _p1_census_oracle as census_oracle
from tests.architectural import _symbol_key as symbol_key
from tests.architectural import test_no_dead_modules as dead_modules_gate
from tests.architectural import test_no_dead_symbols as dead_symbols_gate
from tests.architectural import test_no_retired_subsystems as retired_gate
from tests.architectural._dead_symbol_allowlist import DeadSymbolKey

pytestmark = [pytest.mark.architectural, pytest.mark.fast]

_REPO_ROOT = Path(__file__).resolve().parents[2]

# WP16 (a PARALLEL lane, not a WP15 dependency) commits this membership manifest. When
# it is present the E4 cross-reference activates; when absent (as on this lane's base)
# T080 falls back to asserting the enforcement allowlists directly.
_MEMBERSHIP_PATH = _REPO_ROOT / "tests" / "architectural" / "shape_guard_membership.yaml"

# The three always-on enforcement allowlists (C-006 boundary). They quote dead surfaces
# as banned strings and must never be scrubbed, excluded, or demoted off the gate.
_ENFORCEMENT_GATE_NAMES: tuple[str, ...] = (
    "test_no_dead_symbols",
    "test_no_dead_modules",
    "test_no_retired_subsystems",
)

# The retired subsystems whose banned-import prefixes the retirement allowlist must keep.
_RETIRED_SUBSYSTEMS: tuple[str, ...] = (
    "specify_cli.sync",
    "specify_cli.delivery",
    "specify_cli.event_journal",
    "specify_cli.saas",
    "specify_cli.egress",
)

# Planted retired *src* surfaces used as synthetic dead-code shards. Each lives under a
# banned retirement prefix (``specify_cli.sync`` / ``specify_cli.saas``), so the census
# oracle recognizes it as dead via the instant retirement path — no importer scan, and
# no such module exists on disk (they are pure fixtures).
_PLANTED_RETIRED_SURFACES: tuple[str, ...] = (
    "specify_cli.sync.planted_dead_shard",
    "specify_cli.saas.planted_dead_shard",
)

# The evidence string the census records for a retirement-backed dead surface; it must
# match the oracle's own constant so the injected census is valid, independent evidence.
_RETIREMENT_EVIDENCE = "retirement-gate:test_no_retired_subsystems"


def _neutralized_retirement_evidence(surface: str) -> str | None:
    """A guard-removed stand-in for :func:`_p1_census_oracle.retirement_evidence`.

    Returns ``None`` for every surface — i.e. the retirement recognizer no longer
    substantiates *any* surface as dead. Installed in-process by the self-mutation
    harness and restored by the ``monkeypatch`` fixture at teardown.
    """
    return None


def _planted_surface_is_excluded(
    surface: str,
    census: tuple[census_oracle.CensusEntry, ...],
) -> bool:
    """True iff *surface* is in the coverage-denominator exclusion set for *census*.

    A :class:`_p1_census_oracle.CensusError` (the oracle refusing to substantiate the
    surface once the guard is neutralized) counts as "not excluded" — that refusal is
    exactly the guard-absent red the self-mutation harness observes.
    """
    try:
        return surface in census_oracle.denominator_excluded_surfaces(census=census)
    except census_oracle.CensusError:
        return False


@pytest.mark.parametrize("planted_surface", _PLANTED_RETIRED_SURFACES)
def test_denominator_exclusion_depends_on_the_retirement_guard(
    planted_surface: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C-011 anchor (T077): automated self-mutation of the exclusion guard.

    Intact-guard path (green): the planted retired shard is census-``dead`` and is
    therefore excluded from the coverage denominator (SC-005 / NFR-006).

    Guard-absent path (machine-driven red): the harness neutralizes the retirement
    recognizer in-process; the oracle can no longer substantiate the shard as dead, so
    the shard is **no longer excluded** — :func:`_planted_surface_is_excluded` returns
    ``False``. A tautological exclusion (one that ignored the guard) would still return
    ``True`` here, which is precisely the fakeable outcome this test forbids.
    """
    census = (
        census_oracle.CensusEntry(
            surface=planted_surface,
            status="dead",
            evidence=_RETIREMENT_EVIDENCE,
            authorizes="denominator-exclude",
        ),
    )

    # Intact guard — the exclusion holds.
    assert _planted_surface_is_excluded(planted_surface, census) is True

    # Self-mutation: remove the exclusion guard in-process.
    monkeypatch.setattr(census_oracle, "retirement_evidence", _neutralized_retirement_evidence)

    # Guard-absent path REDS: the planted shard is no longer excluded.
    assert _planted_surface_is_excluded(planted_surface, census) is False

    # Restore (the fixture also restores at teardown) — the exclusion returns.
    monkeypatch.undo()
    assert _planted_surface_is_excluded(planted_surface, census) is True


# ---------------------------------------------------------------------------
# T078 — planted retired-import negative (always-on enforcement allowlist)
# ---------------------------------------------------------------------------
def test_planted_retired_import_still_red_by_retirement_allowlist(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T078: a planted retired-import is caught by the always-on retirement allowlist.

    The detection runs against a throwaway tree with **no census present**, proving the
    retirement allowlist catches the regression *independently* of the census/scrub
    exclusion gate (C-006: the enforcement allowlists are out of scope of exclusion).

    Guard-removal proof: neutralizing the banned-prefix allowlist in-process makes the
    planted import no longer caught — the allowlist is load-bearing, not a tautology.
    """
    fixture = tmp_path / "src/specify_cli/planted_importer.py"
    fixture.parent.mkdir(parents=True)
    fixture.write_text("import specify_cli.sync\nfrom specify_cli import delivery\n", encoding="utf-8")

    # Guard intact — the always-on allowlist catches both retired imports.
    targets = {violation.split(": ", 1)[1] for violation in retired_gate._retired_import_violations(tmp_path)}
    assert "specify_cli.sync" in targets
    assert "specify_cli.delivery" in targets

    # Guard-removal: empty the banned-prefix allowlist in-process; the planted import
    # is no longer caught (proving the allowlist, not the exclusion gate, does the work).
    monkeypatch.setattr(retired_gate, "_BANNED_IMPORT_PREFIXES", ())
    assert retired_gate._retired_import_violations(tmp_path) == []


# ---------------------------------------------------------------------------
# T079 — planted dead-symbol negative (always-on enforcement allowlist)
# ---------------------------------------------------------------------------
def test_planted_dead_symbol_still_red_by_dead_symbol_gate() -> None:
    """T079: a planted zero-caller symbol is flagged by the always-on dead-symbol gate.

    Driven through the *exact* production aggregate path (``_compute_offenders``), so the
    proof exercises the real gate, not a shadow. The gate stays always-on: the only
    sanctioned neutralizers are a real caller or an explicit ``(module, name)`` allowlist
    entry for a keyable name — both proven here to flip the flag off, confirming the
    flagging is load-bearing.
    """
    module_dotted = "specify_cli.planted_dead_module"
    symbol_name = "NeverImportedPlanted"
    offender = f"{module_dotted}::{symbol_name}"
    decls = {module_dotted: frozenset({symbol_name})}
    empty_corpus: dict[str, symbol_key.CorpusModule] = {}
    empty_index: dict[str, list[symbol_key.Location]] = {}

    # Guard intact — nothing imports the symbol, so the gate flags it.
    flagged = dead_symbols_gate._compute_offenders(decls, {}, set(), frozenset(), empty_corpus, empty_index)
    assert flagged == [offender]

    # Neutralizer #1 (control): a real direct caller clears the flag.
    with_caller = {module_dotted: {symbol_name}}
    assert dead_symbols_gate._compute_offenders(decls, with_caller, set(), frozenset(), empty_corpus, empty_index) == []

    # Neutralizer #2 (control): an explicit ``(module, name)`` allowlist entry clears the
    # flag. The exemption also requires the name to be keyable (G1), so the corpus holds
    # a real definition; the same entry over the empty corpus exempts nothing.
    allowlist = frozenset({DeadSymbolKey(module_dotted, symbol_name)})
    source = f"{symbol_name} = object()\n"
    module = symbol_key.CorpusModule(tree=ast.parse(source), source=source, containing_pkg="specify_cli")
    corpus = {module_dotted: module}
    collision_index = symbol_key.classify_collisions(corpus)
    assert dead_symbols_gate._compute_offenders(decls, {}, set(), allowlist, corpus, collision_index) == []
    assert dead_symbols_gate._compute_offenders(decls, {}, set(), allowlist, empty_corpus, empty_index) == [offender]


# ---------------------------------------------------------------------------
# T080 — allowlist preservation (E4 cross-reference, WP16-activated)
# ---------------------------------------------------------------------------
def _marker_names(module: ModuleType) -> set[str]:
    """Return the marker names on *module*'s ``pytestmark`` (single Mark or list)."""
    marks = getattr(module, "pytestmark", [])
    if not isinstance(marks, list):
        marks = [marks]
    return {mark.name for mark in marks}


def test_enforcement_allowlists_preserved_on_the_blocking_gates() -> None:
    """T080: the P1/P2 demotion did not weaken the enforcement allowlists.

    The oracle recognizes all three gates as always-on enforcement allowlists (C-006).
    When WP16's committed membership (E4) is present, cross-reference it: every
    enforcement-allowlist member must still be named on the blocking gate. WP16 is a
    PARALLEL lane, so on this base the file is absent — fall back to asserting the
    enforcement allowlists are intact/behaviorally-unchanged DIRECTLY (always checkable).
    The full E4 cross-reference activates automatically once WP16 merges.
    """
    for gate in _ENFORCEMENT_GATE_NAMES:
        assert census_oracle.is_enforcement_allowlist_gate(gate), f"oracle no longer recognizes {gate!r} as an enforcement allowlist gate"

    if _MEMBERSHIP_PATH.exists():
        # E4 cross-reference (WP16 has landed): every enforcement-allowlist gate is still
        # named in the committed membership.
        membership_text = _MEMBERSHIP_PATH.read_text(encoding="utf-8")
        for gate in _ENFORCEMENT_GATE_NAMES:
            assert gate in membership_text, f"{gate!r} is absent from WP16 shape_guard_membership.yaml (allowlist weakened)"
        return

    # Fallback (WP16 not yet merged): the enforcement allowlists are intact directly.
    assert isinstance(dead_symbols_gate._SYMBOL_ALLOWLIST, frozenset)
    assert isinstance(dead_modules_gate._ALLOWLIST, frozenset)

    banned_prefixes = retired_gate._BANNED_IMPORT_PREFIXES
    for subsystem in _RETIRED_SUBSYSTEMS:
        assert any(prefix == subsystem or prefix.startswith(f"{subsystem}.") for prefix in banned_prefixes), f"retirement allowlist dropped {subsystem!r}"
    assert "websockets" in banned_prefixes

    # The gate modules are still collected as blocking architectural tests — the demotion
    # did not quarantine or skip them off the gate.
    for module in (dead_symbols_gate, dead_modules_gate, retired_gate):
        marks = _marker_names(module)
        assert "architectural" in marks, f"{module.__name__} is no longer a blocking architectural gate"
        assert "skip" not in marks and "quarantine" not in marks, f"{module.__name__} was demoted off the blocking gate"


# ---------------------------------------------------------------------------
# T081 — denominator integrity (SC-005 / NFR-006)
# ---------------------------------------------------------------------------
def test_census_dead_behavioral_test_never_enters_coverage_denominator() -> None:
    """T081: a census-``dead`` behavioral surface never inflates the coverage denominator.

    Consumes the WP02 census. Every census-dead surface is excluded from the coverage
    denominator (SC-005 / NFR-006), except the always-on enforcement allowlists, which
    are never excluded (C-006). The exclusion set is non-vacuous by construction — an
    empty census can never silently pass (DIR-043).
    """
    dead = census_oracle.census_dead_surfaces()
    excluded = census_oracle.denominator_excluded_surfaces()

    # Non-vacuity floor (the census is consumed and yields real dead surfaces).
    assert dead
    assert excluded

    for surface in dead:
        if census_oracle.is_enforcement_allowlist_gate(surface):
            assert surface not in excluded, f"enforcement allowlist {surface!r} must never be excluded from the denominator"
        else:
            assert surface in excluded, f"census-dead surface {surface!r} must be excluded from the coverage denominator"

    # DIR-043 teeth: the denominator-exclusion set refuses to be vacuous.
    with pytest.raises(census_oracle.VacuousCensusError):
        census_oracle.denominator_excluded_surfaces(census=())
