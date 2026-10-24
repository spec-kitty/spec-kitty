"""The legacy (pre-cutover) mission fixture shared by the birth-cutover suites.

``tests/migration/test_birth_cutover.py`` and the accept-time cutover tests
(``tests/architectural/_lifted_cli_accept_birth_cutover.py``, the home shared by
``tests/specify_cli/cli/test_accept_birth_cutover.py`` and its always-on lift)
both seed this one shape. It lives here, in neither suite, so the always-on lift
does not import an out-of-matrix test module for it, and so the two suites
cannot carry diverging copies again (#5015).
"""

from __future__ import annotations

import json
from pathlib import Path


def write_legacy_mission(feature_dir: Path, *, wp_id: str = "WP01") -> None:
    """A mission shaped like the PRE-WP04/WP05 corpus: real ``shell_pid`` /
    ``agent`` / subtask-checkbox runtime living in frontmatter/``tasks.md`` —
    exactly what :func:`backfill_runtime_state` seeds from. Deliberately NOT
    the born-reconciled shape (``tests/migration/test_birth_cutover.py``'s T042
    fixture) — this is the migration-coexistence population IC-08 must stay
    idempotent against."""
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_slug": feature_dir.name,
                # A real, distinct ULID (production-shaped) -- NOT equal to the
                # slug: backfill_runtime_state/verify_backfill collapse
                # ``mission_id == slug`` to ``None`` on the seeded StatusEvent
                # (the "no distinguishable id" convention), while a legacy
                # readback with a MISSING mission_id key defaults it back to the
                # slug -- an artificial mismatch that has nothing to do with
                # this WP's two-target/atomicity behavior, so use a genuine
                # ULID-shaped id here to sidestep it.
                "mission_id": "01JMLEGACYCUTOVERDEMO0001",
                "mid8": "LEGACY001",
                "mission_number": None,
                "mission_type": "software-dev",
                "target_branch": "main",
                "purpose_tldr": "legacy corpus fixture",
                "purpose_context": "a pre-WP04 mission with real frontmatter runtime",
                "created_at": "2026-01-01T00:00:00+00:00",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (tasks_dir / f"{wp_id}-work.md").write_text(
        "---\n"
        f"work_package_id: {wp_id}\n"
        f"title: {wp_id} legacy work\n"
        "agent: implementer-ivan\n"
        'shell_pid: "4242"\n'
        'shell_pid_created_at: "1735689600.0"\n'
        "---\n"
        f"# {wp_id}\n",
        encoding="utf-8",
    )
    (feature_dir / "tasks.md").write_text(
        f"## {wp_id} legacy work\n\n- [x] T001 Legacy completed task\n",
        encoding="utf-8",
    )
