package kitty.acceptance.steps;

import static org.assertj.core.api.Assertions.assertThat;

import io.cucumber.java.en.Given;

import kitty.acceptance.driver.CliResult;
import kitty.acceptance.environment.MissionFixture;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.Comparator;
import java.util.List;
import java.util.stream.Stream;

/**
 * Arrange ({@code Given}): build the scenario's starting conditions, and fail fast when building
 * them did not work, so a broken fixture never reads as a product failure.
 */
public final class ArrangeSteps {

    private final ScenarioContext context;

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

    @Given("a project set up with Spec Kitty whose files are committed")
    public void aProjectSetUpWithSpecKittyWhoseFilesAreCommitted() {
        missions().ensureProject();
    }

    @Given("sparse-checkout is turned on in the project for {string}")
    public void sparseCheckoutIsTurnedOnFor(String patterns) {
        context.world().enableLegacySparseCheckout(Arrays.stream(patterns.split(","))
                .map(String::trim).filter(pattern -> !pattern.isEmpty()).toList());
        assertThat(context.world().gitSetting("core.sparseCheckout"))
                .as("core.sparseCheckout after turning sparse-checkout on").isEqualTo("true");
    }

    @Given("the project has a linked worktree {string} with sparse-checkout turned on")
    public void theProjectHasALinkedWorktreeWithSparseCheckout(String relative) {
        context.world().addSparseWorktree(relative);
        assertThat(context.world().resolve(relative)).as("Linked worktree '%s'", relative).isDirectory();
    }

    @Given("I have a git merge in progress with a conflict in {string}")
    public void iHaveAGitMergeInProgressWithAConflictIn(String file) {
        context.world().startConflictingMerge(file);
        assertThat(context.world().mergeInProgress()).as("A git merge is in progress").isTrue();
    }

    @Given("every change in the project is committed")
    public void everyChangeInTheProjectIsCommitted() {
        context.world().commitEverything("commit the project as it is");
        assertThat(context.world().uncommittedChanges()).as("Uncommitted changes after committing everything").isEmpty();
    }

    @Given("a mission {string} planned on a topic branch with the work packages {string}")
    public void aMissionPlannedOnATopicBranch(String name, String workPackages) {
        context.lifecycle().planMission(name, list(workPackages));
    }

    @Given("a single-branch mission {string} planned on a topic branch with the work packages {string}")
    public void aSingleBranchMissionOnATopicBranch(String name, String workPackages) {
        context.lifecycle().planSingleBranchMission(name, list(workPackages), false);
    }

    @Given("a single-branch mission {string} planned for the primary branch with the work packages {string}")
    public void aSingleBranchMissionForThePrimaryBranch(String name, String workPackages) {
        context.lifecycle().planSingleBranchMission(name, list(workPackages), true);
        assertThat(context.world().git("rev-parse", "--abbrev-ref", "HEAD").trim())
                .as("Checked-out branch after creating mission '%s'", name).isEqualTo(context.lifecycle().missionBranch(name));
    }

    @Given("the file {string} is committed with the text {string}")
    public void theFileIsCommittedWithTheText(String relative, String text) {
        writeInRepository(relative, text);
        context.world().git("add", "--", relative);
        context.world().git("commit", "-m", "edit " + relative);
    }

    @Given("the file {string} has the uncommitted text {string}")
    public void theFileHasTheUncommittedText(String relative, String text) {
        writeInRepository(relative, text);
    }

    private void writeInRepository(String relative, String text) {
        Path file = context.world().resolve(relative);
        try {
            Files.createDirectories(file.getParent());
            Files.writeString(file, text + "\n");
        } catch (IOException e) {
            throw new UncheckedIOException("Could not write " + file, e);
        }
    }

    private static List<String> list(String commaSeparated) {
        return Arrays.stream(commaSeparated.split(",")).map(String::trim).filter(item -> !item.isEmpty()).toList();
    }

    @Given("a mission {string} on a topic branch whose spec is written and committed")
    public void aMissionWhoseSpecIsWrittenAndCommitted(String name) {
        context.lifecycle().specifyMission(name);
    }

    @Given("the work package {string} of mission {string} has been moved to lane {string}")
    public void theWorkPackageIsInLane(String wp, String name, String lane) {
        context.lifecycle().advance(name, wp, lane);
        CliResult status = context.run(List.of("spec-kitty", "agent", "tasks", "status", "--mission",
                context.lifecycle().slug(name), "--json"));
        assertThat(status.stdout()).as("Status after moving %s to %s:%n%s", wp, lane, status)
                .containsPattern("\"id\"\\s*:\\s*\"" + wp + "\"[^}]*\"lane\"\\s*:\\s*\"" + lane + "\"");
    }

    @Given("the work package {string} of mission {string} has been rejected with the feedback {string}")
    public void theWorkPackageHasBeenRejected(String wp, String name, String feedback) {
        context.lifecycle().reject(name, wp, feedback);
    }

    @Given("the review feedback file {string} says {string}")
    public void theReviewFeedbackFileSays(String relative, String text) {
        writeOutsideRepository(relative, "# Review feedback\n\n" + text + "\n");
    }

    @Given("an empty review feedback file {string}")
    public void anEmptyReviewFeedbackFile(String relative) {
        writeOutsideRepository(relative, "");
    }

    /** A reviewer's notes live outside the repository, so writing them never dirties the working tree. */
    private void writeOutsideRepository(String relative, String content) {
        Path file = context.world().resolve(relative).normalize();
        assertThat(file.startsWith(context.world().workDir())).as("Feedback file '%s' is outside the repository", relative).isFalse();
        try {
            Files.writeString(file, content);
        } catch (IOException e) {
            throw new UncheckedIOException("Could not write " + file, e);
        }
    }

    @Given("the mission {string} has been accepted")
    public void theMissionHasBeenAccepted(String name) {
        context.lifecycle().accept(name);
    }

    @Given("the subtasks of the work package {string} of mission {string} are marked done")
    public void theSubtasksAreMarkedDone(String wp, String name) {
        context.lifecycle().markSubtasksDone(name, wp);
    }

    @Given("the work package {string} of mission {string} has committed its work")
    public void theWorkPackageHasCommittedItsWork(String wp, String name) {
        context.lifecycle().commitWork(name, wp);
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
        return context.missions();
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
