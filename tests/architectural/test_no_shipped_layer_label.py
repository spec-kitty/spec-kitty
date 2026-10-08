"""FR-016 architectural regression: public CLI JSON surfaces must never emit
``"shipped"`` as a doctrine-layer label.

The mission ``charter-ux-and-org-pack-vocabulary-01KSAF14`` renames the layer
label from ``"shipped"`` to ``"built-in"``. This test scans the four public
JSON surfaces enumerated in plan.md (Cross-cutting Architectural-test-FR-016)
plus a doctrine pack validation against a fixture pack, walking each payload
for string values that occupy a *layer-label position* (the keys ``source``,
``layer``, ``provenance``, ``layer_label``). If any such value equals the
forbidden term, the test fails — refusing to merge future drift back to the
legacy vocabulary.

The test invokes the Typer app directly via ``CliRunner`` so it works in CI
environments that cannot spawn ``spec-kitty`` subprocesses (per WP08 risks
note). It does **not** ``pytest.skip`` silently — every surface must produce
JSON or the test fails with a clear message.
"""

from __future__ import annotations

import json
import textwrap
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from specify_cli import app as spec_kitty_app


pytestmark = [pytest.mark.architectural]

FORBIDDEN_LAYER_LABEL = "shipped"

# Keys whose string values denote a doctrine layer. Scanning only these keys
# avoids false positives from legitimate prose elsewhere in the payload
# (e.g. a tactic description that mentions the word "shipped" historically).
LAYER_LABEL_KEYS = frozenset({"source", "layer", "provenance", "layer_label"})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _layer_label_values(payload: Any) -> Iterator[str]:
    """Walk a JSON-decoded payload and yield string values at layer-label keys.

    Recurses into dicts and lists. Only emits values for which the *key* in
    the enclosing dict is one of :data:`LAYER_LABEL_KEYS`.
    """
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in LAYER_LABEL_KEYS and isinstance(value, str):
                yield value
            yield from _layer_label_values(value)
    elif isinstance(payload, list):
        for item in payload:
            yield from _layer_label_values(item)


def _materialise_fixture_pack(root: Path) -> Path:
    """Create a minimal, schema-valid org doctrine pack on disk.

    Returns the pack directory. The pack contains one directive so that
    ``charter pack validate`` exercises every code path that could emit a
    layer label (existence check, schema check, collision detection).
    """
    pack_dir = root / "fixture-pack"
    directives = pack_dir / "directives"
    directives.mkdir(parents=True, exist_ok=True)
    (directives / "acme-001.directive.yaml").write_text(
        textwrap.dedent(
            """\
            schema_version: "1.0"
            id: ACME-001
            title: Fixture directive
            intent: Architectural-test fixture for FR-016.
            enforcement: advisory
            """
        ),
        encoding="utf-8",
    )
    return pack_dir


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def fixture_pack(tmp_path: Path) -> Path:
    return _materialise_fixture_pack(tmp_path)


# ---------------------------------------------------------------------------
# Surface coverage — public CLI JSON outputs (FR-016)
# ---------------------------------------------------------------------------


# Each surface is invoked exactly once per test run. The pack-validate surface
# is parameterised to take the fixture pack path; the other four run against
# the worktree's own charter state (or a clean tmp_path if needed).
CHARTER_SURFACES: list[list[str]] = [
    ["charter", "status", "--json"],
    ["charter", "lint", "--json"],
    ["agent", "profile", "list", "--json"],
]


@pytest.mark.parametrize("cmd", CHARTER_SURFACES, ids=lambda c: " ".join(c))
def test_public_json_surface_has_no_shipped_layer_label(
    cmd: list[str], runner: CliRunner
) -> None:
    """FR-016: charter status/lint and agent profile list must not surface
    ``"shipped"`` as a layer-label value.

    Surfaces are invoked against the real repo so they exercise the live
    code paths (DRG materialisation, profile loading) rather than a stripped
    fixture. Exit code 0 or 1 are both acceptable (0 = clean, 1 = lint
    finding); the assertion focuses on the layer-label semantics of the
    emitted JSON, not on the diagnostic outcome.
    """
    result = runner.invoke(spec_kitty_app, cmd)
    assert result.exit_code in (0, 1), (
        f"surface {' '.join(cmd)!r} exited unexpectedly: "
        f"exit={result.exit_code} stdout={result.stdout[:500]!r}"
    )
    assert result.stdout.strip(), (
        f"surface {' '.join(cmd)!r} produced no JSON output; "
        "the architectural regression test cannot skip silently (FR-016)."
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(
            f"surface {' '.join(cmd)!r} did not emit valid JSON: {exc}\n"
            f"stdout: {result.stdout[:500]!r}"
        )

    labels = list(_layer_label_values(payload))
    forbidden = [label for label in labels if label == FORBIDDEN_LAYER_LABEL]
    assert not forbidden, (
        f"public CLI surface {' '.join(cmd)!r} still emits "
        f"{FORBIDDEN_LAYER_LABEL!r} as a layer label at one of "
        f"{sorted(LAYER_LABEL_KEYS)}. Found {len(forbidden)} occurrence(s) "
        f"in payload: {json.dumps(payload)[:600]}"
    )


def test_charter_preflight_has_no_shipped_layer_label(tmp_path: Path) -> None:
    """FR-016 — 4th surface: ``charter preflight`` JSON output (FR-006/FR-008)
    must not surface ``"shipped"`` as a layer-label value.

    The ``charter preflight`` Typer command currently lives in
    :mod:`specify_cli.charter_runtime.preflight.cli` but is not yet registered as a
    subcommand of the ``charter`` group (other WPs handle wiring). To still
    exercise the surface non-skip, we invoke the underlying runner directly
    and serialise its result via the same ``to_dict()`` contract the CLI
    uses, then apply the same layer-label scan.
    """
    from specify_cli.charter_runtime.preflight.runner import run_charter_preflight

    repo_root = Path(__file__).resolve().parents[2]
    result = run_charter_preflight(repo_root, auto_refresh=False, strict=False)
    payload = result.to_dict()

    # Round-trip through JSON to guarantee the serialised shape is what
    # operators (or downstream JSON consumers) actually observe.
    serialised = json.loads(json.dumps(payload, sort_keys=True, ensure_ascii=False))

    labels = list(_layer_label_values(serialised))
    forbidden = [label for label in labels if label == FORBIDDEN_LAYER_LABEL]
    assert not forbidden, (
        f"charter preflight JSON surface still emits "
        f"{FORBIDDEN_LAYER_LABEL!r} as a layer label. "
        f"Payload: {json.dumps(serialised)[:600]}"
    )


def test_charter_pack_validate_has_no_shipped_layer_label(
    runner: CliRunner, fixture_pack: Path
) -> None:
    """FR-016 — 5th surface: ``charter pack validate --json`` against a
    fixture pack must not surface ``"shipped"`` as a layer label in any
    validation message or advisory.
    """
    cmd = ["charter", "pack", "validate", str(fixture_pack), "--json"]
    result = runner.invoke(spec_kitty_app, cmd)
    assert result.exit_code in (0, 1), (
        f"charter pack validate exited unexpectedly: "
        f"exit={result.exit_code} stdout={result.stdout[:500]!r}"
    )
    assert result.stdout.strip(), (
        "charter pack validate --json produced no JSON; the architectural "
        "regression test cannot skip silently (FR-016)."
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(
            f"charter pack validate did not emit valid JSON: {exc}\n"
            f"stdout: {result.stdout[:500]!r}"
        )

    labels = list(_layer_label_values(payload))
    forbidden = [label for label in labels if label == FORBIDDEN_LAYER_LABEL]
    assert not forbidden, (
        f"charter pack validate --json still emits "
        f"{FORBIDDEN_LAYER_LABEL!r} as a layer label. "
        f"Payload: {json.dumps(payload)[:600]}"
    )

    # Also scan the advisory and error messages for the substring — the
    # validator surfaces vocabulary in human-readable strings as well as
    # structured fields.
    def _iter_messages(node: Any) -> Iterator[str]:
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "message" and isinstance(value, str):
                    yield value
                yield from _iter_messages(value)
        elif isinstance(node, list):
            for item in node:
                yield from _iter_messages(item)

    messages_with_shipped = [
        msg for msg in _iter_messages(payload) if FORBIDDEN_LAYER_LABEL in msg
    ]
    assert not messages_with_shipped, (
        "charter pack validate --json messages still mention "
        f"{FORBIDDEN_LAYER_LABEL!r}: {messages_with_shipped}"
    )


# ---------------------------------------------------------------------------
# Helper sanity tests — guard against false positives in the walker itself.
# ---------------------------------------------------------------------------


def test_layer_label_walker_yields_known_keys_only() -> None:
    """The walker must not yield values at non-layer-label keys (e.g. a
    tactic description that legitimately uses the word ``shipped``)."""
    payload = {
        "description": "legacy tactic shipped in 2023",  # not a layer label
        "source": "built-in",
        "items": [
            {"layer": "project", "note": "shipped on tuesday"},
            {"provenance": "org:acme"},
        ],
    }
    values = list(_layer_label_values(payload))
    assert "legacy tactic shipped in 2023" not in values
    assert "shipped on tuesday" not in values
    assert "built-in" in values
    assert "project" in values
    assert "org:acme" in values


def test_layer_label_walker_detects_forbidden_value() -> None:
    """If a payload smuggles ``shipped`` at a layer-label key, the walker
    must surface it so the architectural assertion fires."""
    payload = {"items": [{"source": FORBIDDEN_LAYER_LABEL}]}
    values = list(_layer_label_values(payload))
    assert FORBIDDEN_LAYER_LABEL in values
