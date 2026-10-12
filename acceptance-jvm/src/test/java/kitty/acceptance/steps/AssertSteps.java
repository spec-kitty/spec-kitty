package kitty.acceptance.steps;

import static org.assertj.core.api.Assertions.assertThat;

import io.cucumber.java.en.Then;

import kitty.acceptance.driver.CliResult;

/** Assert ({@code Then}): check that the post-conditions hold after the action. */
public final class AssertSteps {

    private final ScenarioContext context;

    public AssertSteps(ScenarioContext context) {
        this.context = context;
    }

    @Then("the command succeeds")
    public void theCommandSucceeds() {
        CliResult result = context.lastResult();
        assertThat(result.exitCode()).as("Exit code of the command:%n%s", result).isZero();
    }

    @Then("the folder {string} exists")
    public void theFolderExists(String relative) {
        assertThat(context.world().resolve(relative)).as("Folder '%s'", relative).isDirectory();
    }

    @Then("the folder {string} is unchanged")
    public void theFolderIsUnchanged(String relative) {
        assertThat(context.world().isUnchanged(relative))
                .as("Folder '%s' is unchanged since it was recorded", relative)
                .isTrue();
    }

    @Then("the file {string} is unchanged")
    public void theFileIsUnchanged(String relative) {
        assertThat(context.world().isUnchanged(relative))
                .as("File '%s' is unchanged since it was recorded", relative)
                .isTrue();
    }

    @Then("no {string} folder exists in {string}")
    public void noFolderExistsIn(String name, String parent) {
        assertThat(context.world().resolve(parent).resolve(name))
                .as("'%s' in '%s'", name, parent)
                .doesNotExist();
    }

    @Then("the repository HEAD is unchanged")
    public void theRepositoryHeadIsUnchanged() {
        assertThat(context.world().headUnchanged()).as("HEAD is unchanged since it was recorded").isTrue();
    }

    @Then("the repository has no new commits")
    public void theRepositoryHasNoNewCommits() {
        assertThat(context.world().commitCountUnchanged())
                .as("Commit count is unchanged since it was recorded")
                .isTrue();
    }
}
