"""One charter recompile parses the whole governed document at most twice (#6506).

``charter activate``/``deactivate`` on a repository-scale project spent most of its time in the
compiled-charter write path: two sequential single-section writes, each of which parsed and
re-emitted the whole 165 KB ``charter.yaml`` several times, and each of which paid two
whole-document equality checks that serialised both sides (measured: 18 whole-document round
trips per recompile, ~16.7 s for the command before the fix, ~10.4 s after it).

This test pins the *structure* that made that happen, not the wall clock:

* the number of whole-document round trips per recompile is at most
  :data:`MAX_WHOLE_DOCUMENT_ROUND_TRIPS` (six, against eighteen for the two-cycle shape it
  replaced);
* the probe is proved able to see a difference, by measuring the same two-cycle
  reconstruction the fix replaced on the same fixture.

A count is exact, deterministic and load-independent, which is why it — and not a timing
budget — is the measure that runs on every pull request. The repository-scale *timing*
measure lives in ``tests/performance/test_charter_write_repo_scale_timing.py`` and runs in the
nightly performance job, per ADR ``docs/adr/4.x/2026-10-05-2-runner-relative-performance-budgets.md``.

Why not drive the CLI: an in-process ``CliRunner`` invocation of ``charter activate`` also
rewrites the global slash-command asset cache, which is shared machine state and unrelated to
what is counted here — it made this measure flaky for reasons that have nothing to do with the
write path. ``recompile_catalog`` is the function the command itself invokes
(``activate`` → ``_recompile_catalog_best_effort`` → ``recompile_catalog``), so the production
path is still what is measured.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from charter.activation import charter_yaml_io
from charter.activation.charter_yaml_io import apply_yaml_write, prepare_charter_yaml_section
from specify_cli.cli.commands.charter.activate import recompile_catalog

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PROJECT_SOURCE = _REPO_ROOT / ".kittify"
_PACKS_SOURCE = _REPO_ROOT / "packs"

#: The whole-document round-trip budget for one recompile, measured on a project seeded from
#: this repository's own governed charter (165 KB, 264 catalog references).
#:
#: Six is what one merged write cycle needs: the read that decides the write, then the render's
#: own read, compose and scan of the document it must preserve, then the compose and read of the
#: text it produced before the final verification. It is a ratchet on today's structure, not a
#: theoretical floor: the first two of the six read identical bytes, so a future change can
#: lower this number and should.
#:
#: The two-cycle shape this replaced measures eighteen on the same fixture, so a re-introduced
#: per-section write is caught with a wide margin.
MAX_WHOLE_DOCUMENT_ROUND_TRIPS = 6


def _copy_project(target: Path) -> Path:
    """A scratch project carrying this repository's own governed charter, plus its packs."""
    if not (_PROJECT_SOURCE / "charter" / "charter.yaml").is_file():  # pragma: no cover - sdist install
        pytest.skip(f"no project charter under {_PROJECT_SOURCE}")
    shutil.copytree(_PROJECT_SOURCE, target / ".kittify")
    if _PACKS_SOURCE.is_dir():
        shutil.copytree(_PACKS_SOURCE, target / "packs")
    subprocess.run(["git", "init", "--quiet", str(target)], check=True, capture_output=True)
    return target


#: Enough leading characters to recognise the governed document by its own header, whatever
#: the writer has changed inside it.
_DOCUMENT_SENTINEL_CHARS = 64


class _CountingLoader:
    """A ``ruamel`` loader that counts whole-document round trips.

    Delegates everything to the real loader; only ``load``/``compose``/``scan`` are observed,
    because those are the three ways this module gets from text to a value or a node tree.

    A payload counts as the whole document when it *starts with the document's own header*.
    Matching on length would stop seeing the document the moment a write changed its size (which
    every write does), and the two-cycle control would then look like a single round trip.
    """

    def __init__(self, real: Any, counter: list[int], sentinel: bytes) -> None:
        self._counter = counter
        self._sentinel = sentinel
        self._real = real

    def _observe(self, payload: Any) -> None:
        head = payload[:_DOCUMENT_SENTINEL_CHARS] if isinstance(payload, (str, bytes)) else b""
        if isinstance(head, str):
            head = head.encode("utf-8")
        if head == self._sentinel:
            self._counter.append(len(payload))

    def load(self, stream: Any) -> Any:
        self._observe(stream)
        return self._real.load(stream)

    def compose(self, stream: Any) -> Any:
        self._observe(stream)
        return self._real.compose(stream)

    def scan(self, stream: Any) -> Any:
        self._observe(stream)
        return self._real.scan(stream)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._real, name)


def _sentinel(project: Path) -> bytes:
    """The document's own header, used to recognise a whole-document payload."""
    return (project / ".kittify" / "charter" / "charter.yaml").read_bytes()[:_DOCUMENT_SENTINEL_CHARS]


def _round_trips(project: Path, monkeypatch: pytest.MonkeyPatch) -> int:
    """Count whole-document round trips of ``charter.yaml`` during one real recompile."""
    counter: list[int] = []
    # Build the real loader BEFORE patching the factory, or the probe counts itself.
    real_loader = charter_yaml_io._yaml_loader()
    monkeypatch.setattr(charter_yaml_io, "_yaml_loader", lambda: _CountingLoader(real_loader, counter, _sentinel(project)))
    recompile_catalog(project)
    return len(counter)


def _two_cycle_reconstruction(project: Path) -> None:
    """The pre-#6506 write shape: one prepared write per derived section."""
    from charter.activation.compiler import _build_catalog_dict, _build_metadata_dict, compile_charter  # noqa: PLC0415
    from charter.activation.interview import default_interview  # noqa: PLC0415

    compiled = compile_charter(mission="software-dev", interview=default_interview(mission="software-dev", profile="minimal"))
    charter_yaml_path = project / ".kittify" / "charter" / "charter.yaml"
    apply_yaml_write(prepare_charter_yaml_section(charter_yaml_path, "catalog", _build_catalog_dict(compiled)))
    apply_yaml_write(prepare_charter_yaml_section(charter_yaml_path, "metadata", _build_metadata_dict()))


def test_one_recompile_stays_within_the_whole_document_budget(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = _copy_project(tmp_path / "project")
    trips = _round_trips(project, monkeypatch)
    assert 1 <= trips <= MAX_WHOLE_DOCUMENT_ROUND_TRIPS, (
        f"one compiled-charter refresh made {trips} whole-document round trips of charter.yaml; "
        f"the budget is at most {MAX_WHOLE_DOCUMENT_ROUND_TRIPS} (and at least 1, or the probe is blind)"
    )


def test_the_probe_can_see_the_writes_this_replace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Same fixture, same probe, the old two-cycle write shape: the count must be higher.

    Without this the budget assertion could be green because the probe cannot observe the
    round trips at all (tactic ``acceptance-criteria-non-vacuity``: pair every absence assertion
    with a same-fixture positive control).
    """
    project = _copy_project(tmp_path / "project")
    counter: list[int] = []
    real_loader = charter_yaml_io._yaml_loader()
    monkeypatch.setattr(charter_yaml_io, "_yaml_loader", lambda: _CountingLoader(real_loader, counter, _sentinel(project)))
    _two_cycle_reconstruction(project)
    assert len(counter) > MAX_WHOLE_DOCUMENT_ROUND_TRIPS, (
        f"the two-cycle control made {len(counter)} whole-document round trips, which the budget of "
        f"{MAX_WHOLE_DOCUMENT_ROUND_TRIPS} would not have caught; the probe is blind"
    )
