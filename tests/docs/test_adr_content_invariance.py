"""Post-move census-hygiene gate for ADRs under ``docs/adr/<era>/`` (WP06).

WP06 ran WP05's extended converter over the live tree, moving the realpath-unique
ADRs to ``docs/adr/<era>/`` with bare-``status`` frontmatter and dropping the 71
back-compat symlinks. This module is the surviving on-disk hygiene gate for that
move (NFR-001):

* :class:`TestCensus` — no dangling back-compat symlink survives, and **every**
  census ADR (dated ``YYYY-MM-DD-*`` files **and** non-dated promoted ``adr-*``
  files) carries bare-``status`` MADR frontmatter. These are permanent on-disk
  invariants that read only the assembled tree.

**Census predicate (WP06 / FR-011):** ``_is_census_adr`` admits both the dated
ADRs and the non-dated *promoted* ADRs (``adr-<slug>.md``). Before WP06 the
predicate was ``_DATE_PREFIX``-only, so the two promoted ADRs
(``adr-connector-auth-binding-separation.md``,
``adr-github-app-installation-authority.md``) were invisible to these checks —
FR-011 closes that blind-spot so they too are validated for MADR frontmatter.

**Dropped (2026-06-30, doc-quality-hardening review):** the exact-count assertion
(``test_adr_census_matches_expected`` + the hardcoded ``_EXPECTED_CENSUS``
constant). With byte-invariance retired upstream (``ccd278061``), a hardcoded
total guards little and merely fails on every legitimate ADR add/remove — pure
future friction. The durable value is the per-ADR hygiene below (frontmatter +
symlink), which does not need a magic number.

Retired earlier (2026-06-29): the byte-identity content-invariance proof
(``TestContentInvariance`` + ``TestBaseResolutionIsRebaseRobust``) was a
transitional gate for the move itself, self-invalidating once merged to main.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

import pytest

from scripts.docs._inventory import parse_frontmatter
from scripts.docs.adr_converter import MADR_STATUSES

# ``scripts.docs`` is importable without any sys.path bootstrap: pytest's own
# rootdir-prepend (``tests/__init__.py``) already puts the repo root on
# ``sys.path`` before this module is collected.
_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]

# On-disk hygiene invariants over the assembled tree. ``architectural`` puts this
# in the dedicated arch shard; ``git_repo`` is retained so CI's ``-m git_repo``
# filter keeps selecting it in the shard it has always run in.
pytestmark = [pytest.mark.architectural, pytest.mark.git_repo]

_DOCS_ADR: Final[Path] = _REPO_ROOT / "docs" / "adr"
_ERAS: Final[tuple[str, ...]] = ("1.x", "2.x", "3.x", "4.x")
_DATE_PREFIX: Final[re.Pattern[str]] = re.compile(r"^\d{4}-\d{2}-\d{2}-")
# Non-dated *promoted* ADRs: ``adr-<slug>.md`` (no date prefix). READMEs and other
# ``.md`` files are excluded — only ``adr-`` carries the promoted-ADR contract.
_PROMOTED_ADR: Final[re.Pattern[str]] = re.compile(r"^adr-.+\.md$")


def _is_census_adr(name: str) -> bool:
    """True for a census ADR file: a dated ``YYYY-MM-DD-*`` or a promoted ``adr-*``."""
    return bool(_DATE_PREFIX.match(name) or _PROMOTED_ADR.match(name))


def _adr_files_on_disk() -> list[Path]:
    """Every census ADR file under ``docs/adr/<era>/`` (READMEs excluded)."""
    found: list[Path] = []
    for era in _ERAS:
        era_dir = _DOCS_ADR / era
        if not era_dir.is_dir():
            continue
        for path in era_dir.glob("*.md"):
            if path.is_file() and _is_census_adr(path.name):
                found.append(path)
    return found


class TestCensus:
    def test_no_dangling_back_compat_symlinks(self) -> None:
        dangling = [p for p in _DOCS_ADR.rglob("*") if p.is_symlink() and not p.exists()]
        assert dangling == [], f"dangling symlinks under docs/adr: {dangling}"

    def test_every_adr_has_bare_madr_status_frontmatter(self) -> None:
        # FR-011: the promoted (non-dated) ADRs flow through ``_adr_files_on_disk``
        # via ``_is_census_adr`` and are validated here alongside the dated ones.
        canonical = set(MADR_STATUSES.values())
        offenders: list[str] = []
        for path in _adr_files_on_disk():
            front = parse_frontmatter(path.read_text(encoding="utf-8"))
            status = front.get("status") if front else None
            if status not in canonical:
                offenders.append(f"{path.name}: status={status!r}")
        assert offenders == [], f"non-MADR / missing bare status: {offenders}"
