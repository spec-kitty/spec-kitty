"""Dashboard rendering contract for duplicate-prefix missions (WP09 + WP14).

Complements the scanner-level unit tests in
``tests/test_dashboard/test_scanner_mission_id.py`` with a rendering-level
contract that exercises the entire chain from on-disk meta.json through
``build_mission_registry`` and out of the ``spec-kitty dashboard --json``
CLI surface.

Scope
-----
The test fixture is the same 3-mission ``080-*`` scenario used by
``tests/integration/test_colliding_mission_flow.py``.  It proves that:

1. ``build_mission_registry`` exposes three distinct records keyed by
   mission_id (ULIDs), not by directory slug.
2. The emitted records conform to the ``MissionRecord`` TypedDict shape
   (``mission_id``, ``mission_slug``, ``display_number``, ``mid8``,
   ``feature_dir`` all present; correct types).
3. The ``dashboard --json`` CLI output is parseable JSON and round-trips
   into the same ``MissionRecord`` shape, with all 3 missions visible.
4. ``sort_missions_for_display`` returns a stable ordering that keeps all
   3 colliding missions grouped by their slug tie-break (not coalesced
   under a single numeric prefix).
5. Each record's ``mid8`` is visible in the rendered payload so an
   operator can disambiguate at a glance.

Out of scope
------------
The dashboard HTTP server (``specify_cli.dashboard.server``) is not
exercised here.  The CLI ``--json`` code path and ``build_mission_registry``
are the two surfaces where the contract is enforceable without spinning up
an HTTP server in-process.  If the server grows a dedicated rendering
contract in the future, extend this file rather than creating a new one.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from specify_cli.dashboard.api_types import MissionRecord
from specify_cli.dashboard.scanner import (
    build_mission_registry,
    sort_missions_for_display,
)

pytestmark = pytest.mark.fast


# Same three ULIDs as the integration test so fixture data is aligned.
ULID_FOO = "01KNAAA000000000000000FOO1"
ULID_BAR = "01KNBBB000000000000000BAR1"
ULID_BAZ = "01KNCCC000000000000000BAZ1"


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


def _write_meta(
    feature_dir: Path,
    *,
    mission_id: str,
    mission_slug: str,
    mission_number: int = 80,
    friendly_name: str = "",
) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    meta: dict[str, Any] = {
        "slug": mission_slug,
        "mission_slug": mission_slug,
        "friendly_name": friendly_name or mission_slug,
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-04-11T12:00:00+00:00",
        "mission_id": mission_id,
        "mission_number": mission_number,
    }
    (feature_dir / "meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


@pytest.fixture()
def colliding_080_repo(tmp_path: Path) -> Path:
    """Repo root with three ``080-*`` missions carrying distinct ULIDs."""
    specs = tmp_path / "kitty-specs"
    _write_meta(
        specs / "080-foo",
        mission_id=ULID_FOO,
        mission_slug="080-foo",
        friendly_name="Foo Mission",
    )
    _write_meta(
        specs / "080-bar",
        mission_id=ULID_BAR,
        mission_slug="080-bar",
        friendly_name="Bar Mission",
    )
    _write_meta(
        specs / "080-baz",
        mission_id=ULID_BAZ,
        mission_slug="080-baz",
        friendly_name="Baz Mission",
    )
    return tmp_path


# ---------------------------------------------------------------------------
# 1. Scanner output has three distinct ULID keys
# ---------------------------------------------------------------------------


def test_registry_has_three_distinct_mission_id_keys(
    colliding_080_repo: Path,
) -> None:
    """Three ``080-*`` missions must produce three distinct registry rows."""
    registry = build_mission_registry(colliding_080_repo)
    assert set(registry.keys()) == {ULID_FOO, ULID_BAR, ULID_BAZ}, (
        f"Expected exactly these 3 distinct records, got: {list(registry)}"
    )
    # Directory slugs must NEVER be used as registry keys.
    for slug in ("080-foo", "080-bar", "080-baz"):
        assert slug not in registry, (
            f"Registry must key by mission_id (ULID), not slug {slug!r}"
        )


# ---------------------------------------------------------------------------
# 2. MissionRecord TypedDict shape
# ---------------------------------------------------------------------------


_MISSION_RECORD_FIELDS = ("mission_id", "mission_slug", "display_number", "mid8", "feature_dir")


@pytest.mark.parametrize("ulid", [ULID_FOO, ULID_BAR, ULID_BAZ])
def test_record_conforms_to_mission_record_typed_dict(
    colliding_080_repo: Path,
    ulid: str,
) -> None:
    """Every record must carry the MissionRecord required fields with expected types."""
    registry = build_mission_registry(colliding_080_repo)
    record = registry[ulid]
    for field in _MISSION_RECORD_FIELDS:
        assert field in record, f"Record missing field {field!r}: {record}"

    # Type checks — match the MissionRecord TypedDict declarations.
    assert isinstance(record["mission_id"], str)
    assert record["mission_id"] == ulid
    assert isinstance(record["mission_slug"], str)
    assert record["mission_slug"].startswith("080-")
    assert record["display_number"] == 80
    assert record["mid8"] == ulid[:8]
    assert isinstance(record["feature_dir"], str)

    # Static check: the record is assignable to MissionRecord (TypedDict
    # is a dict at runtime — this is an existence check, not instanceof).
    typed_check: MissionRecord = record  # type: ignore[assignment]
    assert typed_check["mission_id"] == ulid


def test_mid8_is_distinct_across_missions(colliding_080_repo: Path) -> None:
    """The mid8 prefix must be unique across all 3 collision candidates."""
    registry = build_mission_registry(colliding_080_repo)
    mid8s = {record["mid8"] for record in registry.values()}
    assert mid8s == {ULID_FOO[:8], ULID_BAR[:8], ULID_BAZ[:8]}, (
        f"Expected exactly these 3 distinct mid8 values, got {mid8s}"
    )


# ---------------------------------------------------------------------------
# 3. dashboard --json CLI output shows all 3 missions
# ---------------------------------------------------------------------------


def test_dashboard_json_cli_renders_three_distinct_rows(
    colliding_080_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``spec-kitty dashboard --json`` must emit three distinct mission rows.

    Uses the Typer CLI in-process so we exercise the real rendering code
    path without spawning a subprocess.
    """
    import typer

    from specify_cli.cli.commands.dashboard import dashboard as dashboard_cmd

    # Monkeypatch the project-root resolver the CLI uses internally so it
    # reads from our temp fixture.
    def fake_project_root(*, json_output: bool = False) -> Path:
        return colliding_080_repo

    monkeypatch.setattr(
        "specify_cli.cli.commands.dashboard.get_project_root_or_exit",
        fake_project_root,
    )
    # ``--json`` is emitted through the console seam's ``emit_json`` (#2632),
    # which bypasses Rich rendering entirely — no width-wrapping or ANSI can
    # corrupt the payload, so no console monkeypatch is required.

    # Build a tiny typer app wrapper so CliRunner can invoke the handler.
    # We use the default callback surface so invoking with ``["--json"]``
    # hits the single registered command directly.
    app = typer.Typer()
    app.command()(dashboard_cmd)

    runner = CliRunner()
    result = runner.invoke(app, ["--json"])
    assert result.exit_code == 0, (
        f"dashboard --json failed: exit={result.exit_code}\n{result.stdout}"
    )

    # With the wide no-wrap Console monkeypatched in, the JSON payload
    # comes out as a single clean block.
    payload = json.loads(result.stdout.strip())
    assert "missions" in payload, f"Expected 'missions' key in payload: {payload}"
    assert "display_order" in payload

    missions = payload["missions"]
    # All three ULIDs appear as keys, exactly.
    assert set(missions.keys()) == {ULID_FOO, ULID_BAR, ULID_BAZ}, (
        f"Expected exactly 3 missions in --json output, got: {sorted(missions)}"
    )

    # Each emitted record keeps the MissionRecord shape.
    for ulid, record in missions.items():
        for field in _MISSION_RECORD_FIELDS:
            assert field in record, f"mission {ulid} missing {field!r}: {record}"
        assert record["mission_id"] == ulid
        assert record["mid8"] == ulid[:8]
        assert record["display_number"] == 80

    # display_order must include all 3 keys, exactly once each (no coalescing).
    assert sorted(payload["display_order"]) == sorted({ULID_FOO, ULID_BAR, ULID_BAZ})


# ---------------------------------------------------------------------------
# 4. Stable display ordering
# ---------------------------------------------------------------------------


def test_sort_missions_is_stable_and_keeps_all_three(
    colliding_080_repo: Path,
) -> None:
    """``sort_missions_for_display`` must preserve all 3 entries in a deterministic order."""
    registry = build_mission_registry(colliding_080_repo)
    order1 = sort_missions_for_display(registry)
    order2 = sort_missions_for_display(registry)

    assert order1 == order2, "Ordering must be deterministic"
    assert set(order1) == {ULID_FOO, ULID_BAR, ULID_BAZ}
    # Secondary sort is by mission_slug: bar < baz < foo
    slugs = [registry[mid]["mission_slug"] for mid in order1]
    assert slugs == ["080-bar", "080-baz", "080-foo"], (
        f"Unexpected display order: {slugs}"
    )


# ---------------------------------------------------------------------------
# 5. Rendered payload visibly includes each mid8
# ---------------------------------------------------------------------------


def test_rendered_json_contains_every_mid8(
    colliding_080_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each mid8 string must appear in the rendered JSON text.

    Operator-visible disambiguator check: the first 8 chars of every ULID
    must surface in the stdout payload so an operator running
    ``spec-kitty dashboard --json | jq`` can eyeball the collision directly.
    """
    import typer

    from specify_cli.cli.commands.dashboard import dashboard as dashboard_cmd

    def fake_project_root(*, json_output: bool = False) -> Path:
        return colliding_080_repo

    monkeypatch.setattr(
        "specify_cli.cli.commands.dashboard.get_project_root_or_exit",
        fake_project_root,
    )
    # ``--json`` uses the seam's ``emit_json`` (#2632) — intrinsically plain and
    # unwrapped, so no width/no-color console monkeypatch is needed.

    app = typer.Typer()
    app.command()(dashboard_cmd)
    runner = CliRunner()
    result = runner.invoke(app, ["--json"])
    assert result.exit_code == 0, result.stdout

    rendered = result.stdout
    for ulid in (ULID_FOO, ULID_BAR, ULID_BAZ):
        mid8_value = ulid[:8]
        assert mid8_value in rendered, (
            f"Rendered JSON missing mid8 {mid8_value!r}:\n{rendered}"
        )
