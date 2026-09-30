"""FS-free identity-resolution leg (mission-resolver-port-01KX1C05 WP03, NFR-001).

Drives the shell's identity-resolution leg — the canonicalizer chain in
``specify_cli.missions._read_path_resolver`` (``resolve_handle_to_read_path``,
the guarded read-side seam :func:`mission_runtime._resolve_mission_slug` calls
FIRST, before any other fragment assembly) down to the single walk
(``specify_cli.context.mission_resolver.resolve_mission``) — with an injected
``FakeMissionResolver`` and **no** ``kitty-specs/`` tree on disk at all. This is
the concrete #1619 unblock: a caller can drive the trunk's handle→mission walk
against an in-memory fixture, with zero filesystem dependency on a materialized
mission directory.

Why ``resolve_handle_to_read_path`` and not the higher-level shell entry points
(``resolve_action_context`` / ``mission_context_for`` / ``resolve_placement_only``)
directly: each of those three gates the canonicalizer's answer behind a
``candidate_dir.exists()`` check before trusting it as the resolved
``mission_slug`` — a **pre-existing**, deliberate production behaviour (a
canonicalized identity is only adopted once something is actually on disk for
it), not something WP03 introduces or should bypass. Driving them end-to-end
therefore always needs a real directory on disk, which is exactly what NFR-001
scopes OUT of this test ("no kitty-specs/ tree present"). The seam this test
drives instead — ``resolve_handle_to_read_path`` with ``require_exists=False``
(the default) — is the same function :func:`mission_runtime._resolve_mission_slug`
calls, one level down: it returns the CANONICAL resolved directory computed via
the injected resolver's answer even when nothing backs it on disk yet, which is
precisely the identity-resolution leg NFR-001 asks to prove FS-free.

Scope (NFR-001, deliberately narrow): this test pins ONLY the identity leg —
resolving an operator handle (mid8 / full ULID / full slug) to its canonical
directory via the injected resolver. It does **not** drive the rest of
:func:`mission_runtime.resolve_action_context` (target-branch read, topology
read, status-surface read, workspace assembly) — those are separate,
still-FS-bound legs (``get_main_repo_root``, ``_resolve_coordination_branch``,
``_resolve_status_surface_dir``, topology) explicitly deferred to later #2173
phases per the WP03 design ruling (D-09).
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

from specify_cli.context.mission_resolver import FakeMissionResolver, ResolvedMission
from specify_cli.missions._read_path_resolver import resolve_handle_to_read_path

from mission_runtime.resolution import _resolve_mission_id
from tests._owned_fixtures import mint_test_fact

# Production-shaped fixture values (26-char ULID, 8-char mid8, a realistic
# on-disk-style composed slug) rather than placeholder shorthand — the mission
# dir NAME already embeds the mid8 tail, exactly as ``_build_index`` produces it
# for a real mission (``mission_slug=entry.name``).
_MISSION_ID = "01KFAKEFSFREEIDNTY00012345"
_MID8 = _MISSION_ID[:8]
_HUMAN_SLUG = "999-fake-fs-free-identity"
_COMPOSED_SLUG = f"{_HUMAN_SLUG}-{_MID8}"


def _fake_resolver(tmp_path: Path) -> FakeMissionResolver:
    """A resolver whose fixture ``feature_dir`` never touches disk."""
    fixture = ResolvedMission(
        mission_id=_MISSION_ID,
        mission_slug=_COMPOSED_SLUG,
        feature_dir=tmp_path / "kitty-specs" / _COMPOSED_SLUG,
        mid8=_MID8,
    )
    return FakeMissionResolver([fixture])


@pytest.mark.parametrize(
    "handle",
    [_MISSION_ID, _MID8, _COMPOSED_SLUG],
    ids=["full-mission-id", "bare-mid8", "full-slug"],
)
def test_identity_leg_resolves_via_injected_resolver_with_no_specs_tree(tmp_path: Path, handle: str) -> None:
    """The canonicalizer chain resolves every handle form via the Fake alone.

    ``tmp_path`` deliberately has NO ``kitty-specs/`` directory created — proving
    NFR-001's "green with the specs dir absent" contract for the identity leg,
    across the three handle priority tiers a real operator can type (full
    ``mission_id``, bare ``mid8``, and the full ``<slug>-<mid8>`` directory name).
    The walk reaches the injected ``FakeMissionResolver`` (zero filesystem access
    inside the resolver itself) through the SAME canonicalizer chain
    ``_resolve_mission_slug`` uses in production — no parallel, test-only path.
    """
    assert not (tmp_path / "kitty-specs").exists()

    resolver = _fake_resolver(tmp_path)
    resolved_dir = resolve_handle_to_read_path(tmp_path, handle, resolver=resolver)

    assert resolved_dir.name == _COMPOSED_SLUG

    # No side-effect materialization: the walk never created the tree it
    # resolved identity against.
    assert not (tmp_path / "kitty-specs").exists()


def test_identity_leg_unknown_handle_degrades_without_raising(
    tmp_path: Path,
) -> None:
    """An unresolvable handle degrades exactly as the pre-WP03 seam did.

    No mission dir exists on disk and the Fake has no matching fixture, so the
    literal-handle fallback applies (unchanged behaviour, ``require_exists=False``
    default) — the injected resolver's fail-closed-loud contract governs
    ``resolver.resolve()`` itself, not this lenient seam, which has always
    tolerated "nothing matched" by returning its best-known candidate.
    """
    resolver = _fake_resolver(tmp_path)
    resolved_dir = resolve_handle_to_read_path(tmp_path, "no-such-mission", resolver=resolver)
    assert resolved_dir == tmp_path / "kitty-specs" / "no-such-mission"


# ---------------------------------------------------------------------------
# T014 — legacy-<slug> bootstrap sentinel carve-out (D-07)
# ---------------------------------------------------------------------------


def test_resolve_mission_id_bootstrap_sentinel_not_routed_through_resolve(
    tmp_path: Path,
) -> None:
    """The ``legacy-<slug>`` carve-out mints a sentinel, never a raised error.

    ``_resolve_mission_id`` is threaded a resolver (WP03) for its internal
    handle-canonicalization step, but its bootstrap/pre-identity fallback line
    is a DELIBERATE carve-out (D-07): a mission with no on-disk ``meta.json``
    (bootstrap window) or one whose meta lacks ``mission_id`` (legacy mission)
    MUST still mint the stable ``legacy-<slug>`` sentinel — it must NOT be
    rewritten to call ``resolver.resolve()`` directly and let a fail-closed
    ``MissionNotFoundError`` propagate out of this function. A resolver with NO
    matching fixture (a cold-miss from the walk's point of view) proves the
    carve-out: the function returns the sentinel rather than raising, with no
    ``kitty-specs/`` tree present either.
    """
    assert not (tmp_path / "kitty-specs").exists()
    empty_resolver = FakeMissionResolver([])  # no missions known to the walk
    mission_id = _resolve_mission_id(tmp_path, "bootstrap-mission-no-meta-yet", resolver=empty_resolver)
    assert mission_id == "legacy-bootstrap-mission-no-meta-yet"


def test_resolve_mission_id_bootstrap_sentinel_reads_owned_checkout(
    tmp_path: Path,
) -> None:
    """The owned-checkout fork of the identity leg (#3328).

    Mirrors the carve-out test above, but drives the ``owned`` branch:
    ``primary_root`` is deliberately a DIFFERENT, never-created path (proving
    it is never read once ``owned`` is supplied, C-002), and the meta read is
    anchored on the fact's own ``mission_dir`` instead of the canonicalizer
    chain. No ``meta.json`` exists there either, so the same
    ``legacy-<slug>`` sentinel carve-out applies.
    """
    owned_root = tmp_path / "owned-checkout"
    owned_root.mkdir()
    decoy_primary_root = tmp_path / "decoy-primary-never-read"
    slug = "owned-bootstrap-mission-no-meta-yet"
    fact = mint_test_fact(
        repository_root=decoy_primary_root,
        owned_root=owned_root,
        mission_dir=owned_root / "kitty-specs" / slug,
        mission_slug=slug,
        write_branch="codex/owned",
    )

    mission_id = _resolve_mission_id(decoy_primary_root, slug, owned=fact)

    assert mission_id == "legacy-owned-bootstrap-mission-no-meta-yet"
