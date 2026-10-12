# Contracts — dead-path-docs-gate-anchor

No external or wire contract applies to this mission. It is a precision fix to a
single internal architectural test gate (`tests/architectural/test_dead_builtin_doc_paths.py`,
Gate D, #6096): it tightens the left boundary of a `git grep` regex and adds a
red-first regression test. There is no API, CLI surface, data model, or
cross-repo contract change — hence no contract artifacts beyond this note.
