"""FR-002 / C-001 — characterization pins for the ``charter context`` prose-presence gate.

WP01 (doctrine-charter-split-unification-01KZ0SRB). The gate in
``charter.activation.context.build_charter_context``::

    if not charter_yaml_path.exists() and not charter_path.exists():

is a **C-003 prose-presence gate**: the context renders when EITHER the
``charter.yaml`` authority OR the ``charter.md`` readable secondary exists, and
reports ``mode == "missing"`` only when BOTH are absent.

**Honesty note (post-tasks squad reclassification):** this module changes no
behaviour. It is a green-first *characterization pin*, not a fabricated ATDD
red. Its value is durability: a later "tidy" that collapses the OR into a
strict ``charter.yaml``-only gate would demote ``charter.md``-only projects to
``missing`` (regressing the pre-``charter.yaml`` fixtures), and these tests are
what catches it.

Four presence cells are pinned, plus the one genuine precedence assertion:

===============================  =========================================
cell                             pinned behaviour
===============================  =========================================
(a) yaml present, md deleted     renders; compiled governance survives (SC-002)
(b) md-only (yaml absent)        renders the ``charter.md`` prose (secondary)
(c) both absent                  ``mode == "missing"``
(d) both present                 governance comes from the COMPILED
                                 ``charter.yaml`` bundle, not parsed from md
===============================  =========================================

Cell (d) is made load-bearing by the ``_CHARTER_MD_WITH_DECOY_REFERENCES``
fixture: ``charter.md`` declares TWO decoy reference bullets while
``charter.yaml``'s ``catalog.references`` declares exactly ONE. Because
``_load_references`` reads only ``charter.yaml``, ``references_count`` must
stay ``1`` wherever ``charter.yaml`` exists (and drop to ``0`` when it does
not) — never ``2`` or ``3``. A future change that parsed the governance
catalog out of ``charter.md`` would move that count, which is exactly the
regression this pin exists to catch.

C-001 guard: these tests never assert that the ``charter.md`` prose/section
readers (``context.py``'s bootstrap "Source:" line, ``_extract_policy_summary``,
the ``--include section:<id>`` selector) were retargeted onto ``charter.yaml``
— they legitimately stay on ``charter.md``.
"""

from __future__ import annotations

import textwrap
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from charter.activation.context import build_charter_context
from tests.charter.test_context import (
    _CHARTER_YAML,
    _GOVERNANCE_YAML,
    _MINIMAL_GRAPH_YAML,
)

if TYPE_CHECKING:
    from charter.activation.context import CharterContextResult

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

#: ``charter.md`` carrying prose (the readable secondary) PLUS two decoy
#: reference bullets. The decoys exist so cell (d) can prove the governance
#: reference catalog is sourced from ``charter.yaml`` (exactly one entry) and
#: never parsed out of ``charter.md`` (which would yield two or three).
_CHARTER_MD_WITH_DECOY_REFERENCES = textwrap.dedent("""\
    # Project Charter

    ## Policy Summary

    - Intent: deterministic delivery
    - Testing: pytest + coverage
    - Quality: ruff linting

    ## Reference Docs

    - MD-DECOY-ONE: a reference declared only in charter.md
    - MD-DECOY-TWO: a second reference declared only in charter.md
""")

#: The single reference id declared by ``_CHARTER_YAML``'s ``catalog.references``.
_YAML_REFERENCE_COUNT = 1

#: A policy-summary bullet that can only have come from ``charter.md``.
_MD_PROSE_MARKER = "Intent: deterministic delivery"

#: A directive reachable from ``action:software-dev/implement`` in the fixture
#: DRG — i.e. compiled-bundle governance, independent of ``charter.md``.
_COMPILED_GOVERNANCE_MARKER = "DIRECTIVE_001"

_MISSING_CHARTER_MESSAGE = "Charter file not found"


def _seed_charter_dir(tmp_path: Path, *, with_yaml: bool, with_md: bool) -> Path:
    """Seed ``.kittify/charter`` with the requested presence cell.

    ``governance.yaml`` is always written: it is the doctrine-selection input,
    orthogonal to the charter.yaml/charter.md presence gate under test.
    """
    charter_dir = tmp_path / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    (charter_dir / "governance.yaml").write_text(_GOVERNANCE_YAML, encoding="utf-8")
    # No ``charter:`` pointer is written to config.yaml here, so PackContext
    # reads activation directly from config.yaml (legacy/un-migrated path).
    # ``mission_type_activations`` is provisioned so ``PackContext.from_config``
    # (WP04, C-A1: the provisioned charter is the sole activation authority)
    # does not hard-fail on a genuinely absent key. Written unconditionally
    # (independent of the with_yaml/with_md presence cell under test) since
    # PackContext resolution is orthogonal to the charter.yaml/charter.md
    # prose-presence gate this fixture pins.
    (tmp_path / ".kittify" / "config.yaml").write_text(
        "mission_type_activations:\n  - software-dev\n", encoding="utf-8"
    )
    if with_yaml:
        (charter_dir / "charter.yaml").write_text(_CHARTER_YAML, encoding="utf-8")
    if with_md:
        (charter_dir / "charter.md").write_text(_CHARTER_MD_WITH_DECOY_REFERENCES, encoding="utf-8")

    assert (charter_dir / "charter.yaml").exists() is with_yaml
    assert (charter_dir / "charter.md").exists() is with_md
    return charter_dir


def _build(tmp_path: Path) -> CharterContextResult:
    """Render ``charter context`` against the seeded fixture repo.

    ``ensure_charter_bundle_fresh`` is stubbed to a no-op: left live it
    auto-syncs and WRITES ``charter.yaml`` from ``charter.md``, silently
    flipping the "charter.yaml absent" precondition that cells (b) and (c)
    depend on.
    """
    from charter.activation.sync import SyncResult
    from charter.offering.drg.models import DRGGraph
    from ruamel.yaml import YAML

    yaml = YAML(typ="safe")
    mock_graph = DRGGraph.model_validate(yaml.load(StringIO(_MINIMAL_GRAPH_YAML)))
    sync_result = SyncResult(
        synced=False,
        stale_before=False,
        files_written=[],
        extraction_mode="",
        canonical_root=tmp_path,
    )

    with (
        patch("charter.activation.sync.ensure_charter_bundle_fresh", return_value=sync_result),
        patch("charter.activation._drg_helpers.load_validated_graph", return_value=mock_graph),
        patch("charter.activation.catalog.resolve_offering_root", return_value=tmp_path),
        patch("charter.offering.drg.validator.assert_valid"),
    ):
        return build_charter_context(tmp_path, action="implement", depth=2, mission_type="software-dev")


# ---------------------------------------------------------------------------
# T001 — the four presence cells
# ---------------------------------------------------------------------------


class TestProsePresenceGateCells:
    """Pin all four cells of the ``charter.yaml`` OR ``charter.md`` gate."""

    def test_cell_a_yaml_present_md_deleted_still_renders(self, tmp_path: Path) -> None:
        """(a) ``charter.yaml`` only — compiled governance renders (SC-002).

        The authority alone is sufficient; a deleted ``charter.md`` must not
        drop the context to ``missing`` nor lose the compiled bundle.
        """
        _seed_charter_dir(tmp_path, with_yaml=True, with_md=False)

        result = _build(tmp_path)

        assert result.mode == "bootstrap"
        assert _MISSING_CHARTER_MESSAGE not in result.text
        assert _COMPILED_GOVERNANCE_MARKER in result.text
        # Governance references still come from charter.yaml's catalog...
        assert result.references_count == _YAML_REFERENCE_COUNT
        # ...while the md-only prose is simply absent (graceful degrade, not a crash).
        assert _MD_PROSE_MARKER not in result.text

    def test_cell_b_md_only_renders_charter_md_prose(self, tmp_path: Path) -> None:
        """(b) ``charter.md`` only — the readable secondary still renders.

        This is the cell the OR-gate exists to keep serving: a legacy,
        pre-``charter.yaml`` project. A strict ``charter.yaml``-only gate would
        regress this to ``missing``.
        """
        _seed_charter_dir(tmp_path, with_yaml=False, with_md=True)

        result = _build(tmp_path)

        assert result.mode == "bootstrap"
        assert result.mode != "missing"
        assert _MISSING_CHARTER_MESSAGE not in result.text
        # The charter.md prose is what makes this cell worth serving.
        assert _MD_PROSE_MARKER in result.text
        # No charter.yaml ⇒ no governance reference catalog. Notably NOT 2:
        # the decoy bullets in charter.md are prose, never a reference source.
        assert result.references_count == 0

    def test_cell_c_both_absent_is_missing(self, tmp_path: Path) -> None:
        """(c) neither file — and only then — reports ``mode == "missing"``."""
        _seed_charter_dir(tmp_path, with_yaml=False, with_md=False)

        result = _build(tmp_path)

        assert result.mode == "missing"
        assert _MISSING_CHARTER_MESSAGE in result.text
        assert result.references_count == 0

    def test_cell_d_both_present_renders_governance_and_prose(self, tmp_path: Path) -> None:
        """(d) both files — compiled governance AND md prose are delivered."""
        _seed_charter_dir(tmp_path, with_yaml=True, with_md=True)

        result = _build(tmp_path)

        assert result.mode == "bootstrap"
        assert _MISSING_CHARTER_MESSAGE not in result.text
        assert _COMPILED_GOVERNANCE_MARKER in result.text
        assert _MD_PROSE_MARKER in result.text


# ---------------------------------------------------------------------------
# T002 — the precedence assertion (the one genuine behaviour pin)
# ---------------------------------------------------------------------------


class TestCharterYamlPrecedenceOverCharterMd:
    """``charter.yaml`` is the governance authority; ``charter.md`` is prose."""

    def test_governance_catalog_comes_from_charter_yaml_not_charter_md(self, tmp_path: Path) -> None:
        """With BOTH present, the reference catalog is the charter.yaml projection.

        ``charter.md`` declares two decoy reference bullets; ``charter.yaml``
        declares exactly one. The delivered count is the charter.yaml one — if
        a future change ORed in (or fell back to) md-parsed references, this
        count would be 2 or 3 instead.
        """
        _seed_charter_dir(tmp_path, with_yaml=True, with_md=True)

        result = _build(tmp_path)

        assert result.references_count == _YAML_REFERENCE_COUNT
        assert result.references_count != 2, "reference catalog leaked in charter.md's decoy bullets"

    def test_deleting_charter_md_drops_only_prose_never_governance(self, tmp_path: Path) -> None:
        """Deleting ``charter.md`` from the both-present state is prose-only loss.

        This is the precedence claim stated as a differential: governance
        (mode, compiled bundle, reference catalog) is byte-identical before and
        after the deletion, so none of it was ever sourced from ``charter.md``.
        Only the prose marker disappears.
        """
        charter_dir = _seed_charter_dir(tmp_path, with_yaml=True, with_md=True)

        before = _build(tmp_path)
        assert before.mode == "bootstrap"
        assert _MD_PROSE_MARKER in before.text
        assert _COMPILED_GOVERNANCE_MARKER in before.text

        (charter_dir / "charter.md").unlink()

        after = _build(tmp_path)

        # Governance is untouched by the deletion — charter.yaml precedence.
        assert after.mode == before.mode == "bootstrap"
        assert after.references_count == before.references_count == _YAML_REFERENCE_COUNT
        assert _COMPILED_GOVERNANCE_MARKER in after.text
        assert _MISSING_CHARTER_MESSAGE not in after.text
        # ...and the prose — the only charter.md-sourced content — is what dropped.
        assert _MD_PROSE_MARKER not in after.text
