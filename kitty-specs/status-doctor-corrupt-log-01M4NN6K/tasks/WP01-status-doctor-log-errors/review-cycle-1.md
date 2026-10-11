---
affected_files: []
cycle_number: 1
mission_slug: status-doctor-corrupt-log-01M4NN6K
reproduction_command:
reviewed_at: '2026-10-11T15:21:05Z'
reviewer_agent: pi:reviewer-renata:reviewer
wp_id: WP01
---

# WP01 review feedback — cycle 1

Reviewer: independent Reviewer Renata correctness and test/delivery lenses.
Outcome: reject; two witnessed P2 gaps contradict FR-001/FR-003.

1. store.py transition decoding (currently lines 710–717): otherwise valid lane event with mission_slug=123 and no mission_id raises AttributeError ('int' object has no attribute 'strip'). Both snapshot states crash; JSON CLI exits1 with empty output. Normalize AttributeError at the existing transition decoder catch, just as the annotation decoder does; preserve physical line-bearing StoreError. No arbitrary doctor catch, model/parser redesign or new authority. Add direct-reader and both-snapshot real doctor/CLI regressions using otherwise valid records.
2. doctor.py later log-dependent reads: successful initial canonical read can be followed by a filesystem/decode failure in drift/materialization or reviewer-self-approval. Guard ALL dependent work with exactly StoreError/OSError/UnicodeError; turn expected late read failure into the existing safe event_log_error and discard any partial log-dependent findings (do not recommend actions from untrusted authority). Independent issue/frontmatter/sparse checks still run. Use a path-scoped deterministic read failure injection after first successful read; real parser and entry points, no mocked doctor or reducer.
3. Nonblocking but fold now: readable ReviewerSelfApproval lifecycle control in run_doctor, paired with corruption and restoration, proves REVIEW_INDEPENDENCE still returns on healthy authority.

Scope clarification approved by parent: C-002's one-site annotation-only restriction must be amended to the two existing canonical decoder exception tuples (annotation and transition); this is still #5924 status-log diagnostics, not a new parser/shared abstraction. Refresh planning analysis after amendment before reimplementation.

Commit new failing tests before remediation; preserve first RED41930fe8f3 and fixcc721e3372 evidence. Targeted tests/lint/type/coverage only; parent owns final broad rerun. Do not merge/consolidate/push main or restore/drop user's evidence stash.
