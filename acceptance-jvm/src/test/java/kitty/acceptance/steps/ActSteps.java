package kitty.acceptance.steps;

import io.cucumber.java.en.When;

import java.util.Arrays;

/** Act ({@code When}): run the CLI command whose outcome the scenario verifies. */
public final class ActSteps {

    private final ScenarioContext context;

    public ActSteps(ScenarioContext context) {
        this.context = context;
    }

    @When("I run {string}")
    public void iRun(String commandLine) {
        context.recordResult(context.run(Arrays.stream(commandLine.trim().split("\\s+")).toList()));
    }
}
