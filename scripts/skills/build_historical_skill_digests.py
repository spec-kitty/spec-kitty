#!/usr/bin/env python3
"""Build the frozen list of every skill render Spec Kitty shipped (#7700).

Reads the committed git history of the skill source roots and writes
``src/specify_cli/skills/data/historical_skill_renders.json``: for each
``<skill>/<relative path>``, the sorted sha256 digests of every version that
shipped. For ``SKILL.md`` it also records today's shared and native frontmatter
projection of each version, the bytes a projected install holds.

The list is append-only: the existing file is unioned with what history
yields, so no digest is ever dropped. Only committed bytes are recorded: it
refuses while a skill source has uncommitted changes, so commit the skill edit
first. Run it in a full-history clone::

    uv run --frozen python -m scripts.skills.build_historical_skill_digests
    uv run --frozen python -m scripts.skills.build_historical_skill_digests --check

``--check`` exits 1 when the file would change (a shipped skill was edited
without regenerating). The CLI never runs this; it only reads the result
(``specify_cli.skills.historical_renders``).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Iterable, Iterator, Mapping, Sequence
from pathlib import Path

from specify_cli.runtime.asset_preparation import digest
from specify_cli.skills.skill_frontmatter import SKILL_FILENAME, project_skill_bytes

SOURCE_ROOTS = ("src/doctrine/skills", "src/charter/offering/skills")
DATA_PATH = Path("src/specify_cli/skills/data/historical_skill_renders.json")
SCHEMA_VERSION = 1


def _sha256(data: bytes) -> str:
    return str(digest(data))  # the digest the install surfaces record (FileState.sha256)


#: sha256 of zero bytes: an empty file (a ``.gitkeep``) is no proof of authorship, so it is never recorded.
EMPTY_DIGEST = _sha256(b"")


def digests_for(relative: str, data: bytes, skill_name: str) -> set[str]:
    """Digests one shipped file version contributes: raw, plus projections for ``SKILL.md``.

    A zero-length version contributes nothing: an empty file proves no authorship.
    """
    if not data:
        return set()
    digests = {_sha256(data)}
    if relative == SKILL_FILENAME:
        for shared in (True, False):
            try:
                digests.add(_sha256(project_skill_bytes(data, shared=shared, skill_name=skill_name)))
            except (UnicodeError, ValueError):
                continue  # an unprojectable historical version still proves its raw bytes
    return digests


def merge_renders(existing: Mapping[str, Iterable[str]], new: Mapping[str, Iterable[str]]) -> dict[str, list[str]]:
    """Union two render maps; never drops a digest except the empty-file one, which proves nothing."""
    merged: dict[str, set[str]] = {key: set(values) for key, values in existing.items()}
    for key, values in new.items():
        merged.setdefault(key, set()).update(values)
    cleaned = {key: values - {EMPTY_DIGEST} for key, values in merged.items()}
    return {key: sorted(values) for key, values in sorted(cleaned.items()) if values}


def _split(path: str) -> tuple[str, str] | None:
    """``src/.../skills/<skill>/<rel>`` -> ``(skill, rel)``; ``None`` outside a skill directory."""
    for root in SOURCE_ROOTS:
        prefix = root + "/"
        if path.startswith(prefix):
            parts = path[len(prefix) :].split("/", 1)
            return (parts[0], parts[1]) if len(parts) == 2 and parts[1] else None
    return None


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout


def _history_blobs(repo: Path) -> dict[str, tuple[str, str]]:
    """Every distinct blob ever shipped under the source roots: ``{blob: (skill, rel)}`` per path."""
    blobs: dict[str, tuple[str, str]] = {}
    for commit in _git(repo, "log", "--format=%H", "--", *SOURCE_ROOTS).split():
        for line in _git(repo, "ls-tree", "-r", commit, "--", *SOURCE_ROOTS).splitlines():
            meta, _, path = line.partition("\t")
            split = _split(path)
            if split is not None and meta.split()[1] == "blob":
                blobs[f"{meta.split()[2]}\0{split[0]}\0{split[1]}"] = split
    return blobs


def _read_blobs(repo: Path, blob_ids: Sequence[str]) -> Iterator[tuple[str, bytes]]:
    process = subprocess.run(["git", "cat-file", "--batch"], cwd=repo, check=True, capture_output=True, input="\n".join(blob_ids).encode() + b"\n")
    out = process.stdout
    offset = 0
    for blob_id in blob_ids:
        header_end = out.index(b"\n", offset)
        size = int(out[offset:header_end].split()[2])
        start = header_end + 1
        yield blob_id, out[start : start + size]
        offset = start + size + 1


def _history_renders(repo: Path) -> dict[str, set[str]]:
    entries = _history_blobs(repo)
    blob_ids = sorted({key.split("\0", 1)[0] for key in entries})
    contents = dict(_read_blobs(repo, blob_ids))
    renders: dict[str, set[str]] = {}
    for key, (skill, relative) in entries.items():
        renders.setdefault(f"{skill}/{relative}", set()).update(digests_for(relative, contents[key.split("\0", 1)[0]], skill))
    return renders


def _serialize(renders: Mapping[str, list[str]]) -> str:
    payload = {"schema_version": SCHEMA_VERSION, "sources": list(SOURCE_ROOTS), "renders": renders}
    return json.dumps(payload, indent=1, sort_keys=True) + "\n"


def build(repo: Path) -> str:
    """The serialized list for *repo*: existing file ∪ every committed version of every skill file."""
    data_file = repo / DATA_PATH
    existing = json.loads(data_file.read_text(encoding="utf-8"))["renders"] if data_file.is_file() else {}
    renders = merge_renders(existing, _history_renders(repo))
    return _serialize(renders)


def _is_shallow(repo: Path) -> bool:
    return _git(repo, "rev-parse", "--is-shallow-repository").strip() == "true"


def _dirty_sources(repo: Path) -> list[str]:
    """Skill source paths with uncommitted (staged, unstaged or untracked) changes."""
    status = _git(repo, "status", "--porcelain", "--untracked-files=all", "--", *SOURCE_ROOTS)
    return [line[3:] for line in status.splitlines() if line.strip()]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="build_historical_skill_digests", description=__doc__)
    parser.add_argument("--check", action="store_true", help="exit 1 when the committed list is out of date")
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="repository root (default: current directory)")
    args = parser.parse_args(argv)
    repo: Path = args.repo
    if _is_shallow(repo):
        print("Refusing: shallow clone; run `git fetch --unshallow` first.", file=sys.stderr)
        return 2
    dirty = _dirty_sources(repo)
    if dirty:
        print(f"Refusing: uncommitted skill sources would be recorded forever; commit them first: {', '.join(dirty)}", file=sys.stderr)
        return 2
    text = build(repo)
    data_file = repo / DATA_PATH
    current = data_file.read_text(encoding="utf-8") if data_file.is_file() else ""
    if args.check:
        if text != current:
            print(f"{DATA_PATH} is out of date; regenerate it.", file=sys.stderr)
            return 1
        return 0
    if text != current:
        data_file.write_text(text, encoding="utf-8")
        print(f"Updated {DATA_PATH}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
