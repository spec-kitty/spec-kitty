"""Acceptance contract for the ``acceptance-criteria-non-vacuity`` tactic.

Written RED-first (charter ATDD-First Discipline): every assertion here must
fail before the tactic/wiring exists, then pass once it lands.

Model: ``tests/doctrine/test_supply_chain_security_layer.py`` (direct scope
edge + depth-1/2 stability) plus additional checks for this tactic (schema
validity, content-carries-the-rules, the review prompt renders the built-in
path and names an id that actually resolves, and sibling tactics reference it
without duplicating its content).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import yaml
from jsonschema import Draft202012Validator

from typer.testing import CliRunner

from charter.activation.context_result_builders import CharterContextResult
from charter.offering.drg.loader import load_built_in_graph
from charter.offering.drg.models import DRGGraph, Relation
from charter.offering.drg.query import resolve_context
from specify_cli.cli.commands.charter import charter_app
from specify_cli.template.asset_generator import render_command_template

pytestmark = [pytest.mark.fast, pytest.mark.doctrine, pytest.mark.corpus]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TACTIC_ID = "acceptance-criteria-non-vacuity"
_TACTIC_URN = f"tactic:{_TACTIC_ID}"
_TACTIC_PATH = _REPO_ROOT / "packs" / "built-in" / "tactics" / "testing" / f"{_TACTIC_ID}.tactic.yaml"
_SCHEMA_PATH = _REPO_ROOT / "src" / "charter" / "offering" / "schemas" / "tactic.schema.yaml"
_REVIEW_PROMPT_PATH = _REPO_ROOT / "packs" / "built-in" / "missions" / "mission-steps" / "software-dev" / "review" / "prompt.md"
_SIBLING_TACTIC_PATHS = {
    "acceptance-test-first": _REPO_ROOT / "packs" / "built-in" / "tactics" / "testing" / "acceptance-test-first.tactic.yaml",
    "atdd-adversarial-acceptance": _REPO_ROOT / "packs" / "built-in" / "tactics" / "testing" / "atdd-adversarial-acceptance.tactic.yaml",
}

# Distinctive, semantically-load-bearing phrases the tactic's rule content
# must carry -- deliberately loose substrings, not the exact wording, so the
# tactic author has room to phrase the rule naturally while the probe still
# fails if the *concept* goes missing.
_REQUIRED_CONTENT_PHRASES = ("same fixture", "half", "production")
_REQUIRED_NOTE_LABELS = ("[build]", "[ratchet]", "[folded]")
_REQUIRED_NOTE_TERMS = ("no-op passable",)

#: Regeneration silently dropped the calibrator-derived
#: ``action:software-dev/review -> tactic:boring-code-review`` scope edge
#: once the review action carried an explicit, non-calibrator tactic entry
#: (the new tactic above). Restored by listing ``boring-code-review``
#: explicitly in ``review/index.yaml``; pinned here so a future regen that
#: drops it again fails loudly instead of silently.
_BORING_CODE_REVIEW_URN = "tactic:boring-code-review"


def _normalize_for_phrase_match(text: str) -> str:
    """Fold hyphens to spaces before a phrase-containment check.

    ``atdd-adversarial-acceptance``'s sentence says "same-fixture"
    (hyphenated); a bare ``"same fixture" in blob`` substring check cannot
    see it, so the no-copy guard would be silently vacuous for that exact
    wording. Both call sites that build a rule-phrase blob route through
    this helper so hyphenated and spaced phrasing match identically.
    """
    return text.replace("-", " ")


def _rule_phrase_blob(payload: dict[str, Any]) -> str:
    """Build the lower-cased, hyphen-normalized rule-prose blob for *payload*.

    Shared by the new tactic's own content check and the sibling no-copy
    guard so both read the same normalization.
    """
    blob_parts: list[str] = [str(payload.get("purpose", ""))]
    for step in payload.get("steps", []):
        blob_parts.append(str(step.get("title", "")))
        blob_parts.append(str(step.get("description", "")))
        blob_parts.extend(str(example) for example in step.get("examples", []) or [])
    return _normalize_for_phrase_match(" ".join(blob_parts).lower())


def _load_yaml(path: Path) -> dict[str, Any]:
    assert path.is_file(), f"expected doctrine artifact at {path}"
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    assert isinstance(data, dict), f"{path}: expected mapping root"
    return data


def _tactic_schema_validator() -> Draft202012Validator:
    schema = _load_yaml(_SCHEMA_PATH)
    return Draft202012Validator(schema)


@pytest.fixture(scope="module")
def graph() -> DRGGraph:
    return load_built_in_graph()


@pytest.fixture(scope="module")
def tactic_payload() -> dict[str, Any]:
    return _load_yaml(_TACTIC_PATH)


# ---------------------------------------------------------------------------
# Schema validity
# ---------------------------------------------------------------------------


class TestTacticSchemaValidity:
    def test_tactic_file_exists_and_validates_against_schema(self, tactic_payload: dict[str, Any]) -> None:
        validator = _tactic_schema_validator()
        errors = sorted(validator.iter_errors(tactic_payload), key=str)
        assert not errors, "\n".join(str(error) for error in errors)

    def test_tactic_id_matches_expected_canonical_id(self, tactic_payload: dict[str, Any]) -> None:
        assert tactic_payload.get("id") == _TACTIC_ID


# ---------------------------------------------------------------------------
# Content carries the three rules + label legend
# ---------------------------------------------------------------------------


class TestTacticContentCarriesTheRules:
    def test_steps_or_purpose_carry_the_distinctive_rule_phrases(self, tactic_payload: dict[str, Any]) -> None:
        """Every distinctive phrase must appear somewhere in the tactic's
        rule-bearing prose (purpose + step descriptions/examples). This is
        deliberately a substring probe on the real, loaded file content --
        not a synthetic dict -- so deleting the corresponding rule from the
        tactic file turns this test red.
        """
        blob = _rule_phrase_blob(tactic_payload)

        for phrase in _REQUIRED_CONTENT_PHRASES:
            assert phrase in blob, f"tactic content missing required phrase {phrase!r}; blob={blob!r}"

    def test_notes_define_all_three_delivery_labels(self, tactic_payload: dict[str, Any]) -> None:
        notes = str(tactic_payload.get("notes", ""))
        assert notes, "tactic must carry a `notes` legend (single canonical definition, C-006)"
        for label in _REQUIRED_NOTE_LABELS:
            assert label in notes, f"notes legend missing delivery label {label!r}"

    def test_notes_define_the_no_op_passable_mark(self, tactic_payload: dict[str, Any]) -> None:
        notes = str(tactic_payload.get("notes", "")).lower()
        for term in _REQUIRED_NOTE_TERMS:
            assert term in notes, f"notes legend missing no-op-passable definition ({term!r})"


# ---------------------------------------------------------------------------
# Direct SCOPE edge from action:software-dev/review
# ---------------------------------------------------------------------------


class TestResolvedContextIncludesTheTactic:
    def test_resolved_context_includes_tactic_at_depth_one(self, graph: DRGGraph) -> None:
        ctx = resolve_context(graph, "action:software-dev/review", depth=1)
        assert _TACTIC_URN in ctx.artifact_urns, f"review: resolved context missing {_TACTIC_URN}; got {sorted(ctx.artifact_urns)}"

    def test_context_resolution_is_stable_at_depth_two(self, graph: DRGGraph) -> None:
        ctx_d2 = resolve_context(graph, "action:software-dev/review", depth=2)
        assert _TACTIC_URN in ctx_d2.artifact_urns


class TestWiringIsDirectScopeNotIncidentalReachability:
    def test_review_action_has_direct_scope_edge_to_tactic(self, graph: DRGGraph) -> None:
        scoped_targets = {edge.target for edge in graph.edges_from("action:software-dev/review", Relation.SCOPE)}
        assert _TACTIC_URN in scoped_targets, f"review: no direct scope edge to {_TACTIC_URN}; scoped targets were {sorted(scoped_targets)}"

    def test_negative_control_unrelated_action_has_no_direct_scope_edge_to_tactic(self, graph: DRGGraph) -> None:
        """Negative control on the same graph fixture: an action that
        should NOT be scoped to the tactic must not have a direct scope
        edge either -- this proves the edge-check above can discriminate a
        real edge from an always-true assertion.
        """
        scoped_targets = {edge.target for edge in graph.edges_from("action:software-dev/specify", Relation.SCOPE)}
        assert _TACTIC_URN not in scoped_targets, (
            f"specify: unexpected direct scope edge to {_TACTIC_URN} (negative control failed -- the discriminating action also has the edge)"
        )


class TestReviewActionKeepsItsPreExistingBoringCodeReviewEdge:
    """Adding an explicit, non-calibrator tactic entry to the review action
    moved the DRG calibrator's derived-edge threshold and silently dropped
    the pre-existing ``action:software-dev/review -> tactic:boring-code-review``
    scope edge. ``boring-code-review`` is now listed explicitly in
    ``review/index.yaml`` alongside the new tactic; pinned here so a future
    regen that drops it again fails loudly.
    """

    def test_boring_code_review_still_has_a_direct_scope_edge(self, graph: DRGGraph) -> None:
        scoped_targets = {edge.target for edge in graph.edges_from("action:software-dev/review", Relation.SCOPE)}
        assert _BORING_CODE_REVIEW_URN in scoped_targets, f"review: no direct scope edge to {_BORING_CODE_REVIEW_URN}; scoped targets were {sorted(scoped_targets)}"

    def test_boring_code_review_still_resolves_at_depth_one_and_two(self, graph: DRGGraph) -> None:
        ctx_d1 = resolve_context(graph, "action:software-dev/review", depth=1)
        ctx_d2 = resolve_context(graph, "action:software-dev/review", depth=2)
        assert _BORING_CODE_REVIEW_URN in ctx_d1.artifact_urns
        assert _BORING_CODE_REVIEW_URN in ctx_d2.artifact_urns


# ---------------------------------------------------------------------------
# Built-in review prompt names the tactic + fetch command, and the named id
# resolves through the charter-context include path
# ---------------------------------------------------------------------------


class TestReviewPromptNamesTheTacticAndItResolves:
    def _render_built_in_review_prompt(self) -> str:
        with patch(
            "specify_cli.template.asset_generator._get_cli_version",
            return_value="0.0.0-test",
        ):
            rendered: str = render_command_template(
                template_path=_REVIEW_PROMPT_PATH,
                script_type="sh",
                agent_key="claude",
                arg_format="$ARGUMENTS",
                extension="md",
            )
            return rendered

    def test_rendered_built_in_review_prompt_names_the_tactic_id(self) -> None:
        rendered = self._render_built_in_review_prompt()
        assert _TACTIC_ID in rendered, "built-in review prompt does not name the non-vacuity tactic id"

    def test_rendered_built_in_review_prompt_names_the_fetch_command(self) -> None:
        rendered = self._render_built_in_review_prompt()
        fetch_command = f"spec-kitty charter context --include tactic:{_TACTIC_ID}"
        assert fetch_command in rendered, "built-in review prompt does not name the tactic fetch command"


# ---------------------------------------------------------------------------
# The REAL CLI command's stdout carries the labels verbatim (production
# path, not a helper).
#
# Rich's default markup parser treats "[build]"/"[ratchet]"/"[folded]" as
# style tags and silently drops them from ``console.print`` output, so a
# helper-only test could stay green while the prescribed fetch command
# printed an unreadable legend. This class drives the real
# ``spec-kitty charter context`` Typer command end to end via CliRunner.
# ---------------------------------------------------------------------------


class TestCliFetchCommandRendersLabelsVerbatim:
    def test_cli_include_tactic_prints_all_three_labels_unmangled(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            charter_app,
            ["context", "--include", f"tactic:{_TACTIC_ID}"],
        )

        assert result.exit_code == 0, result.output
        for label in _REQUIRED_NOTE_LABELS:
            assert label in result.output, f"CLI stdout is missing {label!r} -- Rich markup likely ate the bracketed legend again; full output:\n{result.output}"

    def test_negative_control_an_unknown_tactic_id_still_fails_closed(self) -> None:
        """Same-fixture negative control: the CLI path above must not just
        always exit 0 printing something -- a bogus id on the same command
        surface must fail. This proves the green test above is exercising
        real resolution, not a code path that always succeeds.
        """
        runner = CliRunner()
        result = runner.invoke(
            charter_app,
            ["context", "--include", f"tactic:{_TACTIC_ID}-does-not-exist"],
        )

        assert result.exit_code != 0, f"expected the unknown tactic id to fail closed; got exit 0 with output:\n{result.output}"

    def test_cli_action_context_prints_bracketed_text_unmangled(self) -> None:
        """Second production ``markup=False`` site: the action-scoped body
        (``console.print(result.text, markup=False)``). The real
        ``--action`` body is fetch-command based (progressive disclosure) and
        never itself carries bracketed doctrine prose, so this injects a
        deterministic stand-in result through the real production seam
        (``build_charter_context``) and drives the actual Typer command via
        CliRunner -- proving Rich markup is disabled on this site too, not
        just the ``--include`` site above.
        """
        fake_result = CharterContextResult(
            action="review",
            mode="compact",
            first_load=False,
            text="Legend: [build] [ratchet] [folded]",
            references_count=0,
            depth=1,
        )
        runner = CliRunner()
        with patch(
            "charter.activation.context.build_charter_context",
            return_value=fake_result,
        ):
            result = runner.invoke(charter_app, ["context", "--action", "review"])

        assert result.exit_code == 0, result.output
        for label in _REQUIRED_NOTE_LABELS:
            assert label in result.output, (
                f"CLI stdout is missing {label!r} for --action -- Rich markup likely ate the bracketed text again; full output:\n{result.output}"
            )


# ---------------------------------------------------------------------------
# Sibling tactics reference the new tactic without copying its content
# ---------------------------------------------------------------------------


class TestSiblingTacticsReferenceWithoutDuplicating:
    @pytest.mark.parametrize("sibling_id", sorted(_SIBLING_TACTIC_PATHS))
    def test_sibling_has_a_step_level_reference_to_the_new_tactic(self, sibling_id: str) -> None:
        payload = _load_yaml(_SIBLING_TACTIC_PATHS[sibling_id])
        found = False
        for step in payload.get("steps", []):
            for reference in step.get("references", []) or []:
                if reference.get("id") == _TACTIC_ID:
                    found = True
        assert found, f"{sibling_id} has no step-level `references` entry pointing at {_TACTIC_ID!r}"

    def test_positive_control_the_matcher_does_find_the_phrases_somewhere(self, tactic_payload: dict[str, Any]) -> None:
        """Same-fixture positive control for the no-copy guard below: run
        the identical blob-builder/matcher on the new tactic itself -- where
        the phrases are *supposed* to live -- and confirm it finds them.
        Without this, ``test_sibling_does_not_copy_the_rule_text`` could
        pass vacuously if the matcher were broken (e.g. blind to hyphenated
        wording) rather than because the sibling is actually clean.
        """
        blob = _rule_phrase_blob(tactic_payload)
        assert "same fixture" in blob, "matcher cannot see the phrase even in its canonical home"
        assert "half by half" in blob, "matcher cannot see the phrase even in its canonical home"

    @pytest.mark.parametrize("sibling_id", sorted(_SIBLING_TACTIC_PATHS))
    def test_sibling_does_not_copy_the_rule_text(self, sibling_id: str) -> None:
        """Guard against duplication (C-006): the sibling may name/point to
        the new tactic, but must not restate its rule content. We check this
        by asserting the sibling's own prose does not itself carry the same
        distinctive rule phrases -- if it did, the rule would live in two
        places. Hyphens are normalized (``_normalize_for_phrase_match``) so a
        hyphenated "same-fixture" phrasing cannot slip past a spaced-only
        probe -- see the positive control above for proof the matcher can
        still see the phrase where it belongs.
        """
        payload = _load_yaml(_SIBLING_TACTIC_PATHS[sibling_id])
        blob = _rule_phrase_blob(payload)

        assert "half by half" not in blob, f"{sibling_id} appears to copy the half-by-half proof rule text"

        if "same fixture" in blob:
            # A sibling is allowed at most a one-line gloss explicitly
            # marked as a summary of that tactic -- so a bare mention of the
            # phrase is not itself a violation. It is a violation only when
            # NOT marked as such a summary.
            marker = _normalize_for_phrase_match(f"summary of tactic {_TACTIC_ID}")
            assert marker in blob, (
                f"{sibling_id} carries the same-fixture wording without marking it as a "
                f"one-line summary of {_TACTIC_ID} ({marker!r} not found) -- an explicit "
                "summary marker is required, not a bare restatement"
            )
