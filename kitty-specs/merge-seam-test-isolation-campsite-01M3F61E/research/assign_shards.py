"""Deterministic file -> sweep-shard assignment for the #5118 sweep (plan artifact).

Run from the repository root:  python kitty-specs/<mission>/research/assign_shards.py
Reads global_state_sites_classified.tsv beside this file; writes sweep_shards.tsv.
"""
import collections, csv, fnmatch, pathlib
HERE = pathlib.Path(__file__).parent
CMD = "tests/specify_cli/cli/commands/"
# Files owned by in-flight mission 01M3EW3Z (C-002): never edited here, allowlisted as deferred.
DEFERRED = ["tests/architectural/test_docs_cli_reference_parity.py",
            "tests/architectural/test_single_mission_surface_resolver.py",
            "tests/status/test_parity.py",
            "tests/architectural/surface_resolution_audit/*"]
RULES = [  # (shard, glob patterns) -- first match wins
    ("S1-charter-cli", [CMD + "charter/*", CMD + "*charter_generate*", CMD + "*charter_interview*", CMD + "*end_of_interview*"]),
    ("S2-widen-decision-cli", [CMD + "*widen*", CMD + "*prereq*", CMD + "*decision*", CMD + "*charter*"]),
    ("S3-doctrine-doctor-upgrade-cli", [CMD + "*doctrine*", CMD + "*doctor*", CMD + "*upgrade*"]),
    ("S4-misc-cli", [CMD + "*"]),
    ("S5-specify-cli-other", ["tests/specify_cli/*"]),
    ("S6-import-hygiene", ["tests/docs/*", "tests/architectural/*", "tests/release/*", "tests/scripts/*", "tests/ci/*", "tests/lint/*"]),
    ("S7-integration-research", ["tests/integration/*", "tests/research/*"]),
    ("S8-remaining", ["tests/*"]),
]
rows = list(csv.DictReader(open(HERE / "global_state_sites_classified.tsv"), delimiter="\t"))
per_file = collections.Counter(r["file"] for r in rows)
out, per_shard = [], collections.Counter()
for f, n in sorted(per_file.items()):
    shard = "E4-deferred-01M3EW3Z" if any(fnmatch.fnmatch(f, g) for g in DEFERRED) else next(s for s, pats in RULES if any(fnmatch.fnmatch(f, p) for p in pats))
    out.append((shard, f, n)); per_shard[shard] += n
with open(HERE / "sweep_shards.tsv", "w") as fh:
    fh.write("shard\tfile\tsites\n")
    fh.writelines(f"{s}\t{f}\t{n}\n" for s, f, n in out)
for s, n in sorted(per_shard.items()):
    print(f"{s:34} sites={n:4} files={sum(1 for x in out if x[0]==s)}")
