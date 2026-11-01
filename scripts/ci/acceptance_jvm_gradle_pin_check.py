#!/usr/bin/env python3
"""Check the acceptance-jvm Gradle pins with the pinned ``gradle_pin_check.py`` (#6915, research D-8).

The contract tools are the ``contract-tools`` extra of spec-kitty-events that ``pins/read-service.source.yaml`` pins and
``make sync-services`` unpacks. The released tool's bare run (``check_all``) also scans a ``contracts/`` JVM subproject
that core no longer has, so this wrapper loads the tool by path and calls its ``check_acceptance_jvm(root)`` only. The
output and the exit code are the tool's own: every blocked finding, then every finding (``Finding.render()``), then the
counts line; 0 clean, 1 a pin mismatch, 2 blocked. When the tools themselves cannot be found the exit code is 2 too, with
the ``SERVICE_*`` code on stderr. Residual: an acceptance-only flag on the tool upstream would retire this wrapper.

Nothing from ``scripts`` is imported as a package: ``scripts/sync_services.py`` is loaded by its path.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from types import ModuleType

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SYNC_SERVICES = _REPO_ROOT / "scripts" / "sync_services.py"
READ_SERVICE = "read-service"
CONTRACT_TOOLS_EXTRA = "contract_tools"
TOOL = "gradle_pin_check.py"
EXIT_UNAVAILABLE = 2


class ToolsUnavailable(RuntimeError):
    """The pinned contract tools are not in the cache (or do not match their pin); ``code`` is the ``SERVICE_*`` code."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _load(path: Path, name: str) -> ModuleType:
    """Execute the script at *path* as module *name* (registered, so its dataclasses resolve their module)."""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path.name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def default_tools_root(repo_root: Path, cache_root: Path | None = None) -> Path:
    """The pinned ``contract-tools`` extra of ``read-service`` (``<extra>/contracts/tools``), unpacked from the verified cache."""
    sync_services = _load(_SYNC_SERVICES, "_sync_services_for_gradle_pin_check")
    try:
        root: Path = sync_services.extras_root(repo_root, READ_SERVICE, CONTRACT_TOOLS_EXTRA, cache_root=cache_root)
    except sync_services.SyncServicesError as error:
        raise ToolsUnavailable(error.code) from error
    return root / "contracts" / "tools"


def load_tool(tools_root: Path) -> ModuleType:
    """The ``gradle_pin_check`` module of *tools_root*; ``FileNotFoundError`` when it holds none."""
    script = Path(tools_root) / TOOL
    if not script.is_file():
        raise FileNotFoundError(f"{TOOL} is not in the contract tools directory")
    return _load(script, "_gradle_pin_check_for_acceptance_jvm")


def run(root: Path, tool: ModuleType, out: Callable[[str], None] = print) -> int:
    """Run ``check_acceptance_jvm(root)`` of *tool* and print its findings and counts line like the tool's own ``main``."""
    report = tool.check_acceptance_jvm(root)
    for finding in (*report.blocked, *report.findings):
        out(finding.render())
    out(report.counts_line())
    return int(report.exit_code)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check that acceptance-jvm's Gradle versions equal acceptance-jvm/tools/pins.json.")
    parser.add_argument("--root", type=Path, default=Path("."), help="repository root (default: .)")
    parser.add_argument(
        "--tools-root",
        type=Path,
        default=None,
        help="the contract tools directory (default: the pinned contract-tools extra of read-service, fetched by make sync-services)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        tools_root = default_tools_root(_REPO_ROOT) if args.tools_root is None else args.tools_root
        tool = load_tool(tools_root)
    except ToolsUnavailable as error:
        print(f"the pinned contract tools are not available ({error.code}); run `make sync-services`", file=sys.stderr)
        return EXIT_UNAVAILABLE
    except (FileNotFoundError, ImportError) as error:
        print(f"cannot load the Gradle pin check: {error}", file=sys.stderr)
        return EXIT_UNAVAILABLE
    return run(args.root, tool)


if __name__ == "__main__":
    sys.exit(main())
