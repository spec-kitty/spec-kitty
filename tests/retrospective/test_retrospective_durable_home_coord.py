"""WP03 (FR-001/003 / NFR-002/003) — the retrospective durable-home keystone.

The retrospective record (``retrospective.yaml``) is a terminal PRIMARY-partition
artifact: it MUST land in the durable tracked home
(``kitty-specs/<slug>/retrospective.yaml``) for EVERY topology — never the
ephemeral coordination worktree. Before this mission, the writer resolved the home
through the coord-AWARE ``resolve_feature_dir_for_slug`` primitive, which selects
the materialized ``-coord`` worktree once one exists. The record was therefore
written into ``.worktrees/<slug>-coord/...`` and lost on teardown (#1771).

NFR-002 (the keystone discipline): the behavioral assertion is
``".worktrees" not in resolved.parts`` against a GENUINELY-DIVERGENT coord
topology — a composed ``<slug>-<mid8>`` primary dir with a ``coordination_branch``
set AND a materialized coord worktree whose mission dir LACKS ``meta.json`` /
``lanes.json`` (the surface diverges from primary). ``"kitty-specs" in parts``
ALONE is the #1771 false-green — it is true for BOTH the durable home AND a
``.worktrees/<slug>-coord/kitty-specs/...`` husk path — so it is FORBIDDEN as the
sole assertion (it passed flat in #1771 while the husk still leaked).

Red-first evidence (NFR-002): ``test_red_evidence_old_resolver_leaks_into_coord``
drives the SAME divergent fixture through the OLD coord-aware
``resolve_feature_dir_for_slug`` and proves it resolves INTO ``.worktrees`` — the
genuine divergence the durable-home authority cures. The headline behavioral test
then proves the authority (and the real ``write_record`` entry point) lands in the
PRIMARY home for that same fixture.

Discipline (#2071): fixtures use a production-shaped 26-char Crockford ULID + its
8-char mid8 and the canonical ``meta.json`` serializer — no bare-slug / flattened
stub (a stub fixture is REJECTED per NFR-002).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.retrospective.schema import RetrospectiveRecord
from specify_cli.retrospective.writer import (
    canonical_record_path,
    resolve_retrospective_home,
    write_record,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

# Reuse the canonical fixture record from the round-trip suite.
from tests.retrospective.test_schema_roundtrip import make_completed_record  # noqa: E402

# Production-shaped identity: a real 26-char Crockford ULID + its 8-char mid8.
MISSION_ID = "01KVYM1WQ4D5E6F7G8H9J0K1M2"
MID8 = MISSION_ID[:8]  # "01KVYM1W"
SLUG = "retrospective-durable-home"
SLUG_WITH_MID8 = f"{SLUG}-{MID8}"
COORD_BRANCH = f"kitty/mission-{SLUG_WITH_MID8}"


def _git(repo_root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo_root), *args], check=True, capture_output=True, text=True
    )


def _init_repo(repo_root: Path) -> None:
    _git(repo_root, "init", "-q")
    _git(repo_root, "config", "user.email", "wp03@example.test")
    _git(repo_root, "config", "user.name", "WP03 Gate")
    # The load-bearing rule from the project .gitignore (line 61).
    (repo_root / ".gitignore").write_text(".kittify/missions/\n", encoding="utf-8")
    _git(repo_root, "commit", "--allow-empty", "-qm", "init")


def _write_meta(feature_dir: Path, meta: dict[str, object]) -> None:
    """Persist meta via the canonical sorted-key serializer (NOT a rotting writer)."""
    from tests._meta_write_support import write_meta_canonical as _write_meta_canonical

    feature_dir.mkdir(parents=True, exist_ok=True)
    _write_meta_canonical(feature_dir / "meta.json", meta)


def _record_for(slug_with_mid8: str) -> RetrospectiveRecord:
    """Return the canonical completed record re-homed onto this mission identity.

    ``RetrospectiveRecord`` / ``MissionIdentity`` are pydantic models, so re-home
    via ``model_copy(update=...)`` (NOT ``dataclasses.replace``).
    """
    base = make_completed_record()
    mission = base.mission.model_copy(
        update={
            "mission_id": MISSION_ID,
            "mid8": MID8,
            "mission_slug": slug_with_mid8,
        }
    )
    return base.model_copy(update={"mission": mission})


def _seed_divergent_coord_topology(repo_root: Path) -> tuple[Path, Path]:
    """Seed a GENUINELY-DIVERGENT coord-topology mission (the #1771 trap shape).

    Returns ``(primary_dir, coord_mission_dir)``:

    * ``primary_dir`` — the composed ``kitty-specs/<slug>-<mid8>/`` durable home,
      carrying ``meta.json`` with ``coordination_branch`` + COORD topology;
    * ``coord_mission_dir`` — a MATERIALIZED coord worktree mission dir that
      DELIBERATELY LACKS ``meta.json`` / ``lanes.json`` so the coord surface
      genuinely diverges from primary (NFR-002 — a stub/flat fixture is rejected).

    The coord-aware ``resolve_feature_dir_for_slug`` selects ``coord_mission_dir``
    (proved RED below); the durable-home authority ignores it and returns
    ``primary_dir``.
    """
    _init_repo(repo_root)
    from mission_runtime import MissionTopology
    from specify_cli.missions._read_path_resolver import coord_feature_dir

    meta: dict[str, object] = {
        "mission_id": MISSION_ID,
        "mid8": MID8,
        "mission_slug": SLUG_WITH_MID8,
        "coordination_branch": COORD_BRANCH,
        "topology": MissionTopology.COORD.value,
    }
    primary_dir = repo_root / "kitty-specs" / SLUG_WITH_MID8
    _write_meta(primary_dir, meta)

    # Materialize the coord worktree mission dir WITHOUT meta.json/lanes.json — the
    # genuine surface divergence. ``coord_feature_dir`` builds the exact path the
    # resolver probes; making it exist flips ``probe_coord_state`` → MATERIALIZED.
    coord_mission_dir = coord_feature_dir(repo_root, SLUG_WITH_MID8, MID8)
    coord_mission_dir.mkdir(parents=True, exist_ok=True)
    # A non-meta marker proves the dir is materialized yet lacks the identity files.
    (coord_mission_dir / "status.json").write_text("{}\n", encoding="utf-8")
    assert not (coord_mission_dir / "meta.json").exists()
    assert not (coord_mission_dir / "lanes.json").exists()
    return primary_dir, coord_mission_dir


# --------------------------------------------------------------------------- #
# Red-first evidence (NFR-002): the OLD coord-aware resolver LEAKS into the
# coord husk on the SAME divergent fixture — proving the divergence is genuine.
# --------------------------------------------------------------------------- #
def test_red_evidence_old_resolver_leaks_into_coord(tmp_path: Path) -> None:
    """The retired coord-aware resolver resolves INTO ``.worktrees`` (the #1771 bug).

    This is the red-first witness: on the genuinely-divergent fixture the OLD
    primitive ``resolve_feature_dir_for_slug`` (still present for genuine
    topology-aware STATUS reads) selects the materialized coord husk — exactly the
    home the durable-home authority must NOT return.
    """
    _primary_dir, coord_mission_dir = _seed_divergent_coord_topology(tmp_path)
    from specify_cli.missions._read_path_resolver import resolve_feature_dir_for_slug

    leaked = resolve_feature_dir_for_slug(tmp_path, SLUG_WITH_MID8)

    assert ".worktrees" in leaked.parts, (
        "Fixture is NOT genuinely divergent: the old coord-aware resolver must "
        "leak into .worktrees for the red-first proof to be meaningful (NFR-002)."
    )
    assert leaked.resolve() == coord_mission_dir.resolve()


# --------------------------------------------------------------------------- #
# Headline behavioral (T031): the durable-home authority lands PRIMARY, NOT coord.
#  Assertion is ``".worktrees" not in resolved.parts`` — NOT ``kitty-specs in
#  parts`` (the #1771 false-green that passes for a husk path too).
# --------------------------------------------------------------------------- #
def test_durable_home_authority_lands_primary_not_coord(tmp_path: Path) -> None:
    """The retrospective home resolves PRIMARY on a divergent coord mission."""
    primary_dir, coord_mission_dir = _seed_divergent_coord_topology(tmp_path)

    resolved = resolve_retrospective_home(tmp_path, SLUG_WITH_MID8)

    # The keystone assertion (NFR-002): the home is NOT the coord husk.
    assert ".worktrees" not in resolved.parts, (
        f"Retrospective home {resolved} re-homed into the coord worktree — the "
        "#1771 coord-leak. The durable home must be the PRIMARY kitty-specs dir."
    )
    assert resolved.resolve() == primary_dir.resolve()
    assert resolved.resolve() != coord_mission_dir.resolve()


def test_write_record_lands_in_durable_primary_home(tmp_path: Path) -> None:
    """The REAL ``write_record`` entry point writes into the durable PRIMARY home.

    Drives the actual writer (not a private resolver) on the divergent coord
    fixture and proves the file lands at ``kitty-specs/<slug>/retrospective.yaml``
    — never under ``.worktrees`` (NFR-002 keystone assertion).
    """
    primary_dir, _coord = _seed_divergent_coord_topology(tmp_path)
    record = _record_for(SLUG_WITH_MID8)

    written = write_record(record, repo_root=tmp_path)

    assert written.exists()
    assert ".worktrees" not in written.parts, (
        f"write_record wrote the record under {written} — a coord-husk leak (#1771)."
    )
    assert written.resolve() == (primary_dir / "retrospective.yaml").resolve()


# --------------------------------------------------------------------------- #
# T036 — Payload parity: the lifecycle-event payload path equals the actual home
#        (no longer the hardcoded ``.kittify/missions/<id>/`` string for site #6).
# --------------------------------------------------------------------------- #
def test_runtime_payload_path_equals_actual_durable_home(tmp_path: Path) -> None:
    """Site #6 ``_record_path_str`` reports the ACTUAL durable home, not ``.kittify``.

    Before WP03 the runtime terminus payload hardcoded
    ``repo_root / .kittify / missions / <id> / retrospective.yaml`` — re-splitting
    the brain (the record re-homed but the event still reported the legacy path).
    The payload must now equal the canonical durable home.
    """
    _seed_divergent_coord_topology(tmp_path)
    from runtime.next._internal_runtime.retrospective_terminus import _record_path_str

    record = _record_for(SLUG_WITH_MID8)
    payload = Path(_record_path_str(record, tmp_path))

    assert ".kittify" not in payload.parts, (
        "Runtime payload still reports the legacy .kittify/missions/ path — the "
        "brain is re-split (site #6 not consolidated)."
    )
    assert ".worktrees" not in payload.parts
    assert payload.resolve() == canonical_record_path(tmp_path, SLUG_WITH_MID8).resolve()


# --------------------------------------------------------------------------- #
# T036 — Flattened no-regression (NFR-003): a flattened/single-branch mission
#        resolves the SAME home before/after — byte-identical (the authority is a
#        no-op change vs the old coord-aware resolver when there is no coord husk).
# --------------------------------------------------------------------------- #
def test_flattened_mission_home_is_byte_identical(tmp_path: Path) -> None:
    """A flattened mission resolves the SAME PRIMARY home as the old resolver."""
    _init_repo(tmp_path)
    from mission_runtime import MissionTopology
    from specify_cli.missions._read_path_resolver import resolve_feature_dir_for_slug

    meta: dict[str, object] = {
        "mission_id": MISSION_ID,
        "mid8": MID8,
        "mission_slug": SLUG_WITH_MID8,
        "topology": MissionTopology.SINGLE_BRANCH.value,
    }
    primary_dir = tmp_path / "kitty-specs" / SLUG_WITH_MID8
    _write_meta(primary_dir, meta)

    # No coord worktree → the old coord-aware resolver ALSO resolves PRIMARY, so
    # the authority is byte-identical here (the flattened no-op leg, NFR-003).
    old_home = resolve_feature_dir_for_slug(tmp_path, SLUG_WITH_MID8)
    new_home = resolve_retrospective_home(tmp_path, SLUG_WITH_MID8)

    assert new_home.resolve() == old_home.resolve() == primary_dir.resolve()
    assert ".worktrees" not in new_home.parts


# --------------------------------------------------------------------------- #
# T036 — Read-side unchanged (C-004): ``_legacy_record_path`` is untouched and the
#        pre-#1771 back-compat read still finds legacy records.
# --------------------------------------------------------------------------- #
def test_legacy_record_path_back_compat_read_untouched(tmp_path: Path) -> None:
    """``_legacy_record_path`` still resolves the pre-#1771 ``.kittify`` read path."""
    from specify_cli.retrospective.writer import (
        _legacy_record_path,
        resolve_existing_record_path,
    )

    _init_repo(tmp_path)
    # A pre-#1771 record authored under the legacy gitignored tree.
    legacy = _legacy_record_path(tmp_path, MISSION_ID)
    assert legacy.parts[-4:] == (".kittify", "missions", MISSION_ID, "retrospective.yaml")
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text("schema_version: '1'\n", encoding="utf-8")

    # The tracked durable home does NOT exist → the reader falls back to legacy.
    resolved = resolve_existing_record_path(tmp_path, SLUG_WITH_MID8, MISSION_ID)
    assert resolved.resolve() == legacy.resolve(), (
        "Back-compat read regressed: a pre-#1771 legacy record is no longer found."
    )
