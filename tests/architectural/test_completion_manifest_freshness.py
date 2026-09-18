"""Always-on freshness gate: committed completion manifest vs the live CLI.

The shell-completion fast path serves command/subcommand metadata from a
pre-generated data file (``src/specify_cli/_completion_manifest.json``) instead
of importing the whole CLI, so the manifest MUST stay byte-equivalent to the
live Typer tree — command paths *and* help text.

An identical assertion already lives in the fast-path integration suite
(``tests/specify_cli/cli/commands/test_completion_fast_path.py``), but that
directory is recorded ``out_of_matrix`` in ``.github/ci-module-registry.yml``:
no per-PR lane selects it, so a stale manifest went red only under
``make test-full`` and stayed red on ``main`` unnoticed (#4479). The sibling
CLI-reference gate (``test_docs_cli_reference_parity.py``) guards command-path
*presence* but not help *text*, so help-text drift (the #4479 failure mode:
legacy ``feature`` wording, an un-refreshed ``zeitgeist status`` help string,
a missing ``stale-check`` confidence level) had no always-on guard at all.

This gate closes that CI-routing gap (#4374, narrow scope): the freshness
invariant now runs in the always-on ``tests/architectural`` battery on every
PR, so the manifest can never silently drift on ``main`` again. Regenerate with
``python -m specify_cli.completion --regenerate`` when it reddens.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

# Mirror the CLI-reference parity gate: env flags before importing specify_cli.
os.environ.setdefault("SPEC_KITTY_NO_UPGRADE_CHECK", "1")

from specify_cli import completion  # noqa: E402

pytestmark = [pytest.mark.architectural]


def _committed_manifest() -> dict[str, Any]:
    """Read the committed manifest straight from disk (bypass the module cache)."""
    path = Path(completion.__file__).with_name("_completion_manifest.json")
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def test_committed_completion_manifest_matches_live_cli(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Build the live app the same way the manifest is generated. The SaaS flag
    # no longer gates Typer registration (see generate_manifest docstring), but
    # set it for selection-invariance with the fast-path suite.
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "1")

    live = completion.generate_manifest()
    committed = _committed_manifest()

    assert live == committed, "completion manifest is stale; regenerate with `python -m specify_cli.completion --regenerate`"
