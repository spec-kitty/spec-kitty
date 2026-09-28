"""Served prompts, step contracts and agent profiles reference single owners.

Served prompts, step contracts, and agent profiles must reference the
single owners (the squad procedure with its disposition contract,
``test-first-bug-fixing``, and the supply-chain doctrine) rather than
restating their content:

- The software-dev ``implement``/``plan``/``review`` prompts, the three
  served guideline files, the software-dev step contracts, and the eight
  agent profiles in ``_PROFILE_IDS`` reference ``DIRECTIVE_051`` /
  the ``supply-chain-install-safety`` tactic instead of restating its
  five threat-class pillars.
- Step contracts under ``missions/built_in_step_contracts/`` cite
  directives as ``DIRECTIVE_NNN``, never the ``NNN-slug`` form, and every
  such citation resolves to a real directive.
- The implement prompt assigns draft-PR opening to the orchestrator (the
  WP agent pushes and reports) and contains no raw ``git commit``
  instruction -- every commit instruction uses ``spec-kitty safe-commit``.
- The four profiles that carry the bug-fixing rule (implementer-ivan,
  node-norris, frontend-freddy, drupal-dries) declare
  ``test-first-bug-fixing`` in ``collaboration.operating-procedures``, and
  the profiles that touch BDD cite ``bdd-scenario-formulation``.

Retired ids (``bug-fixing-checklist``, ``behavior-driven-development``,
``adversarial-evidence-contract``) are guarded once, in
``test_retired_ids_absent.py``.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PACKS = _REPO_ROOT / "packs" / "built-in"
_SOFTWARE_DEV = _PACKS / "missions" / "mission-steps" / "software-dev"
_STEP_CONTRACTS_DIR = _PACKS / "missions" / "built_in_step_contracts"
_AGENT_PROFILES_DIR = _PACKS / "agent_profiles"
_DIRECTIVES_DIR = _PACKS / "directives"

_PROMPT_FILES = [_SOFTWARE_DEV / action / "prompt.md" for action in ("implement", "plan", "review")]
_GUIDELINE_FILES = [_SOFTWARE_DEV / action / "guidelines.md" for action in ("implement", "plan", "review")]
_STEP_CONTRACT_FILES = sorted(_STEP_CONTRACTS_DIR.glob("*.step-contract.yaml"))
_SOFTWARE_DEV_STEP_CONTRACTS = [_STEP_CONTRACTS_DIR / f"{action}.step-contract.yaml" for action in ("implement", "plan", "review")]

_PROFILE_IDS = (
    "implementer-ivan",
    "node-norris",
    "frontend-freddy",
    "drupal-dries",
    "reviewer-renata",
    "python-pedro",
    "java-jenny",
    "architect-alphonso",
)
_PROFILE_FILES = [_AGENT_PROFILES_DIR / f"{profile_id}.agent.yaml" for profile_id in _PROFILE_IDS]

_RETARGET_PROFILES = ("implementer-ivan", "node-norris", "frontend-freddy", "drupal-dries")

# The five ecosystem-neutral pillars DIRECTIVE_051 states once (plus the
# Node-LTS baseline concern that lives in the JS/TS
# toolguide -- a profile that still frames it as a 051 matter is restating
# scope, not just vocabulary). A served surface "restates the pillar list"
# when two or more distinct pillar-term variants co-occur within a short
# window of text -- a single incidental mention of one term in passing is
# fine; enumerating even a partial checklist is not.
_PILLAR_TERMS = (
    "registry authenticity",
    "official-registry",
    "package freshness",
    "freshness visibility",
    "lifecycle-script",
    "lifecycle script",
    "lockfile",
    "IoC",
    "indicator of compromise",
    "indicators of compromise",
    "Active LTS",
    "non-LTS",
)
_RESTATEMENT_WINDOW = 300
_RESTATEMENT_THRESHOLD = 2

_SLUG_DIRECTIVE_CITATION = re.compile(r"(?<![A-Za-z0-9_])\d{3}-[a-z][a-z0-9-]*")
_DIRECTIVE_ID_CITATION = re.compile(r"DIRECTIVE_(\d{3})")

_KNOWN_DIRECTIVE_IDS = {path.stem.split("-", 1)[0].zfill(3) for path in _DIRECTIVES_DIR.glob("*.directive.yaml")}


def _read(path: Path) -> str:
    assert path.exists(), f"expected file missing: {path}"
    return path.read_text(encoding="utf-8")


def _max_distinct_pillars_in_window(text: str, window: int = _RESTATEMENT_WINDOW) -> int:
    """Largest number of distinct pillar terms found within any `window`-char span."""
    hits: list[tuple[int, str]] = []
    lowered = text.lower()
    for term in _PILLAR_TERMS:
        for match in re.finditer(re.escape(term.lower()), lowered):
            hits.append((match.start(), term))
    hits.sort()
    best = 0
    for start, _term in hits:
        distinct = {t for pos, t in hits if start <= pos < start + window}
        best = max(best, len(distinct))
    return best


class TestNoPillarRestatement:
    """No served prompt/guideline/step-contract/profile enumerates the pillar list."""

    @pytest.mark.parametrize("path", _PROMPT_FILES, ids=lambda p: p.parent.name)
    def test_prompts_do_not_restate_pillars(self, path: Path) -> None:
        text = _read(path)
        worst = _max_distinct_pillars_in_window(text)
        assert worst < _RESTATEMENT_THRESHOLD, (
            f"{path}: restates {worst} supply-chain pillar terms within {_RESTATEMENT_WINDOW} chars -- reference DIRECTIVE_051 instead"
        )

    @pytest.mark.parametrize("path", _GUIDELINE_FILES, ids=lambda p: p.parent.name)
    def test_guidelines_do_not_restate_pillars(self, path: Path) -> None:
        text = _read(path)
        worst = _max_distinct_pillars_in_window(text)
        assert worst < _RESTATEMENT_THRESHOLD, (
            f"{path}: restates {worst} supply-chain pillar terms within {_RESTATEMENT_WINDOW} chars -- reference DIRECTIVE_051 instead"
        )

    @pytest.mark.parametrize("path", _SOFTWARE_DEV_STEP_CONTRACTS, ids=lambda p: p.stem)
    def test_software_dev_step_contracts_do_not_restate_pillars(self, path: Path) -> None:
        text = _read(path)
        worst = _max_distinct_pillars_in_window(text)
        assert worst < _RESTATEMENT_THRESHOLD, (
            f"{path}: restates {worst} supply-chain pillar terms within {_RESTATEMENT_WINDOW} chars -- reference DIRECTIVE_051 instead"
        )

    @pytest.mark.parametrize("path", _PROFILE_FILES, ids=lambda p: p.stem)
    def test_profiles_do_not_restate_pillars(self, path: Path) -> None:
        text = _read(path)
        worst = _max_distinct_pillars_in_window(text)
        assert worst < _RESTATEMENT_THRESHOLD, (
            f"{path}: restates {worst} supply-chain pillar terms within {_RESTATEMENT_WINDOW} chars -- reference DIRECTIVE_051 instead"
        )


class TestStepContractSlugCitationsConverted:
    """Step contracts cite DIRECTIVE_NNN, never the retired NNN-slug form."""

    @pytest.mark.parametrize("path", _STEP_CONTRACT_FILES, ids=lambda p: p.stem)
    def test_no_slug_directive_citation_remains(self, path: Path) -> None:
        text = _read(path)
        slugs = _SLUG_DIRECTIVE_CITATION.findall(text)
        assert not slugs, f"{path}: retired NNN-slug directive citation(s) remain (convert to DIRECTIVE_NNN): {slugs}"

    @pytest.mark.parametrize("path", _STEP_CONTRACT_FILES, ids=lambda p: p.stem)
    def test_every_directive_id_citation_resolves(self, path: Path) -> None:
        text = _read(path)
        ids = _DIRECTIVE_ID_CITATION.findall(text)
        unresolved = [num for num in ids if num not in _KNOWN_DIRECTIVE_IDS]
        assert not unresolved, f"{path}: DIRECTIVE_NNN citation(s) do not resolve to a known directive: {unresolved}"


class TestImplementPromptOrchestratorOpensDraftPr:
    """#5078: the WP agent pushes and reports; the orchestrator opens the draft PR."""

    def test_orchestrator_opens_draft_pr_and_records_ci_run(self) -> None:
        text = _read(_SOFTWARE_DEV / "implement" / "prompt.md")
        assert "orchestrator" in text.lower(), "implement prompt must name the orchestrator as the draft-PR opener"
        # The WP-agent instruction must be push + report, not open-a-PR-itself.
        assert re.search(r"push.{0,120}(report|orchestrator)", text, re.IGNORECASE | re.DOTALL) or re.search(
            r"orchestrator.{0,200}(draft PR|pull request)", text, re.IGNORECASE | re.DOTALL
        ), "implement prompt does not clearly hand draft-PR opening to the orchestrator"

    def test_no_raw_git_commit_instruction(self) -> None:
        text = _read(_SOFTWARE_DEV / "implement" / "prompt.md")
        # Allow `git commit` only as part of documentation of what safe-commit
        # does internally; forbid a raw instruction telling the agent to run it.
        raw_commits = [line for line in text.splitlines() if re.search(r"\bgit commit\b", line) and "safe-commit" not in line and "safe_commit" not in line]
        assert not raw_commits, f"implement prompt still instructs a raw `git commit` outside safe-commit: {raw_commits}"

    def test_commit_instructions_use_safe_commit(self) -> None:
        text = _read(_SOFTWARE_DEV / "implement" / "prompt.md")
        assert "spec-kitty safe-commit" in text, "implement prompt must instruct commits via `spec-kitty safe-commit`"


class TestProfileBugFixingOwner:
    """The four bug-fixing profiles declare test-first-bug-fixing as their operating procedure."""

    @pytest.mark.parametrize("profile_id", _RETARGET_PROFILES)
    def test_retargeted_profile_declares_operating_procedure(self, profile_id: str) -> None:
        text = _read(_AGENT_PROFILES_DIR / f"{profile_id}.agent.yaml")
        assert "operating-procedures" in text, f"{profile_id}: missing collaboration.operating-procedures block"
        assert re.search(r"operating-procedures:\s*\n(\s*-.*\n)*\s*-\s*test-first-bug-fixing", text), (
            f"{profile_id}: collaboration.operating-procedures does not declare test-first-bug-fixing"
        )

    @pytest.mark.parametrize("profile_id", ("node-norris", "frontend-freddy", "java-jenny"))
    def test_bdd_profiles_cite_bdd_scenario_formulation(self, profile_id: str) -> None:
        text = _read(_AGENT_PROFILES_DIR / f"{profile_id}.agent.yaml")
        assert "bdd-scenario-formulation" in text, f"{profile_id}: does not cite the bdd-scenario-formulation tactic"
