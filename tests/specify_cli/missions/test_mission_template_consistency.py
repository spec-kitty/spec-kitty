"""Global consistency guard for packaged mission prompt templates.

Every step in a packaged ``mission-runtime.yaml`` declares a ``prompt_template``
(or ``None``). At runtime, ``spec-kitty next`` resolves that template one of two
ways:

1. **Composition-driven** -- the step's action is dispatched through
   ``StepContractExecutor`` composition (via ``charter.resolve_mission_type_context``).
   These steps never read a file from ``command-templates/``; the built-in step
   contracts under ``src/charter/offering/missions/built_in_step_contracts/`` are
   authoritative, and prompt templates live under
   ``src/charter/offering/missions/mission-steps/{mission}/{step}/prompt.md``.
2. **Legacy CLI-driven** -- the step's action falls through to
   ``prompt_builder._build_template_prompt`` which calls
   ``resolve_command(f"{action}.md", ..., mission=<mission>)``.

FR-010 (charter-doctrine-mission-type-configuration-01KSWJVX): all command
templates were migrated verbatim from ``src/specify_cli/missions/*/command-templates/``
to ``src/charter/offering/missions/mission-steps/``. The old ``command-templates/``
directories are deleted. The upgrade migration pipeline (which deploys agent
command files) is rewired to the new doctrine path. The ``spec-kitty next``
runtime resolver for non-composed steps is a known follow-up tracked separately.

Steps that are NOT yet routed through composition but whose templates exist in
the doctrine layer must be added to ``KNOWN_CLI_DRIVEN`` so the gap is explicit
and not silent.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from runtime.next._internal_runtime.schema import load_mission_template_file
from runtime.next.runtime_bridge_composition import _should_dispatch_via_composition

pytestmark = pytest.mark.fast


_REPO_ROOT = Path(__file__).resolve().parents[3]
_MISSIONS_ROOT = _REPO_ROOT / "src" / "specify_cli" / "missions"
_DOCTRINE_STEPS_ROOT = _REPO_ROOT / "packs" / "built-in" / "missions" / "mission-steps"


# (mission_key, prompt_template) pairs whose steps are not yet routed through
# composition but whose templates live in the doctrine layer after the FR-010
# migration. Each entry must carry a reason. These are KNOWN GAPS: the
# ``spec-kitty next`` runtime resolver tier-5 path (command-templates) no
# longer has the files; routing them through composition is tracked separately.
KNOWN_CLI_DRIVEN: dict[tuple[str, str], str] = {
    # research/documentation declare an ``accept`` step but never had
    # command-templates/ to begin with.
    ("research", "accept.md"): (
        "research mission never shipped command-templates/; accept prompt "
        "resolution is a known latent gap tracked separately"
    ),
    ("documentation", "accept.md"): (
        "documentation mission never shipped command-templates/; accept "
        "prompt resolution is a known latent gap tracked separately"
    ),
    # FR-010 migration: command-templates/ deleted; template now lives in
    # doctrine (software-dev/accept/prompt.md). Runtime resolver wiring is a
    # follow-up tracked separately.
    ("software-dev", "accept.md"): (
        "FR-010: command-templates/ deleted; accept template is in "
        "src/charter/offering/missions/mission-steps/software-dev/accept/prompt.md. "
        "Runtime resolver wiring (non-composed path) is a follow-up."
    ),
    # FR-010 migration: discovery step references research.md; template now
    # lives in doctrine (software-dev/research/prompt.md).
    ("software-dev", "research.md"): (
        "FR-010: command-templates/ deleted; discovery step's research.md "
        "template is in src/charter/offering/missions/mission-steps/software-dev/research/prompt.md. "
        "Runtime resolver wiring (non-composed path) is a follow-up."
    ),
}


def _packaged_missions() -> list[Path]:
    """Return every packaged mission directory that ships a runtime YAML."""
    missions: list[Path] = []
    for child in sorted(_MISSIONS_ROOT.iterdir()):
        if not child.is_dir():
            continue
        if (child / "mission-runtime.yaml").is_file():
            missions.append(child)
    return missions


def _mission_keys() -> list[str]:
    return [m.name for m in _packaged_missions()]


def test_packaged_missions_discovered() -> None:
    """Sanity: the loader sees the shipped missions, including software-dev."""
    keys = _mission_keys()
    assert keys, "no packaged missions with mission-runtime.yaml were discovered"
    assert "software-dev" in keys


@pytest.mark.parametrize("mission_dir", _packaged_missions(), ids=_mission_keys())
def test_every_prompt_template_is_resolvable(mission_dir: Path) -> None:
    """Each step's ``prompt_template`` is composed, in doctrine, or allow-listed.

    After FR-010 migration (WP02), ``command-templates/`` directories are
    deleted and templates live under ``src/charter/offering/missions/mission-steps/``.
    Composition-driven steps read from charter.offering via StepContractExecutor.
    Non-composed steps that are allow-listed in KNOWN_CLI_DRIVEN are documented
    known gaps where runtime resolver wiring is a follow-up.
    """
    runtime_path = mission_dir / "mission-runtime.yaml"
    template = load_mission_template_file(runtime_path)
    mission_key = template.mission.key

    problems: list[str] = []
    for step in template.steps:
        prompt_template = step.prompt_template
        if not prompt_template:
            # Steps without a prompt_template carry no template contract.
            continue

        # Composition-driven steps never read command-templates/; their
        # templates live in doctrine and are handled by StepContractExecutor.
        if _should_dispatch_via_composition(mission_key, step.id, repo_root=_REPO_ROOT):
            continue

        # Explicitly allow-listed known gaps (runtime resolver wiring pending).
        if (mission_key, prompt_template) in KNOWN_CLI_DRIVEN:
            continue

        # Non-composed steps not in KNOWN_CLI_DRIVEN: the template MUST exist
        # in the doctrine layer (FR-010) so at minimum the content is not lost,
        # even if the runtime resolver wiring is still pending.
        stem = Path(prompt_template).stem  # e.g. "accept" from "accept.md"
        doctrine_candidate = _DOCTRINE_STEPS_ROOT / mission_key / stem / "prompt.md"
        if not doctrine_candidate.is_file():
            problems.append(
                f"mission '{mission_key}' step '{step.id}' references "
                f"prompt_template '{prompt_template}' but no doctrine template "
                f"exists at {doctrine_candidate} (and the step is neither "
                f"composition-driven nor allow-listed in KNOWN_CLI_DRIVEN). "
                f"FR-010 requires all templates to exist in the doctrine layer."
            )

    assert not problems, "\n".join(problems)


def test_software_dev_accept_template_in_doctrine() -> None:
    """Regression guard: the software-dev accept template exists in the doctrine layer.

    FR-010 (charter-doctrine-mission-type-configuration-01KSWJVX) moved all
    command templates from ``src/specify_cli/missions/*/command-templates/`` to
    ``src/charter/offering/missions/mission-steps/``. The ``accept`` step's template
    must be present at the new location so no content is silently lost.
    """
    accept_template = _DOCTRINE_STEPS_ROOT / "software-dev" / "accept" / "prompt.md"
    assert accept_template.is_file(), (
        f"software-dev accept template missing at {accept_template}; "
        "FR-010 requires it in the doctrine layer."
    )
    body = accept_template.read_text(encoding="utf-8")
    assert body.strip(), "accept/prompt.md is empty"
    assert "spec-kitty accept" in body, (
        "accept/prompt.md should instruct the operator to run 'spec-kitty accept'"
    )
