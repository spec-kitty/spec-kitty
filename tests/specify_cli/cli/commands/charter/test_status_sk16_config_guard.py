"""SK-16 (ledger) — ``charter status --json`` must not leak a raw exception,
and must not turn a corrupted config into a silent success either.

Contract under test
--------------------
A corrupted or hand-edited ``.kittify/config.yaml`` whose top-level YAML
content is not a mapping (e.g. a bare scalar) previously made
``load_url_list_from_config`` raise ``AttributeError: 'str' object has no
attribute 'get'`` (``src/charter/activation/evidence/orchestrator.py``, the
``config.get("charter")`` call had no ``isinstance(config, dict)`` guard,
unlike the very next line's guard for ``charter_cfg``). That exception
propagated uncaught through ``EvidenceOrchestrator.collect()`` ->
``_collect_evidence_result`` -> ``_summarize_evidence`` ->
``_collect_synthesis_status`` -> ``status()``'s broad
``except Exception as e: _emit_error(..., message=str(e), unexpected=True)``.

``_emit_error``'s envelope (``result``/``success``/``error`` keys) is already
the structured shape the ``--json`` contract promises -- the defect is that
the *content* of the ``"error"`` field was a raw, unhandled Python exception
message rather than a controlled diagnostic.

Captured-red evidence (live-evidence discipline)
-------------------------------------------------
Against unmodified ``orchestrator.py`` this fixture makes ``charter status
--json`` exit non-zero with::

    {"error": "'str' object has no attribute 'get'", "result": "error",
     "success": false}

-- exactly matching the ledger's captured output (SK-16, verified first-hand
in this checkout).

**A first attempt at this fix over-corrected.** Adding a bare
``isinstance(config, dict): return ()`` guard made
``load_url_list_from_config`` swallow the corruption entirely, so ``charter
status --json`` exited 0 with a normal success envelope on a corrupted
config file -- indistinguishable from a project with no configured URLs.
The ledger's own SK-16 entry is explicit that the *pre-fix* behaviour "fails
closed... this is *not* a silent success" -- only the leaked exception text
was ever the defect. So the corrected contract this file now pins is: the
command must still fail (exit 1), and the error must carry a controlled
diagnostic naming the real problem (the file and the non-mapping shape)
instead of either a raw ``AttributeError`` or nothing at all.

**Re-pinned for #6557 (operator decision 01M5ZCANVH16B2ANT1BJ115S8R).**
``charter status`` errors moved from the legacy ``{result, success, error}``
envelope to the canonical ``{"ok": false, "error": {"code", "message"}}``
one, and the shared charter soundness gate now runs first. That gate reads
``.kittify/config.yaml`` through the activation reader (it follows the
``charter:`` pointer), so a non-mapping config is refused there as
``ACTIVE_CHARTER_CONFIG_INVALID`` before the evidence orchestrator's
``ConfigShapeError`` is reached. The fail-closed contract is unchanged.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

import specify_cli.cli.commands.charter as charter_pkg
from specify_cli.cli.commands.charter import charter_app

runner = CliRunner()

pytestmark = [pytest.mark.fast]


def _build_corrupt_config(repo_root: Path) -> None:
    """A project root whose ``.kittify/config.yaml`` top level is a bare scalar.

    No charter bundle is seeded: ``status()`` only gates on
    ``_assert_bundle_compatible`` when ``charter.yaml`` exists, so a bare
    ``.kittify/config.yaml`` is sufficient to reach the evidence-orchestrator
    code path this test targets, without unrelated bundle scaffolding
    (test-scaffolding-as-design-smell).
    """
    kittify = repo_root / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "config.yaml").write_text("just-a-plain-string-not-a-mapping\n", encoding="utf-8")


@pytest.fixture()
def corrupt_config_repo(tmp_path: Path) -> Path:
    _build_corrupt_config(tmp_path)
    return tmp_path


def _invoke_status_json(repo_root: Path) -> object:
    """Invoke ``charter status --json`` with only the unrelated collectors stubbed.

    ``_collect_synthesis_status`` (the collector that reaches
    ``load_url_list_from_config`` via ``_collect_evidence_result`` ->
    ``_summarize_evidence``) is deliberately left REAL -- it is the sole
    variable under test. ``charter_sync`` / ``org_layer`` /
    ``governance_references`` / ``freshness`` are stubbed to deterministic,
    JSON-safe values (mirroring ``test_status_json_safe.py``'s harness) so a
    bare, charter-less ``tmp_path`` repo is sufficient scaffolding.
    """
    with (
        patch.object(charter_pkg, "find_repo_root", return_value=repo_root),
        patch.object(
            charter_pkg,
            "_collect_charter_sync_status",
            return_value={"available": False, "error": "no charter (test stub)"},
        ),
        patch(
            "specify_cli.cli.commands.charter.status._collect_org_layer_status",
            return_value={"packs": [], "has_built_in": True},
        ),
        patch(
            "specify_cli.cli.commands.charter.status._collect_governance_reference_status",
            return_value={"available": True, "references": [], "warnings": []},
        ),
        patch("specify_cli.charter_runtime.freshness.compute_freshness") as compute_freshness,
    ):
        compute_freshness.return_value.to_dict.return_value = {}
        return runner.invoke(charter_app, ["status", "--json"], catch_exceptions=False)


class TestStatusJsonSurvivesNonMappingConfig:
    def test_status_json_does_not_leak_raw_attribute_error(self, corrupt_config_repo: Path) -> None:
        """The envelope's ``error.message`` must never be the bare
        Python exception text -- the observable symptom of SK-16."""
        result = _invoke_status_json(corrupt_config_repo)

        assert result.stdout.strip(), "expected JSON on stdout"
        payload = json.loads(result.stdout)
        error_message = payload["error"]["message"]
        assert "has no attribute" not in error_message, f"charter status --json leaked a raw AttributeError through the error envelope (SK-16): {payload!r}"

    def test_status_json_fails_closed_with_structured_diagnostic_on_non_mapping_config(self, corrupt_config_repo: Path) -> None:
        """Post-fix: a non-mapping ``config.yaml`` top level must still FAIL
        (exit != 0, ``ok: false``) with a structured diagnostic naming
        the real problem -- not a leaked ``AttributeError``, and not a
        success envelope either. Silent success on a corrupted config is
        this repository's dominant failure mode (charter, ledger SK-16)."""
        result = _invoke_status_json(corrupt_config_repo)

        assert result.exit_code != 0, (
            f"charter status --json must fail closed on a non-mapping "
            f"config.yaml (silent success is the defect ledger SK-16 warns "
            f"against); got exit {result.exit_code}:\n{result.stdout}"
        )
        payload = json.loads(result.stdout)
        assert payload["ok"] is False, payload
        assert payload["error"]["code"] == "ACTIVE_CHARTER_CONFIG_INVALID", payload
        assert "Unexpected" not in payload["error"]["message"], payload
        error_message = payload["error"]["message"]
        assert "has no attribute" not in error_message, f"leaked a raw AttributeError instead of a controlled diagnostic: {payload!r}"
        assert "config.yaml" in error_message, f"diagnostic should name the offending file: {payload!r}"
