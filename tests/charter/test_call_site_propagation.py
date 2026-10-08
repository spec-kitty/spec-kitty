"""Regression tests for the silent-swallow finding (S1/S2) from the
post-merge mission review of ``review-merge-gate-hardening-3-2-x-01KRC57C``,
plus ATDD for Pattern C activation filtering in ``charter.activation.resolver.ActiveCharterService``
(WP09, T042).

The chokepoint at ``src/charter/activation/_io.py`` correctly raises ``CharterEncodingError``
(a subclass of ``KittyInternalConsistencyError``) when encoding detection
cannot resolve unambiguously. The audit surfaced that the two CALL SITES
inside the charter subsystem wrap the call in ``except Exception`` and return
empty results — defeating FR-018's fail-loud guarantee at the consumer
boundary.

These tests verify that the diagnostic propagates through the call sites:

* ``_load_yaml_asset`` (compiler.py) — used to compile charter assets
* ``read_interview_answers`` (interview.py) — used to load interview state

The tests target *behavior*, not file line numbers. A future refactor that
moves the function or changes its name should still pass these tests as
long as the diagnostic propagation contract is honored.

Pattern C ATDD (T042)
---------------------
``ActiveCharterService.agent_profiles`` applies a three-state activation filter:

* ``pack_context=None`` → unfiltered (all profiles returned)
* ``pack_context.activated_agent_profiles is None`` → unfiltered (key absent from config)
* ``pack_context.activated_agent_profiles == frozenset()`` → empty dict (explicit opt-out)
* ``pack_context.activated_agent_profiles = {ids}`` → only those IDs returned

These tests use lightweight ``types.SimpleNamespace`` objects as mock pack
contexts because ``PackContext``'s per-kind three-state fields are added by
WP02 (approved dependency) and may not yet be available in the merged tree.
The ``ActiveCharterService`` wrapper only requires duck-typing on the per-kind
fields, so ``SimpleNamespace`` is the simplest correct fixture.
"""

from __future__ import annotations

import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from charter.activation._io import CharterEncodingError
from kernel.errors import KittyInternalConsistencyError


pytestmark = [pytest.mark.unit]

def _write_ambiguous_yaml(path: Path) -> None:
    """Write bytes that the chokepoint cannot resolve confidently — the
    detector returns a ``best`` candidate whose ``chaos`` keeps the
    confidence below the 0.85 threshold, triggering CHARTER_ENCODING_AMBIGUOUS.

    The full high-bit range (0x80..0xFF) appended to a YAML-ish prefix gives
    charset-normalizer no coherent text in any candidate encoding, so the
    fail-loud branch fires under ``unsafe=False``.
    """
    high_bytes = bytes(range(0x80, 0x100))
    data = b"name: x\n" + high_bytes + b"\nvalue: 1\n"
    path.write_bytes(data)


def test_compiler_load_yaml_asset_propagates_encoding_error(tmp_path: Path) -> None:
    """``_load_yaml_asset`` must NOT swallow ``CharterEncodingError``.

    This is the S2 finding: ``compiler.py`` wraps the chokepoint call in
    ``except Exception`` and returns an empty dict, hiding the diagnostic.
    """
    from charter.activation.compiler import _load_yaml_asset

    bad = tmp_path / "bad.yaml"
    _write_ambiguous_yaml(bad)

    # Must propagate as KittyInternalConsistencyError (the canonical base);
    # CharterEncodingError IS-A KittyInternalConsistencyError, so this is
    # the tightest contract a future refactor must continue to satisfy.
    with pytest.raises(KittyInternalConsistencyError) as excinfo:
        _load_yaml_asset(bad)

    # Confirm we got the specific subclass and the diagnostic body.
    assert isinstance(excinfo.value, CharterEncodingError)
    assert excinfo.value.code == "CHARTER_ENCODING_AMBIGUOUS"
    assert excinfo.value.body  # non-empty operator guidance


def test_interview_read_propagates_encoding_error(tmp_path: Path) -> None:
    """``read_interview_answers`` must NOT swallow ``CharterEncodingError``.

    This is the S1 finding: ``interview.py`` wraps the chokepoint call in
    ``except Exception`` and returns ``None``, making "ambiguous encoding"
    look identical to "file missing".
    """
    from charter.activation.interview import read_interview_answers

    bad = tmp_path / "bad-interview.yaml"
    _write_ambiguous_yaml(bad)

    with pytest.raises(KittyInternalConsistencyError) as excinfo:
        read_interview_answers(bad)

    assert isinstance(excinfo.value, CharterEncodingError)
    assert excinfo.value.code == "CHARTER_ENCODING_AMBIGUOUS"


def test_compiler_load_yaml_asset_still_handles_unrelated_yaml_errors(
    tmp_path: Path,
) -> None:
    """Tighter exception handling must still tolerate non-encoding parse
    issues. The pre-existing behavior is to return an empty dict when YAML
    parsing fails on an otherwise readable file; that resilience stays.
    """
    from charter.activation.compiler import _load_yaml_asset

    # Valid UTF-8 but malformed YAML — encoding succeeds, parse fails.
    malformed = tmp_path / "malformed.yaml"
    malformed.write_text("name: [unclosed\n", encoding="utf-8")

    # Should NOT raise — pre-existing behavior is empty dict.
    result = _load_yaml_asset(malformed)
    assert isinstance(result, dict)
    # The function annotates _source_path even when content is empty.
    assert result.get("_source_path") == str(malformed)


def test_interview_read_returns_none_for_missing_file(tmp_path: Path) -> None:
    """Missing files remain a None-return — only encoding/consistency errors
    propagate."""
    from charter.activation.interview import read_interview_answers

    missing = tmp_path / "does-not-exist.yaml"
    assert read_interview_answers(missing) is None


def test_interview_read_returns_none_for_malformed_utf8_yaml(tmp_path: Path) -> None:
    """Malformed but decodable YAML preserves the legacy None-return contract."""
    from charter.activation.interview import read_interview_answers

    malformed = tmp_path / "malformed-interview.yaml"
    malformed.write_text("responses: [unclosed\n", encoding="utf-8")

    assert read_interview_answers(malformed) is None


def test_unsafe_bypass_propagates_through_compiler(tmp_path: Path) -> None:
    """When the operator opts into ``--unsafe`` semantics, the chokepoint
    does NOT raise — the compiler call site must support this propagation.

    This is the D3 finding: compiler.py:594 calls ``load_charter_file(path)``
    with no ``unsafe`` parameter, so even when an operator passes ``--unsafe``
    through the CLI, the bypass is silently ignored at this call site.
    """
    from charter.activation.compiler import _load_yaml_asset

    bad = tmp_path / "bad.yaml"
    _write_ambiguous_yaml(bad)

    # Pre-fix behavior: _load_yaml_asset accepts no `unsafe` kwarg →
    # passing one is a TypeError, and there is no way for the operator to
    # opt past CHARTER_ENCODING_AMBIGUOUS at this call site.
    # Post-fix behavior: _load_yaml_asset accepts `unsafe` and propagates it.
    result = _load_yaml_asset(bad, unsafe=True)
    assert isinstance(result, dict)
    # The bypass should have produced a non-empty parse (cp1252 decoded).
    # We can't assert exact content because the bytes happen to be invalid
    # YAML once decoded, but the empty-dict-from-encoding-failure path
    # is no longer hit.
    # What we DO assert: no KittyInternalConsistencyError was raised
    # (the pytest.raises wrapper above would have caught it).


# ---------------------------------------------------------------------------
# Pattern C ATDD — ActiveCharterService.agent_profiles activation filter (WP09 T042)
# ---------------------------------------------------------------------------
#
# These tests verify the three-state activation semantics for
# ``ActiveCharterService.agent_profiles``:
#
#   1. ``pack_context=None``                         → full unfiltered dict
#   2. ``pack_context.activated_agent_profiles=None``  → full unfiltered dict
#   3. ``pack_context.activated_agent_profiles=frozenset()`` → empty dict
#   4. ``pack_context.activated_agent_profiles={"alpha"}``   → single-entry dict
#
# A ``SimpleNamespace`` is used as a stand-in for a real ``PackContext``
# because the three-state per-kind fields are added by WP02 (approved
# dependency) and may not yet be present in the dataclass.  The wrapper in
# ``charter.activation.resolver.ActiveCharterService`` only duck-types the per-kind fields,
# so the namespace fixture is fully faithful.


def _make_mock_inner_with_profiles(
    profiles: dict[str, object],
) -> MagicMock:
    """Construct a mock inner doctrine service whose ``agent_profiles`` repo
    returns the supplied ``profiles`` dict when ``list_all()`` is called.
    """
    mock_inner = MagicMock()
    mock_profiles_repo = MagicMock()

    # Build mock profile objects with a ``profile_id`` attribute.
    mock_profile_objects = []
    for profile_id_val, profile_obj in profiles.items():
        if isinstance(profile_obj, MagicMock):
            profile_obj.profile_id = profile_id_val
            mock_profile_objects.append(profile_obj)
        else:
            mock_obj = MagicMock()
            mock_obj.profile_id = profile_id_val
            mock_profile_objects.append(mock_obj)

    mock_profiles_repo.list_all.return_value = mock_profile_objects
    mock_inner.agent_profiles = mock_profiles_repo
    return mock_inner


def test_doctrine_service_agent_profiles_no_pack_context_returns_all() -> None:
    """``pack_context=None`` → ``agent_profiles`` returns the full unfiltered dict.

    This is the backward-compat contract: callers that do not supply a
    ``PackContext`` receive every profile the inner service exposes.
    """
    from charter.activation.resolver import ActiveCharterService

    profiles = {"alpha": MagicMock(), "beta": MagicMock()}
    mock_inner = _make_mock_inner_with_profiles(profiles)

    wrapper = ActiveCharterService(mock_inner, pack_context=None)
    result = wrapper.agent_profiles

    assert set(result.keys()) == {"alpha", "beta"}


def test_doctrine_service_agent_profiles_none_field_returns_all() -> None:
    """``pack_context.activated_agent_profiles=None`` → full unfiltered dict.

    The ``None`` sentinel means "key absent from config.yaml" → all built-in
    profiles are available (three-state: absent = all built-ins).
    """
    from charter.activation.resolver import ActiveCharterService

    profiles = {"alpha": MagicMock(), "beta": MagicMock()}
    mock_inner = _make_mock_inner_with_profiles(profiles)

    pack_ctx = types.SimpleNamespace(
        activated_agent_profiles=None,
    )
    wrapper = ActiveCharterService(mock_inner, pack_context=pack_ctx)
    result = wrapper.agent_profiles

    assert set(result.keys()) == {"alpha", "beta"}


def test_doctrine_service_agent_profiles_empty_frozenset_returns_empty() -> None:
    """``pack_context.activated_agent_profiles=frozenset()`` → empty dict.

    The empty frozenset sentinel means "key present but empty list in
    config.yaml" → explicit opt-out; no profiles should be surfaced.
    This is the primary T042 ATDD assertion.
    """
    from charter.activation.resolver import ActiveCharterService

    profiles = {"alpha": MagicMock(), "beta": MagicMock()}
    mock_inner = _make_mock_inner_with_profiles(profiles)

    pack_ctx = types.SimpleNamespace(
        activated_agent_profiles=frozenset(),
    )
    wrapper = ActiveCharterService(mock_inner, pack_context=pack_ctx)
    result = wrapper.agent_profiles

    assert result == {}, (
        "activated_agent_profiles=frozenset() must return an empty dict "
        "(explicit opt-out), not the full profile set."
    )


def test_doctrine_service_agent_profiles_specific_ids_returns_subset() -> None:
    """``pack_context.activated_agent_profiles={ids}`` → only those IDs returned.

    Profiles whose ID is NOT in the activated set must be excluded.
    """
    from charter.activation.resolver import ActiveCharterService

    profiles = {"alpha": MagicMock(), "beta": MagicMock(), "gamma": MagicMock()}
    mock_inner = _make_mock_inner_with_profiles(profiles)

    pack_ctx = types.SimpleNamespace(
        activated_agent_profiles=frozenset({"alpha", "gamma"}),
    )
    wrapper = ActiveCharterService(mock_inner, pack_context=pack_ctx)
    result = wrapper.agent_profiles

    assert set(result.keys()) == {"alpha", "gamma"}, (
        "Only activated profile IDs should be returned."
    )
