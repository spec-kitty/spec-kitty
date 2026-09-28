"""The project's own governance surfaces follow the single-owner doctrine.

Three independent surfaces:

1. This repository's OWN ``.kittify/charter/charter.md`` and charter
   activation store (binding governance, not a shipped pack artifact) name no
   retired doctrine id, still compile, and Standing Order #1 references the
   ``adversarial-squad-deployment`` procedure instead of restating its
   point-cut list.
2. ``docs/development/reference/quality-and-tech-debt-standing-orders.md``
   points at that procedure under "1. The Adversarial Squad Cadence" instead
   of restating the point-cut table.
3. The "adversarial squad" glossary term lives in the built-in glossary pack
   (not the internal one), and the behaviour/behavior spelling alias resolves
   to the canonical term.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from charter.offering.glossary_packs.repository import GlossaryPackRepository

from tests.doctrine._single_owner_detectors import (
    has_headcount_language,
    restates_point_cut_list,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast, pytest.mark.doctrine]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CHARTER_MD = _REPO_ROOT / ".kittify" / "charter" / "charter.md"
_STANDING_ORDERS_DOC = _REPO_ROOT / "docs" / "development" / "reference" / "quality-and-tech-debt-standing-orders.md"
_BUILT_IN_GLOSSARY = _REPO_ROOT / "packs" / "built-in" / "glossary_packs" / "spec-kitty-core.glossary-pack.yaml"
_INTERNAL_GLOSSARY = _REPO_ROOT / "packs" / "internal" / "glossary_packs" / "spk-internal.glossary-pack.yaml"

#: ``boring-code-review`` is deliberately excluded from this substring-check
#: list: the retirement table's successor for the retired TACTIC of that
#: name is a STYLEGUIDE with the IDENTICAL stem, so it is expected -- and
#: correct -- for activated_styleguides to still carry it after migration.
#: ``test_charter_standing_order_1_does_not_name_retired_styleguide`` below
#: pins the one prose spot that must not name the retired
#: ``adversarial-squad-cadence`` styleguide.
_RETIRED_STEMS = (
    "adversarial-squad-cadence",
    "bug-fixing-checklist",
    "locality-of-change",
    "common-docs-curation",
    "behavior-driven-development",
    "iterative-deepening-review",
    "tracker-organisation-workflow",
)

#: A Standing Order #1 that restates the point-cut list. Positive control: the
#: shared detector must flag this fixture (it restates 4 point-cut tokens),
#: proving the detector is not vacuous.
_RESTATING_STANDING_ORDER_1_FIXTURE = """\
1. **Adversarial squad cadence.** Run a bounded, profile-loaded adversarial squad
   at every planning point-cut (pre-spec / post-spec / post-plan / post-tasks)
   before proceeding — one lens per agent, strongest model for the hard lenses.
   Optional and advisory, never a hard gate. -> `adversarial-squad-cadence` styleguide.
"""


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _section(text: str, start_marker: str, end_marker: str) -> str:
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


# --------------------------------------------------------------------------- #
# Positive control -- the shared detector is not vacuous
# --------------------------------------------------------------------------- #


def test_detector_flags_a_standing_order_1_that_restates_the_point_cut_list() -> None:
    """Sanity check on the detector itself, not on live content."""
    assert restates_point_cut_list(_RESTATING_STANDING_ORDER_1_FIXTURE)


# --------------------------------------------------------------------------- #
# The project charter carries no retired id and still compiles
# --------------------------------------------------------------------------- #


#: DIRECTIVE_024's own id/title/prose legitimately says "locality-of-change"
#: (it is a DIFFERENT, never-retired stem under ``activated_directives`` --
#: the migration's own docstring: "a different stem ... never even
#: inspected"). Matches the catalog id form (``024-locality-of-change``) and
#: the prose form (a directive prose sentence naming its own topic).
_LEGITIMATE_LOCALITY_OF_CHANGE_MENTIONS_RE = re.compile(r"024-locality-of-change|DIRECTIVE_024 for locality-of-change discipline")


def test_no_retired_doctrine_id_remains_activated_under_kittify() -> None:
    """Every retired stem is gone from the project's own charter surfaces.

    A ``history:``/changelog line or ``evidence/`` snapshot may still name a
    retired id (immutable record); an activation list must not.
    """
    kittify_dir = _REPO_ROOT / ".kittify"
    surfaces = [
        kittify_dir / "config.yaml",
        kittify_dir / "charter" / "charter.yaml",
        kittify_dir / "charter" / "references.yaml",
        kittify_dir / "charter" / "interview" / "answers.yaml",
    ]
    for path in surfaces:
        if not path.exists():
            continue
        text = _LEGITIMATE_LOCALITY_OF_CHANGE_MENTIONS_RE.sub("", _read(path))
        for stem in _RETIRED_STEMS:
            assert stem not in text, f"{path} still names retired id {stem!r}"


def test_boring_code_review_tactic_is_retired_its_successor_styleguide_is_not() -> None:
    """The one stem the retired tactic and its successor styleguide share.

    ``activated_tactics`` must drop ``boring-code-review``; the successor
    ``activated_styleguides`` entry of the same name is the expected,
    correct post-migration state, not a leftover.
    """
    charter_yaml = _read(_REPO_ROOT / ".kittify" / "charter" / "charter.yaml")
    tactics_block = _section(charter_yaml, "activated_tactics:\n", "\nactivated_styleguides:")
    styleguides_block = _section(charter_yaml, "activated_styleguides:\n", "\nactivated_toolguides:")
    assert "- boring-code-review" not in tactics_block
    assert "- boring-code-review" in styleguides_block


def test_charter_compiles_against_the_projects_own_answers_without_unknown_artifact_error() -> None:
    """Consumer-facing proof: the fail-closed compiler no longer hard-fails.

    Uses the same route ``tests/charter/test_model_task_routing_resolves.py``
    and ``tests/doctrine/test_activation_parity_guard.py`` already pin
    (``compile_charter`` against this project's REAL
    ``.kittify/charter/interview/answers.yaml``) -- the CLI-level
    ``spec-kitty charter context`` command reads pre-compiled surfaces and
    does not exercise this fail-closed path itself, so a CLI smoke check
    would not prove it.
    """
    from charter.activation.compiler import compile_charter
    from charter.activation.interview import read_interview_answers

    answers_path = _REPO_ROOT / ".kittify" / "charter" / "interview" / "answers.yaml"
    interview = read_interview_answers(answers_path)
    assert interview is not None, "expected the project's real interview answers to load"

    compile_charter(mission=interview.mission, interview=interview, repo_root=_REPO_ROOT)


# --------------------------------------------------------------------------- #
# Charter prose is a pointer, not a restatement
# --------------------------------------------------------------------------- #


def test_charter_standing_order_1_does_not_restate_point_cut_list() -> None:
    text = _read(_CHARTER_MD)
    order_1 = _section(text, "1. **Adversarial squad cadence.**", "2. **Campsite cleaning")
    assert not restates_point_cut_list(order_1), (
        "Standing Order #1 restates the point-cut list; it must reference the adversarial-squad-deployment procedure instead (single owner)."
    )
    assert "adversarial-squad-deployment" in order_1, "Standing Order #1 must point at the owning procedure by id."


def test_charter_standing_order_1_does_not_name_retired_styleguide() -> None:
    text = _read(_CHARTER_MD)
    order_1 = _section(text, "1. **Adversarial squad cadence.**", "2. **Campsite cleaning")
    assert "adversarial-squad-cadence" not in order_1


def test_charter_md_has_no_headcount_language_in_standing_order_1() -> None:
    text = _read(_CHARTER_MD)
    order_1 = _section(text, "1. **Adversarial squad cadence.**", "2. **Campsite cleaning")
    assert not has_headcount_language(order_1)


def test_standing_orders_doc_does_not_restate_point_cut_table() -> None:
    text = _read(_STANDING_ORDERS_DOC)
    section = _section(text, "## 1. The Adversarial Squad Cadence", "## 2. Campsite")
    assert not restates_point_cut_list(section), (
        "quality-and-tech-debt-standing-orders.md §1 restates the point-cut table; it must point at the adversarial-squad-deployment procedure."
    )
    assert "adversarial-squad-deployment" in section


# --------------------------------------------------------------------------- #
# Glossary: single owner + the behaviour/behavior alias
# --------------------------------------------------------------------------- #


def test_adversarial_squad_term_lives_in_built_in_not_internal() -> None:
    built_in_text = _read(_BUILT_IN_GLOSSARY)
    internal_text = _read(_INTERNAL_GLOSSARY)
    assert "surface: adversarial squad" in built_in_text
    assert "surface: adversarial squad" not in internal_text


def test_behaviour_behavior_alias_resolves() -> None:
    """A term surface->term index built from the pack finds the alias.

    Mirrors the ``aliases`` round-trip already proven in
    ``tests/doctrine/glossary_packs/test_repository.py`` -- this pin adds the
    resolution step: an alias must map back to its owning term's surface.
    """
    repo = GlossaryPackRepository(built_in_dir=_BUILT_IN_GLOSSARY.parent)
    pack = repo.get("spec-kitty-core")
    assert pack is not None

    alias_index: dict[str, str] = {}
    for term in pack.terms:
        for alias in term.aliases or ():
            alias_index[alias] = term.surface

    assert alias_index.get("behavior-driven development") == "behaviour-driven development", (
        "the behavior-driven-development alias must resolve to the canonical behaviour-driven-development term surface"
    )
