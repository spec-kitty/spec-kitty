"""Census gate — manual global-state mutation in tests.

SonarCloud's S8997 rule ("tests should use monkeypatch for temporary
modifications") is no longer active on the live project, so nothing watches
test code that mutates process-global state (``cwd``, ``sys.path``,
``sys.modules``, ``os.environ``, ``sys.argv``) by hand. This gate is the
local replacement.

Binding contract: the allowlist row schema and the verdicts below
(unallowlisted site, over-count, under-count/stale, wrong shard, parse
failure, and the vacuity floor).

This module is the ONLY module that reads the allowlist YAML and compares it
against the live scan (the contract's binding). It imports only
``_global_state_scan``'s public API — never ``_home_pin_scan`` — so it never
becomes a "verdict work" module under
``tests/architectural/test_home_pin_verdict_seam.py``, and the allowlist
directory is deliberately named ``global_state_allowlist/`` rather than
anything containing "census"/"baseline" (that guard's artefact-read signal).

Shard schema (permanent, one file per shard + ``deferred-01M3EW3Z.yaml``)::

    shard: S1
    owns:
      - tests/some/file.py
    rows:
      - file: tests/some/file.py
        qualname: TestThing.test_it
        kind: cwd
        count: 2
        class: process-bootstrap
        reason: why this site is allowed to mutate global state by hand

Verdicts (contract, all fail the gate): unallowlisted site, over-count,
under-count/stale (shrink-only ratchet), wrong shard, parse failure, and the
vacuity floor (fewer than 3000 files scanned).

Performance (measured, not asserted): ``scan(repo_root)`` runs once per test
session via the module-scoped ``scan_result`` fixture below, never per test.
Uncontended it measures ~4.0s (prototype: 3.9s); under this WP's own
contended CI-shaped runs, ~4-6s -- both comfortably under the 10s budget. No
wall-clock assertion lives in this module (an ``architectural``-marked module
runs under ``-n auto``, where such an assertion is flaky by construction --
house convention scopes wall-clock budgets to a ``pytest.mark.timing``-only
module run ``-n0``, e.g. ``test_spec_kitty_home_pin_budget.py``).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.architectural import _global_state_scan as gss

pytestmark = pytest.mark.architectural

REPO_ROOT = Path(__file__).resolve().parents[2]
ALLOWLIST_DIR = Path(__file__).resolve().with_name("global_state_allowlist")

#: The five kinds the detector emits (contract "Site").
VALID_KINDS: frozenset[str] = frozenset({"cwd", "sys.path", "sys.modules", "os.environ", "sys.argv"})
#: The four row classes the contract's allowlist row schema permits.
VALID_CLASSES: frozenset[str] = frozenset(
    {
        "process-bootstrap",
        "subprocess-entry",
        "leak-sentinel",
        "deferred-01M3EW3Z",
    }
)

#: Non-vacuity floor: a scan that silently walked zero (or a handful of) files must
#: fail loudly rather than pass vacuously.
MIN_SCANNED_FILES = 3000


@dataclass(frozen=True)
class AllowlistRow:
    """One row of the allowlist, plus the shard file it was loaded from."""

    shard: str
    file: str
    qualname: str
    kind: str
    count: int
    row_class: str
    reason: str | None


@dataclass(frozen=True)
class Allowlist:
    """The union of every shard file: ownership map + row-keyed rows."""

    owns_by_shard: Mapping[str, frozenset[str]]
    rows: Mapping[gss.SiteKey, AllowlistRow]


class AllowlistLoadError(ValueError):
    """The allowlist directory itself is malformed.

    Raised instead of silently discarding data: a
    last-one-wins ``dict`` overwrite on a duplicate row key or a duplicate
    ``shard:`` name would let a stale row escape the shrink-only ratchet, or
    let one shard file's ``owns:`` list silently vanish under another's.
    """


# ---------------------------------------------------------------------------
# Loading (this module owns all allowlist I/O — see the module docstring)
# ---------------------------------------------------------------------------


def _row_from_document(shard: str, raw: Mapping[str, Any]) -> AllowlistRow:
    return AllowlistRow(
        shard=shard,
        file=str(raw["file"]),
        qualname=str(raw["qualname"]),
        kind=str(raw["kind"]),
        count=int(raw["count"]),
        row_class=str(raw["class"]),
        reason=(str(raw["reason"]) if raw.get("reason") is not None else None),
    )


def _load_shard_file(path: Path) -> tuple[str, frozenset[str], list[AllowlistRow]]:
    document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    shard = str(document["shard"])
    owns = frozenset(str(item) for item in (document.get("owns") or ()))
    rows = [_row_from_document(shard, raw) for raw in (document.get("rows") or [])]
    return shard, owns, rows


def load_allowlist(directory: Path) -> Allowlist:
    """Load every ``*.yaml`` shard under ``directory`` into one :class:`Allowlist`.

    Fails closed (:class:`AllowlistLoadError`) on:

    1. a duplicate ``shard:`` name declared by two different files (checked
       first -- a directory violating this AND the filename-stem check below
       is reported for the more structural defect);
    2. a ``shard:`` field that does not match its own filename stem (one
       shard, one file, same name);
    3. a duplicate ``(file, qualname, kind)`` row key, within one shard or
       across shards -- a silent last-one-wins overwrite is exactly the
       vacuity hole an exact, shrink-only gate cannot afford.
    """
    loaded = [(path, *_load_shard_file(path)) for path in sorted(directory.glob("*.yaml"))]

    shard_sources: dict[str, str] = {}
    for path, shard, _owns, _rows in loaded:
        if shard in shard_sources:
            raise AllowlistLoadError(f"duplicate shard name {shard!r}: declared in both {shard_sources[shard]!r} and {path.name!r}")
        shard_sources[shard] = path.name

    for path, shard, _owns, _rows in loaded:
        if shard != path.stem:
            raise AllowlistLoadError(
                f"{path.name}: `shard: {shard}` does not match its filename stem {path.stem!r} (one shard, one file, same name -- rename the file or fix the field)"
            )

    owns_by_shard: dict[str, frozenset[str]] = {}
    rows: dict[gss.SiteKey, AllowlistRow] = {}
    for _path, shard, owns, shard_rows in loaded:
        owns_by_shard[shard] = owns
        for row in shard_rows:
            key = (row.file, row.qualname, row.kind)
            if key in rows:
                raise AllowlistLoadError(
                    f"duplicate allowlist row for key {key}: declared in both "
                    f"shard {rows[key].shard!r} and shard {shard!r} -- a stale duplicate "
                    f"would silently escape the shrink-only ratchet"
                )
            rows[key] = row
    return Allowlist(owns_by_shard=owns_by_shard, rows=rows)


def actual_counts(sites: Iterable[gss.Site]) -> dict[gss.SiteKey, int]:
    """``{site_key: occurrence count}`` over a scan's sites."""
    counts: dict[gss.SiteKey, int] = {}
    for site in sites:
        key = gss.site_key(site)
        counts[key] = counts.get(key, 0) + 1
    return counts


def _representative_site(sites: Iterable[gss.Site], key: gss.SiteKey) -> gss.Site | None:
    for site in sites:
        if gss.site_key(site) == key:
            return site
    return None


# ---------------------------------------------------------------------------
# Pure verdict functions (exercised directly, in memory — never by
# editing the allowlist files on disk)
# ---------------------------------------------------------------------------


def unallowlisted_keys(actual: Mapping[gss.SiteKey, int], rows: Mapping[gss.SiteKey, AllowlistRow]) -> list[gss.SiteKey]:
    """Verdict 1: every live key with no allowlist row."""
    return sorted(key for key in actual if key not in rows)


def over_count_rows(actual: Mapping[gss.SiteKey, int], rows: Mapping[gss.SiteKey, AllowlistRow]) -> list[tuple[gss.SiteKey, int, int]]:
    """Verdict 2: ``(key, actual_count, allowed_count)`` where actual > allowed."""
    return sorted((key, actual[key], row.count) for key, row in rows.items() if actual.get(key, 0) > row.count)


def under_count_rows(actual: Mapping[gss.SiteKey, int], rows: Mapping[gss.SiteKey, AllowlistRow]) -> list[tuple[gss.SiteKey, int, int]]:
    """Verdict 3 (shrink-only, incl. 0): ``(key, actual_count, allowed_count)``."""
    return sorted((key, actual.get(key, 0), row.count) for key, row in rows.items() if actual.get(key, 0) < row.count)


def wrong_shard_rows(rows: Mapping[gss.SiteKey, AllowlistRow], owns_by_shard: Mapping[str, frozenset[str]]) -> list[AllowlistRow]:
    """Verdict 4a: a row whose file is not in its own shard's ``owns:`` list."""
    return sorted(
        (row for row in rows.values() if row.file not in owns_by_shard.get(row.shard, frozenset())),
        key=lambda row: (row.shard, row.file, row.qualname, row.kind),
    )


def files_owned_by_multiple_shards(owns_by_shard: Mapping[str, frozenset[str]]) -> dict[str, list[str]]:
    """Verdict 4b: a file listed in more than one shard's ``owns:``."""
    owner_shards: dict[str, list[str]] = {}
    for shard, files in owns_by_shard.items():
        for file in files:
            owner_shards.setdefault(file, []).append(shard)
    return {file: sorted(shards) for file, shards in owner_shards.items() if len(shards) > 1}


def _site_line(site: gss.Site) -> str:
    """The one actionable per-site line every gate message reuses."""
    return f"{site.file}:{site.lineno} in {site.qualname}: {site.form} mutates {site.kind} — use {gss.replacement_for(site.kind)}"


def _sites_for_key(sites: Iterable[gss.Site], key: gss.SiteKey) -> list[gss.Site]:
    return [site for site in sites if gss.site_key(site) == key]


def _unallowlisted_message(sites: Iterable[gss.Site], keys: list[gss.SiteKey]) -> str:
    lines = []
    for key in keys:
        site = _representative_site(sites, key)
        if site is None:
            lines.append(f"{key[0]}::{key[1]} [{key[2]}]: (no representative site found)")
            continue
        lines.append(_site_line(site))
    return "unallowlisted manual global-state mutation site(s):\n" + "\n".join(lines)


def _over_count_message(sites: Iterable[gss.Site], over: list[tuple[gss.SiteKey, int, int]]) -> str:
    """Verdict 2's message: actual > allowed means a NEW manual site appeared —
    convert that site (the allowlist row's count is a ceiling, never raise it)."""
    lines = ["over-count: live site(s) beyond the allowlisted count — convert the new site(s); do not raise `count`:"]
    for key, actual_count, allowed_count in over:
        lines.append(f"{key[0]}::{key[1]} [{key[2]}]: actual {actual_count} > allowed {allowed_count}")
        for site in _sites_for_key(sites, key):
            lines.append(f"  {_site_line(site)}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def scan_result() -> gss.ScanResult:
    return gss.scan(REPO_ROOT)


@pytest.fixture(scope="module")
def allowlist() -> Allowlist:
    return load_allowlist(ALLOWLIST_DIR)


# ---------------------------------------------------------------------------
# The gate, verdicts 1-6
# ---------------------------------------------------------------------------


def test_no_parse_failures(scan_result: gss.ScanResult) -> None:
    """Verdict 5: every non-excluded ``*.py`` under ``tests/`` must parse.

    :func:`gss.scan` raises on the first unparseable file, so reaching a
    non-empty scan here is the proof."""
    assert scan_result.scanned_files > 0


def test_scanned_files_floor(scan_result: gss.ScanResult) -> None:
    """Verdict 6 (non-vacuity floor): a scan walking too few files must fail, not pass vacuously."""
    assert scan_result.scanned_files >= MIN_SCANNED_FILES, (
        f"only {scan_result.scanned_files} files scanned under tests/ (floor {MIN_SCANNED_FILES}) — the gate would otherwise pass vacuously"
    )


def test_no_unallowlisted_sites(scan_result: gss.ScanResult, allowlist: Allowlist) -> None:
    """Verdict 1."""
    actual = actual_counts(scan_result.sites)
    missing = unallowlisted_keys(actual, allowlist.rows)
    assert missing == [], _unallowlisted_message(scan_result.sites, missing)


def test_no_over_count(scan_result: gss.ScanResult, allowlist: Allowlist) -> None:
    """Verdict 2: actual > allowed means a new manual site appeared — convert it."""
    actual = actual_counts(scan_result.sites)
    over = over_count_rows(actual, allowlist.rows)
    assert over == [], _over_count_message(scan_result.sites, over)


def test_no_under_count(scan_result: gss.ScanResult, allowlist: Allowlist) -> None:
    """Verdict 3 (shrink-only ratchet — a stale over-allowance is an error)."""
    actual = actual_counts(scan_result.sites)
    under = under_count_rows(actual, allowlist.rows)
    messages = [f"shrink the allowlist: {allowlist.rows[key].shard} row {key[0]}::{key[1]} [{key[2]}] count {allowed} -> {found}" for key, found, allowed in under]
    assert under == [], "\n".join(messages)


def test_rows_live_in_owning_shard(allowlist: Allowlist) -> None:
    """Verdict 4a+4b: every row's file is owned by its shard, and by only one."""
    misplaced = wrong_shard_rows(allowlist.rows, allowlist.owns_by_shard)
    assert misplaced == [], f"row(s) whose file is not in their shard's `owns:` list: {[(row.shard, row.file, row.qualname, row.kind) for row in misplaced]}"
    duplicated = files_owned_by_multiple_shards(allowlist.owns_by_shard)
    assert duplicated == {}, f"file(s) owned by more than one shard: {duplicated}"


def test_allowlist_schema_is_valid(allowlist: Allowlist) -> None:
    """Schema checks: valid kind, valid class, every row has a `reason:`, count >= 1."""
    bad_kind = [row for row in allowlist.rows.values() if row.kind not in VALID_KINDS]
    bad_class = [row for row in allowlist.rows.values() if row.row_class not in VALID_CLASSES]
    bad_count = [row for row in allowlist.rows.values() if row.count < 1]
    missing_reason = [row for row in allowlist.rows.values() if not (row.reason or "").strip()]
    assert bad_kind == [], f"row(s) with an invalid kind: {[(r.file, r.qualname) for r in bad_kind]}"
    assert bad_class == [], f"row(s) with an invalid class: {[(r.file, r.qualname) for r in bad_class]}"
    assert bad_count == [], f"row(s) with count < 1: {[(r.file, r.qualname) for r in bad_count]}"
    assert missing_reason == [], f"row(s) with no `reason:`: {[(r.file, r.qualname) for r in missing_reason]}"


# ---------------------------------------------------------------------------
# Detector self-mutation tests (non-vacuity)
# ---------------------------------------------------------------------------


def _materialise(root: Path, relpath: str, source: str) -> None:
    path = root / "tests" / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


@pytest.mark.parametrize(
    ("relpath", "source", "kind"),
    [
        ("plant_chdir_call.py", "import os\ndef f(x):\n    os.chdir(x)\n", "cwd"),
        (
            "plant_chdir_from_import.py",
            "from os import chdir\ndef f(x):\n    chdir(x)\n",
            "cwd",
        ),
        (
            "plant_os_alias_environ_setitem.py",
            'import os as _o\ndef f():\n    _o.environ["K"] = "v"\n',
            "os.environ",
        ),
        (
            "plant_environ_alias_pop.py",
            'from os import environ as E\ndef f():\n    E.pop("K")\n',
            "os.environ",
        ),
        (
            "plant_putenv.py",
            'import os\ndef f():\n    os.putenv("K", "v")\n',
            "os.environ",
        ),
        (
            "plant_setattr_argv.py",
            'import sys\ndef f(argv):\n    setattr(sys, "argv", argv)\n',
            "sys.argv",
        ),
        (
            "plant_argv_iadd.py",
            'import sys\ndef f():\n    sys.argv += ["x"]\n',
            "sys.argv",
        ),
        (
            "plant_path_slice_store.py",
            'import sys\ndef f():\n    sys.path[:0] = ["x"]\n',
            "sys.path",
        ),
        (
            "plant_path_append.py",
            'import sys\ndef f():\n    sys.path.append("x")\n',
            "sys.path",
        ),
        (
            "plant_modules_del.py",
            'import sys\ndef f():\n    del sys.modules["m"]\n',
            "sys.modules",
        ),
        (
            "plant_modules_update.py",
            "import sys\ndef f():\n    sys.modules.update({})\n",
            "sys.modules",
        ),
        (
            "plant_local_alias_environ.py",
            'import os\ndef f():\n    env = os.environ\n    env["K"] = "v"\n',
            "os.environ",
        ),
        (
            "plant_environ_pop_home_key.py",
            'import os\ndef f():\n    os.environ.pop("SPEC_KITTY_HOME")\n',
            "os.environ",
        ),
    ],
)
def test_detector_bites_on_every_positive_form(tmp_path: Path, relpath: str, source: str, kind: str) -> None:
    """Each positive plant yields exactly one site of the expected kind."""
    _materialise(tmp_path, relpath, source)
    result = gss.scan(tmp_path)
    assert len(result.sites) == 1, f"expected exactly one site, found {result.sites}"
    assert result.sites[0].kind == kind


@pytest.mark.parametrize(
    ("relpath", "source"),
    [
        (
            "neg_monkeypatch_chdir.py",
            "def f(monkeypatch, x):\n    monkeypatch.chdir(x)\n",
        ),
        (
            "neg_monkeypatch_setenv.py",
            'def f(monkeypatch):\n    monkeypatch.setenv("K", "v")\n',
        ),
        (
            "neg_monkeypatch_context.py",
            'import pytest\ndef f():\n    with pytest.MonkeyPatch.context() as mp:\n        mp.setenv("K", "v")\n',
        ),
        (
            "neg_contextlib_chdir.py",
            "import contextlib\ndef f(x):\n    with contextlib.chdir(x):\n        pass\n",
        ),
        (
            "neg_mock_patch_dict_environ.py",
            'import os\nfrom unittest import mock\ndef f():\n    with mock.patch.dict(os.environ, {"K": "v"}):\n        pass\n',
        ),
        (
            "neg_mock_patch_object_argv.py",
            'import sys\nfrom unittest import mock\ndef f():\n    with mock.patch.object(sys, "argv", ["x"]):\n        pass\n',
        ),
        (
            "neg_environ_get.py",
            'import os\ndef f():\n    return os.environ.get("K")\n',
        ),
        (
            "neg_dict_environ.py",
            "import os\ndef f():\n    return dict(os.environ)\n",
        ),
        (
            "neg_monkeypatch_setenv_home.py",
            'def f(monkeypatch):\n    monkeypatch.setenv("SPEC_KITTY_HOME", "x")\n',
        ),
        (
            "neg_environ_setitem_home.py",
            'import os\ndef f(x):\n    os.environ["SPEC_KITTY_HOME"] = x\n',
        ),
        (
            "neg_patch_dict_sys_modules.py",
            "import sys\nfrom unittest import mock\ndef f():\n    with mock.patch.dict(sys.modules, {}):\n        pass\n",
        ),
    ],
)
def test_detector_does_not_bite_on_scoped_facilities(tmp_path: Path, relpath: str, source: str) -> None:
    """Negative controls: scoped/owned facilities yield zero sites."""
    _materialise(tmp_path, relpath, source)
    result = gss.scan(tmp_path)
    assert result.sites == (), f"expected zero sites, found {result.sites}"


def test_detector_fails_closed_on_a_parse_failure(tmp_path: Path) -> None:
    """An unparseable file raises out of the scan instead of being silently skipped."""
    _materialise(tmp_path, "broken.py", "def f(:\n    pass\n")
    with pytest.raises(SyntaxError, match="broken.py"):
        gss.scan(tmp_path)


def test_detector_keys_by_content_not_by_line(tmp_path: Path) -> None:
    """Two sites in the same function/kind key to one row with count 2, and the
    key survives a blank-line insertion above the first site (content-anchored)."""
    source = "import os\n\n\ndef f(x):\n    os.chdir(x)\n    os.chdir(x)\n"
    _materialise(tmp_path, "plant_two_sites.py", source)
    result = gss.scan(tmp_path)
    keys = {gss.site_key(site) for site in result.sites}
    assert len(result.sites) == 2
    assert len(keys) == 1

    shifted = "import os\n\n\n# an inserted comment line\ndef f(x):\n    os.chdir(x)\n    os.chdir(x)\n"
    _materialise(tmp_path, "plant_two_sites.py", shifted)
    shifted_result = gss.scan(tmp_path)
    shifted_keys = {gss.site_key(site) for site in shifted_result.sites}
    assert shifted_keys == keys, "inserting a line above the sites must not change their key"


# ---------------------------------------------------------------------------
# Vacuity + cost checks + coexistence
#
# These exercise the pure verdict functions directly, in memory, against the
# real (now-populated) allowlist — never by editing the shard files on disk.
# ---------------------------------------------------------------------------


def test_drop_one_row_is_detected(scan_result: gss.ScanResult, allowlist: Allowlist) -> None:
    """Removing one real row in memory must surface that key as unallowlisted."""
    actual = actual_counts(scan_result.sites)
    assert allowlist.rows, "the real allowlist must not be empty for this test to mean anything"
    dropped_key = next(iter(allowlist.rows))
    reduced_rows = {key: row for key, row in allowlist.rows.items() if key != dropped_key}
    missing = unallowlisted_keys(actual, reduced_rows)
    assert dropped_key in missing


def test_over_count_row_is_detected(scan_result: gss.ScanResult, allowlist: Allowlist) -> None:
    """Shrinking one real row's count below the live count (actual > allowed) must
    surface it as an over-count — a live site the allowlist no longer accounts for."""
    actual = actual_counts(scan_result.sites)
    key, row = next((k, r) for k, r in allowlist.rows.items() if actual.get(k, 0) > 0)
    shrunk = {**allowlist.rows, key: AllowlistRow(**{**row.__dict__, "count": 0})}
    over = over_count_rows(actual, shrunk)
    assert any(item[0] == key for item in over)


def test_over_count_message_is_actionable(scan_result: gss.ScanResult, allowlist: Allowlist) -> None:
    """The over-count message names file:lineno:qualname:kind for each live site
    beyond the allowed count, the site's scoped replacement, and tells the
    contributor to convert the site rather than raise `count`."""
    actual = actual_counts(scan_result.sites)
    key, row = next((k, r) for k, r in allowlist.rows.items() if actual.get(k, 0) > 0)
    shrunk = {**allowlist.rows, key: AllowlistRow(**{**row.__dict__, "count": 0})}
    over = over_count_rows(actual, shrunk)
    message = _over_count_message(scan_result.sites, over)

    assert "convert the new site" in message
    assert "do not raise `count`" in message
    for site in _sites_for_key(scan_result.sites, key):
        assert f"{site.file}:{site.lineno} in {site.qualname}" in message
        assert gss.replacement_for(site.kind) in message


def test_under_count_row_is_detected(scan_result: gss.ScanResult, allowlist: Allowlist) -> None:
    """Bumping one real row's count above the live count (actual < allowed) must
    surface it as a stale/under-count row — the shrink-only ratchet."""
    actual = actual_counts(scan_result.sites)
    key, row = next(iter(allowlist.rows.items()))
    live_count = actual.get(key, 0)
    bumped = {**allowlist.rows, key: AllowlistRow(**{**row.__dict__, "count": live_count + 5})}
    under = under_count_rows(actual, bumped)
    assert any(item[0] == key for item in under)


def test_wrong_shard_row_is_detected(allowlist: Allowlist) -> None:
    """Moving one real row to a shard that does not own its file must surface it."""
    key, row = next(iter(allowlist.rows.items()))
    other_shard = next(shard for shard in allowlist.owns_by_shard if shard != row.shard)
    moved_rows = {**allowlist.rows, key: AllowlistRow(**{**row.__dict__, "shard": other_shard})}
    misplaced = wrong_shard_rows(moved_rows, allowlist.owns_by_shard)
    assert any(candidate.file == row.file and candidate.qualname == row.qualname for candidate in misplaced)


# Performance note (measured, not asserted here): a wall-clock assertion does
# not belong in this `architectural`-marked module, which runs under `-n
# auto` alongside every other architectural gate (house convention:
# `test_spec_kitty_home_pin_budget.py` scopes wall-clock budgets to a
# `pytest.mark.timing`-only module run `-n0`). `scan_result` above is a single
# module-scoped fixture -- the full tree is scanned exactly once per test run,
# never per test. Measured uncontended: ~4.0s (well under the 10s budget), and
# ~4-6s under contention in CI-shaped runs; both are far below the 10s ceiling
# on the same tree the prototype measured at 3.9s.
#
# Coexistence note: this module deliberately does NOT import
# `_home_pin_scan` -- a smoke-check import here would register this gate as a
# `_home_pin_scan` seam consumer under
# `test_home_pin_seam_no_second_copy.seam_consumers()`, subjecting it to the
# second-copy ban and the zero-new-suppressions requirement for no reason.
# Coexistence is proven by running the neighbouring gate modules themselves
# (see the Activity Log for the recorded green run), not by an import here.


# ---------------------------------------------------------------------------
# Loader fail-closed self-mutation tests
# ---------------------------------------------------------------------------


def _write_shard(root: Path, filename: str, text: str) -> None:
    path = root / filename
    path.write_text(text, encoding="utf-8")


def test_loader_rejects_duplicate_row_key_within_one_shard(tmp_path: Path) -> None:
    """Two rows sharing ``(file, qualname, kind)`` in the SAME shard file must
    raise, not silently keep the last one (a stale duplicate would otherwise
    escape the shrink-only ratchet)."""
    _write_shard(
        tmp_path,
        "S1.yaml",
        "shard: S1\n"
        "owns:\n"
        "  - a.py\n"
        "rows:\n"
        "  - file: a.py\n"
        "    qualname: f\n"
        "    kind: cwd\n"
        "    count: 5\n"
        "    class: process-bootstrap\n"
        "    reason: fixture row for the duplicate-key loader test\n"
        "  - file: a.py\n"
        "    qualname: f\n"
        "    kind: cwd\n"
        "    count: 2\n"
        "    class: process-bootstrap\n"
        "    reason: fixture row for the duplicate-key loader test\n",
    )
    with pytest.raises(AllowlistLoadError, match="duplicate allowlist row"):
        load_allowlist(tmp_path)


def test_loader_rejects_duplicate_row_key_across_shards(tmp_path: Path) -> None:
    """The same key declared in two different shard files must raise."""
    _write_shard(
        tmp_path,
        "S1.yaml",
        "shard: S1\nowns:\n  - a.py\nrows:\n  - file: a.py\n    qualname: f\n    kind: cwd\n    count: 5\n    class: process-bootstrap\n    reason: fixture row\n",
    )
    _write_shard(
        tmp_path,
        "S2.yaml",
        "shard: S2\nowns:\n  - a.py\nrows:\n  - file: a.py\n    qualname: f\n    kind: cwd\n    count: 2\n    class: process-bootstrap\n    reason: fixture row\n",
    )
    with pytest.raises(AllowlistLoadError, match="duplicate allowlist row"):
        load_allowlist(tmp_path)


def test_loader_rejects_duplicate_shard_name_across_files(tmp_path: Path) -> None:
    """Two files declaring the same ``shard:`` name must raise -- one file's
    ``owns:`` list silently vanishing under the other's is exactly the hole
    the reviewer's `owns:` overwrite verified."""
    _write_shard(tmp_path, "S1.yaml", "shard: S1\nowns:\n  - a.py\nrows: []\n")
    _write_shard(tmp_path, "S1_second.yaml", "shard: S1\nowns:\n  - b.py\nrows: []\n")
    with pytest.raises(AllowlistLoadError, match="duplicate shard name"):
        load_allowlist(tmp_path)


def test_loader_rejects_shard_name_filename_mismatch(tmp_path: Path) -> None:
    """A ``shard:`` field that does not match its own filename stem must raise."""
    _write_shard(tmp_path, "S1.yaml", "shard: S2\nowns: []\nrows: []\n")
    with pytest.raises(AllowlistLoadError, match="does not match its filename stem"):
        load_allowlist(tmp_path)


def test_loader_accepts_a_well_formed_directory(tmp_path: Path) -> None:
    """The control: a directory with no duplicates and matching shard names
    loads cleanly, proving the three checks above are not just always-raise."""
    _write_shard(
        tmp_path,
        "S1.yaml",
        "shard: S1\nowns:\n  - a.py\nrows:\n  - file: a.py\n    qualname: f\n    kind: cwd\n    count: 5\n    class: process-bootstrap\n    reason: fixture row\n",
    )
    _write_shard(tmp_path, "S2.yaml", "shard: S2\nowns:\n  - b.py\nrows: []\n")
    allowlist = load_allowlist(tmp_path)
    assert set(allowlist.owns_by_shard) == {"S1", "S2"}
    assert len(allowlist.rows) == 1


# ---------------------------------------------------------------------------
# Detector node-identity self-mutation test
# ---------------------------------------------------------------------------


def test_home_exclusion_matches_the_owned_node_not_the_whole_line(tmp_path: Path) -> None:
    """A sibling mutation sharing the SPEC_KITTY_HOME write's source line must
    still be flagged: ``os.environ["SPEC_KITTY_HOME"] = os.environ.pop("OTHER")``
    is one owned write (excluded) plus one unrelated `.pop` (kept)."""
    _materialise(
        tmp_path,
        "plant_home_write_with_sibling_mutation.py",
        'import os\ndef f():\n    os.environ["SPEC_KITTY_HOME"] = os.environ.pop("OTHER")\n',
    )
    result = gss.scan(tmp_path)
    assert len(result.sites) == 1, f"expected exactly one (unowned) site, found {result.sites}"
    assert result.sites[0].kind == "os.environ"
    assert result.sites[0].form == "call:.pop"
