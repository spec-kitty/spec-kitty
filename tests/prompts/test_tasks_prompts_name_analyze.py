"""The tasks-family prompts must name analyze as the required pre-implement gate.

FR-015: the report and next-step sections of the software-dev ``tasks`` and
``tasks-finalize`` prompts must name ``/spec-kitty.analyze`` as the required step
before ``/spec-kitty.implement``, and state that editing the spec, plan, tasks or
charter afterwards makes the analysis report stale.

Section-scoped on purpose: an operator who just finished tasks reads the report
and next-step guidance, not the body of the prompt, so the requirement and the
staleness rule must live there.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_STEPS_DIR = _REPO_ROOT / "packs" / "built-in" / "missions" / "mission-steps" / "software-dev"

# (prompt path, marker that opens the report / next-step region) — the region
# runs from the marker to end of file.
_REGIONS: tuple[tuple[Path, str], ...] = (
    (_STEPS_DIR / "tasks" / "prompt.md", "### Step 10: Implementation Handoff Offer"),
    (_STEPS_DIR / "tasks-finalize" / "prompt.md", "### 5. Report"),
)

_STALENESS_INPUTS = ("spec", "plan", "tasks", "charter")


def _region_id(case: tuple[Path, str]) -> str:
    return case[0].relative_to(_REPO_ROOT).as_posix()


def _region(prompt_path: Path, marker: str) -> str:
    text = prompt_path.read_text(encoding="utf-8")
    assert marker in text, f"{prompt_path} lost its report/next-step marker {marker!r}"
    return text[text.index(marker) :]


@pytest.mark.parametrize(("prompt_path", "marker"), _REGIONS, ids=[_region_id(c) for c in _REGIONS])
def test_report_section_names_analyze_as_required_before_implement(prompt_path: Path, marker: str) -> None:
    region = _region(prompt_path, marker)
    assert "/spec-kitty.analyze" in region, f"{prompt_path} report/next-step section must name /spec-kitty.analyze as the pre-implement gate."
    lower = region.lower()
    assert "required" in lower, f"{prompt_path} report/next-step section must describe analyze as REQUIRED before implement, not optional."
    assert "/spec-kitty.implement" in region or "implement" in lower


@pytest.mark.parametrize(("prompt_path", "marker"), _REGIONS, ids=[_region_id(c) for c in _REGIONS])
def test_report_section_states_the_staleness_rule(prompt_path: Path, marker: str) -> None:
    region = _region(prompt_path, marker)
    lower = region.lower()
    assert "stale" in lower, f"{prompt_path} report/next-step section must state that the analysis report can go stale."
    for token in _STALENESS_INPUTS:
        assert token in lower, f"{prompt_path} staleness rule must name '{token}' as an input that invalidates the report when edited."
