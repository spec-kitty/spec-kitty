"""Tests for ``specify_cli.auth.loopback.pkce`` (feature 080, WP02 T015).

Covers:

- verifier length / alphabet (RFC 7636 §4.1)
- challenge is SHA256 base64url with no padding (RFC 7636 §4.2)
- the RFC 7636 Appendix B known-answer example
- every call returns a fresh verifier (``secrets.token_urlsafe`` uses CSPRNG)
"""

from __future__ import annotations

import re

from specify_cli.auth.loopback.pkce import (
    generate_code_challenge,
    generate_code_verifier,
    generate_pkce_pair,
)

# RFC 7636 §4.1 defines the code verifier alphabet. token_urlsafe uses
# the base64url alphabet which is a strict subset (no `.` or `~`), so this
# regex is sufficient.

import pytest

pytestmark = [pytest.mark.integration]

_VERIFIER_RE = re.compile(r"^[A-Za-z0-9_\-]+$")


def test_verifier_is_43_characters() -> None:
    verifier = generate_code_verifier()
    assert len(verifier) == 43


def test_verifier_uses_urlsafe_alphabet() -> None:
    verifier = generate_code_verifier()
    assert _VERIFIER_RE.match(verifier), f"non-urlsafe char in verifier: {verifier!r}"


def test_verifier_is_random_between_calls() -> None:
    verifiers = {generate_code_verifier() for _ in range(32)}
    # 43 chars of CSPRNG output colliding within 32 calls is statistically
    # impossible; any repeat signals a broken implementation.
    assert len(verifiers) == 32


def test_challenge_has_no_padding() -> None:
    verifier = generate_code_verifier()
    challenge = generate_code_challenge(verifier)
    assert "=" not in challenge


def test_challenge_is_base64url_of_sha256() -> None:
    import base64
    import hashlib

    verifier = "some-verifier-value"
    expected = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest())  # noqa: TID251 — PKCE code_challenge is a raw SHA-256 hash of the verifier (RFC 7636 §4.2), not a charter algorithm
        .rstrip(b"=")
        .decode("ascii")
    )
    assert generate_code_challenge(verifier) == expected


def test_rfc7636_known_answer() -> None:
    """RFC 7636 Appendix B example: verifier -> challenge (S256)."""
    verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
    expected = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
    assert generate_code_challenge(verifier) == expected


def test_generate_pkce_pair_returns_matching_verifier_and_challenge() -> None:
    verifier, challenge = generate_pkce_pair()
    assert len(verifier) == 43
    assert generate_code_challenge(verifier) == challenge
