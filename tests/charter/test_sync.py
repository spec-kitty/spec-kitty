"""Tests for the (retired-extraction) charter sync orchestrator.

consolidate-charter-bundle (IC-04 / WP04, T028c): ``sync()``'s prose->triad
scrape -- parsing ``charter.md`` and writing ``governance.yaml`` /
``directives.yaml`` / ``metadata.yaml`` -- is RETIRED. ``governance``/
``directives`` are hand-authored sections directly inside the git-tracked
``charter.yaml`` now (``charter.activation.sync.load_governance_config`` /
``load_directives_config``). ``sync()`` is RETAINED only for its callers'
contract (canonical-root resolution via ``ensure_charter_bundle_fresh``, the
``charter sync`` CLI command): it still performs the ``charter.md``
staleness check (comparing against a pre-existing ``metadata.yaml``'s
``charter_hash``, when one happens to be present) and reports
``stale_before`` accurately, but ``synced`` is now ALWAYS ``False`` and
``files_written`` ALWAYS ``[]`` -- there is nothing left for this function
to produce.
"""

import pytest
from pathlib import Path

from ruamel.yaml import YAML

from charter.hasher import hash_content
from charter.activation.sync import sync

pytestmark = pytest.mark.fast
# Sample charter content for testing
SAMPLE_CHARTER = """# Testing Standards

## Coverage Requirements
- Minimum 80% code coverage
- All critical paths must be tested

## Quality Gates
- Must pass all linters
- Must pass type checking

## Performance Benchmarks
- API response time < 200ms
- Page load time < 1s

## Branch Strategy
- main: production-ready code
- develop: integration branch

## Agent Configuration
| agent | role | model |
|-------|------|-------|
| claude | implementer | claude-sonnet-4 |
| copilot | reviewer | gpt-4 |

## Project Directives
1. Never commit secrets to repository
2. Always write tests for new missions
3. Document all public APIs
"""


def _write_metadata_with_hash(output_dir: Path, content: str) -> None:
    """Seed a metadata.yaml carrying content's hash, for the staleness check.

    ``metadata.yaml`` is a retired charter-bundle FILE (folded into
    charter.yaml by the WP07 migration), but ``sync()``'s staleness
    comparison still reads whatever happens to sit at
    ``output_dir/metadata.yaml`` -- these fixtures exercise that retained
    read path directly, independent of the retired write path.
    """
    yaml = YAML()
    yaml.dump({"charter_hash": hash_content(content)}, output_dir / "metadata.yaml")


def test_sync_never_writes_derivatives(tmp_path: Path):
    """sync() always reports synced=False and writes nothing -- retirement contract."""
    charter_file = tmp_path / "charter.md"
    charter_file.write_text(SAMPLE_CHARTER, encoding="utf-8")

    result = sync(charter_file, tmp_path)

    assert result.synced is False
    assert result.files_written == []
    assert result.error is None
    for filename in ("governance.yaml", "directives.yaml", "metadata.yaml"):
        assert not (tmp_path / filename).exists(), filename


def test_sync_stale_before_true_when_no_prior_metadata(tmp_path: Path):
    """No pre-existing metadata.yaml -> stale_before=True (nothing to compare against)."""
    charter_file = tmp_path / "charter.md"
    charter_file.write_text(SAMPLE_CHARTER, encoding="utf-8")

    result = sync(charter_file, tmp_path)

    assert result.synced is False
    assert result.stale_before is True
    assert result.error is None


def test_sync_stale_before_false_when_metadata_hash_matches(tmp_path: Path):
    """A pre-existing metadata.yaml with a matching hash -> stale_before=False.

    The staleness COMPARISON is retained (only the WRITE side is retired) --
    ``sync()`` still consults whatever ``charter_hash`` is already on disk.
    """
    charter_file = tmp_path / "charter.md"
    charter_file.write_text(SAMPLE_CHARTER, encoding="utf-8")
    _write_metadata_with_hash(tmp_path, SAMPLE_CHARTER)

    result = sync(charter_file, tmp_path)

    assert result.synced is False
    assert result.stale_before is False
    assert result.files_written == []


def test_sync_stale_before_true_after_charter_modified(tmp_path: Path):
    """A charter.md edited after the last known-good hash -> stale_before=True."""
    charter_file = tmp_path / "charter.md"
    charter_file.write_text(SAMPLE_CHARTER, encoding="utf-8")
    _write_metadata_with_hash(tmp_path, SAMPLE_CHARTER)

    modified_content = SAMPLE_CHARTER + "\n4. New directive\n"
    charter_file.write_text(modified_content, encoding="utf-8")

    result = sync(charter_file, tmp_path)

    assert result.synced is False
    assert result.stale_before is True


def test_sync_repeated_calls_are_stable(tmp_path: Path):
    """Calling sync() repeatedly on unchanged content reports identically each time."""
    charter_file = tmp_path / "charter.md"
    charter_file.write_text(SAMPLE_CHARTER, encoding="utf-8")

    first = sync(charter_file, tmp_path, force=True)
    second = sync(charter_file, tmp_path, force=True)

    assert first.synced == second.synced == False  # noqa: E712 - explicit False comparison for readability of a stability assertion
    assert first.stale_before == second.stale_before
    assert first.files_written == second.files_written == []


def test_sync_custom_output_dir_writes_nothing(tmp_path: Path):
    """sync() to a non-default output_dir still writes nothing there."""
    charter_file = tmp_path / "charter.md"
    charter_file.write_text(SAMPLE_CHARTER, encoding="utf-8")

    output_dir = tmp_path / "custom_output"

    result = sync(charter_file, output_dir)

    assert result.synced is False
    assert result.files_written == []
    assert not output_dir.exists(), "sync() must not fabricate the output directory"


def test_sync_with_empty_charter_reports_no_error(tmp_path: Path):
    """An empty charter.md is handled gracefully -- still no write, no error."""
    charter_file = tmp_path / "charter.md"
    charter_file.write_text("", encoding="utf-8")

    result = sync(charter_file, tmp_path)

    assert result.synced is False
    assert result.error is None


def test_sync_missing_charter_file(tmp_path: Path):
    """Sync returns error when charter file doesn't exist."""
    charter_file = tmp_path / "nonexistent.md"

    result = sync(charter_file, tmp_path)

    assert result.synced is False
    assert result.error is not None
    assert "No such file" in result.error or "does not exist" in result.error.lower()
