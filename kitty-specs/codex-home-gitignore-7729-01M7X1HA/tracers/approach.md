# Approach

- Grounded every #7729 root-cause citation on `cfa68136` before specifying (research/code-grounding.md).
- Red-first: extend the existing reproduction to drive the real upgrade runner and the pulled clone before any fix commit.
- Red-first commit b5c084a7 (reproduction only, marker kept) failed 2/2 on the defect assertions with `SPEC_KITTY_RUN_P0_REPRO=1`; fix commit ecf17856 removed the marker and turned both green.
