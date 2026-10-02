"""Cited code for the citation_check fixtures. It is never imported."""

# commented_only is a name that appears in this comment and nowhere else.
NOTE = "string_only is a name that appears in this string and nowhere else."

REAL_CONSTANT = 1
FIRST, SECOND = 1, 2


def real_function_extended() -> None:
    """A longer name: a prefix of it must not resolve."""


def real_function() -> int:
    return REAL_CONSTANT


class Sample:
    content_invariant: str
    kept: int = 0

    def method(self) -> None:
        local_only = 1
        self.attribute_only = local_only
