package kitty.acceptance.steps;

import kitty.acceptance.driver.CliProcessDriver;
import kitty.acceptance.driver.CliResult;
import kitty.acceptance.driver.SpecKittyDriver;
import kitty.acceptance.environment.CliUnderTest;
import kitty.acceptance.environment.ScenarioWorld;

import java.util.List;

/**
 * The state one scenario shares across its Arrange, Assume, Act and Assert step classes.
 *
 * <p>Cucumber's PicoContainer integration creates one instance per scenario and injects it into
 * every step class that asks for it, so the step classes never hold state of their own. Every
 * interaction with the CLI goes through the {@link SpecKittyDriver} port (constraint C-001):
 * steps inspect files, exit codes and git state, never Python internals.
 */
public final class ScenarioContext {

    private final ScenarioWorld world;
    private final SpecKittyDriver driver;
    private CliResult lastResult;

    public ScenarioContext() {
        world = ScenarioWorld.create(CliUnderTest.instance());
        driver = new CliProcessDriver(world.commandResolver(), world.environment());
    }

    ScenarioWorld world() {
        return world;
    }

    /** Runs a CLI command in the scenario's working directory and records that it ran. */
    CliResult run(List<String> args) {
        CliResult result = driver.run(args, world.workDir());
        world.markCommandObserved();
        return result;
    }

    void recordResult(CliResult result) {
        lastResult = result;
    }

    CliResult lastResult() {
        if (lastResult == null) {
            throw new IllegalStateException("No command has been run yet in this scenario");
        }
        return lastResult;
    }
}
