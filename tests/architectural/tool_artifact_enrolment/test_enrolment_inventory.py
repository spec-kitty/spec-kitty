"""Tool-artifact enrolment inventory (WP10 / owner contract C1, FR-007/FR-013).

C1 bounds the unbounded universal "any path spec-kitty writes" with a **tool-derived
inventory of generated-write sites** that self-asserts in BOTH directions — no
discovered write sink missing from it, and no inventory row without a live sink. Every
row is the site a lifecycle transaction must enrol (commit-or-revert, C2). This is the
countermeasure's landing of the *mechanism*: as the owner (``coordination/transaction``)
enrols each site, its disposition moves ``pending`` → ``enrolled``.

**Cloned from ``tests/architectural/untrusted_path_audit``** — the exact shape C1 names
("Reuse, do not reinvent … clone that shape. Never hand-write the list"):

* an AST matcher discovers generated-write sinks (``write_text`` / ``write_bytes`` /
  ``touch`` / ``replace`` / ``atomic_write`` / ``write_text_within_directory``) across
  the generated-write **surfaces**;
* rows are compared by the **drift-proof composite key** ``(rel_path, qualname, token)``
  from :func:`tests.architectural._ratchet_keys.composite_key_from_file` — a blank/comment
  insertion that shifts a line leaves the inventory GREEN, a real edit/rename reddens it;
* both tripwires fire: **undercount** (a discovered sink absent from ``inventory.md``) and
  **overcount / ghost** (an ``inventory.md`` row with no live sink), each a PURE seam.

Scope boundary (documented, like untrusted's RULESET): the surfaces are the generated-
write **owner** surfaces — ``coordination/transaction.py`` (the transaction owner) and
``merge/bookkeeping_projection.py`` (the bookkeeping projector). As the owner grows to
enrol further sinks, add its surface here and re-freshen the inventory from the tool
output — never by hand.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.architectural._ratchet_keys import composite_key_from_file

_THIS = Path(__file__).resolve()
_REPO_ROOT = _THIS.parents[3]

pytestmark = [pytest.mark.architectural]

_SRC_ROOT = _REPO_ROOT / "src"
INVENTORY_PATH = _THIS.parent / "inventory.md"

#: Generated-write **surfaces** (repo-relative). Tool-derived scope of the enrolment
#: inventory — the owner surfaces whose write sinks a transaction must enrol.
ENROLMENT_SURFACES: tuple[str, ...] = (
    "src/specify_cli/coordination/transaction.py",
    "src/specify_cli/merge/bookkeeping_projection.py",
)

#: Path-method write sinks (``<path>.write_bytes(...)`` etc.).
SINK_METHODS: frozenset[str] = frozenset({"write_text", "write_bytes", "touch", "replace"})
#: Free / qualified write sinks (``atomic_write(...)`` / ``write_text_within_directory(...)``).
SINK_FUNCTIONS: frozenset[str] = frozenset({"atomic_write", "write_text_within_directory"})

#: Composite row identity ``(rel_path, qualname, truncated token)`` — mirrors audit.py.
RowKey = tuple[str, str, str]
TOKEN_MAX_LEN = 60
TOKEN_ELLIPSIS = "…"

#: Valid enrolment dispositions (human judgement recorded in inventory.md).
VALID_DISPOSITIONS: frozenset[str] = frozenset({"enrolled", "pending-owner"})
_INVENTORY_ROW_CELLS = 5


def truncate_token(token: str) -> str:
    """Compact *token* to ``TOKEN_MAX_LEN`` chars with a ``…`` marker (audit.py parity)."""
    if len(token) <= TOKEN_MAX_LEN:
        return token
    return token[:TOKEN_MAX_LEN] + TOKEN_ELLIPSIS


def composite_row_key(rel_path: str, line: int) -> RowKey:
    """Drift-proof identity ``(rel_path, qualname, truncated token)`` for a sink."""
    qualname, token = composite_key_from_file(_REPO_ROOT / rel_path, line)
    return (rel_path, qualname, truncate_token(token))


@dataclass(frozen=True)
class WriteSink:
    """One discovered generated-write sink."""

    rel_path: str
    line: int
    sink_op: str

    def key(self) -> RowKey:
        return composite_row_key(self.rel_path, self.line)

    def locator(self) -> str:
        return f"{self.rel_path}:{self.line}"


def _method_sink(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Attribute) and node.func.attr in SINK_METHODS:
        return f".{node.func.attr}()"
    return None


def _function_sink(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name) and func.id in SINK_FUNCTIONS:
        return f"{func.id}(...)"
    if isinstance(func, ast.Attribute) and func.attr in SINK_FUNCTIONS:
        return f"{func.attr}(...)"
    return None


def _scan_surface(rel_path: str) -> list[WriteSink]:
    path = _REPO_ROOT / rel_path
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    sinks: list[WriteSink] = []
    seen: set[tuple[int, str]] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        sink_op = _method_sink(node) or _function_sink(node)
        if sink_op is None:
            continue
        dedup = (node.lineno, sink_op)
        if dedup in seen:
            continue
        seen.add(dedup)
        sinks.append(WriteSink(rel_path, node.lineno, sink_op))
    return sinks


def discover_write_sinks() -> list[WriteSink]:
    """Every generated-write sink across the enrolment surfaces, sorted."""
    sinks: list[WriteSink] = []
    for rel_path in ENROLMENT_SURFACES:
        sinks.extend(_scan_surface(rel_path))
    sinks.sort(key=lambda s: (s.rel_path, s.line, s.sink_op))
    return sinks


# --------------------------------------------------------------------------- #
# Inventory parsing + both-direction tripwires (PURE seams — audit.py parity).
# --------------------------------------------------------------------------- #
def _parse_inventory_rows(text: str) -> list[dict[str, str]]:
    """Parse the markdown sink table: ``| file:line | qualname | token | op | disposition |``."""
    rows: list[dict[str, str]] = []
    in_table = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("| file:line "):
            in_table = True
            continue
        if in_table and line.replace(" ", "").startswith("|---"):
            continue
        if in_table:
            if not line.startswith("|"):
                in_table = False
                continue
            cells = [c.strip().strip("`").strip() for c in line.strip("|").split("|")]
            if len(cells) < _INVENTORY_ROW_CELLS:
                continue
            rows.append(
                {
                    "locator": cells[0],
                    "qualname": cells[1],
                    "token": cells[2],
                    "sink_op": cells[3],
                    "disposition": cells[4],
                }
            )
    return rows


def _inventory_row_key(row: dict[str, str]) -> RowKey | None:
    rel = row["locator"].rpartition(":")[0]
    qualname = row["qualname"]
    token = row["token"]
    if not rel or not qualname or not token:
        return None
    return (rel, qualname, token)


def build_discovered_key_map(discovered: list[WriteSink]) -> dict[RowKey, str]:
    out: dict[RowKey, str] = {}
    for sink in discovered:
        out.setdefault(sink.key(), sink.locator())
    return out


def build_inventory_key_map(rows: list[dict[str, str]]) -> tuple[list[str], dict[RowKey, str]]:
    errors: list[str] = []
    out: dict[RowKey, str] = {}
    for row in rows:
        key = _inventory_row_key(row)
        if key is None:
            errors.append(f"inventory row {row['locator']!r} has an unparseable identity")
            continue
        out[key] = row["locator"]
    return errors, out


def check_undercount(discovered: Mapping[RowKey, str], inventory: Mapping[RowKey, str]) -> list[str]:
    """Every discovered generated-write sink must be enrolled in the inventory."""
    errors: list[str] = []
    for key in sorted(set(discovered) - set(inventory)):
        rel_path, qualname, token = key
        errors.append(
            f"generated-write sink {discovered[key]} (qualname={qualname!r}, token={token!r}) "
            f"is MISSING from inventory.md (undercount): a write site is unenrolled. Add: "
            f"| {discovered[key]} | {qualname} | {token} | <op> | pending-owner |"
        )
    return errors


def check_overcount(discovered: Mapping[RowKey, str], inventory: Mapping[RowKey, str]) -> list[str]:
    """Every inventory row must map to a live sink (ghost/overcount tripwire)."""
    errors: list[str] = []
    for key in sorted(set(inventory) - set(discovered)):
        rel_path, qualname, token = key
        errors.append(
            f"inventory row {inventory[key]} (qualname={qualname!r}, token={token!r}) has NO "
            f"live write sink (overcount/ghost): the sink was removed or edited. Delete or "
            f"re-freshen the row from the tool output."
        )
    return errors


# =========================================================================== #
# Tests.
# =========================================================================== #
def _load_inventory() -> list[dict[str, str]]:
    assert INVENTORY_PATH.exists(), f"inventory.md missing at {INVENTORY_PATH}"
    rows = _parse_inventory_rows(INVENTORY_PATH.read_text(encoding="utf-8"))
    assert rows, "inventory.md parsed to zero sink rows — the table is empty/malformed."
    return rows


def test_inventory_exactly_enrols_every_live_write_sink() -> None:
    """The nonempty live corpus and inventory agree in both directions."""
    discovered = discover_write_sinks()
    assert discovered, "zero generated-write sinks discovered across the enrolment surfaces — a surface-path misconfiguration, not a genuinely empty result."
    inventory_rows = _load_inventory()
    parse_errors, inventory_keys = build_inventory_key_map(inventory_rows)
    assert not parse_errors, "\n".join(parse_errors)
    discovered_keys = build_discovered_key_map(discovered)
    missing = check_undercount(discovered_keys, inventory_keys)
    assert not missing, "unenrolled generated-write sink(s):\n" + "\n".join(f"  {m}" for m in missing)
    ghosts = check_overcount(discovered_keys, inventory_keys)
    assert not ghosts, "ghost inventory row(s):\n" + "\n".join(f"  {g}" for g in ghosts)
    invalid = [f"{row['locator']}: {row['disposition']!r}" for row in inventory_rows if row["disposition"] not in VALID_DISPOSITIONS]
    assert not invalid, f"rows with invalid disposition (must be one of {sorted(VALID_DISPOSITIONS)}):\n" + "\n".join(f"  {r}" for r in invalid)

    # Controlled incompatible changes prove both sides of the oracle bite.
    key: RowKey = ("m.py", "f", "p write_bytes")
    assert check_undercount({key: "m.py:2"}, {}), "a discovered-but-unenrolled sink must go RED"
    assert check_overcount({}, {key: "m.py:9"}), "a ghost inventory row must go RED"
