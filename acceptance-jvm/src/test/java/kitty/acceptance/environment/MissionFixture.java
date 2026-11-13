package kitty.acceptance.environment;

import kitty.acceptance.driver.CliResult;

import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Builds a project that holds a Mission, only by running the CLI (constraint C-002).
 *
 * <p>The sequence is the one a user follows: a git repository with a commit, {@code spec-kitty init},
 * a commit of whatever {@code init} left uncommitted, then
 * {@code spec-kitty agent mission create <slug> --json}. Since #7555 {@code init} commits its own
 * writes, so that middle commit is usually not needed; it is made only when the tree is dirty. Nothing
 * under {@code .kittify/} or {@code kitty-specs/} is written from here. Each step fails fast with the
 * command output, so a broken fixture never reads as a product failure.
 *
 * <p>A work package in a given lane is deliberately not built: it needs the specify, plan and tasks
 * chain, which an agent authors interactively and which the CLI cannot run as a few non-interactive
 * commands.
 */
public final class MissionFixture {

    private static final Duration GIT_TIMEOUT = Duration.ofSeconds(60);
    private static final Pattern MISSION_SLUG = Pattern.compile("\"mission_slug\"\\s*:\\s*\"([^\"]+)\"");

    private final Path workDir;
    private final Map<String, String> environment;
    private final Function<List<String>, CliResult> cli;
    private final Runnable gitRepoWithCommit;
    private boolean projectReady;

    /**
     * @param gitRepoWithCommit creates the throwaway repository with its seed commit (the world's
     *                          existing git fixture)
     * @param cli               runs a CLI command in the working directory through the driver
     */
    public MissionFixture(Path workDir, Map<String, String> environment, Runnable gitRepoWithCommit,
            Function<List<String>, CliResult> cli) {
        this.workDir = workDir;
        this.environment = environment;
        this.gitRepoWithCommit = gitRepoWithCommit;
        this.cli = cli;
    }

    /**
     * Sets up Spec Kitty in the repository once, so that every file {@code init} wrote is committed.
     *
     * <p>Since #7555 {@code init} commits its own writes, which leaves a clean tree, and a plain
     * {@code git commit} on a clean tree fails with "nothing to commit". The fixture commits only
     * what is still uncommitted (an opt-out, or anything {@code init} does not commit), and never an
     * empty commit, so the history stays what a user would have.
     */
    public void ensureProject() {
        if (projectReady) {
            return;
        }
        if (!Files.exists(workDir.resolve(".git"))) {
            gitRepoWithCommit.run();
        }
        succeed(List.of("spec-kitty", "init", "--non-interactive", "--ai", "claude"));
        if (!git("status", "--porcelain").isBlank()) {
            git("add", "-A");
            git("commit", "-m", "set up spec-kitty");
        }
        projectReady = true;
    }

    /**
     * Creates a coordination Mission and returns the full Mission slug the CLI assigned to it.
     *
     * <p>The topology is explicit because the scenarios that use this builder (abort, discard,
     * per-Mission status) are about a coordination Mission. Since #7282 a create without
     * {@code --topology} records an unsettled {@code single_branch} Mission instead: it switches the
     * checkout onto that Mission's topic branch and leaves its {@code spec.md} scaffold uncommitted.
     * A second such create is then refused with {@code WRITE_CHECKOUT_DIRTY}, and that refusal is
     * intended: the first Mission's untracked scaffold would otherwise follow the checkout onto the
     * second Mission's branch. A scenario about the default topology commits or discards the first
     * scaffold before the next create.
     */
    public String createMission(String slug) {
        ensureProject();
        CliResult result = succeed(List.of("spec-kitty", "agent", "mission", "create", slug, "--json",
                "--topology", "lanes_with_coord"));
        Matcher matcher = MISSION_SLUG.matcher(result.stdout());
        if (!matcher.find()) {
            throw new IllegalStateException("No mission_slug in the output of 'mission create':\n" + result);
        }
        return matcher.group(1);
    }

    private CliResult succeed(List<String> args) {
        CliResult result = cli.apply(args);
        if (result.exitCode() != 0) {
            throw new IllegalStateException("Building the mission fixture failed at " + args + ":\n" + result);
        }
        return result;
    }

    private String git(String... args) {
        List<String> command = new ArrayList<>(List.of("git", "-c", "user.name=" + GitFixture.GIT_NAME,
                "-c", "user.email=" + GitFixture.GIT_EMAIL, "-c", "commit.gpgsign=false"));
        command.addAll(List.of(args));
        ProcessBuilder builder = new ProcessBuilder(command);
        builder.directory(workDir.toFile());
        builder.environment().clear();
        builder.environment().putAll(environment);
        ProcessRunner.Outcome outcome = ProcessRunner.run(builder, GIT_TIMEOUT, "git " + List.of(args));
        if (outcome.exitCode() != 0) {
            throw new IllegalStateException("git " + List.of(args) + " failed:\n" + outcome.output());
        }
        return outcome.output();
    }
}
