---
work_package_id: WP15
reviewer: claude (reviewer-renata)
reviewed_tip: 4ce85c71c
verdict: changes_requested
---

# WP15 review, cycle 2

F1, F2 and F3 are fixed in the code. One finding is left, about the record of F3 and not about its behaviour.

Evidence on `4ce85c71c`:
- `clean check` is BUILD SUCCESSFUL with the bundle (digest `fadf8a86...0effd`).
- Native compile, nativeTest (3) and nativeSmoke pass; the smoke digest is `15b1eb6ae389c4752ff3577e32e226730f31f610b61fdee4a9d169073bf2e979`, unchanged.
- pytest `tests/ci/test_mission_status_*.py`, `tests/contract/test_mission_status_conformance.py` and three architectural files: 428 passed.
- `ruff check` and `ruff format --check` are clean.
- JaCoCo recount: domain=130, application=126 (equal to the floor file).
- F1: the mutant `false && leaks.credential(...)` turns exactly the two new tests red.
- F2: removing the sort turns `WorkPackageDetailCyclesTest#theLastRowInLedgerFileOrderDecidesEvenWhenItIsTheEarlierInTime` and `ReviewCycleReaderTest#theLedgerLineNumberDecidesWhichRowIsLastWhateverOrderTheHistoryIsGivenIn` red.
- F3: dropping the file instead of refusing turns `WorkPackageDetailCyclesTest#aCycleNumberTooLargeForTheServedIntegerRefusesTheRequestInsteadOfDroppingTheCycle` red.
- The test token is synthetic: `DetailRoute.secret()` assembles `gh` + `p_` + a made-up string at run time.
- WP14's lane (lane-m, `c0d69dc4b`) merged with this tip compiles its tests unchanged (its 9-argument `HistoryRow` calls resolve to the retained constructor). The only textual conflicts of the merge are `OutOfScopeRoutesTest` and `jacoco-class-floor.properties`, which are WP-local files and not a `HistoryRow` matter.
- Native replay: file order gives `changes_requested`; `review-cycle-2147483648.md` gives 500 `source_unreadable` with one diagnostic; `review-cycle-2147483647.md` is served with `verdict: null`.

## F5 (severity 3): V26 is declared only in the planning prose; AC-14.4 requires a `knownDivergence` manifest entry

**Where:** `tests/contract/_mission_status_conformance.py` (`KNOWN_DIVERGENCES`, V1 to V25), `tests/contract/test_mission_status_conformance.py:1564` (`EXPECTED_ENTRY_IDS = V1..V25`) and `divergence_problems`; `data-model.md` section 10.2 (row V26), `traces/design-decisions.md` (D-P11-6 amended).

**Why it is a finding.** spec AC-14.4 says "the manifest holds one `knownDivergence` entry for each row" of the divergence table, and that it "makes this list complete". A test-time-generated case does not escape it: V5, V10, V11 and V17 are all generated at test time, and each is a manifest entry with `fixture: GENERATED` and `fixtures: []`. `divergence_problems` accepts exactly that shape ("names no committed fixture and is neither injected nor generated" is the only refusal). V15 is the same for an injected case. So there is no class of fixture-less divergence that lives outside the manifest. Today V26 has a Java pin (`WorkPackageDetailCyclesTest`) but nothing in the manifest, so the "every divergence pinned" checks cannot see it, and a later change that makes the oracle and Java agree, or deletes the Java pin, goes unnoticed. The data-model sentence "V26 has no committed fixture" is not a reason to omit the entry.

**Remedy (the exact one).** Add the entry V26 to `KNOWN_DIVERGENCES` in `tests/contract/_mission_status_conformance.py`:
- `id: "V26"`, `cause: "a review-cycle file whose number is above the int range (WP15 F3)"`, `fixture: GENERATED`, `fixtures: []`;
- `oracleOutcome`: the oracle's `_CYCLE_NAME` is unbounded, so it lists the cycle and serves its number;
- `javaAssertion: "500 source_unreadable"`.

No committed fixture is needed or wanted: the name is plain ASCII, so the non-ASCII constraint does not apply, and a committed golden would hold a `cycleNumber` Java can never serve. Then:
- regenerate the manifest with the generator's `--write`, so `manifest.json` carries V26 and `--check` passes;
- move `EXPECTED_ENTRY_IDS` to `range(1, 27)` and the message "not V1 to V25" to "V1 to V26";
- correct "V1 to V25" wherever a test or doc pins that range (grep `V1 to V25`);
- keep `WorkPackageDetailCyclesTest#aCycleNumberTooLarge...` as the Java pin, and put its name in the entry's `javaAssertion` or `cause` if the neighbouring entries do so.
Show the new entry in the manifest diff and run `tests/contract/test_mission_status_conformance.py` red-then-green (delete the entry, the divergence test must go red; the existing deletion control for V9 is the model).
The `.gitattributes` and router filters need no change (no new fixture directory).
