"""Pack-root sanction files, consumer revocations and the effective-policy loader.

Covers :func:`load_pack_sanction`, the consumer ``revoked_pack_sanctions`` key,
:func:`load_effective_override_policy` (isolation, dedupe, bounded I/O, fail-closed
consumer), :func:`pack_roots_from_fragments`, :func:`legacy_template_entries` and
forward compatibility with the merge-base parser (NFR-002).
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from charter.offering.drg.org_pack_loader import OrgDRGFragment
from charter.offering.drg.override_policy import (
    LEGACY_TEMPLATE_RELPATH,
    PACK_POLICY_FILENAME,
    POLICY_RELPATH,
    EffectiveOverridePolicy,
    OverridePolicyError,
    ReplaceableBuiltin,
    ReplaceableBuiltinsPolicy,
    dump_pack_sanction,
    legacy_template_entries,
    load_effective_override_policy,
    load_pack_sanction,
    pack_roots_from_fragments,
    pack_sanction_present,
)

pytestmark = pytest.mark.fast

_VALID = "replaceable_builtins:\n  - urn: directive:risk\n    reason: We differ.\n"
_MERGE_BASE = "14d653bb"


def _write(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def _consumer(repo: Path, body: str) -> Path:
    return _write(repo / POLICY_RELPATH, body)


def _pack(root: Path, body: str | None) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    if body is not None:
        _write(root / PACK_POLICY_FILENAME, body)
    return root


def _symlink(link: Path, target: Path, *, is_dir: bool = False) -> None:
    try:
        link.symlink_to(target, target_is_directory=is_dir)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are unavailable on this platform")


# ---------------------------------------------------------------------------
# load_pack_sanction
# ---------------------------------------------------------------------------


def test_absent_pack_file_is_an_empty_policy(tmp_path: Path) -> None:
    policy = load_pack_sanction("acme", _pack(tmp_path / "acme", None))
    assert policy == ReplaceableBuiltinsPolicy(entries=())


def test_absent_pack_root_is_an_empty_policy(tmp_path: Path) -> None:
    assert load_pack_sanction("acme", tmp_path / "missing").entries == ()


def test_valid_pack_file_is_parsed(tmp_path: Path) -> None:
    policy = load_pack_sanction("acme", _pack(tmp_path / "acme", _VALID))
    assert policy.is_allowed("directive:risk")
    assert policy.reason_for("directive:risk") == "We differ."


def test_empty_pack_file_is_an_empty_policy(tmp_path: Path) -> None:
    assert load_pack_sanction("acme", _pack(tmp_path / "acme", "")).entries == ()


@pytest.mark.parametrize(
    "body",
    [
        "replaceable_builtins: not-a-list\n",
        "- bare-list\n",
        "replaceable_builtins:\n  - not-a-mapping\n",
        "replaceable_builtins:\n  - urn: ''\n",
        "replaceable_builtins:\n  - {urn: directive:x, reason: 7}\n",
        "key: [unclosed\n",
        "revoked_pack_sanctions:\n  - urn: directive:x\n",
    ],
)
def test_malformed_pack_file_names_pack_and_path(tmp_path: Path, body: str) -> None:
    root = _pack(tmp_path / "acme", body)
    with pytest.raises(OverridePolicyError) as exc_info:
        load_pack_sanction("acme", root)
    message = str(exc_info.value)
    assert "'acme'" in message
    assert str(root / PACK_POLICY_FILENAME) in message


def test_revocation_key_in_a_pack_file_is_rejected_as_consumer_only(tmp_path: Path) -> None:
    root = _pack(tmp_path / "acme", "revoked_pack_sanctions: []\n")
    with pytest.raises(OverridePolicyError, match="consumer"):
        load_pack_sanction("acme", root)


def test_unknown_top_level_keys_are_ignored(tmp_path: Path) -> None:
    root = _pack(tmp_path / "acme", _VALID + "future_key: 1\n")
    assert load_pack_sanction("acme", root).is_allowed("directive:risk")


def test_symlink_escaping_the_pack_root_is_an_error(tmp_path: Path) -> None:
    outside = _write(tmp_path / "outside.yaml", _VALID)
    root = tmp_path / "acme"
    root.mkdir()
    _symlink(root / PACK_POLICY_FILENAME, outside)
    with pytest.raises(OverridePolicyError, match="acme"):
        load_pack_sanction("acme", root)


def test_directory_in_place_of_the_file_is_an_error(tmp_path: Path) -> None:
    root = tmp_path / "acme"
    (root / PACK_POLICY_FILENAME).mkdir(parents=True)
    with pytest.raises(OverridePolicyError, match="regular file"):
        load_pack_sanction("acme", root)


def test_dangling_symlink_is_an_error_not_silent_absence(tmp_path: Path) -> None:
    root = tmp_path / "acme"
    root.mkdir()
    _symlink(root / PACK_POLICY_FILENAME, root / "nowhere.yaml")
    with pytest.raises(OverridePolicyError, match="regular file"):
        load_pack_sanction("acme", root)


def test_undecodable_pack_file_is_an_error(tmp_path: Path) -> None:
    root = tmp_path / "acme"
    root.mkdir()
    (root / PACK_POLICY_FILENAME).write_bytes(b"\xff\xfe\x00bad")
    with pytest.raises(OverridePolicyError, match="acme"):
        load_pack_sanction("acme", root)


# ---------------------------------------------------------------------------
# Consumer revocations (through the effective loader, the only public door)
# ---------------------------------------------------------------------------


def test_consumer_revocations_are_parsed(tmp_path: Path) -> None:
    _consumer(
        tmp_path,
        "revoked_pack_sanctions:\n  - urn: directive:risk\n    reason: we do not accept it\n  - pack: acme\n",
    )
    effective = load_effective_override_policy(tmp_path, {"acme": tmp_path / "acme"})
    assert effective.consumer_error is None
    assert effective.consumer.revoked_urns == frozenset({"directive:risk"})
    assert effective.consumer.revoked_packs == frozenset({"acme"})
    assert effective.revocation_errors == ()


@pytest.mark.parametrize(
    "body",
    [
        "revoked_pack_sanctions: nope\n",
        "revoked_pack_sanctions:\n  - not-a-mapping\n",
        "revoked_pack_sanctions:\n  - {}\n",
        "revoked_pack_sanctions:\n  - {urn: directive:x, pack: acme}\n",
        "revoked_pack_sanctions:\n  - {urn: ''}\n",
        "revoked_pack_sanctions:\n  - {pack: 3}\n",
        "revoked_pack_sanctions:\n  - {urn: directive:x, reason: 5}\n",
        "revoked_pack_sanctions:\n  - {urn: directive:x, surprise: 1}\n",
    ],
)
def test_invalid_revocations_are_a_consumer_error(tmp_path: Path, body: str) -> None:
    _consumer(tmp_path, body)
    effective = load_effective_override_policy(tmp_path, {})
    assert effective.consumer_error is not None
    assert "revoked_pack_sanctions" in effective.consumer_error


def test_null_revocations_and_null_reason_are_empty(tmp_path: Path) -> None:
    _consumer(tmp_path, "revoked_pack_sanctions:\n")
    assert load_effective_override_policy(tmp_path, {}).consumer.revoked_urns == frozenset()
    _consumer(tmp_path, "revoked_pack_sanctions:\n  - {urn: tactic:x, reason: ~}\n")
    assert load_effective_override_policy(tmp_path, {}).consumer.revoked_urns == frozenset({"tactic:x"})


def test_unknown_revoked_pack_is_a_revocation_error_case_sensitive(tmp_path: Path) -> None:
    _consumer(tmp_path, "revoked_pack_sanctions:\n  - pack: Acme\n")
    effective = load_effective_override_policy(tmp_path, {"acme": tmp_path / "acme"})
    assert len(effective.revocation_errors) == 1
    assert "Acme" in effective.revocation_errors[0]
    assert "revoked_pack_sanctions" in effective.revocation_errors[0]


# ---------------------------------------------------------------------------
# load_effective_override_policy
# ---------------------------------------------------------------------------


def test_effective_policy_without_files_is_empty_and_healthy(tmp_path: Path) -> None:
    effective = load_effective_override_policy(tmp_path, {})
    assert isinstance(effective, EffectiveOverridePolicy)
    assert effective.consumer.entries == ()
    assert dict(effective.packs) == {}
    assert effective.pack_errors == ()
    assert effective.consumer_error is None
    assert effective.revocation_errors == ()


def test_consumer_and_pack_files_are_both_loaded(tmp_path: Path) -> None:
    _consumer(tmp_path, "replaceable_builtins:\n  - urn: tactic:mine\n")
    root = _pack(tmp_path / "packs" / "acme", _VALID)
    effective = load_effective_override_policy(tmp_path, {"acme": root})
    assert effective.consumer.is_allowed("tactic:mine")
    assert effective.packs["acme"].is_allowed("directive:risk")


def test_one_bad_pack_does_not_void_the_good_one(tmp_path: Path) -> None:
    good = _pack(tmp_path / "good", _VALID)
    bad = _pack(tmp_path / "bad", "key: [unclosed\n")
    effective = load_effective_override_policy(tmp_path, {"bad": bad, "good": good})
    assert effective.packs["good"].is_allowed("directive:risk")
    assert "bad" not in effective.packs
    assert len(effective.pack_errors) == 1
    assert "'bad'" in effective.pack_errors[0]
    assert str(bad / PACK_POLICY_FILENAME) in effective.pack_errors[0]


def test_same_file_is_false_when_a_path_cannot_be_resolved(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from charter.offering.drg import override_policy

    def failing(path: Path) -> Path:
        raise OSError("boom")

    monkeypatch.setattr(override_policy, "resolve_rejecting_loops", failing)
    assert override_policy._same_file(tmp_path / "a", tmp_path / "a") is False


def test_same_file_is_false_for_a_symlink_loop(tmp_path: Path) -> None:
    from charter.offering.drg import override_policy

    loop_a, loop_b = tmp_path / "loop-a", tmp_path / "loop-b"
    try:
        loop_a.symlink_to(loop_b)
        loop_b.symlink_to(loop_a)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are not supported on this platform")
    assert override_policy._same_file(loop_a / "replaceable-builtins.yaml", tmp_path / "other.yaml") is False


def test_failed_pack_names_are_carried_for_attribution(tmp_path: Path) -> None:
    good = _pack(tmp_path / "good", _VALID)
    bad = _pack(tmp_path / "bad", "key: [unclosed\n")
    effective = load_effective_override_policy(tmp_path, {"bad": bad, "good": good})
    assert effective.pack_error_names == frozenset({"bad"})


def test_revocation_of_a_configured_but_unloaded_pack_is_not_unknown(tmp_path: Path) -> None:
    _consumer(tmp_path, "revoked_pack_sanctions:\n  - pack: ghost\n")
    default = load_effective_override_policy(tmp_path, {})
    assert len(default.revocation_errors) == 1 and "ghost" in default.revocation_errors[0]
    configured = load_effective_override_policy(tmp_path, {}, configured_pack_names=["ghost"])
    assert configured.revocation_errors == ()
    still_unknown = load_effective_override_policy(tmp_path, {}, configured_pack_names=["other"])
    assert len(still_unknown.revocation_errors) == 1


def test_malformed_consumer_is_recorded_empty_and_packs_still_load(tmp_path: Path) -> None:
    _consumer(tmp_path, "replaceable_builtins: not-a-list\n")
    root = _pack(tmp_path / "acme", _VALID)
    effective = load_effective_override_policy(tmp_path, {"acme": root})
    assert effective.consumer_error is not None
    assert str(POLICY_RELPATH) in effective.consumer_error
    assert effective.consumer.entries == ()
    assert effective.packs["acme"].is_allowed("directive:risk")


def test_pack_whose_sanction_path_is_the_consumer_file_counts_once(tmp_path: Path) -> None:
    # A pack rooted at the consumer's own ``.kittify/charter-packs`` dir: the file there
    # is the consumer allowlist, so its consumer-only key must not be a pack error.
    _consumer(
        tmp_path,
        _VALID + "revoked_pack_sanctions:\n  - urn: directive:other\n",
    )
    effective = load_effective_override_policy(tmp_path, {"self": tmp_path / POLICY_RELPATH.parent})
    assert effective.pack_errors == ()
    assert effective.consumer.is_allowed("directive:risk")
    assert effective.consumer.revoked_urns == frozenset({"directive:other"})
    assert effective.packs.get("self", ReplaceableBuiltinsPolicy(entries=())).entries == ()


def test_consumer_dedupe_survives_a_symlinked_kittify_dir(tmp_path: Path) -> None:
    real = tmp_path / "real_kittify"
    _write(real / "charter-packs" / PACK_POLICY_FILENAME, _VALID + "revoked_pack_sanctions: []\n")
    repo = tmp_path / "repo"
    repo.mkdir()
    _symlink(repo / ".kittify", real, is_dir=True)
    effective = load_effective_override_policy(repo, {"self": real / "charter-packs"})
    assert effective.pack_errors == ()
    assert effective.consumer.is_allowed("directive:risk")


def test_dump_then_load_round_trips_entries(tmp_path: Path) -> None:
    entries = (
        ReplaceableBuiltin(urn="directive:risk", reason="We differ."),
        ReplaceableBuiltin(urn="tactic:plain", reason=""),
    )
    root = _pack(tmp_path / "acme", dump_pack_sanction(entries))
    assert load_pack_sanction("acme", root).entries == entries


def test_dump_of_no_entries_is_an_empty_policy(tmp_path: Path) -> None:
    root = _pack(tmp_path / "acme", dump_pack_sanction(()))
    assert load_pack_sanction("acme", root).entries == ()


def test_pack_sanction_present_covers_file_absence_and_dangling_symlink(tmp_path: Path) -> None:
    assert pack_sanction_present(_pack(tmp_path / "none", None)) is False
    assert pack_sanction_present(_pack(tmp_path / "real", _VALID)) is True
    dangling = _pack(tmp_path / "dangling", None)
    _symlink(dangling / PACK_POLICY_FILENAME, tmp_path / "missing-target")
    assert pack_sanction_present(dangling) is True


def test_each_pack_file_is_read_exactly_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    roots = {name: _pack(tmp_path / name, _VALID) for name in ("a", "b", "c")}
    reads: list[Path] = []
    original = Path.read_text

    def counting(self: Path, *args: Any, **kwargs: Any) -> str:
        if self.name == PACK_POLICY_FILENAME:
            reads.append(self)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", counting)
    load_effective_override_policy(tmp_path, roots)
    assert sorted(reads) == sorted(root / PACK_POLICY_FILENAME for root in roots.values())


# ---------------------------------------------------------------------------
# pack_roots_from_fragments
# ---------------------------------------------------------------------------


def _fragment(name: str, source_ref: str) -> OrgDRGFragment:
    return OrgDRGFragment.model_validate(
        {
            "pack_name": name,
            "source_kind": "local_path",
            "source_ref": source_ref,
            "layer_index": 1,
            "provenance_marker": "org",
            "nodes": [],
            "edges": [],
        }
    )


def test_pack_roots_are_keyed_by_registry_name(tmp_path: Path) -> None:
    roots = pack_roots_from_fragments([_fragment("acme", str(tmp_path / "acme"))], tmp_path)
    assert roots == {"acme": tmp_path / "acme"}


def test_relative_source_ref_is_resolved_against_the_repo_root(tmp_path: Path) -> None:
    roots = pack_roots_from_fragments([_fragment("acme", "packs/acme")], tmp_path)
    assert roots == {"acme": tmp_path / "packs" / "acme"}


# ---------------------------------------------------------------------------
# legacy_template_entries -- tolerant, advisory probe
# ---------------------------------------------------------------------------


def _legacy(root: Path, body: str) -> Path:
    _write(root / LEGACY_TEMPLATE_RELPATH, body)
    return root


def test_legacy_probe_returns_reasons_for_requested_urns_only(tmp_path: Path) -> None:
    root = _legacy(
        tmp_path / "acme",
        "replaceable_builtins:\n  - {urn: directive:a, reason: why a}\n  - {urn: directive:b, reason: why b}\n",
    )
    assert legacy_template_entries(root, ["directive:a", "directive:zzz"]) == {"directive:a": "why a"}


@pytest.mark.parametrize("body", ["key: [unclosed\n", "- bare\n", "replaceable_builtins: 3\n"])
def test_legacy_probe_swallows_malformed_templates(tmp_path: Path, body: str) -> None:
    assert legacy_template_entries(_legacy(tmp_path / "acme", body), ["directive:a"]) == {}


def test_legacy_probe_absent_template_is_empty(tmp_path: Path) -> None:
    assert legacy_template_entries(tmp_path, ["directive:a"]) == {}


def test_legacy_probe_swallows_an_escaping_symlink(tmp_path: Path) -> None:
    outside = _write(tmp_path / "outside.yaml", "replaceable_builtins:\n  - urn: directive:a\n")
    root = tmp_path / "acme"
    (root / "templates" / "setup").mkdir(parents=True)
    _symlink(root / LEGACY_TEMPLATE_RELPATH, outside)
    assert legacy_template_entries(root, ["directive:a"]) == {}


# ---------------------------------------------------------------------------
# NFR-002: a CLI that predates this change tolerates both new surfaces
# ---------------------------------------------------------------------------


def _merge_base_module(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    repo = Path(__file__).resolve().parents[3]
    try:
        probe = subprocess.run(
            ["git", "cat-file", "-e", f"{_MERGE_BASE}^{{commit}}"],
            cwd=repo,
            capture_output=True,
            check=False,
        )
    except OSError:
        pytest.skip("git is not available to probe the merge-base commit")
    if probe.returncode != 0:
        pytest.skip(f"merge-base commit {_MERGE_BASE} is not available in this clone (shallow or pruned)")
    try:
        source = subprocess.run(
            ["git", "show", f"{_MERGE_BASE}:src/charter/offering/drg/override_policy.py"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        pytest.fail(f"merge-base commit {_MERGE_BASE} exists but its parser source could not be read: {exc}")
    target = tmp_path / "old_override_policy.py"
    target.write_text(source, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("old_override_policy", target)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "old_override_policy", module)
    spec.loader.exec_module(module)
    return module


def test_merge_base_parser_ignores_revocations_and_never_reads_pack_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    old = _merge_base_module(tmp_path, monkeypatch)
    repo = tmp_path / "repo"
    # Exercise the loaded merge-base parser with a fixture at the path *it* reads:
    # the data-path rename (.kittify/doctrine -> .kittify/charter-packs, #3732) means
    # the old parser's POLICY_RELPATH can differ from this module's current constant.
    _write(
        repo / old.POLICY_RELPATH,
        _VALID + "revoked_pack_sanctions:\n  - {pack: acme}\n  - {urn: directive:x}\n",
    )
    _pack(repo / "acme", "key: [unclosed\n")  # would error if anything read it
    seen: list[Path] = []
    original = Path.read_text

    def recording(self: Path, *args: Any, **kwargs: Any) -> str:
        seen.append(self)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", recording)
    policy = old.load_replaceable_builtins(repo)
    assert policy.is_allowed("directive:risk")
    assert seen == [repo / old.POLICY_RELPATH], "only the consumer file (full path) may be read, never the pack's same-named file"


def test_render_sanction_entries_is_keyed_pasteable_and_omits_blank_reason() -> None:
    import yaml

    from charter.offering.drg.override_policy import ReplaceableBuiltin, render_sanction_entries

    text = render_sanction_entries([ReplaceableBuiltin("directive:D1", "why: [x]"), ReplaceableBuiltin("tactic:t", "")])

    assert yaml.safe_load(text) == {"replaceable_builtins": [{"urn": "directive:D1", "reason": "why: [x]"}, {"urn": "tactic:t"}]}
