"""Regression test for #4968: ``accept --normalize-encoding`` must recover
mission-artifact encoding honestly instead of silently corrupting content.

Before this fix, ``specify_cli.acceptance._recover_normalized_text`` --
reached via ``normalize_feature_encoding``, which
``cli/commands/accept.py::_collect_summary_with_optional_repair`` calls when
a strict UTF-8 read raises ``ArtifactEncodingError`` -- decoded via a
cp1252-then-latin-1-then-``utf-8`` (``errors="replace"``) fallback chain and
then applied an ASCII smart-punctuation substitution map:

- for a strictly cp1252-decodable artifact (no undefined bytes), the first
  ``cp1252`` decode attempt already succeeds, so the file was silently
  rewritten with smart quotes/dashes flattened to ASCII -- NOT a byte-exact
  recovery -- and with no backup of the original bytes;
- for a genuinely ambiguous artifact (bytes no single-byte codepage can
  strictly decode), the chain fell through to ``latin-1`` -- which decodes
  every byte value and therefore never raises -- so the artifact was ALWAYS
  "recovered" (never refused), even though the true source encoding was
  unknowable.

This test drives the real ``normalize_feature_encoding`` entry point -- the
SAME function ``accept --normalize-encoding`` calls -- over a fixture mission
directory (``feature_repo`` / ``mission_slug``, ``tests/conftest.py``), and
pins the post-fix contract (``contracts/cli-behaviour-contract.md``,
``contracts/detector-contract.md``):

- byte-exact cp1252 SENTINEL recovery to UTF-8, with an original-bytes
  ``.bak`` backup;
- honest (<1.0) confidence + the detected codepage + the backup path,
  surfaced via the module's logger;
- a genuinely ambiguous artifact is refused: untouched, no backup, no
  ``U+FFFD``, and the accept pipeline's own strict re-read still raises
  ``ArtifactEncodingError`` (blocking verdict);
- idempotency: an already-UTF-8 artifact is left alone, no backup created.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import pytest

from specify_cli import acceptance as acc

pytestmark = pytest.mark.regression

# "# Spec" + 8 body lines + an attribution line carrying accented Latin-1
# characters (e / n / a with diacritics) plus Unicode smart-punctuation
# (curly quotes, em dash, right-single-quote apostrophe) -- all of which
# cp1252 encodes losslessly (round-trips byte-exact).
SENTINEL = "# Spec\n\n" + "Body line.\n" * 8 + "Owner: José Peña, São Paulo. “freeze” — don’t ship.\n"

# The five byte values Windows-1252 leaves undefined (charter.encoding_recovery
# ._CP1252_UNDEFINED_BYTES). No single-byte codepage candidate can strictly
# decode these, so the canonical detector reports ambiguous=True -- this is
# the SAME fixture shape tests/charter/test_encoding_recovery.py pins as
# ``UNDEFINED_CP1252_FIXTURE``.
AMBIGUOUS_BYTES = bytes(sorted({0x81, 0x8D, 0x8F, 0x90, 0x9D}))


def _backup_path(path: Path) -> Path:
    return path.with_name(f"{path.name}.bak")


def _spec_path(feature_repo: Path, mission_slug: str) -> Path:
    return feature_repo / "kitty-specs" / mission_slug / "spec.md"


class TestAcceptNormalizeEncodingIssue4968:
    """Drives the real ``normalize_feature_encoding`` entry point (WP03)."""

    def test_cp1252_sentinel_recovers_byte_exact_with_backup(self, feature_repo: Path, mission_slug: str) -> None:
        spec_path = _spec_path(feature_repo, mission_slug)
        spec_path.write_bytes(SENTINEL.encode("cp1252"))

        rewritten = acc.normalize_feature_encoding(feature_repo, mission_slug)

        assert spec_path in rewritten
        # WHOLE-FILE byte-exact equality -- never a substring match, and
        # never the ASCII-flattened ("--"/straight-quote) corruption the old
        # fallback silently produced.
        assert spec_path.read_bytes() == SENTINEL.encode("utf-8")

        backup = _backup_path(spec_path)
        assert backup.exists()
        assert backup.read_bytes() == SENTINEL.encode("cp1252")

    def test_honest_confidence_and_backup_path_are_reported(
        self,
        feature_repo: Path,
        mission_slug: str,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        spec_path = _spec_path(feature_repo, mission_slug)
        spec_path.write_bytes(SENTINEL.encode("cp1252"))

        with caplog.at_level(logging.INFO, logger="specify_cli.acceptance"):
            acc.normalize_feature_encoding(feature_repo, mission_slug)

        records = [record for record in caplog.records if str(spec_path) in record.getMessage()]
        assert records, "expected a log record naming the repaired artifact"
        message = records[0].getMessage()

        assert "cp1252" in message
        assert str(_backup_path(spec_path)) in message

        # Honest confidence: a tie-broken single-byte pick must never claim a
        # bare 1.0 (detector-contract.md guarantee #3).
        confidence_match = re.search(r"confidence (\d+\.\d+)", message)
        assert confidence_match is not None, message
        assert float(confidence_match.group(1)) < 1.0

    def test_ambiguous_artifact_refuses_untouched_no_backup(self, feature_repo: Path, mission_slug: str) -> None:
        spec_path = _spec_path(feature_repo, mission_slug)
        spec_path.write_bytes(AMBIGUOUS_BYTES)

        rewritten = acc.normalize_feature_encoding(feature_repo, mission_slug)

        assert spec_path not in rewritten
        assert spec_path.read_bytes() == AMBIGUOUS_BYTES
        assert not _backup_path(spec_path).exists()
        # Never a mojibake replacement character anywhere on disk.
        assert "�".encode() not in spec_path.read_bytes()

        # The accept pipeline's own strict read must still refuse on the
        # SAME unchanged bytes: cli/commands/accept.py::
        # _collect_summary_with_optional_repair's post-repair re-collect
        # relies on this to surface a blocking (exit != 0) verdict rather
        # than a mojibake "Normalized" success.
        with pytest.raises(acc.ArtifactEncodingError):
            acc.collect_feature_summary(feature_repo, mission_slug, mutate_matrix=False)

    def test_already_utf8_artifact_is_idempotent(self, feature_repo: Path, mission_slug: str) -> None:
        spec_path = _spec_path(feature_repo, mission_slug)
        original = spec_path.read_bytes()  # fixture seeds valid UTF-8 content

        rewritten = acc.normalize_feature_encoding(feature_repo, mission_slug)

        assert spec_path not in rewritten
        assert spec_path.read_bytes() == original
        assert not _backup_path(spec_path).exists()


class TestAcceptNormalizeEncodingBackupCollision:
    """#4962 review fold B: ``_write_recovered_artifact`` must never clobber
    a pre-existing ``.bak`` sibling.

    Mirrors ``migrate charter-encoding``'s ``_BackupCollisionError`` guard
    (``cli/commands/migrate/charter_encoding.py``), which the pre-fold
    ``accept --normalize-encoding`` repair path lacked entirely: an
    unconditional ``backup_path.write_bytes(...)`` silently overwrote
    whatever was already at ``<name>.bak`` -- clobbering the ORIGINAL bytes a
    prior repair preserved there, breaking the "never a one-way trip"
    guarantee on a re-run.
    """

    def test_preexisting_backup_refuses_and_leaves_both_files_untouched(self, feature_repo: Path, mission_slug: str) -> None:
        spec_path = _spec_path(feature_repo, mission_slug)
        spec_path.write_bytes(SENTINEL.encode("cp1252"))

        backup_path = _backup_path(spec_path)
        stale_backup_bytes = b"stale backup from a prior repair run\x92"
        backup_path.write_bytes(stale_backup_bytes)

        with pytest.raises(acc.EncodingBackupCollisionError) as exc_info:
            acc.normalize_feature_encoding(feature_repo, mission_slug)

        # Non-vacuous: without the fold B guard this raises nothing -- the
        # collision is silently overwritten and the call returns normally.
        assert str(spec_path) in str(exc_info.value)
        assert str(backup_path) in str(exc_info.value)

        # The stale backup is NEVER silently overwritten...
        assert backup_path.read_bytes() == stale_backup_bytes
        # ...and the artifact needing repair is left exactly as it was
        # (refused, not partially rewritten).
        assert spec_path.read_bytes() == SENTINEL.encode("cp1252")
