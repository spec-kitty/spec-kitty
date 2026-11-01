package kitty.acceptance.steps;

import kitty.acceptance.driver.CliProcessDriver;
import kitty.acceptance.driver.CliResult;
import kitty.acceptance.driver.SpecKittyDriver;
import kitty.acceptance.environment.CliUnderTest;
import kitty.acceptance.environment.MissionFixture;
import kitty.acceptance.environment.MissionLifecycle;
import kitty.acceptance.environment.ScenarioWorld;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * The state one scenario shares across its Arrange, Assume, Act and Assert step classes.
 *
 * <p>Cucumber's PicoContainer integration creates one instance per scenario and injects it into
 * every step class that asks for it, so the step classes never hold state of their own. Every
 * interaction with the CLI goes through the {@link SpecKittyDriver} port (constraint C-001):
 * steps inspect files, exit codes and git state, never Python internals.
 */
public final class ScenarioContext {

    /** The Mission every event-traceability step builds on, as the repository's other features do. */
    static final String SCENARIO_MISSION = "demo";

    private final ScenarioWorld world;
    private final SpecKittyDriver driver;
    private CliResult lastResult;
    private MissionFixture missions;
    private MissionLifecycle lifecycle;
    private final Map<String, String> recordedCoordinationFiles = new HashMap<>();
    private final Map<String, String> missionBranchTips = new HashMap<>();

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

    /** The one Mission fixture of this scenario, so every step builds on the same project. */
    MissionFixture missions() {
        if (missions == null) {
            missions = new MissionFixture(world.workDir(), world.environment(), world::initGitRepoWithCommit, this::run);
        }
        return missions;
    }

    /** The one Mission lifecycle builder of this scenario. */
    MissionLifecycle lifecycle() {
        if (lifecycle == null) {
            lifecycle = new MissionLifecycle(world.workDir(), missions(), this::run, world::git);
        }
        return lifecycle;
    }

    /**
     * The contents of a file of a Mission's folder on its coordination branch ({@code git show}), or
     * {@code null} when the branch does not hold it.
     */
    String coordinationFile(String mission, String file) {
        String spec = lifecycle().coordinationBranch(mission) + ":kitty-specs/" + lifecycle().slug(mission) + "/" + file;
        String listed = world.git("ls-tree", "--name-only", lifecycle().coordinationBranch(mission), "--",
                "kitty-specs/" + lifecycle().slug(mission) + "/" + file).trim();
        return listed.isEmpty() ? null : world.git("show", spec);
    }

    void recordCoordinationFile(String mission, String file) {
        String contents = coordinationFile(mission, file);
        if (contents == null) {
            throw new IllegalStateException("The coordination branch of mission '" + mission + "' has no " + file);
        }
        recordedCoordinationFiles.put(mission + "/" + file, contents);
    }

    String recordedCoordinationFile(String mission, String file) {
        String contents = recordedCoordinationFiles.get(mission + "/" + file);
        if (contents == null) {
            throw new IllegalStateException("No recorded state for " + file + " of mission '" + mission + "'");
        }
        return contents;
    }

    void recordMissionBranchTip(String mission) {
        missionBranchTips.put(mission, world.git("rev-parse", lifecycle().missionBranch(mission)).trim());
    }

    String recordedMissionBranchTip(String mission) {
        String tip = missionBranchTips.get(mission);
        if (tip == null) {
            throw new IllegalStateException("No recorded tip for the mission branch of mission '" + mission + "'");
        }
        return tip;
    }

    void recordResult(CliResult result) {
        lastResult = result;
    }

    /**
     * Records the rejection the event-traceability promise is about. The approval row is planted as a
     * teammate's clock-skewed pull delivers it (see
     * {@link MissionLifecycle#plantFutureStampedApproval(String, String)}), then the reviewer's
     * rejection goes through the real CLI, so the CLI's own guard decides the outcome. The result is
     * recorded for the assertions: a refusal is the scenario's red, never something to paper over.
     */
    CliResult rejectAfterApproval(String wp) {
        lifecycle().plantFutureStampedApproval(SCENARIO_MISSION, wp);
        String feedback = reviewerFeedback(wp);
        CliResult result = run(List.of("spec-kitty", "agent", "status", "emit", wp, "--to", "in_progress",
                "--mission", lifecycle().slug(SCENARIO_MISSION), "--actor", "reviewer",
                "--review-ref", feedback, "--reason", "review: changes requested after the approval"));
        recordResult(result);
        return result;
    }

    /**
     * The reviewer's notes, kept outside the repository as a reviewer delivers them, and returned as
     * the reference the CLI records with the rejection (an {@code approved -> in_progress} transition
     * requires one).
     */
    private String reviewerFeedback(String wp) {
        Path file = world().workDir().getParent().resolve("review-feedback-" + wp + ".md");
        try {
            Files.writeString(file, "# Review feedback\n\nThe approval stands, but this needs rework.\n");
        } catch (IOException e) {
            throw new UncheckedIOException("Could not write " + file, e);
        }
        return "../" + file.getFileName();
    }

    /** Consolidates the scenario's Mission as the user does, recording the result for the assertions. */
    CliResult consolidateMission() {
        CliResult result = run(List.of("spec-kitty", "consolidate", "--mission",
                lifecycle().slug(SCENARIO_MISSION), "--yes"));
        recordResult(result);
        return result;
    }

    CliResult lastResult() {
        if (lastResult == null) {
            throw new IllegalStateException("No command has been run yet in this scenario");
        }
        return lastResult;
    }
}
