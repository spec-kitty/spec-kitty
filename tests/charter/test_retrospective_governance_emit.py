"""FR-005 (a)+(b)+(c): ``governance.retrospective`` schema, emitter, omit-when-empty.

Mission ``doctrine-charter-split-unification-01KZ0SRB``, WP05. Authoritative:
``kitty-specs/doctrine-charter-split-unification-01KZ0SRB/spec.md`` FR-005 /
User Story 2 / SC-002 / C-003 and ``research.md`` **D3**.

``GovernanceConfig`` carried no ``retrospective`` field before this WP, so an
operator-authored ``governance.retrospective:`` block was silently DROPPED by
``GovernanceConfig.model_validate`` (pydantic ignores unknown keys). This module
pins the two halves of the fix, which have deliberately different red-timing
(research.md D10 — do not conflate them):

**Case (a) — the committed-first ATDD red** (``TestAuthoredRetrospectiveIsEmitted``):
``charter.activation.sync.load_governance_config`` must preserve an authored
``governance.retrospective`` block and ``compiler.write_compiled_charter`` must
emit it. RED on first authoring (no field exists yet).

**Case (b) — the NFR-005 byte-stability guard** (``TestOmittedWhenUnset``):
a charter with NO retrospective config must emit byte-identical YAML. GREEN
today (nothing is emitted at all), goes RED the moment the schema field lands,
and returns to green only once the omit-when-empty pruner drops it. It is a
mid-implementation regression gate, NOT a committed-first red.

The two emit paths are protected by two different mechanisms, and both are
exercised here on purpose:

* ``schemas.emit_yaml`` dumps WITHOUT ``exclude_none`` (see the ``convention:``
  null it still writes), so a bare ``retrospective: None`` WOULD leak a trailing
  ``retrospective:`` key into its output. Only the extended
  ``_prune_optional_empties`` omit-when-empty allow-list keeps it out —
  :func:`TestOmittedWhenUnset.test_emit_yaml_default_governance_is_byte_identical`
  is that mechanism's proof, pinned against the exact pre-WP05 bytes.
* ``compiler._bootstrap_charter_yaml`` dumps WITH ``exclude_none=True``, which
  drops the ``None`` before the pruner ever sees it. Pinned separately so a
  future switch away from ``exclude_none`` cannot silently start leaking the
  block into every compiled ``charter.yaml``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML

from charter.activation.charter_yaml_io import load_charter_yaml, save_charter_yaml
from charter.activation.compiler import CompiledCharter, compile_charter, write_compiled_charter
from charter.activation.interview import default_interview
from charter.activation.schemas import GovernanceConfig, emit_yaml
from charter.activation.sync import load_governance_config

pytestmark = pytest.mark.fast


#: The EXACT bytes ``emit_yaml(GovernanceConfig())`` produced before WP05.
#: Captured from the pre-change implementation; any additive schema field that
#: starts serializing here is an NFR-005 byte-stability regression.
_DEFAULT_GOVERNANCE_YAML_GOLDEN = (
    "# Auto-generated from charter.md — do not edit directly.\n"
    "# Run 'spec-kitty charter generate' to regenerate.\n"
    "\n"
    "testing:\n"
    "  min_coverage: 0\n"
    "  tdd_required: false\n"
    "  framework: ''\n"
    "  type_checking: ''\n"
    "quality:\n"
    "  linting: ''\n"
    "  pr_approvals: 1\n"
    "  pre_commit_hooks: false\n"
    "commits:\n"
    "  convention:\n"
    "performance:\n"
    "  cli_timeout_seconds: 2.0\n"
    "  dashboard_max_wps: 100\n"
    "branch_strategy:\n"
    "  main_branch: main\n"
    "  dev_branch:\n"
    "  rules: []\n"
    "charter:\n"
    "  selected_paradigms: []\n"
    "  selected_directives: []\n"
    "  selected_tactics: []\n"
    "  available_tools: []\n"
    "  template_set:\n"
    "enforcement: {}\n"
)

#: An authored ``governance:`` section carrying a PARTIAL retrospective block.
#: Partial on purpose: C-003 keeps ``charter.md`` frontmatter a contributing
#: secondary, so the authority block must be able to express "these keys only"
#: without inventing defaults for the rest (WP06 feeds it as the
#: highest-precedence block into ``_apply_block_to_policy``).
_AUTHORED_RETROSPECTIVE: dict[str, Any] = {
    "enabled": False,
    "failure_policy": "block",
    "permissions": {"apply_low_risk_changes": True},
}


@pytest.fixture(scope="module")
def compiled() -> CompiledCharter:
    interview = default_interview(mission="software-dev", profile="minimal")
    return compile_charter(mission="software-dev", interview=interview)


def _write_authored_charter_yaml(root: Path, governance: dict[str, Any]) -> Path:
    """Author ``<root>/.kittify/charter/charter.yaml`` with a governance section.

    ``root`` is the canonical repo root (the ``tests/charter/conftest.py``
    autouse fixture git-inits ``tmp_path``, so ``resolve_canonical_repo_root``
    maps it to itself).
    """
    charter_yaml_path = root / ".kittify" / "charter" / "charter.yaml"
    save_charter_yaml(charter_yaml_path, {"governance": governance})
    return charter_yaml_path


def _bootstrap_into(
    root: Path, compiled: CompiledCharter, *, subdir: str = "charter-bootstrap"
) -> dict[str, Any]:
    """Run ``write_compiled_charter``'s BOOTSTRAP path and return the document.

    The output directory deliberately differs from the canonical
    ``.kittify/charter/`` so no ``charter.yaml`` pre-exists there: that is the
    branch which seeds ``governance`` from
    :func:`charter.activation.sync.load_governance_config` (the FR-005b emitter seam).
    """
    output_dir = root / ".kittify" / subdir
    write_compiled_charter(output_dir, compiled, repo_root=root)
    document = load_charter_yaml(output_dir / "charter.yaml")
    assert isinstance(document, dict)
    return dict(document)


# ---------------------------------------------------------------------------
# Case (a) — FR-005 (a)+(b): the authored block survives and is emitted
# ---------------------------------------------------------------------------


class TestAuthoredRetrospectiveIsEmitted:
    def test_load_governance_config_preserves_authored_retrospective(
        self, tmp_path: Path
    ) -> None:
        """The schema must model the block — without the field, pydantic drops it."""
        _write_authored_charter_yaml(
            tmp_path, {"retrospective": dict(_AUTHORED_RETROSPECTIVE)}
        )

        governance = load_governance_config(tmp_path)

        assert governance.retrospective is not None, (
            "GovernanceConfig dropped the authored governance.retrospective block"
        )
        assert governance.retrospective.enabled is False
        assert governance.retrospective.failure_policy == "block"
        assert governance.retrospective.permissions is not None
        assert governance.retrospective.permissions.apply_low_risk_changes is True

    def test_partial_block_does_not_gain_invented_defaults(
        self, tmp_path: Path
    ) -> None:
        """Unauthored keys stay ``None`` (C-003: charter.md remains a
        contributing secondary for keys charter.yaml does not claim)."""
        _write_authored_charter_yaml(
            tmp_path, {"retrospective": dict(_AUTHORED_RETROSPECTIVE)}
        )

        retrospective = load_governance_config(tmp_path).retrospective

        assert retrospective is not None
        assert retrospective.timing is None
        assert retrospective.generate_proposals is None
        assert retrospective.generator is None
        assert retrospective.permissions is not None
        assert retrospective.permissions.write_record is None

    def test_write_compiled_charter_emits_governance_retrospective(
        self, tmp_path: Path, compiled: CompiledCharter
    ) -> None:
        """FR-005b: the compiler emitter populates ``governance.retrospective``."""
        _write_authored_charter_yaml(
            tmp_path, {"retrospective": dict(_AUTHORED_RETROSPECTIVE)}
        )

        document = _bootstrap_into(tmp_path, compiled)

        emitted = document["governance"]["retrospective"]
        assert emitted["enabled"] is False
        assert emitted["failure_policy"] == "block"
        assert emitted["permissions"]["apply_low_risk_changes"] is True

    def test_emitted_block_omits_unauthored_keys(
        self, tmp_path: Path, compiled: CompiledCharter
    ) -> None:
        """A partial authored block round-trips as a partial emitted block."""
        _write_authored_charter_yaml(
            tmp_path, {"retrospective": dict(_AUTHORED_RETROSPECTIVE)}
        )

        document = _bootstrap_into(tmp_path, compiled)

        emitted = document["governance"]["retrospective"]
        assert set(emitted) == {"enabled", "failure_policy", "permissions"}
        assert set(emitted["permissions"]) == {"apply_low_risk_changes"}

    def test_emit_yaml_round_trips_an_authored_block(self, tmp_path: Path) -> None:
        """``schemas.emit_yaml`` serializes a populated block (the pruner must
        drop only EMPTY values, never a real one)."""
        governance = GovernanceConfig.model_validate(
            {"retrospective": dict(_AUTHORED_RETROSPECTIVE)}
        )
        path = tmp_path / "governance.yaml"

        emit_yaml(governance, path)

        loaded = YAML(typ="safe").load(path.read_text(encoding="utf-8"))
        assert loaded["retrospective"]["enabled"] is False
        assert loaded["retrospective"]["failure_policy"] == "block"


# ---------------------------------------------------------------------------
# Case (b) — NFR-005: omitted when unset, bytes unchanged
# ---------------------------------------------------------------------------


class TestOmittedWhenUnset:
    def test_emit_yaml_default_governance_is_byte_identical(
        self, tmp_path: Path
    ) -> None:
        """THE pruner proof.

        ``emit_yaml`` dumps without ``exclude_none``, so the new
        ``retrospective: RetrospectiveGovernance | None = None`` field WOULD
        serialize as a trailing ``retrospective:`` key here. The omit-when-empty
        allow-list in ``_prune_optional_empties`` is the only thing keeping
        these bytes identical to the pre-WP05 golden.
        """
        path = tmp_path / "governance.yaml"

        emit_yaml(GovernanceConfig(), path)

        assert path.read_text(encoding="utf-8") == _DEFAULT_GOVERNANCE_YAML_GOLDEN

    def test_emit_yaml_drops_an_explicitly_empty_block(self, tmp_path: Path) -> None:
        """An explicit ``retrospective: {}`` carries no policy, so it is pruned
        (the empty-dict arm of the omit-when-empty rule)."""
        governance = GovernanceConfig.model_validate({"retrospective": {}})
        path = tmp_path / "governance.yaml"

        emit_yaml(governance, path)

        assert path.read_text(encoding="utf-8") == _DEFAULT_GOVERNANCE_YAML_GOLDEN

    def test_bootstrap_omits_retrospective_when_charter_has_none(
        self, tmp_path: Path, compiled: CompiledCharter
    ) -> None:
        """A charter.yaml authored WITHOUT a retrospective block must not grow
        one when the compiler refreshes the bundle."""
        _write_authored_charter_yaml(tmp_path, {"testing": {"min_coverage": 87}})

        document = _bootstrap_into(tmp_path, compiled)

        assert "retrospective" not in document["governance"], (
            "a default retrospective block leaked into the compiled charter.yaml"
        )
        assert document["governance"]["testing"]["min_coverage"] == 87

    def test_bootstrap_without_repo_root_omits_retrospective(
        self, tmp_path: Path, compiled: CompiledCharter
    ) -> None:
        """The fresh-project bootstrap (empty ``GovernanceConfig()``) stays clean."""
        output_dir = tmp_path / ".kittify" / "charter"

        write_compiled_charter(output_dir, compiled)

        document = load_charter_yaml(output_dir / "charter.yaml")
        assert "retrospective" not in document["governance"]

    def test_other_optional_empties_still_pruned(self, tmp_path: Path) -> None:
        """Regression pin on the pruner's pre-existing list-only behaviour:
        widening it to ``None``/empty-dict must not stop dropping empty lists,
        nor start dropping non-allow-listed empties such as ``enforcement``."""
        path = tmp_path / "governance.yaml"

        emit_yaml(GovernanceConfig(), path)

        text = path.read_text(encoding="utf-8")
        assert "activations:" not in text  # allow-listed empty list -> dropped
        assert "selected_styleguides:" not in text  # allow-listed empty list -> dropped
        assert "enforcement: {}\n" in text  # NOT allow-listed -> still emitted
