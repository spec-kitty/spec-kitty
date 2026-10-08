"""WP01 T001/T006 (mission charter-authority-flip-01M14RB3): standing 3-authority
glossary parity for the governing-term flip ``doctrine`` -> ``charter``.

Extends the seed<->pack join pattern already standing in
``test_glossary_pack_parity.py`` (do NOT delete that file -- it stays the
authority-1<->authority-2 gate) to a **third** authority:
``docs/context/charter.md``, the renamed Markdown context glossary
(``docs/context/charter.offering.md`` before T003's ``git mv``).

Scope (per plan.md Slice 4 / research.md Seam 1): this is NOT a full
104-term Markdown mirror. The three authorities only need to agree on the
**governing term itself** -- the disputed ``doctrine``/``charter`` pair --
because that is the only pair this mission (M1 of
``retire-doctrine-term-01M0JMK9``) actually rewrites. Every other seed
surface keeps whatever (possibly absent) Markdown representation it already
had; asserting full coverage there would test WP02/M2-M6 surfaces this WP
does not own.

Anti-vacuity (squad H1 + B2, non-negotiable):
  - H1: the governing ``doctrine`` surface must be ABSENT from all three
    authorities and ``charter`` must be PRESENT in all three.
  - B2: EXACTLY ONE ``charter`` surface may exist per authority -- a
    careless "rename doctrine -> charter" edit that forgets the
    pre-existing ``charter`` term would silently produce a duplicate
    ``surface: charter`` entry that ``extra="forbid"`` + surface-as-ID
    treats as two distinct terms.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML

from charter.offering.glossary_packs.repository import GlossaryPackRepository

pytestmark = [pytest.mark.architectural, pytest.mark.doctrine]


def _repo_root() -> Path:
    """Resolve the repository root by walking up to a ``.kittify/`` marker."""
    here = Path(__file__).resolve()
    for parent in (here, *here.parents):
        if (parent / ".kittify").is_dir():
            return parent
    raise RuntimeError("Could not locate repo root (no .kittify/ marker found).")


_REPO_ROOT = _repo_root()
_SEED_PATH: Path = _REPO_ROOT / ".kittify" / "glossaries" / "spec_kitty_core.yaml"
_BUILT_IN_DIR: Path = _REPO_ROOT / "packs" / "built-in" / "glossary_packs"
_PACK_ID = "spec-kitty-core"
_RETIRED_GLOSSARY_MD_PATH: Path = _REPO_ROOT / "docs" / "context" / "charter.offering.md"
_CHARTER_MD_PATH: Path = _REPO_ROOT / "docs" / "context" / "charter.md"

_RETIRED_GOVERNING_SURFACE = "doctrine"
_CANONICAL_GOVERNING_SURFACE = "charter"

#: T004's required Terminology-Canon senses for the new ``### charter`` entry
#: (plan.md Slice 4 / mission prompt bullet 4).
#: Mission charter-pack-cutover-01M491G6 (FR-013, ADR 2026-10-06-1 §1) retires the
#: "Pack Default Charter" sense in favour of the activation preset and adds the
#: active charter; the entry must name both instead.
_REQUIRED_CHARTER_CANON_SENSES: tuple[str, ...] = (
    "Charter Bundle",
    "Charter Pack",
    "src/charter/",
    "spec-kitty charter",
    "Active-Inactive Charter",
    "Activation preset",
    "Active charter",
)

_MD_HEADING_RE = re.compile(r"^### (.+?)\s*$", re.MULTILINE)


def _load_seed_terms() -> list[dict[str, Any]]:
    yaml = YAML(typ="safe")
    with _SEED_PATH.open("r", encoding="utf-8") as fh:
        data = yaml.load(fh)
    return list(data["terms"])


def _slugify_heading(text: str) -> str:
    """Mirror ``tests/doctrine/test_glossary_link_integrity.py``'s GitHub-compatible slugger."""
    heading = re.sub(r"\s+#+\s*$", "", text.strip())
    heading = heading.replace("`", "").lower()
    heading = re.sub(r"[^a-z0-9 _-]", "", heading)
    heading = heading.replace(" ", "-")
    return heading.strip("-")


def _parse_markdown_headings(path: Path) -> list[str]:
    """Return every ``### <Term>`` heading's raw text, in document order."""
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    return [m.group(1).strip() for m in _MD_HEADING_RE.finditer(text)]


def _section_body(path: Path, heading_text: str) -> str:
    """Return the raw text of the section starting at ``### {heading_text}``
    up to (but excluding) the next ``---`` divider or heading."""
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(
        r"^### " + re.escape(heading_text) + r"\s*$(.*?)(?=^---\s*$|^### |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(text)
    assert match is not None, f"could not locate ### {heading_text} section in {path}"
    return match.group(1)


@pytest.fixture(scope="module")
def seed_terms() -> list[dict[str, Any]]:
    return _load_seed_terms()


@pytest.fixture(scope="module")
def pack_terms_by_surface() -> dict[str, Any]:
    repo = GlossaryPackRepository(built_in_dir=_BUILT_IN_DIR)
    pack = repo.get(_PACK_ID)
    assert pack is not None, f"built-in pack {_PACK_ID!r} failed to load from {_BUILT_IN_DIR}"
    return {term.surface: term for term in pack.terms}


@pytest.fixture(scope="module")
def charter_md_headings() -> list[str]:
    return _parse_markdown_headings(_CHARTER_MD_PATH)


# ---------------------------------------------------------------------------
# T003 file-move precondition (authority-3 rename)
# ---------------------------------------------------------------------------


def test_authority_3_file_moved_to_charter_md() -> None:
    """OC-40: ``docs/context/charter.offering.md`` is renamed to ``docs/context/charter.md``."""
    assert not _RETIRED_GLOSSARY_MD_PATH.exists(), "docs/context/charter.offering.md must be git-mv'd to docs/context/charter.md (T003)"
    assert _CHARTER_MD_PATH.exists(), "docs/context/charter.md (glossary authority 3) does not exist yet (T003)"


# ---------------------------------------------------------------------------
# H1 anti-vacuity: governing term absent, canonical term present, everywhere.
# ---------------------------------------------------------------------------


def test_governing_doctrine_surface_absent_everywhere(
    seed_terms: list[dict[str, Any]],
    pack_terms_by_surface: dict[str, Any],
    charter_md_headings: list[str],
) -> None:
    seed_surfaces = {t["surface"] for t in seed_terms}
    charter_md_surface_set = {h.lower() for h in charter_md_headings}

    assert _RETIRED_GOVERNING_SURFACE not in seed_surfaces, "seed authority still carries the retired 'doctrine' governing surface"
    assert _RETIRED_GOVERNING_SURFACE not in pack_terms_by_surface, "pack authority still carries the retired 'doctrine' governing surface"
    assert _RETIRED_GOVERNING_SURFACE not in charter_md_surface_set, (
        "docs/context/charter.md still carries a bare '### doctrine' heading "
        "(the governing sense) -- domain headings like 'Doctrine Domain' or "
        "'Doctrine Catalog' are fine and must stay; only a bare 'doctrine' "
        "heading is forbidden"
    )


def test_canonical_charter_surface_present_everywhere(
    seed_terms: list[dict[str, Any]],
    pack_terms_by_surface: dict[str, Any],
    charter_md_headings: list[str],
) -> None:
    seed_surfaces = {t["surface"] for t in seed_terms}
    charter_md_surface_set = {h.lower() for h in charter_md_headings}

    assert _CANONICAL_GOVERNING_SURFACE in seed_surfaces, "seed authority missing 'charter'"
    assert _CANONICAL_GOVERNING_SURFACE in pack_terms_by_surface, "pack authority missing 'charter'"
    assert _CANONICAL_GOVERNING_SURFACE in charter_md_surface_set, "docs/context/charter.md missing the '### charter' Terminology-Canon heading (T004)"


# ---------------------------------------------------------------------------
# B2 reconcile: exactly one `charter` surface per authority (no duplicate
# surface produced by a careless doctrine->charter rename).
# ---------------------------------------------------------------------------


def test_exactly_one_charter_surface_per_authority(
    seed_terms: list[dict[str, Any]],
    charter_md_headings: list[str],
) -> None:
    seed_charter_count = sum(1 for t in seed_terms if t["surface"] == _CANONICAL_GOVERNING_SURFACE)
    assert seed_charter_count == 1, (
        f"seed authority has {seed_charter_count} 'charter' surfaces, expected exactly 1 "
        "(B2 reconcile must retire 'doctrine' into the single pre-existing 'charter' term, "
        "not create a duplicate)"
    )

    repo = GlossaryPackRepository(built_in_dir=_BUILT_IN_DIR)
    pack = repo.get(_PACK_ID)
    assert pack is not None
    pack_charter_count = sum(1 for t in pack.terms if t.surface == _CANONICAL_GOVERNING_SURFACE)
    assert pack_charter_count == 1, f"pack authority has {pack_charter_count} 'charter' surfaces, expected exactly 1"

    md_charter_count = sum(1 for h in charter_md_headings if h.lower() == _CANONICAL_GOVERNING_SURFACE)
    assert md_charter_count == 1, f"docs/context/charter.md has {md_charter_count} '### charter' headings, expected exactly 1"


# ---------------------------------------------------------------------------
# Definition + alias-by-surface parity across the two data authorities
# (seed <-> pack, reinforced here for the governing term specifically), plus
# the reconciled definition no longer self-references the retired term.
# ---------------------------------------------------------------------------


def test_charter_definition_parity_seed_and_pack(
    seed_terms: list[dict[str, Any]],
    pack_terms_by_surface: dict[str, Any],
) -> None:
    seed_charter = next(t for t in seed_terms if t["surface"] == _CANONICAL_GOVERNING_SURFACE)
    pack_charter = pack_terms_by_surface[_CANONICAL_GOVERNING_SURFACE]

    assert seed_charter["definition"] == pack_charter.definition, (
        f"seed<->pack 'charter' definition drifted:\n  seed: {seed_charter['definition']!r}\n  pack: {pack_charter.definition!r}"
    )


def test_charter_definition_no_longer_self_references_doctrine(
    seed_terms: list[dict[str, Any]],
) -> None:
    """T005a: the reconciled 'charter' definition folds in doctrine's 'body of
    governance artifacts' meaning and drops the 'and doctrine' self-reference."""
    seed_charter = next(t for t in seed_terms if t["surface"] == _CANONICAL_GOVERNING_SURFACE)
    definition = seed_charter["definition"]
    assert "doctrine" not in definition.lower(), (
        f"'charter' definition still self-references 'doctrine' -- T005a requires dropping the 'and doctrine' phrase once the meaning is folded in: {definition!r}"
    )
    # zero-loss: the folded-in meaning ("body of ... governance artifacts") must
    # actually survive the fold, not just have the word "doctrine" deleted.
    assert "governance artifact" in definition.lower(), (
        f"'charter' definition dropped the retired 'doctrine' term's meaning entirely instead of folding it in: {definition!r}"
    )


def test_charter_md_heading_matches_seed_surface_alias(
    seed_terms: list[dict[str, Any]],
    charter_md_headings: list[str],
) -> None:
    """Alias-by-surface: the Markdown heading text used for the Canon entry is
    the literal (lowercase, trimmed) 'surface' join key, not a paraphrase."""
    seed_charter = next(t for t in seed_terms if t["surface"] == _CANONICAL_GOVERNING_SURFACE)
    matching_headings = [h for h in charter_md_headings if h.lower() == _CANONICAL_GOVERNING_SURFACE]
    assert matching_headings, "no '### charter' heading found in docs/context/charter.md"
    assert matching_headings[0] == seed_charter["surface"], (
        f"docs/context/charter.md heading text {matching_headings[0]!r} does not alias the seed surface {seed_charter['surface']!r} exactly"
    )


# ---------------------------------------------------------------------------
# T004: the new Canon entry disambiguates the required charter senses.
# ---------------------------------------------------------------------------


def test_charter_canon_entry_covers_required_senses() -> None:
    body = _section_body(_CHARTER_MD_PATH, "charter")
    missing = [sense for sense in _REQUIRED_CHARTER_CANON_SENSES if sense not in body]
    assert not missing, f"docs/context/charter.md '### charter' Canon entry is missing required senses (T004): {missing}"
    assert "Do NOT use when" in body or "**Do NOT use when**" in body, "'### charter' Canon entry must carry a 'Do NOT use when' disambiguation row"


# ---------------------------------------------------------------------------
# Link closure: every relative link inside the new charter Canon section
# resolves to a real anchor in charter.md (defense-in-depth alongside the
# generic tests/doctrine/test_glossary_link_integrity.py sweep).
# ---------------------------------------------------------------------------

_LINK_RE = re.compile(r"\[[^\]]+\]\(#([^)]+)\)")


def test_charter_canon_entry_internal_links_resolve(charter_md_headings: list[str]) -> None:
    anchors = {_slugify_heading(h) for h in charter_md_headings}
    body = _section_body(_CHARTER_MD_PATH, "charter")
    broken = [target for target in _LINK_RE.findall(body) if target not in anchors]
    assert not broken, f"'### charter' Canon entry has dangling in-page anchor links: {broken}"


# ---------------------------------------------------------------------------
# T003 atomicity: the 6 known intra-docs/context inline links are re-pointed
# in the same slice as the git mv (no dangling ./charter.offering.md references left
# in the 3 WP01-owned referrer files' inline term tables).
# ---------------------------------------------------------------------------

_OWNED_REFERRER_FILES: tuple[Path, ...] = (
    _REPO_ROOT / "docs" / "context" / "orchestration.md",
    _REPO_ROOT / "docs" / "context" / "governance.md",
    _REPO_ROOT / "docs" / "context" / "configuration-project-structure.md",
)


def test_owned_referrer_inline_links_repointed_to_charter_md() -> None:
    failures: list[str] = []
    for path in _OWNED_REFERRER_FILES:
        text = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            if "](./charter.offering.md" in line:
                failures.append(f"{path.relative_to(_REPO_ROOT)}:{line_number}: {line.strip()!r}")
    assert not failures, "found un-repointed inline './charter.offering.md' links (T003 atomicity):\n  " + "\n  ".join(failures)


def test_owned_referrer_preserved_anchors_and_link_text() -> None:
    """T003 preserved the #procedure anchor + link TEXT; the retired Doctrine
    Catalog entry's links now point at its successor, Charter offering
    (mission charter-pack-cutover-01M491G6, FR-013)."""
    orchestration = _REPO_ROOT / "docs" / "context" / "orchestration.md"
    governance = _REPO_ROOT / "docs" / "context" / "governance.md"
    config_structure = _REPO_ROOT / "docs" / "context" / "configuration-project-structure.md"

    orchestration_text = orchestration.read_text(encoding="utf-8")
    governance_text = governance.read_text(encoding="utf-8")
    config_structure_text = config_structure.read_text(encoding="utf-8")

    assert "[Procedure](./charter.md#procedure)" in orchestration_text
    assert "[Charter offering](./charter.md#charter-offering)" in governance_text
    assert "[Charter offering](./charter.md#charter-offering)" in config_structure_text
