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

    /**
     * The reviewer's rejection of a work package that is already approved. The approval row is planted
     * as a teammate's clock-skewed pull delivers it, then the rejection goes through the real CLI.
     */
    @When("a reviewer records a rejection of {string} after that approval")
    public void aReviewerRecordsARejectionAfterTheApproval(String wp) {
        context.rejectAfterApproval(wp);
    }

    /** The user consolidates the Mission whose work package a reviewer has just sent back. */
    @When("I consolidate the Mission")
    public void iConsolidateTheMission() {
        context.consolidateMission();
    }
}
