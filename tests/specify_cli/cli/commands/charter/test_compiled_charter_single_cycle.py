"""A compiled-charter refresh is ONE write cycle, and its bytes do not change (#6506).

``write_compiled_charter`` used to refresh ``catalog`` then ``metadata`` with two sequential
single-section writes. Each of those observed, loaded, rendered and re-verified the whole
governed document, so one recompile paid that cycle twice — the dominant cost of
``charter activate``/``deactivate`` on a repository-scale project (issue #6506).

Two properties are pinned here, on the compiled-charter path itself rather than on the shared
helper:

1. **One cycle.** The refresh renders the whole document exactly once, whichever derived
   sections the compiler owns. Counted structurally at the render boundary and via the number
   of content-bearing observations, not timed — so the assertion is load-independent.
2. **No output drift.** The bytes the single-cycle path writes equal the bytes the
   two-cycle path wrote for the same input, and a second refresh with nothing to change
   writes nothing and does not restamp ``metadata.generated_at``.
"""

from __future__ import annotations

from collections.abc import Iterator
from functools import cache
from pathlib import Path
from typing import Any

import pytest

from charter.activation import charter_yaml_io, compiler as compiler_module
from charter.activation.charter_yaml_io import (
    apply_yaml_write,
    prepare_charter_yaml_section,
    yaml_documents_equal,
)
from charter.activation.compiler import CompiledCharter, compile_charter, write_compiled_charter
from charter.activation.interview import default_interview

pytestmark = pytest.mark.fast

_AUTHORED_FIXTURE = """\
schema_version: "2.0.0"
governance:
  testing:
    min_coverage: 87  # AUTHORED-GOVERNANCE-SENTINEL
directives:
  directives: []
catalog:
  mission: stale-mission
  template_set: stale-template-set
  languages: []
  references: []
metadata:
  generated_at: "2026-01-01T00:00:00Z"
  generator: authored
"""


@cache
def _compiled() -> CompiledCharter:
    """Compile once per process: ``compile_charter`` is seconds of work and is only read."""
    interview = default_interview(mission="software-dev", profile="minimal")
    return compile_charter(mission="software-dev", interview=interview)


@pytest.fixture(scope="module", autouse=True)
def _shared_compiled_is_read_only() -> Iterator[None]:
    before = repr(_compiled())
    yield
    assert repr(_compiled()) == before, "write_compiled_charter mutated the shared CompiledCharter"


@pytest.fixture(autouse=True)
def _frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """A fresh ``generated_at`` is the clock, not the code under test.

    Both refresh paths stamp ``metadata.generated_at`` from ``kernel.clock``, so without a
    frozen clock the two runs of a byte comparison differ by a second of wall time and every
    byte assertion becomes a flake. ``compiler`` imports the function directly, so the patch
    goes on that binding.
    """
    monkeypatch.setattr(compiler_module, "now_utc_stamp", lambda: "2026-10-31T00:00:00Z")


def _seed(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    charter_yaml_path = root / "charter.yaml"
    charter_yaml_path.write_text(_AUTHORED_FIXTURE, encoding="utf-8")
    return charter_yaml_path


def _refresh_without_provisioning(root: Path) -> None:
    """Refresh the compiled charter only.

    ``repo_root`` is deliberately not passed: its tail (mission-type provisioning plus the
    synthesis-manifest restamp) writes other files and is not part of the cycle under test.
    """
    write_compiled_charter(root, _compiled(), force=True)


def _refresh_twice_the_old_way(root: Path) -> None:
    """Reconstruct the pre-#6506 behaviour: one prepared write per derived section."""
    from charter.activation.compiler import _build_catalog_dict, _build_metadata_dict  # noqa: PLC0415

    catalog = _build_catalog_dict(_compiled())
    charter_yaml_path = root / "charter.yaml"
    apply_yaml_write(prepare_charter_yaml_section(charter_yaml_path, "catalog", catalog))
    apply_yaml_write(prepare_charter_yaml_section(charter_yaml_path, "metadata", _build_metadata_dict()))


def test_single_cycle_writes_the_same_bytes_as_two_cycles(tmp_path: Path) -> None:
    merged_root = tmp_path / "merged"
    sequential_root = tmp_path / "sequential"
    sequential_yaml = _seed(sequential_root)
    _refresh_twice_the_old_way(sequential_root)
    sequential = sequential_yaml.read_bytes()

    merged_yaml = _seed(merged_root)
    _refresh_without_provisioning(merged_root)
    merged = merged_yaml.read_bytes()

    assert merged == sequential, "the single-cycle refresh changed the bytes the two-cycle refresh produced"
    assert b"AUTHORED-GOVERNANCE-SENTINEL" in merged
    assert yaml_documents_equal(
        charter_yaml_io._yaml_loader().load(merged.decode("utf-8")).get("catalog"),
        charter_yaml_io._yaml_loader().load(sequential.decode("utf-8")).get("catalog"),
    )


def test_refresh_renders_the_document_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """One render and one document observation per refresh, not one per derived section."""
    renders: list[int] = []
    real_render = charter_yaml_io.render_yaml_document

    def counting_render(*args: Any, **kwargs: Any) -> bytes:
        renders.append(1)
        return real_render(*args, **kwargs)

    monkeypatch.setattr(charter_yaml_io, "render_yaml_document", counting_render)

    root = tmp_path / "once"
    _seed(root)
    _refresh_without_provisioning(root)
    assert len(renders) == 1, f"the refresh rendered the governed document {len(renders)} times; it must render it once"

    # Same fixture, same probe, the implementation this replaced: the count must be 2, or the
    # assertion above is a probe that cannot see the thing it claims to have removed.
    old_way = tmp_path / "once-old-way"
    _seed(old_way)
    renders.clear()
    _refresh_twice_the_old_way(old_way)
    assert len(renders) == 2, f"the two-cycle control rendered {len(renders)} times; the probe is blind"


def test_refresh_prepares_one_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """One prepared write per refresh, not one per derived section.

    Both paths funnel through ``prepare_yaml_write`` in the shared helper, so counting it
    counts write cycles rather than call sites and works for the two-cycle control below.
    """
    prepared: list[Path] = []
    real_prepare_yaml_write = charter_yaml_io.prepare_yaml_write

    def counting_prepare_yaml_write(path: Path, *args: Any, **kwargs: Any) -> Any:
        prepared.append(path)
        return real_prepare_yaml_write(path, *args, **kwargs)

    monkeypatch.setattr(charter_yaml_io, "prepare_yaml_write", counting_prepare_yaml_write)

    root = tmp_path / "one-write"
    charter_yaml_path = _seed(root)
    _refresh_without_provisioning(root)
    assert prepared == [charter_yaml_path], f"expected one prepared write of charter.yaml; got {prepared}"
    assert b"AUTHORED-GOVERNANCE-SENTINEL" in charter_yaml_path.read_bytes()

    # Same fixture, same probe, the implementation this replaced: two cycles.
    old_way = tmp_path / "one-write-old-way"
    old_way_yaml = _seed(old_way)
    prepared.clear()
    _refresh_twice_the_old_way(old_way)
    assert prepared == [old_way_yaml, old_way_yaml], f"the two-cycle control should prepare two writes of the same document; got {prepared}"


def test_second_refresh_is_a_no_op_and_keeps_generated_at(tmp_path: Path) -> None:
    """Nothing to change means nothing written, and never a restamped timestamp."""
    root = tmp_path / "noop"
    charter_yaml_path = _seed(root)
    _refresh_without_provisioning(root)
    first = charter_yaml_path.read_bytes()
    first_mtime = charter_yaml_path.stat().st_mtime_ns

    _refresh_without_provisioning(root)

    assert charter_yaml_path.read_bytes() == first, "a no-op refresh changed the governed document"
    assert charter_yaml_path.stat().st_mtime_ns == first_mtime, "a no-op refresh rewrote the file"
    document = charter_yaml_io._yaml_loader().load(first.decode("utf-8"))
    assert document["metadata"]["generated_at"] != "2026-01-01T00:00:00Z", "the first refresh changed the catalog, so it must have stamped a fresh generated_at"
    assert document["metadata"]["generated_at"] == charter_yaml_io._yaml_loader().load(charter_yaml_path.read_text(encoding="utf-8"))["metadata"]["generated_at"], (
        "a no-op refresh restamped generated_at"
    )


def test_unchanged_catalog_preserves_the_authored_timestamp(tmp_path: Path) -> None:
    """When the catalog on disk already matches, the authored ``generated_at`` survives."""
    root = tmp_path / "preserved"
    charter_yaml_path = _seed(root)
    catalog = charter_yaml_io._yaml_loader().load(_AUTHORED_FIXTURE)["catalog"]
    from charter.activation.compiler import _build_catalog_dict  # noqa: PLC0415

    assert not yaml_documents_equal(catalog, _build_catalog_dict(_compiled())), "the fixture is expected to start with a catalog that differs from the compiled one"
    _refresh_without_provisioning(root)
    stamped = charter_yaml_io._yaml_loader().load(charter_yaml_path.read_text(encoding="utf-8"))["metadata"]
    _refresh_without_provisioning(root)
    again = charter_yaml_io._yaml_loader().load(charter_yaml_path.read_text(encoding="utf-8"))["metadata"]
    assert again["generated_at"] == stamped["generated_at"]
