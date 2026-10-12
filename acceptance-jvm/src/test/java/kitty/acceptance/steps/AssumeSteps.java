package kitty.acceptance.steps;

import static org.assertj.core.api.Assertions.assertThat;

import io.cucumber.java.en.Given;

import java.nio.file.Path;

/**
 * Assume ({@code Given}/{@code And}): check that the arranged starting state is what the scenario
 * expects, and record it so the Assert steps can compare against it afterwards.
 */
public final class AssumeSteps {

    private final ScenarioContext context;

    public AssumeSteps(ScenarioContext context) {
        this.context = context;
    }

    @Given("the folder {string} is present")
    public void theFolderIsPresent(String relative) {
        Path folder = context.world().resolve(relative);
        assertThat(folder).as("Folder '%s' before the action", relative).isDirectory();
        context.world().recordState(relative);
    }

    @Given("the file {string} is present")
    public void theFileIsPresent(String relative) {
        Path file = context.world().resolve(relative);
        assertThat(file).as("File '%s' before the action", relative).isRegularFile();
        context.world().recordState(relative);
    }

    @Given("the repository has at least one commit")
    public void theRepositoryHasAtLeastOneCommit() {
        assertThat(context.world().recordRepoState()).as("Commits in the repository").isPositive();
    }
}
