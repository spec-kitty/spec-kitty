# Contracts

This mission adds no external contract. The change is confined to the JVM acceptance harness
(`acceptance-jvm/src/test/java/.../RealHomeFingerprint.java` and `ScenarioLifecycle.java`), one
documentation page and one changelog fragment: no CLI surface, no request/response shape, no file
format and no environment variable that another process consumes. The switch it introduces
(`SPEC_KITTY_ACCEPTANCE_SHARED_HOST`) is read by the harness itself and documented on
`docs/development/testing/acceptance-scenarios.md`; it is described by `plan.md` (D-2) rather than
by a contract fixture.
