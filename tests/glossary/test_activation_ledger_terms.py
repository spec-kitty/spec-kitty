"""The core glossary names the activation ledger and the current active charter.

Regression guard for spec-kitty/spec-kitty#6562. `.kittify/charter/activation.yaml`
became the single activation authority in #6496 (ADR `2026-10-19-1`), but the
glossary seed and the built-in pack still described the pre-ledger location for
`active charter` and carried no `activation ledger` term. The seed drives the
published glossary page (``scripts/docs/generate_kitty_specs_docs.py``), so this
test reads it directly.

The standing seed<->pack parity gate
(``tests/architectural/test_glossary_pack_parity.py``) is the other half of the
proof: it fails if the seed changes without the built-in pack changing with it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML

pytestmark = pytest.mark.fast

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SEED_PATH = _REPO_ROOT / ".kittify" / "glossaries" / "spec_kitty_core.yaml"


def _seed_terms() -> dict[str, dict[str, Any]]:
    yaml = YAML(typ="safe")
    with _SEED_PATH.open("r", encoding="utf-8") as handle:
        data = yaml.load(handle)
    return {term["surface"]: term for term in data["terms"]}


@pytest.fixture(scope="module")
def terms() -> dict[str, dict[str, Any]]:
    return _seed_terms()


def test_activation_ledger_is_a_canonical_glossary_term(terms: dict[str, dict[str, Any]]) -> None:
    term = terms.get("activation ledger")
    assert term is not None, "the activation ledger term is missing from the core glossary seed"
    assert term["status"] == "active"
    assert float(term["confidence"]) >= 0.9


def test_activation_ledger_definition_names_the_ledger_and_its_rules(terms: dict[str, dict[str, Any]]) -> None:
    definition = terms["activation ledger"]["definition"]
    assert ".kittify/charter/activation.yaml" in definition
    assert "activated_kinds" in definition
    assert "mission_type_activations" in definition
    assert "deactivated_" in definition
    # The effective set is allow minus exclusions, and the exclusion never
    # removes an org-required id.
    assert "org-required" in definition
    # Not the Migration Ledger.
    assert "Migration Ledger" in definition


def test_active_charter_definition_names_the_ledger_not_the_legacy_home(terms: dict[str, dict[str, Any]]) -> None:
    definition = terms["active charter"]["definition"]
    assert "activation ledger" in definition
    assert ".kittify/charter/activation.yaml" in definition
    assert "deactivated_" in definition
    # A project not yet on 4.0.0rc8 keeps the allow keys in the legacy location;
    # the entry may say that, but it must not present the old location as the home.
    assert "4.0.0rc8" in definition
    legacy_lead = "What a project has activated: its activated_<kind> keys, activated_kinds and mission_type_activations, in .kittify/config.yaml"
    assert not definition.startswith(legacy_lead)


def test_activation_module_docstrings_link_their_glossary_entries() -> None:
    """FR-005: the code seams that name the concepts point at the glossary."""
    ledger_source = (_REPO_ROOT / "src" / "charter" / "activation" / "activation_ledger.py").read_text(encoding="utf-8")
    resolver_source = (_REPO_ROOT / "src" / "charter" / "activation" / "resolver.py").read_text(encoding="utf-8")
    assert "docs/context/charter.md#activation-ledger" in ledger_source
    assert "docs/context/charter.md#active-charter" in resolver_source


def test_governance_guide_points_the_preset_write_at_the_activation_ledger() -> None:
    """FR-006: the guide no longer sends a preset's write to the pre-#6496 home."""
    guide = (_REPO_ROOT / "docs" / "guides" / "how-to" / "governance" / "troubleshoot-charter.md").read_text(encoding="utf-8")
    assert "only writes activation keys into the activation ledger (`.kittify/charter/activation.yaml`)" in guide
    assert "only writes activation keys into the active charter (`.kittify/config.yaml`)" not in guide
