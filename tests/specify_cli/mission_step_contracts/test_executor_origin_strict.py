"""#4984/#6012: step-contract execution fails closed on an unfetched org pack."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from charter.mission_steps import MissionStepContract, MissionStepContractStep
from specify_cli.mission_step_contracts.executor import (
    StepContractExecutionContext,
    StepContractExecutor,
)

pytestmark = [pytest.mark.fast, pytest.mark.regression]

_PACK = "unfetched-org-pack"


class _StubInvocationExecutor:
    """Never invoked: the chain resolution refuses before any step dispatch."""


def test_declared_but_unfetched_pack_fails_closed(tmp_path: Path) -> None:
    kit = tmp_path / ".kittify"
    kit.mkdir()
    (kit / "config.yaml").write_text(
        yaml.safe_dump({"charter_packs": {"org": {"packs": [{"name": _PACK, "local_path": f"never-fetched/{_PACK}"}]}}}),
        encoding="utf-8",
    )
    contract = MissionStepContract(
        id="c",
        schema_version="1.0",
        action="composer",
        mission="fixture",
        steps=[MissionStepContractStep(id="s", description="d")],
        gates=[],
    )
    executor = StepContractExecutor(
        repo_root=tmp_path,
        invocation_executor=_StubInvocationExecutor(),  # type: ignore[arg-type]
    )

    with pytest.raises(ValueError, match=_PACK) as excinfo:
        executor.execute(
            StepContractExecutionContext(
                repo_root=tmp_path,
                mission="fixture",
                action="composer",
                actor="pytest",
                profile_hint="implementer-fixture",
            ),
            contract=contract,
        )

    assert "spec-kitty charter fetch" in str(excinfo.value)
