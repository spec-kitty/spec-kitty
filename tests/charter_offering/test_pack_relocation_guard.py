"""T020 — Three-part relocation guard + per-kind loud-failure (FR-009).

The relocation moved the shipped built-in doctrine content out of
``src/charter/offering/<kind>/built-in/`` into the flat pack root
``packs/built-in/<kind>/``. Three independent surfaces must all agree that the
move actually happened, and a fourth (parametrized) surface fails LOUDLY if any
single kind's repository was left pointing at an emptied tree:

1. *filesystem* — every path the WP01 content manifest recorded as moved is now
   ABSENT under ``src/charter/offering/`` (exact set vs ``content-manifest.json``).
2. *resolved-path* — every built-in repository resolves its ``built_in_dir``
   inside ``packs/built-in/`` (``is_relative_to``), never back into
   ``src/charter/offering/``.
3. *anchor* — no ``files("doctrine.<kind>")`` importlib content anchor survives
   for any of the 9 moved kinds (a hyphenated ``packs/built-in`` is not a legal
   package, so any surviving per-kind package anchor is a missed repoint).

Loud-failure (4): parametrized over the 9 kinds, each repository's resolved
``built_in_dir`` must EXIST and be NON-EMPTY. A missed repoint returns an empty
directory (or a stale ``src/charter/offering/<kind>/built-in`` that no longer holds
content) and every consuming repo silently degrades to ``[]`` while the build
stays green — this parametrized loop is what turns that silent ``[]`` into a
red.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from charter.offering.pack_paths import resolve_pack_root
from charter.offering.service import CharterOfferingService

pytestmark = [pytest.mark.fast, pytest.mark.doctrine, pytest.mark.corpus]

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTENT_MANIFEST = Path(__file__).parent / "fixtures" / "content-manifest.json"

# The 9 relocated content kinds -> the CharterOfferingService accessor that builds each
# kind's repository. ``mission_step_contracts`` and ``templates``/``schemas`` are
# intentionally excluded: they were NOT part of the pack relocation.
KIND_TO_ACCESSOR: dict[str, str] = {
    "agent_profiles": "agent_profiles",
    "assets": "assets",
    "directives": "directives",
    "glossary_packs": "glossary_packs",
    "paradigms": "paradigms",
    "procedures": "procedures",
    "styleguides": "styleguides",
    "tactics": "tactics",
    "toolguides": "toolguides",
}
RELOCATED_KINDS = sorted(KIND_TO_ACCESSOR)


def _self_resolving_service() -> CharterOfferingService:
    """A service with no explicit built-in root so each repo self-resolves the pack."""
    return CharterOfferingService()


def _resolved_built_in_dir(kind: str) -> Path:
    service = _self_resolving_service()
    repo = getattr(service, KIND_TO_ACCESSOR[kind])
    return repo._built_in_dir  # noqa: SLF001 — guard asserts the resolved seam directly


# ---------------------------------------------------------------------------
# Part 1 — filesystem: the moved trees are absent under src/charter/offering/
# ---------------------------------------------------------------------------


def test_moved_content_is_absent_under_src_doctrine() -> None:
    """Every manifest-recorded path is gone from ``src/charter/offering/`` (exact set)."""
    with CONTENT_MANIFEST.open(encoding="utf-8") as fh:
        moved_paths: list[str] = json.load(fh)

    assert moved_paths, "content manifest must be non-empty"
    still_present = sorted(p for p in moved_paths if (REPO_ROOT / p).exists())
    assert still_present == [], (
        f"{len(still_present)} moved path(s) still present under src/charter/offering/: "
        f"{still_present[:10]}"
    )


# ---------------------------------------------------------------------------
# Part 2 — resolved-path: every built-in resolution lands in packs/built-in/
# ---------------------------------------------------------------------------


def test_every_built_in_resolution_is_within_packs_built_in() -> None:
    pack_root = resolve_pack_root("built-in")
    for kind in RELOCATED_KINDS:
        resolved = _resolved_built_in_dir(kind)
        assert resolved.is_relative_to(pack_root), (
            f"{kind} built_in_dir {resolved} is not inside {pack_root}"
        )


# ---------------------------------------------------------------------------
# Part 3 — anchor: no files("doctrine.<kind>") content anchor survives
# ---------------------------------------------------------------------------


def test_no_per_kind_importlib_content_anchor_remains() -> None:
    """No ``files("doctrine.<kind>")`` anchor for any relocated kind (all 9).

    ``packs/built-in`` cannot be addressed by ``importlib.resources.files`` (the
    hyphen is not a legal identifier), so any surviving per-kind package anchor
    is a resolution path that never reaches the moved content.
    """
    doctrine_src = REPO_ROOT / "src" / "charter" / "offering"
    forbidden = tuple(
        anchor
        for kind in RELOCATED_KINDS
        for anchor in (f'files("doctrine.{kind}")', f"files('doctrine.{kind}')")
    )
    offenders: list[str] = []
    for py_file in doctrine_src.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        for anchor in forbidden:
            if anchor in text:
                offenders.append(f"{py_file.relative_to(REPO_ROOT)}: {anchor}")
    assert offenders == [], f"surviving per-kind content anchors: {offenders}"


# ---------------------------------------------------------------------------
# Loud-failure (4) — per-kind resolved built_in_dir exists AND is non-empty
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", RELOCATED_KINDS)
def test_resolved_built_in_dir_exists_and_is_non_empty(kind: str) -> None:
    resolved = _resolved_built_in_dir(kind)
    assert resolved.exists(), f"{kind} built_in_dir does not exist: {resolved}"
    assert resolved.is_dir(), f"{kind} built_in_dir is not a directory: {resolved}"
    contents = [p for p in resolved.iterdir() if not p.name.startswith(".")]
    assert contents, f"{kind} built_in_dir resolved to an EMPTY directory: {resolved}"


@pytest.mark.parametrize("kind", RELOCATED_KINDS)
def test_each_repository_loads_a_non_empty_built_in_set(kind: str) -> None:
    """The repo actually LOADS content — the strongest signal against silent []."""
    service = _self_resolving_service()
    repo = getattr(service, KIND_TO_ACCESSOR[kind])
    assert repo.list_all(), f"{kind} repository loaded ZERO built-in items"
