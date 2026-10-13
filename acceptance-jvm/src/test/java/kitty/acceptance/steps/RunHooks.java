package kitty.acceptance.steps;

import io.cucumber.java.BeforeAll;
import kitty.acceptance.environment.CliUnderTest;
import kitty.acceptance.environment.RunMetadata;

/** Run-level hook: stamps the pass's Allure results with the build under test, once per JVM. */
public final class RunHooks {

    private RunHooks() {
    }

    /** Runs before the first scenario; {@link RunMetadata#write} is idempotent. */
    @BeforeAll
    public static void stampRunMetadata() {
        RunMetadata.write(CliUnderTest.instance());
    }
}
