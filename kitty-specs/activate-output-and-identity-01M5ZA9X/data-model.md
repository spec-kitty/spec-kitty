# Data model: Activate output and identity

No persisted data changes (C-001). In-memory shapes only:

- **Preservation result** (`pack_manager`, replaces the `(ids, warnings, in_force)` tuple): `ids: list[str]`, `warnings: list[str]`, `in_force: bool`, `unresolved_reason: str | None` (set only when the effective set could not be resolved and `ids` is a stand-in).
- **`ActivationResult.listed`** (`pack_manager`): `list[str]`, the post-state list the plan wrote for the kind (empty when the allow list stayed absent). The CLI prints it only under `--only`.
- **Org-required freeze warning** (`activation_engine`): text derived from the kind token and its plural; emitted for kinds whose `ArtifactKind.effective_when_absent == "required"`.

Invariants: the written allow list, the deny list and exit codes are byte-identical to `origin/main` for every input (pinned by asserting the written list in each new CLI test).
