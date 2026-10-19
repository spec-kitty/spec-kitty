"""Gate test for the #2787 ``context_schema_version`` contract ledger.

Pins two invariants of ``charter.activation.context_contract``:

1. Every ``build_charter_context_json`` payload — bootstrap action AND
   non-bootstrap action — carries a top-level ``context_schema_version``
   equal to :data:`~charter.activation.context_contract.CONTEXT_SCHEMA_VERSION`.
2. Every top-level key either payload carries is a declared member of
   :data:`~charter.activation.context_contract.CONTEXT_CONTRACT_TOP_LEVEL_KEYS` — a
   *superset* guard, not strict equality, because the exact key set is
   conditional on the action (bootstrap vs. non-bootstrap) and on
   charter/doctrine state. An undeclared key escaping the ledger must red
   this test rather than pass silently.

Uses the same "copy the checkout's activated charter into an isolated
tmp project" fixture pattern as ``test_every_load_delivery.py`` so both a
real bootstrap render (``implement``) and a real non-bootstrap render
(``tasks``) resolve against genuine doctrine, not a hand-rolled stub.
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from charter.activation.context import build_charter_context_json
from charter.activation.context_contract import (
    CONTEXT_CONTRACT_TOP_LEVEL_KEYS,
    CONTEXT_SCHEMA_VERSION,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".kittify" / "charter").is_dir() and (parent / "pyproject.toml").is_file():
            return parent
    raise RuntimeError("could not locate repo root with .kittify/charter")


@pytest.fixture
def project(tmp_path: Path) -> Iterator[Path]:
    """Isolated tmp project seeded with the checkout's activated charter."""
    src = _repo_root()
    dst_kittify = tmp_path / ".kittify"
    dst_kittify.mkdir()
    shutil.copytree(
        src / ".kittify" / "charter",
        dst_kittify / "charter",
        ignore=shutil.ignore_patterns("context-state.json"),
    )
    shutil.copy(src / ".kittify" / "config.yaml", dst_kittify / "config.yaml")
    # This checkout's own config.yaml points at charter.yaml (the activation
    # source once the ``charter:`` pointer is present). The copied charter.yaml
    # now carries the WP04 (C-A1) ``mission_type_activations`` provisioning key
    # verbatim from the checkout's tracked file -- the charter generation path
    # (``charter.activation.compiler.provision_mission_type_activations``) emits it -- so
    # ``PackContext.from_config`` resolves this isolated fixture project without
    # any fixture-side append.
    subprocess.run(["git", "init", "--quiet", str(tmp_path)], check=False, capture_output=True)
    yield tmp_path
    try:
        from charter.resolution import resolve_canonical_repo_root

        resolve_canonical_repo_root.cache_clear()
    except Exception:
        pass


def _assert_stamped_and_declared(payload: dict[str, object]) -> None:
    assert payload.get("context_schema_version") == CONTEXT_SCHEMA_VERSION
    undeclared = set(payload) - CONTEXT_CONTRACT_TOP_LEVEL_KEYS
    assert not undeclared, (
        f"payload carries top-level key(s) {sorted(undeclared)!r} absent from "
        "CONTEXT_CONTRACT_TOP_LEVEL_KEYS -- either the ledger is stale "
        "(bump CONTEXT_SCHEMA_VERSION and add the key) or an unversioned "
        "key is leaking out of the contract."
    )


class TestContextSchemaVersionStamped:
    def test_bootstrap_action_carries_stamped_version(self, project: Path) -> None:
        payload = build_charter_context_json(
            project, action="implement", mission_type="software-dev"
        )
        assert payload["mode"] == "bootstrap"
        _assert_stamped_and_declared(payload)

    def test_non_bootstrap_action_carries_stamped_version(self, project: Path) -> None:
        """REVERSED (WP02, #3596, ADR 2026-08-21-1-charter-gate-predicate-inversion,
        reversal A). ``tasks`` is a DRG-declared ``action:software-dev/tasks``
        node and now resolves ``bootstrap``, not ``compact`` — the ledger
        superset guard must hold for the delivering payload shape too. Do NOT
        restore the old ``compact`` assertion.
        """
        payload = build_charter_context_json(
            project, action="tasks", mission_type="software-dev"
        )
        assert payload["mode"] == "bootstrap"
        _assert_stamped_and_declared(payload)


class TestContextSchemaVersionDiagnosticsEntry:
    """1.4.0 ledger entry (#6407): ``diagnostics`` is declared and always present."""

    def test_diagnostics_is_declared_and_always_present(self, project: Path) -> None:
        assert "diagnostics" in CONTEXT_CONTRACT_TOP_LEVEL_KEYS
        for action in ("implement", "tasks"):
            payload = build_charter_context_json(project, action=action, mission_type="software-dev")
            assert isinstance(payload["diagnostics"], list)
