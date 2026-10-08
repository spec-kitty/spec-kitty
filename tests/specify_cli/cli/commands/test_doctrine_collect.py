"""Focused tests for the ``_doctrine_collect`` collector module (WP03, #2059).

Exercise each Cluster J collector branch directly: pack-version resolution
(git / manifest / fallback), artifact counting, org-charter summary degradation,
profile-health collection (incl. the recorded-crash path), pack-entry assembly,
pack-health attachment, artifact-source resolution, project/org selection reads,
and selection-block composition. Targets >=90% coverage of the new module.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from specify_cli.cli.commands import _doctrine_collect as collect

pytestmark = [pytest.mark.fast]


# --- _resolve_pack_version ---------------------------------------------------


def test_resolve_pack_version_git_describe(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr(subprocess, "check_output", lambda *a, **k: "v1.2.3\n")
    version, fetched_at, is_git = collect._resolve_pack_version(tmp_path)
    assert version == "v1.2.3"
    assert fetched_at is None
    assert is_git is True


def test_resolve_pack_version_git_describe_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()

    def _boom(*_a: Any, **_k: Any) -> str:
        raise subprocess.CalledProcessError(1, "git")

    monkeypatch.setattr(subprocess, "check_output", _boom)
    version, _fetched, is_git = collect._resolve_pack_version(tmp_path)
    assert version == "git (version unavailable)"
    assert is_git is True


def test_resolve_pack_version_manifest(tmp_path: Path) -> None:
    (tmp_path / "pack-manifest.yaml").write_text("pack_version: '9.9.9'\nfetched_at: '2026-01-01'\n", encoding="utf-8")
    version, fetched_at, is_git = collect._resolve_pack_version(tmp_path)
    assert version == "9.9.9"
    assert fetched_at == "2026-01-01"
    assert is_git is False


def test_resolve_pack_version_manifest_malformed(tmp_path: Path) -> None:
    (tmp_path / "pack-manifest.yaml").write_text("::: not yaml :::\n", encoding="utf-8")
    version, fetched_at, is_git = collect._resolve_pack_version(tmp_path)
    assert version == "unknown"
    assert fetched_at is None
    assert is_git is False


# --- _count_pack_artifacts ---------------------------------------------------


def test_count_pack_artifacts(tmp_path: Path) -> None:
    (tmp_path / "directives").mkdir()
    (tmp_path / "directives" / "a.yaml").write_text("x", encoding="utf-8")
    (tmp_path / "directives" / "b.yaml").write_text("y", encoding="utf-8")
    (tmp_path / "tactics").mkdir()
    counts = collect._count_pack_artifacts(tmp_path)
    assert counts == {"directives": 2, "tactics": 0}


# --- _summarize_org_charter --------------------------------------------------


def test_summarize_org_charter_module_unavailable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / "org-charter.yaml").write_text("x: 1\n", encoding="utf-8")
    import builtins

    real_import = builtins.__import__

    def _fake_import(name: str, *a: Any, **k: Any) -> Any:
        if name == "charter.activation.org_charter":
            raise ImportError("not shipped")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", _fake_import)
    result = collect._summarize_org_charter(tmp_path)
    assert result == {"present": True, "module_available": False}


# --- _collect_org_layer_data + _collect_profile_health -----------------------


def test_collect_profile_health_records_crash(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Force the org-layer collector to return a clean dict and the profile
    # load to fail, so the crash is recorded into org_drg["errors"].
    monkeypatch.setattr(collect, "_collect_org_layer_data", lambda _r: {"errors": []})

    import charter.offering.service as svc

    def _boom(*_a: Any, **_k: Any) -> Any:
        raise RuntimeError("load failed")

    monkeypatch.setattr(svc, "CharterOfferingService", _boom)
    report = collect._collect_profile_health(tmp_path)
    assert any("profile-health load error" in e for e in report.org_drg["errors"])
    # Honest unhealthy: a recorded crash must not be vacuously green.
    assert report.healthy is False


# --- _attach_pack_health -----------------------------------------------------


class _FakePackHealth:
    layer = "org"

    def to_dict(self) -> dict[str, str]:
        return {"layer": "org", "status": "healthy"}


class _FakeReport:
    def __init__(self, packs: list[Any]) -> None:
        self.packs = packs


def test_attach_pack_health_attaches_to_present_packs() -> None:
    entries: list[dict[str, Any]] = [
        {"snapshot_present": True},
        {"snapshot_present": False},
    ]
    collect._attach_pack_health(entries, _FakeReport(packs=[_FakePackHealth()]))
    assert entries[0]["pack_health"] == {"layer": "org", "status": "healthy"}
    assert "pack_health" not in entries[1]


# --- _build_pack_entries -----------------------------------------------------


class _FakePack:
    def __init__(self, root: Path, present: bool) -> None:
        self._root = root
        self.name = "pack-a"
        self.source_type = "git"
        self.url = "https://example/pack"
        self.ref = "main"
        self._present = present

    def effective_root(self, _repo_root: Path) -> Path:
        return self._root


class _FakeRegistry:
    def __init__(self, packs: list[Any]) -> None:
        self.packs = packs


def test_build_pack_entries_present_snapshot(tmp_path: Path) -> None:
    snap = tmp_path / "snap"
    snap.mkdir()
    (snap / "pack-manifest.yaml").write_text("pack_version: '1.0'\n", encoding="utf-8")
    registry = _FakeRegistry([_FakePack(snap, present=True)])
    entries = collect._build_pack_entries(registry, tmp_path)
    assert entries[0]["snapshot_present"] is True
    assert entries[0]["pack_version"] == "1.0"
    assert entries[0]["artifact_counts"] == {}
    assert entries[0]["org_charter"] == {"present": False}


# --- _resolve_artifact_source ------------------------------------------------


class _FakeRepo:
    def __init__(self, provenance: dict[str, str]) -> None:
        self._provenance = provenance

    def get_provenance(self, item_id: str) -> str | None:
        return self._provenance.get(item_id)


class _FakeService:
    """Stands in for ``charter.activation.resolver.DoctrineService`` (WP03, #2059 followup:
    charter-sole-door-bypass-closure-01KZ3WAA T013). ``_resolve_artifact_source``
    now reads through the wrapper's ``raw_repository(plural)`` accessor rather
    than plain ``getattr(service, plural)`` (the gated per-kind properties on
    the real wrapper always return a filtered ``dict``, which has no
    ``.get_provenance()``), so this fake mirrors that accessor's shape.
    """

    def __init__(self, repos: dict[str, Any]) -> None:
        self._repos = repos

    def raw_repository(self, name: str) -> Any:
        return self._repos.get(name)


@pytest.mark.parametrize(
    "provenance,expected",
    [("builtin", "built-in"), ("project", "project"), ("org", "org")],
)
def test_resolve_artifact_source_from_provenance(provenance: str, expected: str) -> None:
    service = _FakeService({"directives": _FakeRepo({"d1": provenance})})
    result = collect._resolve_artifact_source("d1", "directives", service, {}, set())
    assert result == expected


# --- _read_project_selections + _read_org_required ---------------------------


def test_read_project_selections_reads_lists(tmp_path: Path) -> None:
    charter = tmp_path / ".kittify" / "charter"
    charter.mkdir(parents=True)
    (charter / "charter.yaml").write_text(
        "governance:\n  charter:\n    selected_directives:\n      - d1\n      - d2\n",
        encoding="utf-8",
    )
    selections = collect._read_project_selections(tmp_path)
    assert selections["directives"] == ["d1", "d2"]


def test_read_project_selections_malformed_degrades(tmp_path: Path) -> None:
    charter = tmp_path / ".kittify" / "charter"
    charter.mkdir(parents=True)
    (charter / "charter.yaml").write_text("::: bad :::\n", encoding="utf-8")
    selections = collect._read_project_selections(tmp_path)
    assert all(v == [] for v in selections.values())


# --- _build_selection_block --------------------------------------------------


def test_build_selection_block_dedup_and_order(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        collect,
        "_read_project_selections",
        lambda _r: {k: (["d1", "d2"] if k == "directives" else []) for k in collect._SELECTION_KIND_PLURALS},
    )
    monkeypatch.setattr(
        collect,
        "_read_org_required",
        lambda _r: {k: (["d2", "d3"] if k == "directives" else []) for k in collect._SELECTION_KIND_PLURALS},
    )
    monkeypatch.setattr(collect, "_resolve_artifact_source", lambda *a, **k: "built-in")

    import charter.offering.service as svc

    monkeypatch.setattr(svc, "CharterOfferingService", lambda **k: object())

    block = collect._build_selection_block(tmp_path)
    ids = [e["id"] for e in block["directives"]]
    # project ids first, org-required appended, deduped.
    assert ids == ["d1", "d2", "d3"]
    assert all(e["source"] == "built-in" for e in block["directives"])
