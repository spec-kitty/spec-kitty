"""``map-requirements`` grammar-consumer tests (WP03).

Mission ``requirement-id-grammar-01M3NRCA`` WP03: ``map-requirements`` becomes
a consumer of the WP01 grammar (``specify_cli.requirement_mapping.grammar``)
and stops destroying authored data (FR-005), accepts SC/letter-suffixed input
(FR-006), reports exactly one reason per rejected ref (FR-010/FR-019), and
explains its refusals by naming the grammar (FR-012).

T015's two repros were red-first proof against the WP01-merged base (charter
C-011, ADR 2026-07-17-1): a first commit containing only this file, RED. Both
were demoted from ``@pytest.mark.regression`` once green (T019).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.tasks import app as tasks_app
from specify_cli.cli.commands.agent.tasks_map_requirements import (
    _canonical_input_refs,
    _mr_accepted_refs_by_wp,
    _mr_classify_wp_refs,
    _mr_sorted_spec_ids,
)
from specify_cli.frontmatter import read_frontmatter
from specify_cli.requirement_mapping import grammar

pytestmark = [pytest.mark.unit, pytest.mark.fast]
runner = CliRunner()

#: Declares FR-001, FR-002, FR-006a, NFR-001 and SC-001 -- every id T015's two
#: repros and T019's focused tests exercise. Table shape for FRs/NFRs, a
#: bold-led bullet for the success criterion (the template shapes WP01 makes
#: "declared").
SPEC_CONTENT = """\
# Spec

## Functional Requirements

| ID | Requirement | Acceptance Criteria | Status |
| --- | --- | --- | --- |
| FR-001 | First requirement | Done | proposed |
| FR-002 | Second requirement | Done | proposed |
| FR-006a | Sixth requirement variant | Done | proposed |

## Non-Functional Requirements

| ID | Requirement |
| --- | --- |
| NFR-001 | Performance |

## Success Criteria

- **SC-001**: Something measurable holds.
"""


@pytest.fixture(autouse=True)
def _bypass_protected_branch_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    """The documented operator escape hatch for fixtures committing on a
    protected branch (PR #1850 guard-bypass fix)."""
    monkeypatch.setenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", "1")
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "0")


def _setup_feature(
    tmp_path: Path,
    *,
    wp_refs: dict[str, str] | None = None,
) -> Path:
    """A minimal feature directory with ``spec.md`` and raw-seeded WP files.

    ``wp_refs`` maps a WP id to the RAW YAML text of its ``requirement_refs``
    block (e.g. ``'["SC-001", "FR-006A"]'`` or ``"[]"``) so the on-disk bytes
    seeded here are exactly what the test author wrote -- not whatever a
    normalising reader/writer would have produced.
    """
    feature_dir = tmp_path / "kitty-specs" / "001-test"
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)

    (feature_dir / "spec.md").write_text(SPEC_CONTENT, encoding="utf-8")

    for wp_id, refs_literal in (wp_refs or {}).items():
        (tasks_dir / f"{wp_id}-test.md").write_text(
            f'---\nwork_package_id: "{wp_id}"\ntitle: "{wp_id}"\nrequirement_refs: {refs_literal}\n---\n\n# {wp_id}\n',
            encoding="utf-8",
        )

    return feature_dir


def _raw_refs(feature_dir: Path, wp_id: str) -> list[str]:
    """Raw on-disk ``requirement_refs`` (un-normalised) for *wp_id*."""
    tasks_dir = feature_dir / "tasks"
    wp_file = next(tasks_dir.glob(f"{wp_id}*.md"))
    frontmatter, _ = read_frontmatter(wp_file)
    return frontmatter.get("requirement_refs", [])


def _invoke(*args: str) -> object:
    return runner.invoke(tasks_app, ["map-requirements", *args, "--json"])


@patch("specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out")
@patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
@patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
def test_research_kind_is_accepted_only_for_research_mission(mock_locate: Mock, mock_slug: Mock, mock_branch: Mock, tmp_path: Path) -> None:
    mock_locate.return_value = tmp_path
    mock_slug.return_value = "001-test"
    mock_branch.return_value = (tmp_path, "main")
    feature_dir = _setup_feature(tmp_path, wp_refs={"WP01": "[]"})
    (feature_dir / "spec.md").write_text("# Research\n\n- **DR-001**: Collect records.\n")

    refused = _invoke("--wp", "WP01", "--refs", "DR-001")
    assert refused.exit_code == 1

    (feature_dir / "meta.json").write_text(json.dumps({"mission_type": "research"}))
    accepted = _invoke("--wp", "WP01", "--refs", "dr-001")
    assert accepted.exit_code == 0, accepted.stdout
    assert _raw_refs(feature_dir, "WP01") == ["DR-001"]


class TestMapRequirementsGrammarRepros:
    """T015: red-first repros for #2991 and #3519, demoted to focused tests
    once green (T019)."""

    @patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
    @patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
    @patch("specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out")
    def test_existing_items_survive_byte_identical_in_place(
        self,
        mock_branch: Mock,
        mock_slug: Mock,
        mock_locate: Mock,
        tmp_path: Path,
    ) -> None:
        """#2991: map-requirements must never erase or respell an authored ref (FR-005)."""
        mock_locate.return_value = tmp_path
        mock_slug.return_value = "001-test"
        mock_branch.return_value = (tmp_path, "main")
        feature_dir = _setup_feature(tmp_path, wp_refs={"WP01": '["SC-001", "FR-006A"]'})

        result = _invoke("--wp", "WP01", "--refs", "FR-002")

        # Assert the disk state FIRST: the write precedes the stale gate, so a
        # partial write is observable even on a refusing (exit 1) run -- this
        # makes the RED failure message show the erasure, not an incidental
        # exit code.
        assert _raw_refs(feature_dir, "WP01") == ["SC-001", "FR-006A", "FR-002"]
        assert result.exit_code == 0, result.stdout

    @patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
    @patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
    @patch("specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out")
    def test_declared_sc_and_suffixed_refs_accepted_canonical(
        self,
        mock_branch: Mock,
        mock_slug: Mock,
        mock_locate: Mock,
        tmp_path: Path,
    ) -> None:
        """#3519 part 2: declared SC and letter-suffixed IDs are accepted in
        canonical form (FR-006)."""
        mock_locate.return_value = tmp_path
        mock_slug.return_value = "001-test"
        mock_branch.return_value = (tmp_path, "main")
        feature_dir = _setup_feature(tmp_path, wp_refs={"WP02": "[]"})

        result = _invoke("--wp", "WP02", "--refs", "SC-001,FR-006a")

        assert result.exit_code == 0, result.stdout
        assert _raw_refs(feature_dir, "WP02") == ["SC-001", "FR-006a"]
        payload = json.loads(result.stdout.strip())
        assert payload["result"] == "success"


@patch("specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out")
@patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
@patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
class TestMapRequirementsGrammarFocused:
    """T019: focused tests over every named behaviour (non-vacuity: every
    refusal/absence assertion carries a same-fixture positive control)."""

    def test_dedup_by_canonical_form_keeps_stored_spelling(self, mock_locate: Mock, mock_slug: Mock, mock_branch: Mock, tmp_path: Path) -> None:
        mock_locate.return_value = tmp_path
        mock_slug.return_value = "001-test"
        mock_branch.return_value = (tmp_path, "main")
        feature_dir = _setup_feature(tmp_path, wp_refs={"WP01": '["FR-006A"]'})

        dedup_result = _invoke("--wp", "WP01", "--refs", "FR-006a")
        assert dedup_result.exit_code == 0, dedup_result.stdout
        assert _raw_refs(feature_dir, "WP01") == ["FR-006A"]

        # Positive control: a genuinely new ref on the same fixture appends.
        append_result = _invoke("--wp", "WP01", "--refs", "FR-002")
        assert append_result.exit_code == 0, append_result.stdout
        assert _raw_refs(feature_dir, "WP01") == ["FR-006A", "FR-002"]

    def test_undeclared_sc_refused_unknown_no_write(self, mock_locate: Mock, mock_slug: Mock, mock_branch: Mock, tmp_path: Path) -> None:
        mock_locate.return_value = tmp_path
        mock_slug.return_value = "001-test"
        mock_branch.return_value = (tmp_path, "main")
        feature_dir = _setup_feature(tmp_path, wp_refs={"WP01": "[]"})

        result = _invoke("--wp", "WP01", "--refs", "SC-009")
        assert result.exit_code == 1
        payload = json.loads(result.stdout.strip())
        assert payload["error"] == "Invalid requirement refs"
        assert payload["unknown_refs"] == ["SC-009"]
        # FR-012 parity: the unknown_spec_id refusal names the parsed set the
        # same way the malformed refusal does (test_pre_write_malformed_refusal_
        # names_grammar_no_write below), not just the "Available:" hint prose.
        assert payload["parsed_spec_ids"] == ["FR-001", "FR-002", "FR-006a", "NFR-001", "SC-001"]
        assert _raw_refs(feature_dir, "WP01") == []

        # Positive control (FR-006 pairing): the declared SC-001 is accepted.
        control = _invoke("--wp", "WP01", "--refs", "SC-001")
        assert control.exit_code == 0, control.stdout
        assert _raw_refs(feature_dir, "WP01") == ["SC-001"]

    def test_foreign_qualified_never_blocks_or_covers(self, mock_locate: Mock, mock_slug: Mock, mock_branch: Mock, tmp_path: Path) -> None:
        mock_locate.return_value = tmp_path
        mock_slug.return_value = "001-test"
        mock_branch.return_value = (tmp_path, "main")
        feature_dir = _setup_feature(tmp_path, wp_refs={"WP01": "[]"})

        result = _invoke("--wp", "WP01", "--refs", "other-mission-01KAAAAA#FR-001")
        assert result.exit_code == 0, result.stdout
        payload = json.loads(result.stdout.strip())
        assert "FR-001" in payload["coverage"]["unmapped_functional"]
        assert _raw_refs(feature_dir, "WP01") == ["other-mission-01KAAAAA#FR-001"]

        # Positive control: the plain (local, unqualified) FR-001 covers it.
        control = _invoke("--wp", "WP01", "--refs", "FR-001")
        assert control.exit_code == 0, control.stdout
        control_payload = json.loads(control.stdout.strip())
        assert "FR-001" not in control_payload["coverage"]["unmapped_functional"]

    def test_kept_rejected_ref_on_mapped_wp_then_replace_recovers(self, mock_locate: Mock, mock_slug: Mock, mock_branch: Mock, tmp_path: Path) -> None:
        mock_locate.return_value = tmp_path
        mock_slug.return_value = "001-test"
        mock_branch.return_value = (tmp_path, "main")
        feature_dir = _setup_feature(tmp_path, wp_refs={"WP01": '["FR_009"]'})

        result = _invoke("--wp", "WP01", "--refs", "FR-001")
        assert result.exit_code == 1
        payload = json.loads(result.stdout.strip())
        assert payload["stale_ref_reasons"]["WP01"]["malformed"] == ["FR_009"]
        # T017: reported, not erased -- the malformed item survives the write.
        assert _raw_refs(feature_dir, "WP01") == ["FR_009", "FR-001"]

        # --replace is the documented recovery.
        replace_result = _invoke("--wp", "WP01", "--refs", "FR-001", "--replace")
        assert replace_result.exit_code == 0, replace_result.stdout
        assert _raw_refs(feature_dir, "WP01") == ["FR-001"]

    def test_foreign_only_stale_set_passes_but_malformed_addition_fails(self, mock_locate: Mock, mock_slug: Mock, mock_branch: Mock, tmp_path: Path) -> None:
        mock_locate.return_value = tmp_path
        mock_slug.return_value = "001-test"
        mock_branch.return_value = (tmp_path, "main")
        feature_dir = _setup_feature(
            tmp_path,
            wp_refs={
                "WP01": "[]",
                "WP02": '["other-mission-01KAAAAA#FR-013"]',
                "WP03": '["other-mission-01KAAAAA#FR-014"]',
            },
        )

        # WP02 carries ONLY a foreign-qualified ref -- mapping the unrelated
        # WP01 still runs the ALL-WP stale gate, and it passes silently.
        passes = _invoke("--wp", "WP01", "--refs", "FR-001")
        assert passes.exit_code == 0, passes.stdout

        # Add a genuinely malformed token to WP02 directly (map-requirements
        # itself would refuse to WRITE a malformed NEW ref -- this simulates
        # a pre-existing stale item, e.g. authored by hand or a prior tool).
        wp02_file = next((feature_dir / "tasks").glob("WP02*.md"))
        wp02_file.write_text(
            '---\nwork_package_id: "WP02"\ntitle: "WP02"\nrequirement_refs: ["other-mission-01KAAAAA#FR-013", "FR_001"]\n---\n\n# WP02\n',
            encoding="utf-8",
        )

        fails = _invoke("--wp", "WP01", "--refs", "FR-002")
        assert fails.exit_code == 1
        payload = json.loads(fails.stdout.strip())
        assert payload["stale_ref_reasons"]["WP02"]["foreign_qualified"] == ["other-mission-01KAAAAA#FR-013"]
        assert payload["stale_ref_reasons"]["WP02"]["malformed"] == ["FR_001"]

        # C6: a foreign_qualified citation is never "stale" -- it must never
        # appear in stale_refs (whose hint invites --replace, i.e. deletion),
        # even for a WP (WP02) that IS listed there for its genuine malformed
        # offender. And WP03, whose ONLY ref is foreign-qualified, must never
        # be listed in stale_refs at all, even though the payload as a whole
        # IS emitted (blocking on WP02's malformed ref).
        assert payload["stale_refs"]["WP02"] == ["FR_001"]
        assert "WP03" not in payload["stale_refs"]
        assert payload["stale_ref_reasons"]["WP03"]["foreign_qualified"] == ["other-mission-01KAAAAA#FR-014"]

    def test_pre_write_malformed_refusal_names_grammar_no_write(self, mock_locate: Mock, mock_slug: Mock, mock_branch: Mock, tmp_path: Path) -> None:
        mock_locate.return_value = tmp_path
        mock_slug.return_value = "001-test"
        mock_branch.return_value = (tmp_path, "main")
        feature_dir = _setup_feature(tmp_path, wp_refs={"WP01": "[]"})
        wp_file = next((feature_dir / "tasks").glob("WP01*.md"))
        before = wp_file.read_bytes()

        result = _invoke("--wp", "WP01", "--refs", "FR_001")
        assert result.exit_code == 1
        payload = json.loads(result.stdout.strip())
        assert payload["parsed_spec_ids"] == ["FR-001", "FR-002", "FR-006a", "NFR-001", "SC-001"]
        assert "kind FR, NFR, C or SC" in payload["hint"]
        assert wp_file.read_bytes() == before

    def test_replace_lists_what_it_removed_positive_control(self, mock_locate: Mock, mock_slug: Mock, mock_branch: Mock, tmp_path: Path) -> None:
        mock_locate.return_value = tmp_path
        mock_slug.return_value = "001-test"
        mock_branch.return_value = (tmp_path, "main")
        feature_dir = _setup_feature(tmp_path, wp_refs={"WP01": '["FR_009", "FR-001", "SC-001"]'})

        result = _invoke("--wp", "WP01", "--refs", "FR-001", "--replace")
        assert result.exit_code == 0, result.stdout
        payload = json.loads(result.stdout.strip())
        assert payload["replaced_refs_removed"] == {"WP01": ["FR_009", "SC-001"]}
        assert _raw_refs(feature_dir, "WP01") == ["FR-001"]

        # Positive control: without --replace, existing items survive and the
        # key is absent entirely. Deliberately a DIFFERENT WP (WP02, not
        # WP01): WP01's own fixture still carries the malformed FR_009, so a
        # non-replace run against it would exit 1 (stale gate) rather than
        # demonstrate the "absent key on success" contract this control is for.
        feature_dir2 = _setup_feature(tmp_path, wp_refs={"WP02": '["FR-002"]'})
        control = _invoke("--wp", "WP02", "--refs", "FR-001")
        assert control.exit_code == 0, control.stdout
        control_payload = json.loads(control.stdout.strip())
        assert "replaced_refs_removed" not in control_payload
        assert _raw_refs(feature_dir2, "WP02") == ["FR-002", "FR-001"]

    def test_legacy_scalar_string_splits_into_single_id_items(self, mock_locate: Mock, mock_slug: Mock, mock_branch: Mock, tmp_path: Path) -> None:
        """T017 step 1, edge 1 (B1): a legacy SCALAR ``requirement_refs``
        value (``"FR-001, FR-002"``, one comma-joined string, not a list) is
        the ONE defined exception to FR-005's "existing items byte-identical"
        contract. The typed WP model splits a scalar string into list items
        before this command ever sees it (``status/wp_metadata.py``'s
        ``_normalize_legacy_fields``, tokenised through the single grammar
        authority) -- a list of single-ID tokens is the only item form that
        can ever reach disk, so "byte-identical" degrades to "every id
        survives, in order, as its own item" for this one legacy shape.
        """
        mock_locate.return_value = tmp_path
        mock_slug.return_value = "001-test"
        mock_branch.return_value = (tmp_path, "main")
        feature_dir = _setup_feature(tmp_path, wp_refs={"WP01": '"FR-001, FR-002"'})

        result = _invoke("--wp", "WP01", "--refs", "NFR-001")

        assert result.exit_code == 0, result.stdout
        # No id is lost and order is preserved -- the positive control that
        # keeps this from being read as a silent respell/erasure.
        assert _raw_refs(feature_dir, "WP01") == ["FR-001", "FR-002", "NFR-001"]

    def test_legacy_compound_list_item_splits_into_single_id_items(self, mock_locate: Mock, mock_slug: Mock, mock_branch: Mock, tmp_path: Path) -> None:
        """T017 step 1, edge 1 (B1), the list-shaped sibling: a single list
        item holding a comma-joined pair (``["FR-001, FR-002"]``) is tokenised
        the SAME way as the bare-scalar case above -- ``read_all_wp_raw_
        requirement_refs`` -> ``grammar.tokenize_refs`` splits each list item
        on ``[,\\s]+`` regardless of whether the value arrived as a scalar or
        as one list entry. Same defined-behaviour exception to FR-005
        byte-identity; same positive control (no id lost, order preserved)."""
        mock_locate.return_value = tmp_path
        mock_slug.return_value = "001-test"
        mock_branch.return_value = (tmp_path, "main")
        feature_dir = _setup_feature(tmp_path, wp_refs={"WP01": '["FR-001, FR-002"]'})

        result = _invoke("--wp", "WP01", "--refs", "NFR-001")

        assert result.exit_code == 0, result.stdout
        assert _raw_refs(feature_dir, "WP01") == ["FR-001", "FR-002", "NFR-001"]

    def test_non_string_frontmatter_item_fails_typed_write_file_unchanged(self, mock_locate: Mock, mock_slug: Mock, mock_branch: Mock, tmp_path: Path) -> None:
        """T017: a WP carrying a non-string ``requirement_refs`` item (e.g. an
        int) reaches ``plan_mapping``/``to_write`` as a synthetic
        ``<NON_STRING:...>`` token (never written to disk as a string) -- the
        typed frontmatter read in ``_mr_write_frontmatter`` fails BEFORE any
        write, so the file is left byte-unchanged."""
        mock_locate.return_value = tmp_path
        mock_slug.return_value = "001-test"
        mock_branch.return_value = (tmp_path, "main")
        feature_dir = _setup_feature(tmp_path, wp_refs={"WP01": "[42]"})
        wp_file = next((feature_dir / "tasks").glob("WP01*.md"))
        before = wp_file.read_bytes()

        result = _invoke("--wp", "WP01", "--refs", "FR-001")

        assert result.exit_code == 1
        assert wp_file.read_bytes() == before

    def test_batch_parity_canonicalizes(self, mock_locate: Mock, mock_slug: Mock, mock_branch: Mock, tmp_path: Path) -> None:
        mock_locate.return_value = tmp_path
        mock_slug.return_value = "001-test"
        mock_branch.return_value = (tmp_path, "main")
        feature_dir = _setup_feature(tmp_path, wp_refs={"WP01": "[]"})

        batch = json.dumps({"WP01": ["sc-001", "FR-006A"]})
        result = runner.invoke(tasks_app, ["map-requirements", "--batch", batch, "--json"])
        assert result.exit_code == 0, result.stdout
        assert _raw_refs(feature_dir, "WP01") == ["SC-001", "FR-006a"]

    def test_batch_comma_joined_item_splits_into_two_refs(self, mock_locate: Mock, mock_slug: Mock, mock_branch: Mock, tmp_path: Path) -> None:
        """C4: a ``--batch`` list item may itself be a comma-joined pair --
        the shell must route it through ``grammar.tokenize_refs`` (the same
        ``[,\\s]+`` split stored items get), not accept it verbatim as one
        token."""
        mock_locate.return_value = tmp_path
        mock_slug.return_value = "001-test"
        mock_branch.return_value = (tmp_path, "main")
        feature_dir = _setup_feature(tmp_path, wp_refs={"WP01": "[]"})

        batch = json.dumps({"WP01": ["FR-001, FR-002"]})
        result = runner.invoke(tasks_app, ["map-requirements", "--batch", batch, "--json"])
        assert result.exit_code == 0, result.stdout
        assert _raw_refs(feature_dir, "WP01") == ["FR-001", "FR-002"]

    def test_refs_whitespace_separated_splits_into_two_refs(self, mock_locate: Mock, mock_slug: Mock, mock_branch: Mock, tmp_path: Path) -> None:
        """C4: ``--refs`` split on ``,`` only before this fold; whitespace-
        separated tokens (no comma) must also be accepted as separate refs
        via ``grammar.tokenize_refs``."""
        mock_locate.return_value = tmp_path
        mock_slug.return_value = "001-test"
        mock_branch.return_value = (tmp_path, "main")
        feature_dir = _setup_feature(tmp_path, wp_refs={"WP01": "[]"})

        result = _invoke("--wp", "WP01", "--refs", "FR-001 FR-002")
        assert result.exit_code == 0, result.stdout
        assert _raw_refs(feature_dir, "WP01") == ["FR-001", "FR-002"]

        # Positive control (same fixture): a genuinely malformed token,
        # whitespace-joined with a well-formed one, is still refused -- the
        # shared tokenizer splits the input, it never widens what's accepted.
        control = _invoke("--wp", "WP01", "--refs", "FR-001 FR_bad")
        assert control.exit_code == 1
        assert _raw_refs(feature_dir, "WP01") == ["FR-001", "FR-002"]


class TestCanonicalInputRefs:
    """T016 pure helper: ``_canonical_input_refs``."""

    def test_letter_suffix_lowercased(self) -> None:
        assert _canonical_input_refs(["fr-006A"]) == ["FR-006a"]

    def test_success_criterion_uppercased(self) -> None:
        assert _canonical_input_refs(["sc-001"]) == ["SC-001"]

    def test_foreign_qualified_canonicalized(self) -> None:
        assert _canonical_input_refs(["other-mission-01KAAAAA#fr-013"]) == ["other-mission-01KAAAAA#FR-013"]

    def test_malformed_underscore_kept_verbatim(self) -> None:
        assert _canonical_input_refs(["FR_001"]) == ["FR_001"]

    def test_compound_constraint_kept_verbatim(self) -> None:
        assert _canonical_input_refs(["C-007-mission"]) == ["C-007-mission"]


class TestMrClassifyWpRefs:
    """T018 pure helper: ``_mr_classify_wp_refs``."""

    def test_one_reason_per_ref_all_three_buckets(self) -> None:
        declared = {"FR-001"}
        result = _mr_classify_wp_refs(
            {"WP01": ["FR_1", "FR-999", "other-mission-01KAAAAA#FR-001", "FR-001"]},
            declared,
        )
        assert result["WP01"] == {
            grammar.MALFORMED: ["FR_1"],
            grammar.UNKNOWN_SPEC_ID: ["FR-999"],
            grammar.FOREIGN_QUALIFIED: ["other-mission-01KAAAAA#FR-001"],
        }

    def test_every_wp_present_gets_all_three_keys_even_when_empty(self) -> None:
        result = _mr_classify_wp_refs({"WP01": ["FR-001"]}, {"FR-001"})
        assert result["WP01"] == {
            grammar.MALFORMED: [],
            grammar.UNKNOWN_SPEC_ID: [],
            grammar.FOREIGN_QUALIFIED: [],
        }


class TestMrAcceptedRefsByWp:
    """T018 (3b) pure helper: ``_mr_accepted_refs_by_wp``."""

    def test_rejected_refs_never_counted(self) -> None:
        declared = {"FR-001"}
        result = _mr_accepted_refs_by_wp({"WP01": ["FR-001", "other-mission-01KAAAAA#FR-013"]}, declared)
        assert result["WP01"] == ["FR-001"]

    def test_positive_control_plain_wp_shows_both(self) -> None:
        declared = {"FR-001", "FR-002"}
        result = _mr_accepted_refs_by_wp({"WP01": ["FR-001", "FR-002"]}, declared)
        assert result["WP01"] == ["FR-001", "FR-002"]

    def test_wp_with_no_accepted_refs_is_omitted(self) -> None:
        result = _mr_accepted_refs_by_wp({"WP01": ["FR_1"]}, {"FR-001"})
        assert "WP01" not in result


def test_mr_sorted_spec_ids_shared_helper() -> None:
    assert _mr_sorted_spec_ids({"FR-002", "FR-001"}) == ["FR-001", "FR-002"]
