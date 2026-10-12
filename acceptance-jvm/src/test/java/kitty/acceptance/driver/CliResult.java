package kitty.acceptance.driver;

import java.nio.file.Path;
import java.util.Objects;

/**
 * Immutable outcome of one CLI invocation.
 *
 * <p>Line endings in {@link #stdout()} / {@link #stderr()} are already normalised to {@code \n} by
 * {@link CliProcessDriver}, so cross-OS assertions compare like for like.
 */
public final class CliResult {

    private final int exitCode;
    private final String stdout;
    private final String stderr;
    private final Path workingTree;

    private CliResult(int exitCode, String stdout, String stderr, Path workingTree) {
        this.exitCode = exitCode;
        this.stdout = Objects.requireNonNull(stdout, "stdout");
        this.stderr = Objects.requireNonNull(stderr, "stderr");
        this.workingTree = Objects.requireNonNull(workingTree, "workingTree");
    }

    public static CliResult of(int exitCode, String stdout, String stderr, Path workingTree) {
        return new CliResult(exitCode, stdout, stderr, workingTree);
    }

    public int exitCode() {
        return exitCode;
    }

    public String stdout() {
        return stdout;
    }

    public String stderr() {
        return stderr;
    }

    public Path workingTree() {
        return workingTree;
    }

    @Override
    public String toString() {
        return "CliResult{exitCode=" + exitCode
                + ", workingTree=" + workingTree
                + "\n--- stdout ---\n" + stdout
                + "\n--- stderr ---\n" + stderr
                + "\n--------------}";
    }
}
