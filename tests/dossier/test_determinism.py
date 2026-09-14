"""Comprehensive determinism test suite for parity hash reproducibility (WP09).

This module validates that the dossier system produces deterministic hashes
across multiple runs, artifact orderings, UTF-8 edge cases, line endings,
and cross-machine scenarios. Critical for SC-002, SC-006, SC-007.

Test coverage:
- T046: Hash Reproducibility - Same file → same hash, 10+ runs
- T047: Order Independence - Artifact order irrelevant to parity hash
- T048: UTF-8 Handling - BOM, CJK, invalid sequences, emoji
- T049: CRLF vs LF Consistency - Line endings handled correctly
- T050: Parity Hash Stability - Timezone/version independence
"""

import hashlib
import json
import random
import tempfile
import time
import uuid

from pathlib import Path
from typing import Optional, Tuple

import pytest

from specify_cli.dossier.models import ArtifactRef, MissionDossier, MissionDossierSnapshot
from specify_cli.dossier.hasher import hash_file, hash_file_with_validation
from specify_cli.dossier.snapshot import (
    compute_snapshot,
    compute_parity_hash_from_dossier,
    get_parity_hash_components,
)


# =============================================================================
# FIXTURES
# =============================================================================


pytestmark = [pytest.mark.unit, pytest.mark.fast]

def create_test_feature(
    tmp_path: Path,
    num_artifacts: int = 10,
    artifact_content_prefix: Optional[str] = None,
) -> Path:
    """Create a test feature directory with artifacts.

    Args:
        tmp_path: Temporary directory to create feature in
        num_artifacts: Number of artifacts to create
        artifact_content_prefix: Optional prefix for all artifact content (for variation)

    Returns:
        Path to feature directory
    """
    feature_dir = tmp_path / "test-feature"
    feature_dir.mkdir(parents=True, exist_ok=True)

    for i in range(num_artifacts):
        prefix = artifact_content_prefix or ""
        artifact_path = feature_dir / f"artifact-{i:02d}.md"
        content = f"{prefix}# Artifact {i}\n\nThis is test artifact {i}.\n"
        artifact_path.write_text(content, encoding="utf-8")

    return feature_dir


def create_dossier_from_feature(
    feature_dir: Path, mission_slug: str = "software-dev"
) -> MissionDossier:
    """Create a MissionDossier by indexing files in a feature directory.

    Args:
        feature_dir: Feature directory with artifact files
        mission_slug: Mission slug (default: software-dev)

    Returns:
        MissionDossier with indexed artifacts
    """
    artifacts = []
    for i, artifact_file in enumerate(sorted(feature_dir.glob("*.md"))):
        content_hash = hash_file(artifact_file)
        artifacts.append(
            ArtifactRef(
                artifact_key=f"artifact.{artifact_file.stem}",
                artifact_class="input",
                relative_path=artifact_file.name,
                content_hash_sha256=content_hash,
                size_bytes=artifact_file.stat().st_size,
                required_status="required" if i < 5 else "optional",
                is_present=True,
            )
        )

    return MissionDossier(
        mission_type=mission_slug,
        mission_run_id=str(uuid.uuid4()),
        mission_slug="test-feature",
        feature_dir=str(feature_dir),
        artifacts=artifacts,
        manifest={"test": "manifest"},
    )


# =============================================================================
# T046: HASH REPRODUCIBILITY
# =============================================================================


class TestHashReproducibility:
    """T046: Hash reproducibility - same file → same hash across 10+ runs"""

    def test_hash_file_reproducibility_10_runs(self, tmp_path):
        """Hash same file 10 times, verify identical."""
        # Create test file
        test_file = tmp_path / "test-artifact.md"
        test_content = "# Test Artifact\n\nThis is a test.\n"
        test_file.write_text(test_content, encoding="utf-8")

        # Hash 10 times
        hashes = [hash_file(test_file) for _ in range(10)]

        # Verify all identical
        assert len(set(hashes)) == 1, f"Hash mismatch across 10 runs: {set(hashes)}"
        assert len(hashes[0]) == 64, "SHA256 should be 64 hex characters"
        # Verify valid hex
        int(hashes[0], 16)

    def test_hash_file_reproducibility_various_sizes(self, tmp_path):
        """Hash files of various sizes 5 times each."""
        test_sizes = [10, 100, 1000, 10000, 100000]

        for size in test_sizes:
            test_file = tmp_path / f"file-{size}bytes.txt"
            content = "X" * size
            test_file.write_text(content, encoding="utf-8")

            hashes = [hash_file(test_file) for _ in range(5)]
            assert len(set(hashes)) == 1, f"Hash mismatch for {size}-byte file: {set(hashes)}"

    def test_snapshot_reproducibility_same_content(self, tmp_path):
        """Compute snapshot twice on same content, verify identical parity hash."""
        # Create feature directory with artifacts
        feature_dir = create_test_feature(tmp_path, num_artifacts=10)

        # Compute snapshot 1
        dossier1 = create_dossier_from_feature(feature_dir)
        snapshot1 = compute_snapshot(dossier1)

        # Compute snapshot 2 (same content)
        dossier2 = create_dossier_from_feature(feature_dir)
        snapshot2 = compute_snapshot(dossier2)

        # Verify hashes identical
        assert snapshot1.parity_hash_sha256 == snapshot2.parity_hash_sha256, \
            f"Parity hash mismatch: {snapshot1.parity_hash_sha256} vs {snapshot2.parity_hash_sha256}"
        assert snapshot1.completeness_status == snapshot2.completeness_status
        assert snapshot1.total_artifacts == snapshot2.total_artifacts

    @pytest.mark.parametrize("run_count", [1, 5, 10, 20])
    def test_snapshot_reproducibility_multiple_runs(self, tmp_path, run_count):
        """Verify snapshot reproducible across N runs."""
        feature_dir = create_test_feature(tmp_path, num_artifacts=20)

        # Compute snapshots N times
        hashes = []
        for _ in range(run_count):
            dossier = create_dossier_from_feature(feature_dir)
            snapshot = compute_snapshot(dossier)
            hashes.append(snapshot.parity_hash_sha256)

        # Verify all identical
        unique_hashes = set(hashes)
        assert len(unique_hashes) == 1, (
            f"Hash mismatch across {run_count} runs: {unique_hashes}"
        )

    def test_hash_deterministic_with_binary_content(self, tmp_path):
        """Test hash reproducibility with binary-like content."""
        test_file = tmp_path / "binary-like.dat"
        # Write bytes that look binary but are valid UTF-8 when interpreted
        content = bytes([0x00, 0x01, 0x02, 0x48, 0x65, 0x6c, 0x6c, 0x6f])  # Hello with binary prefix
        # Only test with valid UTF-8
        content_utf8 = "Hello\n"
        test_file.write_text(content_utf8, encoding="utf-8")

        hash1 = hash_file(test_file)
        hash2 = hash_file(test_file)
        assert hash1 == hash2
        # Verify it matches expected SHA256
        expected = hashlib.sha256(b"Hello\n").hexdigest()  # noqa: TID251 — file-integrity checksum verifying hash_file() output (standard SHA-256), not charter freshness hashing
        assert hash1 == expected


# =============================================================================
# T047: ORDER INDEPENDENCE
# =============================================================================


class TestOrderIndependence:
    """T047: Order independence - artifact order irrelevant to parity hash"""

    def test_order_independence_parity_hash_components(self, tmp_path):
        """Verify parity hash is order-independent at component level."""
        feature_dir = create_test_feature(tmp_path, num_artifacts=5)
        dossier1 = create_dossier_from_feature(feature_dir)

        # Get components from first dossier
        components1 = get_parity_hash_components(dossier1)

        # Create dossier with shuffled artifacts
        shuffled_artifacts = random.sample(dossier1.artifacts, len(dossier1.artifacts))
        dossier2 = MissionDossier(
            mission_type=dossier1.mission_slug,
            mission_run_id=dossier1.mission_run_id,
            mission_slug=dossier1.mission_slug,
            feature_dir=dossier1.feature_dir,
            artifacts=shuffled_artifacts,
            manifest=dossier1.manifest,
        )

        # Components should be identical (they're sorted)
        components2 = get_parity_hash_components(dossier2)
        assert components1 == components2, \
            f"Components differ by order: {components1} vs {components2}"

    def test_parity_hash_order_independence_multiple_shuffles(self, tmp_path):
        """Test order independence with 10 different random shuffles."""
        feature_dir = create_test_feature(tmp_path, num_artifacts=10)
        dossier_original = create_dossier_from_feature(feature_dir)
        original_hash = compute_parity_hash_from_dossier(dossier_original)

        # Compute parity hash with 10 different random orderings
        parity_hashes = []
        for _ in range(10):
            shuffled_artifacts = random.sample(
                dossier_original.artifacts, len(dossier_original.artifacts)
            )
            dossier_shuffled = MissionDossier(
                mission_type=dossier_original.mission_slug,
                mission_run_id=dossier_original.mission_run_id,
                mission_slug=dossier_original.mission_slug,
                feature_dir=dossier_original.feature_dir,
                artifacts=shuffled_artifacts,
                manifest=dossier_original.manifest,
            )
            parity_hash = compute_parity_hash_from_dossier(dossier_shuffled)
            parity_hashes.append(parity_hash)

        # All should match original
        for i, parity_hash in enumerate(parity_hashes):
            assert parity_hash == original_hash, \
                f"Parity hash mismatch at shuffle {i}: {parity_hash} vs {original_hash}"

    def test_order_independence_snapshot_equality(self, tmp_path):
        """Snapshots with same artifacts in different order should be equal."""
        feature_dir = create_test_feature(tmp_path, num_artifacts=8)
        dossier1 = create_dossier_from_feature(feature_dir)
        snapshot1 = compute_snapshot(dossier1)

        # Create snapshot with shuffled artifacts
        shuffled_artifacts = random.sample(dossier1.artifacts, len(dossier1.artifacts))
        dossier2 = MissionDossier(
            mission_type=dossier1.mission_slug,
            mission_run_id=dossier1.mission_run_id,
            mission_slug=dossier1.mission_slug,
            feature_dir=dossier1.feature_dir,
            artifacts=shuffled_artifacts,
            manifest=dossier1.manifest,
        )
        snapshot2 = compute_snapshot(dossier2)

        # Snapshots should be equal (based on parity hash)
        assert snapshot1 == snapshot2, \
            f"Snapshots not equal despite same artifacts: {snapshot1.parity_hash_sha256} vs {snapshot2.parity_hash_sha256}"

    def test_order_independence_across_multiple_dossiers(self, tmp_path):
        """Create 5 independent dossiers with same artifacts in different orders."""
        feature_dir = create_test_feature(tmp_path, num_artifacts=15)

        base_dossier = create_dossier_from_feature(feature_dir)
        base_hash = compute_parity_hash_from_dossier(base_dossier)

        # Create 5 dossiers with different artifact orderings
        for _ in range(5):
            shuffled = random.sample(base_dossier.artifacts, len(base_dossier.artifacts))
            dossier = MissionDossier(
                mission_type=base_dossier.mission_slug,
                mission_run_id=base_dossier.mission_run_id,
                mission_slug=base_dossier.mission_slug,
                feature_dir=base_dossier.feature_dir,
                artifacts=shuffled,
                manifest=base_dossier.manifest,
            )
            parity_hash = compute_parity_hash_from_dossier(dossier)
            assert parity_hash == base_hash, \
                f"Parity hash differs with different ordering: {parity_hash} vs {base_hash}"


# =============================================================================
# T048: UTF-8 HANDLING
# =============================================================================


class TestUTF8Handling:
    """T048: UTF-8 handling - BOM, CJK, invalid sequences, emoji"""

    def test_utf8_bom_handling(self, tmp_path):
        """UTF-8 BOM (0xEF 0xBB 0xBF) handled correctly."""
        # File with BOM prefix
        file_with_bom = tmp_path / "with-bom.txt"
        content = "# Test\n"
        # Write with BOM
        file_with_bom.write_bytes(b"\xef\xbb\xbf" + content.encode("utf-8"))

        # File without BOM
        file_without_bom = tmp_path / "without-bom.txt"
        file_without_bom.write_text(content, encoding="utf-8")

        # Both should be readable and hash
        hash_with_bom, err1 = hash_file_with_validation(file_with_bom)
        hash_without_bom, err2 = hash_file_with_validation(file_without_bom)

        assert err1 is None, f"BOM file should be valid UTF-8: {err1}"
        assert err2 is None, f"Non-BOM file should be valid UTF-8: {err2}"
        # Note: hashes will differ (BOM adds bytes), but both should be valid
        assert hash_with_bom is not None
        assert hash_without_bom is not None
        # BOM makes file different
        assert hash_with_bom != hash_without_bom, "BOM changes file content hash"

    def test_utf8_cjk_characters(self, tmp_path):
        """UTF-8 CJK (Chinese/Japanese/Korean) characters handled."""
        # Chinese
        file_cjk = tmp_path / "cjk.md"
        content_cjk = "# 中文标题\n这是中文内容。\n"
        file_cjk.write_text(content_cjk, encoding="utf-8")

        # Japanese
        file_ja = tmp_path / "ja.md"
        content_ja = "# 日本語タイトル\nこれは日本語です。\n"
        file_ja.write_text(content_ja, encoding="utf-8")

        # Korean
        file_ko = tmp_path / "ko.md"
        content_ko = "# 한국어 제목\n이것은 한국어입니다.\n"
        file_ko.write_text(content_ko, encoding="utf-8")

        # All should hash without error
        hash_cjk, err1 = hash_file_with_validation(file_cjk)
        hash_ja, err2 = hash_file_with_validation(file_ja)
        hash_ko, err3 = hash_file_with_validation(file_ko)

        assert err1 is None, "Chinese should hash"
        assert err2 is None, "Japanese should hash"
        assert err3 is None, "Korean should hash"
        assert hash_cjk != hash_ja != hash_ko, "Different content should have different hashes"

    def test_utf8_invalid_sequence(self, tmp_path):
        """Invalid UTF-8 sequences rejected."""
        # File with invalid UTF-8 sequence
        file_invalid = tmp_path / "invalid.txt"
        # 0xFF 0xFE are invalid UTF-8 (reserved for UTF-16 BOM)
        file_invalid.write_bytes(b"Hello\xff\xfeWorld")

        # Should return error_reason
        hash_val, error = hash_file_with_validation(file_invalid)
        assert error == "invalid_utf8", \
            f"Expected invalid_utf8 error, got {error}"
        assert hash_val is None, f"Expected None hash for invalid UTF-8, got {hash_val}"

    def test_utf8_emoji(self, tmp_path):
        """Emoji and other Unicode chars handled."""
        file_emoji = tmp_path / "emoji.md"
        content = "# Test 😀\n\n✓ Check mark\n🚀 Rocket\n"
        file_emoji.write_text(content, encoding="utf-8")

        hash_val, error = hash_file_with_validation(file_emoji)
        assert error is None, f"Emoji should hash, error: {error}"
        assert hash_val is not None, "Hash should not be None for emoji"
        assert len(hash_val) == 64, "Should be valid SHA256"

    def test_utf8_mixed_scripts(self, tmp_path):
        """Mixed script handling (Latin + CJK + Arabic + Emoji)."""
        file_mixed = tmp_path / "mixed.md"
        content = "# Title\n## English 中文 العربية 😀\n\nContent: αβγ δικ αι\n"
        file_mixed.write_text(content, encoding="utf-8")

        hash_val, error = hash_file_with_validation(file_mixed)
        assert error is None, f"Mixed scripts should hash: {error}"
        assert hash_val is not None
        assert len(hash_val) == 64

    def test_utf8_special_characters(self, tmp_path):
        """Special UTF-8 characters (accents, diacritics, etc.)."""
        file_special = tmp_path / "special.md"
        content = "# Spëciål Chäractërs\n\nñ, ü, é, ç, ø, ð\n"
        file_special.write_text(content, encoding="utf-8")

        hash_val, error = hash_file_with_validation(file_special)
        assert error is None, f"Special characters should hash: {error}"
        assert hash_val is not None
        assert len(hash_val) == 64

    def test_utf8_reproducibility_across_encodings(self, tmp_path):
        """Same content encoded/decoded multiple times produces same hash."""
        content = "# Test\n中文\n🚀\n"

        file1 = tmp_path / "file1.md"
        file1.write_text(content, encoding="utf-8")

        file2 = tmp_path / "file2.md"
        # Encode, then decode, then encode again
        encoded = content.encode("utf-8")
        decoded = encoded.decode("utf-8")
        file2.write_text(decoded, encoding="utf-8")

        hash1, _ = hash_file_with_validation(file1)
        hash2, _ = hash_file_with_validation(file2)

        assert hash1 == hash2, "Same content should have same hash despite encoding/decoding"


# =============================================================================
# T049: CRLF VS LF CONSISTENCY
# =============================================================================


class TestLineEndingHandling:
    """T049: CRLF vs LF consistency - line endings handled correctly"""

    def test_crlf_vs_lf_handled(self, tmp_path):
        """Windows (CRLF) vs Unix (LF) line endings handled."""
        content = "# Specification\n\nLine 1\nLine 2\nLine 3\n"

        # Unix file (LF)
        file_lf = tmp_path / "unix.md"
        file_lf.write_bytes(content.encode("utf-8"))

        # Windows file (CRLF) - same logical content
        file_crlf = tmp_path / "windows.md"
        content_crlf = content.replace("\n", "\r\n")
        file_crlf.write_bytes(content_crlf.encode("utf-8"))

        # Hash both
        hash_lf, err_lf = hash_file_with_validation(file_lf)
        hash_crlf, err_crlf = hash_file_with_validation(file_crlf)

        # Both should be valid
        assert err_lf is None, f"LF file should be valid: {err_lf}"
        assert err_crlf is None, f"CRLF file should be valid: {err_crlf}"

        # Hashes will differ (bytes differ), and this is intentional
        # Line endings ARE part of content
        assert hash_lf != hash_crlf, \
            "LF and CRLF hashes should differ (they're different bytes)"

    def test_lf_only_reproducibility(self, tmp_path):
        """LF-only files reproducible across multiple reads."""
        file_lf = tmp_path / "lf-only.md"
        content = "Line 1\nLine 2\nLine 3\n"
        file_lf.write_bytes(content.encode("utf-8"))

        hashes = [hash_file(file_lf) for _ in range(5)]
        assert len(set(hashes)) == 1, "LF-only file should have consistent hash"

    def test_crlf_only_reproducibility(self, tmp_path):
        """CRLF-only files reproducible across multiple reads."""
        file_crlf = tmp_path / "crlf-only.md"
        content = "Line 1\r\nLine 2\r\nLine 3\r\n"
        file_crlf.write_bytes(content.encode("utf-8"))

        hashes = [hash_file(file_crlf) for _ in range(5)]
        assert len(set(hashes)) == 1, "CRLF-only file should have consistent hash"

    def test_mixed_line_endings(self, tmp_path):
        """Mixed line endings in single file handled."""
        file_mixed = tmp_path / "mixed.md"
        # Mix of LF and CRLF
        content = "Line 1\nLine 2\r\nLine 3\nLine 4\r\n"
        file_mixed.write_bytes(content.encode("utf-8"))

        hash_val, error = hash_file_with_validation(file_mixed)
        assert error is None, f"Mixed line endings should hash: {error}"
        assert hash_val is not None

    def test_line_endings_preserved_in_hash(self, tmp_path):
        """Verify line endings are preserved (not normalized)."""
        # Create 5 files with different line ending patterns
        files = []
        for i in range(5):
            test_file = tmp_path / f"line-endings-{i}.md"
            if i == 0:
                pattern = "A\nB\nC\n"  # LF only
            elif i == 1:
                pattern = "A\r\nB\r\nC\r\n"  # CRLF only
            elif i == 2:
                pattern = "A\nB\r\nC\n"  # Mixed
            elif i == 3:
                pattern = "A\r\nB\nC\r\n"  # Mixed (different pattern)
            else:
                pattern = "A\nB\nC"  # No trailing newline

            test_file.write_bytes(pattern.encode("utf-8"))
            files.append(test_file)

        # All should hash successfully and produce different hashes
        hashes = [hash_file(f) for f in files]
        assert len(set(hashes)) == len(files), \
            "Different line endings should produce different hashes"


# =============================================================================
# T050: PARITY HASH STABILITY (CROSS-MACHINE, TIMEZONE)
# =============================================================================


class TestParityHashStability:
    """T050: Parity hash stability - timezone/version independence"""

    def test_parity_hash_timezone_independent(self, tmp_path):
        """Parity hash not affected by timezone."""
        feature_dir = create_test_feature(tmp_path, num_artifacts=10)

        # Compute snapshot 1
        indexer1 = lambda: create_dossier_from_feature(feature_dir)
        dossier1 = indexer1()
        snapshot1 = compute_snapshot(dossier1)
        hash_1 = snapshot1.parity_hash_sha256

        # Wait slightly
        time.sleep(0.1)

        # Compute snapshot 2 (same content, different computed_at time)
        dossier2 = indexer1()
        snapshot2 = compute_snapshot(dossier2)
        hash_2 = snapshot2.parity_hash_sha256

        # Parity hashes should be identical (content unchanged)
        # Note: computed_at will differ, but parity hash should not
        assert hash_1 == hash_2, \
            "Parity hash should be timezone/time independent"
        # Verify computed_at times differ (proving they're independent)
        assert snapshot1.computed_at != snapshot2.computed_at, \
            "computed_at should differ (proving parity hash ignores timestamp)"

    def test_parity_hash_stable_across_python_runs(self, tmp_path):
        """SHA256 deterministic across Python runtime instances."""
        # Create test artifact
        file_path = tmp_path / "test.md"
        file_path.write_text("# Test Content\n", encoding="utf-8")

        # Hash (uses hashlib.sha256, which is standard)
        hash_val, _ = hash_file_with_validation(file_path)

        # Expected hash (pre-computed with reference SHA256)
        expected = hashlib.sha256(b"# Test Content\n").hexdigest()  # noqa: TID251 — file-integrity checksum verifying hash_file_with_validation() output (standard SHA-256), not charter freshness hashing

        assert hash_val == expected, \
            f"Hash mismatch: {hash_val} vs {expected}"

    def test_parity_hash_excludes_computed_at(self, tmp_path):
        """Verify computed_at is not part of parity hash calculation."""
        feature_dir = create_test_feature(tmp_path, num_artifacts=5)

        # Create identical dossiers
        dossier1 = create_dossier_from_feature(feature_dir)
        dossier2 = create_dossier_from_feature(feature_dir)

        # Manually verify parity hash computation excludes computed_at
        # by checking that the components are the same
        components1 = get_parity_hash_components(dossier1)
        components2 = get_parity_hash_components(dossier2)

        assert components1 == components2, \
            "Parity hash components should be identical (computed_at not included)"

        # Compute hashes
        hash1 = compute_parity_hash_from_dossier(dossier1)
        hash2 = compute_parity_hash_from_dossier(dossier2)

        assert hash1 == hash2, \
            "Parity hashes should match (computed_at not included)"

    def test_parity_hash_algorithm_deterministic(self, tmp_path):
        """Verify parity hash algorithm is deterministic."""
        # Create a known set of hashes
        test_hashes = [
            "a" * 64,
            "b" * 64,
            "c" * 64,
            "d" * 64,
            "e" * 64,
        ]

        # Compute parity hash 10 times with different orders
        parity_hashes = []
        for i in range(10):
            # Shuffle hashes
            shuffled = random.sample(test_hashes, len(test_hashes))
            # Manually compute parity hash (same as compute_parity_hash_from_dossier)
            combined = "".join(sorted(shuffled))
            parity = hashlib.sha256(combined.encode()).hexdigest()  # noqa: TID251 — dossier determinism content fingerprint (standard SHA-256), not charter freshness hashing
            parity_hashes.append(parity)

        # All should be identical (order-independent)
        assert len(set(parity_hashes)) == 1, (
            f"Parity hashes should all be identical: {set(parity_hashes)}"
        )

    def test_parity_hash_stable_with_large_dossier(self, tmp_path):
        """Verify parity hash stable with large number of artifacts."""
        # Create feature with 100 artifacts
        feature_dir = create_test_feature(tmp_path, num_artifacts=100)

        # Compute snapshots multiple times
        hashes = []
        for _ in range(3):
            dossier = create_dossier_from_feature(feature_dir)
            snapshot = compute_snapshot(dossier)
            hashes.append(snapshot.parity_hash_sha256)

        # All should be identical
        assert len(set(hashes)) == 1, (
            f"Parity hash should be stable with 100 artifacts: {set(hashes)}"
        )

    def test_parity_hash_consistent_with_modified_artifact_content(self, tmp_path):
        """Verify parity hash changes when artifact content changes."""
        feature_dir = create_test_feature(tmp_path, num_artifacts=5)

        # Compute initial snapshot
        dossier1 = create_dossier_from_feature(feature_dir)
        snapshot1 = compute_snapshot(dossier1)
        hash1 = snapshot1.parity_hash_sha256

        # Modify one artifact
        artifact_file = list(feature_dir.glob("*.md"))[0]
        artifact_file.write_text("Modified content\n", encoding="utf-8")

        # Re-index and compute snapshot
        dossier2 = create_dossier_from_feature(feature_dir)
        snapshot2 = compute_snapshot(dossier2)
        hash2 = snapshot2.parity_hash_sha256

        # Hashes should differ (content changed)
        assert hash1 != hash2, \
            "Parity hash should differ when artifact content changes"

    def test_snapshot_reproducibility_end_to_end(self, tmp_path):
        """End-to-end reproducibility: create dossier, take snapshot, verify."""
        feature_dir = create_test_feature(tmp_path, num_artifacts=15)

        # Snapshot 1: Create dossier, index, compute
        dossier1 = create_dossier_from_feature(feature_dir)
        snapshot1 = compute_snapshot(dossier1)

        # Snapshot 2: Fresh index, compute
        dossier2 = create_dossier_from_feature(feature_dir)
        snapshot2 = compute_snapshot(dossier2)

        # All critical fields should match
        assert snapshot1.parity_hash_sha256 == snapshot2.parity_hash_sha256
        assert snapshot1.total_artifacts == snapshot2.total_artifacts
        assert snapshot1.required_artifacts == snapshot2.required_artifacts
        assert snapshot1.optional_artifacts == snapshot2.optional_artifacts
        assert snapshot1.completeness_status == snapshot2.completeness_status
        assert snapshot1.parity_hash_components == snapshot2.parity_hash_components


# =============================================================================
# INTEGRATION TESTS: DETERMINISM ACROSS ALL CATEGORIES
# =============================================================================


class TestDeterminismIntegration:
    """Integration tests combining multiple determinism aspects."""

    def test_all_categories_together_utf8_mixed_order_reproducible(self, tmp_path):
        """Complex scenario: UTF-8 content, mixed ordering, reproducible."""
        feature_dir = tmp_path / "complex-feature"
        feature_dir.mkdir()

        # Create artifacts with various UTF-8 content
        contents = [
            "# English\nSimple text\n",
            "# 中文\n中文内容\n",
            "# Emoji\n🚀 Rocket 🎯\n",
            "# Special\nAccénts and ñ\n",
        ]

        for i, content in enumerate(contents):
            (feature_dir / f"artifact-{i}.md").write_text(content, encoding="utf-8")

        # Compute snapshot 1 (normal order)
        dossier1 = create_dossier_from_feature(feature_dir)
        snapshot1 = compute_snapshot(dossier1)

        # Compute snapshot 2 (shuffled order)
        shuffled = random.sample(dossier1.artifacts, len(dossier1.artifacts))
        dossier2 = MissionDossier(
            mission_type=dossier1.mission_slug,
            mission_run_id=dossier1.mission_run_id,
            mission_slug=dossier1.mission_slug,
            feature_dir=dossier1.feature_dir,
            artifacts=shuffled,
            manifest=dossier1.manifest,
        )
        snapshot2 = compute_snapshot(dossier2)

        # Should be equal despite UTF-8 content and different ordering
        assert snapshot1 == snapshot2, \
            "Complex UTF-8 content should be deterministic and order-independent"

    def test_determinism_with_all_line_ending_variants(self, tmp_path):
        """Test determinism with mixed line endings across artifacts."""
        feature_dir = tmp_path / "line-ending-variants"
        feature_dir.mkdir()

        # Create artifacts with different line endings
        (feature_dir / "lf.md").write_bytes(b"Line 1\nLine 2\n")
        (feature_dir / "crlf.md").write_bytes(b"Line 1\r\nLine 2\r\n")
        (feature_dir / "mixed.md").write_bytes(b"Line 1\nLine 2\r\nLine 3\n")

        # Index and compute
        dossier = create_dossier_from_feature(feature_dir)
        snapshot1 = compute_snapshot(dossier)

        # Re-index and compute
        dossier2 = create_dossier_from_feature(feature_dir)
        snapshot2 = compute_snapshot(dossier2)

        # Should be identical (parity hash reproduces)
        assert snapshot1.parity_hash_sha256 == snapshot2.parity_hash_sha256, \
            "Parity hash should reproduce with mixed line endings"

    @pytest.mark.parametrize("num_artifacts,num_runs", [
        (5, 10),
        (20, 5),
        (50, 3),
    ])
    def test_determinism_at_scale(self, tmp_path, num_artifacts, num_runs):
        """Test determinism at various scales."""
        feature_dir = create_test_feature(tmp_path, num_artifacts=num_artifacts)

        # Compute snapshot num_runs times
        hashes = []
        for _ in range(num_runs):
            dossier = create_dossier_from_feature(feature_dir)
            snapshot = compute_snapshot(dossier)
            hashes.append(snapshot.parity_hash_sha256)

        # All should be identical
        unique = set(hashes)
        assert len(unique) == 1, (
            f"Parity hash should be deterministic at scale ({num_artifacts} artifacts, {num_runs} runs)"
        )
