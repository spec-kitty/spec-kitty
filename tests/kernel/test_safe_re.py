"""Unit tests for kernel._safe_re — RE2-backed drop-in for stdlib re.

These tests verify:
- The ``re`` export is a module-like object (types.ModuleType)
- All stdlib re attributes are present (Pattern, Match, RegexFlag, error, flags)
- Core regex functions work correctly
- Fallback to stdlib re when RE2 is unavailable
- ``is_re2_active()`` returns bool
"""

from __future__ import annotations

import re as _stdlib_re
import types

import pytest

import kernel._safe_re as safe_re_mod
from kernel._safe_re import is_re2_active, re

pytestmark = pytest.mark.fast


class TestModuleType:
    """re export must be a proper module, not a plain object."""

    def test_re_is_module_type(self) -> None:
        assert isinstance(re, types.ModuleType)

    def test_re_has_pattern_attribute(self) -> None:
        assert re.Pattern is _stdlib_re.Pattern  # type: ignore[attr-defined]

    def test_re_has_match_attribute(self) -> None:
        assert re.Match is _stdlib_re.Match  # type: ignore[attr-defined]

    def test_re_has_regex_flag_attribute(self) -> None:
        assert re.RegexFlag is _stdlib_re.RegexFlag  # type: ignore[attr-defined]

    def test_re_has_error_attribute(self) -> None:
        assert re.error is _stdlib_re.error  # type: ignore[attr-defined]


class TestFlagConstants:
    """Flag constants are forwarded from stdlib re."""

    def test_ignorecase(self) -> None:
        assert re.IGNORECASE == _stdlib_re.IGNORECASE  # type: ignore[attr-defined]

    def test_i_alias(self) -> None:
        assert re.I == _stdlib_re.IGNORECASE  # type: ignore[attr-defined]

    def test_multiline(self) -> None:
        assert re.MULTILINE == _stdlib_re.MULTILINE  # type: ignore[attr-defined]

    def test_m_alias(self) -> None:
        assert re.M == _stdlib_re.MULTILINE  # type: ignore[attr-defined]

    def test_dotall(self) -> None:
        assert re.DOTALL == _stdlib_re.DOTALL  # type: ignore[attr-defined]

    def test_s_alias(self) -> None:
        assert re.S == _stdlib_re.DOTALL  # type: ignore[attr-defined]

    def test_verbose(self) -> None:
        assert re.VERBOSE == _stdlib_re.VERBOSE  # type: ignore[attr-defined]

    def test_x_alias(self) -> None:
        assert re.X == _stdlib_re.VERBOSE  # type: ignore[attr-defined]

    def test_ascii(self) -> None:
        assert re.ASCII == _stdlib_re.ASCII  # type: ignore[attr-defined]

    def test_unicode(self) -> None:
        assert re.UNICODE == _stdlib_re.UNICODE  # type: ignore[attr-defined]

    def test_noflag(self) -> None:
        assert re.NOFLAG == _stdlib_re.NOFLAG  # type: ignore[attr-defined]


class TestCompile:
    """re.compile returns a compiled pattern that works correctly."""

    def test_compile_returns_pattern_like_object(self) -> None:
        """Compiled result exposes the standard Pattern interface (search/match/etc).

        When RE2 is active the returned object is re2._Regexp, not re.Pattern.
        We verify the duck-type interface rather than the concrete type.
        """
        pat = re.compile(r"\d+")  # type: ignore[attr-defined]
        assert hasattr(pat, "search")
        assert hasattr(pat, "match")
        assert hasattr(pat, "findall")

    def test_compiled_pattern_matches(self) -> None:
        pat = re.compile(r"\d+")  # type: ignore[attr-defined]
        m = pat.search("abc 123 def")
        assert m is not None
        assert m.group() == "123"

    def test_compile_with_multiline_flag(self) -> None:
        pat = re.compile(r"^\w+", re.MULTILINE)  # type: ignore[attr-defined]
        matches = pat.findall("foo\nbar\nbaz")
        assert matches == ["foo", "bar", "baz"]

    def test_compile_with_ignorecase_flag(self) -> None:
        pat = re.compile(r"hello", re.IGNORECASE)  # type: ignore[attr-defined]
        assert pat.search("HELLO world") is not None

    def test_compile_with_dotall_flag(self) -> None:
        pat = re.compile(r"a.b", re.DOTALL)  # type: ignore[attr-defined]
        assert pat.search("a\nb") is not None

    def test_compile_inline_multiline(self) -> None:
        """Inline (?m) flag in the pattern string always works."""
        pat = re.compile(r"(?m)^\w+")  # type: ignore[attr-defined]
        matches = pat.findall("foo\nbar")
        assert matches == ["foo", "bar"]


class TestSearchAndMatch:
    """Module-level search/match/fullmatch functions."""

    def test_search_finds_match(self) -> None:
        m = re.search(r"\d+", "abc 42 xyz")  # type: ignore[attr-defined]
        assert m is not None
        assert m.group() == "42"

    def test_search_no_match_returns_none(self) -> None:
        assert re.search(r"\d+", "no digits here") is None  # type: ignore[attr-defined]

    def test_match_at_start(self) -> None:
        m = re.match(r"\w+", "hello world")  # type: ignore[attr-defined]
        assert m is not None
        assert m.group() == "hello"

    def test_match_not_at_start_returns_none(self) -> None:
        assert re.match(r"\d+", "abc123") is None  # type: ignore[attr-defined]

    def test_fullmatch(self) -> None:
        assert re.fullmatch(r"\d+", "123") is not None  # type: ignore[attr-defined]
        assert re.fullmatch(r"\d+", "123abc") is None  # type: ignore[attr-defined]


class TestFindall:
    """re.findall function."""

    def test_findall_returns_list(self) -> None:
        results = re.findall(r"\d+", "1 two 3 four 5")  # type: ignore[attr-defined]
        assert results == ["1", "3", "5"]

    def test_findall_empty_when_no_match(self) -> None:
        assert re.findall(r"\d+", "no digits") == []  # type: ignore[attr-defined]


class TestFinditer:
    """re.finditer function."""

    def test_finditer_returns_iterator(self) -> None:
        matches = list(re.finditer(r"\d+", "1 and 22 and 333"))  # type: ignore[attr-defined]
        assert [m.group() for m in matches] == ["1", "22", "333"]


class TestSub:
    """re.sub and re.subn functions."""

    def test_sub_replaces_pattern(self) -> None:
        result = re.sub(r"\d+", "NUM", "I have 2 cats and 3 dogs")  # type: ignore[attr-defined]
        assert result == "I have NUM cats and NUM dogs"

    def test_sub_with_count_limit(self) -> None:
        result = re.sub(r"\d+", "NUM", "1 2 3", count=2)  # type: ignore[attr-defined]
        assert result == "NUM NUM 3"

    def test_subn_returns_tuple(self) -> None:
        text, n = re.subn(r"\d+", "NUM", "1 and 2")  # type: ignore[attr-defined]
        assert text == "NUM and NUM"
        assert n == 2


class TestSplit:
    """re.split function."""

    def test_split_on_pattern(self) -> None:
        parts = re.split(r"\s+", "one  two   three")  # type: ignore[attr-defined]
        assert parts == ["one", "two", "three"]


class TestEscape:
    """re.escape function (always uses stdlib)."""

    def test_escape_special_chars(self) -> None:
        """re.escape delegates to stdlib re.escape."""
        result = re.escape("a.b")  # type: ignore[attr-defined]
        assert result == _stdlib_re.escape("a.b")


class TestPurge:
    """re.purge should tolerate RE2 bindings without a purge() helper."""

    def test_purge_ignores_missing_re2_purge(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[str] = []

        monkeypatch.setattr(safe_re_mod, "_re2_mod", object())
        monkeypatch.setattr(safe_re_mod._stdlib_re, "purge", lambda: calls.append("stdlib"))

        re.purge()  # type: ignore[attr-defined]

        assert calls == ["stdlib"]


class TestPCREPatternsFail:
    """PCRE-only patterns raise re.error — there is no silent fallback."""

    def test_positive_lookahead_raises(self) -> None:
        """Lookahead is not supported by RE2; raises re.error immediately."""
        with pytest.raises(_stdlib_re.error):
            re.search(r"\w+(?= world)", "hello world")  # type: ignore[attr-defined]

    def test_negative_lookahead_raises(self) -> None:
        with pytest.raises(_stdlib_re.error):
            re.search(r"\w+(?! world)", "hello there")  # type: ignore[attr-defined]

    def test_positive_lookbehind_raises(self) -> None:
        with pytest.raises(_stdlib_re.error):
            re.search(r"(?<=hello )\w+", "hello world")  # type: ignore[attr-defined]

    def test_verbose_flag_raises(self) -> None:
        """re.VERBOSE is not supported by RE2; raises re.error."""
        with pytest.raises(_stdlib_re.error):
            re.compile(r"\d+  # digits", re.VERBOSE)  # type: ignore[attr-defined]


class TestIsRe2Active:
    """is_re2_active() always returns True (google-re2 is a hard dependency)."""

    def test_returns_true(self) -> None:
        assert is_re2_active() is True


class TestInstanceofPattern:
    """isinstance checks with re.Pattern work correctly for RE2-compatible patterns."""

    def test_compiled_pattern_is_pattern_like(self) -> None:
        """RE2-compiled pattern exposes the Pattern duck-type interface."""
        pat = re.compile(r"\w+")  # type: ignore[attr-defined]
        assert hasattr(pat, "search")
        assert hasattr(pat, "match")
        assert hasattr(pat, "findall")


# ══════════════════════════════════════════════════════════════════════════════
# WP02 mutation-kill tests — kernel._safe_re survivors (2026-04-20)
#
# Target survivors (per mission mutant-slaying-core-packages-01KPNFQR, WP02):
#   - x__re2_compile__mutmut_{8,9,10,11,12,13} — error-message corruption
#   - x__fullmatch__mutmut_6, x__finditer__mutmut_6, x__findall__mutmut_6,
#     x__match__mutmut_6, x__split__mutmut_11, x__sub__mutmut_12,
#     x__subn__mutmut_12 — `_re2_compile(pattern, )` drops the flags
#     argument; killable by calling the module-level wrapper with a
#     non-default ``flags`` kwarg and asserting flag-sensitive behaviour.
#   - x__split__mutmut_6 — `.split(string, )` drops maxsplit; killable by
#     calling split() with a non-zero maxsplit value.
#   - x__subn__mutmut_8 — `.subn(repl, string, )` drops count; killable by
#     calling subn() with a non-zero count value.
#
# The ``*__mutmut_1`` / ``*__mutmut_2`` family (default-value substitutions
# on the mutant's own signature — ``flags: int = 0 → 1``, ``count: int = 0
# → 1``, etc.) are trampoline-equivalent under mutmut 3.x: the module-level
# wrapper function (``_compile``, ``_search``, ``_sub`` etc.) always fills
# its own defaults BEFORE invoking ``_mutmut_trampoline``, then passes every
# argument positionally — so the mutant's own default is never used. These
# are documented as residuals in docs/development/mutation-testing-findings.md.
# ══════════════════════════════════════════════════════════════════════════════


class TestRe2CompileMessageKills:
    """Kill x__re2_compile__mutmut_{8..13} — RE2-rejection error message corruption.

    The _re2_compile helper catches RE2's native compile exception and re-raises
    as ``re.error`` with a user-facing guidance message.  Mutations 8–13 corrupt
    that message in six different ways (blank-out, string-literal swap, case
    inversion). Each is killed by asserting the exact substrings are preserved
    in the raised error.

    Pattern applied: **Exact-message assertions** (replaces None-substitution and
    string-mutation survivors, per the mutation-aware-test-design styleguide
    'assert observable outcomes' principle).
    """

    def test_re2_rejected_error_has_non_none_message(self) -> None:
        """Kills x__re2_compile__mutmut_8: raise _stdlib_re.error(None).

        Asserts the raised re.error carries a readable string payload.
        """
        with pytest.raises(_stdlib_re.error) as exc_info:
            re.compile(r"(?=foo)")  # type: ignore[attr-defined]  # lookahead — PCRE-only
        # str() must succeed and return a non-empty non-"None" string.
        msg = str(exc_info.value)
        assert msg  # non-empty
        assert msg != "None"
        assert "None" not in msg.splitlines()[0]  # first line is not just "None"

    def test_re2_rejected_error_mentions_kernel_safe_re_prefix(self) -> None:
        """Kills x__re2_compile__mutmut_8 (error message blanked to None).

        The message template begins with 'kernel._safe_re: RE2 rejected pattern';
        a None-body mutation drops that prefix entirely.
        """
        with pytest.raises(_stdlib_re.error) as exc_info:
            re.compile(r"(?=foo)")  # type: ignore[attr-defined]
        assert "kernel._safe_re" in str(exc_info.value)
        assert "RE2 rejected pattern" in str(exc_info.value)

    def test_re2_rejected_error_preserves_if_this_pattern_clause(self) -> None:
        """Kills x__re2_compile__mutmut_9: replaces the 'If this pattern
        requires PCRE features (lookahead, lookbehind, ' clause with the
        sentinel 'XXIf this pattern requires PCRE features (lookahead,
        lookbehind, XX'.

        Also kills x__re2_compile__mutmut_10 (lowercase 'if this pattern')
        and x__re2_compile__mutmut_11 (uppercase 'IF THIS PATTERN ...').
        """
        with pytest.raises(_stdlib_re.error) as exc_info:
            re.compile(r"(?=foo)")  # type: ignore[attr-defined]
        msg = str(exc_info.value)
        # Exact-casing substring — fails for both lowercase and uppercase mutations.
        assert "If this pattern requires PCRE features" in msg
        # Reject the sentinel that mutmut 3 uses to mark string-literal mutations.
        assert "XX" not in msg

    def test_re2_rejected_error_preserves_back_references_clause(self) -> None:
        """Kills x__re2_compile__mutmut_12: replaces 'back-references), use
        stdlib re directly.' with the sentinel 'XXback-references)...XX'.

        Also kills x__re2_compile__mutmut_13 (uppercase 'BACK-REFERENCES),
        USE STDLIB RE DIRECTLY.').
        """
        with pytest.raises(_stdlib_re.error) as exc_info:
            re.compile(r"(?=foo)")  # type: ignore[attr-defined]
        msg = str(exc_info.value)
        assert "back-references)" in msg  # exact casing
        assert "use stdlib re directly" in msg  # exact casing
        assert "XX" not in msg

    def test_re2_rejected_error_includes_original_pattern_and_cause(self) -> None:
        """Belt-and-braces: the formatted message interpolates ``{pattern!r}``
        and ``{exc}``. Confirms these template slots still fire — any mutation
        that blanks the whole f-string (mutmut_8) also drops these.
        """
        with pytest.raises(_stdlib_re.error) as exc_info:
            re.compile(r"(?=foo)")  # type: ignore[attr-defined]
        msg = str(exc_info.value)
        assert "(?=foo)" in msg  # repr of the rejected pattern
        # __cause__ must be the original RE2 exception.
        assert exc_info.value.__cause__ is not None


class TestCompileAndRe2CompileTrampolineResiduals:
    """Residual survivors that cannot be killed without touching production code.

    These mutations change the mutant's own default argument value
    (``flags: int = 0 → 1``). Under mutmut 3.x's trampoline architecture, the
    wrapper function (``_compile``, ``_re2_compile``) always materialises the
    default value at its own level and forwards every argument positionally to
    the trampoline — so the mutant's own default is never observable.

    We still add a positive-observability test per function to document that
    the wrapper's own default is 0 (not 1) and that flagless compilation
    actually works.  This does not kill the trampoline-equivalent mutants,
    but guards against regressions in the wrapper itself.

    Tracked survivors: x__compile__mutmut_1, x__re2_compile__mutmut_1 —
    documented as residuals in docs/development/mutation-testing-findings.md
    (WP02 residuals section).
    """

    def test_compile_no_flags_behaves_as_flagless(self) -> None:
        """Wrapper default flags=0 — compiling 'Hello' with no flags must
        NOT match 'hello' in mixed case.  If the wrapper's default ever
        drifted to IGNORECASE=2, this would start matching.
        """
        pat = re.compile(r"Hello")  # type: ignore[attr-defined]
        assert pat.search("hello") is None  # case-sensitive without flag
        assert pat.search("Hello world") is not None

    def test_re2_compile_no_flags_behaves_as_flagless(self) -> None:
        """Same contract via the internal helper.  ``_re2_compile`` is
        imported directly because it is the hot path beneath every
        module-level re.* wrapper.
        """
        from kernel._safe_re import _re2_compile  # type: ignore[attr-defined]

        pat = _re2_compile(r"Hello")  # flags omitted → wrapper default 0
        assert pat.search("hello") is None
        assert pat.search("Hello there") is not None


class TestSearchMatchFamilyMutationKills:
    """Kill survivors in the module-level search/match/fullmatch/findall/finditer
    dispatchers.

    Scope:
      - x__search__mutmut_1, x__match__mutmut_1, x__fullmatch__mutmut_1,
        x__finditer__mutmut_1, x__findall__mutmut_1 — default-arg changes,
        trampoline-equivalent residuals (see
        TestCompileAndRe2CompileTrampolineResiduals).
      - x__fullmatch__mutmut_6, x__finditer__mutmut_6, x__findall__mutmut_6,
        x__match__mutmut_6 — `_re2_compile(pattern, )` drops the flags kwarg
        and falls back to the helper's default (0). Killable by passing a
        non-zero ``flags`` argument via the module-level function and
        asserting flag-sensitive behaviour.

    Pattern applied: **Non-Identity Inputs** — use ``re.IGNORECASE`` (value 2,
    non-zero) so the mutation of "forward flags" vs "drop flags" is visible.
    """

    def test_search_with_ignorecase_flag_forwards_through_dispatcher(self) -> None:
        """Kills x__search__mutmut_6 equivalent (flags forwarding).

        Module-level re.search must forward its ``flags`` argument through
        to _re2_compile.  Dropping the flags argument would cause the
        compile to use flags=0 (case-sensitive), and the case-inverted
        search would return None.
        """
        m = re.search(r"hello", "WORLD HELLO", flags=re.IGNORECASE)  # type: ignore[attr-defined]
        assert m is not None
        # Original (with flags forwarded): match found with .group() == "HELLO".
        # Mutant (drops flags): no match → AttributeError on the next line.
        assert m.group() == "HELLO"

    def test_search_without_flag_remains_case_sensitive(self) -> None:
        """Boundary assertion: WITHOUT the flag, search must remain case-sensitive.

        This is the reference-line of the Non-Identity Inputs pattern — confirms
        the flag value we're testing actually matters.
        """
        assert re.search(r"hello", "WORLD HELLO") is None  # type: ignore[attr-defined]

    def test_match_with_ignorecase_flag_forwards_through_dispatcher(self) -> None:
        """Kills x__match__mutmut_6: _re2_compile(pattern, ) drops flags.

        match() anchors at the start; with IGNORECASE, 'HELLO world' must match.
        """
        m = re.match(r"hello", "HELLO world", flags=re.IGNORECASE)  # type: ignore[attr-defined]
        assert m is not None
        assert m.group() == "HELLO"

    def test_match_without_flag_is_case_sensitive(self) -> None:
        assert re.match(r"hello", "HELLO world") is None  # type: ignore[attr-defined]

    def test_fullmatch_with_ignorecase_flag_forwards_through_dispatcher(self) -> None:
        """Kills x__fullmatch__mutmut_6: _re2_compile(pattern, ) drops flags.

        fullmatch requires the entire input match; IGNORECASE is needed.
        """
        m = re.fullmatch(r"hello", "HELLO", flags=re.IGNORECASE)  # type: ignore[attr-defined]
        assert m is not None
        assert m.group() == "HELLO"

    def test_fullmatch_rejects_prefix_only_match(self) -> None:
        """Canonical fullmatch boundary — with the flag active, a prefix
        must still not fullmatch.  Distinguishes fullmatch from match.
        """
        assert re.fullmatch(r"hello", "HELLO world", flags=re.IGNORECASE) is None  # type: ignore[attr-defined]

    def test_findall_with_ignorecase_flag_forwards_through_dispatcher(self) -> None:
        """Kills x__findall__mutmut_6: _re2_compile(pattern, ) drops flags."""
        results = re.findall(r"cat", "CAT dog Cat mouse cat", flags=re.IGNORECASE)  # type: ignore[attr-defined]
        assert results == ["CAT", "Cat", "cat"]

    def test_findall_returns_list_not_iterator(self) -> None:
        """Distinguishes findall (list) from finditer (iterator).

        Per the mutation-aware-test-design styleguide 'Assert observable
        outcomes' — asserting concrete container type kills any mutation
        that silently swaps the two.
        """
        results = re.findall(r"\d+", "1 22 333")  # type: ignore[attr-defined]
        assert isinstance(results, list)
        assert results == ["1", "22", "333"]

    def test_finditer_with_ignorecase_flag_forwards_through_dispatcher(self) -> None:
        """Kills x__finditer__mutmut_6: _re2_compile(pattern, ) drops flags."""
        it = re.finditer(r"cat", "CAT dog cat", flags=re.IGNORECASE)  # type: ignore[attr-defined]
        matches = [m.group() for m in it]
        assert matches == ["CAT", "cat"]

    def test_finditer_returns_iterator_not_list(self) -> None:
        """Distinguishes finditer from findall. ``list`` does not qualify as
        an iterator for the purposes of ``next()``; enforcing this assertion
        kills any swap.
        """
        it = re.finditer(r"\d+", "1 22 333")  # type: ignore[attr-defined]
        assert not isinstance(it, list)
        # Iterators support next().
        first = next(iter(it))
        assert first.group() == "1"


class TestSplitMutationKills:
    """Kill x__split__ survivors.

    Scope:
      - x__split__mutmut_1 (maxsplit default 0→1): trampoline-equivalent
        residual — wrapper forwards maxsplit positionally.
      - x__split__mutmut_2 (flags default 0→1): trampoline-equivalent
        residual.
      - x__split__mutmut_6 `.split(string, )`: drops maxsplit argument to
        the compiled pattern.  Killable by passing a non-zero maxsplit.
      - x__split__mutmut_11 `_re2_compile(pattern, )`: drops flags forwarding
        at the compile step. Killable by passing non-zero flags.

    Patterns applied: **Boundary Pair** (maxsplit ∈ {0, 1, 2}) plus
    **Non-Identity Inputs** (flags=IGNORECASE on a case-sensitive pattern).
    """

    def test_split_with_maxsplit_one_stops_after_first_match(self) -> None:
        """Kills x__split__mutmut_6: .split(string, ) drops maxsplit → defaults to 0.

        Boundary Pair pattern: maxsplit=1 must produce exactly 2 chunks
        (one split). With maxsplit=0 (mutant behaviour) we would get 3.
        """
        parts = re.split(r",", "a,b,c", maxsplit=1)  # type: ignore[attr-defined]
        assert parts == ["a", "b,c"]  # exactly one split happened

    def test_split_with_maxsplit_two_stops_after_second_match(self) -> None:
        """Boundary-pair upper bound: maxsplit=2 over three commas yields
        three chunks, with the final chunk containing the untouched tail.
        """
        parts = re.split(r",", "a,b,c,d,e", maxsplit=2)  # type: ignore[attr-defined]
        assert parts == ["a", "b", "c,d,e"]

    def test_split_with_maxsplit_zero_splits_all(self) -> None:
        """Boundary-pair reference: maxsplit=0 means 'no limit'. This is
        the value the x__split__mutmut_6 mutation falls back to, so we
        record the expected full-split behaviour explicitly.
        """
        parts = re.split(r",", "a,b,c,d")  # maxsplit omitted → wrapper default 0  # type: ignore[attr-defined]
        assert parts == ["a", "b", "c", "d"]

    def test_split_with_ignorecase_flag_forwards_through_dispatcher(self) -> None:
        """Kills x__split__mutmut_11: _re2_compile(pattern, ) drops flags.

        Use IGNORECASE on a case-sensitive separator pattern so the
        flag-forwarding path is observable.
        """
        parts = re.split(r"X", "aXbxc", flags=re.IGNORECASE)  # type: ignore[attr-defined]
        # Original (flags forwarded): both X and x are separators → 3 chunks.
        # Mutant (flags dropped): only X is a separator → 2 chunks.
        assert parts == ["a", "b", "c"]

    def test_split_without_flag_remains_case_sensitive(self) -> None:
        """Reference assertion for Non-Identity Inputs — confirms the
        flag actually matters for this pattern.
        """
        parts = re.split(r"X", "aXbxc")  # type: ignore[attr-defined]
        assert parts == ["a", "bxc"]


class TestSubMutationKills:
    """Kill x__sub__ survivors.

    Scope:
      - x__sub__mutmut_1 (count default 0→1): trampoline-equivalent residual.
      - x__sub__mutmut_2 (flags default 0→1): trampoline-equivalent residual.
      - x__sub__mutmut_12 `_re2_compile(pattern, )`: drops flags. Killable
        by passing non-zero flags.

    Pattern applied: **Non-Identity Inputs** — replacement string differs
    visibly from the match, and flags alter whether the match even occurs.
    """

    def test_sub_with_ignorecase_flag_forwards_through_dispatcher(self) -> None:
        """Kills x__sub__mutmut_12: _re2_compile(pattern, ) drops flags."""
        result = re.sub(r"cat", "DOG", "CAT and Cat and cat", flags=re.IGNORECASE)  # type: ignore[attr-defined]
        # Original (flags forwarded): all three case-variants replaced → 'DOG and DOG and DOG'.
        # Mutant (flags dropped): only lowercase 'cat' replaced → 'CAT and Cat and DOG'.
        assert result == "DOG and DOG and DOG"

    def test_sub_without_flag_is_case_sensitive(self) -> None:
        """Reference case — confirms the IGNORECASE flag actually matters."""
        result = re.sub(r"cat", "DOG", "CAT and Cat and cat")  # type: ignore[attr-defined]
        assert result == "CAT and Cat and DOG"

    def test_sub_count_limits_replacements(self) -> None:
        """Guards against count forwarding regressions. Replacement is
        visibly different from the match (Non-Identity Input), so any
        mutation that skips the replacement altogether would be visible.
        """
        result = re.sub(r"\d+", "NUM", "1 2 3 4", count=2)  # type: ignore[attr-defined]
        assert result == "NUM NUM 3 4"


class TestSubnMutationKills:
    """Kill x__subn__ survivors.

    Scope:
      - x__subn__mutmut_1 (count default 0→1): trampoline-equivalent residual.
      - x__subn__mutmut_2 (flags default 0→1): trampoline-equivalent residual.
      - x__subn__mutmut_8 `.subn(repl, string, )`: drops count. Killable by
        passing non-zero count and asserting both tuple elements.
      - x__subn__mutmut_12 `_re2_compile(pattern, )`: drops flags. Killable
        by passing non-zero flags.

    Pattern applied: **Non-Identity Inputs** combined with assertion of the
    full (string, count) tuple — subn returns BOTH parts, and mutations
    hide in either element.
    """

    def test_subn_with_count_limits_replacements_and_reports_count(self) -> None:
        """Kills x__subn__mutmut_8: .subn(repl, string, ) drops count.

        With count=2 over three matches, original returns (new_string, 2);
        mutant (count dropped) returns (fully-substituted_string, 3).

        Asserting BOTH tuple elements kills any mutation that hides in
        either place.
        """
        result_str, n = re.subn(r"\d+", "NUM", "1 2 3 4 5", count=2)  # type: ignore[attr-defined]
        assert result_str == "NUM NUM 3 4 5"
        assert n == 2

    def test_subn_with_count_zero_replaces_all(self) -> None:
        """Reference case: count=0 means 'replace all'.  Subn reports the
        total replacement count — asserting it prevents the return-shape
        mutations.
        """
        result_str, n = re.subn(r"\d+", "NUM", "1 2 3")  # type: ignore[attr-defined]
        assert result_str == "NUM NUM NUM"
        assert n == 3

    def test_subn_with_ignorecase_flag_forwards_through_dispatcher(self) -> None:
        """Kills x__subn__mutmut_12: _re2_compile(pattern, ) drops flags.

        Asserts the full tuple so count-shape mutations cannot hide.
        """
        result_str, n = re.subn(r"cat", "DOG", "CAT Cat cat", flags=re.IGNORECASE)  # type: ignore[attr-defined]
        # Original (flags forwarded): 3 case-insensitive matches → count=3.
        # Mutant (flags dropped): only lowercase 'cat' matches → count=1.
        assert result_str == "DOG DOG DOG"
        assert n == 3

    def test_subn_without_flag_is_case_sensitive(self) -> None:
        """Reference assertion for Non-Identity Inputs."""
        result_str, n = re.subn(r"cat", "DOG", "CAT Cat cat")  # type: ignore[attr-defined]
        assert result_str == "CAT Cat DOG"
        assert n == 1

    def test_subn_returns_tuple_not_string(self) -> None:
        """Asserts the structural return type. Any swap of subn→sub (tuple
        →string) is visible.
        """
        out = re.subn(r"\d+", "N", "1 2")  # type: ignore[attr-defined]
        assert isinstance(out, tuple)
        assert len(out) == 2  # (2-tuple structure)
        new_str, n = out
        assert isinstance(new_str, str)
        assert isinstance(n, int)
