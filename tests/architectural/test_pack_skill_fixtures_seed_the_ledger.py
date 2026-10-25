"""Always-on gate: pack-skill fixtures never put activation keys in ``extra=``.

``tests/charter/skill_pack_support.write_config`` seeds activation into the
activation ledger through ``ledger=`` and raises when ``extra=`` carries an
activation key (#6595). That check runs only with its caller, and most callers
sit in nightly-only trees, so #6474's projection test merged green and went red
in the nightly (#6563). This gate reads every ``write_config`` call statically.
It fails closed: an ``extra=`` that is neither a string literal nor a name bound
once in the file to one, a ``*``/``**`` unpack, or a reference that is not a
direct call (an alias, ``functools.partial``) is unreadable and fails. Calls
inside ``with pytest.raises(ValueError)`` are the helper's own refusal tests.
"""

from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path

import pytest
import yaml

from charter.activation.activation_ledger import LEDGER_KEYS

pytestmark = [pytest.mark.architectural, pytest.mark.fast]

_TESTS_ROOT = Path(__file__).resolve().parents[1]
_HELPER = "write_config"
_MIN_CALLS = 30  # 37 callers when the gate landed; fewer means the scan stopped reading them
_UNREADABLE = None


def _string_constants(tree: ast.Module) -> dict[str, str]:
    """Module-level ``NAME = "..."`` whose name is bound nowhere else in the file."""
    nodes = list(ast.walk(tree))
    bound = Counter(n.id for n in nodes if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store))
    bound.update(n.arg for n in nodes if isinstance(n, ast.arg))
    bound.update((n.asname or n.name).split(".")[0] for n in nodes if isinstance(n, ast.alias))
    return {
        target.id: node.value.value
        for node in tree.body
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        and isinstance(target := node.targets[0] if isinstance(node, ast.Assign) else node.target, ast.Name)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
        and bound[target.id] == 1
    }


def _read_extra(call: ast.Call, constants: dict[str, str]) -> str | None:
    if any(kw.arg is None for kw in call.keywords) or any(isinstance(arg, ast.Starred) for arg in call.args):
        return _UNREADABLE
    extra = next((kw.value for kw in call.keywords if kw.arg == "extra"), ast.Constant(""))
    if isinstance(extra, ast.Constant) and isinstance(extra.value, str):
        return extra.value
    return constants.get(extra.id) if isinstance(extra, ast.Name) else _UNREADABLE


def _is_refusal_test(expr: str) -> bool:
    """``pytest.raises(ValueError, match=...ledger=...)``: the helper's own refusal of an activation key."""
    return expr.startswith("pytest.raises(ValueError") and "ledger=" in expr


def scan_source(source: str, filename: str) -> dict[str, str | None]:
    """``file:line:col`` of every ``write_config`` reference -> its ``extra=`` text, or None when unreadable."""
    tree = ast.parse(source, filename=filename)
    constants = _string_constants(tree)
    skipped: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.With) and any(_is_refusal_test(ast.unparse(item.context_expr)) for item in node.items):
            skipped.update(id(sub) for sub in ast.walk(node))
    calls = {id(node.func): node for node in ast.walk(tree) if isinstance(node, ast.Call)}
    found: dict[str, str | None] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.alias) and node.name == _HELPER and node.asname not in (None, _HELPER):
            found[f"{filename}:{node.lineno}:{node.col_offset}"] = _UNREADABLE
        elif isinstance(node, (ast.Name, ast.Attribute)) and (node.id if isinstance(node, ast.Name) else node.attr) == _HELPER and id(node) not in skipped:
            call = calls.get(id(node))
            found[f"{filename}:{node.lineno}:{node.col_offset}"] = _read_extra(call, constants) if call else _UNREADABLE
    return found


def activation_keys_in(extra: str) -> list[str]:
    """The activation keys in *extra*, read the way ``write_config`` reads them."""
    return sorted(set(yaml.safe_load(extra) or {}) & set(LEDGER_KEYS))


def _all_calls() -> dict[str, str | None]:
    found: dict[str, str | None] = {}
    for path in sorted(_TESTS_ROOT.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        if "skill_pack_support" in source and path.name != "skill_pack_support.py":
            found.update(scan_source(source, path.relative_to(_TESTS_ROOT.parent).as_posix()))
    return found


def test_scan_reads_the_callers() -> None:
    assert len(_all_calls()) >= _MIN_CALLS, "the scan stopped reading write_config callers"


def test_every_reference_is_readable() -> None:
    unread = [where for where, extra in _all_calls().items() if extra is _UNREADABLE]
    assert not unread, f"call write_config directly, with extra= a string literal or a module-level string constant: {unread}"


def test_no_caller_seeds_activation_through_extra() -> None:
    offenders = {where: keys for where, extra in _all_calls().items() if extra and (keys := activation_keys_in(extra))}
    assert not offenders, f"pass these activation keys through ledger=, not extra=: {offenders}"


_LEGACY_SHAPES = """\
from tests.charter import skill_pack_support as support
from tests.charter.skill_pack_support import write_config as wc
CONFIG = "agents: {}\\nactivated_skills: []\\n"
REBOUND = "agents: {}\\n"
REBOUND += "deactivated_skills: []\\n"
support.write_config(tmp_path, None, extra="activated_skills: []\\n")
support.write_config(tmp_path, None, extra=CONFIG)
support.write_config(tmp_path, None, extra=REBOUND)
support.write_config(tmp_path, None, extra=dynamic)
support.write_config(tmp_path, None, **kwargs)
with pytest.raises(ValueError, match="ledger="):
    support.write_config(tmp_path, None, extra="activated_skills: []\\n")
write = support.write_config
"""


def test_gate_flags_the_legacy_shape() -> None:
    """#6563: an activation key in a literal or a constant ``extra=`` is flagged; what cannot be read fails."""
    found = {int(where.split(":")[1]): extra for where, extra in scan_source(_LEGACY_SHAPES, "m.py").items()}

    assert {line: activation_keys_in(extra) for line, extra in found.items() if extra} == {6: ["activated_skills"], 7: ["activated_skills"]}
    assert sorted(line for line, extra in found.items() if extra is _UNREADABLE) == [2, 8, 9, 10, 13]
    assert 12 not in found  # the helper's own refusal test
