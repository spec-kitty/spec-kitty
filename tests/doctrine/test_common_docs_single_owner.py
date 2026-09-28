"""Common Docs doctrine owners.

One owner states each rule; every other artifact references the owner by id
instead of restating it. This suite pins the
single-owner shape for the Common Docs doctrine set:

* **ADR status field** — ADR frontmatter guidance (MADR ``status``, never ``doc_status``)
  is owned by DIRECTIVE_042 alone; no tactic restates ``doc_status`` guidance
  for ADRs.
* **Section count and routing** — the "13 sections" count is stated exactly once, in the
  ``common-docs`` styleguide's own principle; every other artifact that used
  to hard-code the number references the styleguide's list instead. The
  built-in structural-lint routing config targets only sections that are in
  its own ``sanctioned_content_sections`` list.
* **Point-in-time markers** — every ``point_in_time_markers`` marker value is either one of
  DIRECTIVE_042's five ``doc_status`` lifecycle values, or explicitly
  declared as a lint-asset-owned marker value in the lint asset's own data
  file (``assets/docs_structural_lint.config.yaml``).
* **Same-change rule** — DIRECTIVE_037 (Living Documentation Sync) owns the "docs updated
  in the same change as behaviour" rule; the other sites reference it by id
  instead of restating it.
* **Lint policy data** — the structural lint's default policy data lives in
  ``packs/built-in/assets/docs_structural_lint.config.yaml`` (owned by the
  lint asset), loadable through the unchanged ``structural_lint_config:``
  wrapper-key loader contract.
* **Validate vocabulary** — the documentation-validate
  accept/mitigate/block-publish vocabulary is mapped onto the adversarial
  squad's findings-disposition contract, citing ``adversarial-squad-deployment``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PACKS = _REPO_ROOT / "packs" / "built-in"

_DIRECTIVE_042 = _PACKS / "directives" / "042-common-docs.directive.yaml"
_STYLEGUIDE_COMMON_DOCS = _PACKS / "styleguides" / "common-docs.styleguide.yaml"
_STYLEGUIDE_FRESHNESS = _PACKS / "styleguides" / "docs-freshness-sla.styleguide.yaml"
_STYLEGUIDE_PUBLICATION = _PACKS / "styleguides" / "publication-authority.styleguide.yaml"
_TACTIC_SCAFFOLD = _PACKS / "tactics" / "common-docs-scaffold.tactic.yaml"
_TACTIC_WRITE = _PACKS / "tactics" / "common-docs-write.tactic.yaml"
_LINT_CONFIG_ASSET = _PACKS / "assets" / "docs_structural_lint.config.yaml"
_LINT_ASSET_MANIFEST = _PACKS / "assets" / "docs_structural_lint.py.asset.yaml"
_GOVERNANCE_PROFILE = _PACKS / "missions" / "documentation" / "governance-profile.yaml"
_PUBLISH_GUIDELINES = _PACKS / "missions" / "mission-steps" / "documentation" / "publish" / "guidelines.md"
_PUBLISH_PROMPT = _PACKS / "missions" / "mission-steps" / "documentation" / "publish" / "prompt.md"
_VALIDATE_GUIDELINES = _PACKS / "missions" / "mission-steps" / "documentation" / "validate" / "guidelines.md"
_VALIDATE_PROMPT = _PACKS / "missions" / "mission-steps" / "documentation" / "validate" / "prompt.md"

_DOC_STATUS_FIVE = {"draft", "active", "deprecated", "superseded", "durable"}

_YAML = YAML(typ="safe")


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_yaml(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = _YAML.load(_text(path))
    return result


def _has_number_or_word(text: str, *, needle_number: str, needle_word: str) -> bool:
    return bool(re.search(rf"\b{needle_number}\b", text)) or needle_word.lower() in text.lower()


def _step_text(step: dict[str, Any]) -> str:
    """Join a step's title, description, and examples into one searchable string."""
    parts = [str(step.get("title", "")), str(step.get("description", ""))]
    parts.extend(str(example) for example in step.get("examples", []) or [])
    return "\n".join(parts)


# --- ADR doc_status guidance has exactly one owner (DIRECTIVE_042) ---------


def test_no_tactic_restates_doc_status_for_adrs() -> None:
    """No live tactic tells an author to give an ADR a ``doc_status`` value.

    DIRECTIVE_042 is explicit that ADR frontmatter uses the MADR ``status``
    field, never ``doc_status``. The scaffold tactic must not carry an example that
    says otherwise.
    """
    scaffold_text = _text(_TACTIC_SCAFFOLD)
    assert "doc_status: draft (PROPOSED)" not in scaffold_text
    assert "doc_status: active) when accepted" not in scaffold_text
    # The ADR guidance defers to DIRECTIVE_042 rather than
    # restating (and mis-stating) the ADR frontmatter field.
    assert "DIRECTIVE_042" in scaffold_text


def test_no_adr_step_prescribes_doc_status_value() -> None:
    """No scaffold/write step that discusses ADRs assigns a doc_status: value.

    An ADR-related step may explain the *general* doc_status schema (as a
    contrast — "never doc_status for ADRs") but must never itself pin a
    doc_status: <value> to an ADR, which is DIRECTIVE_042's exact drift bug.
    """
    # Matches two alternative drift shapes, both anchored on a word-boundary
    # ``doc_status`` mention:
    #   1. The original colon form ``doc_status: <value>`` (optionally with
    #      a backtick and/or the word "field" between the mention and the
    #      colon/paren) — e.g. ``doc_status: draft`` or ``` `doc_status`
    #      field: active```. This is a single bare value, no pipe-list
    #      required, so it also catches the original DIRECTIVE_042 drift bug.
    #   2. The looser prose-drift form that attaches a pipe-separated value
    #      list to a ``doc_status`` mention within the same clause — e.g.
    #      ``doc_status`` field (<value> | <value> | ...)`` or ``uses
    #      `doc_status` to track state (<value> | <value> | ...)``, where
    #      arbitrary words sit between the mention and the value-list
    #      opener.
    # The word-boundary requirement on ``doc_status`` itself keeps the
    # legitimate contrast — "never `doc_status`." with nothing attached —
    # and the general "doc_status schema above" prose reference (matching
    # neither alternative) from matching. This is deliberately not
    # restricted to the five canonical doc_status values: any single value
    # or pipe-list bound to a doc_status mention is drift, whatever
    # vocabulary it uses.
    doc_status_value = re.compile(
        r"\bdoc_status\b(?:`?\s*(?:field)?\s*[:(]\s*[A-Za-z]+|.{0,40}?[:(]\s*[A-Za-z]+(?:\s*\|\s*[A-Za-z]+)+)",
        re.IGNORECASE | re.DOTALL,
    )
    scaffold_adr_steps = [step for step in _load_yaml(_TACTIC_SCAFFOLD)["steps"] if "ADR" in str(step.get("title", ""))]
    assert scaffold_adr_steps, "non-vacuity: the scaffold tactic must keep an ADR-titled step for this guard to inspect"
    for tactic_path in (_TACTIC_SCAFFOLD, _TACTIC_WRITE):
        for step in _load_yaml(tactic_path)["steps"]:
            title = str(step.get("title", ""))
            if "ADR" not in title:
                continue
            text = _step_text(step)
            assert not doc_status_value.search(text), f"{tactic_path} step {step['title']!r} prescribes a doc_status value for an ADR-related step"


# --- The section count is stated exactly once ------------------------------


@pytest.mark.parametrize(
    "path",
    [_DIRECTIVE_042, _GOVERNANCE_PROFILE, _TACTIC_SCAFFOLD],
)
def test_section_count_not_restated_outside_styleguide(path: Path) -> None:
    """Only the ``common-docs`` styleguide states the section count as a number."""
    text = _text(path)
    assert not _has_number_or_word(text, needle_number="13", needle_word="thirteen"), (
        f"{path} restates the section count outside its single owner (the common-docs styleguide's own principle)"
    )


def test_styleguide_still_states_the_section_count_once() -> None:
    """The styleguide remains the ONE place the count is stated (sanity check)."""
    principles = "\n".join(_load_yaml(_STYLEGUIDE_COMMON_DOCS)["principles"])
    assert "13" in principles


def test_built_in_routing_targets_only_its_own_sanctioned_sections() -> None:
    """Every ``concern_bucket_to_section`` target is in the same block's own list.

    A repository-agnostic default must never route content to a section it
    does not itself sanction (a repository-agnostic default once routed ``how_to_internal`` /
    ``reference_policy`` / ``generated_report`` at ``development/`` and
    ``reports/`` — sections absent from the built-in default's own
    ``sanctioned_content_sections``).
    """
    block = _load_yaml(_LINT_CONFIG_ASSET)["structural_lint_config"]
    sanctioned = set(block["sanctioned_content_sections"])
    for bucket, target in block["concern_bucket_to_section"].items():
        section = target.rstrip("/")
        assert section in sanctioned, (
            f"concern_bucket_to_section[{bucket!r}] = {target!r} is not one of this block's own sanctioned_content_sections: {sorted(sanctioned)}"
        )


def test_guides_boundary_prose_matches_its_own_allowlist() -> None:
    """The ``guides_boundary`` prose must not describe a routing split the
    block's own ``concern_bucket_to_section`` does not implement."""
    block = _load_yaml(_LINT_CONFIG_ASSET)["structural_lint_config"]
    prose = block["guides_boundary"]
    concern = block["concern_bucket_to_section"]
    if "development/" in prose or "internal-audience" in prose:
        assert concern.get("how_to_internal") != concern.get("how_to_external"), (
            "guides_boundary prose describes an audience split that concern_bucket_to_section does not implement"
        )


# --- point_in_time marker values vs. the five doc_status values -------------


def test_point_in_time_markers_are_declared_asset_owned_or_in_the_five() -> None:
    """Every marker value is either a real doc_status value or declared distinct.

    ``point_in_time`` / ``closeout`` are not members of DIRECTIVE_042's
    five-value ``doc_status`` vocabulary. The lint asset's own data file must
    say so explicitly (least-disruptive option: declare, do not silently
    reuse a foreign vocabulary).
    """
    raw = _load_yaml(_LINT_CONFIG_ASSET)
    block = raw["structural_lint_config"]
    marker_values = {m["frontmatter_value"] for m in block["point_in_time_markers"]}
    declared = set(raw.get("asset_owned_marker_values", []))

    for value in marker_values:
        assert value in _DOC_STATUS_FIVE or value in declared, (
            f"marker value {value!r} is neither one of DIRECTIVE_042's five doc_status values nor declared as lint-asset-owned"
        )
    # Non-vacuous: the two known markers are exercised, not the five values.
    assert declared == {"point_in_time", "closeout"}
    assert declared.isdisjoint(_DOC_STATUS_FIVE)


# --- DIRECTIVE_037 owns the same-change documentation rule ------------------


@pytest.mark.parametrize(
    "path,forbidden",
    [
        (_DIRECTIVE_042, "in the same commit"),
        (_STYLEGUIDE_FRESHNESS, "in the same change (the source-of-truth rule)"),
        (_STYLEGUIDE_PUBLICATION, "same commit or the same mission"),
        (_PUBLISH_GUIDELINES, "same change set or queued"),
        (_PUBLISH_PROMPT, "same change set or get queued"),
    ],
)
def test_same_change_rule_not_restated_in_full(path: Path, forbidden: str) -> None:
    """The full same-change rule is stated in full only in DIRECTIVE_037."""
    text = _text(path)
    assert forbidden not in text, f"{path} still restates the same-change rule in full"


@pytest.mark.parametrize(
    "path",
    [
        _DIRECTIVE_042,
        _STYLEGUIDE_COMMON_DOCS,
        _STYLEGUIDE_FRESHNESS,
        _STYLEGUIDE_PUBLICATION,
        _PUBLISH_GUIDELINES,
        _PUBLISH_PROMPT,
    ],
)
def test_same_change_rule_sites_reference_directive_037(path: Path) -> None:
    """Every other same-change-rule site references DIRECTIVE_037 by id."""
    text = _text(path)
    assert "DIRECTIVE_037" in text or "037-living-documentation-sync" in text


# --- The lint config data file exists and loads through the asset -----------


def test_lint_config_data_file_exists_and_declares_the_pinned_key() -> None:
    raw = _load_yaml(_LINT_CONFIG_ASSET)
    assert "structural_lint_config" in raw


def test_lint_config_data_file_loads_through_the_asset_loader(monkeypatch: pytest.MonkeyPatch) -> None:
    """The unchanged loader contract: any file carrying the pinned wrapper key loads."""
    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location("docs_structural_lint_under_test", _PACKS / "assets" / "docs_structural_lint.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "docs_structural_lint_under_test", module)
    spec.loader.exec_module(module)
    config = module.load_config(_LINT_CONFIG_ASSET)
    assert "architecture" in config.curated_complete_sections


def test_common_docs_styleguide_no_longer_embeds_the_lint_config() -> None:
    """The block moves OUT of the styleguide; the styleguide keeps prose only."""
    raw = _load_yaml(_STYLEGUIDE_COMMON_DOCS)
    assert "structural_lint_config" not in raw


def test_lint_asset_manifest_declares_the_companion_data_file() -> None:
    """The asset manifest documents where its default policy data now lives."""
    manifest = _load_yaml(_LINT_ASSET_MANIFEST)
    assert "docs_structural_lint.config.yaml" in manifest.get("title", "")


def test_internal_override_styleguide_keeps_working_through_the_same_key() -> None:
    """The repository's own internal override is unaffected by the built-in move."""
    internal = _load_yaml(_REPO_ROOT / "packs" / "internal" / "styleguides" / "spec-kitty-docs-lint-config.styleguide.yaml")
    assert "structural_lint_config" in internal


# --- Documentation-validate vocabulary -> disposition contract mapping -----


@pytest.mark.parametrize("path", [_VALIDATE_GUIDELINES, _VALIDATE_PROMPT])
def test_validate_vocabulary_maps_onto_disposition_contract(path: Path) -> None:
    """The accept/mitigate/block-publish vocabulary maps pair-for-pair onto the owner's terms.

    The owner (``adversarial-squad-deployment``) defines ``accepted`` as "the
    artifact changed accordingly" and ``deferred_with_rationale`` as "valid but
    deferred", so a risk that *stands* is ``deferred_with_rationale`` and a
    risk *mitigated on the page* is ``accepted``. Word presence alone would let
    the inverted mapping (accept -> accepted) pass.
    """
    text = _text(path)
    assert "adversarial-squad-deployment" in text
    assert re.search(r"\baccept\s*->\s*`deferred_with_rationale`", text), "a risk that stands (accept) must map to deferred_with_rationale"
    assert re.search(r"\bmitigate\s*->\s*`accepted`", text), "a risk mitigated on the page must map to accepted (artifact changed accordingly)"
    assert re.search(r"\bblock-publish\s*->\s*`deferred_with_rationale`", text), "block-publish must map to deferred_with_rationale while the rework is pending"
    assert not re.search(r"\baccept\s*->\s*`accepted`", text), "accept must not map to accepted: the owner defines accepted as 'artifact changed'"
    assert not re.search(r"\bmitigate\s*->\s*`changed`", text), "mitigate (action taken on the page) must map to accepted, not changed"
