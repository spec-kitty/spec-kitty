package kitty.acceptance.steps;

import static org.assertj.core.api.Assertions.assertThat;

import io.cucumber.java.en.Then;

import kitty.acceptance.driver.CliResult;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Optional;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Stream;

/** Assert ({@code Then}): check that the post-conditions hold after the action. */
public final class AssertSteps {

    private static final Pattern MISSION_SLUG = Pattern.compile("\"mission_slug\"\\s*:\\s*\"([^\"]+)\"");

    private final ScenarioContext context;

    public AssertSteps(ScenarioContext context) {
        this.context = context;
    }

    @Then("the command succeeds")
    public void theCommandSucceeds() {
        CliResult result = context.lastResult();
        assertThat(result.exitCode()).as("Exit code of the command:%n%s", result).isZero();
    }

    @Then("the command fails")
    public void theCommandFails() {
        CliResult result = context.lastResult();
        assertThat(result.exitCode()).as("Exit code of the command:%n%s", result).isNotZero();
    }

    @Then("the mission {string} is listed")
    public void theMissionIsListed(String handle) {
        assertThat(listedMissionSlug()).as("Mission listed by the status command").isPresent()
                .hasValueSatisfying(slug -> assertThat(isMission(slug, handle))
                        .as("Listed mission '%s' is the mission '%s'", slug, handle).isTrue());
    }

    @Then("the mission {string} is not listed")
    public void theMissionIsNotListed(String handle) {
        assertThat(listedMissionSlug().filter(slug -> isMission(slug, handle)))
                .as("Mission '%s' in the output of the status command", handle)
                .isEmpty();
    }

    /** The CLI appends an identifier to the slug it is given, so a mission matches its name or name-plus-suffix. */
    private static boolean isMission(String listedSlug, String handle) {
        return listedSlug.matches(Pattern.quote(handle) + "(-[0-9A-Z]{8})?");
    }

    private Optional<String> listedMissionSlug() {
        Matcher matcher = MISSION_SLUG.matcher(context.lastResult().stdout());
        return matcher.find() ? Optional.of(matcher.group(1)) : Optional.empty();
    }

    @Then("the folder {string} exists")
    public void theFolderExists(String relative) {
        assertThat(context.world().resolve(relative)).as("Folder '%s'", relative).isDirectory();
    }

    @Then("the folder {string} is not empty")
    public void theFolderIsNotEmpty(String relative) {
        Path folder = context.world().resolve(relative);
        assertThat(folder).as("Folder '%s'", relative).isDirectory();
        try (Stream<Path> entries = Files.list(folder)) {
            assertThat(entries.findAny()).as("Contents of folder '%s'", relative).isPresent();
        } catch (IOException e) {
            throw new UncheckedIOException("Could not list " + folder, e);
        }
    }

    @Then("the folder {string} is unchanged")
    public void theFolderIsUnchanged(String relative) {
        assertUnchanged("Folder", relative);
    }

    @Then("the file {string} is unchanged")
    public void theFileIsUnchanged(String relative) {
        assertUnchanged("File", relative);
    }

    @Then("no {string} folder exists in {string}")
    public void noFolderExistsIn(String name, String parent) {
        Path parentDir = context.world().resolve(parent);
        assertThat(parentDir).as("Parent folder '%s'", parent).isDirectory();
        assertThat(parentDir.resolve(name)).as("'%s' in '%s'", name, parent).doesNotExist();
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

    private void assertUnchanged(String kind, String relative) {
        assertThat(context.world().isUnchanged(relative))
                .as("%s '%s' is unchanged since it was recorded", kind, relative)
                .isTrue();
    }
}
