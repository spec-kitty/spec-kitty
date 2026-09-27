import ast, sys
from pathlib import Path
SRC = Path.cwd() / "src"  # run from the repository root
def pkg_of(path):
    rel = path.relative_to(SRC).with_suffix("")
    parts = list(rel.parts)
    return parts[:-1] if parts[-1] != "__init__" else parts[:-1]
def resolve_from(node, path):
    if node.level == 0:
        base = node.module or ""
    else:
        pkg = pkg_of(path)
        pkg = pkg[: len(pkg) - (node.level - 1)] if node.level > 1 else pkg
        base = ".".join(pkg + ([node.module] if node.module else []))
    out = [base]
    for a in node.names:
        cand = SRC.joinpath(*base.split("."), a.name)
        if cand.is_dir() or cand.with_suffix(".py").is_file():
            out.append(f"{base}.{a.name}")
    return out
def collect(root):
    found = []
    for p in sorted(root.rglob("*.py")):
        t = ast.parse(p.read_text())
        for n in ast.walk(t):
            mods = []
            if isinstance(n, ast.ImportFrom):
                mods = resolve_from(n, p)
            elif isinstance(n, ast.Import):
                mods = [a.name for a in n.names]
            elif isinstance(n, ast.Call) and n.args and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str):
                f = n.func
                name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)
                if name in {"import_module", "__import__", "find_spec"}:
                    mods = [n.args[0].value]
            for m in mods:
                found.append((f"{p.relative_to(SRC)}:{n.lineno}", m))
    return found
F = "specify_cli.cli.commands"
hits = collect(SRC / "specify_cli" / "merge")
print([h for h in hits if h[1] == F or h[1].startswith(F + ".")])
print(sorted({h[0].split(':')[0] for h in hits if h[1].startswith("specify_cli.cli.console")}))
print(sorted({m for _, m in hits if m.startswith("specify_cli.cli")}))
