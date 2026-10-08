"""Active charter teaching surfaces use the canonical selection keys."""

from __future__ import annotations

from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[2]
_SURFACES = (
    _REPO_ROOT / "src/charter/offering/skills/spk-charter-governance/SKILL.md",
    _REPO_ROOT / "src/charter/offering/skills/spk-charter-governance/references/charter-governance-workflow.md",
    _REPO_ROOT / "docs/context/charter-overview.md",
    _REPO_ROOT / "docs/context/governance-files.md",
    _REPO_ROOT / "docs/guides/how-to/governance/setup-governance.md",
)


def test_teaching_surfaces_do_not_offer_retired_doctrine_selection_keys() -> None:
    retired_prefix = "governance.doctrine" + "."
    offenders = [path.relative_to(_REPO_ROOT) for path in _SURFACES if retired_prefix in path.read_text(encoding="utf-8")]

    assert not offenders, f"retired charter selection keys remain in: {offenders}"
