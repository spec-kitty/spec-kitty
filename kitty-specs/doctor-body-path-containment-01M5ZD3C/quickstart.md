# Quickstart — verify #6418

```bash
# in a scratch project: spec-kitty init, then a team pack at .kittify/team-pack with
# drg/fragment.yaml declaring:  - {id: team-asset, kind: assets, title: Team asset, body_path: ../../../../etc/hostname}
spec-kitty doctor charter-packs --json; echo "rc=$?"   # expect rc=1, org_drg.body_path_escapes has 1 entry
spec-kitty doctor charter-packs                        # expect "body_path escapes: 1 ..." naming team-asset
# change body_path to bodies/team-asset.md (no such file needed)
spec-kitty doctor charter-packs --json; echo "rc=$?"   # expect rc=0, body_path_escapes == []
```
