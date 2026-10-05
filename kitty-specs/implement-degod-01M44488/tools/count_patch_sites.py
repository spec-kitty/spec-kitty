"""Count test patch sites into the implement command family (SC-002).

Usage (from the repository root):

    uv run --frozen python kitty-specs/implement-degod-01M44488/tools/count_patch_sites.py [--json]

Family = every module under ``src/specify_cli/cli/commands/`` whose stem is ``implement`` or
starts with ``implement_`` (the command module, the siblings this mission adds, and
``implement_cores``). Re-pointing a patch from the command module to a sibling therefore does
NOT reduce the count.

Reported:
- ``string``  -- dotted string targets ``"specify_cli.cli.commands.<family>.<name>"`` used in
  ``patch(...)`` / ``monkeypatch.setattr(...)`` / ``mocker.patch(...)`` and any other string literal
  (the original #5635 measurement also counted every such literal);
- ``object``  -- ``monkeypatch.setattr(<alias>, "name", ...)`` / ``patch.object(<alias>, "name", ...)``
  where ``<alias>`` is bound in that test file to a family module (``import ... as``,
  ``from specify_cli.cli.commands import implement as``, ``importlib.import_module``);
- ``dispatch`` -- ``patch_collaborator(...)`` calls (the characterization dispatch-map helper):
  each one substitutes a family name, so it counts as a patch site too;
- ``console`` -- ``<alias>.console`` accesses (output-capture couplings to a family module);
- ``private_imports`` -- distinct ``_private`` names imported from a family module.

SC-002 compares ``string + object + dispatch`` (the patch-site total) against the baseline this script
measured on the mission base commit: 119 (95 string + 24 object; 10 console couplings; 46 distinct
private imports). The grounding's 112 was measured over ``implement`` only with a different
object-patch scanner.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
CMD_DIR = REPO / "src" / "specify_cli" / "cli" / "commands"
FAMILY = sorted(p.stem for p in CMD_DIR.glob("implement*.py") if p.stem == "implement" or p.stem.startswith("implement_"))
FAMILY_DOTTED = {f"specify_cli.cli.commands.{m}" for m in FAMILY}
STRING_RE = re.compile(r"[\"']specify_cli\.cli\.commands\.(" + "|".join(map(re.escape, FAMILY)) + r")\.([A-Za-z_][A-Za-z0-9_]*)")


def _family_aliases(tree: ast.AST) -> set[str]:
    aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name in FAMILY_DOTTED and a.asname:
                    aliases.add(a.asname)
        elif isinstance(node, ast.ImportFrom) and node.module == "specify_cli.cli.commands":
            for a in node.names:
                if a.name in FAMILY:
                    aliases.add(a.asname or a.name)
        elif isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            call = node.value
            fn = call.func
            name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
            if name == "import_module" and call.args and isinstance(call.args[0], ast.Constant) and call.args[0].value in FAMILY_DOTTED:
                aliases.update(t.id for t in node.targets if isinstance(t, ast.Name))
    return aliases


def _is_patch_call(call: ast.Call) -> bool:
    """``monkeypatch.setattr(...)`` / ``patch.object(...)`` (object-style patch calls)."""
    fn = call.func
    return isinstance(fn, ast.Attribute) and fn.attr in {"setattr", "object"}


def scan() -> dict[str, object]:
    string_hits: Counter[str] = Counter()
    object_hits: Counter[str] = Counter()
    console_hits = 0
    dispatch_hits = 0
    private_imports: set[str] = set()
    files_string: Counter[str] = Counter()
    for path in sorted((REPO / "tests").rglob("*.py")):
        text = path.read_text(encoding="utf-8", errors="replace")
        rel = path.relative_to(REPO).as_posix()
        # The dispatch map's own target strings are counted at their use sites
        # (``patch_collaborator`` calls), not as literals, to avoid double counting.
        literal_text = "" if path.name == "_implement_dispatch.py" else text
        for m in STRING_RE.finditer(literal_text):
            string_hits[f"{m.group(1)}.{m.group(2)}"] += 1
            files_string[rel] += 1
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        aliases = _family_aliases(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn = node.func
                fname = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
                if fname == "patch_collaborator":
                    dispatch_hits += 1
            if isinstance(node, ast.ImportFrom) and node.module in FAMILY_DOTTED:
                private_imports.update(f"{node.module.rsplit('.', 1)[1]}.{a.name}" for a in node.names if a.name.startswith("_"))
            if not aliases:
                continue
            if isinstance(node, ast.Call) and _is_patch_call(node) and len(node.args) >= 2:
                target, name = node.args[0], node.args[1]
                if isinstance(target, ast.Name) and target.id in aliases and isinstance(name, ast.Constant) and isinstance(name.value, str):
                    object_hits[name.value] += 1
            if isinstance(node, ast.Attribute) and node.attr == "console" and isinstance(node.value, ast.Name) and node.value.id in aliases:
                console_hits += 1
    total = sum(string_hits.values()) + sum(object_hits.values()) + dispatch_hits
    return {
        "family": FAMILY,
        "string": sum(string_hits.values()),
        "string_distinct": len(string_hits),
        "object": sum(object_hits.values()),
        "object_distinct": len(object_hits),
        "dispatch": dispatch_hits,
        "patch_sites_total": total,
        "console": console_hits,
        "private_imports_distinct": len(private_imports),
        "string_by_target": dict(string_hits.most_common()),
        "object_by_target": dict(object_hits.most_common()),
        "string_by_file": dict(files_string.most_common()),
    }


def main() -> int:
    result = scan()
    if "--json" in sys.argv:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    print(f"family: {', '.join(result['family'])}")
    print(f"string patch targets : {result['string']} ({result['string_distinct']} distinct)")
    print(f"object patch targets : {result['object']} ({result['object_distinct']} distinct)")
    print(f"dispatch-map patches : {result['dispatch']}")
    print(f"PATCH SITES TOTAL    : {result['patch_sites_total']}  (SC-002 baseline 119 on 2026-10-04, target <= 45)")
    print(f"console couplings    : {result['console']}")
    print(f"private imports      : {result['private_imports_distinct']} distinct")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
