"""Structural pin for the mission-identity migration page (#6760).

``docs/migrations/mission-id-canonical-identity.md`` documents the
``spec-kitty doctor identity`` audit. Its state list and JSON samples drifted
from the live CLI contract (issue #6760: states ``ok``/``legacy``/``conflict``
and a ``status``/``total``/``ok``/``conflicts`` sample the CLI no longer
prints), because — unlike ``docs/api/cli-commands.md`` — a migrations page has
no CLI-reference freshness check. This suite pins the page to the *imported*
live contract so that drift fails CI instead of recurring.

Contract sources (imported, never restated here):

- ``specify_cli.status.identity_audit.IDENTITY_STATES`` — the five state
  labels, in report order;
- ``IdentityState.to_dict()`` — the ``missions[]`` row keys;
- ``specify_cli.cli.commands._identity_audit._build_identity_json`` — the
  report's top-level keys, including the conditional ``residue_remedies``.

Following the ``tests/docs/test_artifact_placement_seam_page.py`` precedent,
this suite asserts **structure, not prose**: which states the page documents
and which keys its samples carry. It never pins sentences.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from specify_cli.cli.commands._identity_audit import _build_identity_json
from specify_cli.status.identity_audit import IDENTITY_STATES, IdentityState, summarize

pytestmark = [pytest.mark.unit]

REPO_ROOT = Path(__file__).resolve().parents[2]
PAGE_PATH = REPO_ROOT / "docs" / "migrations" / "mission-id-canonical-identity.md"

#: A row with every field populated — the full ``missions[]`` row key set.
_FULL_ROW = IdentityState(
    path=Path("/repo/kitty-specs/001-auth-system"),
    slug="001-auth-system",
    mission_id="01J6XW9KQT7M0YB3N4R5CQZ2EX",
    mission_number=1,
    state="assigned",
)
#: A ``residue`` row — carries the conditional ``residue_reason`` field.
_RESIDUE_ROW = IdentityState(
    path=Path("/repo/kitty-specs/leftover-junk"),
    slug="leftover-junk",
    mission_id=None,
    mission_number=None,
    state="residue",
    residue_reason="no_meta",
)

# ---------------------------------------------------------------------------
# Live contract, derived from the report builder itself
# ---------------------------------------------------------------------------


def _live_report_keys(states: list[IdentityState]) -> set[str]:
    """The top-level keys ``doctor identity --json`` prints for *states*."""
    report = _build_identity_json(
        states,
        summarize(states),
        {},
        {},
        fail_on_triggered=False,
    )
    assert isinstance(report, dict)
    return set(report)


#: Keys every report carries, from an all-``assigned`` report (no residue).
_BASE_REPORT_KEYS: set[str] = _live_report_keys([_FULL_ROW])
#: Keys a report with at least one ``residue`` row additionally carries.
_RESIDUE_REPORT_KEYS: set[str] = _live_report_keys([_FULL_ROW, _RESIDUE_ROW]) - _BASE_REPORT_KEYS
#: The ``missions[]`` row key set, from the serialiser itself.
_ROW_KEYS: set[str] = set(_FULL_ROW.to_dict())


# ---------------------------------------------------------------------------
# Page parsing helpers
# ---------------------------------------------------------------------------


def _page_text() -> str:
    assert PAGE_PATH.is_file(), f"missing migration page: {PAGE_PATH}"
    return PAGE_PATH.read_text(encoding="utf-8")


def _audit_report_samples(text: str) -> list[dict[str, Any]]:
    """Every fenced JSON block in the page that is a ``doctor identity`` report.

    A report is recognized structurally: it carries ``summary`` and
    ``missions`` keys. Other JSON-ish blocks on the page are ignored.
    """
    samples: list[dict[str, Any]] = []
    for match in re.finditer(r"```json\n(.*?)```", text, flags=re.DOTALL):
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and "summary" in payload and "missions" in payload:
            samples.append(payload)
    return samples


def _documented_states(text: str) -> set[str]:
    """The state labels the page's audit-state bullet list documents.

    Scoped to the bullet list of Step 2 (between "classifies every mission:"
    and the section's first fenced block), then matched on the
    ``- ``state`` —`` bullet shape used by the page (and by the CLI's own help
    text), so a state the page fails to document — or a stale one it still
    documents — breaks set equality with ``IDENTITY_STATES``.
    """
    scope = re.split(r"classifies every mission", text, maxsplit=1)
    assert len(scope) == 2, "page no longer carries the audit-state bullet list intro"
    segment = re.split(r"```", scope[1], maxsplit=1)[0]
    return set(re.findall(r"^- `([a-z_]+)`", segment, flags=re.MULTILINE))


# ---------------------------------------------------------------------------
# The pin
# ---------------------------------------------------------------------------


def test_page_documents_exactly_the_live_states() -> None:
    """The audit-state list names exactly the five live states."""
    assert _documented_states(_page_text()) == set(IDENTITY_STATES)


def test_page_carries_at_least_two_audit_report_samples() -> None:
    """Both audit steps (legacy present, and clean after backfill) show samples."""
    samples = _audit_report_samples(_page_text())
    assert len(samples) >= 2, "expected a Step 2 sample and a Step 4 sample"
    states = [s["summary"] for s in samples]
    assert any(s.get("legacy", 0) > 0 for s in states), "no sample shows a legacy mission"
    assert any(s.get("legacy", 0) == 0 and s.get("residue", 0) == 0 for s in states), "no sample shows a clean post-backfill project"


@pytest.mark.parametrize("index", [0, 1], ids=["step-2-sample", "step-4-sample"])
def test_audit_report_samples_match_the_live_contract(index: int) -> None:
    """Every audit sample's keys equal the live report contract's keys."""
    samples = _audit_report_samples(_page_text())
    assert len(samples) > index, f"expected at least {index + 1} audit report samples"
    sample = samples[index]

    top = set(sample)
    assert top & _BASE_REPORT_KEYS == _BASE_REPORT_KEYS, f"sample {index} is missing live report keys: {_BASE_REPORT_KEYS - top}"
    assert top - _BASE_REPORT_KEYS <= _RESIDUE_REPORT_KEYS, (
        f"sample {index} carries keys the live report never prints: {top - _BASE_REPORT_KEYS - _RESIDUE_REPORT_KEYS}"
    )

    summary = sample["summary"]
    assert isinstance(summary, dict)
    assert set(summary) == set(IDENTITY_STATES), f"sample {index} summary keys {sorted(summary)} != live states {sorted(IDENTITY_STATES)}"

    missions = sample["missions"]
    assert isinstance(missions, list) and missions, f"sample {index} has no missions[] rows"
    for row in missions:
        assert isinstance(row, dict)
        assert set(row) == _ROW_KEYS, f"sample {index} missions[] row keys {sorted(row)} != live row keys {sorted(_ROW_KEYS)}"
        assert row["state"] in IDENTITY_STATES

    for report_key in ("duplicate_prefixes", "ambiguous_selectors"):
        value = sample[report_key]
        assert isinstance(value, dict)
        for rows in value.values():
            for row in rows:
                assert set(row) == _ROW_KEYS

    assert isinstance(sample["fail_on_triggered"], bool)


@pytest.mark.parametrize("index", [0, 1], ids=["step-2-sample", "step-4-sample"])
def test_residue_remedies_present_exactly_when_a_residue_row_exists(index: int) -> None:
    """``residue_remedies`` is the live contract's only conditional key (#5875)."""
    samples = _audit_report_samples(_page_text())
    assert len(samples) > index
    sample = samples[index]
    has_residue_row = any(row["state"] == "residue" for row in sample["missions"])
    has_remedies = "residue_remedies" in sample
    assert has_remedies == has_residue_row, (
        f"sample {index}: residue_remedies={has_remedies} but residue row present={has_residue_row}; "
        "the live report prints residue_remedies only when at least one residue row exists"
    )


def test_page_backfill_transcript_matches_live_output_shape() -> None:
    """The Step 3 transcript is the live ``backfill-identity`` summary.

    The live command prints a summary table (see
    ``spec-kitty/cli/commands/migrate_cmd.py``), never the per-mission
    "legacy -> minted" walk with a trailing git-commit line the page used to
    show.
    """
    text = _page_text()
    step3 = re.split(r"## Step 3", text, maxsplit=1)
    assert len(step3) == 2, "page no longer carries a Step 3 backfill section"
    segment = re.split(r"## Step 4", step3[1], maxsplit=1)[0]
    blocks = re.findall(r"```text\n(.*?)```", segment, flags=re.DOTALL)
    assert blocks, "Step 3 no longer shows a backfill output transcript"
    transcript = blocks[0]
    for live_line in (
        "backfill-identity summary",
        "Total missions scanned",
        "Written (mission_id)",
        "Skipped (already set)",
        "Errors",
        "Number coerced",
    ):
        assert live_line in transcript, f"Step 3 transcript lacks the live line {live_line!r}"
    for fictional_line in ("Scanning kitty-specs", "legacy -> minted", "Git commit:"):
        assert fictional_line not in transcript, f"Step 3 transcript still shows the fictional line {fictional_line!r}"


def test_page_carries_no_stale_contract_tokens() -> None:
    """No removed contract key, state or claim survives anywhere in the page."""
    text = _page_text()
    for stale in (
        '"status"',
        '"conflicts"',
        '"total"',
        '"dir"',
        "legacy_present",
        "- `ok`",
        "- `conflict`",
        "conflicts are present",
    ):
        assert stale not in text, f"page still carries the removed contract token {stale!r}"
