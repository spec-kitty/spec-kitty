# Efficient Local Tooling

Use efficient, operation-appropriate local tools by default.

## Session record

- Record the locally available preferred tools, the tool choice for the current session, and any missing-tool remediation in `.kittify/memory/available_tooling.md`.
- When a preferred tool is missing, warn the user that a more efficient option exists and offer to guide them through installation or setup before falling back.
- Use `has` when it helps confirm whether a preferred tool is installed and to capture that result in the session tooling record.

Examples:

```bash
has rg fd jq yq
has lnav ncdu bat
```

## Repository search

- Prefer `rg` over `grep`, `git grep`, or `find | xargs grep` for repository text searches.
- Scope searches deliberately with options such as `-n`, `-l`, `--type`, and path filters.
- Prefer `fd` over slower recursive `find` usage for file and path discovery when you are locating files rather than searching file contents.
- Use `fzf` to narrow large result sets interactively when a non-interactive `rg` or `fd` result is too broad.

Examples:

```bash
rg -n "Directive" docs
rg --type py "validate_" src
rg -l "TODO" tests
fd '\.directive\.yaml$' .kittify
fd prompt src .kittify | fzf
```

## Large-file inspection

- Prefer `less` or another pager for large files instead of dumping them directly with `cat`.
- Use targeted extraction commands when only a file section is needed.
- Use `bat` for syntax-highlighted previews or short, structured inspection, but keep `less` as the default for very large files.

Examples:

```bash
less CHANGELOG.md
sed -n '1,120p' README.md
bat --style=plain pyproject.toml
```

## Compressed content

- Prefer stream-oriented tools such as `zcat` when inspecting gzip-compressed content.
- Avoid unpacking archives to disk unless the workflow genuinely requires extracted files.

Examples:

```bash
zcat logs/app.log.gz | less
zcat snapshot.json.gz | jq '.items[0]'
```

## Structured data inspection

- Prefer `jq` for JSON inspection and transformation instead of ad hoc text matching.
- Prefer `yq` for YAML inspection and transformation when repository configuration or doctrine artifacts need structured queries.

Examples:

```bash
jq '.project.version' package.json
yq '.agents.available' .kittify/config.yaml
```

## Logs and disk usage

- Prefer `lnav` for log-heavy workflows where indexed viewing, filtering, or multi-file navigation is materially better than a pager.
- Prefer `ncdu` for disk-usage investigation instead of manual recursive size checks.

Examples:

```bash
lnav logs/app.log
ncdu .
```

## Git ergonomics

- Prefer local git defaults that reduce noisy paging, expensive status scans, or accidental interactive flows in automation.
- Use repository-safe settings and explicit flags when they improve speed or reproducibility.

Examples:

```bash
git -c core.pager=cat status --short
git -c commit.gpgsign=false commit -m "..."
```

## Navigation

- Prefer `zoxide` for repeated navigation across large repositories or multi-worktree setups when jumping directly to known directories is faster than manual `cd` traversal.

Examples:

```bash
zoxide query src
z src
```

## Python environment isolation (uv)

- In a git worktree or a fresh clone of a `uv`-managed Python project, a bare `python` or `pytest` invocation resolves imports against the interpreter's installed/site-packages state, not necessarily the checkout you are standing in. A lane worktree and a fresh clone are separate checkouts from the repository root; running the bare interpreter can silently import the wrong checkout's source tree instead of the one you intend to test.
- Prefer `uv run <command>` for every gate, test, or script invocation so the command resolves against the current checkout's declared environment and dependencies, not whatever a bare interpreter happens to find first.
- This matters most for every gate run inside a lane worktree: linting, type-checking, and the test suite must all go through `uv run` so a green result reflects the lane's own code, not a sibling checkout's.

Examples:

```bash
uv run pytest tests/ -q
uv run ruff check .
uv run mypy src/
```

## Gate execution mode

- Run verification gates (test suites, linters, type checkers, terminology or policy guards) in the foreground and wait for them to finish before continuing or handing off. Backgrounding a gate run and moving on to the next step stalls any handoff that depends on the gate's result — the calling turn ends while the gate is still pending, and no later turn resumes it automatically.
- Only background a long-running command when nothing in the current turn depends on its outcome; if the very next action is "commit," "hand off," or "advance state" based on the gate passing, run it in the foreground.

Examples:

```bash
uv run pytest tests/ -q            # foreground: wait, then act on the result
uv run pytest tests/ -q &          # avoid before a commit/handoff that needs the result
```

## Shell quoting

- A backtick inside a double-quoted shell string (`"...`text`..."`) is interpreted as command substitution, not literal text — this silently corrupts commit messages, PR bodies, and any other quoted argument that contains a backtick (for example code-span markdown inside `gh ... --body "..."` or `git commit -m "..."`).
- Prefer `--body-file <path>`, `-F key=@-` piped from a heredoc, or a heredoc passed directly to `-m`/`-F` when the content may contain backticks, instead of embedding it in a double-quoted argument.

Examples:

```bash
gh pr create --title "..." --body-file body.md
gh api ... -F body=@- <<'EOF'
Some text with `inline code` that must stay literal.
EOF
git commit -F - <<'EOF'
fix: handle `inline code` in commit body safely
EOF
```

## Windows and WSL

- Prefer WSL for repository-scale Unix-oriented workflows on Windows when it materially improves tool availability or throughput.
- Use efficient native tools such as `robocopy` or `7z` when Windows-native workflows are required.
- Prefer faster copy or sync tools over slow exploratory copy loops.

Examples:

```powershell
robocopy src dst /E
7z x archive.tar.gz
wsl rg -n "TODO" /mnt/c/project
```

## Avoid

- `grep -R "..." .` for routine repository search
- `find . -type f ...` when `fd` covers the same path-discovery task more directly
- `cat` on large files when a pager or targeted slice is sufficient
- regex or text scraping when `jq` or `yq` can query the structure directly
- extracting gzip archives to disk just to inspect contents
- slow copy loops when `rsync`, `robocopy`, or an equivalent optimized tool is available
- bare `python`/`pytest` invocations for gates or tests in a worktree or fresh clone when `uv run` is available
- backgrounding a gate/test run when the next action depends on its pass/fail result
- backticks inside a double-quoted shell string when the content may contain them — use `--body-file`, `-F key=@-`, or a heredoc instead
