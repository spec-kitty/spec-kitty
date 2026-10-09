"""Architectural gate: relative cross-links in built-in doctrine markdown
must resolve on disk.

Narrowed (mission ``doctrine-consumer-surface-missions-extraction-01KZ6G6H``
WP01, FR-001) to Gate C alone -- the only ``_DOCTRINE_ROOT``-scoped gate of
the three this file used to carry. Gate A and Gate B (both ``src/``-wide, not
doctrine-scoped) moved to ``test_no_dead_cli_paths.py``; Gate D
(``docs/``-scoped) moved to ``test_dead_builtin_doc_paths.py``. This file
keeps its original name because, after the split, the name means what it
says: doctrine-content-scoped only.

Originally: mission ``doctrine-silence-guards-01KYFV7Q`` WP07 (FR-008, FR-009,
NFR-003).

``C`` -- relative cross-links in built-in doctrine markdown.

Gate C carries **discriminators**: semantic exclusions that keep it from
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
from pathlib import Path

import pytest

from tests.architectural._dead_path_scan import (
    _DOCTRINE_ROOT,
    _PACKS_ROOT,
    Site,
    _read_lines,
    _rel,
    _render,
)

#: Without this the CI shard that selects ``-m architectural`` collects none of
#: these tests, and the gate silently never runs.
pytestmark = [pytest.mark.architectural, pytest.mark.git_repo]

#: Mission-tier templates are copied into a mission directory before anyone
#: reads them, so their sibling links resolve at the destination and never at
#: the source. Gate C scopes them out wholesale rather than allowlisting each
#: link; the exclusion is asserted by ``test_cross_link_scope_is_pinned``.
_DEPLOYMENT_RELATIVE_SUBTREE = "missions"

# ---------------------------------------------------------------------------
# Gate C -- relative cross-links in built-in doctrine markdown
# ---------------------------------------------------------------------------

_FENCE_RE = re.compile(r"^\s*(?:```|~~~)")
_INLINE_CODE_RE = re.compile(r"`[^`]*`")
_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "#", "<")
#: Discriminator C2: an unfilled template slot is not a broken link.
_PLACEHOLDER_RE = re.compile(r"[{}]")


@dataclass(frozen=True)
class CrossLinkScan:
    """Gate C result, split by discriminator."""

    unresolved: tuple[Site, ...]
    code_examples: tuple[Site, ...]
    placeholders: tuple[Site, ...]
    boundary_escapes: tuple[Site, ...]


def _link_targets(line: str) -> list[str]:
    return [match.group(1).strip() for match in _LINK_RE.finditer(line)]


def _resolves(md_path: Path, target: str) -> bool:
    bare = target.split("#", 1)[0].strip()
    if not bare:
        return True
    return (md_path.parent / bare).exists()


def _escapes_boundary(
    md_path: Path,
    target: str,
    root: Path,
    boundary_roots: tuple[Path, ...] | None = None,
) -> bool:
    """True when *target*, resolved relative to *md_path*, would land outside
    **every** root in *boundary_roots* -- the in-boundary set Gate C is
    actually scoped to. Defaults to ``(root,)`` so callers that scan a single
    tree in isolation (the four ``tmp_path`` unit tests below) keep
    single-root semantics unchanged.

    Discriminator C3 (US2-AS3, mission
    ``doctrine-consumer-surface-missions-extraction-01KZ6G6H`` WP02, FR-002).
    Requiring such a link to resolve on THIS repo's own disk forever is the
    same coupling shape #3036 tracks for discriminator A2: a link that
    legitimately cross-references content outside its own package boundary
    (the project's ``docs/`` glossary, ...) is not a dead-path defect, but the
    package cannot verify or guarantee that target's presence once it ships
    on its own -- so Gate C stops trying, rather than perpetually depending on
    the surrounding monorepo checkout to keep the link alive.

    Crucially, this is a per-link *union* test, not a per-root test: a link
    from ``src/charter/offering/**`` into ``packs/built-in/**`` (or the reverse) is
    NOT a boundary escape when both trees are members of *boundary_roots* --
    ``scan_doctrine_cross_links_shipped()`` treats both shipped roots as one
    corpus, so the escape/no-escape verdict must agree with that model
    regardless of which single root a link happened to be scanned under.
    """
    boundary = boundary_roots if boundary_roots is not None else (root,)
    bare = target.split("#", 1)[0].strip()
    if not bare:
        return False
    resolved = (md_path.parent / bare).resolve()
    for boundary_root in boundary:
        try:
            resolved.relative_to(boundary_root.resolve())
            return False
        except ValueError:
            continue
    return True


def _classify_link(
    md_path: Path,
    number: int,
    target: str,
    root: Path,
    boundary_roots: tuple[Path, ...] | None = None,
) -> tuple[str, Site] | None:
    if target.startswith(_EXTERNAL_PREFIXES):
        return None
    site = Site(_rel(md_path, root), number, target)
    if _PLACEHOLDER_RE.search(target):
        return ("placeholder", site)
    if _escapes_boundary(md_path, target, root, boundary_roots):
        return ("boundary_escape", site)
    if _resolves(md_path, target):
        return None
    return ("unresolved", site)


def scan_doctrine_cross_links(
    root: Path, boundary_roots: tuple[Path, ...] | None = None
) -> CrossLinkScan:
    """Resolve every relative markdown cross-link under *root*.

    Discriminator C1 drops links that live inside a fenced code block or an
    inline code span: those are *illustrations of link syntax*, not
    navigation. Discriminator C2 drops targets carrying a ``{placeholder}``.
    Discriminator C3 drops targets that resolve outside every root in
    *boundary_roots* (defaulting to ``(root,)`` -- see ``_escapes_boundary``)
    -- a legitimate cross-reference to content outside the shipped package
    boundary, not a dead path within it.
    """
    unresolved: list[Site] = []
    code_examples: list[Site] = []
    placeholders: list[Site] = []
    boundary_escapes: list[Site] = []
    skipped = root / _DEPLOYMENT_RELATIVE_SUBTREE
    for md_path in sorted(root.rglob("*.md")):
        if skipped in md_path.parents:
            continue
        in_fence = False
        for number, line in enumerate(_read_lines(md_path), start=1):
            if _FENCE_RE.match(line):
                in_fence = not in_fence
                continue
            raw_targets = _link_targets(line)
            if in_fence:
                live_targets: list[str] = []
            else:
                live_targets = _link_targets(_INLINE_CODE_RE.sub("", line))
            for target in raw_targets:
                if target in live_targets:
                    continue
                if target.startswith(_EXTERNAL_PREFIXES):
                    continue
                code_examples.append(Site(_rel(md_path, root), number, target))
            for target in live_targets:
                verdict = _classify_link(md_path, number, target, root, boundary_roots)
                if verdict is None:
                    continue
                bucket, site = verdict
                if bucket == "placeholder":
                    placeholders.append(site)
                elif bucket == "boundary_escape":
                    boundary_escapes.append(site)
                else:
                    unresolved.append(site)
    return CrossLinkScan(
        unresolved=tuple(sorted(unresolved)),
        code_examples=tuple(sorted(code_examples)),
        placeholders=tuple(sorted(placeholders)),
        boundary_escapes=tuple(sorted(boundary_escapes)),
    )


def scan_doctrine_cross_links_shipped() -> CrossLinkScan:
    """Gate C over the shipped doctrine markdown: ``src/charter/offering/`` merged with
    ``packs/built-in/``.

    The in-boundary set for *both* sub-scans is the union of both shipped
    roots (mission ``doctrine-consumer-surface-missions-extraction-01KZ6G6H``
    WP02 cycle-2, B1): a link is a ``boundary_escape`` only when it lands
    outside every shipped root, not merely outside whichever single root it
    was scanned under. Without this, a link crossing ``src/charter/offering/`` <->
    ``packs/built-in/`` escaped the boundary of its own scan root even though
    the two scans are merged into one corpus two lines below -- silently
    exempting a genuinely broken cross-tree link from resolution checking
    instead of surfacing it as ``unresolved``.
    """
    boundary_roots = (_DOCTRINE_ROOT, _PACKS_ROOT)
    src, pack = (
        scan_doctrine_cross_links(_DOCTRINE_ROOT, boundary_roots),
        scan_doctrine_cross_links(_PACKS_ROOT, boundary_roots),
    )
    return CrossLinkScan(
        unresolved=tuple(sorted(src.unresolved + pack.unresolved)),
        code_examples=tuple(sorted(src.code_examples + pack.code_examples)),
        placeholders=tuple(sorted(src.placeholders + pack.placeholders)),
        boundary_escapes=tuple(sorted(src.boundary_escapes + pack.boundary_escapes)),
    )


# ---------------------------------------------------------------------------
# Gate C assertions
# ---------------------------------------------------------------------------


def test_every_built_in_doctrine_cross_link_resolves() -> None:
    """SC-008: relative cross-links in built-in doctrine markdown resolve."""
    scan = scan_doctrine_cross_links_shipped()
    assert not scan.unresolved, "Broken relative cross-links in doctrine markdown:\n" + _render(scan.unresolved)


def test_code_example_links_would_false_red_without_their_discriminator() -> None:
    """NFR-003 proof for discriminator C1, with its effect set pinned."""
    scan = scan_doctrine_cross_links_shipped()
    excluded = sorted({(site.path, site.text) for site in scan.code_examples})
    # Relocated (mission relocate-builtin-doctrine-packs-01KYT87F): the toolguide
    # markdown moved to the flattened ``packs/built-in/toolguides/`` home; the
    # SKILL.md stays under ``src/charter/offering/skills/`` (skills did not move).
    # ``spk-practice-show-me`` carries byte-pinned portable copies of both
    # guides, so their fenced link examples intentionally appear twice.
    assert excluded == [
        ("packs/built-in/toolguides/MERMAID_DIAGRAMMING.md", "diagram.svg"),
        ("packs/built-in/toolguides/PLANTUML_DIAGRAMMING.md", "diagram.svg"),
        ("src/charter/offering/skills/spk-charter-spdd-reasons/references/reasons-canvas-workflow.md", "../spec.md#x"),
        (
            "src/charter/offering/skills/spk-practice-show-me/assets/MERMAID_DIAGRAMMING.md",
            "diagram.svg",
        ),
        (
            "src/charter/offering/skills/spk-practice-show-me/assets/PLANTUML_DIAGRAMMING.md",
            "diagram.svg",
        ),
    ], f"C1's effect set moved: {excluded}"


def test_placeholder_links_would_false_red_without_their_discriminator() -> None:
    """NFR-003 proof for discriminator C2, with its effect set pinned."""
    scan = scan_doctrine_cross_links_shipped()
    excluded = sorted({(site.path, site.text) for site in scan.placeholders})
    assert excluded == [
        ("src/charter/offering/templates/guides/HOW-TO.template.md", "../explanation/{topic}.md"),
        ("src/charter/offering/templates/guides/HOW-TO.template.md", "../reference/{file}.md"),
        ("src/charter/offering/templates/guides/HOW-TO.template.md", "./{related-guide}.md"),
    ], f"C2's effect set moved: {excluded}"


def test_boundary_escaping_link_would_false_red_without_its_discriminator(tmp_path: Path) -> None:
    """NFR-003 proof for discriminator C3, driven from a planted ``tmp_path``
    fixture from the start (mission
    ``doctrine-consumer-surface-missions-extraction-01KZ6G6H`` WP02, FR-002,
    US2-AS3) rather than a live corpus pin.

    Unlike A2 (see the sibling proof in ``test_no_dead_cli_paths.py``), C3 has
    no pre-existing live-pinned assertion to redrive: it is added here to
    close the same coupling shape before it becomes a live defect. A doctrine
    markdown file legitimately cross-referencing something outside its own
    package boundary (the project's ``docs/`` glossary, the sibling doctrine
    tree, ...) must not be forced to resolve on THIS repo's disk forever --
    once ``packs/built-in`` or ``src/doctrine`` ships on its own, whatever
    lives outside its boundary is not guaranteed to be checked out alongside
    it.
    """
    root = tmp_path / "doctrine_root"
    root.mkdir()
    (root / "page.md").write_text(
        "See [glossary](../../docs/context/charter.md#term).\n",
        encoding="utf-8",
    )
    scan = scan_doctrine_cross_links(root)
    assert scan.boundary_escapes, (
        "C3 excludes nothing, so it cannot be proven. Either the escaping-link "
        "case no longer applies (delete C3) or the pattern stopped matching it."
    )
    assert [site.text for site in scan.boundary_escapes] == [
        "../../docs/context/charter.md#term"
    ], f"C3's effect set moved -- widening it needs a reason: {_render(scan.boundary_escapes)}"
    assert not scan.unresolved, "A legitimately escaping link must not become a false unresolved-link red."


def test_gate_c_boundary_discriminator_does_not_swallow_an_in_boundary_violation(tmp_path: Path) -> None:
    """C3 must not become a blanket escape: a broken link that stays inside
    *root* is still a violation, and a resolvable sibling stays resolved,
    alongside a genuinely escaping link in the same file."""
    root = tmp_path / "doctrine_root"
    root.mkdir()
    (root / "sibling.md").write_text("ok\n", encoding="utf-8")
    planted = root / "page.md"
    planted.write_text(
        "See [outside](../../docs/context/charter.md#term).\n"
        "See [gone](./missing.md).\n"
        "See [here](./sibling.md).\n",
        encoding="utf-8",
    )
    scan = scan_doctrine_cross_links(root)
    assert [site.text for site in scan.boundary_escapes] == ["../../docs/context/charter.md#term"]
    assert [site.text for site in scan.unresolved] == ["./missing.md"]


def test_gate_c_boundary_discriminator_treats_sibling_shipped_roots_as_in_boundary(
    tmp_path: Path,
) -> None:
    """B1 regression (mission ``doctrine-consumer-surface-missions-extraction-01KZ6G6H``
    WP02 cycle 2): the shipped scan's in-boundary set is the *union* of both
    shipped roots, not each root scanned in isolation.

    ``test_gate_c_boundary_discriminator_does_not_swallow_an_in_boundary_violation``
    above only plants a broken link inside a *single* root, which is why the
    sibling-tree gap survived cycle 1: a link from one shipped root into the
    other escaped the boundary of whichever root it was scanned under, even
    though ``scan_doctrine_cross_links_shipped()`` merges both roots into one
    corpus. This test builds two sibling roots (mimicking ``src/doctrine`` and
    ``packs/built-in``) and plants three links in root A: one to a *real* file
    in root B (must resolve -- neither ``boundary_escape`` nor
    ``unresolved``), one to a *missing* file in root B (must surface as
    ``unresolved``, not be exempted as a ``boundary_escape``), and one to a
    file genuinely outside both roots (must stay a ``boundary_escape``).
    """
    root_a = tmp_path / "root_a"
    root_b = tmp_path / "root_b"
    root_a.mkdir()
    root_b.mkdir()
    (root_b / "real.md").write_text("ok\n", encoding="utf-8")
    (tmp_path / "outside.md").write_text("ok\n", encoding="utf-8")
    (root_a / "page.md").write_text(
        "See [real sibling](../root_b/real.md).\n"
        "See [broken sibling](../root_b/missing.md).\n"
        "See [truly outside](../outside.md).\n",
        encoding="utf-8",
    )
    scan = scan_doctrine_cross_links(root_a, boundary_roots=(root_a, root_b))
    assert [site.text for site in scan.unresolved] == ["../root_b/missing.md"], (
        "A broken link into a sibling SHIPPED root must surface as unresolved -- "
        "it must not be exempted as a boundary_escape just because it was scanned "
        "under a different single root."
    )
    assert [site.text for site in scan.boundary_escapes] == ["../outside.md"], (
        "A link genuinely outside every shipped root must still escape the boundary."
    )


def test_boundary_escape_live_count_has_a_floor() -> None:
    """C3's live effect bucket, unlike C1 and C2's, is not pinned by an exact
    site list -- the reviewer flagged this gap in WP02 cycle 1 (mission
    ``doctrine-consumer-surface-missions-extraction-01KZ6G6H``): C1 and C2 pin
    their exact live excluded sites, but C3 pins only its fixture, leaving its
    live effect invisible.

    Why a count and not the sites: pinning the exact live paths would
    reintroduce the same repo-local coupling FR-002 exists to remove -- just
    moved from the resolution side to the exclusion side. A bound keeps the
    AS3 exemption (US2-AS3) intact for ordinary content churn while still
    failing loudly if ``_escapes_boundary`` is ever narrowed/refactored until
    this bucket collapses toward zero -- which would silently change Gate C's
    only live check on those sites (``relative_link_fixer.py`` scans
    ``docs/`` only, not doctrine markdown). A future maintainer who
    "improves" this into a site-list pin undoes that fix -- don't.

    This floor only catches *collapse*, not widening: widening is instead
    caught by ``test_gate_c_boundary_discriminator_does_not_swallow_an_in_boundary_violation``
    and ``test_gate_c_boundary_discriminator_treats_sibling_shipped_roots_as_in_boundary``
    above, which each plant a genuinely in-boundary violation and assert it is
    NOT exempted -- a widened discriminator would swallow those and red them
    directly, independent of this count.

    Measured 2026-08-04 (cycle 1, before the B1 fix): 33 live
    ``boundary_escapes`` sites -- 15 of which were ``src/doctrine`` <->
    ``packs/built-in`` sibling-tree links wrongly exempted by the
    single-root bug B1 fixed (cycle 2). Re-measured 2026-08-04 (cycle 2,
    after the fix): 18 -- exactly the ``docs/``-pointing set, since the 15
    sibling-tree links are now in-boundary (the union of both shipped roots)
    and resolution-checked like any other link, not exempted. Pinned at
    ``>= 12``: comfortably below 18 so ordinary content churn does not red
    this, but high enough that a collapse toward zero -- a wholesale
    silencing move -- still fails.
    """
    scan = scan_doctrine_cross_links_shipped()
    assert len(scan.boundary_escapes) >= 12, (
        f"C3's live boundary_escapes count fell to {len(scan.boundary_escapes)} from a "
        "measured 18 (post-B1-fix). This bucket is Gate C's only live check on these "
        "sites (relative_link_fixer.py scans docs/ only) -- a collapse toward zero means "
        "_escapes_boundary stopped matching real cross-boundary links, silently "
        "removing coverage rather than exercising the AS3 exemption. If intentional, "
        "say why and re-pin."
    )


def test_cross_link_scope_is_pinned() -> None:
    """The one scope exclusion is the mission-tier template subtree, whose
    links resolve at the mission directory they are copied into.

    Relocated (mission relocate-builtin-doctrine-packs-01KYT87F): Gate C now
    covers BOTH shipped trees, so the in-scope corpus is the union of
    ``src/charter/offering/`` markdown (skills, templates, package READMEs — the
    ``missions`` subtree still lives here and is still excluded) and the
    relocated ``packs/built-in/`` markdown (toolguides, pack READMEs).
    """
    in_scope: set[str] = set()
    for root in (_DOCTRINE_ROOT, _PACKS_ROOT):
        skipped = root / _DEPLOYMENT_RELATIVE_SUBTREE
        in_scope |= {
            _rel(path, root)
            for path in root.rglob("*.md")
            if skipped not in path.parents
        }
    assert _DOCTRINE_ROOT.is_dir() and _PACKS_ROOT.is_dir()
    assert not any(path.startswith("src/charter/offering/missions/") for path in in_scope)
    # Pinned near the live combined count (159 = 141 under src/doctrine + 18 under
    # packs/built-in), not at a token floor. The exclusion is subtree-shaped, so
    # this assertion is the only thing standing between Gate C and a silencing
    # move: at a floor of 20, most files could be relocated under a skipped
    # subtree before anything noticed. Re-measured 2026-07-30 after the built-in
    # pack relocation; the gap to 159 is slack for ordinary authoring, not for a
    # migration.
    assert len(in_scope) >= 150, (
        f"Gate C's in-scope set fell to {len(in_scope)} from a measured 159. "
        "Moving files under a skipped `missions/` subtree removes them from link "
        "checking entirely — if that is intended, say why and re-pin."
    )


def test_gate_c_rejects_a_planted_broken_link(tmp_path: Path) -> None:
    """Self-mutation: a broken link must be flagged, while its code-span and
    placeholder neighbours must not be."""
    (tmp_path / "sibling.md").write_text("ok\n", encoding="utf-8")
    planted = tmp_path / "page.md"
    planted.write_text(
        "See [gone](./missing.md).\nSee [here](./sibling.md).\nWrite `[see spec](../spec.md#x)` like this.\nFill in [topic]({topic}.md).\n",
        encoding="utf-8",
    )
    scan = scan_doctrine_cross_links(tmp_path)
    assert [site.text for site in scan.unresolved] == ["./missing.md"]
    assert [site.text for site in scan.code_examples] == ["../spec.md#x"]
    assert [site.text for site in scan.placeholders] == ["{topic}.md"]


def test_gate_c_fence_discriminator_does_not_swallow_live_links(tmp_path: Path) -> None:
    """A closed fence must restore checking; otherwise one stray fence
    silences the rest of a file."""
    planted = tmp_path / "page.md"
    planted.write_text(
        "```\n[in fence](./nope.md)\n```\n[after fence](./also-nope.md)\n",
        encoding="utf-8",
    )
    scan = scan_doctrine_cross_links(tmp_path)
    assert [site.text for site in scan.unresolved] == ["./also-nope.md"]
    assert [site.text for site in scan.code_examples] == ["./nope.md"]
