"""Shared helpers for the charter-pack cutover acceptance suite (#3732, C-006).

* :func:`covers` records which requirement ids a test covers; ``test_traceability``
  reads the decorators with ``ast``.
* :func:`run_cli` drives the real ``spec-kitty`` Typer app in-process.

Post-cutover modules are never imported at module level anywhere in this package:
an ``ImportError`` at collection time would error a whole file instead of one xfail.
"""

from __future__ import annotations

import contextlib
import subprocess
import hashlib
import json
import re
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any, TypeVar

from click.testing import Result
from ruamel.yaml import YAML

from ._requirements import ID_GRAMMAR

_T = TypeVar("_T")

_COVERS_ATTR = "__covers__"

_ANSI_SGR_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def covers(*ids: str) -> Callable[[_T], _T]:
    """Record the requirement ids a test function or class covers (``__covers__``)."""
    if not ids:
        raise ValueError("covers: at least one id is required")
    bad = [i for i in ids if not ID_GRAMMAR.match(i)]
    if bad:
        raise ValueError(f"covers: ids do not match the requirement id grammar: {bad}")

    def decorate(obj: _T) -> _T:
        existing = tuple(getattr(obj, _COVERS_ATTR, ()))
        setattr(obj, _COVERS_ATTR, existing + tuple(ids))
        return obj

    return decorate


# --------------------------------------------------------------------------------------
# CLI driving
# --------------------------------------------------------------------------------------


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences Rich may emit under CI."""
    return _ANSI_SGR_RE.sub("", text)


def run_cli(args: list[str], cwd: Path, *, input: str | None = None) -> Result:
    """Invoke ``spec-kitty <args>`` in-process with *cwd* as the working directory."""
    from typer.testing import CliRunner

    from specify_cli import app

    runner = CliRunner()
    with contextlib.chdir(cwd):
        return runner.invoke(app, args, input=input, catch_exceptions=True)


def output_of(result: Result) -> str:
    """Plain text of everything the command printed (stdout and stderr)."""
    return strip_ansi(result.output)


def describe(result: Result) -> str:
    """A failure message carrying the exit code, output and any exception."""
    exc = f"\nexception: {result.exception!r}" if result.exception is not None else ""
    return f"exit={result.exit_code}\noutput:\n{output_of(result)}{exc}"


def read_json_output(result: Result) -> Any:
    """Parse the first JSON document printed on stdout."""
    text = strip_ansi(result.stdout)
    starts = [i for i in (text.find("{"), text.find("[")) if i >= 0]
    if not starts:
        raise AssertionError(f"no JSON document on stdout\n{describe(result)}")
    try:
        value, _ = json.JSONDecoder().raw_decode(text[min(starts) :])
    except json.JSONDecodeError as exc:
        raise AssertionError(f"stdout is not JSON ({exc})\n{describe(result)}") from exc
    return value


# --------------------------------------------------------------------------------------
# Project state readers (independent of the production readers on purpose)
# --------------------------------------------------------------------------------------

GOVERNED_EXTRA_KEYS = ("activated_kinds", "mission_type_activations")


def load_yaml(path: Path) -> Any:
    """Safe-load a YAML file (``None`` for an empty document)."""
    return YAML(typ="safe").load(path.read_text(encoding="utf-8"))


def activation_store(project: Path) -> Path:
    """The file holding the active charter: ``config.yaml`` or its ``charter:`` pointer target."""
    config = project / ".kittify" / "config.yaml"
    data = load_yaml(config) if config.is_file() else None
    pointer = data.get("charter") if isinstance(data, dict) else None
    if isinstance(pointer, str) and pointer.strip():
        return project / pointer
    return config


def governed_keys(data: object) -> dict[str, object]:
    """The activation keys of a mapping: every ``activated_*`` key plus ``mission_type_activations``."""
    if not isinstance(data, dict):
        return {}
    return {k: v for k, v in data.items() if isinstance(k, str) and (k.startswith("activated_") or k in GOVERNED_EXTRA_KEYS)}


def active_charter(project: Path) -> dict[str, object]:
    """The governed keys of *project*'s resolved activation store."""
    store = activation_store(project)
    return governed_keys(load_yaml(store)) if store.is_file() else {}


# --------------------------------------------------------------------------------------
# Digests
# --------------------------------------------------------------------------------------


def sha256_hex(data: bytes) -> str:
    """Hex SHA-256 of raw bytes (file-integrity digest, not a charter hash)."""
    return hashlib.sha256(data).hexdigest()  # noqa: TID251 - file-integrity digest of raw bytes; charter.hasher hashes normalised text


def file_digest(path: Path) -> str:
    """Digest of a file's bytes."""
    return sha256_hex(path.read_bytes())


#: Agent directories always covered by :func:`tree_digest` (``AGENT_DIRS`` adds the rest).
_BASE_AGENT_ROOTS = (".claude", ".agents", ".codex", ".vibe")


def agent_roots() -> tuple[str, ...]:
    """Top-level agent directories (the canonical ``AGENT_DIRS`` plus the skill roots)."""
    roots = set(_BASE_AGENT_ROOTS)
    with contextlib.suppress(ImportError, AttributeError):
        from specify_cli.upgrade.migrations.m_0_9_1_complete_lane_migration import AGENT_DIRS

        roots.update(str(entry[0]).split("/")[0] for entry in AGENT_DIRS)
    return tuple(sorted(roots))


def _digest_targets(project: Path) -> Iterable[Path]:
    for name in (".kittify", ".gitignore", *agent_roots()):
        top = project / name
        if top.is_file():
            yield top
        elif top.is_dir():
            yield from (p for p in top.rglob("*") if p.is_file() and not p.is_symlink())


def tree_digest(project: Path) -> str:
    """Deterministic digest over ``.kittify/``, ``.gitignore`` and the agent directories (NFR-004)."""
    lines = sorted(f"{p.relative_to(project).as_posix()}\0{file_digest(p)}" for p in _digest_targets(project))
    return sha256_hex("\n".join(lines).encode())


# --------------------------------------------------------------------------------------
# Git
# --------------------------------------------------------------------------------------

_GIT_IDENTITY = ("-c", "user.name=Charter Pack Cutover Fixture", "-c", "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false")


def git(project: Path, *args: str) -> str:
    """Run ``git -C project <args>`` with a fixed identity; return stripped stdout."""

    proc = subprocess.run(["git", *_GIT_IDENTITY, "-C", str(project), *args], check=True, capture_output=True, text=True)
    return proc.stdout.strip()


def git_init_commit(project: Path, message: str = "fixture: initial state") -> None:
    """``git init -b main`` (when needed), stage everything and commit."""
    if not (project / ".git").exists():
        git(project, "init", "-q", "-b", "main")
    git(project, "add", "-A")
    git(project, "commit", "-q", "--no-verify", "--allow-empty", "-m", message)
