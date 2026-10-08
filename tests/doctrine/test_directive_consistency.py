"""Consistency checks between shipped/proposed profile directive references and directives.

Cross-reference / linking checks apply to **shipped** artifacts only.
_proposed artifacts are work-in-progress and may reference artifacts that do not
yet exist.  Only schema-syntactic checks run across both shipped and _proposed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import jsonschema
from ruamel.yaml import YAML

from charter.offering.drg.migration.id_normalizer import normalize_directive_id
from tests.doctrine.conftest import DOCTRINE_SOURCE_ROOT, REPO_ROOT

pytestmark = [pytest.mark.fast, pytest.mark.doctrine, pytest.mark.corpus]

_DOCTRINE_ROOT = DOCTRINE_SOURCE_ROOT

# Built-in doctrine pack content relocated out of ``src/charter/offering/<kind>/built-in``
# into the flattened top-level ``packs/built-in/<kind>`` pack root (mission
# ``relocate-builtin-doctrine-packs-01KYT87F``). Schemas and templates stay under
# ``src/charter/offering/``.
_PACKS_BUILT_IN = REPO_ROOT / "packs" / "built-in"

PROFILES_DIR = _PACKS_BUILT_IN / "agent_profiles"
DIRECTIVE_SCHEMA = _DOCTRINE_ROOT / "schemas" / "directive.schema.yaml"

# Pack content is flattened -- one directory per kind, no ``built-in``/``_proposed`` split.
_DIRECTIVES_DIRS = [_PACKS_BUILT_IN / "directives"]
_TACTICS_DIRS = [_PACKS_BUILT_IN / "tactics"]
_PARADIGMS_DIRS = [_PACKS_BUILT_IN / "paradigms"]
_STYLEGUIDES_DIRS = [_PACKS_BUILT_IN / "styleguides"]
_TOOLGUIDES_DIRS = [_PACKS_BUILT_IN / "toolguides"]
_PROCEDURES_DIRS = [_PACKS_BUILT_IN / "procedures"]
_TEMPLATES_DIR = _DOCTRINE_ROOT / "templates"
_SHIPPED_DIRECTIVES_DIR = _PACKS_BUILT_IN / "directives"
_BUILT_IN_TACTICS_DIR = _PACKS_BUILT_IN / "tactics"
_SHIPPED_PARADIGMS_DIR = _PACKS_BUILT_IN / "paradigms"


def _multi_glob(dirs: list[Path], pattern: str) -> list[Path]:
    """Glob across multiple directories, returning sorted unique paths."""
    results: list[Path] = []
    for d in dirs:
        if d.exists():
            results.extend(d.rglob(pattern))
    return sorted(set(results))


def _load_yaml(path: Path) -> dict[str, Any]:
    yaml = YAML(typ="safe")
    with path.open("r", encoding="utf-8") as fh:
        return yaml.load(fh) or {}


def _profile_directive_refs() -> dict[str, str]:
    refs: dict[str, str] = {}
    yaml = YAML(typ="safe")

    for profile_path in sorted(PROFILES_DIR.glob("*.agent.yaml")):
        with profile_path.open("r", encoding="utf-8") as fh:
            profile = yaml.load(fh) or {}

        for ref in profile.get("directive-references", []):
            code = str(ref.get("code", "")).strip()
            title = str(ref.get("name", "")).strip()
            if not code:
                continue
            refs[code] = title

    return refs


def _directive_index() -> dict[str, tuple[str, str]]:
    """Map each shipped directive's canonical id -> ``(filename, title)``.

    The canonical id is what :func:`normalize_directive_id` produces from a
    directive's own ``id`` field — the SAME resolution the DRG extractor's
    ``artifact_to_urn`` uses when it mints ``agent_profile --requires-->
    directive`` edges from a profile's ``directive-references``. Numeric
    directives resolve to ``DIRECTIVE_NNN`` (from either the ``NNN`` a profile
    cites or the ``DIRECTIVE_NNN`` the file declares); slug-id directives
    (e.g. ``use-c4-model-techniques`` -> ``USE_C4_MODEL_TECHNIQUES``) resolve to
    their own upper-cased id.

    Resolving by canonical id — not by a ``{code}-*.directive.yaml`` filename
    glob — is what lets a *validly referenced* slug-id directive resolve to its
    real file + title. The old glob silently assumed every directive is
    ``NNN-slug``, so it could never match a directive whose whole stem is the
    slug (the first such profile reference, diagram-daisy -> USE_C4_MODEL_TECHNIQUES,
    is exactly what exposed the gap). The check's strength is unchanged: a
    referenced code must still resolve to a shipped directive file whose title
    matches the profile's declared name.
    """
    index: dict[str, tuple[str, str]] = {}
    for path in _multi_glob(_DIRECTIVES_DIRS, "*.directive.yaml"):
        data = _load_yaml(path)
        raw_id = str(data.get("id", "")).strip()
        if not raw_id:
            continue
        canonical = normalize_directive_id(raw_id)
        index[canonical] = (path.name, str(data.get("title", "")).strip())
    return index


def test_all_referenced_directives_have_matching_files_and_titles() -> None:
    refs = _profile_directive_refs()
    assert refs, "No directive references found in shipped profiles"

    index = _directive_index()
    for code, expected_title in refs.items():
        canonical = normalize_directive_id(code)
        assert canonical in index, (
            f"Missing directive file for code {code} (resolved to {canonical}); "
            f"known directive ids: {sorted(index)}"
        )

        _filename, actual_title = index[canonical]
        assert actual_title == expected_title, (
            f"Directive title mismatch for code {code}: "
            f"expected '{expected_title}', got '{actual_title}'"
        )


def test_directive_files_validate_against_schema() -> None:
    schema = _load_yaml(DIRECTIVE_SCHEMA)
    validator = jsonschema.Draft202012Validator(schema)

    directive_files = _multi_glob(_DIRECTIVES_DIRS, "*.directive.yaml")
    assert directive_files, "No directive files found"

    for path in directive_files:
        data = _load_yaml(path)
        errors = sorted(validator.iter_errors(data), key=lambda e: e.path)
        assert not errors, f"Schema validation failed for {path.name}: {[e.message for e in errors]}"


def test_lenient_adherence_directives_declare_explicit_allowances() -> None:
    directive_files = _multi_glob(_DIRECTIVES_DIRS, "*.directive.yaml")
    assert directive_files, "No directive files found"

    violations: list[str] = []
    for path in directive_files:
        data = _load_yaml(path)
        if str(data.get("enforcement", "")).strip() != "lenient-adherence":
            continue

        allowances = data.get("explicit_allowances", []) or []
        if not isinstance(allowances, list) or not any(str(item).strip() for item in allowances):
            violations.append(f"{path.name}: lenient-adherence requires non-empty explicit_allowances")

    assert not violations, "Lenient-adherence directive allowance violations:\n" + "\n".join(violations)


def _shipped_tactic_ids() -> set[str]:
    tactic_ids: set[str] = set()
    for path in _multi_glob([_BUILT_IN_TACTICS_DIR], "*.tactic.yaml"):
        data = _load_yaml(path)
        tactic_id = str(data.get("id", "")).strip()
        if tactic_id:
            tactic_ids.add(tactic_id)
    return tactic_ids


def test_no_directive_carries_inline_tactic_refs() -> None:
    """Post-WP02: shipped directives must not carry inline ``tactic_refs``.

    Cross-artifact relationships (directive → tactic) live exclusively as
    edges in ``packs/built-in/directive.graph.yaml`` after Phase 1 excision (edges
    shard by source kind). This test
    guards against regressions that reintroduce inline references.
    """
    directive_files = _multi_glob([_SHIPPED_DIRECTIVES_DIR], "*.directive.yaml")
    assert directive_files, "No shipped directive files found"

    offenders: list[str] = []
    for path in directive_files:
        data = _load_yaml(path)
        if "tactic_refs" in data:
            offenders.append(f"{path.name}: still declares inline `tactic_refs`")

    assert not offenders, (
        "Inline `tactic_refs` reintroduced on shipped directives — all "
        "cross-artifact relationships must live in packs/built-in/directive.graph.yaml "
        "(see WP02 of excise-doctrine-curation-and-inline-references-01KP54J6):\n"
        + "\n".join(offenders)
    )


def _shipped_styleguide_ids() -> set[str]:
    ids: set[str] = set()
    for pattern in ("*.styleguide.yaml", "**/*.styleguide.yaml"):
        for path in _multi_glob(_STYLEGUIDES_DIRS, pattern):
            data = _load_yaml(path)
            styleguide_id = str(data.get("id", "")).strip()
            if styleguide_id:
                ids.add(styleguide_id)
    return ids


def _shipped_toolguide_ids() -> set[str]:
    ids: set[str] = set()
    for path in _multi_glob(_TOOLGUIDES_DIRS, "*.toolguide.yaml"):
        data = _load_yaml(path)
        toolguide_id = str(data.get("id", "")).strip()
        if toolguide_id:
            ids.add(toolguide_id)
    return ids


def _shipped_procedure_ids() -> set[str]:
    ids: set[str] = set()
    for path in _multi_glob(_PROCEDURES_DIRS, "*.procedure.yaml"):
        data = _load_yaml(path)
        procedure_id = str(data.get("id", "")).strip()
        if procedure_id:
            ids.add(procedure_id)
    return ids


def _shipped_template_ids() -> set[str]:
    ids: set[str] = set()
    if not _TEMPLATES_DIR.exists():
        return ids

    for path in _TEMPLATES_DIR.glob("**/*.md"):
        if path.is_dir():
            continue
        if any(part.startswith(".") for part in path.relative_to(_TEMPLATES_DIR).parts):
            continue
        ids.add(path.stem.replace(".", "-"))
    return ids


def test_directive_references_resolve_to_known_artifacts() -> None:
    """All shipped directive references must point to shipped doctrine artifacts.

    _proposed directives are skipped — they may reference artifacts that are not yet shipped.
    """
    id_map = {
        "directive": _shipped_directive_ids(),
        "tactic": _shipped_tactic_ids(),
        "styleguide": _shipped_styleguide_ids(),
        "toolguide": _shipped_toolguide_ids(),
        "paradigm": _shipped_paradigm_ids(),
        "procedure": _shipped_procedure_ids(),
        "template": _shipped_template_ids(),
    }

    unresolved: list[str] = []
    for path in _multi_glob([_SHIPPED_DIRECTIVES_DIR], "*.directive.yaml"):
        data = _load_yaml(path)
        directive_id = str(data.get("id", "")).strip() or path.name
        for ref in data.get("references", []) or []:
            ref_type = str(ref.get("type", "")).strip()
            ref_id = str(ref.get("id", "")).strip()
            if ref_type not in id_map:
                unresolved.append(f"{directive_id}: unknown reference type '{ref_type}'")
                continue
            if ref_id and ref_id not in id_map[ref_type]:
                unresolved.append(f"{directive_id}: unresolved {ref_type} reference '{ref_id}'")

    assert not unresolved, "Unresolved directive references:\n" + "\n".join(unresolved)


# ---------------------------------------------------------------------------
# Tactic cross-reference graph: loop detection
# ---------------------------------------------------------------------------

def _build_tactic_ref_graph() -> dict[str, list[str]]:
    """Return adjacency list: tactic_id -> [referenced tactic_ids].

    Only shipped tactics are included; _proposed tactics may have dangling refs.
    """
    graph: dict[str, list[str]] = {}
    for path in _multi_glob([_BUILT_IN_TACTICS_DIR], "*.tactic.yaml"):
        data = _load_yaml(path)
        tactic_id = str(data.get("id", "")).strip()
        if not tactic_id:
            continue
        neighbours: list[str] = []
        # Root-level references
        for ref in data.get("references", []) or []:
            if ref.get("type") == "tactic":
                neighbours.append(str(ref["id"]).strip())
        # Step-level references
        for step in data.get("steps", []) or []:
            for ref in step.get("references", []) or []:
                if ref.get("type") == "tactic":
                    neighbours.append(str(ref["id"]).strip())
        graph[tactic_id] = neighbours
    return graph


def _detect_cycles(graph: dict[str, list[str]]) -> list[list[str]]:
    """DFS cycle detection; returns list of cycles (each cycle as ordered node list)."""
    visited: set[str] = set()
    path: list[str] = []
    path_set: set[str] = set()
    cycles: list[list[str]] = []

    def dfs(node: str) -> None:
        if node in path_set:
            start = path.index(node)
            cycles.append(path[start:] + [node])
            return
        if node in visited:
            return
        visited.add(node)
        path.append(node)
        path_set.add(node)
        for neighbour in graph.get(node, []):
            dfs(neighbour)
        path.pop()
        path_set.discard(node)

    for node in graph:
        dfs(node)
    return cycles


def test_tactic_reference_graph_has_no_cycles() -> None:
    """Tactic cross-references must form a DAG; cycles would cause infinite resolution loops."""
    graph = _build_tactic_ref_graph()
    assert graph, "No tactics found to build reference graph"
    cycles = _detect_cycles(graph)
    assert not cycles, (
        "Cyclic tactic references detected (would cause infinite resolution loops):\n"
        + "\n".join(" -> ".join(cycle) for cycle in cycles)
    )


def test_tactic_references_resolve_to_known_tactics() -> None:
    """All tactic-type cross-references inside shipped tactic files must point to a shipped tactic.

    _proposed tactics are excluded — their references may target artifacts not yet shipped.
    """
    tactic_ids = _shipped_tactic_ids()
    unresolved: list[str] = []
    for path in _multi_glob([_BUILT_IN_TACTICS_DIR], "*.tactic.yaml"):
        data = _load_yaml(path)
        tactic_id = str(data.get("id", "")).strip()
        for ref in data.get("references", []) or []:
            if ref.get("type") == "tactic":
                ref_id = str(ref.get("id", "")).strip()
                if ref_id and ref_id not in tactic_ids:
                    unresolved.append(f"{tactic_id}: root reference '{ref_id}' not found")
        for step in data.get("steps", []) or []:
            for ref in step.get("references", []) or []:
                if ref.get("type") == "tactic":
                    ref_id = str(ref.get("id", "")).strip()
                    if ref_id and ref_id not in tactic_ids:
                        step_title = step.get("title", "?")
                        unresolved.append(
                            f"{tactic_id} step '{step_title}': reference '{ref_id}' not found"
                        )
    assert not unresolved, "Unresolved tactic-to-tactic references:\n" + "\n".join(unresolved)


# ---------------------------------------------------------------------------
# Shipped-artifact ID lookups (used by the reference-resolution checks above
# and by ``test_no_paradigm_carries_inline_tactic_refs`` below).
#
# The three contradiction-declaration resolution checks that used to live in
# this section (retired-field entries resolving to known artifacts) were
# removed in WP03 of doctrine-tension-edges-01KY1WPC alongside the retired
# field itself. Their coverage is not lost: every edge in the shipped graph
# (including the hand-authored ``in_tension_with``/``reconciles_tension``/
# ``rejects`` edges that replaced the old contradiction declarations) is
# already validated for dangling references by ``assert_valid`` via the
# ``shipped_drg_graph`` fixture (``tests/doctrine/conftest.py``), which every
# DRG-consuming test in this suite shares. A ``rejects`` edge's target being
# specifically anti-pattern-kinded is WP04's dedicated validator test
# (INV-004), not duplicated here.
# ---------------------------------------------------------------------------

def _shipped_directive_ids() -> set[str]:
    ids: set[str] = set()
    for path in _multi_glob([_SHIPPED_DIRECTIVES_DIR], "*.directive.yaml"):
        data = _load_yaml(path)
        d_id = str(data.get("id", "")).strip()
        if d_id:
            ids.add(d_id)
    return ids


def _shipped_paradigm_ids() -> set[str]:
    ids: set[str] = set()
    for path in _multi_glob([_SHIPPED_PARADIGMS_DIR], "*.paradigm.yaml"):
        data = _load_yaml(path)
        p_id = str(data.get("id", "")).strip()
        if p_id:
            ids.add(p_id)
    return ids


def test_no_paradigm_carries_inline_tactic_refs() -> None:
    """Post-WP02: shipped paradigms must not carry inline ``tactic_refs``.

    Paradigm → tactic relationships live in ``src/charter/offering/paradigm.graph.yaml``
    after Phase 1 excision; this test guards against regression.
    """
    offenders: list[str] = []
    for path in _multi_glob([_SHIPPED_PARADIGMS_DIR], "*.paradigm.yaml"):
        data = _load_yaml(path)
        paradigm_id = str(data.get("id", "")).strip()
        if "tactic_refs" in data:
            offenders.append(f"{paradigm_id}: still declares inline `tactic_refs`")
    assert not offenders, (
        "Inline `tactic_refs` reintroduced on shipped paradigms — all "
        "relationships must live in src/charter/offering/paradigm.graph.yaml "
        "(see WP02 of excise-doctrine-curation-and-inline-references-01KP54J6):\n"
        + "\n".join(offenders)
    )


def _entry_title(entry: object) -> str:
    """Return the leading title segment of a colon-delimited doctrine entry.

    Failure-mode / procedure entries in this doctrine pack are authored as
    ``"<Title>: <explanation ...>"``. Anchoring an assertion on this leading
    segment — rather than the whole entry string — avoids a false match on
    an incidental restatement of a needle phrase buried later in the
    explanatory prose (pr-tests-001, mission analyze-prompt-context-load-01M3F4BV
    pre-merge squad): a case-sensitive substring check against the full entry
    text passed only because the entry's closing sentence happened to repeat
    the phrase in lowercase, not because the assertion was anchored to the
    entry's own stable identity (its title). No entry in this pack's
    failure_modes/procedures lists is titleless — every one is authored
    ``"<Title>: ..."`` — so the ``sep`` fallback below is defensive only.
    """
    title, sep, _ = str(entry).partition(":")
    return title.strip() if sep else str(entry).strip()


def test_size_assumption_bypass_failure_mode_documented() -> None:
    """FR-002 (mission analyze-prompt-context-load-01M3F4BV, issue #5005): DIRECTIVE_044 /
    the canonical-source-unification tactic must name the evidenced failure mode explicitly —
    an agent bypassing a canonical prompt/skill/CLI surface on an *unverified size assumption*
    instead of attempting to load/measure it first. Neither doctrine-source file names this
    failure mode today.

    GREEN: ``canonical-source-unification.tactic.yaml`` carries a failure-mode entry whose
    own TITLE (the segment before the first ``:``) names the phrase — anchored
    case-insensitively on the title via :func:`_entry_title` (pr-tests-001 fix, mission
    analyze-prompt-context-load-01M3F4BV pre-merge squad): the prior version of this test
    matched a case-sensitive substring against the WHOLE entry string, which passed only
    because of an incidental lowercase restatement in the entry's closing sentence — a
    behaviour-preserving copy-edit of that restatement (or a capitalization normalization
    of the title) would have flipped the assertion's verdict without the underlying
    doctrine content actually regressing. Anchoring on the title segment instead couples
    the assertion to the entry's stable identity.
    """
    tactic_path = _BUILT_IN_TACTICS_DIR / "canonical-source-unification.tactic.yaml"
    directive_path = _SHIPPED_DIRECTIVES_DIR / "044-canonical-sources-and-unification.directive.yaml"
    assert tactic_path.is_file(), f"expected FR-002 target file to exist: {tactic_path}"
    assert directive_path.is_file(), f"expected FR-002 target file to exist: {directive_path}"

    tactic_data = _load_yaml(tactic_path)
    directive_data = _load_yaml(directive_path)

    failure_modes = tactic_data.get("failure_modes", []) or []
    procedures = directive_data.get("procedures", []) or []

    needle = "unverified size assumption"
    found_in_tactic = any(needle in _entry_title(entry).lower() for entry in failure_modes)
    found_in_directive = any(needle in _entry_title(entry).lower() for entry in procedures)

    assert found_in_tactic or found_in_directive, (
        f"Expected the failure-mode text {needle!r} in the TITLE of an entry in "
        f"canonical-source-unification.tactic.yaml's failure_modes and/or "
        f"044-canonical-sources-and-unification.directive.yaml's procedures "
        f"(FR-002, analyze-prompt-context-load-01M3F4BV / issue #5005) — found in neither."
    )


#: The four shipped profiles that cite DIRECTIVE_044 via ``directive-references``
#: (confirmed via ``grep -rl 'code: "044"' packs/built-in/agent_profiles/``). Operator
#: Decision 8 (mission analyze-prompt-context-load-01M3F4BV, round-2 rework, 2026-09-27)
#: authorizes the failure-mode clause on all four, not ``implementer-ivan`` alone.
DIRECTIVE_044_CITING_PROFILES = (
    "architect-alphonso",
    "implementer-ivan",
    "doctrine-daphne",
    "python-pedro",
)


@pytest.mark.parametrize("profile_id", DIRECTIVE_044_CITING_PROFILES)
def test_size_assumption_bypass_failure_mode_in_each_profiles_own_source_file(
    profile_id: str,
) -> None:
    """WP01-C3-001 / pr-FRESH2-001 (mission analyze-prompt-context-load-01M3F4BV cycle-3
    fix): assert directly on each profile's OWN source YAML, not on
    ``resolve_profile``'s lineage-merged output.

    The companion test immediately below (``..._reaches_rendered_profile_context``) proves the
    failure-mode text reaches rendered agent-visible context through the *production*
    render path — but for ``python-pedro`` specifically, that path is satisfied by
    inheritance from its DRG ``specializes_from`` parent ``implementer-ivan``, not by
    ``python-pedro``'s own file. ``AgentProfileRepository.resolve_profile``'s lineage
    union-merge (``_union_merge``,
    ``src/charter/offering/agent_profiles/repository.py:190-204``) seeds ``seen`` from
    the accumulated ancestor merge first, so a child's own ``directive-references`` item
    sharing a ``code`` with an item the accumulator already carries (here, ``"044"``,
    contributed by ``implementer-ivan``) is filtered out of the merge entirely — the
    child's own entry never reaches ``resolve_profile("python-pedro")``'s output. A
    revert of ONLY ``python-pedro.agent.yaml``'s own DIRECTIVE_044 rationale hunk is
    therefore invisible to the rendered-reachability test (it stays green via
    inheritance) even though the source file itself regressed. This test closes that
    gap: it reads each of the four DIRECTIVE_044-citing profiles' own YAML file
    directly (not through ``resolve_profile``) and asserts the failure-mode clause is
    present in THAT file's own ``directive-references[].rationale`` for code ``"044"``
    — so a revert of any one profile's own hunk (including ``python-pedro``'s, which
    the rendered-reachability test's production-path assertion cannot catch) is
    caught here. Reproduced RED-first in an isolated scratch worktree with only
    ``python-pedro``'s own hunk reverted (see the WP's commit history / review record
    for the exact command and output); GREEN on the lane as shipped.
    """
    profile_path = PROFILES_DIR / f"{profile_id}.agent.yaml"
    assert profile_path.is_file(), f"expected shipped profile file to exist: {profile_path}"

    data = _load_yaml(profile_path)
    directive_refs = data.get("directive-references", []) or []
    entry_044 = next((e for e in directive_refs if str(e.get("code")) == "044"), None)
    assert entry_044 is not None, (
        f"expected {profile_id}.agent.yaml's own directive-references to cite "
        "DIRECTIVE_044 (code \"044\")"
    )

    needle = "unverified size assumption"
    rationale = str(entry_044.get("rationale", ""))
    assert needle in rationale.lower(), (
        f"Expected {profile_id}.agent.yaml's OWN DIRECTIVE_044 directive-references "
        f"entry rationale to name the failure mode {needle!r} directly in its source "
        "file — this is a raw-YAML, own-file check that catches a revert of this "
        "profile's own hunk even when resolve_profile's lineage union-merge would "
        "otherwise shadow it (python-pedro's case: its own entry is discarded by "
        "_union_merge in favor of implementer-ivan's, per "
        "src/charter/offering/agent_profiles/repository.py:190-204). "
        f"Rationale found: {rationale!r}"
    )


@pytest.mark.parametrize("profile_id", DIRECTIVE_044_CITING_PROFILES)
def test_size_assumption_bypass_failure_mode_reaches_rendered_profile_context(
    profile_id: str,
) -> None:
    """FR-002 delivery gap (pr-contract-001, mission analyze-prompt-context-load-01M3F4BV
    pre-merge squad): the failure-mode text documented in
    ``canonical-source-unification.tactic.yaml``'s ``failure_modes`` is never read by any
    automatic doctrine renderer — a tactic's inline body only ever renders
    Name/Purpose/Steps (``_format_inline_tactic_body`` /
    ``format_inline_named_body``) — and both that tactic's rendered body (~4.3K chars)
    and DIRECTIVE_044's rendered body (~3.5K chars) already exceed the 2,400-char
    per-artifact inline ceiling (``_PROFILE_INLINE_BODY_LIMIT_CHARS``,
    ``token_budget.py``), so both fall back to a generic fetch-stanza pointer in every
    automatic render path regardless of which file carries the new text.

    The one surface that DOES render unconditionally, independent of that per-artifact
    body budget, is the profile-citation header line: ``_render_directive_entry``
    (``charter.activation.context_renderers.profile_sections``) appends a profile's own
    ``directive-references[].rationale`` to the citation's header line BEFORE the
    body/fetch-stanza budget check ever runs — so that rationale text always reaches the
    rendered context for any profile citing the directive, regardless of the directive's
    own body length.

    This test exercises the REAL shipped doctrine catalog (not a synthetic fixture)
    through ``_render_profile_sections`` — the same profile-channel renderer
    ``build_charter_context`` / ``spec-kitty charter context`` calls for every action an
    agent under any of the four shipped profiles performs — so it asserts on real
    rendered output through the pre-existing entry point, not raw YAML.

    **Extended 2026-09-27 (round-2 rework, Operator Decision 8, WP01 cycle-2 finding
    WP01-C2-003 context):** parametrized over all four DIRECTIVE_044-citing profiles —
    ``architect-alphonso``, ``implementer-ivan``, ``doctrine-daphne``, ``python-pedro``
    — not ``implementer-ivan`` alone. RED before round 2's fix, GREEN after, for TWO of
    the four cases: ``architect-alphonso`` and ``doctrine-daphne`` (their own files'
    rationale genuinely lacked the clause, and ``resolve_profile`` reads each of those
    two directly — neither has a lineage parent whose own "044" entry could shadow
    it). ``implementer-ivan`` was already green from the round-1 rework and stays green.

    **``python-pedro`` is a distinct, third case — corrected 2026-09-27, cycle-3 fix
    (WP01-C3-001 / pr-FRESH2-001): it was ALREADY GREEN before this round's fix too,**
    but not because its own file's rationale mentioned the failure mode at that time.
    ``python-pedro`` ``specializes_from`` ``implementer-ivan`` in the DRG
    (``packs/built-in/agent_profile.graph.yaml``), and
    ``AgentProfileRepository.resolve_profile``'s lineage union-merge (``_union_merge``,
    ``src/charter/offering/agent_profiles/repository.py:190-204``) resolves a
    same-``code`` collision on ``directive-references`` to whichever entry the
    accumulated ancestor merge already carries when the child is folded in — that is
    ``implementer-ivan``'s "044" entry, never ``python-pedro``'s own. So this
    parametrized case for ``python-pedro`` has always exercised (and only ever proves)
    the INHERITED rationale, reached via lineage from ``implementer-ivan``, through the
    real ``resolve_profile``/``_render_profile_sections`` production path — not
    ``python-pedro``'s own file content. Reverting ONLY ``python-pedro``'s own
    DIRECTIVE_044 rationale hunk leaves this specific parametrized case green
    regardless, because the rendered output it asserts on is unaffected by that file.
    The companion test
    ``test_size_assumption_bypass_failure_mode_in_each_profiles_own_source_file``
    (immediately above) closes that gap by asserting directly on each profile's own
    source YAML, catching a revert of ``python-pedro``'s own hunk that this test
    cannot. This still does **not** reach the mission-level orchestrating agent for
    analyze/specify/plan/tasks/review/accept, whose step contract carries
    ``agent_profile: null`` — that residual gap (WP01-C2-003) is out of this test's
    scope and is recorded in spec.md's Known Residual section, not silently claimed as
    closed here.
    """
    from charter.activation.context_renderers.profile_sections import (
        _render_profile_sections,
    )
    from charter.offering.agent_profiles import AgentProfileRepository
    from charter.offering.service import CharterOfferingService

    service = CharterOfferingService()
    profile = AgentProfileRepository().resolve_profile(profile_id)
    assert profile is not None, f"expected the shipped {profile_id} profile to resolve"

    rendered = _render_profile_sections(profile, service)

    needle = "unverified size assumption"
    assert needle in rendered.lower(), (
        f"Expected the FR-002 failure-mode text to reach {profile_id}'s rendered "
        "profile-cited-directives context (DIRECTIVE_044's citation rationale) — the "
        "one automatic render path that survives the per-artifact inline-body budget "
        "both the tactic and the directive already exceed. Rendered block:\n" + rendered
    )
