"""#4327 unit tests: creation-time validation of the inline moment fields.

Covers the scope-clarification acceptance items that live in
``status/moment_fields.py`` itself: the 239/240/241 UTF-8 byte boundaries
(ASCII and multibyte — multibyte printable input is VALID within the bound,
never an error), the named-codepoint rejection of newlines and other
non-printables, whitespace-only normalization (tabs and runs of spaces
collapse; nothing else does), and the full pointer grammar actually in use —
scheme pointers, sentinels, synthetic colon tokens, PR refs, bare tokens,
repo-relative paths WITH spaces, absolute-path conversion, and the
outside-repo / traversal / no-root refusals — plus the #4327 squad fix-round
regressions: the scheme grammar is an allowlist (not any RFC 3986 scheme),
Windows drive-letter paths are classified before the scheme arms (never
scheme ``C``), and UNC device paths are refused in both slash spellings.
Pointers are never truncated and carry no byte bound.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from specify_cli.status.moment_fields import (
    _SUMMARY_MAX_UTF8_BYTES,
    ReviewRefValidationError,
    SummaryValidationError,
    validate_review_ref,
    validate_summary,
)

pytestmark = pytest.mark.fast


# ---------------------------------------------------------------------------
# --summary: one printable line, at most 240 UTF-8 bytes
# ---------------------------------------------------------------------------


class TestSummaryByteBoundaries:
    def test_239_bytes_pass(self) -> None:
        assert validate_summary("a" * 239) == "a" * 239

    def test_240_bytes_pass(self) -> None:
        assert validate_summary("a" * 240) == "a" * 240

    def test_241_bytes_fail_naming_the_actual_size_and_bound(self) -> None:
        with pytest.raises(SummaryValidationError, match=r"--summary is 241 UTF-8 bytes.*240"):
            validate_summary("a" * 241)

    def test_multibyte_printable_is_valid_within_the_bound(self) -> None:
        # 120 × 'é' (U+00E9, 2 UTF-8 bytes each) = 240 bytes: valid, and the
        # multibyte-ness is not itself an error (scope clarification).
        gist = "é" * 120
        assert len(gist.encode("utf-8")) == 240
        assert validate_summary(gist) == gist

    def test_multibyte_one_codepoint_over_the_bound_fails(self) -> None:
        gist = "é" * 120 + "é"  # 242 bytes
        with pytest.raises(SummaryValidationError, match=r"--summary is 242 UTF-8 bytes"):
            validate_summary(gist)

    def test_mixed_script_printable_gist_passes(self) -> None:
        # Printability, not ASCII-ness, is the rule (scope clarification).
        gist = "承認済み — approved after the focus-time fix ✓"
        assert validate_summary(gist) == gist


class TestSummaryPrintability:
    def test_newline_is_rejected_with_the_codepoint_named(self) -> None:
        with pytest.raises(SummaryValidationError, match=r"U\+000A"):
            validate_summary("approved\nsilently")

    def test_carriage_return_is_rejected(self) -> None:
        with pytest.raises(SummaryValidationError, match=r"U\+000D"):
            validate_summary("approved\rsilently")

    def test_control_characters_are_rejected(self) -> None:
        with pytest.raises(SummaryValidationError, match=r"U\+0000"):
            validate_summary("approved\x00silently")
        with pytest.raises(SummaryValidationError, match=r"U\+001B"):
            validate_summary("approved\x1bsilently")

    def test_zero_width_and_private_use_characters_are_rejected(self) -> None:
        with pytest.raises(SummaryValidationError, match=r"U\+200B"):
            validate_summary("approved\u200bsilently")
        with pytest.raises(SummaryValidationError, match=r"U\+E000"):
            validate_summary("approved\ue000silently")

    def test_non_ascii_space_separator_is_rejected(self) -> None:
        # NBSP is a Separator the relay side would still count toward the
        # byte bound; only ASCII space/tab normalize.
        with pytest.raises(SummaryValidationError, match=r"U\+00A0"):
            validate_summary("approved\u00a0fix")


class TestSummaryNormalization:
    def test_runs_of_spaces_and_tabs_collapse_to_one_space(self) -> None:
        assert validate_summary("  Claimed   after the\tinterview answers  ") == "Claimed after the interview answers"

    def test_blank_gist_is_rejected_not_emptied(self) -> None:
        with pytest.raises(SummaryValidationError, match="empty after trimming"):
            validate_summary("   \t  ")

    def test_nothing_is_ever_truncated(self) -> None:
        # A 240-byte gist is returned whole; the rejection path is the ONLY
        # response to an over-bound gist.
        gist = "x" * _SUMMARY_MAX_UTF8_BYTES
        assert validate_summary(gist) == gist


# ---------------------------------------------------------------------------
# --review-ref / --approval-ref: pointer-only, never prose
# ---------------------------------------------------------------------------


class TestPointerGrammarInUse:
    def test_scheme_pointers_are_accepted(self) -> None:
        for pointer in (
            "review-cycle://034-feature/WP01-some-title/review-cycle-1.md",
            "feedback://arbiter/WP01/review-cycle-1.md",
            "rev://ref/1",
            "approval://abc",
            "review://WP01/approved",
        ):
            assert validate_review_ref(pointer) == pointer

    def test_sentinels_are_accepted(self) -> None:
        assert validate_review_ref("action-review-claim") == "action-review-claim"
        assert validate_review_ref("force-override") == "force-override"

    def test_synthetic_colon_tokens_are_accepted(self) -> None:
        for pointer in (
            "review:WP01",
            "approval:WP01",
            "approval:local-review",
            "auto-approval:WP01:20260914",
        ):
            assert validate_review_ref(pointer) == pointer

    def test_pr_refs_are_accepted(self) -> None:
        assert validate_review_ref("PR#42") == "PR#42"
        assert validate_review_ref("PR#42-changes-requested") == "PR#42-changes-requested"
        assert validate_review_ref("#1298") == "#1298"

    def test_bare_tokens_are_accepted(self) -> None:
        # The pre-#4327 corpus' short handles (ref-123, review-001, ...).
        for pointer in ("ref-123", "review-001", "review-feedback-001", "local-review"):
            assert validate_review_ref(pointer) == pointer

    def test_surrounding_whitespace_is_trimmed(self) -> None:
        assert validate_review_ref("  review:WP01  ") == "review:WP01"

    def test_repo_relative_path_with_spaces_is_accepted(self) -> None:
        # Paths may contain spaces: absence of whitespace is never the
        # pointer classifier (scope clarification).
        pointer = "kitty-specs/034 my feature/review notes 1.md"
        assert validate_review_ref(pointer, repo_root=Path("/repo")) == pointer

    def test_pointers_are_never_truncated_and_carry_no_byte_bound(self) -> None:
        long_pointer = "review-cycle://" + "x" * 400 + "/review-cycle-1.md"
        assert validate_review_ref(long_pointer) == long_pointer

    def test_scheme_grammar_is_allowlisted_not_any_rfc3986_scheme(self) -> None:
        # The five documented URI families pass (case-insensitively — scheme
        # comparison follows RFC 3986); any OTHER `://` scheme is refused with
        # the pointer-forms message, because `file:///home/…`/`https://…` are
        # absolute-location pointers in URI clothing (#4327 squad fix round).
        assert validate_review_ref("Review-Cycle://034-feature/WP01/rc-1.md") == "Review-Cycle://034-feature/WP01/rc-1.md"
        for pointer in (
            "file:///home/user/secret/notes.txt",
            "https://internal.example/secret",
            "http://example.com/x",
            "ftp://files.internal/secret.txt",
        ):
            with pytest.raises(ReviewRefValidationError, match="pointer forms"):
                validate_review_ref(pointer)

    def test_colon_token_grammar_is_allowlisted_to_the_documented_prefixes(self) -> None:
        # `review:`/`approval:`/`auto-approval:` are the synthetic tokens in
        # use; any other bare-colon scheme (`javascript:…`, `data:…`) is
        # refused, never passed verbatim on the strength of scheme shape
        # alone (#4327 squad fix round).
        for pointer in ("javascript:alert(1)", "data:text/plain,hello", "mailto:me@example.com"):
            with pytest.raises(ReviewRefValidationError, match="pointer forms"):
                validate_review_ref(pointer)


class TestProseRefusal:
    def test_sentence_prose_is_refused_naming_the_pointer_forms(self) -> None:
        with pytest.raises(ReviewRefValidationError, match="pointer forms"):
            validate_review_ref("Looks good to me, ship it after the focus-time fix")

    def test_colon_prefixed_prose_is_still_prose(self) -> None:
        with pytest.raises(ReviewRefValidationError, match="pointer forms"):
            validate_review_ref("review: looks good to me")

    def test_dot_and_dotdot_bare_values_are_refused(self) -> None:
        with pytest.raises(ReviewRefValidationError, match="pointer forms"):
            validate_review_ref(".")
        with pytest.raises(ReviewRefValidationError, match="pointer forms"):
            validate_review_ref("..")

    def test_empty_value_is_refused(self) -> None:
        with pytest.raises(ReviewRefValidationError, match="non-empty pointer"):
            validate_review_ref("   ")


class TestAbsolutePathHandling:
    def test_absolute_path_inside_the_repo_becomes_repo_relative(self, tmp_path: Path) -> None:
        artifact = tmp_path / "kitty-specs" / "034-feature" / "review-cycle-1.md"
        assert validate_review_ref(str(artifact), repo_root=tmp_path) == "kitty-specs/034-feature/review-cycle-1.md"

    def test_absolute_path_outside_the_repo_is_refused(self, tmp_path: Path) -> None:
        with pytest.raises(ReviewRefValidationError, match="outside the repository"):
            validate_review_ref("/etc/passwd", repo_root=tmp_path)

    def test_absolute_path_without_a_resolved_repo_root_is_refused(self) -> None:
        # A caller with no root must fail clearly, never leak the absolute
        # path onto the wire.
        with pytest.raises(ReviewRefValidationError, match="no repository root"):
            validate_review_ref("/home/operator/checkout/kitty-specs/x.md")

    def test_traversal_escaping_the_repo_root_is_refused(self) -> None:
        with pytest.raises(ReviewRefValidationError, match=r"escapes the repository root"):
            validate_review_ref("../outside/review.md", repo_root=Path("/repo"))
        with pytest.raises(ReviewRefValidationError, match=r"escapes the repository root"):
            validate_review_ref("kitty-specs/../../../etc/passwd", repo_root=Path("/repo"))

    def test_inner_dotdot_that_stays_inside_is_normalized(self) -> None:
        assert validate_review_ref("kitty-specs/034/../034/review-cycle-1.md", repo_root=Path("/repo")) == "kitty-specs/034/review-cycle-1.md"

    def test_dot_components_are_normalized_away(self) -> None:
        assert validate_review_ref("./kitty-specs/034/review-cycle-1.md", repo_root=Path("/repo")) == "kitty-specs/034/review-cycle-1.md"

    def test_windows_drive_letter_paths_are_paths_never_scheme_c(self, tmp_path: Path) -> None:
        # `C:` (and lowercase `c:`) match the RFC 3986 scheme shape, so the
        # drive-letter prefix is classified BEFORE the scheme arms: both
        # spellings are absolute paths — refused without a root, converted
        # when genuinely in-repo — never returned verbatim (#4327 squad fix
        # round).
        for pointer in ("C:\\Users\\me\\secret.txt", "C:/Users/me/secret.txt", "c://foo"):
            with pytest.raises(ReviewRefValidationError, match="no repository root"):
                validate_review_ref(pointer)
            with pytest.raises(ReviewRefValidationError, match="outside the repository"):
                validate_review_ref(pointer, repo_root=tmp_path)

    def test_windows_drive_letter_path_inside_the_repo_becomes_repo_relative(self, tmp_path: Path) -> None:
        # On Windows the in-repo drive-letter spelling converts like any
        # other absolute path; on POSIX `C:/…` is not an OS-absolute path,
        # so the converter refuses it fail-closed instead of letting
        # resolve() ground it under the process CWD (which can sit inside
        # the repo and smuggle the drive path through as repo-relative).
        resolved = tmp_path.resolve()
        if sys.platform == "win32":
            artifact = resolved / "kitty-specs" / "review-cycle-1.md"
            assert validate_review_ref(str(artifact), repo_root=resolved) == "kitty-specs/review-cycle-1.md"
        else:
            with pytest.raises(ReviewRefValidationError, match="outside the repository"):
                validate_review_ref("C:/Users/me/secret.txt", repo_root=resolved)

    def test_unc_device_paths_are_refused_in_both_spellings(self, tmp_path: Path) -> None:
        # `\\fileserver\share\…` starts with neither `/` nor a drive letter,
        # but classification runs on the forward-slash spelling
        # (`//fileserver/share/…`), so both forms are absolute device paths —
        # an internal hostname never reaches the wire, with or without a
        # resolved root (#4327 squad fix round).
        for pointer in ("\\\\fileserver\\share\\secret.txt", "//fileserver/share/secret.txt"):
            with pytest.raises(ReviewRefValidationError, match="no repository root"):
                validate_review_ref(pointer)
            with pytest.raises(ReviewRefValidationError, match="outside the repository"):
                validate_review_ref(pointer, repo_root=tmp_path)

    def test_leading_backslash_path_is_classified_absolute_not_relative(self) -> None:
        # `\Users\me\secret.txt` converts to `/Users/me/secret.txt`: an
        # absolute path, never a repo-relative candidate.
        with pytest.raises(ReviewRefValidationError, match="no repository root"):
            validate_review_ref("\\Users\\me\\secret.txt")
