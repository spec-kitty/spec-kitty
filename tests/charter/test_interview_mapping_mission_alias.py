"""RED-first single-source pickup driver + characterization guard (#2669 WP03).

Covers Rosters D (``charter.activation.activations.ALLOWED_MISSION_TYPES``) and E
(``charter.activation.synthesizer.interview_mapping._MISSION_IDENTIFIER_ANSWERS``):

* ``test_synthetic_mission_type_is_picked_up_by_both_rosters`` — genuine
  RED-first driver (C-008). Runs in an isolated subprocess (its own fresh
  interpreter) that patches ``MissionTypeRepository.default`` to a synthetic
  ``analysis`` mission-type roster *before* ``charter.activation.activations`` /
  ``charter.activation.synthesizer.interview_mapping`` are ever imported, so their
  module-level derived frozensets are computed against the synthetic roster
  on first (and only) import. Before Rosters D/E are wired to the accessor
  (i.e. while they remain hardcoded literals), this is RED: neither frozenset
  contains ``"analysis"``. After the derivation lands, it is GREEN.

  Subprocess isolation is deliberate, not incidental: an in-process
  ``importlib.reload()`` of ``charter.activation.activations`` rebinds a *new*
  ``ActivationEntry`` pydantic class object distinct from the one other
  already-imported charter schema modules (e.g. ``GovernanceConfig`` in
  ``charter/schemas.py``) captured as a field type at their own import time —
  which breaks ``isinstance``-based pydantic validation for every other test
  in the same worker for the rest of the process lifetime (reproduced via
  ``pydantic_core.ValidationError: ... not ... instance of ActivationEntry``
  when this test ran before ``test_schemas_selection.py`` in the same
  process). A subprocess sidesteps this entirely: the patched root is in
  place before first import, so no reload — and no shared-class pollution —
  is ever needed.
* ``test_hyphen_mission_type_resolves_via_underscore_alias`` — a
  green-stays-green characterization guard (per C-008, NOT a red-first
  driver) that protects the ``software_dev`` underscore-alias behavior in
  ``_section_answer_with_source`` across the Roster E derivation. A naive
  ``frozenset(builtin_mission_type_ids())`` (hyphen-only, unnormalized)
  would silently drop the underscore form and break this test.
"""

from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SHIPPED_MISSION_TYPES_DIR = _REPO_ROOT / "packs" / "built-in" / "missions" / "mission_types"

_SYNTHETIC_ANALYSIS_YAML = (
    "schema_version: 1\n"
    "id: analysis\n"
    'display_name: "Analysis"\n'
    "action_sequence:\n"
    "  - specify\n"
    "  - plan\n"
)

_SUBPROCESS_DRIVER = """
import sys
from pathlib import Path

root = Path(sys.argv[1])

from charter.offering.missions.mission_type_repository import (
    MissionTypeRepository,
    builtin_mission_type_ids,
)

MissionTypeRepository.default = classmethod(lambda cls: cls(root))
builtin_mission_type_ids.cache_clear()

import charter.activation.activations as activations_module
import charter.activation.synthesizer.interview_mapping as interview_mapping_module

assert "analysis" in activations_module.ALLOWED_MISSION_TYPES, (
    f"analysis not in ALLOWED_MISSION_TYPES={sorted(activations_module.ALLOWED_MISSION_TYPES)}"
)
assert "analysis" in interview_mapping_module._MISSION_IDENTIFIER_ANSWERS, (
    "analysis not in "
    f"_MISSION_IDENTIFIER_ANSWERS={sorted(interview_mapping_module._MISSION_IDENTIFIER_ANSWERS)}"
)
print("OK")
"""


def test_synthetic_mission_type_is_picked_up_by_both_rosters(tmp_path: Path) -> None:
    """RED-first (C-008): D/E must derive from the accessor, not a literal.

    See the module docstring for why this runs in a subprocess rather than
    monkeypatching + reloading in-process.
    """
    for shipped_yaml in _SHIPPED_MISSION_TYPES_DIR.glob("*.yaml"):
        (tmp_path / shipped_yaml.name).write_text(
            shipped_yaml.read_text(encoding="utf-8"), encoding="utf-8"
        )
    (tmp_path / "analysis.yaml").write_text(_SYNTHETIC_ANALYSIS_YAML, encoding="utf-8")

    driver_script = tmp_path / "_driver.py"
    driver_script.write_text(textwrap.dedent(_SUBPROCESS_DRIVER), encoding="utf-8")

    # Invoked via ``uv run`` (not a bare ``sys.executable`` subprocess): a raw
    # interpreter subprocess resolves the editable ``doctrine``/``charter``
    # install recorded at the *primary* checkout's last ``uv sync``, not this
    # lane worktree's own ``src/`` — ``uv run`` re-resolves the project rooted
    # at ``cwd`` so the subprocess sees the worktree's own accessor (T012-T014).
    # ``--no-sync`` (#4866 WP04 scope extension, was #4922): this call wants
    # the project environment as-is, never a resync. Without it, a bare
    # ``uv run --frozen`` silently resyncs whatever ``UV_PROJECT_ENVIRONMENT``
    # (or the default ``.venv``) currently names down to the repo's
    # ``.python-version`` pin — corrupting a concurrently-running xdist
    # worker's environment underneath it. See
    # ``tracer-design-decisions.md`` for the empirical comparison against
    # ``--python``/``--all-extras``.
    result = subprocess.run(  # noqa: S603, S607 — fixed args, no shell, test-only; `uv` resolved via PATH like every other `uv run` invocation in this suite
        ["uv", "run", "--frozen", "--no-sync", "python", str(driver_script), str(tmp_path)],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert result.returncode == 0, (
        f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
    )
    assert "OK" in result.stdout


def test_hyphen_mission_type_resolves_via_underscore_alias() -> None:
    """Green-stays-green characterization guard for the ``software_dev`` alias.

    ``resolve_sections()`` must, when ``mission_type`` carries a recognized
    identifier (here the shipped hyphen spelling ``software-dev``), prefer
    the richer ``project_intent`` narrative over the terse identifier — this
    is driven by ``_section_answer_with_source``'s reordering, which only
    triggers when ``_normalize_section_selector("software-dev")`` (i.e.
    ``"software_dev"``) is a member of ``_MISSION_IDENTIFIER_ANSWERS``. If a
    naive hyphen-only derivation dropped the underscore alias, the reorder
    would never trigger and this assertion would fail.
    """
    from charter.activation.synthesizer.interview_mapping import resolve_sections

    snapshot = {
        "mission_type": "software-dev",
        "project_intent": "Build an internal metrics platform.",
    }

    results = resolve_sections(snapshot)
    mission_type_results = [context for label, context in results if label == "mission_type"]

    assert mission_type_results
    assert mission_type_results[0]["answer"] == "Build an internal metrics platform."
    assert mission_type_results[0]["answer_source"] == "project_intent"
