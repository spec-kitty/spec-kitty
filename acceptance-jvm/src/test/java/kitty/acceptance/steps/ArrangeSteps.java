package kitty.acceptance.steps;

import static org.assertj.core.api.Assertions.assertThat;

import io.cucumber.java.en.Given;

import kitty.acceptance.driver.CliResult;
import kitty.acceptance.environment.MissionFixture;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Comparator;
import java.util.List;
import java.util.stream.Stream;

/**
 * Arrange ({@code Given}): build the scenario's starting conditions, and fail fast when building
 * them did not work, so a broken fixture never reads as a product failure.
 */
public final class ArrangeSteps {

    private final ScenarioContext context;
    private MissionFixture missions;

    public ArrangeSteps(ScenarioContext context) {
        this.context = context;
    }

    @Given("a project already set up with Spec Kitty for the agents {string}")
    public void aProjectAlreadySetUpForTheAgents(String agents) {
        CliResult result = context.run(List.of("spec-kitty", "init", "--non-interactive", "--ai", agents));
        assertThat(result.exitCode())
                .as("Setting up the project with 'spec-kitty init' failed:%n%s", result)
                .isZero();
    }

    @Given("an existing git repository with commit history")
    public void anExistingGitRepositoryWithCommitHistory() {
        context.world().initGitRepoWithCommit();
    }

    @Given("a project with a mission {string}")
    public void aProjectWithAMission(String slug) {
        missions().createMission(slug);
    }

    @Given("the project also has a mission {string}")
    public void theProjectAlsoHasAMission(String slug) {
        missions().createMission(slug);
    }

    @Given("the status of the mission {string} can be read")
    public void theStatusOfTheMissionCanBeRead(String slug) {
        CliResult result = context.run(List.of("spec-kitty", "agent", "tasks", "status", "--mission", slug, "--json"));
        assertThat(result.exitCode())
                .as("Reading the status of mission '%s' before the action:%n%s", slug, result)
                .isZero();
    }

    private MissionFixture missions() {
        if (missions == null) {
            missions = new MissionFixture(context.world().workDir(), context.world().environment(),
                    context.world()::initGitRepoWithCommit, context::run);
        }
        return missions;
    }

    @Given("the folder {string} has been deleted")
    public void theFolderHasBeenDeleted(String relative) {
        Path target = context.world().resolve(relative);
        assertThat(target).as("The folder to delete").isDirectory();
        deleteRecursively(target);
        assertThat(target).as("The folder after deleting it").doesNotExist();
    }

    private static void deleteRecursively(Path root) {
        try (Stream<Path> tree = Files.walk(root)) {
            tree.sorted(Comparator.reverseOrder()).forEach(ArrangeSteps::delete);
        } catch (IOException e) {
            throw new UncheckedIOException("Could not delete " + root, e);
        }
    }

    private static void delete(Path path) {
        try {
            // spec-kitty installs its managed skill files read-only. Windows refuses to
            // delete a read-only file, so clear the flag first, as a user's rm -rf would.
            path.toFile().setWritable(true);
            Files.deleteIfExists(path);
        } catch (IOException e) {
            throw new UncheckedIOException("Could not delete " + path, e);
        }
    }
}
