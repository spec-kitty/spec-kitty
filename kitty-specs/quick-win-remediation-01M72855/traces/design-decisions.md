# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-10 · claude:claude-opus-5-5:planner-priti · **[2026-11-10][plan] Seed: decisions already taken.** #7445 Option A (utf-8-sig in load_meta/parse_meta_file, kernel decoder unchanged); #7442 refuse non-id roster entries and repair Mission 058 under a dated sanctioned archive correction; #7463 hoist + add, no wall-clock test; #7439 one splitter + one decode helper in store.py only; #7441 allow_nan=False + LF writes; #7440 drop the mixed pair; #7443 one locator in new core/wp_task_files.py. Same-class sites elsewhere are follow-ups.

2026-11-10 · claude:claude-opus-5-5:python-pedro · **[2026-11-10][implement] #7439 splitter + decode-helper shape.** store.py gets one module-private regex splitter (_jsonl_lines, CRLF|LF|CR, numbering identical to splitlines for LF logs) and one decode helper (_decode_json_line) that raises StoreError itself; seed_scratch_event_log re-maps it to its documented ValueError and the lenient reader catches it, so the except tuple (ValueError, RecursionError) lives in exactly one place.

2026-11-10 · opencode:glm-5.3:python-pedro · **[2026-11-10][implement] #7445 Option A (decision 01M72871WDH3GYMFKTAHRZFJ14): made _UTF8_SIG the default encoding of load_meta and parse_meta_file only. kernel/meta_decode.py untouched (C-002) and load_meta_strict keeps bom_tolerant=False meaning reject, so BOM tolerance on the canonical readers is the new default but stays opt-out; utf-8-sig decodes a BOM-less file byte-identically to utf-8 (FR-015), so no caller's accepted set shrinks.**

2026-11-10 · claude:claude-opus-5-5:python-pedro (WP02) · WP02 #7442: roster entry refusal is a typed SubtaskRosterEntryError (subclass of SubtaskRosterResolutionError), so every existing fail-closed catch keeps working while the WP view can tolerate exactly this case (empty authored subtasks, other authored fields kept) without swallowing missing/ambiguous-file errors. authored_roster_owner_map re-raises it unprefixed because the message already names the file. #7443: match_wp_task_files returns non-regular entries on purpose; gate readers refuse them ('is not a regular file'), the view and phase-1 mirror treat them as no file; several matches stay 'ambiguous' even if one is a directory.

2026-11-10 · claude:claude-opus-5-5:python-pedro · **[2026-11-10][implement] #7441 refusal ident and #7440 mixed pair.** serialize_event_line names the row by event_id and wp_id (a tiny _event_ident helper, '<unidentified>' fallback); the refusal fires while additions are built, before mkstemp, so nothing is written. The sanitizer drops a mixed naive/aware pair with one debug line and does not normalize naive values to UTC, unlike the events write service which refuses it at its request boundary.
