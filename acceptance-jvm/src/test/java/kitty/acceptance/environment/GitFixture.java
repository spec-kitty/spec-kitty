package kitty.acceptance.environment;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/** The throwaway git repository in the working tree, plus the recorded HEAD / commit-count read model. */
public final class GitFixture {

    private static final Duration GIT_TIMEOUT = Duration.ofSeconds(60);
    // The one source of the harness git identity: ScenarioEnvironment reuses it for GIT_AUTHOR_*/GIT_COMMITTER_*.
    static final String GIT_NAME = "Acceptance Harness";
    static final String GIT_EMAIL = "harness@example.invalid";

    private final Path workDir;
    private final Map<String, String> environment;

    private String recordedHead;
    private Integer recordedCommitCount;

    public GitFixture(Path workDir, Map<String, String> environment) {
        this.workDir = workDir;
        this.environment = environment;
    }

    public void initGitRepoWithCommit() {
        git("init");
        try {
            Files.writeString(workDir.resolve("README.md"), "seed\n");
        } catch (IOException e) {
            throw new UncheckedIOException("Could not write the seed file", e);
        }
        git("add", "README.md");
        git("commit", "-m", "seed commit");
    }

    /** Records HEAD and the commit count, and returns the recorded count. */
    public int recordRepoState() {
        recordedHead = git("rev-parse", "HEAD").trim();
        recordedCommitCount = Integer.parseInt(git("rev-list", "--count", "HEAD").trim());
        return recordedCommitCount;
    }

    public boolean headUnchanged() {
        return recordedHead != null && recordedHead.equals(git("rev-parse", "HEAD").trim());
    }

    public boolean commitCountUnchanged() {
        return recordedCommitCount != null
                && recordedCommitCount == Integer.parseInt(git("rev-list", "--count", "HEAD").trim());
    }

    private String git(String... args) {
        List<String> command = new ArrayList<>();
        command.add("git");
        command.add("-c");
        command.add("user.name=" + GIT_NAME);
        command.add("-c");
        command.add("user.email=" + GIT_EMAIL);
        command.add("-c");
        command.add("commit.gpgsign=false");
        command.addAll(List.of(args));

        ProcessBuilder builder = new ProcessBuilder(command);
        builder.directory(workDir.toFile());
        builder.environment().clear();
        builder.environment().putAll(environment);
        ProcessRunner.Outcome outcome = ProcessRunner.run(builder, GIT_TIMEOUT, "git " + List.of(args));
        if (outcome.exitCode() != 0) {
            throw new IllegalStateException("git " + List.of(args) + " failed:"
                    + System.lineSeparator() + outcome.output());
        }
        return outcome.output();
    }
}
