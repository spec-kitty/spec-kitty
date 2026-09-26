"""Regression test for #4962: `migrate charter-encoding` must decode via the
canonical cp1252 tie-break detector, not ``charset_normalizer``'s raw
``.best()`` pick.

Before the fix, ``charter.activation._io._load_inner`` (the WP06 chokepoint
``migrate charter-encoding`` delegates to) called
``charset_normalizer.from_bytes(data).best()`` directly and trusted its
ranking. For a byte sequence where several code pages tie at zero chaos
(``SENTINEL`` below, encoded as cp1252), ``.best()``'s internal tie-breaking
does not honor the canonical cp1252-preference contract
(``contracts/detector-contract.md`` guarantee #4) -- it silently picked
``cp1250`` instead, corrupting every non-ASCII byte on rewrite while the
migration reported success.

This test drives the REAL CLI (``spec-kitty migrate charter-encoding --yes``,
via subprocess -- see ``tests/test_isolation_helpers.run_cli_subprocess``)
over a fixture charter file written as cp1252 ``SENTINEL`` bytes, and pins:

- The fix: on-disk bytes become the byte-exact UTF-8 ``SENTINEL`` (never a
  substring check), and the ``.bak`` sibling holds the exact original
  cp1252 bytes.
- Idempotency (NFR-006): re-running ``--yes`` on an already-UTF-8 file is a
  byte-unchanged no-op that writes zero additional ``.bak`` files.
- The defined backup-collision behaviour: a pre-existing ``.bak`` sibling
  blocks normalization of that file (never silently overwritten) and the
  command exits non-zero.

RED-first discipline: this test was written and run against the pre-fix
``_io.py``/``charter_encoding.py`` BEFORE the fix landed. Pre-fix, the
first test below failed because the on-disk bytes were the wrong-page
transcode ``SENTINEL.encode("cp1252").decode("cp1250").encode("utf-8")``
(confirmed empirically), not the byte-exact ``SENTINEL`` this test requires
-- see the WP02 handoff report for the captured RED CLI transcript.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from tests.test_isolation_helpers import run_cli_subprocess

pytestmark = [pytest.mark.regression, pytest.mark.git_repo]  # #4962

MISSION_SLUG = "001-issue-4962"

SENTINEL = "# Team Charter\n\n" + "Tests must pass before merge.\n" * 10 + "We don’t ship on Fridays — the “freeze” rule. Owner: José Peña, São Paulo.\n"

# The pre-fix chokepoint's exact wrong-page corruption for SENTINEL: it
# selects cp1250 instead of cp1252 (both tie at zero chaos in
# charset_normalizer's ranking; `.best()` picks the wrong one).
_WRONG_PAGE_BYTES = SENTINEL.encode("cp1252").decode("cp1250").encode("utf-8")


def _init_fixture_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True, check=True)
    (tmp_path / ".kittify").mkdir()
    charter_dir = tmp_path / "kitty-specs" / MISSION_SLUG / "charter"
    charter_dir.mkdir(parents=True)
    return charter_dir


class TestIssue4962WrongCodePageFix:
    """The committed, post-fix regression contract (GREEN)."""

    def test_cp1252_sentinel_becomes_byte_exact_utf8_with_backup(self, tmp_path: Path) -> None:
        charter_dir = _init_fixture_repo(tmp_path)
        charter_file = charter_dir / "charter.md"
        original_bytes = SENTINEL.encode("cp1252")
        charter_file.write_bytes(original_bytes)

        result = run_cli_subprocess(tmp_path, "migrate", "charter-encoding", "--yes")

        on_disk = charter_file.read_bytes()
        assert on_disk == SENTINEL.encode("utf-8"), f"expected byte-exact UTF-8 SENTINEL, got {on_disk!r} (cmd stdout={result.stdout!r} stderr={result.stderr!r})"
        # Pin the specific pre-fix bug is NOT reproduced: this must not be
        # the wrong-page (cp1250) transcode.
        assert on_disk != _WRONG_PAGE_BYTES

        backup_file = charter_file.with_name(charter_file.name + ".bak")
        assert backup_file.exists(), "expected a .bak sibling holding the original bytes"
        assert backup_file.read_bytes() == original_bytes

    def test_already_utf8_file_is_untouched_and_idempotent(self, tmp_path: Path) -> None:
        charter_dir = _init_fixture_repo(tmp_path)
        charter_file = charter_dir / "charter.md"
        utf8_bytes = SENTINEL.encode("utf-8")
        charter_file.write_bytes(utf8_bytes)
        backup_file = charter_file.with_name(charter_file.name + ".bak")

        first = run_cli_subprocess(tmp_path, "migrate", "charter-encoding", "--yes", "--json")
        first_payload = json.loads(first.stdout)

        assert charter_file.read_bytes() == utf8_bytes
        assert first_payload["result"] == "success"
        assert str(charter_file) in first_payload["already_utf8"]
        assert first_payload["normalized"] == []
        assert not backup_file.exists(), "already-UTF-8 file must never get a .bak sibling"

        second = run_cli_subprocess(tmp_path, "migrate", "charter-encoding", "--yes", "--json")
        second_payload = json.loads(second.stdout)

        assert charter_file.read_bytes() == utf8_bytes, "second run must be byte-unchanged"
        assert not backup_file.exists()
        assert second.returncode == 0
        assert str(charter_file) in second_payload["already_utf8"]

    def test_preexisting_backup_blocks_normalization(self, tmp_path: Path) -> None:
        charter_dir = _init_fixture_repo(tmp_path)
        charter_file = charter_dir / "charter.md"
        original_bytes = SENTINEL.encode("cp1252")
        charter_file.write_bytes(original_bytes)

        backup_file = charter_file.with_name(charter_file.name + ".bak")
        stale_backup_content = b"stale backup from an earlier run\n"
        backup_file.write_bytes(stale_backup_content)

        result = run_cli_subprocess(tmp_path, "migrate", "charter-encoding", "--yes")

        # Defined collision behaviour: refuse, never silently overwrite.
        assert result.returncode != 0
        assert backup_file.read_bytes() == stale_backup_content, "a pre-existing .bak must never be silently overwritten"
        assert charter_file.read_bytes() == original_bytes, "the source file must stay untouched when its backup collides"
