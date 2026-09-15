"""Contract tests for the atomic-write snapshot helper."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import yaml

from specify_cli.doctrine.snapshot import fetch_pack, write_pack_manifest, write_snapshot
from specify_cli.doctrine.sources.protocol import FetchResult


import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]


@dataclass
class _ScriptedSource:
    """Test double implementing the OrgDoctrineSource protocol structurally."""

    layout: Callable[[Path], None]
    result: FetchResult
    url: str = "https://example.com/pack.tar.gz"

    def fetch(self, target_dir: Path) -> FetchResult:
        target_dir.mkdir(parents=True, exist_ok=True)
        self.layout(target_dir)
        return self.result


def _populate_valid_pack(target_dir: Path) -> None:
    directives = target_dir / "directives"
    directives.mkdir(parents=True, exist_ok=True)
    (directives / "sec-001.directive.yaml").write_text("id: sec-001\n")
    agents = target_dir / "agent_profiles"
    agents.mkdir(parents=True, exist_ok=True)
    (agents / "eng.agent.yaml").write_text("id: eng\n")


class TestFetchPackEnvVarExpansion:
    """Adversarial-squad follow-up: ``fetch_pack`` must write to the SAME
    expanded directory ``effective_root()`` reads from, not the raw
    ``${VAR}``-templated ``local_path`` literal."""

    def test_fetch_pack_writes_into_expanded_target_not_literal_template(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from charter.offering.drg.org_pack_config import OrgPackConfig

        env_var = "SPEC_KITTY_PACK_HOME"
        monkeypatch.setenv(env_var, str(tmp_path))

        pack = OrgPackConfig(
            name="acme",
            local_path=Path("${" + env_var + "}/acme-doctrine"),
            source_type="https",
            url="https://example.com/pack.tar.gz",
        )
        source = _ScriptedSource(
            layout=_populate_valid_pack,
            result=FetchResult(ok=True, artifacts_written=2, pack_version="v1.0.0"),
        )
        monkeypatch.setattr("specify_cli.doctrine.snapshot._build_source", lambda _pack: source)

        result = fetch_pack(pack, tmp_path)

        assert result.ok is True
        expanded_target = tmp_path / "acme-doctrine"
        assert (expanded_target / "directives" / "sec-001.directive.yaml").is_file()
        # The literal, unexpanded template must NOT exist as a directory name.
        literal_target = tmp_path / ("${" + env_var + "}")
        assert not literal_target.exists()

    def test_fetch_pack_fails_closed_on_unset_env_var(self, tmp_path: Path) -> None:
        from charter.offering.drg.org_pack_config import OrgPackConfig

        pack = OrgPackConfig(
            name="acme",
            local_path=Path("${SPEC_KITTY_DOES_NOT_EXIST}/acme-doctrine"),
            source_type="https",
            url="https://example.com/pack.tar.gz",
        )
        result = fetch_pack(pack, tmp_path)
        assert result.ok is False
        assert any("SPEC_KITTY_DOES_NOT_EXIST" in err for err in result.errors)


class TestWriteSnapshot:
    def test_atomic_write_success(self, tmp_path: Path) -> None:
        local_path = tmp_path / "doctrine"
        source = _ScriptedSource(
            layout=_populate_valid_pack,
            result=FetchResult(ok=True, artifacts_written=2, pack_version="v1.0.0"),
        )

        result = write_snapshot(source, local_path)

        assert result.ok is True
        assert (local_path / "directives" / "sec-001.directive.yaml").is_file()
        # No leftover staging directory.
        leftover = list(tmp_path.glob(".tmp-*"))
        assert leftover == []
        # Manifest written.
        assert (local_path / "pack-manifest.yaml").is_file()

    def test_atomic_write_fetch_failure_preserves_existing(self, tmp_path: Path) -> None:
        local_path = tmp_path / "doctrine"
        # Pre-existing snapshot must remain unchanged on failure.
        _populate_valid_pack(local_path)
        (local_path / "marker").write_text("keep-me\n")

        def _broken_layout(target_dir: Path) -> None:
            # Source writes nothing useful before declaring failure.
            target_dir.mkdir(parents=True, exist_ok=True)

        source = _ScriptedSource(
            layout=_broken_layout,
            result=FetchResult(
                ok=False,
                artifacts_written=0,
                pack_version=None,
                errors=["network down"],
            ),
        )

        result = write_snapshot(source, local_path)

        assert result.ok is False
        assert (local_path / "marker").read_text() == "keep-me\n"
        # Staging dir cleaned up.
        leftover = list(tmp_path.glob(".tmp-*"))
        assert leftover == []

    def test_atomic_write_replaces_existing(self, tmp_path: Path) -> None:
        local_path = tmp_path / "doctrine"
        _populate_valid_pack(local_path)
        # Stale file from the previous snapshot must not survive replace.
        (local_path / "stale.txt").write_text("old\n")

        def _new_layout(target_dir: Path) -> None:
            directives = target_dir / "directives"
            directives.mkdir(parents=True, exist_ok=True)
            (directives / "new.directive.yaml").write_text("id: new\n")

        source = _ScriptedSource(
            layout=_new_layout,
            result=FetchResult(ok=True, artifacts_written=1, pack_version="v2"),
        )

        result = write_snapshot(source, local_path)

        assert result.ok is True
        assert (local_path / "directives" / "new.directive.yaml").is_file()
        assert not (local_path / "stale.txt").exists()

    def test_replace_failure_restores_existing_snapshot(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        local_path = tmp_path / "doctrine"
        _populate_valid_pack(local_path)
        (local_path / "marker").write_text("keep-me\n")

        source = _ScriptedSource(
            layout=_populate_valid_pack,
            result=FetchResult(ok=True, artifacts_written=2, pack_version="v2"),
        )

        original_replace = Path.replace

        def _flaky_replace(self: Path, target: Path) -> Path:
            if self.name.startswith(".tmp-"):
                raise OSError("promote failed")
            return original_replace(self, target)

        monkeypatch.setattr(Path, "replace", _flaky_replace)

        result = write_snapshot(source, local_path)

        assert result.ok is False
        assert "promote failed" in " ".join(result.errors)
        assert (local_path / "marker").read_text() == "keep-me\n"
        assert not list(tmp_path.glob(".tmp-*"))
        assert not list(tmp_path.glob(".old-*"))

    def test_replace_and_restore_failure_preserves_recovery_backup(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A double filesystem fault must never delete the only last-good tree."""
        local_path = tmp_path / "doctrine"
        _populate_valid_pack(local_path)
        (local_path / "marker").write_text("last-good\n")
        source = _ScriptedSource(
            layout=_populate_valid_pack,
            result=FetchResult(ok=True, artifacts_written=2, pack_version="v2"),
        )
        original_replace = Path.replace

        def _double_fault(self: Path, target: Path) -> Path:
            if self.name.startswith(".tmp-"):
                raise OSError("promote failed")
            if self.name.startswith(".old-"):
                raise OSError("restore failed")
            return original_replace(self, target)

        monkeypatch.setattr(Path, "replace", _double_fault)

        result = write_snapshot(source, local_path)

        assert result.ok is False
        assert "promote failed" in " ".join(result.errors)
        assert "restore failed" in " ".join(result.errors)
        backups = list(tmp_path.glob(".old-*"))
        assert len(backups) == 1
        assert (backups[0] / "marker").read_text() == "last-good\n"
        assert str(backups[0]) in " ".join(result.errors)

    def test_failed_unchanged_result_cannot_be_promoted_to_success(self, tmp_path: Path) -> None:
        """FetchResult invariants fail closed even for third-party adapters."""
        local_path = tmp_path / "doctrine"
        _populate_valid_pack(local_path)
        source = _ScriptedSource(
            layout=lambda _target: None,
            result=FetchResult(
                ok=False,
                artifacts_written=0,
                pack_version=None,
                unchanged=True,
                errors=["adapter failed"],
            ),
        )

        result = write_snapshot(source, local_path)

        assert result.ok is False
        assert result.unchanged is True
        assert result.errors == ["adapter failed"]

    def test_manifest_write_failure_preserves_last_good_snapshot(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Manifest construction is staged before the atomic promotion."""
        local_path = tmp_path / "doctrine"
        _populate_valid_pack(local_path)
        (local_path / "marker").write_text("last-good\n")
        source = _ScriptedSource(
            layout=_populate_valid_pack,
            result=FetchResult(ok=True, artifacts_written=2, pack_version="v2"),
        )
        original_write_bytes = Path.write_bytes

        def _fail_manifest(self: Path, data: bytes) -> int:
            if self.name == "pack-manifest.yaml":
                raise OSError("manifest disk full")
            return original_write_bytes(self, data)

        monkeypatch.setattr(Path, "write_bytes", _fail_manifest)

        result = write_snapshot(source, local_path)

        assert result.ok is False
        assert "manifest disk full" in " ".join(result.errors)
        assert (local_path / "marker").read_text() == "last-good\n"
        assert not list(tmp_path.glob(".tmp-*"))
        assert not list(tmp_path.glob(".old-*"))

    def test_empty_snapshot_rejected(self, tmp_path: Path) -> None:
        local_path = tmp_path / "doctrine"

        def _empty_layout(target_dir: Path) -> None:
            # Source claims success but writes no recognised artifact dirs.
            (target_dir / "random.txt").write_text("noise\n")

        source = _ScriptedSource(
            layout=_empty_layout,
            result=FetchResult(ok=True, artifacts_written=0, pack_version=None),
        )

        result = write_snapshot(source, local_path)

        assert result.ok is False
        assert any("No artifact directories" in err for err in result.errors)
        # local_path was never populated.
        assert not local_path.exists()

    def test_subdir_validates_effective_root(self, tmp_path: Path) -> None:
        """HTTPS/API archives may nest the pack under ``pack/`` (FR-007).

        After a single top-dir flatten the snapshot root is ``pack/…`` with
        artifact dirs only inside that subdir. Validation and the manifest
        must target the effective root, not the clone/snapshot root.
        """
        local_path = tmp_path / "doctrine-rnd"

        def _nested_pack_layout(target_dir: Path) -> None:
            _populate_valid_pack(target_dir / "pack")

        source = _ScriptedSource(
            layout=_nested_pack_layout,
            result=FetchResult(ok=True, artifacts_written=2, pack_version="v9"),
        )

        result = write_snapshot(source, local_path, subdir="pack", source_type="https")

        assert result.ok is True
        assert (local_path / "pack" / "directives" / "sec-001.directive.yaml").is_file()
        # Manifest at effective root so doctor doctrine finds it.
        manifest_path = local_path / "pack" / "pack-manifest.yaml"
        assert manifest_path.is_file()
        manifest = yaml.safe_load(manifest_path.read_text())
        assert manifest["artifact_counts"]["directives"] == 1
        assert not (local_path / "pack-manifest.yaml").exists()

    def test_subdir_rejects_when_only_wrapper_present(self, tmp_path: Path) -> None:
        """Without ``subdir``, a nested ``pack/`` tree is rejected (legacy)."""
        local_path = tmp_path / "doctrine-rnd"

        def _nested_pack_layout(target_dir: Path) -> None:
            _populate_valid_pack(target_dir / "pack")

        source = _ScriptedSource(
            layout=_nested_pack_layout,
            result=FetchResult(ok=True, artifacts_written=2, pack_version="v9"),
        )

        result = write_snapshot(source, local_path)

        assert result.ok is False
        assert any("No artifact directories" in err for err in result.errors)
        assert not local_path.exists()

    def test_fetch_pack_passes_subdir_to_write_snapshot(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from specify_cli.doctrine.config import OrgPackConfig

        pack = OrgPackConfig(
            name="doctrine-rnd",
            local_path=tmp_path / "doctrine-rnd",
            source_type="https",
            url="https://example.com/doctrine-rnd.tar.gz",
            subdir="pack",
        )

        def _nested_pack_layout(target_dir: Path) -> None:
            _populate_valid_pack(target_dir / "pack")

        source = _ScriptedSource(
            layout=_nested_pack_layout,
            result=FetchResult(ok=True, artifacts_written=2, pack_version="v9"),
        )
        monkeypatch.setattr("specify_cli.doctrine.snapshot._build_source", lambda _pack: source)

        result = fetch_pack(pack, tmp_path)

        assert result.ok is True
        assert result.artifacts_written == 2
        assert (tmp_path / "doctrine-rnd" / "pack" / "directives" / "sec-001.directive.yaml").is_file()


class TestEtagConditionalFetch:
    @pytest.mark.parametrize(
        "invalid_url",
        [
            "https://[bad/artifactory/repo/pack.tar.gz",
            "https://example.com:not-a-port/artifactory/repo/pack.tar.gz",
            "http://example.com/artifactory/repo/pack.tar.gz",
            "https:///artifactory/repo/pack.tar.gz",
            "https://exa mple.com/artifactory/repo/pack.tar.gz",
            "https://%ZZ/artifactory/repo/pack.tar.gz",
            "https://./artifactory/repo/pack.tar.gz",
            "https://💩.example/artifactory/repo/pack.tar.gz",
            "https://a\u200db.example/artifactory/repo/pack.tar.gz",
            "https://\u0301bad.example/artifactory/repo/pack.tar.gz",
            f"https://{'.'.join(['é' * 20] * 10)}/artifactory/repo/pack.tar.gz",
            "https://[v1.fe]/artifactory/repo/pack.tar.gz",
            "https://download.example\\@metadata.example/artifactory/repo/pack.tar.gz",
            "https://download.example\t@metadata.example/artifactory/repo/pack.tar.gz",
            "https://download.example\n@metadata.example/artifactory/repo/pack.tar.gz",
        ],
    )
    def test_invalid_authority_preserves_existing_snapshot_without_request(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        invalid_url: str,
    ) -> None:
        from specify_cli.doctrine.sources.https_source import HttpsBundleSource

        local_path = tmp_path / "doctrine"
        _populate_valid_pack(local_path)
        marker = local_path / "last-good"
        marker.write_text("preserve\n")
        write_pack_manifest(
            local_path,
            FetchResult(
                ok=True,
                artifacts_written=2,
                pack_version="v1",
                etag='"v1"',
            ),
            source_url="https://example.com/pack.tar.gz",
            source_type="https",
        )
        calls: list[str] = []

        def _unexpected_get(url: str, **kwargs: object) -> object:
            calls.append(url)
            raise AssertionError("invalid source reached requests.get")

        monkeypatch.setattr(
            "specify_cli.doctrine.sources.https_source.requests.get",
            _unexpected_get,
        )
        monkeypatch.setattr(
            "specify_cli.doctrine.sources.https_source.requests.post",
            _unexpected_get,
        )

        result = write_snapshot(
            HttpsBundleSource(url=invalid_url),
            local_path,
            source_url=invalid_url,
            source_type="https",
        )

        assert result.ok is False
        assert any("URL is invalid" in error for error in result.errors)
        assert marker.read_text() == "preserve\n"
        assert calls == []

    @pytest.mark.parametrize(
        ("raw_url", "canonical_url"),
        [
            (
                "https://bücher.example/pack.tar.gz",
                "https://xn--bcher-kva.example/pack.tar.gz",
            ),
            (
                "https://example.com/a/%2e%2e/pack.tar.gz",
                "https://example.com/pack.tar.gz",
            ),
        ],
    )
    def test_snapshot_persists_the_canonical_request_identity(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        raw_url: str,
        canonical_url: str,
    ) -> None:
        from specify_cli.doctrine.sources.https_source import HttpsBundleSource

        seen_urls: list[str] = []

        def _fake_fetch(source: HttpsBundleSource, target_dir: Path) -> FetchResult:
            seen_urls.append(source.url)
            _populate_valid_pack(target_dir)
            return FetchResult(ok=True, artifacts_written=2, pack_version="v1")

        monkeypatch.setattr(HttpsBundleSource, "fetch", _fake_fetch)
        local_path = tmp_path / "doctrine"

        result = write_snapshot(
            HttpsBundleSource(url=raw_url),
            local_path,
            source_type="https",
        )

        manifest = yaml.safe_load((local_path / "pack-manifest.yaml").read_text())
        assert result.ok is True
        assert seen_urls == [canonical_url]
        assert manifest["source_url"] == canonical_url

    def test_query_bearing_source_never_reuses_persisted_etag(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from specify_cli.doctrine.sources.https_source import HttpsBundleSource

        local_path = tmp_path / "doctrine"
        _populate_valid_pack(local_path)
        source_a = "https://example.com/pack.tar.gz?artifact=A&signature=one"
        source_b = "https://example.com/pack.tar.gz?artifact=B&signature=two"
        write_pack_manifest(
            local_path,
            FetchResult(
                ok=True,
                artifacts_written=2,
                pack_version="A",
                etag='"etag-A"',
            ),
            source_url=source_a,
            source_type="https",
        )
        validators: list[str | None] = []

        def _fetch(source: HttpsBundleSource, target: Path) -> FetchResult:
            validators.append(source.if_none_match)
            _populate_valid_pack(target)
            (target / "directives" / "sec-001.directive.yaml").write_text("id: B\n")
            return FetchResult(
                ok=True,
                artifacts_written=2,
                pack_version="B",
                etag='"etag-B"',
            )

        monkeypatch.setattr(HttpsBundleSource, "fetch", _fetch)

        result = write_snapshot(
            HttpsBundleSource(url=source_b),
            local_path,
            source_url=source_b,
            source_type="https",
        )

        assert result.ok is True
        assert validators == [None]
        assert (local_path / "directives" / "sec-001.directive.yaml").read_text() == "id: B\n"

    def test_locally_modified_snapshot_disables_conditional_fetch(self, tmp_path: Path) -> None:
        from specify_cli.doctrine.snapshot import _with_stored_etag
        from specify_cli.doctrine.sources.https_source import HttpsBundleSource

        local_path = tmp_path / "doctrine"
        _populate_valid_pack(local_path)
        source_url = "https://example.com/pack.tar.gz"
        write_pack_manifest(
            local_path,
            FetchResult(
                ok=True,
                artifacts_written=2,
                pack_version="v1",
                etag='"v1"',
            ),
            source_url=source_url,
            source_type="https",
        )
        (local_path / "directives" / "sec-001.directive.yaml").write_text("id: locally-mutated\n")

        prepared = _with_stored_etag(
            HttpsBundleSource(url=source_url),
            local_path,
            None,
            source_url=source_url,
            source_type="https",
        )

        assert isinstance(prepared, HttpsBundleSource)
        assert prepared.if_none_match is None

    def test_304_fails_when_local_snapshot_changed_after_preparation(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from specify_cli.doctrine.sources.https_source import HttpsBundleSource

        local_path = tmp_path / "doctrine"
        _populate_valid_pack(local_path)
        source_url = "https://example.com/pack.tar.gz"
        write_pack_manifest(
            local_path,
            FetchResult(
                ok=True,
                artifacts_written=2,
                pack_version="v1",
                etag='"v1"',
            ),
            source_url=source_url,
            source_type="https",
        )
        (local_path / "directives" / "sec-001.directive.yaml").write_text("id: changed-after-preparation\n")

        class _NotModified:
            status_code = 304
            headers: dict[str, str] = {}
            reason = "Not Modified"
            url = "https://example.com/pack.tar.gz"

            def close(self) -> None:
                return None

        monkeypatch.setattr(
            "specify_cli.doctrine.sources.https_source.requests.get",
            lambda _url, **_kwargs: _NotModified(),
        )

        result = write_snapshot(
            HttpsBundleSource(url=source_url, if_none_match='"v1"'),
            local_path,
            source_type="https",
        )

        assert result.ok is False
        assert any("integrity digest" in error for error in result.errors)

    def test_legacy_artifactory_manifest_forces_one_versioned_download(self, tmp_path: Path) -> None:
        from specify_cli.doctrine.snapshot import _with_stored_etag
        from specify_cli.doctrine.sources.https_source import HttpsBundleSource

        local_path = tmp_path / "doctrine"
        _populate_valid_pack(local_path)
        write_pack_manifest(
            local_path,
            FetchResult(
                ok=True,
                artifacts_written=2,
                pack_version="legacy-etag-without-dedicated-field",
                etag="legacy-etag-without-dedicated-field",
            ),
            source_url=("https://artifactory.example.com/artifactory/repo/doctrine-rnd-latest.tar.gz"),
            source_type="artifactory",
        )
        source = HttpsBundleSource(
            url=("https://artifactory.example.com/artifactory/repo/doctrine-rnd-latest.tar.gz"),
            source_type="artifactory",
        )

        prepared = _with_stored_etag(
            source,
            local_path,
            None,
            source_url=source.url,
            source_type="artifactory",
        )

        assert isinstance(prepared, HttpsBundleSource)
        assert prepared.if_none_match is None

    def test_write_snapshot_skips_replace_on_304(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from specify_cli.doctrine.sources.https_source import HttpsBundleSource

        local_path = tmp_path / "doctrine"
        _populate_valid_pack(local_path)
        write_pack_manifest(
            local_path,
            FetchResult(
                ok=True,
                artifacts_written=2,
                pack_version="v1",
                etag='"etag-1"',
            ),
            source_url="https://example.com/pack.tar.gz",
            source_type="https",
        )
        marker = local_path / "directives" / "sec-001.directive.yaml"
        original = marker.read_text()
        manifest_path = local_path / "pack-manifest.yaml"
        manifest = yaml.safe_load(manifest_path.read_text())
        manifest["fetched_at"] = "original-fetch-time"
        manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=True))
        original_manifest = manifest_path.read_bytes()

        def _fake_get(url: str, **kwargs: object) -> object:
            headers = kwargs.get("headers") or {}
            assert isinstance(headers, dict)
            assert headers.get("If-None-Match") == '"etag-1"'

            class _Resp:
                status_code = 304
                headers: dict[str, str] = {}
                reason = "Not Modified"
                url = "https://example.com/pack.tar.gz"

                def close(self) -> None:
                    return None

                def iter_content(self, chunk_size: int = 65536):  # noqa: ARG002
                    yield from ()

            return _Resp()

        monkeypatch.setattr("specify_cli.doctrine.sources.https_source.requests.get", _fake_get)

        result = write_snapshot(
            HttpsBundleSource(url="https://example.com/pack.tar.gz"),
            local_path,
            source_type="https",
        )

        assert result.ok is True
        assert result.unchanged is True
        assert result.artifacts_written == 2
        assert result.pack_version == "v1"
        assert marker.read_text() == original
        assert manifest_path.read_bytes() == original_manifest

    def test_manifest_persists_etag(self, tmp_path: Path) -> None:
        local_path = tmp_path / "doctrine"
        _populate_valid_pack(local_path)
        write_pack_manifest(
            local_path,
            FetchResult(
                ok=True,
                artifacts_written=2,
                pack_version="v1",
                etag='"abc"',
            ),
            source_url="https://example.com/pack.tar.gz",
            source_type="https",
        )
        manifest = yaml.safe_load((local_path / "pack-manifest.yaml").read_text())
        assert manifest["etag"] == '"abc"'
        assert manifest["pack_version"] == "v1"
        assert len(manifest["snapshot_sha256"]) == 64


class TestPackManifest:
    def test_fetched_manifest_round_trips_through_canonical_schema(self, tmp_path: Path) -> None:
        from specify_cli.doctrine.pack_manifest import (
            load_pack_manifest,
            resolve_counts,
        )

        local_path = tmp_path / "doctrine"
        _populate_valid_pack(local_path)
        write_pack_manifest(
            local_path,
            FetchResult(
                ok=True,
                artifacts_written=2,
                pack_version="release-42",
                etag='"etag-42"',
            ),
            source_url="https://example.com/pack.tar.gz",
            source_type="https",
        )

        loaded = load_pack_manifest(local_path / "pack-manifest.yaml")

        assert loaded.pack_version == "release-42"
        assert loaded.etag == '"etag-42"'
        assert loaded.source_type == "https"
        assert loaded.source_uses_query is False
        assert loaded.snapshot_sha256 is not None
        assert len(loaded.snapshot_sha256) == 64
        assert loaded.source_fingerprint is not None
        assert len(loaded.source_fingerprint) == 64
        assert loaded.artifact_counts == {
            "agent_profiles": 1,
            "directives": 1,
        }
        assert loaded.constituents is None
        assert resolve_counts(loaded.constituents, loaded.artifact_counts) == {
            "agent_profiles": 1,
            "directives": 1,
        }

    def test_manifest_contains_required_fields(self, tmp_path: Path) -> None:
        local_path = tmp_path / "doctrine"
        _populate_valid_pack(local_path)

        write_pack_manifest(
            local_path,
            FetchResult(ok=True, artifacts_written=2, pack_version="v1.2.0"),
            source_url="https://example.com/pack.tar.gz",
            source_type="https",
        )

        manifest = yaml.safe_load((local_path / "pack-manifest.yaml").read_text())
        assert manifest["pack_version"] == "v1.2.0"
        assert manifest["source_type"] == "https"
        assert manifest["source_url"] == "https://example.com/pack.tar.gz"
        assert manifest["artifact_counts"]["directives"] == 1
        assert manifest["artifact_counts"]["agent_profiles"] == 1
        # fetched_at is a Z-suffixed UTC timestamp.
        assert manifest["fetched_at"].endswith("Z")

    def test_manifest_strips_credentials(self, tmp_path: Path) -> None:
        local_path = tmp_path / "doctrine"
        _populate_valid_pack(local_path)

        write_pack_manifest(
            local_path,
            FetchResult(ok=True, artifacts_written=2, pack_version="v1"),
            source_url="https://oauth2:secret@example.com/pack.tar.gz",
            source_type="https",
        )

        manifest = yaml.safe_load((local_path / "pack-manifest.yaml").read_text())
        assert "secret" not in manifest["source_url"]
        assert manifest["source_url"] == "https://example.com/pack.tar.gz"

    def test_manifest_omits_signed_query_fragment_and_records_fingerprint(self, tmp_path: Path) -> None:
        local_path = tmp_path / "doctrine"
        _populate_valid_pack(local_path)

        write_pack_manifest(
            local_path,
            FetchResult(ok=True, artifacts_written=2, pack_version="v1"),
            source_url=("https://oauth2:secret@example.com/pack.tar.gz?X-JFrog-Art-Api=signed-secret#private-fragment"),
            source_type="https",
        )

        manifest = yaml.safe_load((local_path / "pack-manifest.yaml").read_text())
        assert manifest["source_url"] == "https://example.com/pack.tar.gz"
        assert "secret" not in str(manifest)
        assert len(manifest["source_fingerprint"]) == 64
        assert manifest["source_uses_query"] is True

    def test_manifest_counts_top_level_graph_fragments(self, tmp_path: Path) -> None:
        """FR-014 (mission #2680): top-level ``*.graph.yaml`` fragments count.

        The sharded built-in layout (WP05) ships DRG fragments as top-level
        ``*.graph.yaml`` files rather than under a ``drg/`` directory.
        ``_count_artifacts`` must fold them into the ``drg_fragments`` bucket so
        a sharded doctrine tree categorises identically to the ``drg/``-dir
        layout.
        """
        local_path = tmp_path / "doctrine"
        _populate_valid_pack(local_path)
        (local_path / "directives.graph.yaml").write_text("nodes: []\nedges: []\n")
        (local_path / "actions.graph.yaml").write_text("nodes: []\nedges: []\n")

        write_pack_manifest(
            local_path,
            FetchResult(ok=True, artifacts_written=4, pack_version="v1"),
            source_url="https://example.com/pack.tar.gz",
            source_type="https",
        )

        manifest = yaml.safe_load((local_path / "pack-manifest.yaml").read_text())
        assert manifest["artifact_counts"]["drg_fragments"] == 2
        # Unrelated dir buckets remain intact (no double-counting).
        assert manifest["artifact_counts"]["directives"] == 1
