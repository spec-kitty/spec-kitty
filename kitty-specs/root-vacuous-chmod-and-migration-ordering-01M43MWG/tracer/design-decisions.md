# design-decisions

1. The history-db seam is `Path.mkdir` on the db parent, wrapped by a `_connect` spy. The spy is what makes the test non-vacuous: without it, a runner that skips recording also "returns normally".
2. The `_atomic_write` tests are retargeted rather than deleted. The mkstemp hook was already dead, because `NamedTemporaryFile` never calls `tempfile.mkstemp`.
3. `TestOrdering` gets a class-scoped autouse `auto_discover_migrations()` fixture, not a module import, because other tests call `MigrationRegistry.clear()`.
