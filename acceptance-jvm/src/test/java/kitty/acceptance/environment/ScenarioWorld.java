package kitty.acceptance.environment;

import kitty.acceptance.driver.CliProcessDriver;

import java.nio.file.Path;
import java.util.List;
import java.util.Map;

/**
 * Per-scenario isolation, composed from four single-responsibility collaborators (NFR-002, FR-008):
 * {@link ScenarioEnvironment} (the redirected, hermetic environment and dir layout),
 * {@link FileSnapshots} (before/after digests), {@link GitFixture} (the throwaway repo and its read
 * model), {@link GitStates} (plain-git repository states) and {@link ScenarioLifecycle} (the
 * real-home positive control and teardown).
 *
 * <p>This class is a thin aggregate: it holds the collaborators and delegates each public method to
 * the one that owns the concern, so step classes keep reaching the world through one object.
 */
public final class ScenarioWorld {

    private final ScenarioEnvironment environment;
    private final FileSnapshots snapshots;
    private final GitFixture git;
    private final GitStates gitStates;
    private final ScenarioLifecycle lifecycle;
    private String recordedBranches;

    private ScenarioWorld(ScenarioEnvironment environment, FileSnapshots snapshots, GitFixture git,
            ScenarioLifecycle lifecycle) {
        this.environment = environment;
        this.snapshots = snapshots;
        this.git = git;
        this.gitStates = new GitStates(environment.workDir(), git);
        this.lifecycle = lifecycle;
    }

    public static ScenarioWorld create(CliUnderTest cli) {
        ScenarioEnvironment env = ScenarioEnvironment.create(cli);
        return new ScenarioWorld(
                env,
                new FileSnapshots(env.workDir()),
                new GitFixture(env.workDir(), env.environment()),
                new ScenarioLifecycle(env.homeDir(), env.tempRoot()));
    }

    public Map<String, String> environment() {
        return environment.environment();
    }

    /** Maps the {@code "spec-kitty"} token to the provisioned venv entry point; passes anything else through. */
    public CliProcessDriver.CommandResolver commandResolver() {
        return environment.commandResolver();
    }

    public Path workDir() {
        return environment.workDir();
    }

    public Path resolve(String relative) {
        return environment.resolve(relative);
    }

    public void markCommandObserved() {
        lifecycle.markCommandObserved();
    }

    public void recordState(String relative) {
        snapshots.recordState(relative);
    }

    public boolean isUnchanged(String relative) {
        return snapshots.isUnchanged(relative);
    }

    public void initGitRepoWithCommit() {
        git.initGitRepoWithCommit();
    }

    /** Records HEAD and the commit count, and returns the recorded count. */
    public int recordRepoState() {
        return git.recordRepoState();
    }

    public boolean headUnchanged() {
        return git.headUnchanged();
    }

    public boolean commitCountUnchanged() {
        return git.commitCountUnchanged();
    }

    /** The paths the commits made since the repository state was recorded changed. */
    public List<String> pathsChangedSinceRecorded() {
        return git.pathsChangedSinceRecorded();
    }

    /** Runs a plain git command in the working tree (the harness identity, no signing) and returns its output. */
    public String git(String... args) {
        return git.git(args);
    }

    public void enableLegacySparseCheckout(List<String> patterns) {
        gitStates.enableLegacySparseCheckout(patterns);
    }

    public void addSparseWorktree(String relative) {
        gitStates.addSparseWorktree(relative);
    }

    public void startConflictingMerge(String file) {
        gitStates.startConflictingMerge(file);
    }

    public boolean mergeInProgress() {
        return gitStates.mergeInProgress();
    }

    public String gitSetting(String key) {
        return gitStates.setting(key);
    }

    public void commitEverything(String message) {
        gitStates.commitEverything(message);
    }

    /** Records every local branch and its tip, for {@link #branchesUnchanged()}. */
    public void recordBranches() {
        recordedBranches = gitStates.branches();
    }

    public boolean branchesUnchanged() {
        if (recordedBranches == null) {
            throw new IllegalStateException("No recorded branches: record them with an Assume step first");
        }
        return recordedBranches.equals(gitStates.branches());
    }

    public String uncommittedChanges() {
        return gitStates.uncommittedChanges();
    }

    /** NFR-002 positive control: see {@link ScenarioLifecycle#assertObservedWriteInsideTempDir()}. */
    public void assertObservedWriteInsideTempDir() {
        lifecycle.assertObservedWriteInsideTempDir();
    }

    public void cleanUp() {
        lifecycle.cleanUp();
    }
}
