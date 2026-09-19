"""Decision Moment ledger package.

Re-exports the public API from ``models``, ``store``, and ``verify`` so
callers can do::

    from specify_cli.decisions import IndexEntry, DecisionIndex, load_index
    from specify_cli.decisions import verify, VerifyResponse, VerifyFinding
"""

from specify_cli.decisions.models import (
    DecisionErrorCode,
    DecisionIndex,
    DecisionOpenResponse,
    DecisionStatus,
    DecisionTerminalResponse,
    IndexEntry,
    OriginFlow,
    logical_key,
)
from specify_cli.decisions.store import (
    DecisionIndexReadError,
    append_entry,
    artifact_path,
    decisions_dir,
    find_by_logical_key,
    index_path,
    load_index,
    save_index,
    update_entry,
    write_artifact,
)
from specify_cli.decisions.verify import (
    SENTINEL_RE,
    VerifyFinding,
    VerifyResponse,
    scan_markers,
    verify,
)

__all__ = [
    # models
    "OriginFlow",
    "DecisionStatus",
    "DecisionErrorCode",
    "IndexEntry",
    "DecisionIndex",
    "DecisionOpenResponse",
    "DecisionTerminalResponse",
    "logical_key",
    # store
    "decisions_dir",
    "index_path",
    "artifact_path",
    "load_index",
    "save_index",
    "append_entry",
    "update_entry",
    "write_artifact",
    "find_by_logical_key",
    "DecisionIndexReadError",
    # verify
    "SENTINEL_RE",
    "VerifyFinding",
    "VerifyResponse",
    "scan_markers",
    "verify",
]
