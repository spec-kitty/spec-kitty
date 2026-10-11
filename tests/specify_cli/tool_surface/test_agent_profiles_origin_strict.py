"""#4984/#6012: agent-profile projection reports the canonical unfetched-pack refusal."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from tests.specify_cli.tool_surface.providers.test_agent_profiles import _assess_real

pytestmark = [pytest.mark.fast, pytest.mark.regression]

_PACK = "unfetched-org-pack"


def test_declared_but_unfetched_pack_reports_canonical_message(tmp_path: Path) -> None:
    kit = tmp_path / ".kittify"
    kit.mkdir()
    (kit / "config.yaml").write_text(
        yaml.safe_dump({"charter_packs": {"org": {"packs": [{"name": _PACK, "local_path": f"never-fetched/{_PACK}"}]}}}),
        encoding="utf-8",
    )

    assessment = _assess_real(tmp_path)

    assert not assessment.complete
    messages = " ".join(d.message for d in assessment.diagnostics)
    assert _PACK in messages
    assert "spec-kitty charter fetch" in messages
