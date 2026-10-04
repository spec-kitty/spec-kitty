# Contracts — move-task-executor-seam

This mission adds no new external or CLI contract. The one contract it preserves is the internal compat surface: every symbol that moved out of `tasks_move_task` still resolves by identity as `tasks_move_task.<name>` and `tasks.<name>`. That guarantee is pinned by `tests/specify_cli/cli/commands/agent/test_tasks_compat_surface.py` and `test_tasks_move_task_seams.py`.

The one new internal seam is `specify_cli.coordination.status_transition.emit_runtime_annotation(*, owned, auto_commit, operation=None, **emit_kwargs)`. It picks an emitter in this order:

1. `owned` set: the transactional emitter, called with `owned=` and `operation=`.
2. Otherwise, `auto_commit` truthy: the transactional emitter.
3. Otherwise: the plain `specify_cli.status.emit_inner_state_changed`. It receives neither `operation` nor `owned`.
