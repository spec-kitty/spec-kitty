"""The ledger ADR's *current* visibility decision may only name real commands.

`docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md` decides, in §5 and in its
**#E** deliverable bullet, which command surface reports the migration ledger. Those two
statements are the ones a reader (or a re-planning agent) acts on, so a command path that
does not exist there is a trap: it fails when run, and it invites a second read surface.

This module binds those two statements to the live Typer surface. It fails when the current
decision names a `spec-kitty …` command path that is not registered, and it requires the
shipped surface, `spec-kitty migrate ledger`, to be named.

Scope is deliberately narrow. Plenty of ADRs record proposals that were never built while
remaining valuable history; a tree-wide "every command in every ADR exists" gate would be
wrong. The historical paragraph inside §5 is therefore free prose (it names the retired
`doctor migrations` / `upgrade --list-applied` proposal *without* a `spec-kitty` prefix), and
this guard only scans the two current-decision slices.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import typer

from scripts.docs._typer_walker import walk
from scripts.docs.check_cli_reference_freshness import extract_referenced_paths

pytestmark = [pytest.mark.docs_scoped]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LEDGER_ADR = _REPO_ROOT / "docs" / "adr" / "4.x" / "2026-10-17-1-explicit-migration-ledger.md"

#: The shipped read surface the current visibility decision must name.
_SHIPPED_SURFACE: tuple[str, ...] = ("migrate", "ledger")

_SECTION_5_HEADING = "### 5. "
_NEXT_SECTION_PREFIX = "### 6. "
_E_BULLET_RE = re.compile(r"^- \*\*#E\b.*?(?=^- \*\*#F\b|\n## )", re.MULTILINE | re.DOTALL)

#: Any of these in §5 labels the retired proposal as history rather than as the decision.
_HISTORY_MARKERS: tuple[str, ...] = ("historical", "not built", "was not built", "rejected")


def _read_adr() -> str:
    assert _LEDGER_ADR.is_file(), f"ADR is missing: {_LEDGER_ADR.relative_to(_REPO_ROOT)}"
    return _LEDGER_ADR.read_text(encoding="utf-8")


def _visibility_section(text: str) -> str:
    """Return §5's body (from its heading up to the next `### ` heading)."""
    start = text.find(_SECTION_5_HEADING)
    assert start != -1, "§5 ('### 5. ') is missing from the ledger ADR"
    end = text.find(_NEXT_SECTION_PREFIX, start)
    assert end != -1, "The heading after §5 ('### 6. ') is missing from the ledger ADR"
    return text[start:end]


def _e_deliverable_bullet(text: str) -> str:
    """Return the `- **#E** …` follow-up bullet, with its wrapped lines."""
    start = text.find("- **#E")
    assert start != -1, "The #E deliverable bullet is missing from the ledger ADR"
    match = _E_BULLET_RE.search(text, start)
    assert match is not None, "The #E deliverable bullet is not terminated as expected"
    return match.group(0)


def _registered_paths() -> set[tuple[str, ...]]:
    import specify_cli

    with pytest.MonkeyPatch.context() as env:
        env.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "1")
        env.setenv("SPEC_KITTY_NO_UPGRADE_CHECK", "1")
        app = specify_cli._build_app()
    assert isinstance(app, typer.Typer), "specify_cli._build_app() must return a Typer app"
    return {entry.path for entry in walk(app)}


def _referenced_paths() -> set[tuple[str, ...]]:
    text = _read_adr()
    slices = f"{_visibility_section(text)}\n\n{_e_deliverable_bullet(text)}"
    return set(extract_referenced_paths(slices))


def test_current_visibility_decision_names_the_shipped_surface() -> None:
    """§5 and #E must name `spec-kitty migrate ledger` — the surface that shipped."""
    referenced = _referenced_paths()
    assert _SHIPPED_SURFACE in referenced, (
        f"The ledger ADR's current visibility decision (§5 / #E) must name 'spec-kitty migrate ledger'; extracted command paths were {sorted(referenced)}"
    )


def test_current_visibility_decision_names_only_registered_commands() -> None:
    """No phantom command path in §5 or #E: every named path must be registered."""
    referenced = _referenced_paths()
    assert referenced, (
        "Expected §5 / #E to name at least one 'spec-kitty …' command path; the scan found none (did the sections get reworded away from code spans?)"
    )
    registered = _registered_paths()
    unregistered = sorted(path for path in referenced if path not in registered)
    assert not unregistered, (
        "The ledger ADR's current visibility decision names command paths that are "
        f"not registered on the live CLI surface: {[' '.join(p) for p in unregistered]}. "
        "Name the shipped surface ('spec-kitty migrate ledger') or move the retired "
        "proposal into the marked-historical paragraph without a 'spec-kitty' prefix."
    )


def test_retired_proposal_survives_as_marked_history() -> None:
    """The rejected proposal stays in §5, labelled history rather than presented as current.

    Deleting it would erase *why* the decision changed, and keeping the names without the
    label would present a retired design as the live one. Assert the two retired names and a
    historical marker, not exact sentences, so the wording stays editable.
    """
    section = _visibility_section(_read_adr())
    missing = [name for name in ("doctor migrations", "upgrade --list-applied") if name not in section]
    assert not missing, f"§5 no longer records the rejected visibility proposal (missing: {missing}); the decision trail must keep it as marked history."
    lowered = section.lower()
    assert any(marker in lowered for marker in _HISTORY_MARKERS), (
        "§5 mentions the retired 'doctor migrations' / 'upgrade --list-applied' proposal without labelling it historical; a reader cannot tell it was never built."
    )
