"""The claim carrier's envelope identity: a seed row must read back as itself.

Contract this file owns: the deterministic claim carrier's ``mission_id`` field is
exactly what ``read_event_stream`` re-derives for that row, for every Mission
identity shape (a real ULID, a legacy slug, or none declared), and the verifier
tolerates no divergence beyond its documented pre-existing cases.

Red-first regression for #6689 — the runtime-state cutover must converge on a
legacy Mission whose ``meta.json`` carries its own slug as ``mission_id``.
Reported shape (transcribed from the issue): a Mission accepted *before* the
event-sourced runtime cutover, whose

* ``meta.json`` ``mission_id`` is the Mission's own slug (not a ULID),
* ``tasks/WP01*.md`` frontmatter still carries the pre-cutover claim slots
  (``agent``, ``shell_pid``) with no ``shell_pid_created_at`` and no ``lane:``,
* ``status.events.jsonl`` history starts at ``claimed -> in_progress`` — there is
  no initial ``planned -> claimed`` transition.

On the pre-fix tree that shape mints a seed row whose envelope ``mission_id`` is
``None`` (collapsed away by ``_claim_carrier``), so the persisted JSON has no
``mission_id`` key; reading it back re-resolves the row's slug through
``meta.json`` and injects the slug-valued id, and ``verify_backfill`` then
reports ``WP01: claim mismatch (deterministic seed payload diverged)`` on every
run, forever — one historical Mission blocking the whole ``upgrade --project``.

The rows below are the standing ratchet for the fix. Each refusal assertion is
paired with a positive control built from the *same* fixture, so a "fix" that
merely widens the verifier's tolerance fails here (tactic
``acceptance-criteria-non-vacuity``).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import Result
from typer.testing import CliRunner

from specify_cli.cli.commands.migrate_cmd import app as migrate_app
from specify_cli.migration import backfill_runtime_state as b
from specify_cli.migration.backfill_runtime_state import MigrationOrderingError
from specify_cli.migration.strip_frontmatter import strip_mutable_fields
from specify_cli.status.store import read_event_stream

pytestmark = [pytest.mark.integration]

runner = CliRunner()

_LOCATE = "specify_cli.cli.commands.migrate_cmd.locate_project_root"

#: The reported Mission's own slug — used as its ``mission_id`` in ``meta.json``.
SLUG = "cache-known-card-ceo-checks"

#: The claim seed id the PRE-FIX code mints for this exact fixture. Byte-identical
#: to the id quoted in the #6689 report, which is what ties this fixture to the
#: reporter's corpus; it is also the IDEMPOTENCY key, so the fix must not move it.
PREFIX_SEED_ID = "0RWXZFHX7REDZWCZC43GQB3SPF"

#: ``status_phase`` value the cutover writes for a Mission it has flipped to
#: snapshot authority (mirrors ``test_backfill_runtime_state_cli``).
FLIPPED_STATUS_PHASE = "1"


def _write_meta(feature_dir: Path, *, mission_id: str | None) -> None:
    meta: dict[str, object] = {
        "mission_slug": feature_dir.name,
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-08-01T00:00:00+00:00",
        # The reported Mission was accepted (2026-08-08) before it ever flipped;
        # these stamps are why the operator could not simply retire it.
        "accept_commit": "0" * 40,
        "accepted_at": "2026-08-08T10:00:00+00:00",
        "accepted_by": "root",
    }
    if mission_id is not None:
        meta["mission_id"] = mission_id
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_wp01(feature_dir: Path) -> None:
    """WP01 in the reported legacy shape: claim slots present, no ``lane:``."""
    tasks = feature_dir / "tasks"
    tasks.mkdir(parents=True, exist_ok=True)
    (tasks / "WP01-known-card-fast-path.md").write_text(
        '---\nwork_package_id: WP01\ntitle: known card fast path\nassignee: root\nagent: "codex"\nshell_pid: "21224"\n---\n\n# WP01 — known card fast path\n',
        encoding="utf-8",
    )
    (feature_dir / "tasks.md").write_text(
        "# Tasks\n\n## WP01 known card fast path\n- [x] T001 harness the fast path\n",
        encoding="utf-8",
    )


def _write_events(feature_dir: Path) -> None:
    """History that starts at ``claimed -> in_progress`` (no ``planned -> claimed``)."""
    events = [
        {
            "event_id": "01AAAAAAAAAAAAAAAAAAAAAAA1",
            "mission_slug": feature_dir.name,
            "wp_id": "WP01",
            "from_lane": "claimed",
            "to_lane": "in_progress",
            "at": "2026-08-08T01:00:00+00:00",
            "actor": "codex",
            "force": False,
            "execution_mode": "worktree",
        },
        {
            "event_id": "01AAAAAAAAAAAAAAAAAAAAAAA2",
            "mission_slug": feature_dir.name,
            "wp_id": "WP01",
            "from_lane": "in_progress",
            "to_lane": "done",
            "at": "2026-08-08T02:00:00+00:00",
            "actor": "codex",
            "force": False,
            "execution_mode": "worktree",
        },
    ]
    (feature_dir / "status.events.jsonl").write_text(
        "\n".join(json.dumps(event, sort_keys=True) for event in events) + "\n",
        encoding="utf-8",
    )


def _build_reported_mission(
    root: Path,
    *,
    slug: str = SLUG,
    mission_id: str | None = SLUG,
) -> Path:
    """Materialise the #6689 Mission shape under *root* and return its directory.

    ``mission_id`` defaults to the reported slug-valued id; ``None`` omits the key
    entirely; any string is used verbatim. One builder for every identity shape
    keeps the declared/undeclared rows paired on a single fixture family.
    """
    feature_dir = root / "kitty-specs" / slug
    feature_dir.mkdir(parents=True, exist_ok=True)
    _write_meta(feature_dir, mission_id=mission_id)
    _write_wp01(feature_dir)
    _write_events(feature_dir)
    return feature_dir


def _invoke(repo_root: Path, args: list[str]) -> Result:
    with patch(_LOCATE, return_value=repo_root):
        return runner.invoke(migrate_app, ["backfill-runtime-state", *args])


def _rows(feature_dir: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in (feature_dir / "status.events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]


def _claim_row(feature_dir: Path, namespace: str) -> dict[str, object] | None:
    """Return the persisted claim carrier row for WP01, looked up by its seed id.

    *namespace* is the SEED-ID namespace root (the declared mission id, or the
    directory name when ``meta.json`` declares none) — the same input
    ``_seed_id`` takes, so the lookup cannot silently disagree with the writer.
    """
    seed_id = b._seed_id(namespace, "WP01", "claim")
    for row in _rows(feature_dir):
        if row.get("event_id") == seed_id:
            return row
    return None


# ---------------------------------------------------------------------------
# The fix: the reported shape converges (engine level)
# ---------------------------------------------------------------------------


def test_seed_row_carries_the_declared_mission_id(tmp_path: Path) -> None:
    """FR-002: the minted envelope carries the id ``meta.json`` declares, verbatim.

    Both halves matter: the seed id must be the PRE-FIX one (else every
    already-seeded corpus is re-seeded, breaking idempotency) and the envelope
    must now carry the declared value (else verify can never agree with the
    reader).
    """
    feature_dir = _build_reported_mission(tmp_path)

    b.backfill_runtime_state(feature_dir)

    claim = _claim_row(feature_dir, SLUG)
    assert claim is not None, "deterministic claim seed missing"
    assert claim["event_id"] == PREFIX_SEED_ID, "the claim seed id must not move (idempotency)"
    assert claim["mission_id"] == SLUG, "the seed row must declare the mission_id meta.json declares"
    assert claim["policy_metadata"] == {"agent": "codex", "shell_pid": 21224}

    # INV-1 as the invariant, not the symptom: every derived row survives a
    # write/read round-trip with an identical typed payload, so the next
    # envelope field cannot reintroduce the #6689 asymmetry.
    stream = read_event_stream(feature_dir)
    actual = {event.event_id: event for event in (*stream.transitions, *stream.annotations)}
    legacy = b.read_legacy_runtime(feature_dir)
    expected_t, expected_a = b._build_seed_events(feature_dir, feature_dir, legacy, b._claim_anchors(feature_dir), [])
    for expected in (*expected_t, *expected_a):
        assert actual[expected.event_id].to_dict() == expected.to_dict(), expected.event_id


def test_pre_fix_seed_row_without_mission_id_is_sound(tmp_path: Path) -> None:
    """FR-009: a row seeded by the buggy build reads back AS the declared id.

    A half-migrated project already carries a claim row whose JSON has no
    ``mission_id`` key. Event rows are immutable and deduplicated on first
    write, so verify must accept that row rather than demand a rewrite it cannot
    perform.
    """
    feature_dir = _build_reported_mission(tmp_path)
    assert b.backfill_runtime_state(feature_dir).action == "wrote"

    rows = _rows(feature_dir)
    for row in rows:
        if row.get("event_id") == PREFIX_SEED_ID:
            row.pop("mission_id", None)
    (feature_dir / "status.events.jsonl").write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )

    verify = b.verify_backfill(feature_dir)
    assert verify.ok, verify.mismatches


# ---------------------------------------------------------------------------
# The reported entry point: the CLI flips the Mission and a re-run is a no-op
# ---------------------------------------------------------------------------


def test_cli_flips_slug_identified_mission(tmp_path: Path) -> None:
    """FR-008 / SC-001: the production entry point exits 0 and flips ``status_phase``."""
    feature_dir = _build_reported_mission(tmp_path)

    result = _invoke(tmp_path, ["--mission", SLUG, "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["summary"]["flipped"] == 1
    assert payload["summary"]["failed"] == 0
    assert json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))["status_phase"] == FLIPPED_STATUS_PHASE
    verify = b.verify_backfill(feature_dir)
    assert verify.ok, verify.mismatches
    assert verify.wp_count == 1


def test_cli_second_run_seeds_nothing_and_still_verifies(tmp_path: Path) -> None:
    """FR-005 / SC-002: convergence, not a new state on every run."""
    feature_dir = _build_reported_mission(tmp_path)
    assert _invoke(tmp_path, ["--mission", SLUG]).exit_code == 0
    after_first = (feature_dir / "status.events.jsonl").read_bytes()

    result = _invoke(tmp_path, ["--mission", SLUG, "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["summary"]["seeded"] == 0
    assert payload["summary"]["failed"] == 0
    assert (feature_dir / "status.events.jsonl").read_bytes() == after_first
    verify = b.verify_backfill(feature_dir)
    assert verify.ok, verify.mismatches


# ---------------------------------------------------------------------------
# Ratchets: the identity shapes this fix must NOT change
# ---------------------------------------------------------------------------


def test_declared_ulid_mission_id_is_written_verbatim(tmp_path: Path) -> None:
    """A real ULID id is unchanged on the envelope and namespaces the seed id."""
    ulid = "01JMLEGACYCUTOVERDEMO0001"
    feature_dir = _build_reported_mission(tmp_path, slug="ulid-mission", mission_id=ulid)

    assert b.backfill_runtime_state(feature_dir).action == "wrote"

    claim = _claim_row(feature_dir, ulid)
    assert claim is not None
    assert claim["mission_id"] == ulid
    assert b.verify_backfill(feature_dir).ok


def test_undeclared_mission_id_stays_absent(tmp_path: Path) -> None:
    """FR-003 / INV-3: no identity is fabricated when ``meta.json`` declares none."""
    feature_dir = _build_reported_mission(tmp_path, slug="no-identity-mission", mission_id=None)

    assert b.backfill_runtime_state(feature_dir).action == "wrote"

    claim = _claim_row(feature_dir, "no-identity-mission")
    assert claim is not None
    assert "mission_id" not in claim, "an undeclared id must not be fabricated on the envelope"
    assert b.verify_backfill(feature_dir).ok


# ---------------------------------------------------------------------------
# Fail-closed controls: every refusal is paired with a positive control on the
# identical fixture, so a widened tolerance fails instead of passing.
# ---------------------------------------------------------------------------


def _seeded(feature_dir: Path) -> None:
    assert b.backfill_runtime_state(feature_dir).action == "wrote"


def test_tampered_claim_payload_still_fails_closed(tmp_path: Path) -> None:
    """FR-006: the fix must not buy the reported shape by tolerating a corrupted seed."""
    feature_dir = _build_reported_mission(tmp_path)
    _seeded(feature_dir)
    assert b.verify_backfill(feature_dir).ok  # positive control, same fixture

    rows = _rows(feature_dir)
    for row in rows:
        if row.get("event_id") == PREFIX_SEED_ID:
            row["policy_metadata"] = {"agent": "EVIL-DIVERGENT", "shell_pid": 21224}
    (feature_dir / "status.events.jsonl").write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )

    verify = b.verify_backfill(feature_dir)
    assert not verify.ok
    assert any("claim mismatch" in mismatch for mismatch in verify.mismatches), verify.mismatches


def test_missing_claim_seed_still_fails_closed(tmp_path: Path) -> None:
    """FR-006: a missing deterministic seed is still a terminal mismatch."""
    feature_dir = _build_reported_mission(tmp_path)
    _seeded(feature_dir)
    assert b.verify_backfill(feature_dir).ok  # positive control, same fixture

    kept = [row for row in _rows(feature_dir) if row.get("event_id") != PREFIX_SEED_ID]
    (feature_dir / "status.events.jsonl").write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in kept) + "\n",
        encoding="utf-8",
    )

    verify = b.verify_backfill(feature_dir)
    assert not verify.ok
    assert any("deterministic seed missing" in mismatch for mismatch in verify.mismatches), verify.mismatches


def test_strip_before_verify_still_raises_ordering_error(tmp_path: Path) -> None:
    """FR-007: the pinned ``backfill -> verify(pre-strip)`` order is still enforced."""
    feature_dir = _build_reported_mission(tmp_path)
    _seeded(feature_dir)
    assert b.verify_backfill(feature_dir).ok  # positive control, same fixture

    wp_file = feature_dir / "tasks" / "WP01-known-card-fast-path.md"
    stripped = strip_mutable_fields(feature_dir)
    assert stripped.fields_stripped > 0, stripped
    assert not wp_file.exists() or "agent" not in wp_file.read_text(encoding="utf-8"), stripped

    with pytest.raises(MigrationOrderingError, match="strip_mutable_fields ran before verify"):
        b.verify_backfill(feature_dir)
