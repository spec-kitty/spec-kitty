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
    private final RealHomeFingerprint realHome;
    private final Path realSpecKittyHome;
    private final String realHomeBefore;

    private boolean commandObserved;

    ScenarioLifecycle(Path homeDir, Path tempRoot) {
        this.homeDir = homeDir;
        this.tempRoot = tempRoot;
        this.realSpecKittyHome = Path.of(System.getProperty("user.home"), ".spec-kitty");
        this.realHome = RealHomeFingerprint.of(realSpecKittyHome, System.getenv());
        // The guard proves it can still fail before it is trusted with the scenario's before-state, so a
        // comparison that has become vacuous fails loudly instead of quietly passing every run.
        RealHomeFingerprint.proveStillDetectsLeaks(tempRoot);
        this.realHomeBefore = realHome.value();
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
     * <p><b>The real home stayed clean.</b> The real {@code ~/.spec-kitty} must look as it did when the
     * scenario started (existence, file count, newest mtime, total size; see
     * {@link RealHomeFingerprint}). Lock files are left out: another {@code spec-kitty} process on a
     * developer machine touches them (for example {@code auth/session.lock}) and would trip the check
     * without the scenario being at fault. On a shared host the comparison is narrowed to the surfaces a
     * scenario could plausibly corrupt — the {@code SPEC_KITTY_ACCEPTANCE_SHARED_HOST} switch is described
     * by {@link RealHomeFingerprint} and cannot be set on a CI runner — and the failure message names the
     * scope it compared, so a reader can tell a leak from a mis-scoped run.
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
        String after = realHome.value();
        if (!realHomeBefore.equals(after)) {
            throw new AssertionError("The scenario changed the real " + realSpecKittyHome
                    + " (scope=" + realHome.scope() + ", before: " + realHomeBefore
                    + ", after: " + after + ")");
        }
    }

    private static boolean modifiedSince(Path file, long floorMillis) {
        try {
            return Files.getLastModifiedTime(file).toMillis() >= floorMillis;
        } catch (IOException e) {
            return false;
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
