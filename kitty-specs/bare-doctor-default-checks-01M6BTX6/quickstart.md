# Quickstart — see the bare `doctor` default run

## Before (current `main`, 4.0.0rc8)

```console
$ cd <any spec-kitty project>
$ spec-kitty doctor; echo "exit=$?"
 Usage: spec-kitty doctor [OPTIONS] COMMAND [ARGS]...
 ... help table ...
Error: no diagnostic ran. `spec-kitty doctor` needs a subcommand ...
exit=2
```

No check runs, and exit 2 reads as a usage error to a human and to a wrapper.

## After

```console
$ spec-kitty doctor; echo "exit=$?"
Default checks (3)

  ok    command-files  all agent command files match the installed version
  ok    state-roots    every state root and surface is present and gitignored
  ok    ops            no orphan Op records

3 of 3 checks healthy -- run `spec-kitty doctor <subcommand>` for a full report.
exit=0
```

With a real finding the owning subcommand is named on the finding line and the exit code
is 1:

```console
$ spec-kitty doctor; echo "exit=$?"
Default checks (3)

  ok    command-files  all agent command files match the installed version
  FAIL  state-roots    1 finding -- full report: spec-kitty doctor state-roots
          runtime surface .kittify/state is not covered by .gitignore
  ok    ops            no orphan Op records

2 of 3 checks healthy -- run `spec-kitty doctor <subcommand>` for a full report.
exit=1
```

Outside a project the standard not-in-project error is printed and the command exits 1.

## Unchanged

Every `spec-kitty doctor <subcommand>` keeps its own output and exit codes; only the bare
invocation and the group help string change.
