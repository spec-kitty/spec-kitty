package kitty.acceptance.steps;

import io.cucumber.java.After;

/** Scenario lifecycle hooks: verify isolation held, then remove the scenario's temp dir. */
public final class ScenarioHooks {

    private final ScenarioContext context;

    public ScenarioHooks(ScenarioContext context) {
        this.context = context;
    }

    @After
    public void tearDown() {
        try {
            context.world().assertObservedWriteInsideTempDir();
        } finally {
            context.world().cleanUp();
        }
    }
}
