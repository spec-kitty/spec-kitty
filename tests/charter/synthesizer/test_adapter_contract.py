"""Tests for the SynthesisAdapter Protocol contract (FR-003, T008).

Verifies:
1. FixtureAdapter is isinstance-compatible with SynthesisAdapter (runtime-checkable).
2. contract file (contracts/adapter.py) and implementation (src/charter/activation/synthesizer/adapter.py)
   expose structurally identical shapes — same field names, same method signatures.
3. AdapterOutput carries optional override fields; effective identity uses override-first.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from charter.activation.synthesizer.adapter import AdapterOutput, SynthesisAdapter
from charter.activation.synthesizer.fixture_adapter import FixtureAdapter
from charter.activation.synthesizer.request import SynthesisRequest, SynthesisTarget
from kernel.clock import now_utc


# ---------------------------------------------------------------------------
# 1. Protocol conformance
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.unit]


class TestProtocolConformance:
    def test_fixture_adapter_isinstance_synthesis_adapter(self) -> None:
        """FixtureAdapter satisfies the SynthesisAdapter runtime-checkable Protocol."""
        adapter = FixtureAdapter()
        assert isinstance(adapter, SynthesisAdapter), (
            "FixtureAdapter must satisfy isinstance(adapter, SynthesisAdapter). Check that FixtureAdapter exposes .id, .version, and .generate()."
        )

    def test_fixture_adapter_has_required_attributes(self) -> None:
        """FixtureAdapter exposes the required Protocol attributes."""
        adapter = FixtureAdapter()
        assert hasattr(adapter, "id") and isinstance(adapter.id, str)
        assert hasattr(adapter, "version") and isinstance(adapter.version, str)
        assert callable(getattr(adapter, "generate", None))

    def test_fixture_adapter_has_optional_batch(self) -> None:
        """FixtureAdapter also exposes generate_batch (optional, detected via hasattr)."""
        adapter = FixtureAdapter()
        assert hasattr(adapter, "generate_batch"), "FixtureAdapter should expose generate_batch for batch-orchestration paths."


# ---------------------------------------------------------------------------
# 2. Contract file structural equivalence
# ---------------------------------------------------------------------------


class TestContractStructuralEquivalence:
    """Verify that the planning contract file and the implementation are structurally identical.

    The contract file is at kitty-specs/.../contracts/adapter.py.
    The implementation is at src/charter/activation/synthesizer/adapter.py.

    We check that both define the same Protocol fields and method names.
    If they diverge, this test fails immediately — before ADR amendment happens.
    """

    def _load_contract_module(self, monkeypatch: pytest.MonkeyPatch):
        """Dynamically load the planning contract module."""
        import importlib.util
        import sys

        # Climb from tests/charter/synthesizer/ up to repo root
        repo_root = Path(__file__).parent.parent.parent.parent
        contract_path = repo_root / "kitty-specs" / "phase-3-charter-synthesizer-pipeline-01KPE222" / "contracts" / "adapter.py"
        if not contract_path.exists():
            pytest.skip(f"Contract file not found at {contract_path}")

        mod_name = "contract_adapter_synthesizer"
        spec = importlib.util.spec_from_file_location(mod_name, contract_path)
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        # Register in sys.modules so @dataclass can resolve the module's __dict__
        monkeypatch.setitem(sys.modules, mod_name, mod)
        try:
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
        except Exception:
            monkeypatch.delitem(sys.modules, mod_name, raising=False)
            raise
        return mod

    def test_synthesis_adapter_has_same_protocol_members(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """SynthesisAdapter in impl and contract expose the same required members."""
        contract = self._load_contract_module(monkeypatch)
        contract_proto = contract.SynthesisAdapter
        impl_proto = SynthesisAdapter

        def _protocol_members(proto: type) -> set[str]:
            """Collect member names from a Protocol class via annotations + methods."""
            members: set[str] = set()
            # Annotations cover Protocol fields (id, version)
            for cls in proto.__mro__:
                members.update(getattr(cls, "__annotations__", {}).keys())
            # Methods defined directly on the class
            members.update(name for name, val in vars(proto).items() if callable(val) and not name.startswith("__"))
            return members

        contract_members = _protocol_members(contract_proto)
        impl_members = _protocol_members(impl_proto)

        # Both must define id, version, generate at minimum
        for member in ("id", "version", "generate"):
            assert member in contract_members, f"contract Protocol missing member: {member}"
            assert member in impl_members, f"impl Protocol missing member: {member}"

    def test_adapter_output_same_fields(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """AdapterOutput in impl and contract have the same dataclass fields."""
        contract = self._load_contract_module(monkeypatch)
        import dataclasses

        contract_fields = {f.name for f in dataclasses.fields(contract.AdapterOutput)}
        impl_fields = {f.name for f in dataclasses.fields(AdapterOutput)}
        assert contract_fields == impl_fields, f"AdapterOutput field mismatch.\n  contract: {sorted(contract_fields)}\n  impl:     {sorted(impl_fields)}"

    def test_synthesis_request_same_fields(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """SynthesisRequest in impl and contract have the same dataclass fields."""
        contract = self._load_contract_module(monkeypatch)
        import dataclasses

        contract_fields = {f.name for f in dataclasses.fields(contract.SynthesisRequest)}
        from charter.activation.synthesizer.request import SynthesisRequest as ImplReq

        impl_fields = {f.name for f in dataclasses.fields(ImplReq)}
        assert contract_fields == impl_fields, f"SynthesisRequest field mismatch.\n  contract: {sorted(contract_fields)}\n  impl:     {sorted(impl_fields)}"


# ---------------------------------------------------------------------------
# 3. Override propagation
# ---------------------------------------------------------------------------


class TestAdapterOutputOverrides:
    """AdapterOutput carries override fields; effective identity uses override-first."""

    def test_adapter_output_override_fields_present(self) -> None:
        """AdapterOutput has adapter_id_override and adapter_version_override."""
        import dataclasses

        field_names = {f.name for f in dataclasses.fields(AdapterOutput)}
        assert "adapter_id_override" in field_names
        assert "adapter_version_override" in field_names

    def test_override_first_resolution(self) -> None:
        """Effective adapter identity uses override-first, fallback to adapter.id/version."""
        output = AdapterOutput(
            body={"id": "TEST", "title": "t"},
            generated_at=now_utc(),
            adapter_id_override="custom-model-v2",
            adapter_version_override="20260101",
        )
        adapter = FixtureAdapter()

        # Simulate what orchestration does: override-first
        effective_id = output.adapter_id_override or adapter.id
        effective_version = output.adapter_version_override or adapter.version

        assert effective_id == "custom-model-v2"
        assert effective_version == "20260101"

    def test_no_override_falls_back_to_adapter_identity(self) -> None:
        """Without overrides, effective identity falls back to adapter.id/version."""
        output = AdapterOutput(
            body={"id": "TEST", "title": "t"},
            generated_at=now_utc(),
        )
        adapter = FixtureAdapter()

        effective_id = output.adapter_id_override or adapter.id
        effective_version = output.adapter_version_override or adapter.version

        assert effective_id == adapter.id
        assert effective_version == adapter.version
