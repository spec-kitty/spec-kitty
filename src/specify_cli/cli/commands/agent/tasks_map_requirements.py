"""The ``map-requirements`` command family, relocated out of ``tasks.py`` (WP06, #2305).

Mission ``tasks-py-degod-wave2-01KWH9EQ`` FR-001/FR-002: ``_do_map_requirements``
+ the 11 ``_mr_*`` phase helpers + ``_MapReqState`` +
``_default_map_requirements_ports`` live here, moved VERBATIM from ``tasks.py``.
The ``@app.command`` Typer wrapper (``map_requirements``) stays in ``tasks.py``
and delegates to :func:`_do_map_requirements` (the byte-frozen ``--help``
surface is the registration shim's).

**Orchestration shape** (unchanged): the Typer command declares the CLI
surface; ``_do_map_requirements`` runs the phase helpers in the SAME order as
the original single body — validate → resolve → plan (the pure WP04
``plan_mapping`` core) → gate → write → stale gate → finalize — so the
frontmatter write still precedes the post-write stale gate
(partial-write-on-refusal timing, NFR-001/WP04). The write/commit executes
through the WP02 ports (``FsReader.primary_anchor_dir`` fold,
``commit_artifact`` on the coord WRITE authority).

**C-001 divergence wiring**: ``map_requirements`` sits on the REFUSE arm —
when auto-commit resolves on, ``_mr_resolve_context`` resolves the placement
and refuses exit-1 through ``_tasks._protected_branch_status_commit_error``
with NO ``_skip_target_branch_commit`` pre-gate (that skip-exit-0 pre-gate is
``move_task``-only). The wiring moved untouched; the coord harness refuse-arm
case (harness label T005) pins it.

**Seam bridge** (research.md D1/D7): the relocated bodies reach every patched
seam symbol through a lazy in-function import of the ``tasks`` module
(``from specify_cli.cli.commands.agent import tasks as _tasks``) and call
``_tasks.<attr>(...)``, so every historical ``@patch("...agent.tasks.<sym>")``
/ ``monkeypatch.setattr(tasks, ...)`` keeps INTERCEPTING after the move.
``tasks.py`` re-imports the family in the explicit ``as`` re-export form, so
``tasks.<name>`` stays a module attribute. Symbols with ZERO patch sites and a
canonical home outside ``tasks.py`` are imported directly at module scope
(cycle-safe: none of those modules import ``tasks``).

Per-symbol routing/interception evidence:
``kitty-specs/tasks-py-degod-wave2-01KWH9EQ/seam-checklist.md`` (Layer 4 of
the parity contract).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import typer

from kernel._safe_re import re
from mission_runtime import CommitTarget, MissionArtifactKind, placement_seam
from specify_cli.agent_tasks_ports import MissionHandle, TasksPorts
from specify_cli.cli.commands.agent.tasks_mapping_core import (
    TRACKER_ONLY_MODE,
    MappingPlan,
    MappingRequest,
)
from specify_cli.cli.commands.agent.tasks_outline import TASKS_MD_FILENAME
from specify_cli.requirement_mapping import CoverageSummary, grammar
from specify_cli.upgrade.pre30_guard import Pre30LayoutError, check_pre30_layout

#: ``actor`` recorded on the ``tracker_refs`` ``InnerStateChanged`` annotation
#: (WP08 / T030) -- mirrors the ``<FOO>_COMMAND_NAME`` convention used by the
#: sibling agent commands (e.g. ``mission.FINALIZE_TASKS_COMMAND_NAME``).
MAP_REQUIREMENTS_COMMAND_NAME = "spec-kitty agent tasks map-requirements"

#: requirement-id-grammar-01M3NRCA WP03 (FR-012, Sonar S1192): the ONE hint
#: naming the grammar, composed from :data:`grammar.RULE_TEXT` rather than
#: restating the retired per-kind rule text locally (C-001 -- this string
#: has no ``<kind>-\d`` shape, so it never trips the single-source
#: pattern-literal gate). Every refusal site below (the
#: pre-write malformed gate and the post-write stale gate, JSON and console
#: legs alike) derives from this ONE constant.
_REQUIREMENT_ID_GRAMMAR_HINT = (
    f"Requirement IDs must match {grammar.RULE_TEXT} with kind FR, NFR, C or SC (e.g. FR-003, FR-003a, SC-001); cite another mission's ID as <mission-slug>#<ID>."
)

#: The post-write stale-gate hint: the grammar hint plus the reason
#: explanation plus the ``--replace`` recovery example.
_STALE_REFS_HINT = (
    f"{_REQUIREMENT_ID_GRAMMAR_HINT} 'malformed' refs violate that format; "
    "'unknown_spec_id' refs are well-formed but not declared in spec.md "
    "(see parsed_spec_ids). Re-run with --replace to correct, "
    "e.g.: map-requirements --wp WP01 --refs FR-001 --replace"
)


def _mr_sorted_spec_ids(spec_ids: set[str]) -> list[str]:
    """``sorted(spec_ids)`` -- shared between the pre-write and stale gates."""
    return sorted(spec_ids)


def _canonical_input_refs(refs: list[str]) -> list[str]:
    """Canonicalise operator-supplied refs through the grammar (FR-006).

    A token the grammar cannot parse is passed through VERBATIM (never
    uppercased), so the pre-write gate reports exactly what the author typed
    (``bogus`` stays ``bogus``, ``FR_001`` stays ``FR_001``). A well-formed
    token (SC, letter-suffixed, or foreign-qualified included) is rendered in
    its canonical form.
    """
    return [grammar.canonical(ref) or ref for ref in refs]


def _default_map_requirements_ports(target_branch: str | None) -> TasksPorts:
    """Production port bundle for ``map_requirements`` (coord router bound to tasks.py)."""
    from specify_cli.cli.commands.agent import tasks as _tasks

    return TasksPorts(
        fs=_tasks.RealFsReader(),
        # map_requirements threads the resolved ``target_branch`` into
        # ``commit_for_mission`` (ff-advance parity) and routes only the commit
        # seam through ``tasks`` (it inherited the base ``commit_status``).
        coord=_tasks.seam_coord_router(thread_target_branch=True, target_branch=target_branch),
        git=_tasks.RealGitOps(),
        render=_tasks.RealRender(),
    )


@dataclass
class _MapReqState:
    """Mutable orchestration state threaded through ``map_requirements``' phases.

    The single-body command tracked ~20 loose locals across resolve → plan →
    write → gate → finalize; the phase helpers exchange this one value object
    instead. Not frozen: each phase fills its own slice in the SAME order the
    original body did, so the frontmatter write still fires BEFORE the post-write
    stale gate (partial-write-on-refusal timing — NFR-001/WP04).
    """

    # --- raw command inputs ---
    wp: str | None
    refs: str | None
    batch: str | None
    replace: bool
    tracker_ref: list[str] | None
    mission: str | None
    json_output: bool
    auto_commit: bool | None
    # --- phase A: input-mode facts ---
    tracker_ref_values: list[str] = field(default_factory=list)
    tracker_only_mode: bool = False
    # --- phase B: resolved context ---
    repo_root: Path = field(default_factory=Path)
    mission_slug: str = ""
    main_repo_root: Path = field(default_factory=Path)
    target_branch: str = ""
    auto_commit_on: bool = False
    commit_target: CommitTarget = field(default_factory=lambda: CommitTarget(ref=""))
    # --- phase C: resolved read dirs + parsed reads ---
    feature_dir: Path = field(default_factory=Path)
    primary_dir: Path = field(default_factory=Path)
    tasks_dir: Path = field(default_factory=Path)
    all_spec_ids: set[str] = field(default_factory=set)
    functional_ids: set[str] = field(default_factory=set)
    #: #3394 review F1 -- non-blocking signal: raw requirement-shaped tokens in
    #: spec.md that matched none of the recognized declared shapes.
    requirement_extraction_warnings: list[str] = field(default_factory=list)
    #: WP06 (#3396) T032a plumbing fix: the raw spec.md text, stored here so
    #: ``_mr_plan`` (Phase D) can feed it to the bare-prose requirement-id
    #: detector -- previously this text was read locally in this phase and
    #: discarded, leaving Phase D with no access to it.
    spec_content: str = ""
    new_mappings: dict[str, list[str]] = field(default_factory=dict)
    # --- phase D: pure decision ---
    mapping_plan: MappingPlan | None = None
    # --- phase F: finalize ---
    coverage: CoverageSummary | None = None
    committed: bool = False
    commit_sha: str | None = None
    commit_result_payload: dict[str, str] | None = None


def _mr_validate_modes(st: _MapReqState) -> None:
    """Phase A: the operator-mode gates (batch vs wp/refs vs tracker-only)."""
    from specify_cli.cli.commands.agent import tasks as _tasks

    # T040 / FR-011 (F-10): tracker_ref values are persisted alongside
    # requirement_refs.  --tracker-ref is repeatable and requires --wp.
    st.tracker_ref_values = [t.strip() for t in (st.tracker_ref or []) if t and t.strip()]

    if st.batch and (st.wp or st.refs):
        _tasks._output_error(st.json_output, "Cannot combine --batch with --wp/--refs. Use one mode.")
        raise typer.Exit(1)

    if st.tracker_ref_values and (st.batch or st.wp is None):
        _tasks._output_error(
            st.json_output,
            "--tracker-ref requires --wp (cannot be combined with --batch).",
        )
        raise typer.Exit(1)

    # When only --tracker-ref is supplied (no --refs), allow the persistence of
    # tracker refs without changing requirement_refs.  This is the primary usage
    # shape per the WP10 spec.
    st.tracker_only_mode = bool(st.tracker_ref_values and st.wp is not None and not st.refs)

    if not st.batch and not (st.wp and st.refs) and not st.tracker_only_mode:
        _tasks._output_error(
            st.json_output,
            "Provide either --wp + --refs (individual), --batch, or --wp + --tracker-ref.",
        )
        raise typer.Exit(1)


def _mr_resolve_context(st: _MapReqState) -> None:
    """Phase B: repo/mission/target-branch resolution + the protected-branch gate."""
    from specify_cli.cli.commands.agent import tasks as _tasks

    repo_root = _tasks.locate_project_root()
    if repo_root is None:
        _tasks._output_error(st.json_output, "Could not locate project root")
        raise typer.Exit(1)
    st.repo_root = repo_root

    # FR-010 / FR-019: one-shot sparse-checkout session warning.
    _tasks._emit_sparse_session_warning(repo_root, command="spec-kitty agent tasks map-requirements")

    st.mission_slug = _tasks._find_mission_slug(explicit_mission=st.mission, json_output=st.json_output, repo_root=repo_root)
    st.main_repo_root, st.target_branch = _tasks._ensure_target_branch_checked_out(repo_root, st.mission_slug, st.json_output)
    st.auto_commit_on = _tasks.get_auto_commit_default(st.main_repo_root) if st.auto_commit is None else st.auto_commit
    st.commit_target = CommitTarget(ref=st.target_branch)
    if st.auto_commit_on:
        from specify_cli.coordination.commit_router import _resolve_planning_placement

        # map-requirements edits WP prompt files → WORK_PACKAGE_TASK (primary)
        # (write-surface-coherence WP02 / T009). Resolve the destination through
        # the kind authority instead of the hardcoded target_branch above.
        st.commit_target = _resolve_planning_placement(st.main_repo_root, st.mission_slug, kind=MissionArtifactKind.WORK_PACKAGE_TASK)
        protected_error = _tasks._protected_branch_status_commit_error(
            st.commit_target.ref,
            st.main_repo_root,
            "spec-kitty agent tasks map-requirements",
            st.mission_slug,
        )
        if protected_error is not None:
            _tasks._output_error(st.json_output, protected_error)
            raise typer.Exit(1)


def _mr_build_new_mappings(st: _MapReqState) -> None:
    """Phase C(i): build the per-WP new-mapping dict from the active input mode."""
    from specify_cli.cli.commands.agent import tasks as _tasks

    if st.batch:
        try:
            parsed_batch = json.loads(st.batch)
        except json.JSONDecodeError as exc:
            _tasks._output_error(st.json_output, f"Invalid JSON in --batch: {exc}")
            raise typer.Exit(1) from None
        if not isinstance(parsed_batch, dict):
            _tasks._output_error(st.json_output, "--batch must be a JSON object {WP_ID: [refs]}")
            raise typer.Exit(1)
        for wp_id, ref_list in parsed_batch.items():
            if not isinstance(ref_list, list) or not all(isinstance(ref, str) for ref in ref_list):
                _tasks._output_error(
                    st.json_output,
                    f"Refs for {wp_id} must be a list of strings",
                )
                raise typer.Exit(1)
            st.new_mappings[wp_id.upper()] = _canonical_input_refs(grammar.tokenize_refs(ref_list))
    elif st.tracker_only_mode:
        # Only --wp + --tracker-ref: no requirement refs to validate, but we still
        # register the WP key so the persistence loop visits it.
        assert st.wp is not None  # narrowed by tracker_only_mode
        st.new_mappings[st.wp.upper()] = []
    else:
        if st.wp is None or st.refs is None:
            _tasks._output_error(st.json_output, "Both --wp and --refs are required in individual mode.")
            raise typer.Exit(1)
        ref_list_parsed = grammar.tokenize_refs(st.refs)
        st.new_mappings[st.wp.upper()] = _canonical_input_refs(ref_list_parsed)


def _mr_unknown_wp_gate(st: _MapReqState) -> None:
    """Phase C(ii): reject WP ids the tasks/ dir does not carry."""
    from specify_cli.cli.commands.agent import tasks as _tasks

    existing_wps: set[str] = set()
    if st.tasks_dir.exists():
        for wp_file in st.tasks_dir.glob("WP*.md"):
            match = re.match(r"(WP\d{2})", wp_file.name)
            if match:
                existing_wps.add(match.group(1))

    unknown_wps = sorted(wp_id for wp_id in st.new_mappings if wp_id not in existing_wps)
    if not unknown_wps:
        return
    hint = f"Available WPs: {', '.join(sorted(existing_wps))}" if existing_wps else "No WP files found in tasks/"
    if st.json_output:
        render = _tasks.RealRender()
        print(
            render.json_envelope(
                {
                    "error": "Unknown WP IDs",
                    "unknown_wps": unknown_wps,
                    "hint": hint,
                }
            )
        )
    else:
        _tasks.console.print(f"[red]Error:[/red] Unknown WP IDs: {', '.join(unknown_wps)}")
        _tasks.console.print(f"  {hint}")
    raise typer.Exit(1)


def _mr_resolve_read_dirs(st: _MapReqState, ports: TasksPorts) -> None:
    """Phase C: resolve read dirs (fold via the FsReader port), parse spec ids, build mappings.

    T030: the co-located canonicalizer fold — ``primary_feature_dir_for_mission(
    _canonicalize_primary_read_handle(...))`` — routes through the WP02
    ``FsReader.primary_anchor_dir`` port (its named consumer per WP02 Note A); the
    blind primitive + the C-002 fold stay co-located INSIDE that adapter method.
    """
    from specify_cli.cli.commands.agent import tasks as _tasks
    from specify_cli.requirement_mapping import (
        find_undeclared_requirement_citations,
        parse_requirement_ids_from_spec_md,
    )

    # #2064: resolve the WP ``tasks/`` dir through the SAME seam finalize uses.
    st.feature_dir = _tasks._map_requirements_feature_dir(st.main_repo_root, st.mission_slug)
    # Boundary guard — hard-reject pre-3.0 layout before any WP mutation.
    try:
        check_pre30_layout(st.feature_dir)
    except Pre30LayoutError as e:
        _tasks._output_error(st.json_output, str(e))
        raise typer.Exit(1) from None
    # PRIMARY-input invariant: ``spec.md`` is authored on PRIMARY — unchanged.
    # FR-011 / T012: fold the handle to its canonical dir NAME first so a bare
    # mid8 / human slug resolves the durable ``<slug>-<mid8>`` home (ambiguous
    # handle RAISES — no silent pick, C-002). Routed through the port (T030).
    handle = MissionHandle(repo_root=st.main_repo_root, mission_slug=st.mission_slug)
    st.primary_dir = ports.fs.primary_anchor_dir(handle)

    if not st.feature_dir.exists():
        _tasks._output_error(st.json_output, f"Mission directory not found: {st.feature_dir}")
        raise typer.Exit(1)

    spec_md = st.primary_dir / _tasks.SPEC_MD_FILENAME
    if not spec_md.exists():
        _tasks._output_error(st.json_output, f"spec.md not found: {spec_md}")
        raise typer.Exit(1)

    spec_content = spec_md.read_text(encoding="utf-8")
    spec_ids = parse_requirement_ids_from_spec_md(spec_content)
    st.all_spec_ids = set(spec_ids["all"])
    st.functional_ids = set(spec_ids["functional"])
    # #3394 review F1: non-blocking signal, never a gate -- see _mr_emit_output.
    st.requirement_extraction_warnings = find_undeclared_requirement_citations(spec_content)
    # WP06 (#3396) T032a: stash the raw text for Phase D's bare-prose detector.
    st.spec_content = spec_content

    _mr_build_new_mappings(st)

    # #2107 / FR-004 (gate-read-surface-completion WP04): the WP ``tasks/*.md``
    # files are WORK_PACKAGE_TASK — a PRIMARY-partition kind. Resolve the read dir
    # through the kind-aware seam (the SAME single authority WP01 routed the rest
    # of the gate reads onto) instead of the topology-routed ``feature_dir``.
    st.tasks_dir = placement_seam(st.main_repo_root, st.mission_slug).read_dir(MissionArtifactKind.WORK_PACKAGE_TASK) / "tasks"
    _mr_unknown_wp_gate(st)


def _mr_detect_bare_prose_requirement_ids(spec_content: str) -> frozenset[str]:
    """WP06 (#3396) T032a fail-loud wrapper: bare-prose requirement-id
    detection for ``map-requirements``.

    Lives in the shell, never inside :func:`~.tasks_mapping_core.plan_mapping`
    (that core is pure/no-I/O, INV-4). Textually separate from the
    ``find_undeclared_requirement_citations`` advisory read a few lines above
    in ``_mr_resolve_read_dirs`` (that helper's "never fail the command"
    contract is the opposite of this one) -- any classification exception is
    caught ONCE and converted into an explicit, non-empty failure entry
    (mirroring WP05/T023's ``BareProseRequirementFacts.classification_error``
    contract) rather than silently reporting "0 uncounted" (NFR-002).
    """
    try:
        from specify_cli.requirement_mapping import find_bare_prose_requirement_ids

        candidates = find_bare_prose_requirement_ids(spec_content)
        return frozenset(req_id for candidate in candidates for req_id in candidate.ids)
    except Exception as exc:  # noqa: BLE001 -- fail-loud: converted below into an explicit, non-empty failure, never swallowed
        return frozenset({f"<bare-prose-detection-error: {exc!r} -- treating as blocking, never silently clean (NFR-002)>"})


def _mr_plan(st: _MapReqState) -> None:
    """Phase D: freeze the reads and run the pure WP04 ``plan_mapping`` core."""
    from specify_cli.cli.commands.agent import tasks as _tasks
    from specify_cli.requirement_mapping import read_all_wp_raw_requirement_refs

    # WP04 (FR-005 / FR-002), re-pointed by requirement-id-grammar-01M3NRCA WP03
    # (FR-005, T017): the merge base is now the RAW stored items (WP01's unified
    # raw reader, the same one finalize-tasks/the runtime classify) rather than
    # the normalising typed-frontmatter reader (deleted, zero product callers,
    # WP06 C6/F13) -- a letter-suffixed, SC, or foreign-qualified item survives
    # byte-identical instead of being silently dropped or respelled before
    # ``plan_mapping`` ever sees it. This
    # ONE read feeds BOTH the union-merge base and the coverage projection;
    # ``plan_mapping`` owns the FR↔WP mapping, new-ref verdicts, and coverage
    # decision.
    existing_all_refs = read_all_wp_raw_requirement_refs(st.tasks_dir)
    tasks_md_refs: dict[str, list[str]] = {}
    tasks_md_file = st.feature_dir / TASKS_MD_FILENAME
    if tasks_md_file.exists():
        from specify_cli.cli.commands.agent.mission import (
            _parse_requirement_refs_from_tasks_md,
        )

        tasks_md_refs = _parse_requirement_refs_from_tasks_md(tasks_md_file.read_text(encoding="utf-8"))

    if st.tracker_only_mode:
        _mapping_mode = TRACKER_ONLY_MODE
    elif st.batch:
        _mapping_mode = "batch"
    else:
        _mapping_mode = "wp_refs"
    bare_prose_requirement_ids = _mr_detect_bare_prose_requirement_ids(st.spec_content)
    st.mapping_plan = _tasks.plan_mapping(
        MappingRequest(
            spec_all_ids=frozenset(st.all_spec_ids),
            spec_functional_ids=frozenset(st.functional_ids),
            new_mappings=st.new_mappings,
            existing_all_refs=existing_all_refs,
            tasks_md_refs=tasks_md_refs,
            mode=_mapping_mode,
            replace=st.replace,
            bare_prose_requirement_ids=bare_prose_requirement_ids,
        )
    )


def _mr_gate_offenders(st: _MapReqState) -> None:
    """Phase D(ii): the PRE-write refusal gates driven by the core's offenders.

    Malformed FIRST, then unknown — the old inline validate_ref_format/validate_refs
    gate is deleted, not shadowed. Runs BEFORE the write loop, so a bad new ref
    refuses with NO write. ``foreign_qualified`` never reaches either arm — it
    is not an offender (FR-019).
    """
    from specify_cli.cli.commands.agent import tasks as _tasks

    assert st.mapping_plan is not None
    if st.mapping_plan.offenders.malformed:
        malformed = list(st.mapping_plan.offenders.malformed)
        parsed_spec_ids = _mr_sorted_spec_ids(st.all_spec_ids)
        payload = {
            "error": "Invalid requirement ref format",
            "malformed_refs": malformed,
            "parsed_spec_ids": parsed_spec_ids,
            "hint": _REQUIREMENT_ID_GRAMMAR_HINT,
        }
        if st.json_output:
            render = _tasks.RealRender()
            print(render.json_envelope(payload))
        else:
            _tasks.console.print(f"[red]Error:[/red] Invalid ref format: {', '.join(malformed)}")
            _tasks.console.print(f"  {_REQUIREMENT_ID_GRAMMAR_HINT}")
            _tasks.console.print(f"  Parsed spec IDs: {', '.join(parsed_spec_ids) or '(none)'}")
        raise typer.Exit(1)

    if st.mapping_plan.offenders.unknown_spec_id:
        unknown_refs = list(st.mapping_plan.offenders.unknown_spec_id)
        parsed_spec_ids = _mr_sorted_spec_ids(st.all_spec_ids)
        available_range = f"Available: {', '.join(parsed_spec_ids)}" if parsed_spec_ids else "No requirement IDs found in spec.md"
        payload = {
            "error": "Invalid requirement refs",
            "unknown_refs": sorted(set(unknown_refs)),
            "parsed_spec_ids": parsed_spec_ids,
            "hint": f"Refs not found in spec.md. {available_range}",
        }
        if st.json_output:
            render = _tasks.RealRender()
            print(render.json_envelope(payload))
        else:
            _tasks.console.print(f"[red]Error:[/red] Unknown refs: {', '.join(sorted(set(unknown_refs)))}")
            _tasks.console.print(f"  {available_range}")
        raise typer.Exit(1)


def _mr_write_frontmatter(st: _MapReqState) -> None:
    """Phase E: apply the core's ``to_write`` to WP frontmatter + emit the
    ``tracker_refs`` annotation (WP08 / FR-006).

    Fires BEFORE the post-write stale gate — partial-write-on-refusal timing is
    preserved (NFR-001/WP04). ``tracker_refs`` is no longer a frontmatter field
    (evicted to the event log): the merge semantics move onto WP01's reducer —
    this emits the *new* refs on the default (union) path, or the full
    replacement set via the dedicated ``tracker_refs_replace`` channel on
    ``--replace`` (never degraded to a union). No frontmatter read/write is
    involved in the tracker_refs path any more (C-002 typed delta).
    """
    from specify_cli.frontmatter import write_frontmatter
    from specify_cli.status import read_wp_frontmatter
    from specify_cli.status import emit_inner_state_changed
    from specify_cli.status import WPInnerStateDelta

    assert st.mapping_plan is not None
    for wp_id in st.new_mappings:
        wp_file = next((wp_file for wp_file in st.tasks_dir.glob(f"{wp_id}*.md")), None)
        if wp_file is None:
            continue

        wp_meta, body = read_wp_frontmatter(wp_file)
        update_kwargs: dict[str, list[str]] = {}

        # Only update requirement_refs when refs were supplied; preserves backward
        # compatibility for the tracker-only invocation. The merged value is the
        # pure core's ``to_write`` (WP04) — the inline replace/union is deleted.
        if not st.tracker_only_mode:
            update_kwargs["requirement_refs"] = st.mapping_plan.to_write[wp_id]

        if update_kwargs:
            updated_meta = wp_meta.update(**update_kwargs)
            write_frontmatter(wp_file, updated_meta.model_dump(exclude_none=True), body)

        # T030 / WP08 / FR-006: tracker_refs is event-sourced now. Emit the
        # delta instead of pre-merging a frontmatter read — the reducer owns
        # the union. ``--replace`` MUST route through WP01's dedicated
        # ``tracker_refs_replace`` channel (set-replace); it must never
        # degrade to a union emit (that would resurrect stale refs).
        if st.tracker_ref_values and st.wp is not None and wp_id == st.wp.upper():
            delta = (
                WPInnerStateDelta(tracker_refs_replace=sorted(set(st.tracker_ref_values)))
                if st.replace
                else WPInnerStateDelta(tracker_refs=list(st.tracker_ref_values))
            )
            # destination_ref/feature_dir resolves from the map-requirements
            # feature dir (``_map_requirements_feature_dir``, topology-based),
            # never Path.cwd() (C-003 / #2647).
            emit_inner_state_changed(
                st.feature_dir,
                wp_id,
                delta,
                actor=MAP_REQUIREMENTS_COMMAND_NAME,
                mission_slug=st.mission_slug,
                repo_root=st.main_repo_root,
            )


def _mr_classify_wp_refs(all_wp_raw: dict[str, list[str]], declared: set[str]) -> dict[str, dict[str, list[str]]]:
    """Classify every raw token per WP into the three rejection-reason buckets.

    Pure (no I/O): one :func:`grammar.classify` verdict per raw token.
    Returns ``{wp_id: {"malformed": [...], "unknown_spec_id": [...],
    "foreign_qualified": [...]}}`` — sorted, every WP present in *all_wp_raw*
    gets all three keys (empty lists where nothing offends), so the shell can
    both decide whether to refuse (``malformed``/``unknown_spec_id`` present
    ANYWHERE) and report the full partition (``foreign_qualified`` included)
    without a second pass. Kept a standalone helper (not folded into
    :func:`_mr_stale_gate`) to keep that phase at complexity <= 15.
    """
    result: dict[str, dict[str, list[str]]] = {}
    for wp_id, tokens in all_wp_raw.items():
        buckets: dict[str, list[str]] = {
            grammar.MALFORMED: [],
            grammar.UNKNOWN_SPEC_ID: [],
            grammar.FOREIGN_QUALIFIED: [],
        }
        for token in tokens:
            verdict = grammar.classify(token, declared)
            if isinstance(verdict, grammar.Rejected):
                buckets[verdict.reason].append(verdict.raw)
        for bucket in buckets.values():
            bucket.sort()
        result[wp_id] = buckets
    return result


def _mr_accepted_refs_by_wp(all_wp_raw: dict[str, list[str]], declared: set[str]) -> dict[str, list[str]]:
    """Per-WP ACCEPTED refs, canonical and sorted (FR-019 / #3396 C1).

    Companion to :func:`_mr_classify_wp_refs`: reads through the SAME raw
    tokens + grammar verdicts, but keeps only the ``Accepted`` leg, so a
    rejected ref (any reason) is never silently counted as a mapping. A WP
    with zero accepted refs is omitted, matching the pre-existing
    ``total_mappings`` shape (only WPs with refs are keyed).
    """
    result: dict[str, list[str]] = {}
    for wp_id, tokens in all_wp_raw.items():
        accepted = sorted({verdict.requirement_id.canonical for token in tokens if isinstance(verdict := grammar.classify(token, declared), grammar.Accepted)})
        if accepted:
            result[wp_id] = accepted
    return result


def _mr_stale_gate(st: _MapReqState) -> None:
    """Phase E(ii): post-write hard-fail on stale/invalid refs across ALL WPs.

    Runs AFTER the frontmatter write (original sequence position), so a pre-existing
    stale ref on an untouched WP still refuses (exit 1) with the partial write on
    disk — the exact partial-write-on-refusal behaviour WP04 preserved.

    Verdict table (FR-019): the gate refuses (exit 1) iff any rejected ref's
    reason is in ``grammar.FAILING_REASONS`` (malformed / unknown_spec_id). A
    WP set whose only rejected refs are ``foreign_qualified`` passes the
    stale gate silently — no payload is emitted at all.
    """
    from specify_cli.cli.commands.agent import tasks as _tasks
    from specify_cli.requirement_mapping import read_all_wp_raw_requirement_refs

    all_wp_raw = read_all_wp_raw_requirement_refs(st.tasks_dir)
    classified = _mr_classify_wp_refs(all_wp_raw, st.all_spec_ids)

    stale_refs: dict[str, list[str]] = {}
    stale_ref_reasons: dict[str, dict[str, list[str]]] = {}
    blocking = False
    for wp_id, reasons in classified.items():
        combined = sorted(reasons[grammar.MALFORMED] + reasons[grammar.UNKNOWN_SPEC_ID] + reasons[grammar.FOREIGN_QUALIFIED])
        if not combined:
            continue
        # A foreign_qualified citation is never stale (FR-019): it is a
        # valid cross-mission reference, not something --replace should
        # correct. Keep it visible in stale_ref_reasons (informational) but
        # never in stale_refs, whose "--replace to correct" hint invites
        # deleting it -- and never let a foreign-only WP set the gate.
        blocking_refs = sorted(reasons[grammar.MALFORMED] + reasons[grammar.UNKNOWN_SPEC_ID])
        if blocking_refs:
            stale_refs[wp_id] = blocking_refs
            blocking = True
        stale_ref_reasons[wp_id] = reasons

    if not blocking:
        return

    parsed_spec_ids = _mr_sorted_spec_ids(st.all_spec_ids)
    payload = {
        "error": "Stale or invalid refs in WP frontmatter",
        "stale_refs": stale_refs,
        "stale_ref_reasons": stale_ref_reasons,
        "parsed_spec_ids": parsed_spec_ids,
        "hint": _STALE_REFS_HINT,
    }
    if st.json_output:
        render = _tasks.RealRender()
        print(render.json_envelope(payload))
    else:
        _tasks.console.print("[red]Error:[/red] Stale or invalid refs in WP frontmatter:")
        _tasks.console.print(f"  {_REQUIREMENT_ID_GRAMMAR_HINT}")
        for wp_id, bad_refs in sorted(stale_refs.items()):
            _tasks.console.print(f"  {wp_id}: {', '.join(bad_refs)}")
        _tasks.console.print(f"  Parsed spec IDs: {', '.join(parsed_spec_ids) or '(none)'}")
        _tasks.console.print("  Use --replace to correct mappings")
    raise typer.Exit(1)


def _mr_auto_commit(st: _MapReqState, ports: TasksPorts) -> None:
    """Phase F(i): route the WP-file auto-commit through the WP02 ``commit_artifact`` port.

    map-requirements edits WP prompt files → WORK_PACKAGE_TASK (a primary kind,
    write-surface-coherence WP03 / T014). The coord router carries the resolved
    ``target_branch`` so the WP09 ff-advance fires for a coord write; the ``--json``
    ``commit_result`` envelope shape (#1891 / FR-013) is reconstructed byte-identically.
    """
    from specify_cli.cli.commands.agent import tasks as _tasks

    if not st.auto_commit_on:
        return
    written_files: list[Path] = []
    for wp_id in st.new_mappings:
        wp_file = next((f for f in st.tasks_dir.glob(f"{wp_id}*.md")), None)
        if wp_file is not None:
            written_files.append(wp_file.resolve())
    if not written_files:
        return
    spec_number = st.mission_slug.split("-")[0] if "-" in st.mission_slug else st.mission_slug
    commit_msg = f"chore: Map requirements for {', '.join(sorted(st.new_mappings))} on spec {spec_number}"
    handle = MissionHandle(repo_root=st.main_repo_root, mission_slug=st.mission_slug)
    try:
        _router_result = ports.coord.commit_artifact(
            handle,
            tuple(written_files),
            commit_msg,
            kind=MissionArtifactKind.WORK_PACKAGE_TASK,
            policy=_tasks.ProtectionPolicy.resolve(st.main_repo_root),
        )
        if _router_result.status == "committed":
            st.committed = True
            st.commit_sha = _router_result.commit_hash
            st.commit_result_payload = {
                "sha": _router_result.commit_hash or "",
                "destination_ref": _router_result.placement_ref,
                "worktree_root": str(st.main_repo_root),
            }
    except Exception as exc_commit:
        if not st.json_output:
            _tasks.console.print(f"[yellow]Warning:[/yellow] Auto-commit skipped: {exc_commit}")


def _mr_emit_output(st: _MapReqState) -> None:
    """Phase F(ii): reconstruct coverage from the core + emit the success envelope."""
    from specify_cli.cli.commands.agent import tasks as _tasks
    from specify_cli.requirement_mapping import read_all_wp_raw_requirement_refs

    assert st.mapping_plan is not None
    # ``total_mappings`` reflects the post-write disk state. requirement-id-
    # grammar-01M3NRCA WP03 (C1): re-pointed from the normalising reader to
    # the RAW reader + ``grammar.classify`` (:func:`_mr_accepted_refs_by_wp`),
    # so a rejected ref is never silently dropped from the coverage view --
    # by the time this phase runs the stale gate has already refused on any
    # failing (malformed/unknown) ref, and a ``foreign_qualified`` ref is
    # correctly excluded (it is not this mission's own mapping). The coverage
    # summary is reconstructed from the core's ``unmapped_fr``: every
    # functional FR is either mapped or unmapped, so ``mapped = total - len(unmapped)``
    # is byte-identical to ``compute_coverage`` over the post-write state (WP04).
    all_wp_raw = read_all_wp_raw_requirement_refs(st.tasks_dir)
    all_wp_refs = _mr_accepted_refs_by_wp(all_wp_raw, st.all_spec_ids)
    coverage: CoverageSummary = {
        "total_functional": len(st.functional_ids),
        "mapped_functional": len(st.functional_ids) - len(st.mapping_plan.unmapped_fr),
        "unmapped_functional": st.mapping_plan.unmapped_fr,
    }
    st.coverage = coverage

    payload = {
        "result": "success",
        **_tasks._mission_identity_payload(st.primary_dir),
        "mapped": {wp_id: sorted(refs) for wp_id, refs in st.new_mappings.items()},
        "total_mappings": {wp_id: sorted(refs) for wp_id, refs in all_wp_refs.items() if refs},
        "coverage": coverage,
        "committed": st.committed,
        "commit_sha": st.commit_sha,
        "commit_result": st.commit_result_payload,
        "requirement_extraction_warnings": st.requirement_extraction_warnings,
        # WP06 (#3396) T032: distinct, separately-labeled signal -- never
        # merged into ``coverage.unmapped_functional`` (Story 1 / FR-001 / FR-004).
        "bare_prose_requirement_ids": st.mapping_plan.bare_prose_requirement_ids,
    }
    if st.replace:
        # requirement-id-grammar-01M3NRCA WP03 (FR-005): additive, ``--replace``-
        # only key -- the default-mode ``map_requirements_success`` byte
        # contract must not move (NFR-002).
        payload["replaced_refs_removed"] = st.mapping_plan.replaced_refs_removed
    if st.json_output:
        render = _tasks.RealRender()
        print(render.json_envelope(payload))
    else:
        _tasks.console.print("[green]✓[/green] Requirement mappings saved")
        for wp_id, ref_list in sorted(st.new_mappings.items()):
            _tasks.console.print(f"  {wp_id}: {', '.join(ref_list)}")
        _tasks.console.print(f"\n  Coverage: {coverage['mapped_functional']}/{coverage['total_functional']} FRs mapped")
        if coverage["unmapped_functional"]:
            _tasks.console.print(f"  [yellow]Unmapped:[/yellow] {', '.join(coverage['unmapped_functional'])}")
        if st.committed:
            _tasks.console.print("[cyan]→ Committed mapping changes[/cyan]")
        if st.replace:
            for wp_id, removed in sorted(st.mapping_plan.replaced_refs_removed.items()):
                if removed:
                    _tasks.console.print(f"  Removed by --replace: {wp_id}: {', '.join(removed)}")
        for warning in st.requirement_extraction_warnings:
            _tasks.console.print(f"[yellow]Warning:[/yellow] {warning}")
        if st.mapping_plan.bare_prose_requirement_ids:
            _tasks.console.print(f"  [red]Bare-prose requirement id(s) found, uncounted:[/red] {', '.join(st.mapping_plan.bare_prose_requirement_ids)}")


def _do_map_requirements(
    wp: str | None,
    refs: str | None,
    batch: str | None,
    replace: bool,
    tracker_ref: list[str] | None,
    mission: str | None,
    json_output: bool,
    auto_commit: bool | None,
    *,
    ports: TasksPorts | None = None,
) -> None:
    """Orchestrate ``map-requirements`` over the WP04 core + WP02 ports (C-005 seam).

    ``ports=None`` builds the production bundle AFTER ``target_branch`` resolves
    (the coord router threads it for the ff-advance). Tests inject a Fake bundle to
    observe the executed side-effects (T032). The phase helpers run in the SAME
    order as the original single body: validate → resolve → plan → write → stale
    gate → finalize — so the frontmatter write still precedes the post-write stale
    gate (partial-write-on-refusal timing, NFR-001/WP04).
    """
    from specify_cli.cli.commands.agent import tasks as _tasks

    st = _MapReqState(
        wp=wp,
        refs=refs,
        batch=batch,
        replace=replace,
        tracker_ref=tracker_ref,
        mission=mission,
        json_output=json_output,
        auto_commit=auto_commit,
    )
    try:
        _mr_validate_modes(st)
        _mr_resolve_context(st)
        ports = ports or _default_map_requirements_ports(st.target_branch)
        _mr_resolve_read_dirs(st, ports)
        _mr_plan(st)
        _mr_gate_offenders(st)
        _mr_write_frontmatter(st)
        _mr_stale_gate(st)
        _mr_auto_commit(st, ports)
        _mr_emit_output(st)
    except typer.Exit:
        raise
    except Exception as exc:
        _tasks._output_error(json_output, str(exc))
        raise typer.Exit(1) from None


# ===========================================================================
# WP09 (tasks-py-degod-wave2-01KWH9EQ / FR-008, IC-07): the final
# registration-shim sweep relocates the map_requirements-family straggler that
# remained ``tasks.py``-resident after WP06 — the kind-aware ``tasks/`` read
# resolver (``_map_requirements_feature_dir``). Moved VERBATIM
# (``resolve_planning_read_dir`` / ``MissionArtifactKind`` are module-scope
# imports here already; neither is a ``tasks``-namespace patch seam). The
# ``_mr_resolve_read_dirs`` call site above keeps routing through
# ``_tasks.<attr>``, so the pre30-guard-wiring / read-surface
# ``@patch("...agent.tasks._map_requirements_feature_dir")`` contracts keep
# INTERCEPTING; ``tasks.py`` re-imports the name in the explicit ``as``
# re-export form (NFR-002).
# ===========================================================================


def _map_requirements_feature_dir(main_repo_root: Path, mission_slug: str) -> Path:
    """Resolve the WP ``tasks/`` read surface for ``map-requirements`` (#2064).

    Routes through ``PlacementSeam.read_dir(WORK_PACKAGE_TASK)`` — the
    per-leg seam split (WP03 / FR-001 / C-001): the WP-frontmatter read always
    lands on the PRIMARY checkout regardless of topology (INV-5 symmetry), so a
    coord-topology mission no longer routes to the STATUS-only coord husk for this
    planning-artifact read.

    ``PlacementSeam.read_dir(WORK_PACKAGE_TASK)`` selects the PRIMARY partition,
    preserving the user-facing contract that ``map-requirements`` surfaces its own
    ``"Mission directory not found: …"`` message via the caller's existence guard
    on the returned path (Risk #1 — unchanged user-facing behaviour).
    """
    # WP03 / FR-001 / C-001: tasks/ is WORK_PACKAGE_TASK (PRIMARY-partition).
    # The topology-blind primary_feature_dir_for_mission never raises, so the
    # caller's existence guard preserves the historical user-facing contract.
    resolved: Path = placement_seam(main_repo_root, mission_slug).read_dir(MissionArtifactKind.WORK_PACKAGE_TASK)
    return resolved
