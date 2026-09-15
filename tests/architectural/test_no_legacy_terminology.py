"""Architectural test: forbidden legacy terminology must not reappear.

Locks in the rename performed by mission 01KSPN6C
(rename-[forbidden]-to-status-commit). If either forbidden term
reappears in the active-source surface (`src/`, `tests/`, `docs/`),
CI fails and the PR is rejected.

The forbidden terms are constructed via string concatenation in this
module so the test file does not flag itself.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

import pytest

# #3919: reviewed recovery evidence is immutable, not a general archive exemption.
_RECEIPT_PATH = "docs/archive/program-evidence/upgrade-preview-mission-health-01M1V6E1/recovery-receipt.json"
_RECEIPT_SHA256 = "f320ada834fbabcddd7186147d606551dcecf066dad4c4eef182eafcf0a7f4b8"

# #3919: collection evidence introduced by 177e0626 and frozen by 89c8e373.
# Only these reviewed whole-file bytes qualify, not other reports or node IDs.
_CENSUS_DIRECTORY = "docs/reports/test-sanitation/assertive-test-suite-sanitation-01KZME3P/raw"
_CENSUS_SHA256 = {
    f"{_CENSUS_DIRECTORY}/base-census.json": "c15ef616766752ac1d30ddac8d24b7929f4f874d45cc131392d443c1de9d5d8b",
    f"{_CENSUS_DIRECTORY}/head-census.json": "44349d051e845bc13a97babb59eb4034bebb515ab85cc9bc3ba111a6613c9bda",
}

# Architectural invariant scan that shells out to ``git grep`` over the live
# repo, so it carries both the architectural-gate marker and ``git_repo``
# (Rule 1 of test_pytest_marker_correctness: git subprocess users must be
# visible to CI's ``-m git_repo`` filter).
# ``docs_scoped``: this test scans ``docs/`` content (``_SCAN_ROOTS`` below), so a
# docs-only PR could newly-red it — it MUST run on the arch pole's docs-only trim.
pytestmark = [pytest.mark.architectural, pytest.mark.git_repo, pytest.mark.docs_scoped]


# Build forbidden terms from fragments so this test file does not contain
# the literal strings (otherwise the test would flag itself).
_FORBIDDEN_TERMS: tuple[str, ...] = (
    "cere" + "mony",
    "status" + "-writing",
)


_SCAN_ROOTS: tuple[str, ...] = ("src", "tests", "docs")
_EXTENSIONS: tuple[str, ...] = ("*.py", "*.md", "*.yaml", "*.yml")

# Paths excluded from the scan. kitty-specs/ contains historical mission
# artifacts that are explicitly out of scope per spec C-001. Worktrees and
# vendor directories are operational state.
_EXCLUDED_PATH_FRAGMENTS: tuple[str, ...] = (
    "kitty-specs/",
    # docs/adr/ holds immutable historical decision records whose bodies are
    # preserved byte-for-byte (NFR-001/C-002). Legacy terms in those snapshots
    # are quoted history, not active prose — same historical-artifact rationale
    # as the kitty-specs/ exemption above. The narrowness of this exemption
    # (docs/adr/ only, not the rest of docs/) is pinned by
    # test_docs_adr_exemption_is_narrow below.
    "docs/adr/",
    # packs/built-in/glossary_packs/ ships the built-in glossary pack, whose
    # data faithfully carries the seed's DEPRECATED entries ("ceremony commit",
    # "status-writing operation") and the `synonyms_to_avoid` list on "status
    # commit" -- i.e. it *documents* the forbidden legacy terms as data, the
    # same way this test's own `_FORBIDDEN_TERMS` construction or a dictionary
    # defining a banned word does. That is quoted/cataloged terminology, not
    # active prose using it -- the same historical-artifact rationale as the
    # docs/adr/ exemption above, applied to glossary pack data instead of
    # decision records. (The pack moved here from the retired
    # `src/charter/offering/glossary_packs/built-in/` location; `packs/` is not in
    # `_SCAN_ROOTS` today, so this exemption is kept forward-correct at the
    # pack's canonical home for when the pack tree enters the scan scope.)
    "packs/built-in/glossary_packs/",
    ".worktrees/",
    ".venv/",
    "node_modules/",
    ".git/",
    # The test file itself is excluded as a belt-and-suspenders measure;
    # the string-fragment construction above is the primary self-flag defense.
    "tests/architectural/test_no_legacy_terminology.py",
)


def _line_is_excluded(line: str) -> bool:
    """Exclude only canonical source paths; content never grants an exemption."""
    hit = _hit_parts(line)
    if hit is None:
        return False
    path = hit[0]
    directories = path.split("/")[:-1]
    for excluded in _EXCLUDED_PATH_FRAGMENTS:
        if excluded in {".worktrees/", ".venv/", "node_modules/", ".git/"}:
            if excluded[:-1] in directories:
                return True
        elif (excluded.endswith("/") and path.startswith(excluded)) or path == excluded:
            return True
    return False


def _hit_parts(line: str) -> tuple[str, int, str] | None:
    """Parse diagnostic hits, JSON-quoted for unusual paths by the Git adapter.

    Legacy plain hits remain supported by the pure seams. Malformed or
    noncanonical paths are retained as violations, never normalized to history.
    """
    if line.startswith('"'):
        try:
            path, end = json.JSONDecoder().raw_decode(line)
        except ValueError:
            return None
        remainder = line[end:]
    else:
        path, separator, rest = line.partition(":")
        remainder = separator + rest
    match = re.fullmatch(r":([1-9][0-9]*):(.*)", remainder, flags=re.DOTALL)
    if not isinstance(path, str) or match is None:
        return None
    if "\\" in path or any(part in {"", ".", ".."} for part in path.split("/")):
        return None
    return path, int(match[1]), match[2]


def _git_grep_hits(needle: str, roots: tuple[str, ...], *, kind: str, ignore_case: bool = False) -> list[str]:
    """Read NUL-delimited paths and line numbers, independent of Git quoting/config."""
    cmd = [
        "git",
        "-C",
        str(_repo_root()),
        "grep",
        "--null",
        "--line-number",
        "--full-name",
        "--no-color",
        "--no-heading",
        "--no-break",
        "--text",
        "--fixed-strings",
        *(["--ignore-case"] if ignore_case else []),
        "-e",
        needle,
        "--",
        *(f"{root}/" for root in roots),
    ]
    result = subprocess.run(cmd, capture_output=True, check=False)
    if result.returncode == 1:
        return []
    if result.returncode != 0:
        raise RuntimeError(f"git grep failed for {kind} {needle!r}: exit={result.returncode} stderr={result.stderr!r}")
    return _decode_grep_hits(result.stdout)


def _decode_grep_hits(output: bytes) -> list[str]:
    hits: list[str] = []
    remaining = output
    while remaining:
        path, path_separator, remaining = remaining.partition(b"\0")
        number, number_separator, remaining = remaining.partition(b"\0")
        content, newline, remaining = remaining.partition(b"\n")
        if not path or not path_separator or not number_separator or not newline or not re.fullmatch(rb"[1-9][0-9]*", number):
            raise RuntimeError("Malformed git grep output; refusing to suppress hits")
        # Git's -z bypasses C-style path quoting. JSON is only our diagnostic
        # encoding; it keeps colons, newlines and non-ASCII path bytes unambiguous.
        source_path = path.decode("utf-8", errors="surrogateescape")
        if not source_path.isascii() or any(char in source_path for char in ':"\\\r\n\t'):
            source_path = json.dumps(source_path)
        hits.append(f"{source_path}:{number.decode('ascii')}:{content.decode('utf-8', errors='surrogateescape')}")
    if not hits:
        raise RuntimeError("Malformed git grep output: success without hits")
    return hits


def _is_reviewed_recovery_hit(line: str, root: Path) -> bool:
    hit = _hit_parts(line)
    if hit is None or hit[0] != _RECEIPT_PATH:
        return False
    content = hit[2]
    if content.strip() != f'"rename-{_FORBIDDEN_TERMS[0]}-to-status-commit-01KSPN6C",':
        return False
    return _matches_frozen_source_hit(hit, root, _RECEIPT_SHA256)


def _is_reviewed_census_hit(line: str, root: Path) -> bool:
    hit = _hit_parts(line)
    if hit is None or (expected := _CENSUS_SHA256.get(hit[0])) is None:
        return False
    return _matches_frozen_source_hit(hit, root, expected)


def _matches_frozen_source_hit(hit: tuple[str, int, str], root: Path, expected: str) -> bool:
    relative, number, content = hit
    path = root
    for component in relative.split("/"):
        path /= component
        if path.is_symlink():
            return False
    evidence = path.read_bytes()
    # This is byte-integrity evidence, not a charter-content hash.
    if hashlib.sha256(evidence).hexdigest() != expected:  # noqa: TID251
        return False
    # Git separates content lines only on LF, retaining any other source bytes.
    lines = evidence.removesuffix(b"\n").split(b"\n")
    return number <= len(lines) and lines[number - 1] == content.encode("utf-8", errors="surrogateescape")


def _repo_root() -> Path:
    """Resolve the repository root by walking up to a .kittify/ marker."""
    here = Path(__file__).resolve()
    for parent in (here, *here.parents):
        if (parent / ".kittify").is_dir():
            return parent
    raise RuntimeError("Could not locate repo root (no .kittify/ marker found).")


def _require_tracked_scan_roots(roots: tuple[str, ...]) -> None:
    """Fail closed when a scan root has no tracked files under the repo root.

    ``git grep`` exits 1 for a pathspec that matches nothing exactly as it does
    for a clean tree, so a zero-hit verdict over a missing or renamed root
    (``src/`` -> ``source/``) would pass vacuously. The real gates call this
    before trusting an empty scan; the fixture-scoped helper tests stage only
    the roots they exercise and are not routed through it.
    """
    root_dir = _repo_root()
    for root in roots:
        result = subprocess.run(
            ["git", "-C", str(root_dir), "ls-files", "-z", "--", f"{root}/"],
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"git ls-files failed for scan root {root!r}: exit={result.returncode} stderr={result.stderr!r}")
        if not result.stdout:
            raise RuntimeError(f"Scan root {root!r} has no tracked files under {root_dir}; a zero-hit scan would be vacuous")


def _grep_for(term: str) -> list[str]:
    """Scan tracked active sources; Git/read/parse errors fail closed."""
    root = _repo_root()
    return [
        line
        for line in _git_grep_hits(term, _SCAN_ROOTS, kind="term")
        if not _line_is_excluded(line) and not _is_reviewed_recovery_hit(line, root) and not _is_reviewed_census_hit(line, root)
    ]


@pytest.mark.parametrize("term", _FORBIDDEN_TERMS)
def test_forbidden_term_does_not_appear(term: str) -> None:
    """Each forbidden legacy term must have zero occurrences in active source.

    Excluded surfaces: kitty-specs/ historical artifacts, worktrees, vendor
    directories. The test file itself is excluded via _EXCLUDED_PATH_FRAGMENTS
    and via the string-fragment construction of _FORBIDDEN_TERMS.
    """
    _require_tracked_scan_roots(_SCAN_ROOTS)
    hits = _grep_for(term)
    if hits:
        formatted = "\n  ".join(hits)
        pytest.fail(
            f"Forbidden legacy term {term!r} reappeared in active source.\n"
            f"Canonical term is 'status commit' (see "
            f".kittify/glossaries/spec_kitty_core.yaml).\n"
            f"Hits ({len(hits)}):\n  {formatted}"
        )


def test_docs_adr_exemption_is_narrow() -> None:
    """docs/adr/ is exempt as historical snapshots, but the rest of docs/ is not.

    Regression for WP06 (mission 01KW3SBK): 117 historical ADRs moved from the
    unscanned ``architecture/`` tree into the scanned ``docs/adr/`` tree. Their
    bodies are immutable, byte-for-byte snapshots (NFR-001/C-002), so quoted
    legacy terms inside them must not trip the guard — mirroring the existing
    kitty-specs/ historical-artifact exemption.

    This test pins the exemption as *narrow*: only ``docs/adr/`` is excluded.
    Any other docs/ path (guides, architecture, a top-level docs page) must
    still be scanned, so a real regression there is caught.
    """
    forbidden = _FORBIDDEN_TERMS[0]

    # A hit inside docs/adr/ is treated as an immutable historical snapshot.
    adr_hit = f"docs/adr/3.x/2026-04-17-1-some-decision.md:103:No inheritance {forbidden}."
    assert _line_is_excluded(adr_hit), "docs/adr/ hits must be exempt — historical decision records are immutable snapshots (NFR-001/C-002)."

    # The rest of docs/ must remain in scope: an exemption here would be a
    # blanket docs/ carve-out and a regression.
    still_scanned = (
        f"docs/guides/onboarding.md:7:Run the {forbidden} before merging.",
        f"docs/architecture/overview.md:12:The {forbidden} step is required.",
        f"docs/status-model.md:3:Avoid the legacy {forbidden} wording.",
    )
    for hit in still_scanned:
        assert not _line_is_excluded(hit), (
            f"Non-ADR docs path must still be scanned for legacy terms: {hit!r}. The docs/adr/ exemption must not blanket-exempt all of docs/."
        )


# --------------------------------------------------------------------------- #
# FR-016 / SC-011 -- lane-consolidation-sense "merge" drift-ratchet guard
# --------------------------------------------------------------------------- #
#
# ``merge`` is a three-sense overloaded term (ADR
# docs/adr/3.x/2026-07-23-2-post-consolidation-deferral-and-external-enforcement.md):
# lane consolidation (E1, ``spec-kitty merge``'s LOCAL operation), branch
# integration (``git merge``), and publish-to-origin. ADR
# docs/adr/3.x/2026-07-30-1-consolidated-write-surface-and-consolidate-terminology.md
# canonicalizes ``consolidate`` / ``consolidation`` for the lane-consolidation
# sense (#3080 foundation) and grandfathers existing "merge" occurrences for
# that sense pending the full #3080 rename.
#
# This is a SEPARATE, curated **phrase** ratchet from the term-level
# ``_FORBIDDEN_TERMS`` gate above -- a bare "merge" ban would flood every
# legitimate git-merge / publish-to-origin use, so only phrases that pair a
# lane concept with a merge-verb are forbidden. A **file-level** baseline
# (mirroring ``tests/architectural/test_no_tmp_paths_in_tests.py``'s
# grandfathering pattern) allows the phrase inside files that already carried
# it before this ratchet landed; any OTHER file introducing one of these
# phrases fails the gate. The baseline is a ceiling to shrink (full rename via
# #3080), not a floor to grow.

_LANE_CONSOLIDATION_FORBIDDEN_PHRASES: tuple[str, ...] = (
    "lane merge",
    "merge the lanes",
    "merging lanes",
    "lane-merge",
)

_LANE_CONSOLIDATION_SCAN_ROOTS: tuple[str, ...] = ("src", "docs")

# Grandfathered baseline as of mission post-merge-write-authoring-finish-01KYRRM5
# WP01/T003 (2026-07-30). Every relative path below was verified, at authoring
# time, to contain at least one of the phrases above via:
#
#   for term in "lane merge" "merge the lanes" "merging lanes" "lane-merge"; do
#     git grep -n -i --fixed-strings "$term" -- src/ docs/
#   done | grep -v '^docs/adr/'
#
# A file leaves this set only by being converted to "consolidate" terminology
# (#3080) -- entries are removed as they are fixed, never added to
# (test_lane_consolidation_baseline_does_not_grow pins that direction). The
# docs/adr/ tree is excluded (immutable historical snapshots, same rationale as
# the term-level exemption above); kitty-specs/ is excluded by construction
# (not one of the two scanned roots).
_LANE_CONSOLIDATION_PHRASE_BASELINE: frozenset[str] = frozenset(
    {
        "docs/changelog/CHANGELOG.md",
        "docs/development/3-2-docs-retrieval-index.yaml",
        "docs/plans/engineering-notes/naming-identity-ssot-strangler/00-OVERVIEW.md",
        "docs/plans/engineering-notes/naming-identity-ssot-strangler/randy-reducer-split-brain-map.md",
        "packs/built-in/procedures/mission-wrap-up-sequence.procedure.yaml",
        "src/charter/offering/skills/spec-kitty-git-workflow/references/git-operations-matrix.md",
        "src/charter/offering/skills/spec-kitty-implement-review/SKILL.md",
        "src/specify_cli/lanes/merge.py",
        "src/specify_cli/lanes/stale_check.py",
        "src/specify_cli/merge/git_probes.py",
    }
)


def _grep_for_phrase_ci(phrase: str, *, roots: tuple[str, ...]) -> list[str]:
    """Case-insensitive ``git grep`` for *phrase* across *roots*, docs/adr/ excluded.

    Returns raw ``<path>:<line>:<content>`` hit lines (unfiltered by baseline --
    baseline application is a separate, pure step in ``_hits_outside_baseline``
    so it stays independently testable without a git subprocess).
    """
    return [
        line for line in _git_grep_hits(phrase, roots, kind="phrase", ignore_case=True) if (hit := _hit_parts(line)) is None or not hit[0].startswith("docs/adr/")
    ]


def _hits_outside_baseline(hits: list[str], baseline: frozenset[str]) -> dict[str, list[str]]:
    """Group ``<path>:<line>:<content>`` hits by path, keeping only non-baseline paths.

    Pure function (no I/O) so the bite fixture and the green-on-legit/baseline
    proofs can exercise the exact grouping/filtering logic the real gate uses,
    without shelling out to git (SC-011's red-first + green-on-legit proof).
    """
    violations: dict[str, list[str]] = {}
    for line in hits:
        hit = _hit_parts(line)
        rel_path = hit[0] if hit is not None else line
        if rel_path in baseline:
            continue
        violations.setdefault(rel_path, []).append(line)
    return violations


def _collect_lane_consolidation_phrase_violations() -> dict[str, list[str]]:
    """Real-repo scan: every lane-consolidation-sense phrase hit outside the baseline."""
    violations: dict[str, list[str]] = {}
    for phrase in _LANE_CONSOLIDATION_FORBIDDEN_PHRASES:
        hits = _grep_for_phrase_ci(phrase, roots=_LANE_CONSOLIDATION_SCAN_ROOTS)
        for rel_path, grouped in _hits_outside_baseline(hits, _LANE_CONSOLIDATION_PHRASE_BASELINE).items():
            violations.setdefault(rel_path, []).extend(grouped)
    return violations


def test_lane_consolidation_phrasing_does_not_grow_beyond_baseline() -> None:
    """FR-016/SC-011: no NEW lane-consolidation-sense "merge" phrasing outside the baseline.

    The real CI gate. Bare "merge" is never banned (git-merge / publish-to-origin
    uses are untouched -- see test_lane_consolidation_guard_green_on_legit_uses);
    only the curated phrases in ``_LANE_CONSOLIDATION_FORBIDDEN_PHRASES`` are
    forbidden, and only outside the grandfathered ``_LANE_CONSOLIDATION_PHRASE_BASELINE``.
    """
    _require_tracked_scan_roots(_LANE_CONSOLIDATION_SCAN_ROOTS)
    violations = _collect_lane_consolidation_phrase_violations()
    if violations:
        formatted = "\n".join(f"  {rel}:\n    " + "\n    ".join(hits) for rel, hits in sorted(violations.items()))
        pytest.fail(
            "New lane-consolidation-sense 'merge' phrasing detected outside the "
            "grandfathered baseline. Canonical term is 'consolidate' / 'consolidation' "
            "(see docs/adr/3.x/2026-07-30-1-consolidated-write-surface-and-consolidate-"
            "terminology.md and docs/context/orchestration.md#lane-consolidation).\n"
            f"Offenders:\n{formatted}"
        )


def test_lane_consolidation_baseline_does_not_grow() -> None:
    """The grandfathered baseline is a ceiling to shrink, not a floor to grow.

    Regression for the exact class of silent-regrandfathering failure
    ``test_no_tmp_paths_in_tests.py::test_baseline_is_empty`` guards against:
    pins the current baseline SIZE so an agent cannot quietly widen the
    exemption instead of fixing (or genuinely, narrowly, justifying) a new
    offender.
    """
    assert len(_LANE_CONSOLIDATION_PHRASE_BASELINE) <= 10, (
        f"_LANE_CONSOLIDATION_PHRASE_BASELINE grew to {len(_LANE_CONSOLIDATION_PHRASE_BASELINE)} "
        "entries (was 10 at mission post-merge-write-authoring-finish-01KYRRM5 WP01/T003). "
        "Growing the baseline re-grandfathers new drift instead of fixing it or writing new "
        "code/prose with the canonical 'consolidate' term (C-012 boyscouting) -- if a new "
        "entry is genuinely unavoidable, widen this ceiling deliberately with a documented "
        "rationale, do not just raise the number to force green."
    )


def test_lane_consolidation_phrase_bite_fixture_fails_on_new_phrasing() -> None:
    """SC-011 red-first bite: a NEW (non-baseline) lane-consolidation phrasing is flagged.

    Proves the guard actually bites: a synthetic hit in a file that is NOT in
    the baseline must surface as a violation.
    """
    synthetic_hits = ["src/mission_runtime/some_new_module.py:10:    # lane merge happens here"]
    violations = _hits_outside_baseline(synthetic_hits, _LANE_CONSOLIDATION_PHRASE_BASELINE)
    assert "src/mission_runtime/some_new_module.py" in violations, (
        f"The guard must flag a new forbidden phrasing in a file outside the baseline -- got violations={violations}"
    )


def test_lane_consolidation_guard_green_on_legit_uses() -> None:
    """No false-positive flood: legitimate git-merge / publish-to-origin "merge" uses
    and bare "merge" never match any curated phrase.

    This is the SC-011 "stays green on legitimate ... uses" half of the bite
    proof: it directly exercises ``_LANE_CONSOLIDATION_FORBIDDEN_PHRASES``
    against realistic branch-integration and publish-to-origin lines, so the
    guard cannot regress into a bare-"merge" ban.
    """
    legit_lines = (
        "src/specify_cli/merge/executor.py:42:    subprocess.run(['git', 'merge', '--no-ff', branch])",
        "docs/guides/accept-and-merge.md:10:    Publish merged work to origin/main via a pull request.",
        'src/specify_cli/cli/commands/merge.py:5:    """Merge an accepted mission into the target branch."""',
        'docs/context/orchestration.md:568:    This is `merge` **Sense 1** -- the first of three distinct "merge" operations.',
    )
    for line in legit_lines:
        content = line.split(":", 2)[-1].lower()
        matched = [phrase for phrase in _LANE_CONSOLIDATION_FORBIDDEN_PHRASES if phrase in content]
        assert matched == [], f"Legitimate line falsely matched forbidden phrase(s) {matched}: {line!r}"


def test_lane_consolidation_guard_green_on_grandfathered_baseline() -> None:
    """A hit inside a baseline file is treated as grandfathered, not a violation.

    SC-011 "stays green on ... the grandfathered baseline" half of the bite
    proof.
    """
    hits_from_baseline_files = [f"{rel_path}:1:some lane merge related text" for rel_path in sorted(_LANE_CONSOLIDATION_PHRASE_BASELINE)]
    violations = _hits_outside_baseline(hits_from_baseline_files, _LANE_CONSOLIDATION_PHRASE_BASELINE)
    assert violations == {}, f"Baseline files must be grandfathered, got violations: {violations}"


def test_lane_consolidation_baseline_entries_are_currently_real() -> None:
    """Every baseline entry still exists and still contains a forbidden phrase.

    Guards against baseline staleness (a renamed/deleted file, or a file that
    was already fixed off the phrase, left in the baseline) -- which would
    silently weaken the ratchet without anyone noticing, the same
    stale-grandfather failure class ``test_lane_consolidation_baseline_does_not_grow``
    guards from the opposite direction (growth instead of staleness).
    """
    root = _repo_root()
    for rel_path in sorted(_LANE_CONSOLIDATION_PHRASE_BASELINE):
        path = root / rel_path
        assert path.is_file(), f"Baseline entry {rel_path!r} does not exist on disk."
        text = path.read_text(encoding="utf-8", errors="replace").lower()
        assert any(phrase in text for phrase in _LANE_CONSOLIDATION_FORBIDDEN_PHRASES), (
            f"Baseline entry {rel_path!r} no longer contains any forbidden phrase -- "
            "it has already been fixed and should be REMOVED from "
            "_LANE_CONSOLIDATION_PHRASE_BASELINE (shrink-only ratchet), not left in it."
        )


def test_glossary_pack_builtin_exemption_is_narrow() -> None:
    """packs/built-in/glossary_packs/ data is exempt; the rest of the tree is not.

    The built-in glossary pack ships the full seed -- including its DEPRECATED
    entries and the ``synonyms_to_avoid`` list on "status commit" -- at
    ``packs/built-in/glossary_packs/*.glossary-pack.yaml``. That data
    *documents* the forbidden legacy terms (same rationale as docs/adr/'s
    quoted-history exemption above), so it is exempt.

    This test pins the exemption as *narrow*: only the pack-data directory is
    excluded. Real code elsewhere (a sibling ``packs/`` subtree, or anything
    under ``src/``) must still be scanned, so an actual regression there is
    caught.
    """
    forbidden = _FORBIDDEN_TERMS[0]

    pack_hit = f"packs/built-in/glossary_packs/spec-kitty-core.glossary-pack.yaml:88:  surface: {forbidden} commit"
    assert _line_is_excluded(pack_hit), (
        "packs/built-in/glossary_packs/ hits must be exempt -- the pack "
        "faithfully documents the seed's deprecated/forbidden terminology "
        "as data, not active prose using it."
    )

    # Real code / a sibling pack subtree (and anything under src/) must remain
    # in scope: an exemption here would be an over-broad carve-out.
    still_scanned = (
        f"packs/built-in/procedures/some-procedure.yaml:3:# never say {forbidden}",
        f"src/charter/offering/glossary_packs/models.py:10:# {forbidden} is banned",
        f"src/charter/offering/drg/models.py:1:# {forbidden}",
    )
    for hit in still_scanned:
        assert not _line_is_excluded(hit), (
            f"Non-pack-data path must still be scanned for legacy terms: "
            f"{hit!r}. The packs/built-in/glossary_packs/ exemption must not "
            "blanket-exempt sibling pack subtrees or the rest of the tree."
        )


@pytest.mark.parametrize("fragment", _EXCLUDED_PATH_FRAGMENTS)
def test_exclusion_ignores_path_mentions_in_content(fragment: str) -> None:
    assert not _line_is_excluded(f"docs/guides/current.md:7:Use {_FORBIDDEN_TERMS[0]}; see {fragment}")


@pytest.mark.parametrize(
    "path",
    [
        "src/docs/adr/current.md",
        "docs/adr-extra/current.md",
        "src/notkitty-specs/current.py",
        "docs/guides/notnode_modules/current.md",
        "docs/guides/not.venv/current.md",
        "tests/architectural/test_no_legacy_terminology.py.bak",
        "tests/architectural/test_no_legacy_terminology.py/current.md",
        "src/tests/architectural/test_no_legacy_terminology.py",
        "docs/adr/../guides/current.md",
        "docs//adr/current.md",
        '"docs/adr/current.md:7:forged',
        "docs\\adr\\current.md",
    ],
)
def test_exclusion_respects_source_path_boundaries(path: str) -> None:
    assert not _line_is_excluded(f"{path}:7:{_FORBIDDEN_TERMS[0]}")


@pytest.mark.parametrize(
    "path",
    [
        "kitty-specs/history/spec.md",
        "docs/adr/history.md",
        "packs/built-in/glossary_packs/core.yaml",
        ".worktrees/lane/src/file.py",
        "src/node_modules/vendor.py",
        "tests/.venv/vendor.py",
        ".git/objects/file",
        "tests/architectural/test_no_legacy_terminology.py",
    ],
)
def test_exclusion_preserves_legitimate_paths(path: str) -> None:
    assert _line_is_excluded(f"{path}:7:{_FORBIDDEN_TERMS[0]}")


def _stage_scanner_fixture(root: Path, files: Mapping[str, str | bytes], *, ensure_roots: bool = True) -> None:
    """Stage *files* in a fresh repo at *root*.

    ``ensure_roots`` (default) also tracks an empty ``.keep`` under every scan
    root the fixture leaves untouched, so the real gates' non-vacuity
    precondition (:func:`_require_tracked_scan_roots`) sees a complete scan
    set; pass ``False`` to model a missing/renamed root deliberately.
    """
    subprocess.run(["git", "init", "--quiet", str(root)], check=True, capture_output=True)
    staged = dict(files)
    if ensure_roots:
        for scan_root in sorted(set(_SCAN_ROOTS) | set(_LANE_CONSOLIDATION_SCAN_ROOTS)):
            if not any(relative.startswith(f"{scan_root}/") for relative in staged):
                staged[f"{scan_root}/.keep"] = ""
    for relative, content in staged.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode("utf-8") if isinstance(content, str) else content)
    subprocess.run(["git", "-C", str(root), "add", "--", *staged], check=True, capture_output=True)


def test_real_term_scanner_keeps_active_hits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    term = _FORBIDDEN_TERMS[0]
    active = [
        "docs/current.md",
        "src/docs/adr/current.md",
        "tests/architectural/test_no_legacy_terminology.py.bak",
        "docs/notnode_modules/current.md",
        "docs/name:7:tail.md",
        'docs/quoted"name.md',
        "docs/nonascii-\u00e9.md",
        "docs/line\nbreak.md",
        "docs/back\\slash.md",
    ]
    _stage_scanner_fixture(
        tmp_path,
        {
            **dict.fromkeys(active, f"Use {term}; see docs/adr/history.md\n"),
            "docs/adr/history.md": f"Historical {term}\n",
        },
    )
    monkeypatch.setattr(sys.modules[__name__], "_repo_root", lambda: tmp_path)
    hits = _grep_for(term)
    assert len(hits) == len(active), hits
    with pytest.raises(pytest.fail.Exception, match="Forbidden legacy term"):
        test_forbidden_term_does_not_appear(term)


def test_real_phrase_scanner_keeps_path_lookalikes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _stage_scanner_fixture(
        tmp_path,
        {
            "src/docs/adr/current.md": "LANE MERGE\n",
            "docs/current.md": "lane merge; see docs/adr/history.md\n",
            "docs/name:7:tail.md": "lane merge\n",
            "docs/line\nbreak.md": "lane merge\n",
            "docs/adr/history.md": "lane merge\n",
        },
    )
    monkeypatch.setattr(sys.modules[__name__], "_repo_root", lambda: tmp_path)
    hits = _grep_for_phrase_ci("lane merge", roots=("src", "docs"))
    assert len(hits) == 4, hits
    assert len(_hits_outside_baseline(hits, frozenset({"docs/name"}))) == 4
    with pytest.raises(pytest.fail.Exception, match="New lane-consolidation"):
        test_lane_consolidation_phrasing_does_not_grow_beyond_baseline()


def test_real_scanners_fail_closed_outside_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys.modules[__name__], "_repo_root", lambda: tmp_path)
    with pytest.raises(RuntimeError, match="git grep failed for term"):
        _grep_for(_FORBIDDEN_TERMS[0])
    with pytest.raises(RuntimeError, match="git grep failed for phrase"):
        _grep_for_phrase_ci("lane merge", roots=("docs",))


def _regular_frozen_evidence_path(relative: str) -> Path:
    # Git grep omits staged symlinks; enforce this even when there are no hits.
    path = _repo_root()
    message = f"Frozen evidence must be a regular file without symlinks: {relative}"
    for component in relative.split("/"):
        path /= component
        assert not path.is_symlink(), message
    assert path.is_file(), message
    return path


def test_reviewed_receipt_bytes_are_preserved() -> None:
    path = _regular_frozen_evidence_path(_RECEIPT_PATH)
    # Reviewed file-integrity checksum; deliberately not charter normalization.
    assert hashlib.sha256(path.read_bytes()).hexdigest() == _RECEIPT_SHA256  # noqa: TID251


@pytest.mark.parametrize("mutation", ["none", "append", "replace", "alongside", "lookalike"])
def test_real_scanner_receipt_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    receipt = (_repo_root() / _RECEIPT_PATH).read_bytes()
    # Reviewed file-integrity checksum; deliberately not charter normalization.
    assert hashlib.sha256(receipt).hexdigest() == _RECEIPT_SHA256  # noqa: TID251
    term = _FORBIDDEN_TERMS[0]
    prose = f"Use {term}; see docs/adr/history.md"
    if mutation == "append":
        receipt += f"\n{prose}\n".encode()
    elif mutation == "replace":
        receipt = receipt.replace(b'"rename-', f'"{prose} rename-'.encode(), 1)
    files = {_RECEIPT_PATH: receipt}
    if mutation == "alongside":
        files[str(Path(_RECEIPT_PATH).with_name("current.md"))] = prose.encode()
    elif mutation == "lookalike":
        files = {_RECEIPT_PATH + ".bak": receipt}
    _stage_scanner_fixture(tmp_path, files)
    monkeypatch.setattr(sys.modules[__name__], "_repo_root", lambda: tmp_path)
    hits = _grep_for(term)
    if mutation == "none":
        assert hits == []
        test_forbidden_term_does_not_appear(term)
    else:
        assert hits, mutation
        if mutation in {"append", "replace", "alongside"}:
            assert any(prose in hit for hit in hits), hits
        if mutation == "alongside":
            assert len(hits) == 1, hits
        elif mutation == "lookalike":
            assert len(hits) == 2, hits
        with pytest.raises(pytest.fail.Exception, match="Forbidden legacy term"):
            test_forbidden_term_does_not_appear(term)


def test_real_scanners_empty_matches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _stage_scanner_fixture(tmp_path, {"docs/current.md": "Use status commits and consolidate lanes.\n"})
    monkeypatch.setattr(sys.modules[__name__], "_repo_root", lambda: tmp_path)
    assert _grep_for(_FORBIDDEN_TERMS[0]) == []
    assert _grep_for_phrase_ci("lane merge", roots=("docs",)) == []


def test_real_gates_refuse_an_untracked_scan_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A renamed/missing scan root must red the gate, never pass it vacuously."""
    term = _FORBIDDEN_TERMS[0]
    _stage_scanner_fixture(
        tmp_path,
        {"source/live.py": f"BANNER = '{term} commit'\n", "tests/t.py": "x = 1\n", "docs/d.md": "ok\n"},
        ensure_roots=False,
    )
    monkeypatch.setattr(sys.modules[__name__], "_repo_root", lambda: tmp_path)
    assert _grep_for(term) == []  # the vacuous verdict the gate must not trust
    with pytest.raises(RuntimeError, match="Scan root 'src' has no tracked files"):
        test_forbidden_term_does_not_appear(term)
    with pytest.raises(RuntimeError, match="Scan root 'src' has no tracked files"):
        test_lane_consolidation_phrasing_does_not_grow_beyond_baseline()


def test_real_gates_run_when_every_scan_root_is_tracked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _stage_scanner_fixture(tmp_path, {"src/live.py": "x = 1\n", "tests/t.py": "x = 1\n", "docs/d.md": "ok\n"})
    monkeypatch.setattr(sys.modules[__name__], "_repo_root", lambda: tmp_path)
    test_forbidden_term_does_not_appear(_FORBIDDEN_TERMS[0])
    test_lane_consolidation_phrasing_does_not_grow_beyond_baseline()


@pytest.mark.parametrize("output", [b"", b"docs/adr/history.md:1:bad\n", b"docs/a\0x\0bad\n", b"docs/a\x001\x00bad"])
def test_scanners_reject_malformed_git_output(output: bytes, monkeypatch: pytest.MonkeyPatch) -> None:
    def malformed(*args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(["git", "grep"], 0, stdout=output, stderr=b"")

    monkeypatch.setattr(subprocess, "run", malformed)
    with pytest.raises(RuntimeError, match="Malformed git grep output"):
        _grep_for(_FORBIDDEN_TERMS[0])
    with pytest.raises(RuntimeError, match="Malformed git grep output"):
        _grep_for_phrase_ci("lane merge", roots=("docs",))


@pytest.mark.parametrize("line", ['"docs/adr/broken:1:text', "docs/adr/file:zero:text", "/docs/adr/file:1:text"])
def test_malformed_hits_cannot_join_phrase_baseline(line: str) -> None:
    assert not _line_is_excluded(line)
    assert _hits_outside_baseline([line], frozenset({"docs/adr/file"}))


def test_receipt_hit_requires_real_matching_bytes(tmp_path: Path) -> None:
    term = _FORBIDDEN_TERMS[0]
    literal = f'"rename-{term}-to-status-commit-01KSPN6C",'
    source = (_repo_root() / _RECEIPT_PATH).read_bytes()
    _stage_scanner_fixture(tmp_path, {_RECEIPT_PATH: source})
    assert not _is_reviewed_recovery_hit(f"{_RECEIPT_PATH}:1:{literal}", tmp_path)
    assert not _is_reviewed_recovery_hit(f"{_RECEIPT_PATH}:999999:{literal}", tmp_path)
    assert not _is_reviewed_recovery_hit(f"{_RECEIPT_PATH}:337:Use {term}", tmp_path)
    path = tmp_path / _RECEIPT_PATH
    path.unlink()
    with pytest.raises(FileNotFoundError):
        _is_reviewed_recovery_hit(f"{_RECEIPT_PATH}:337:{literal}", tmp_path)
    original = tmp_path / "original.json"
    original.write_bytes(source)
    path.symlink_to(original)
    assert not _is_reviewed_recovery_hit(f"{_RECEIPT_PATH}:337:{literal}", tmp_path)


def test_real_phrase_scanner_rejects_prose_in_receipt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    receipt = (_repo_root() / _RECEIPT_PATH).read_bytes()
    _stage_scanner_fixture(tmp_path, {_RECEIPT_PATH: receipt + b"\nlane merge; see docs/adr/history.md\n"})
    monkeypatch.setattr(sys.modules[__name__], "_repo_root", lambda: tmp_path)
    assert len(_grep_for_phrase_ci("lane merge", roots=("docs",))) == 1
    with pytest.raises(pytest.fail.Exception, match="New lane-consolidation"):
        test_lane_consolidation_phrasing_does_not_grow_beyond_baseline()


@pytest.mark.parametrize("name", ["base", "head"])
def test_frozen_census_bytes(name: str) -> None:
    assert set(_CENSUS_SHA256) == {f"{_CENSUS_DIRECTORY}/{census}-census.json" for census in ("base", "head")}
    relative = f"{_CENSUS_DIRECTORY}/{name}-census.json"
    path = _regular_frozen_evidence_path(relative)
    # Parent-reviewed whole-file evidence integrity, not charter hashing.
    assert hashlib.sha256(path.read_bytes()).hexdigest() == _CENSUS_SHA256[relative]  # noqa: TID251


@pytest.mark.parametrize("name", ["base", "head"])
@pytest.mark.parametrize("mutation", ["none", "append", "replace", "neighbor", "lookalike"])
def test_real_census_term_boundary(name: str, mutation: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    relative = f"{_CENSUS_DIRECTORY}/{name}-census.json"
    source = (_repo_root() / relative).read_bytes()
    prose = f"Use {_FORBIDDEN_TERMS[0]}; see docs/adr/history.md"
    if mutation == "append":
        source += f"\n{prose}\n".encode()
    elif mutation == "replace":
        source = source.replace(b'"collection":', json.dumps(prose).encode() + b":", 1)
    files = {relative: source}
    if mutation == "neighbor":
        files[f"{_CENSUS_DIRECTORY}/current.md"] = prose.encode()
    elif mutation == "lookalike":
        files = {relative + ".bak": source}
    _stage_scanner_fixture(tmp_path, files)
    monkeypatch.setattr(sys.modules[__name__], "_repo_root", lambda: tmp_path)
    for term in _FORBIDDEN_TERMS:
        hits = _grep_for(term)
        if mutation == "none" or (mutation == "neighbor" and term == _FORBIDDEN_TERMS[1]):
            assert len(hits) == 0
            test_forbidden_term_does_not_appear(term)
        else:
            assert len(hits) > 0
            if mutation in {"append", "replace", "neighbor"} and term == _FORBIDDEN_TERMS[0]:
                assert any(prose in hit for hit in hits)
            if mutation == "neighbor":
                assert len(hits) == 1
            with pytest.raises(pytest.fail.Exception, match="Forbidden legacy term"):
                test_forbidden_term_does_not_appear(term)


@pytest.mark.parametrize("name", ["base", "head"])
@pytest.mark.parametrize("attack", ["content", "line-number", "symlink", "parent-symlink"])
def test_census_source_hits_cannot_be_forged(name: str, attack: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    relative = f"{_CENSUS_DIRECTORY}/{name}-census.json"
    source = (_repo_root() / relative).read_bytes()
    _stage_scanner_fixture(tmp_path, {relative: source})
    path = tmp_path / relative
    if attack == "symlink":
        path.unlink()
        original = tmp_path / "original.json"
        original.write_bytes(source)
        path.symlink_to(original)
    elif attack == "parent-symlink":
        original_dir = tmp_path / "original"
        path.parent.rename(original_dir)
        path.parent.symlink_to(original_dir, target_is_directory=True)
    number = 2 if attack == "line-number" else 1
    content = f"Use {_FORBIDDEN_TERMS[0]}" if attack == "content" else source.decode().rstrip("\n")
    forged = f"{relative}:{number}:{content}"
    monkeypatch.setattr(sys.modules[__name__], "_repo_root", lambda: tmp_path)
    monkeypatch.setattr(sys.modules[__name__], "_git_grep_hits", lambda *args, **kwargs: [forged])
    hits = _grep_for(_FORBIDDEN_TERMS[0])
    assert hits == [forged]


@pytest.mark.parametrize("name", ["base", "head"])
def test_real_census_phrase_prose_remains_visible(name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    relative = f"{_CENSUS_DIRECTORY}/{name}-census.json"
    source = (_repo_root() / relative).read_bytes()
    _stage_scanner_fixture(tmp_path, {relative: source + b"\nlane merge; see docs/adr/history.md\n"})
    monkeypatch.setattr(sys.modules[__name__], "_repo_root", lambda: tmp_path)
    hits = _grep_for_phrase_ci("lane merge", roots=("docs",))
    assert any("lane merge; see docs/adr/history.md" in hit for hit in hits)
    with pytest.raises(pytest.fail.Exception, match="New lane-consolidation"):
        test_lane_consolidation_phrasing_does_not_grow_beyond_baseline()


@pytest.mark.parametrize("relative", [_RECEIPT_PATH, *_CENSUS_SHA256])
@pytest.mark.parametrize("replacement", ["leaf-symlink", "parent-symlink", "directory"])
def test_real_git_frozen_evidence_requires_regular_path(relative: str, replacement: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = (_repo_root() / relative).read_bytes()
    _stage_scanner_fixture(tmp_path, {relative: source})
    monkeypatch.setattr(sys.modules[__name__], "_repo_root", lambda: tmp_path)

    def assert_integrity() -> None:
        if relative == _RECEIPT_PATH:
            test_reviewed_receipt_bytes_are_preserved()
        else:
            test_frozen_census_bytes(Path(relative).name.removesuffix("-census.json"))

    assert_integrity()
    assert _git_grep_hits(_FORBIDDEN_TERMS[0], ("docs",), kind="term")
    path = tmp_path / relative
    target = tmp_path / "outside-scan"
    if replacement == "parent-symlink":
        path.parent.rename(target)
        path.parent.symlink_to(target, target_is_directory=True)
        staged_path = str(Path(relative).parent)
    else:
        path.rename(target)
        if replacement == "leaf-symlink":
            path.symlink_to(target)
        else:
            path.mkdir()
            (path / "placeholder").write_text("No legacy terms here.\n", encoding="utf-8")
        staged_path = relative
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A", "--", "docs"], check=True, capture_output=True)
    if replacement != "directory":
        index = subprocess.run(
            ["git", "-C", str(tmp_path), "ls-files", "--stage", "--", staged_path],
            check=True,
            capture_output=True,
        )
        assert index.stdout.split()[0] == b"120000"
        assert path.read_bytes() == source
    # No fabricated hits: Git skips the symlink, so the byte gate must reject it.
    for term in _FORBIDDEN_TERMS:
        assert _git_grep_hits(term, ("docs",), kind="term") == []
        test_forbidden_term_does_not_appear(term)
    with pytest.raises(AssertionError, match="Frozen evidence must be a regular file without symlinks"):
        assert_integrity()
