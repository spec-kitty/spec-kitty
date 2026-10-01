"""Corpus-lane selection for ``packs.yml`` through the single gate-selection authority.

FR-009 (mission ``ci-runtime-stabilisation``, WP09): the ``-m corpus`` suite has ONE
owner, the Packs workflow. Its ``changes`` job must select the corpus lane on every
path that used to select the router's (now deleted) ``tests (corpus)`` job. The
predicate being mirrored is the router's own ``changes.outputs.corpus`` fold in
``ci-router.yml``::

    (mode == 'full' || unmatched src/**) ? 'true' : <the `corpus` dorny filter group>

That predicate is answered here by :func:`scripts.ci.gate_selection.select_gates`,
which parses the router's ``corpus`` filter group straight out of ``ci-router.yml``.
There is deliberately NO glob list in this module or in ``packs.yml`` (C-003, #2476:
a second hand-maintained encoding is the drift hazard the authority exists to close);
the unmatched-``src/**`` fan-out (C-008, #4368) is inherited from ``select_gates``.

The workflow step runs this file as a bare script before any ``uv sync``; PyYAML is
the only third-party import (pulled in by ``gate_selection``), installed by the
workflow with the same pinned ``pip install`` ``ci-modules.yml`` uses.

Contract of :func:`main` (the workflow edge):

* ``--mode`` / ``--event`` -- the run mode (``pr`` / ``full``) and the GitHub event name;
* ``CHANGED_FILES`` -- a JSON array of changed paths, ``CHANGED_OUTCOME`` -- the diff
  step's outcome. Anything other than ``success`` (or an unparseable list) means the
  diff is UNAVAILABLE and the selection fails closed to ``true``;
* writes ``selected=true|false`` to ``$GITHUB_OUTPUT`` when set and prints
  ``corpus selection: <bool> (<reason>)``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

# Actions runs this trusted-checkout script before installing the package, and
# ``scripts.ci`` resolves as a namespace package only with the repo root on the
# path. Resolve from the script, never the caller's cwd.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.ci.gate_selection import Router, load_router, select_gates  # noqa: E402  (import after the path guard above)

__all__ = ["corpus_selected", "decide", "main"]

_CORPUS_GROUP = "corpus"
_SUCCESS = "success"
_PUSH_EVENT = "push"
_FULL_MODE = "full"


def corpus_selected(paths: Sequence[str], *, router: Router, mode: str = "pr") -> bool:
    """Whether ``paths`` select the corpus lane (the router's ``changes.outputs.corpus`` fold)."""
    selection = select_gates(paths, router=router, mode=mode)
    return mode == _FULL_MODE or selection.unmatched_src or _CORPUS_GROUP in selection.matched_groups


def _reason(paths: Sequence[str], *, router: Router, mode: str) -> str:
    if mode == _FULL_MODE:
        return "full mode runs everything"
    selection = select_gates(paths, router=router, mode=mode)
    if selection.unmatched_src:
        return "unmatched src/** fan-out (C-008)"
    if _CORPUS_GROUP in selection.matched_groups:
        return "diff touches the router corpus group"
    return "no corpus path in the diff"


def decide(
    changed: Sequence[str] | None,
    *,
    router: Router,
    mode: str,
    event_name: str,
) -> tuple[bool, str]:
    """Return ``(selected, reason)``.

    ``changed is None`` means the diff is unavailable: fail closed to ``True``.
    A push (to ``main``) selects unconditionally, like the Packs lane outputs.
    """
    if changed is None:
        return True, "fail-closed: the changed-file list is unavailable"
    if event_name == _PUSH_EVENT:
        return True, "push runs everything"
    return corpus_selected(changed, router=router, mode=mode), _reason(changed, router=router, mode=mode)


def _changed_from_env(environ: Mapping[str, str]) -> list[str] | None:
    """The changed paths from ``CHANGED_FILES`` / ``CHANGED_OUTCOME``; ``None`` when unusable."""
    if environ.get("CHANGED_OUTCOME", "") != _SUCCESS:
        return None
    try:
        parsed = json.loads(environ.get("CHANGED_FILES", ""))
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
        return None
    return list(parsed)


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Select the Packs corpus lane via the single gate-selection authority.")
    parser.add_argument("--mode", default="pr", choices=("pr", _FULL_MODE), help="run mode (pr or full)")
    parser.add_argument("--event", default="", help="GitHub event name (pull_request, push, workflow_dispatch)")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Workflow edge: env in, ``$GITHUB_OUTPUT`` out. Always exits 0 (the verdict is the output)."""
    args = _parse_args(argv)
    selected, reason = decide(_changed_from_env(os.environ), router=load_router(), mode=args.mode, event_name=args.event)
    verdict = "true" if selected else "false"
    print(f"corpus selection: {verdict} ({reason})")
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as handle:
            handle.write(f"selected={verdict}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
