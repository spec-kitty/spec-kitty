"""WP11 T049/T054: the evidence manifest builder fails closed and emits an immutable, deterministic bundle.

Exercises ``scripts/evidence/build_project_sync_consent_manifest.py`` through
its real CLI surface (subprocess, exact exit codes) against throwaway git
candidates, proving:

* floating or missing candidate refs are refused with no partial manifest;
* a one-byte artifact change is caught by checksum recomputation;
* a candidate commit mismatch, dirty checkout, contract digest drift, and a
  mocked (unreachable) tombstone commit each fail closed;
* duplicate evidence ownership (core re-claiming a SaaS claim, or two rows
  with one claim) is refused;
* missing/expired retention metadata is refused;
* a valid explicit input set produces a schema-complete manifest that is
  byte-deterministic for identical inputs and never overwritten once written.
"""

from __future__ import annotations

from pathlib import Path

import pytest
# The tests and helpers shared with this suite's always-on lift live once, in
# ``tests/architectural/_lifted_evidence.py`` (#5015); importing a test is what makes pytest collect it here.
from tests.architectural._lifted_evidence import (
    _CONTRACT_BODY,
    _sha256,
    _Inputs,
)
from tests.architectural._lifted_evidence import inputs as inputs
from tests.architectural._lifted_evidence import test_valid_inputs_produce_schema_complete_manifest as test_valid_inputs_produce_schema_complete_manifest
from tests.architectural._lifted_evidence import test_existing_manifest_is_never_overwritten as test_existing_manifest_is_never_overwritten

pytestmark = [pytest.mark.fast]


_EXPIRES_SHORT = "2026-08-23T00:00:00Z"  # 10 days after creation


def test_manifest_is_byte_deterministic_for_identical_inputs(inputs: _Inputs, tmp_path: Path) -> None:
    assert inputs.run().returncode == 0
    first = inputs.manifest_path.read_bytes()
    inputs.output_root = tmp_path / "bundle-second"
    assert inputs.run().returncode == 0
    assert inputs.manifest_path.read_bytes() == first


def test_floating_saas_ref_is_refused(inputs: _Inputs) -> None:
    inputs.saas_commit = "develop"
    inputs.assert_refused("floating ref")


def test_missing_candidate_ref_is_refused_without_partial_manifest(inputs: _Inputs) -> None:
    argv = inputs.argv()
    index = argv.index("--expected-saas-commit")
    del argv[index : index + 2]
    result = inputs.run(argv)
    assert result.returncode == 2  # argparse usage failure: the input set is incomplete
    assert "--expected-saas-commit" in result.stderr
    assert not inputs.output_root.exists()


def test_candidate_commit_mismatch_fails_closed(inputs: _Inputs) -> None:
    inputs.saas_commit = inputs.tombstone_commit  # a real commit, but not the candidate HEAD
    inputs.assert_refused("differs from the expected candidate commit")


def test_dirty_saas_candidate_is_refused(inputs: _Inputs) -> None:
    contract = inputs.saas_checkout / "contracts" / "cli-saas-current-api.yaml"
    contract.write_text(_CONTRACT_BODY + "# drift\n", encoding="utf-8")
    inputs.assert_refused("dirty")


def test_contract_digest_drift_fails_closed(inputs: _Inputs) -> None:
    inputs.contract_sha256 = _sha256(b"some other contract body")
    inputs.assert_refused("canonical contract digest")


def test_one_byte_artifact_change_fails_checksum(inputs: _Inputs) -> None:
    mutated = bytearray(inputs.artifact_body)
    mutated[0] ^= 0x01
    (inputs.artifact_root / "six-project-omission.json").write_bytes(bytes(mutated))
    inputs.assert_refused("checksum mismatch")


def test_mocked_tombstone_commit_is_refused(inputs: _Inputs) -> None:
    inputs.tombstone_commit = "0" * 40  # well-formed, but no such object in the SaaS candidate
    inputs.assert_refused("failed for checkout")

    inputs.tombstone_commit = inputs.core_commit  # a real commit, but from the wrong repository
    inputs.assert_refused("failed for checkout")


def test_duplicate_evidence_ownership_is_refused(inputs: _Inputs) -> None:
    inputs.artifacts = [inputs.artifacts[0], inputs.artifacts[0]]
    inputs.assert_refused("duplicate evidence ownership")


def test_core_cannot_claim_saas_owned_evidence(inputs: _Inputs) -> None:
    sha = _sha256(inputs.artifact_body)
    inputs.artifacts = [f"core:saas-wp08-admission-boundary:{sha}:six-project-omission.json"]
    inputs.assert_refused("duplicate evidence ownership")

    inputs.artifacts = [f"saas:stale-generation-refusal:{sha}:six-project-omission.json"]
    inputs.assert_refused("core-owned evidence only")


def test_expired_retention_metadata_is_refused(inputs: _Inputs) -> None:
    inputs.retention_expires_at = _EXPIRES_SHORT
    inputs.assert_refused("90-day minimum")


def test_malformed_retention_metadata_is_refused(inputs: _Inputs) -> None:
    inputs.retention_uri = "ftp://not-a-persistent-coordinate"
    inputs.assert_refused("retention coordinate")

    inputs.retention_uri = "https://evidence.example.test/retention/run-1"
    inputs.retention_expires_at = "whenever"
    inputs.assert_refused("UTC timestamp")
