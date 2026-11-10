"""Acceptance tests for the redirect coverage gate's self-test (#6933; ADR 2026-10-31-1 D-5).

``scripts/docs/site_redirects_selftest.py`` plants three mutants on a hard-linked copy of the
built site and requires the real gate's verdicts. Node is not on the pytest shards, so the
real gate runs in the docs-site job; here a gate is injected. A model of the real gate
passes, and every way a gate can go wrong (never failing, always failing, ignoring
``--docs``, a usage error) fails the self-test. The real built site is never modified.
"""

from __future__ import annotations

import importlib
import json
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _selftest() -> ModuleType:
    return importlib.import_module("scripts.docs.site_redirects_selftest")


def _write(root: Path, rel: str, text: str = "") -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _stub(target: str) -> str:
    return f'<!doctype html><title>Redirecting to: {target}</title><meta http-equiv="refresh" content="0;url={target}">'


MAP = {"/guides/old.html": "/guides/new/", "/guides/live.html": "/guides/live/", "/plans/note.html": "/plans/"}
DRAFT_ROUTE = "/plans/engineering-notes/note/"


@pytest.fixture
def site(tmp_path: Path) -> dict[str, Path]:
    """A built dist (pages plus one stub per key), its docs tree, declared map and baseline."""
    docs = tmp_path / "docs"
    _write(docs, "index.md", "---\ndoc_status: active\n---\n")
    _write(docs, "plans/engineering-notes/note.md", "---\ndoc_status: draft\n---\n")
    dist = tmp_path / "dist"
    for route in ("/", "/guides/new/", "/guides/live/", "/plans/"):
        _write(dist, f"{route.strip('/')}/index.html".lstrip("/"), f"<html>{route}</html>")
    for key, target in MAP.items():
        _write(dist, key.lstrip("/"), _stub(target))
    declared = _write(tmp_path, "legacy-redirects.json", json.dumps(MAP))
    baseline = _write(tmp_path, "url-baseline.txt", "\n".join(MAP) + "\n")
    return {"dist": dist, "docs": docs, "declared": declared, "baseline": baseline}


def _model_gate(args: Sequence[str]) -> int:
    """The real gate's verdicts, reduced to what the three mutants exercise."""
    baseline, dist = Path(args[0]), Path(args[1])
    declared = json.loads(Path(args[args.index("--declared-redirects") + 1]).read_text()) if "--docs" in args else {}
    for url in baseline.read_text().split():
        stub = dist / url.lstrip("/")
        if stub.is_file():
            target = stub.read_text().split("url=", 1)[1].split('"', 1)[0]
            if not (dist / target.strip("/") / "index.html").is_file():
                return 1
        elif declared.get(url) != DRAFT_ROUTE:
            return 1
    return 0


def _run(site: dict[str, Path], gate: object) -> list[str]:
    return list(_selftest().selftest(**site, gate=gate))


def test_a_gate_that_gives_every_expected_verdict_passes(site: dict[str, Path]) -> None:
    assert _run(site, _model_gate) == []


@pytest.mark.parametrize(
    ("gate", "failing"),
    [
        pytest.param(lambda args: 0, {"dead-target", "missing-key", "draft-excused"}, id="never-fails"),
        pytest.param(lambda args: 1, {"draft-excused"}, id="always-fails"),
        pytest.param(lambda args: _model_gate([a for a in args if a != "--docs"]), {"draft-excused"}, id="ignores-docs"),
        pytest.param(lambda args: 2, {"dead-target", "missing-key", "draft-excused"}, id="usage-error"),
    ],
)
def test_a_gate_with_a_wrong_verdict_fails_the_selftest(site: dict[str, Path], gate: object, failing: set[str]) -> None:
    problems = _run(site, gate)

    assert {problem.split(":", 1)[0] for problem in problems} == failing


def test_the_built_site_is_never_modified(site: dict[str, Path]) -> None:
    before = {path.relative_to(site["dist"]): path.read_bytes() for path in site["dist"].rglob("*") if path.is_file()}

    _run(site, _model_gate)

    after = {path.relative_to(site["dist"]): path.read_bytes() for path in site["dist"].rglob("*") if path.is_file()}
    assert after == before
    assert json.loads(site["declared"].read_text()) == MAP


def test_main_exits_one_and_names_the_mutant_on_a_mismatch(site: dict[str, Path], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    module = _selftest()
    monkeypatch.setattr(module, "_run_pnpm_gate", lambda args: 0)
    paths = ["--docs", str(site["docs"]), "--declared", str(site["declared"]), "--baseline", str(site["baseline"])]

    assert module.main([str(site["dist"]), *paths]) == 1
    assert "dead-target" in capsys.readouterr().err
