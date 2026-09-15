"""All-four-types + Go ``internal/`` coverage for the project path-convention override (#3016, WP02).

STRICTLY TEST-ONLY. This module proves the *by-construction* breadth of WP01's override: because the
override resolves at the single shared ``validators.paths.validate_mission_paths`` seam (reached via
``acceptance.summary_core.evaluate_path_conventions``), every built-in mission type honors it identically
— not just software-dev. It also pins the two composition edges the contract calls out:

* an artifact-routed key (``deliverables``) is *ignored*, so mission-surface artifact routing is never
  flipped (C-010 / precedence-contract "Artifact-routing invariant"); and
* for a research mission, a project override composes with research's ``path_prefix`` in the documented
  order — override remap first, prefix second (precedence-contract step 3).

Per-type doctrine defaults are READ from the real canonical ``mission.yaml`` files (never assumed), so a
future doctrine edit that moves a default surfaces here instead of silently diverging from the fixture.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import specify_cli
from specify_cli.acceptance.summary_core import evaluate_path_conventions
from specify_cli.config.path_conventions import (
    ARTIFACT_ROUTED_KEYS,
    load_project_path_conventions,
)
from specify_cli.mission import Mission
from specify_cli.validators.paths import validate_mission_paths

pytestmark = [pytest.mark.unit, pytest.mark.fast]

# Canonical packaged mission directory (``src/specify_cli/missions/<type>/mission.yaml``). Located via the
# installed ``specify_cli`` package rather than a hand-built relative path, mirroring
# ``mission._packaged_missions_dir``.
_PACKAGED_MISSIONS_DIR = Path(specify_cli.__file__).resolve().parent / "missions"


def _real_mission(mission_type: str) -> Mission:
    """Load the real canonical ``Mission`` for ``mission_type`` (reads its shipped ``mission.yaml``)."""
    return Mission(_PACKAGED_MISSIONS_DIR / mission_type)


class _MissionStub:
    """Minimal mission-like object for path-validator unit cases.

    Mirrors the ``_MissionStub`` pattern in ``tests/agent/test_validators_unit.py`` so the Go ``internal/``
    layout can be exercised without coupling to a specific built-in mission's full ``paths:`` set.
    """

    def __init__(
        self,
        name: str,
        paths: dict[str, str],
        *,
        required_artifacts: tuple[str, ...] = (),
        optional_artifacts: tuple[str, ...] = (),
        domain: str = "software",
    ) -> None:
        self.name = name
        self.domain = domain
        self.config = SimpleNamespace(
            paths=paths,
            artifacts=SimpleNamespace(
                required=list(required_artifacts),
                optional=list(optional_artifacts),
            ),
        )


# ---------------------------------------------------------------------------
# T008 (FR-004 / US2-1) — every mission type honors the override at the shared seam
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "mission_type, key, override_value",
    [
        ("research", "workspace", "experiments/"),
        ("plan", "workspace", "planning/"),
        ("documentation", "workspace", "handbook/"),
    ],
)
def test_override_supersedes_doctrine_default_for_every_type(tmp_path: Path, mission_type: str, key: str, override_value: str) -> None:
    """FR-004: for research/plan/documentation, the override supersedes that type's doctrine default at the
    shared validator seam. Asserts the RESOLVED ``required_paths[key]`` equals the override (a discriminating
    assertion — a type whose declared dirs happened to exist would pass green *without* honoring the
    override; asserting the resolved value proves the override was applied, not merely that accept passed).
    """
    mission = _real_mission(mission_type)
    doctrine_default = mission.config.paths[key]  # READ from the real mission.yaml, not assumed
    # The discriminator is only meaningful if the override differs from the doctrine default.
    assert override_value != doctrine_default

    result = validate_mission_paths(mission, tmp_path, path_overrides={key: override_value})

    assert result.required_paths[key] == override_value
    assert result.required_paths[key] != doctrine_default


def test_evaluate_seam_forwards_config_override_to_validator(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-004 wiring: ``evaluate_path_conventions`` is the seam that reads ``project.path_conventions`` from
    ``.kittify/config.yaml`` and forwards it to ``validate_mission_paths`` as ``path_overrides``. Spy on the
    validator (the same patch point the acceptance-core tests use) to prove the override the operator wrote in
    config actually reaches the resolver — for a research mission, identically to software-dev.
    """
    repo_root = tmp_path / "repo"
    (repo_root / ".kittify").mkdir(parents=True)
    (repo_root / ".kittify" / "config.yaml").write_text(
        "project:\n  path_conventions:\n    workspace: experiments/\n",
        encoding="utf-8",
    )
    feature_dir = repo_root / "kitty-specs" / "some-slug"
    feature_dir.mkdir(parents=True)

    mission = _real_mission("research")

    captured: dict[str, object] = {}

    def _spy(*args: object, **kwargs: object):
        captured["path_overrides"] = kwargs.get("path_overrides")
        return SimpleNamespace(missing_paths=[], format_errors=lambda: "", format_warnings=lambda: "")

    monkeypatch.setattr("specify_cli.acceptance.summary_core.validate_mission_paths", _spy)

    evaluate_path_conventions(mission, repo_root, feature_dir, feature_dir, strict_metadata=True)

    assert captured["path_overrides"] == {"workspace": "experiments/"}


# ---------------------------------------------------------------------------
# T009 (FR-005) — Go ``internal/`` layout accepts honestly, no fabricated ``src/``
# ---------------------------------------------------------------------------


def test_go_internal_layout_accepts_without_fabricating_src(tmp_path: Path) -> None:
    """FR-005: a Go service whose real layout is ``internal/`` (no ``src/``) with colocated tests (no
    ``tests/`` dir) accepts under the override ``{workspace: internal/, tests: internal/}`` — no ``src``
    violation, and no fabricated directory. The non-fakeable part: ``src/`` is never created and never
    reported, and the honest accept comes from ``internal/`` actually existing.
    """
    (tmp_path / "internal").mkdir()  # real Go source root; colocated tests live here too
    # NOTE: neither ``src/`` nor ``tests/`` exists.

    mission = _MissionStub("Go Service Kitty", {"workspace": "src/", "tests": "tests/"})

    result = validate_mission_paths(
        mission,
        tmp_path,
        strict=False,
        path_overrides={"workspace": "internal/", "tests": "internal/"},
    )

    assert result.is_valid, result.warnings
    assert "internal/" in result.existing_paths
    # No ``src`` violation: neither the resolved paths nor any warning names src.
    assert set(result.required_paths.values()) == {"internal/"}
    assert not any("src" in warning for warning in result.warnings)
    assert result.missing_paths == []
    # No fabricated directory: the validator is pure — it never creates ``src/``.
    assert not (tmp_path / "src").exists()


# ---------------------------------------------------------------------------
# T010 (US1-4 / US2-3) — artifact-routed-key rejection + path_prefix composition
# ---------------------------------------------------------------------------


def test_deliverables_override_is_ignored_by_reader(
    tmp_path: Path,
) -> None:
    """C-010: ``deliverables`` is artifact-routed and cannot be overridden. The reader
    (``load_project_path_conventions``) warns-and-drops it, so it never reaches the validator. Guards the
    frozenset vocabulary directly (equality, not membership-by-count -- the new-dir style formerly golden-count-guarded).
    """
    assert frozenset({"deliverables"}) == ARTIFACT_ROUTED_KEYS

    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".kittify" / "config.yaml").write_text(
        "project:\n  path_conventions:\n    deliverables: fake-deliverables/\n    workspace: apps/\n",
        encoding="utf-8",
    )

    with pytest.warns(UserWarning, match="artifact-routed"):
        override = load_project_path_conventions(tmp_path)

    # The remap-able key survives; the artifact-routed key is dropped entirely.
    assert override == {"workspace": "apps/"}
    assert "deliverables" not in override


def test_deliverables_override_does_not_flip_artifact_routing(tmp_path: Path) -> None:
    """US1-4 / I3: even end-to-end through the ``evaluate_path_conventions`` seam, a ``deliverables`` override
    must NOT flip the mission-surface artifact check. ``contracts/`` (software-dev's ``deliverables`` value,
    also a declared artifact) is placed ONLY under the mission's planning surface, never at the repo root.

    Discriminator: if the override had been honored, ``deliverables`` would remap to ``fake-deliverables/``
    (not an artifact token) and resolve at the repo root → missing → a blocking ``path_violations`` entry.
    Because routing is NOT flipped, ``contracts/`` still resolves against ``feature_dir`` and the strict run
    produces zero path violations.
    """
    repo_root = tmp_path / "repo"
    (repo_root / "src").mkdir(parents=True)  # workspace → repo root
    (repo_root / "tests").mkdir()  # tests → repo root
    (repo_root / "docs").mkdir()  # documentation → repo root
    (repo_root / ".kittify").mkdir()
    (repo_root / ".kittify" / "config.yaml").write_text(
        "project:\n  path_conventions:\n    deliverables: fake-deliverables/\n",
        encoding="utf-8",
    )
    feature_dir = repo_root / "kitty-specs" / "some-slug"
    (feature_dir / "contracts").mkdir(parents=True)  # artifact → mission surface only
    # NOTE: neither repo_root/contracts nor repo_root/fake-deliverables exists.

    mission = _real_mission("software-dev")

    with pytest.warns(UserWarning, match="artifact-routed"):
        path_violations, warning, dedup_tokens = evaluate_path_conventions(mission, repo_root, feature_dir, feature_dir, strict_metadata=True)

    # Routing intact: contracts/ was found on the mission surface, so nothing blocks.
    assert path_violations == []
    assert warning is None


def test_research_override_composes_with_path_prefix_in_documented_order(tmp_path: Path) -> None:
    """US2-3 / precedence-contract step 3: for a research mission the composition of a project override and
    research's ``path_prefix`` is deterministic and pinned — the override remap is applied to ``declared``
    FIRST, then ``path_prefix`` is applied, yielding ``<prefix>/<override>/``. Pinning the resolved path
    documents the order rather than leaving it implicit.
    """
    mission = _real_mission("research")

    result = validate_mission_paths(
        mission,
        tmp_path,
        path_prefix="deliverables-root",
        path_overrides={"workspace": "experiments/"},
    )

    # override ("experiments/") composed UNDER the prefix ("deliverables-root") — order is prefix∘override.
    assert result.required_paths["workspace"] == "deliverables-root/experiments/"
