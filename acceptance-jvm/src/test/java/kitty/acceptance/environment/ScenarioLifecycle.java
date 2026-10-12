package kitty.acceptance.environment;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Comparator;
import java.util.stream.Stream;

/** The NFR-002 positive control and the teardown of the scenario's temp dir. */
final class ScenarioLifecycle {

    private final Path homeDir;
    private final Path tempRoot;
    private final long startEpochMillis = System.currentTimeMillis();
    private final Path realSpecKittyHome = Path.of(System.getProperty("user.home"), ".spec-kitty");
    private final String realHomeBefore = fingerprint(realSpecKittyHome);

    private boolean commandObserved;

    ScenarioLifecycle(Path homeDir, Path tempRoot) {
        this.homeDir = homeDir;
        this.tempRoot = tempRoot;
    }

    void markCommandObserved() {
        commandObserved = true;
    }


    /**
     * NFR-002 positive control, in two halves.
     *
     * <p><b>Redirection took effect.</b> After a CLI invocation, something under the redirected
     * home directory (not the working tree, which also holds the harness's own git fixture) must
     * have been written since the scenario started. {@code spec-kitty init} installs its global
     * command and skill files and missions under {@code HOME}, so a missing write there means the
     * environment redirection is not in effect. The start time is floored to whole seconds so
     * coarse-mtime filesystems cannot hide a fresh write.
     *
     * <p><b>The real home stayed clean.</b> The real {@code ~/.spec-kitty} must look exactly as it
     * did when the scenario started (existence, file count, newest mtime). Lock files are left out:
     * another {@code spec-kitty} process on a developer machine touches them (for example
     * {@code auth/session.lock}) and would trip the check without the scenario being at fault.
     */
    void assertObservedWriteInsideTempDir() {
        if (!commandObserved) {
            return;
        }
        long floor = startEpochMillis / 1000 * 1000;
        try (Stream<Path> tree = Files.walk(homeDir)) {
            boolean wrote = tree.filter(Files::isRegularFile).anyMatch(file -> modifiedSince(file, floor));
            if (!wrote) {
                throw new AssertionError("Positive control failed: the CLI run wrote nothing under the "
                        + "redirected home " + homeDir + " - environment redirection may not be in effect");
            }
        } catch (IOException e) {
            throw new UncheckedIOException("Could not walk the redirected home for the positive control", e);
        }
        String after = fingerprint(realSpecKittyHome);
        if (!realHomeBefore.equals(after)) {
            throw new AssertionError("The scenario changed the real " + realSpecKittyHome
                    + " (before: " + realHomeBefore + ", after: " + after + ")");
        }
    }

    private static boolean modifiedSince(Path file, long floorMillis) {
        try {
            return Files.getLastModifiedTime(file).toMillis() >= floorMillis;
        } catch (IOException e) {
            return false;
        }
    }

    /**
     * Existence, regular-file count, newest mtime and total size of a tree, ignoring {@code *.lock} files; cheap
     * proof it was left alone.
     */
    private static String fingerprint(Path root) {
        if (!Files.exists(root)) {
            return "absent";
        }
        try (Stream<Path> tree = Files.walk(root)) {
            long[] stats = {0, 0, 0};
            tree.filter(Files::isRegularFile)
                    .filter(file -> !file.getFileName().toString().endsWith(".lock"))
                    .forEach(file -> {
                stats[0]++;
                try {
                    stats[1] = Math.max(stats[1], Files.getLastModifiedTime(file).toMillis());
                    stats[2] += Files.size(file);
                } catch (IOException ignored) {
                    // A file vanishing mid-walk is itself a change the count will show.
                }
            });
            return "files=" + stats[0] + ",newestMtime=" + stats[1] + ",bytes=" + stats[2];
        } catch (IOException e) {
            throw new UncheckedIOException("Could not fingerprint " + root, e);
        }
    }

    void cleanUp() {
        if (!Files.exists(tempRoot)) {
            return;
        }
        try (Stream<Path> tree = Files.walk(tempRoot)) {
            tree.sorted(Comparator.reverseOrder()).forEach(ScenarioLifecycle::deleteQuietly);
        } catch (IOException ignored) {
            // Best-effort teardown; a leaked temp dir is not worth failing a passing scenario.
        }
    }

    private static void deleteQuietly(Path path) {
        try {
            // Managed skill files are read-only; Windows will not delete them otherwise.
            path.toFile().setWritable(true);
            Files.deleteIfExists(path);
        } catch (IOException ignored) {
            // Best-effort teardown.
        }
    }
}
