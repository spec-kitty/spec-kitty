"""#7346 operator ruling: a lifecycle record file is consolidate's bookkeeping.

``doctor ops --close-stale`` commits ``abandoned`` records in every checkout, lane
worktrees included, so the approval bound and the content axes must treat
``kitty-ops/lifecycle/<ULID>.json`` at the repository root as bookkeeping, as they
treat a root ``kitty-ops/<ULID>.jsonl`` Op record.
"""

from __future__ import annotations

import pytest

from specify_cli.consolidation.reconciliation_kernel import _is_bookkeeping

pytestmark = pytest.mark.unit

_ULID = "01M72B89ABCDEFGHJKMNPQRSTV"


@pytest.mark.parametrize("path", [f"kitty-ops/lifecycle/{_ULID}.json", f"kitty-ops/{_ULID}.jsonl"])
def test_root_kitty_ops_records_are_bookkeeping(path: str) -> None:
    assert _is_bookkeeping(path, "some-mission-01M72B89", None)


@pytest.mark.parametrize(
    "path",
    [
        f"src/kitty-ops/lifecycle/{_ULID}.json",
        f"kitty-ops/lifecycle/{_ULID}.jsonl",
        "kitty-ops/lifecycle/not-a-ulid.json",
        f"kitty-ops/lifecycle/sub/{_ULID}.json",
        "kitty-ops/lifecycle.jsonl",
        "kitty-ops/lifecycle",
    ],
)
def test_other_kitty_ops_shaped_paths_stay_content(path: str) -> None:
    assert not _is_bookkeeping(path, "some-mission-01M72B89", None)
