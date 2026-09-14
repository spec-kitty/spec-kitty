"""Architectural gates: guidance across ``src/`` must not name a dead path.

Split out of ``test_no_dead_doctrine_paths.py`` (mission
``doctrine-consumer-surface-missions-extraction-01KZ6G6H`` WP01, FR-001) --
Gate A and Gate B both scan ``_SRC_ROOT`` (all of ``src/``, plus the relocated
``packs/built-in/`` shipped tree), not just ``src/doctrine/``. They share a
CLI-wide scope with each other but not with Gate C (``src/doctrine/``-only,
still in ``test_no_dead_doctrine_paths.py``) or Gate D (``docs/``-only, in
``test_dead_builtin_doc_paths.py``).

Originally: mission ``doctrine-silence-guards-01KYFV7Q`` WP07 (FR-008, FR-009,
NFR-003).

``A`` -- the DRG monolith ``src/doctrine/graph.yaml``, sharded out of
existence by #2680 into one ``<kind>.graph.yaml`` fragment per kind, and the
``src/doctrine/<kind>.graph.yaml`` fragment home those shards first landed in,
itself emptied when mission ``relocate-builtin-doctrine-packs-01KYT87F`` moved
the fragments to the ``packs/built-in/`` pack root (#2715).

``B`` -- the ``<kind>/shipped/`` pack layer, which has never existed on disk;
the shipped pack layer is ``<kind>/built-in/``.

Each gate carries **discriminators**: semantic exclusions that keep it from
false-redding on correct code. A gate that flags every mention of a string is
not a gate, it is a spell-checker, and the first correct site it flags gets it
deleted. NFR-003 therefore requires every discriminator be proven by a fixture
that would false-red *without* it -- the ``*_would_false_red_without_*`` tests
below are those proofs. Each also pins the discriminator's **effect set**
positively (the exact excluded sites and their count), so widening a
discriminator to silence an inconvenient site is a visible diff here rather
than a quiet regex tweak.

There is no violation allowlist. Discriminators exclude sites that are
*correct*; they never excuse a site that is wrong.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pytest

from tests.architectural._dead_path_scan import (
    _PACKS_ROOT,
    _REPO_ROOT,
    _SRC_ROOT,
    Site,
    _rel,
    _render,
    _text_files,
)

#: Without this the CI shard that selects ``-m architectural`` collects none of
#: these tests, and the gate silently never runs.
pytestmark = [pytest.mark.architectural, pytest.mark.git_repo]


# ---------------------------------------------------------------------------
# Gate A -- the dead DRG monolith path
# ---------------------------------------------------------------------------

#: Any slash-joined literal naming a ``graph.yaml`` -- the monolith, or a
#: ``<kind>.graph.yaml`` / ``*.graph.yaml`` fragment -- directly inside a
#: ``doctrine`` directory. Deliberately broader than the exact built-in
#: string: the defect class is "names a doctrine-directory DRG graph file", and
#: a gate keyed only on ``src/doctrine/graph.yaml`` is evaded by rewording the
#: prefix or by naming a fragment instead of the monolith (#2715). The live
#: fragments sit at ``packs/built-in/<kind>.graph.yaml``, which has no
#: ``doctrine/`` segment and so never matches.
_GRAPH_MONOLITH_RE = re.compile(r"[\w./<>*-]*doctrine/(?:[\w<>*-]+\.)?graph\.yaml")

#: Discriminator A1. The project tier really does write a single
#: ``graph.yaml`` under ``.kittify/doctrine/``; that path is live, not dead.
_PROJECT_TIER_PATH = ".kittify/doctrine/graph.yaml"

#: Discriminator A2. An agent profile's avoidance boundary names a path in
#: order to *forbid* it. Rewriting such a mention inverts the sentence.
_FORBIDDING_FIELD = "avoidance-boundary:"


@dataclass(frozen=True)
class GraphMonolithScan:
    """Gate A result, split by discriminator."""

    violations: tuple[Site, ...]
    project_tier: tuple[Site, ...]
    forbidding_mentions: tuple[Site, ...]

    @property
    def naive(self) -> tuple[Site, ...]:
        """Every match, as a gate with no discriminators would report it."""
        return tuple(sorted(self.violations + self.project_tier + self.forbidding_mentions))


def _forbidding_span(path: Path, lines: tuple[str, ...]) -> tuple[int, int] | None:
    """Return the 1-based inclusive line span of an agent profile's
    ``avoidance-boundary`` block, or ``None`` when the file has no such block.

    The span is derived from YAML block structure (key indentation), not from
    prose matching, so it cannot be widened by wording.
    """
    if not path.name.endswith(".agent.yaml"):
        return None
    for index, line in enumerate(lines):
        stripped = line.lstrip()
        if not stripped.startswith(_FORBIDDING_FIELD):
            continue
        key_indent = len(line) - len(stripped)
        end = len(lines)
        for follow in range(index + 1, len(lines)):
            following = lines[follow]
            if not following.strip():
                continue
            if len(following) - len(following.lstrip()) <= key_indent:
                end = follow
                break
        return (index + 1, end)
    return None


def scan_graph_monolith_paths(root: Path) -> GraphMonolithScan:
    """Classify every ``doctrine/graph.yaml`` mention under *root*."""
    violations: list[Site] = []
    project_tier: list[Site] = []
    forbidding: list[Site] = []
    for path, lines in _text_files(root):
        span = _forbidding_span(path, lines)
        for number, line in enumerate(lines, start=1):
            for match in _GRAPH_MONOLITH_RE.finditer(line):
                site = Site(_rel(path, root), number, match.group(0))
                if _PROJECT_TIER_PATH in match.group(0):
                    project_tier.append(site)
                elif span is not None and span[0] <= number <= span[1]:
                    forbidding.append(site)
                else:
                    violations.append(site)
    return GraphMonolithScan(
        violations=tuple(sorted(violations)),
        project_tier=tuple(sorted(project_tier)),
        forbidding_mentions=tuple(sorted(forbidding)),
    )


# ---------------------------------------------------------------------------
# Gate B -- the `<kind>/shipped/` pack layer that never existed
# ---------------------------------------------------------------------------

#: Discriminator B1 is the leading path segment: ``shipped/`` only counts as a
#: pack-layer reference when a directory segment precedes it. English prose
#: ("the shipped/packaged artifact", "a shipped/custom step") has no such
#: segment and is not a path.
_SHIPPED_PATH_RE = re.compile(r"(?:<[A-Za-z_][\w-]*>|[A-Za-z_][\w-]*)/shipped/")

#: The same class with B1 removed -- used only to prove B1 does work.
_SHIPPED_NAIVE_RE = re.compile(r"shipped/")

#: The whole dead path, not just its ``<segment>/shipped/`` core. Discriminator
#: B2 compares this token against the frozen seed, so a pack that *invented* a
#: sibling dead path under the same segment cannot ride the seed's coat-tails.
_SHIPPED_FULL_PATH_RE = re.compile(r"[\w./<>-]*(?:<[A-Za-z_][\w-]*>|[A-Za-z_][\w-]*)/shipped/[\w./-]*")

#: Discriminator B2 -- built-in glossary packs mirroring a hash-pinned seed.
#:
#: ``src/doctrine/glossary_packs/built-in/<pack-id>.glossary-pack.yaml`` is a
#: field-for-field migration of the read-only seed
#: ``.kittify/glossaries/<pack-id>.yaml`` (the ``{scope.value}.yaml`` layout
#: ``glossary.scope.load_seed_file`` resolves). Two standing gates make the pack
#: text non-editable in BOTH directions: ``test_glossary_pack_parity`` requires
#: every seed-present field to round-trip byte-identically, and
#: ``test_glossary_pack_no_regression`` pins the seed's sha256 under C-003 ("the
#: seed is READ, never modified"). A stale doctrine path quoted inside that prose
#: is therefore a *frozen historical inaccuracy*, not a live defect: it cannot be
#: corrected on the pack side without breaking parity, nor on the seed side
#: without breaking the C-003 content pin. Dead path, frozen artefact -- different
#: problems, and a dead-path sweep owns only the first.
#:
#: The exclusion is derived, not declared: it fires only for a token that is
#: present VERBATIM in the seed the pack mirrors. It is also self-retiring --
#: when Mission C retires the seed, the token stops resolving and every pack site
#: reverts to a violation with no edit here.
# Relocated to the flattened pack root (mission relocate-builtin-doctrine-packs-01KYT87F):
# the built-in glossary packs now live at ``packs/built-in/glossary_packs/`` (the
# inner ``built-in`` segment is dropped). Matched as a parent-path substring.
_GLOSSARY_PACK_SUBTREE = "built-in/glossary_packs"
_GLOSSARY_PACK_SUFFIX = ".glossary-pack.yaml"
_GLOSSARY_SEED_DIR = _REPO_ROOT / ".kittify" / "glossaries"


@lru_cache(maxsize=8)
def _frozen_seed_text(seed_path: Path) -> str:
    return seed_path.read_text(encoding="utf-8")


def _frozen_seed_for_pack(path: Path) -> Path | None:
    """The hash-pinned migration seed *path* mirrors, or ``None``.

    Anchored at ``_REPO_ROOT`` rather than the scan root on purpose: the seed
    lives under ``.kittify/``, outside every root gate B is pointed at.
    """
    if not path.name.endswith(_GLOSSARY_PACK_SUFFIX):
        return None
    if _GLOSSARY_PACK_SUBTREE not in path.parent.as_posix():
        return None
    pack_id = path.name[: -len(_GLOSSARY_PACK_SUFFIX)]
    seed = _GLOSSARY_SEED_DIR / f"{pack_id.replace('-', '_')}.yaml"
    return seed if seed.is_file() else None


def _full_path_token(line: str, naive: re.Match[str]) -> str | None:
    """The whole path literal enclosing a bare ``shipped/`` match."""
    for hit in _SHIPPED_FULL_PATH_RE.finditer(line):
        if hit.start() <= naive.start() and naive.end() <= hit.end():
            return hit.group(0)
    return None


@dataclass(frozen=True)
class ShippedLayerScan:
    """Gate B result, split by discriminator."""

    violations: tuple[Site, ...]
    prose: tuple[Site, ...]
    frozen_mirrors: tuple[Site, ...]

    @property
    def naive(self) -> tuple[Site, ...]:
        return tuple(sorted(self.violations + self.prose + self.frozen_mirrors))


def scan_shipped_pack_paths(root: Path) -> ShippedLayerScan:
    """Classify every ``shipped/`` occurrence under *root*."""
    violations: list[Site] = []
    prose: list[Site] = []
    frozen_mirrors: list[Site] = []
    for path, lines in _text_files(root):
        for number, line in enumerate(lines, start=1):
            for match in _SHIPPED_NAIVE_RE.finditer(line):
                start = match.start()
                window = line[:start]
                as_path = any(hit.end() == match.end() for hit in _SHIPPED_PATH_RE.finditer(line))
                site = Site(_rel(path, root), number, (window[-24:] + match.group(0)).strip())
                if not as_path:
                    prose.append(site)
                    continue
                token = _full_path_token(line, match)
                seed = _frozen_seed_for_pack(path)
                if token is not None and seed is not None and token in _frozen_seed_text(seed):
                    # Site.text is the full path token here (not the prose window
                    # the other buckets carry): it is what B2 actually matched on,
                    # so it is stable identity for the effect-set pin below.
                    frozen_mirrors.append(Site(_rel(path, root), number, token))
                    continue
                violations.append(site)
    return ShippedLayerScan(
        violations=tuple(sorted(violations)),
        prose=tuple(sorted(prose)),
        frozen_mirrors=tuple(sorted(frozen_mirrors)),
    )


# ---------------------------------------------------------------------------
# Two-tree shipped scans (mission relocate-builtin-doctrine-packs-01KYT87F)
# ---------------------------------------------------------------------------
# The shipped assertions walk BOTH ``src/`` (consuming code) and
# ``packs/built-in/`` (relocated authored pack content), because the dead-path
# defect class now spans the two. The mutation-proof tests keep calling the
# single-root scanners against a ``tmp_path`` fixture and are untouched by this.
#
# NOTE (#3036): this is a scope widening, not a re-framing. #3036 tracks the
# fuller rework of this suite (canonical pack-root discovery in place of a
# hard-coded root pair); that reframing is deliberately NOT attempted here.


def scan_graph_monolith_shipped() -> GraphMonolithScan:
    """Gate A over the shipped trees: ``src/`` merged with ``packs/built-in/``."""
    src, pack = (
        scan_graph_monolith_paths(_SRC_ROOT),
        scan_graph_monolith_paths(_PACKS_ROOT),
    )
    return GraphMonolithScan(
        violations=tuple(sorted(src.violations + pack.violations)),
        project_tier=tuple(sorted(src.project_tier + pack.project_tier)),
        forbidding_mentions=tuple(sorted(src.forbidding_mentions + pack.forbidding_mentions)),
    )


def scan_shipped_pack_shipped() -> ShippedLayerScan:
    """Gate B over the shipped trees: ``src/`` merged with ``packs/built-in/``."""
    src, pack = (
        scan_shipped_pack_paths(_SRC_ROOT),
        scan_shipped_pack_paths(_PACKS_ROOT),
    )
    return ShippedLayerScan(
        violations=tuple(sorted(src.violations + pack.violations)),
        prose=tuple(sorted(src.prose + pack.prose)),
        frozen_mirrors=tuple(sorted(src.frozen_mirrors + pack.frozen_mirrors)),
    )


# ---------------------------------------------------------------------------
# Gate A assertions
# ---------------------------------------------------------------------------


def test_no_source_site_names_the_dead_drg_monolith() -> None:
    """FR-008 / SC-007: nothing under the shipped trees (``src/`` +
    ``packs/built-in/``) points at the sharded-away ``src/doctrine/graph.yaml``
    or at the relocated-away ``src/doctrine/<kind>.graph.yaml`` fragments."""
    scan = scan_graph_monolith_shipped()
    assert not scan.violations, (
        "These sites name a doctrine-directory graph file that no longer exists (#2680 sharded the "
        "monolith; the fragments then moved to the pack root). "
        "Point them at the per-kind fragment (packs/built-in/<kind>.graph.yaml):\n" + _render(scan.violations)
    )


def test_the_migration_hint_names_a_fragment_that_exists() -> None:
    """FR-008: the hint an operator is handed must be followable -- the file
    it names must be on disk for every artifact kind that can raise it."""
    from charter.offering.shared.errors import build_migration_hint

    kinds = (
        "directive",
        "tactic",
        "procedure",
        "paradigm",
        "styleguide",
        "toolguide",
        "agent_profile",
    )
    unfollowable: list[str] = []
    for kind in kinds:
        hint = build_migration_hint(forbidden_field="tactic_refs", source_kind=kind, source_id="example")
        named = [token for token in hint.split() if token.endswith(".graph.yaml")]
        if len(named) != 1 or not (_REPO_ROOT / named[0]).is_file():
            unfollowable.append(f"{kind}: {hint}")
            continue
        # Existence alone is too weak: every per-kind fragment exists, so a hint
        # hard-coded to any one of them passes an is_file() check for all seven.
        # Review proved it by replacing the interpolation with a constant
        # "tactic.graph.yaml" -- 61 tests stayed green while an operator holding
        # a directive-sourced edge was sent to the tactic shard. Edges shard by
        # SOURCE kind (extractor._partition_by_kind), verified against all 774
        # shipped edges, so the named fragment must be the source kind's own.
        # Relocated (mission relocate-builtin-doctrine-packs-01KYT87F): the shipped
        # per-kind fragments moved from ``src/doctrine/`` to the ``packs/built-in/``
        # pack root, so the followable hint names the fragment there.
        expected = f"packs/built-in/{kind}.graph.yaml"
        if named[0] != expected:
            unfollowable.append(f"{kind}: names {named[0]}, but its edges shard into {expected}")
    assert not unfollowable, "Migration hints that do not name the fragment the operator must open:\n" + "\n".join(unfollowable)


def test_project_tier_graph_path_would_false_red_without_its_discriminator() -> None:
    """NFR-003 proof for discriminator A1, with its effect set pinned."""
    scan = scan_graph_monolith_shipped()
    assert scan.project_tier, (
        "A1 excludes nothing, so it cannot be proven. Either the live project-tier path is gone (delete A1) or the pattern stopped matching it."
    )
    naive_paths = {site.path for site in scan.naive}
    kept_paths = {site.path for site in scan.violations} | {site.path for site in scan.forbidding_mentions}
    excluded = sorted(naive_paths - kept_paths)
    assert excluded == [
        # Direct-authored artifact registration writes the live project overlay;
        # this is the same project-tier path, not a retired built-in monolith.
        "src/charter/activation/project_registration.py",
        "src/charter/activation/synthesizer/manifest.py",
        "src/charter/activation/synthesizer/project_drg.py",
        "src/charter/offering/drg/merge.py",
        "src/glossary/drg_builder.py",
        "src/specify_cli/charter_runtime/freshness/computer.py",
        "src/specify_cli/state/contract.py",
    ], f"A1's effect set moved -- widening it needs a reason, not a regex tweak: {excluded}"


def test_forbidding_mention_would_false_red_without_its_discriminator(tmp_path: Path) -> None:
    """NFR-003 proof for discriminator A2, redriven from a planted ``tmp_path``
    fixture rather than the live shipped artifact (mission
    ``doctrine-consumer-surface-missions-extraction-01KZ6G6H`` WP02, FR-002).

    Issue #3036 tracked a real gate/rule contradiction: this proof used to pin
    the exact live effect set of ``doctrine-daphne.agent.yaml``'s own
    avoidance-boundary mention, which meant shipped doctrine content could
    never drop that repo-local reference without turning this proof
    vacuous -- exactly the coupling the "Shippable doctrine" rule forbids.
    Issue #3036's own tracker comment (2026-07-28) explicitly rejects
    loosening the assertion to tolerate an empty effect set as the fix
    ("that remedy would make the problem worse"); the correct shape is to
    decouple *what proves the discriminator is real* from *what the live
    artifact carries*. This fixture plays the role the live artifact used to:
    the discriminator's effect-set pin still runs, and widening it is still a
    visible diff here, while ``doctrine-daphne.agent.yaml`` itself is now free
    to be repo-agnostic.

    (path, matched text) rather than a path set plus a count: a second
    forbidding mention in the SAME file collapses out of a path set, and a
    different mention swapped in for this one keeps any count unchanged.
    ``Site.text`` is gate A's raw ``match.group(0)`` -- the path itself, so it
    is stable identity rather than surrounding prose.
    """
    fixture = tmp_path / "synthetic-forbidding-mention.agent.yaml"
    fixture.write_text(
        "specialization:\n  avoidance-boundary: >\n    Does not name src/doctrine/graph.yaml as guidance to follow.\n",
        encoding="utf-8",
    )
    scan = scan_graph_monolith_paths(tmp_path)
    assert scan.forbidding_mentions, (
        "A2 excludes nothing, so it cannot be proven. Either the fixture's forbidding mention is gone or the pattern stopped matching it."
    )
    excluded = sorted((site.path, site.text) for site in scan.forbidding_mentions)
    assert excluded == [
        ("synthetic-forbidding-mention.agent.yaml", "src/doctrine/graph.yaml"),
    ], f"A2's effect set moved -- widening it needs a reason: {_render(scan.forbidding_mentions)}"


def test_gate_a_rejects_a_planted_violation(tmp_path: Path) -> None:
    """Self-mutation: the gate must catch the regression it exists to catch."""
    planted = tmp_path / "guidance.md"
    planted.write_text("Add the edge to src/doctrine/graph.yaml.\n", encoding="utf-8")
    scan = scan_graph_monolith_paths(tmp_path)
    assert [site.text for site in scan.violations] == ["src/doctrine/graph.yaml"]


def test_gate_a_rejects_a_planted_dead_fragment_path(tmp_path: Path) -> None:
    """Self-mutation (#2715): a fragment path under the retired
    ``src/doctrine/`` home is dead in every spelling -- placeholder, glob, or a
    concrete kind -- while the live pack-root fragment path is not flagged.

    Scans a dedicated subroot: ``_text_files`` caches by root path, and this
    test's ``tmp_path`` shares its 30-character truncated prefix with
    ``test_gate_a_rejects_a_planted_violation``'s, so a bare ``tmp_path`` can be
    handed that test's cached read (see ``_dead_path_scan._text_files``)."""
    root = tmp_path / "dead-fragment"
    root.mkdir()
    planted = root / "guidance.yaml"
    planted.write_text(
        "a: the per-kind src/doctrine/<kind>.graph.yaml fragments\n"
        "b: every src/doctrine/*.graph.yaml fragment\n"
        "c: src/doctrine/tactic.graph.yaml\n"
        "d: the per-kind packs/built-in/<kind>.graph.yaml fragments\n",
        encoding="utf-8",
    )
    scan = scan_graph_monolith_paths(root)
    assert [(site.line, site.text) for site in scan.violations] == [
        (1, "src/doctrine/<kind>.graph.yaml"),
        (2, "src/doctrine/*.graph.yaml"),
        (3, "src/doctrine/tactic.graph.yaml"),
    ]
    assert not scan.project_tier
    assert not scan.forbidding_mentions


def test_gate_a_discriminators_do_not_swallow_a_planted_violation(tmp_path: Path) -> None:
    """A1/A2 must not become blanket escapes: a dead path inside an agent
    profile but *outside* its avoidance boundary is still a violation."""
    profile = tmp_path / "example.agent.yaml"
    profile.write_text(
        "specialization:\n"
        "  primary-focus: >\n"
        "    Edit src/doctrine/graph.yaml to add the edge.\n"
        "  avoidance-boundary: >\n"
        "    Does not tell an operator to edit src/doctrine/graph.yaml.\n",
        encoding="utf-8",
    )
    scan = scan_graph_monolith_paths(tmp_path)
    assert [site.line for site in scan.violations] == [3]
    assert [site.line for site in scan.forbidding_mentions] == [5]


# ---------------------------------------------------------------------------
# Gate B assertions
# ---------------------------------------------------------------------------


def test_no_source_site_references_the_shipped_pack_layer() -> None:
    """FR-009 / SC-008: ``<kind>/shipped/`` has never existed; the shipped
    pack layer is ``<kind>/built-in/``."""
    scan = scan_shipped_pack_shipped()
    assert not scan.violations, "These sites reference a `shipped/` pack layer that is not on disk. The shipped pack layer is `<kind>/built-in/`:\n" + _render(
        scan.violations
    )


def test_shipped_prose_would_false_red_without_the_path_shape_discriminator() -> None:
    """NFR-003 proof for discriminator B1, with its effect set pinned."""
    scan = scan_shipped_pack_shipped()
    # A list, not a set: duplicates survive, so a second prose match appearing in
    # any of these three files goes red instead of collapsing into the same path.
    # Unlike gate A, ``Site.text`` here is a 24-char prose window built for the
    # failure message, so it is not part of the pinned identity.
    #
    # 2026-07-29 (PR #3070 landing pass, WP05 doctrine-delivery-reachability):
    # widened by one entry for `src/specify_cli/cli/commands/_doctrine_asset.py`
    # — its module docstring reads "...resolve shipped/overlay doctrine assets",
    # genuine English prose (no `<segment>/` immediately precedes `shipped/`),
    # not a `<kind>/shipped/` pack-layer path reference.
    excluded = sorted(site.path for site in scan.prose)
    assert excluded == [
        "src/charter/offering/model_task_routing/catalog/model-to-task_type.yaml",
        "src/runtime/next/_internal_runtime/planner.py",
        "src/specify_cli/cli/commands/_doctrine_asset.py",
    ], f"B1's effect set moved -- widening it needs a reason: {_render(scan.prose)}"


def test_frozen_seed_mirror_would_false_red_without_its_discriminator() -> None:
    """NFR-003 proof for discriminator B2, with its effect set pinned.

    A list of ``(path, token)`` pairs, duplicates intact: the pack quotes the
    same dead path twice (once in the term's ``definition`` prose, once in its
    ``see_also`` entry) and both must stay excluded. Collapsing to a set would
    let one of the two silently become a violation.
    """
    scan = scan_shipped_pack_shipped()
    excluded = sorted((site.path, site.text) for site in scan.frozen_mirrors)
    # Relocated (mission relocate-builtin-doctrine-packs-01KYT87F): the built-in
    # glossary pack moved to the flattened ``packs/built-in/glossary_packs/`` home.
    pack = "packs/built-in/glossary_packs/spec-kitty-core.glossary-pack.yaml"
    dead_path = "src/doctrine/tactics/shipped/secure-regex-catastrophic-backtracking.tactic.yaml"
    assert excluded == [(pack, dead_path), (pack, dead_path)], (
        "B2's effect set moved. It may only exclude a pack site whose dead path "
        "is verbatim in the hash-pinned seed it mirrors -- widening it needs a "
        f"reason, not a regex tweak: {_render(scan.frozen_mirrors)}"
    )


def test_frozen_seed_mirror_discriminator_is_anchored_in_the_live_seed() -> None:
    """B2 is only sound while the seed really does carry the dead path.

    Reads the seed directly rather than trusting the scan: if the seed were
    edited to "fix" the path (the C-003 violation this discriminator exists to
    make unnecessary), B2 would go quietly inert and the pack sites would flip
    to violations with no explanation. This fails first, and says why.
    """
    seed = _GLOSSARY_SEED_DIR / "spec_kitty_core.yaml"
    assert seed.is_file(), f"the mirrored migration seed is missing: {seed}"
    dead_path = "src/doctrine/tactics/shipped/secure-regex-catastrophic-backtracking.tactic.yaml"
    assert dead_path in _frozen_seed_text(seed), (
        f"the seed no longer carries {dead_path!r}. The seed is READ, never "
        "modified (C-003, pinned by test_glossary_pack_no_regression) -- if it "
        "was legitimately retired, drop discriminator B2 and fix the pack."
    )


def test_gate_b_frozen_mirror_discriminator_requires_the_seed_to_carry_the_path(
    tmp_path: Path,
) -> None:
    """B2 must not degrade into a subtree escape for the glossary-pack dir.

    Three planted sites in the pack subtree, one excluded: only the path the
    real seed actually carries. A sibling dead path under the same
    ``tactics/shipped/`` segment, and a pack whose id maps to no seed at all,
    both stay violations.
    """
    # Flattened pack home (mission relocate-builtin-doctrine-packs-01KYT87F):
    # ``packs/built-in/glossary_packs/`` (the inner ``built-in`` is dropped).
    pack_dir = tmp_path / "packs" / "built-in" / "glossary_packs"
    pack_dir.mkdir(parents=True)
    mirrored = "src/doctrine/tactics/shipped/secure-regex-catastrophic-backtracking.tactic.yaml"
    (pack_dir / "spec-kitty-core.glossary-pack.yaml").write_text(
        f"a: {mirrored}\nb: src/doctrine/tactics/shipped/invented.tactic.yaml\n",
        encoding="utf-8",
    )
    (pack_dir / "no-such-seed.glossary-pack.yaml").write_text(f"a: {mirrored}\n", encoding="utf-8")
    scan = scan_shipped_pack_paths(tmp_path)
    assert [(site.path, site.line) for site in scan.frozen_mirrors] == [("packs/built-in/glossary_packs/spec-kitty-core.glossary-pack.yaml", 1)]
    assert [(site.path, site.line) for site in scan.violations] == [
        ("packs/built-in/glossary_packs/no-such-seed.glossary-pack.yaml", 1),
        ("packs/built-in/glossary_packs/spec-kitty-core.glossary-pack.yaml", 2),
    ]


def test_gate_b_rejects_a_planted_violation(tmp_path: Path) -> None:
    """Self-mutation: a planted pack-layer path must be flagged, and the
    adjacent prose form must not be."""
    planted = tmp_path / "guide.md"
    planted.write_text(
        "Artifacts live in src/doctrine/tactics/shipped/.\nThe shipped/packaged catalogue is generated.\n",
        encoding="utf-8",
    )
    scan = scan_shipped_pack_paths(tmp_path)
    assert [site.line for site in scan.violations] == [1]
    assert [site.line for site in scan.prose] == [2]


def test_gate_b_flags_the_placeholder_pack_layer_form(tmp_path: Path) -> None:
    """``<kind>/shipped/`` is the operator-facing form and must not slip
    through on account of its angle brackets."""
    planted = tmp_path / "guide.md"
    planted.write_text("Shipped artifacts: src/doctrine/<kind>/shipped/\n", encoding="utf-8")
    scan = scan_shipped_pack_paths(tmp_path)
    assert len(scan.violations) == 1
