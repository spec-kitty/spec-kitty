package kitty.acceptance.environment;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

/**
 * Builds repository states a user reaches with plain git, never with Spec Kitty internals.
 *
 * <p>Each builder runs git in the scenario's working tree and fails fast when git did not do what
 * the arrange step asked for, so a broken fixture never reads as a product failure. Files are
 * written only where a user writing git state by hand would write them (a tracked file, or git's own
 * {@code .git/info/sparse-checkout} pattern file); nothing under {@code .kittify/} or
 * {@code kitty-specs/} is touched.
 */
final class GitStates {

    private final Path workDir;
    private final GitFixture git;

    GitStates(Path workDir, GitFixture git) {
        this.workDir = workDir;
        this.git = git;
    }

    /**
     * Turns on legacy (non-cone) sparse-checkout the way Spec Kitty 2.x left it behind: the
     * {@code core.sparseCheckout} setting plus a pattern file, without re-reading the working tree.
     */
    void enableLegacySparseCheckout(List<String> patterns) {
        git.git("config", "core.sparseCheckout", "true");
        Path patternFile = Path.of(git.git("rev-parse", "--git-path", "info/sparse-checkout").trim());
        Path absolute = patternFile.isAbsolute() ? patternFile : workDir.resolve(patternFile);
        write(absolute, String.join("\n", patterns) + "\n");
    }

    /** Adds a linked worktree at {@code relative} on a new branch, with its own sparse-checkout setting turned on. */
    void addSparseWorktree(String relative) {
        Path target = workDir.resolve(relative);
        String branch = "feature/" + target.getFileName();
        git.git("worktree", "add", "-b", branch, target.toString());
        git.git("config", "extensions.worktreeConfig", "true");
        git.git("-C", target.toString(), "config", "--worktree", "core.sparseCheckout", "true");
    }

    /**
     * Leaves a git merge in progress with an unresolved conflict in {@code file}: the file is
     * changed on a side branch and on the current branch, then the side branch is merged.
     */
    void startConflictingMerge(String file) {
        Path path = workDir.resolve(file);
        write(path, "base\n");
        git.git("add", file);
        git.git("commit", "-m", "add " + file);
        String current = git.git("rev-parse", "--abbrev-ref", "HEAD").trim();
        git.git("checkout", "-b", "incoming");
        write(path, "incoming change\n");
        git.git("commit", "-am", "incoming change");
        git.git("checkout", current);
        write(path, "local change\n");
        git.git("commit", "-am", "local change");
        ProcessRunner.Outcome merge = git.tryGit("merge", "incoming");
        if (merge.exitCode() == 0 || !mergeInProgress()) {
            throw new IllegalStateException("Expected 'git merge incoming' to stop on a conflict:"
                    + System.lineSeparator() + merge.output());
        }
    }

    /** Commits everything in the working tree, as a user's {@code git add -A && git commit} would. */
    void commitEverything(String message) {
        git.git("add", "-A");
        git.git("commit", "--allow-empty", "-m", message);
    }

    /** Every local branch and the commit it points at, one {@code <ref> <sha>} line each, sorted. */
    String branches() {
        return git.git("for-each-ref", "--sort=refname", "--format=%(refname) %(objectname)", "refs/heads").trim();
    }

    /** The {@code git status --porcelain} lines of the working tree (empty when it is clean). */
    String uncommittedChanges() {
        return git.git("status", "--porcelain").trim();
    }

    /** Whether git has a merge in progress ({@code MERGE_HEAD} resolves). */
    boolean mergeInProgress() {
        return git.tryGit("rev-parse", "-q", "--verify", "MERGE_HEAD").exitCode() == 0;
    }

    /** The value of a git setting, or the empty string when it is not set. */
    String setting(String key) {
        ProcessRunner.Outcome outcome = git.tryGit("config", "--get", key);
        return outcome.exitCode() == 0 ? outcome.output().trim() : "";
    }

    private static void write(Path path, String content) {
        try {
            Files.createDirectories(path.getParent());
            Files.writeString(path, content);
        } catch (IOException e) {
            throw new UncheckedIOException("Could not write " + path, e);
        }
    }
}
