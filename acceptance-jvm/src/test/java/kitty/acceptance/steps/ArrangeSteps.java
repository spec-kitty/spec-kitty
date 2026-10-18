package kitty.acceptance.steps;

import static org.assertj.core.api.Assertions.assertThat;

import io.cucumber.java.en.Given;

import kitty.acceptance.driver.CliResult;
import kitty.acceptance.environment.MissionFixture;
import kitty.acceptance.environment.MissionLifecycle;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
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

    @Given("a lanes mission {string} planned on a topic branch with the work packages {string}")
    public void aLanesMissionPlannedOnATopicBranch(String name, String workPackages) {
        context.lifecycle().planMission(name, list(workPackages), List.of("--topology", "lanes"));
    }

    @Given("the work package {string} of mission {string} is amended to build on {string}")
    public void theWorkPackageIsAmendedToBuildOn(String joiner, String name, String owner) {
        context.lifecycle().amendToJoin(name, joiner, owner);
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

    @Given("a project set up with Spec Kitty on the topic branch {string}")
    public void aProjectOnTheTopicBranch(String branch) {
        assertThat(branch).as("The topic branch the builders use").isEqualTo(MissionLifecycle.TOPIC_BRANCH);
        context.lifecycle().useTopicBranch();
    }

    @Given("a mission {string} created on a topic branch")
    public void aMissionCreatedOnATopicBranch(String name) {
        context.lifecycle().createMission(name);
    }

    @Given("the spec of mission {string} is written but not committed")
    public void theSpecIsWrittenButNotCommitted(String name) {
        context.lifecycle().writeSpec(name, false);
    }

    @Given("the spec of mission {string} is committed as it was scaffolded")
    public void theSpecIsCommittedAsScaffolded(String name) {
        context.lifecycle().commitAsCreated(name);
    }

    @Given("the plan of mission {string} is written")
    public void thePlanIsWritten(String name) {
        context.lifecycle().writePlan(name);
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

    @Given("the charter interview has been answered with its defaults")
    public void theCharterInterviewHasBeenAnsweredWithItsDefaults() {
        succeed(List.of("spec-kitty", "charter", "interview", "--defaults", "--profile", "minimal", "--json"),
                "Answering the charter interview with its defaults");
    }

    @Given("a charter has been generated from the interview")
    public void aCharterHasBeenGeneratedFromTheInterview() {
        succeed(List.of("spec-kitty", "charter", "generate", "--from-interview"), "Generating the charter");
    }

    @Given("the charter has been synthesized")
    public void theCharterHasBeenSynthesized() {
        succeed(List.of("spec-kitty", "charter", "synthesize", "--json"), "Synthesizing the charter");
    }

    private void succeed(List<String> args, String what) {
        CliResult result = context.run(args);
        assertThat(result.exitCode()).as("%s failed:%n%s", what, result).isZero();
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

    // ----------------------------------------------------------------------------------------- //
    // Migration-ledger arrange steps (#5230). Each builds its starting state only through the CLI
    // and plain git, and observes the clone-local git effect the way a user would — whether git
    // excludes ".spec-kitty/" — never by reaching into product internals. Each fails fast so a
    // broken fixture never reads as a product failure.
    // ----------------------------------------------------------------------------------------- //

    /** The clone-local git effect the per-clone setup step installs: a ".spec-kitty/" exclude line. */
    private static final String SPEC_KITTY_EXCLUDE = ".spec-kitty/";

    /** A recorded setup step the backfill scenario checks is recognised rather than redone. */
    private static final String BACKFILL_MARKER_STEP = "0.4.8_gitignore_agents";

    private static final Pattern LEDGER_ID = Pattern.compile("\"id\"\\s*:\\s*\"([^\"]+)\"");

    @Given("a setup step the project declares but has not recorded as run")
    public void aSetupStepDeclaredButNotRecordedAsRun() {
        // The project is set up but its local git setup has not run yet: there is no git repository
        // to carry the clone-local effect, so create one, settle the tree, and confirm the step is
        // declared (the project asks for it) but not yet in effect.
        if (!Files.isDirectory(context.world().resolve(".git"))) {
            context.world().initGitRepoWithCommit();
        }
        commitWorkingTree("commit the project before its pending setup step runs");
        context.world().recordRepoState();
        assertThat(cloneLocalSetupInPlace())
                .as("A declared local git setup step has not yet taken effect")
                .isFalse();
    }

    @Given("a freshly pulled clone whose shared records show its local git setup ran but whose own local git state is missing")
    public void aFreshlyPulledCloneMissingItsLocalGitSetup() {
        // Set the project up and run its setup so the SHARED, committed records show the project's
        // setup ran, commit those records, then reduce the checkout to what a freshly pulled clone
        // actually carries: it has neither the per-clone record (that lives only in the git-ignored
        // per-clone ledger, which never travels with a pull) nor the clone-local git effect.
        context.missions().ensureProject();
        succeed(List.of("spec-kitty", "upgrade", "--yes"),
                "Running the project's setup steps so they run and are recorded");
        commitWorkingTree("commit the shared records of the setup that ran");
        deleteRelative(".kittify/migrations/clone-local.jsonl");
        removeCloneLocalSetup();
        context.world().recordRepoState();
        assertThat(cloneLocalSetupInPlace())
                .as("This clone's own local git setup is missing before the upgrade")
                .isFalse();
    }

    @Given("a project set up before Spec Kitty recorded its applied setup steps")
    public void aProjectSetUpBeforeSpecKittyRecordedItsAppliedSetupSteps() {
        // Build a fully set-up project, then put it back into the shape a project set up before the
        // applied-work records existed carries: its prior setup noted in the legacy project metadata,
        // with no applied-work records yet.
        context.missions().ensureProject();
        succeed(List.of("spec-kitty", "upgrade", "--yes"),
                "Setting the project up fully before recasting it as a pre-record project");
        commitWorkingTree("commit the fully set-up project");
        recastAsProjectWithoutAppliedRecords();
        commitWorkingTree("commit the pre-record project state");
        context.world().recordRepoState();
    }

    @Given("a project whose recorded setup step no longer matches its current definition")
    public void aProjectWhoseRecordedSetupStepNoLongerMatchesItsCurrentDefinition() {
        // Set the project up so its setup steps are recorded, then change the recorded fingerprint of
        // one step so it no longer matches the step's current definition (as a pulled change to a
        // step's source would leave it).
        context.missions().ensureProject();
        succeed(List.of("spec-kitty", "upgrade", "--yes"),
                "Setting the project up so its setup steps are recorded");
        commitWorkingTree("commit the recorded setup steps");
        driftOneRecordedSetupStep();
        context.world().recordRepoState();
    }

    private void commitWorkingTree(String message) {
        context.world().git("add", "-A");
        context.world().git("commit", "--allow-empty", "-m", message);
    }

    /** The git exclude file this clone uses, resolved so it is correct for a linked worktree too. */
    private Path excludeFile() {
        String path = context.world().git("rev-parse", "--git-path", "info/exclude").trim();
        Path candidate = Path.of(path);
        return candidate.isAbsolute() ? candidate : context.world().workDir().resolve(candidate);
    }

    /** Whether this checkout's own local git setup is in place: git excludes ".spec-kitty/". */
    private boolean cloneLocalSetupInPlace() {
        Path exclude = excludeFile();
        if (!Files.isRegularFile(exclude)) {
            return false;
        }
        try {
            return Files.readAllLines(exclude).stream().map(String::strip).anyMatch(SPEC_KITTY_EXCLUDE::equals);
        } catch (IOException e) {
            throw new UncheckedIOException("Could not read " + exclude, e);
        }
    }

    private void removeCloneLocalSetup() {
        Path exclude = excludeFile();
        assertThat(exclude).as("The repository's git exclude file").isRegularFile();
        try {
            List<String> kept = Files.readAllLines(exclude).stream()
                    .filter(line -> !line.strip().equals(SPEC_KITTY_EXCLUDE)).toList();
            Files.writeString(exclude, String.join("\n", kept) + "\n");
        } catch (IOException e) {
            throw new UncheckedIOException("Could not rewrite " + exclude, e);
        }
    }

    private void recastAsProjectWithoutAppliedRecords() {
        // Note each step the records show as applied in the legacy project metadata, so the project
        // recognises the work as already done, then remove the applied-work records themselves.
        List<String> steps = new ArrayList<>(new LinkedHashSet<>(recordedSuccessfulStepIds()));
        if (!steps.contains(BACKFILL_MARKER_STEP)) {
            steps.add(BACKFILL_MARKER_STEP);
        }
        StringBuilder block = new StringBuilder("migrations:\n  applied:\n");
        for (String step : steps) {
            block.append("  - id: ").append(step).append("\n")
                    .append("    applied_at: '2026-01-01T00:00:00+00:00'\n")
                    .append("    result: success\n")
                    .append("    notes: null\n");
        }
        Path metadata = context.world().resolve(".kittify/metadata.yaml");
        assertThat(metadata).as("The project metadata file").isRegularFile();
        try {
            String text = Files.readString(metadata);
            // Drop any applied-steps block already present, then append the legacy one.
            text = text.replaceAll("(?s)\\nmigrations:.*\\z", "\n");
            Files.writeString(metadata, text.stripTrailing() + "\n" + block);
        } catch (IOException e) {
            throw new UncheckedIOException("Could not rewrite " + metadata, e);
        }
        deleteRelative(".kittify/migration-ledger.jsonl");
        deleteRelative(".kittify/migrations/clone-local.jsonl");
    }

    private void driftOneRecordedSetupStep() {
        Path records = context.world().resolve(".kittify/migration-ledger.jsonl");
        assertThat(records).as("The recorded setup steps").isRegularFile();
        try {
            List<String> lines = new ArrayList<>(Files.readAllLines(records));
            int target = -1;
            for (int i = 0; i < lines.size(); i++) {
                if (!lines.get(i).isBlank()) {
                    target = i;
                    break;
                }
            }
            assertThat(target).as("A recorded setup step whose fingerprint can be changed").isNotNegative();
            String changed = lines.get(target).replaceAll(
                    "\"content_hash\"\\s*:\\s*\"[^\"]*\"",
                    "\"content_hash\": \"sha256:0000000000000000000000000000000000000000000000000000000000000000\"");
            assertThat(changed).as("The step's recorded fingerprint was changed").isNotEqualTo(lines.get(target));
            lines.set(target, changed);
            Files.writeString(records, String.join("\n", lines) + "\n");
        } catch (IOException e) {
            throw new UncheckedIOException("Could not rewrite " + records, e);
        }
    }

    private List<String> recordedSuccessfulStepIds() {
        Path records = context.world().resolve(".kittify/migration-ledger.jsonl");
        List<String> ids = new ArrayList<>();
        if (!Files.isRegularFile(records)) {
            return ids;
        }
        try {
            for (String line : Files.readAllLines(records)) {
                if (line.isBlank() || !line.contains("\"result\": \"success\"")) {
                    continue;
                }
                Matcher matcher = LEDGER_ID.matcher(line);
                if (matcher.find()) {
                    ids.add(matcher.group(1));
                }
            }
        } catch (IOException e) {
            throw new UncheckedIOException("Could not read " + records, e);
        }
        return ids;
    }

    private void deleteRelative(String relative) {
        Path target = context.world().resolve(relative);
        try {
            Files.deleteIfExists(target);
        } catch (IOException e) {
            throw new UncheckedIOException("Could not delete " + target, e);
        }
    }
}
