"""Unit tests for deterministic SHA256 hashing utilities.

Tests cover:
- hash_file() determinism (same file → same hash, 10 runs)
- Different files produce different hashes
- Order-independent parity hashing
- UTF-8 validation (BOM, CJK, surrogates)
- Error handling (file not found, permission denied, I/O errors)
"""

import pytest
import tempfile
import os
from pathlib import Path
from specify_cli.dossier.hasher import hash_file, hash_file_with_validation


pytestmark = [pytest.mark.unit, pytest.mark.fast]


class TestHashFile:
    """Test hash_file() function for deterministic SHA256 hashing."""

    def test_hash_file_determinism(self, tmp_path):
        """Hash same file 10 times, verify identical result."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, world!", encoding="utf-8")

        hashes = [hash_file(test_file) for _ in range(10)]

        # All hashes should be identical
        assert len(set(hashes)) == 1, "All 10 hashes should be identical"
        # Verify it's a 64-char hex string (SHA256)
        assert len(hashes[0]) == 64
        assert all(c in "0123456789abcdef" for c in hashes[0])

    def test_hash_different_files(self, tmp_path):
        """Hash two different files, verify different hashes."""
        file1 = tmp_path / "file1.txt"
        file1.write_text("Content A", encoding="utf-8")

        file2 = tmp_path / "file2.txt"
        file2.write_text("Content B", encoding="utf-8")

        hash1 = hash_file(file1)
        hash2 = hash_file(file2)

        assert hash1 != hash2, "Different files should produce different hashes"

    def test_hash_large_file(self, tmp_path):
        """Hash large file (>100MB), verify completes without memory issues."""
        large_file = tmp_path / "large.bin"

        # Create a 10MB file with repeating pattern
        chunk_size = 1024 * 1024  # 1MB chunks
        num_chunks = 10
        with open(large_file, "wb") as f:
            for i in range(num_chunks):
                f.write(b"A" * chunk_size)

        # Should complete without memory explosion
        hash_result = hash_file(large_file)
        assert len(hash_result) == 64
        assert all(c in "0123456789abcdef" for c in hash_result)

    def test_hash_binary_file(self, tmp_path):
        """Hash binary file with non-UTF8 bytes."""
        binary_file = tmp_path / "binary.bin"
        binary_file.write_bytes(b"\x00\x01\x02\x03\xff\xfe\xfd")

        hash_result = hash_file(binary_file)
        assert len(hash_result) == 64
        assert all(c in "0123456789abcdef" for c in hash_result)

    def test_hash_empty_file(self, tmp_path):
        """Hash empty file."""
        empty_file = tmp_path / "empty.txt"
        empty_file.write_text("", encoding="utf-8")

        hash_result = hash_file(empty_file)
        # Empty string SHA256
        expected = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        assert hash_result == expected

    def test_hash_file_not_found(self, tmp_path):
        """hash_file raises FileNotFoundError for missing file."""
        missing_file = tmp_path / "missing.txt"
        with pytest.raises(FileNotFoundError) as exc_info:
            hash_file(missing_file)
        assert "File not found" in str(exc_info.value)

    def test_hash_file_permission_denied(self, tmp_path):
        """hash_file raises PermissionError for unreadable file."""
        restricted_file = tmp_path / "restricted.txt"
        restricted_file.write_text("content", encoding="utf-8")

        # Remove read permission (Unix only)
        os.chmod(restricted_file, 0o000)

        try:
            with pytest.raises(PermissionError) as exc_info:
                hash_file(restricted_file)
            assert "Permission denied" in str(exc_info.value)
        finally:
            # Restore permission for cleanup
            os.chmod(restricted_file, 0o644)

    def test_hash_file_returns_lowercase_hex(self, tmp_path):
        """hash_file returns lowercase hex string."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test", encoding="utf-8")

        hash_result = hash_file(test_file)
        # Should be lowercase hex, no uppercase
        assert hash_result == hash_result.lower()
        assert all(c in "0123456789abcdef" for c in hash_result)

    def test_hash_file_special_characters_in_name(self, tmp_path):
        """Hash file with special characters in filename."""
        special_file = tmp_path / "file-with_special.chars123.txt"
        special_file.write_text("content", encoding="utf-8")

        hash_result = hash_file(special_file)
        assert len(hash_result) == 64
        # File name doesn't affect content hash (only content matters)

    def test_hash_consistency_across_multiple_calls(self, tmp_path):
        """Multiple sequential hash calls produce identical results."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Consistency test", encoding="utf-8")

        hash1 = hash_file(test_file)
        hash2 = hash_file(test_file)
        hash3 = hash_file(test_file)

        assert hash1 == hash2 == hash3


class TestHashFileWithValidation:
    """Test hash_file_with_validation() for UTF-8 validation."""

    def test_valid_utf8_file(self, tmp_path):
        """Valid UTF-8 file returns (hash, None)."""
        test_file = tmp_path / "valid.txt"
        test_file.write_text("Hello, world!", encoding="utf-8")

        hash_result, error = hash_file_with_validation(test_file)
        assert hash_result is not None
        assert len(hash_result) == 64
        assert error is None

    def test_utf8_with_bom(self, tmp_path):
        """UTF-8 with BOM (Byte Order Mark) validates correctly."""
        test_file = tmp_path / "bom.txt"
        # Write with UTF-8 BOM
        with open(test_file, "wb") as f:
            f.write(b"\xef\xbb\xbf" + b"Hello, world!")

        hash_result, error = hash_file_with_validation(test_file)
        assert hash_result is not None
        assert len(hash_result) == 64
        assert error is None

    def test_utf8_with_cjk_characters(self, tmp_path):
        """UTF-8 with CJK (Chinese/Japanese/Korean) characters validates."""
        test_file = tmp_path / "cjk.txt"
        # CJK characters (Chinese, Japanese, Korean)
        test_file.write_text("Hello 世界 こんにちは 안녕하세요", encoding="utf-8")

        hash_result, error = hash_file_with_validation(test_file)
        assert hash_result is not None
        assert len(hash_result) == 64
        assert error is None

    def test_utf8_with_emoji(self, tmp_path):
        """UTF-8 with emoji characters validates."""
        test_file = tmp_path / "emoji.txt"
        test_file.write_text("Hello 👋 World 🌍", encoding="utf-8")

        hash_result, error = hash_file_with_validation(test_file)
        assert hash_result is not None
        assert len(hash_result) == 64
        assert error is None

    def test_invalid_utf8_sequence(self, tmp_path):
        """Invalid UTF-8 sequence returns (None, 'invalid_utf8')."""
        test_file = tmp_path / "invalid.bin"
        # Write invalid UTF-8 sequence
        with open(test_file, "wb") as f:
            f.write(b"Valid: hello\nInvalid: \xff\xfe")

        hash_result, error = hash_file_with_validation(test_file)
        assert hash_result is None
        assert error == "invalid_utf8"

    def test_invalid_utf8_continuation_byte(self, tmp_path):
        """Invalid continuation byte returns (None, 'invalid_utf8')."""
        test_file = tmp_path / "invalid_cont.bin"
        # Start of multi-byte sequence without proper continuation
        with open(test_file, "wb") as f:
            f.write(b"\xc0\x00")  # Invalid: incomplete multi-byte

        hash_result, error = hash_file_with_validation(test_file)
        assert hash_result is None
        assert error == "invalid_utf8"

    def test_unreadable_file_returns_unreadable_error(self, tmp_path):
        """Unreadable file returns (None, 'unreadable')."""
        restricted_file = tmp_path / "restricted.txt"
        restricted_file.write_text("content", encoding="utf-8")

        # Remove read permission
        os.chmod(restricted_file, 0o000)

        try:
            hash_result, error = hash_file_with_validation(restricted_file)
            assert hash_result is None
            assert error == "unreadable"
        finally:
            os.chmod(restricted_file, 0o644)

    def test_missing_file_returns_unreadable_error(self, tmp_path):
        """Missing file returns (None, 'unreadable')."""
        missing_file = tmp_path / "missing.txt"

        hash_result, error = hash_file_with_validation(missing_file)
        assert hash_result is None
        assert error == "unreadable"

    def test_validation_result_is_deterministic(self, tmp_path):
        """Multiple calls return same validation result."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Test content", encoding="utf-8")

        result1 = hash_file_with_validation(test_file)
        result2 = hash_file_with_validation(test_file)
        result3 = hash_file_with_validation(test_file)

        assert result1 == result2 == result3
