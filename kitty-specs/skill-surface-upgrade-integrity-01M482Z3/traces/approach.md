# Approach

- 2026-10-06: Three concerns from plan.md: coalesce identical directory creates (IC-01), restore metadata version on failed upgrade (IC-02, serial after IC-01), doctor `missing` finding + `--fix` projection + no-tool-folder finding (IC-03, parallel). Red-first repro through `upgrade` / `doctor skills` per FR.
- 2026-10-06: WP01 rejected once (agent_profiles.py tolerance lacked focused tests and its write guard was broader than its recheck); fixed in 05237ae4. WP02 extended #3334 into a single `VersionStamp` restore authority plus a boundary context manager. WP03 dedups `missing` by installed path so tools sharing `.agents/skills` report once.
