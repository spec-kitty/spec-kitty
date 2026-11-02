"""Conservative wheel-work selection; never a second code-test routing map.

Only documentation prose can be omitted. Unknown paths, metadata references,
missing diff bases and configuration errors request the real wheel/install
check. The workflow still publishes the stable clean-install check either way.
"""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path
import re
import subprocess
import tomllib
from collections.abc import Iterator
from typing import Any

_SHA = re.compile(r"[0-9a-fA-F]{40}\Z")


def _strings(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, child in value.items():
            yield str(key)
            yield from _strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _strings(child)


def _references(path: str, declared: str, root: Path) -> bool:
    # Treat exclusions as possible inputs too: false-positive builds are safe.
    pattern = declared.lstrip("/")
    if fnmatch.fnmatchcase(path, pattern) or fnmatch.fnmatchcase(path, f"{pattern.rstrip('/')}/*"):
        return True
    if "/" not in declared and fnmatch.fnmatchcase(Path(path).name, pattern):
        # Hatch's unanchored basename patterns match at every depth.
        return not declared.startswith("/")
    candidate = root / pattern
    if candidate.is_symlink():
        return root / path == candidate.resolve()
    return False


def requires_build(paths: list[str], root: Path) -> bool:
    """Prove a nonempty change is prose-only and outside declared build inputs."""
    if not paths or any(not path.startswith("docs/") or Path(path).suffix not in {".md", ".rst"} or ".." in Path(path).parts for path in paths):
        return True
    try:
        config = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
        project = config["project"]
        build = config["tool"]["hatch"]["build"]
        # Unknown build backends/hooks need their own input contract.
        backend = config["build-system"]["build-backend"]
        hooks = build.get("hooks", {})
        if backend != "hatchling.build" or set(hooks) != {"custom"} or hooks["custom"].get("path") != "hatch_build.py":
            return True
        inputs = list(_strings(project)) + list(_strings(build))
        return any(_references(path, declared, root) for path in paths for declared in inputs)
    except (OSError, ValueError, KeyError, TypeError):
        return True


def select_from_environment(root: Path) -> bool:
    """Mainline/queue/manual runs and any uncertain diff always verify a wheel."""
    base = os.environ.get("BASE_SHA", "")
    head = os.environ.get("HEAD_SHA", "")
    if os.environ.get("EVENT_NAME") != "pull_request" or not _SHA.fullmatch(base) or not _SHA.fullmatch(head):
        return True
    if set(base) == {"0"} or set(head) == {"0"}:
        return True
    try:
        diff = subprocess.run(
            ["git", "diff", "--name-only", "-z", base, head, "--"],
            cwd=root,
            capture_output=True,
            check=True,
        )
        paths = [path.decode("utf-8") for path in diff.stdout.split(b"\0") if path]
        return requires_build(paths, root)
    except (OSError, subprocess.CalledProcessError, UnicodeError):
        return True


if __name__ == "__main__":
    required = select_from_environment(Path.cwd())
    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as output:
        output.write(f"build-required={str(required).lower()}\n")
    print("wheel/install verification: " + ("required (inputs changed or uncertain)" if required else "not needed (non-input documentation prose only)"))
