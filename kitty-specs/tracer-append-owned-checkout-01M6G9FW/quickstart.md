# Quickstart — verify tracer-append owned-Mission routing

Run from the repository root of a checkout of this branch.

## 0. Environment

```bash
make sync-packs            # once per checkout
uv sync --frozen --all-extras
```

## 1. The selector exists

```bash
uv run spec-kitty agent tracer-append --help | grep -- --owned-checkout
```

On `main` this prints nothing; on this branch it prints the shared owned-checkout help.

## 2. The defect's own scenario (owned checkout, no flag)

```bash
uv run pytest tests/specify_cli/cli/commands/agent/test_tracer_append_owned_checkout_7081.py -q
```

The module builds a repository root `R` on `main` plus an owned checkout `P` on the Mission
branch, with the Mission's `meta.json` in `P`, then invokes the real `tracer-append`
command with cwd inside `P`. On `main` the entry is written into `R` and the command
refuses `PROTECTED_BRANCH_REFUSED`; on this branch it commits on `P` and `R` is untouched.

## 3. Refuse before writing

```bash
uv run spec-kitty agent tracer-append \
  --mission <handle> --category approach --entry "x" --actor tester \
  --owned-checkout <repository-root> --json
```

Expect exit 1 with `{"ok": false, "error": {"code": "OWNED_CHECKOUT_IS_REPOSITORY_ROOT",
...}}` and no `traces/` file created anywhere.

## 4. The gates this change must not disturb

```bash
uv run pytest tests/architectural/test_owned_checkout_single_authority.py \
              tests/mission_runtime/test_coord_read_seam_callers.py \
              tests/specify_cli/cli/commands/test_owned_refusal_format_unified.py -q
```

The single-authority gate must pass with its allowlist still empty.
