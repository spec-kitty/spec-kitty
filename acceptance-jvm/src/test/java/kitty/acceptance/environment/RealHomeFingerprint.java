package kitty.acceptance.environment;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.FileVisitResult;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.SimpleFileVisitor;
import java.nio.file.StandardOpenOption;
import java.nio.file.attribute.BasicFileAttributes;
import java.util.Comparator;
import java.util.Map;
import java.util.Set;
import java.util.stream.Stream;

/**
 * The "the real home stayed clean" comparison: which part of the process owner's runtime state root is
 * compared, and the runtime control that proves the narrowed comparison still detects a genuine leak.
 *
 * <p>A scenario redirects {@code HOME} and {@code SPEC_KITTY_HOME} into its temp dir, so the After hook
 * compares the real runtime state root ({@code ~/.spec-kitty}) before and after the run and refuses any
 * change. On a CI runner that is exact: the harness is the only {@code spec-kitty} writer. On a host that
 * runs several Missions at once it is not, because every {@code spec-kitty next} of every other Mission
 * writes into the same per-user root. Two subtrees are written that way and are per-mission by
 * construction:
 *
 * <ul>
 *   <li>{@value #PROMPT_NAMESPACE_DIRECTORY} — prompt temp files, one directory per resolved repo path
 *       ({@code sha256(repo path)[:16]}). Production owner:
 *       {@code src/runtime/next/_tmp_namespace.py} ({@code SPEC_KITTY_PROMPT_NAMESPACE}), which also
 *       says the namespace is per-repo so concurrent runs never collide.
 *   <li>{@value #GATE_LOCK_DIRECTORY} — machine-wide cross-process gate locks. Production owner:
 *       {@code src/specify_cli/review/pre_review_gate.py}.
 * </ul>
 *
 * <p>Both are named by the shared-machine rule as safe to race. A shared host therefore compares the
 * whole tree <em>minus</em> those two subtrees — and nothing else. Everything else in the root (the
 * tracker {@code credentials} file, an activation ledger, a state entry, any new top-level file a
 * redirection bug would leave behind) stays compared, and the {@code *.lock} filename exclusion keeps
 * its current meaning in every scope.
 *
 * <p><b>Scope.</b> {@code strict} is the default and is what a single-writer machine and every CI runner
 * gets. {@code shared-host} is selected by the {@value #SHARED_HOST_VARIABLE} environment variable, and
 * is refused whenever {@value #CONTINUOUS_INTEGRATION_VARIABLE} marks a GitHub Actions runner — a flag
 * exported into a workflow, or inherited from a developer shell, must not be able to weaken the nightly
 * gate.
 *
 * <p><b>Non-vacuity.</b> A narrowed comparison is worth nothing if it can no longer fail, so
 * {@link #proveStillDetectsLeaks(Path)} runs inside every scenario and exercises both scopes on one
 * synthetic tree: a leak outside the excused subtrees must change the fingerprint in both, a prompt
 * write must change it in strict scope and not in shared-host scope, and an in-place edit of an excused
 * file must still be invisible to shared-host scope. A control that cannot prove that raises; it never
 * degrades to a skip.
 */
final class RealHomeFingerprint {

    /** Declares that this host runs other Missions next to the acceptance suite. */
    static final String SHARED_HOST_VARIABLE = "SPEC_KITTY_ACCEPTANCE_SHARED_HOST";

    /** A GitHub Actions runner is never a shared host; the switch is ignored there. */
    static final String CONTINUOUS_INTEGRATION_VARIABLE = "GITHUB_ACTIONS";

    /** Per-repo, content-addressed prompt temp root; see the class comment for its production owner. */
    static final String PROMPT_NAMESPACE_DIRECTORY = "spec-kitty-prompts";

    /** Machine-wide cross-process gate locks; see the class comment for their production owner. */
    static final String GATE_LOCK_DIRECTORY = "gate-locks";

    /** The subtrees a concurrent Mission may write; excused in shared-host scope, never otherwise. */
    private static final Set<String> CONCURRENT_MISSION_DIRECTORIES =
            Set.of(PROMPT_NAMESPACE_DIRECTORY, GATE_LOCK_DIRECTORY);

    private static final String ABSENT = "absent";
    private static final String SCOPE_STRICT = "strict";
    private static final String SCOPE_SHARED_HOST = "shared-host";

    private final Path root;
    private final boolean sharedHost;

    private RealHomeFingerprint(Path root, boolean sharedHost) {
        this.root = root;
        this.sharedHost = sharedHost;
    }

    /** The comparison for {@code root}, with the scope resolved from {@code environment}. */
    static RealHomeFingerprint of(Path root, Map<String, String> environment) {
        return new RealHomeFingerprint(root, sharedHost(environment));
    }

    /**
     * Whether the host is declared shared with other Missions <em>and</em> is not a CI runner.
     *
     * <p>Pure in {@code environment} on purpose: the guard passes {@link System#getenv()}, while the
     * non-vacuity control passes hand-built maps, so neither has to mutate the process environment.
     */
    static boolean sharedHost(Map<String, String> environment) {
        return truthy(environment.get(SHARED_HOST_VARIABLE))
                && !truthy(environment.get(CONTINUOUS_INTEGRATION_VARIABLE));
    }

    /** The comparison scope, for the guard's failure message. */
    String scope() {
        return sharedHost ? SCOPE_SHARED_HOST : SCOPE_STRICT;
    }

    /**
     * Existence, regular-file count, newest mtime and total size of the root: a cheap proof it was left
     * alone. In strict scope this is byte-for-byte the string this harness produced before the scope
     * existed, so a strict-scope message keeps its shape.
     *
     * <p>Shared-host scope reports as {@code absent} both a root that does not exist and one that holds
     * nothing but concurrent-mission files: a Mission that creates the root on a fresh machine and writes
     * only its prompt has not touched anything this scenario owns, and the two states must compare equal
     * for that reason.
     */
    String value() {
        if (!Files.exists(root)) {
            return ABSENT;
        }
        long[] stats = {0, 0, 0};
        try {
            if (sharedHost) {
                walkSkippingConcurrentMissions(stats);
            } else {
                walkWholeTree(stats);
            }
        } catch (IOException e) {
            throw new UncheckedIOException("Could not fingerprint " + root, e);
        }
        if (sharedHost && stats[0] == 0) {
            return ABSENT;
        }
        return "files=" + stats[0] + ",newestMtime=" + stats[1] + ",bytes=" + stats[2];
    }

    /** The traversal this guard has always used, unchanged: one walk, lazy, every regular file. */
    private void walkWholeTree(long[] stats) throws IOException {
        try (Stream<Path> tree = Files.walk(root)) {
            tree.filter(Files::isRegularFile)
                    .filter(file -> !file.getFileName().toString().endsWith(".lock"))
                    .forEach(file -> accumulate(stats, file));
        }
    }

    /**
     * The shared-host traversal: it never enters a concurrent Mission's subtree, so a prompt file that
     * another Mission creates or deletes mid-walk cannot fail this scenario, and "excused" is one
     * decision taken at the directory, not a per-file test that a disappearance can race.
     */
    private void walkSkippingConcurrentMissions(long[] stats) throws IOException {
        Files.walkFileTree(root, new SimpleFileVisitor<>() {
            @Override
            public FileVisitResult preVisitDirectory(Path dir, BasicFileAttributes attributes) {
                if (!dir.equals(root) && isConcurrentMissionDirectory(root.relativize(dir))) {
                    return FileVisitResult.SKIP_SUBTREE;
                }
                return FileVisitResult.CONTINUE;
            }

            @Override
            public FileVisitResult visitFile(Path file, BasicFileAttributes attributes) {
                if (attributes.isRegularFile() && !file.getFileName().toString().endsWith(".lock")) {
                    accumulate(stats, file);
                }
                return FileVisitResult.CONTINUE;
            }
        });
    }

    private static void accumulate(long[] stats, Path file) {
        stats[0]++;
        try {
            stats[1] = Math.max(stats[1], Files.getLastModifiedTime(file).toMillis());
            stats[2] += Files.size(file);
        } catch (IOException ignored) {
            // A file vanishing mid-walk is itself a change the count will show.
        }
    }

    /**
     * Whether {@code pathBelowRoot} is a subtree a concurrent Mission owns. Matched on the first path
     * component below the root, so a renamed prompt or a new lock file cannot silently escape the list,
     * and a file at the root or under a sibling such as {@code credentials} is never excused.
     */
    private static boolean isConcurrentMissionDirectory(Path pathBelowRoot) {
        return pathBelowRoot.getNameCount() >= 1
                && CONCURRENT_MISSION_DIRECTORIES.contains(pathBelowRoot.getName(0).toString());
    }

    /**
     * The negative control for the comparison above: on one synthetic tree under {@code scratchRoot},
     * prove that a genuine leak still reddens the guard and that only the concurrent-mission subtrees are
     * invisible in shared-host scope.
     *
     * <p>The expectations, each asserted against the same fixture so the two scopes cannot drift apart:
     *
     * <ol>
     *   <li>a file written at the root of the tree (a redirection leak) changes the fingerprint in both
     *       scopes;
     *   <li>a prompt file written under {@value #PROMPT_NAMESPACE_DIRECTORY} changes it in strict scope;
     *   <li>that same write does not change it in shared-host scope;
     *   <li>appending a byte to that excused file changes the strict fingerprint and still not the
     *       shared-host one;
     *   <li>a root that holds nothing but a concurrent Mission's prompt reports the same value as a root
     *       that does not exist yet, so a fresh machine's first Mission cannot fail the guard.
     * </ol>
     *
     * <p>Plus the scope policy itself: the switch alone selects shared-host, and the CI marker wins over
     * the switch. The control owns the directory it writes: it asks for a fresh one under
     * {@code scratchRoot} and removes exactly that, so a pre-existing path (or a symlink planted at it)
     * cannot be overwritten or deleted by the probe.
     *
     * @throws IllegalStateException if any expectation fails: the comparison is vacuous, and a scenario
     *     that cannot prove its own guard must not pass
     */
    static void proveStillDetectsLeaks(Path scratchRoot) {
        requirePolicy(Map.of(), false, "no switch and no CI marker is strict");
        requirePolicy(Map.of(SHARED_HOST_VARIABLE, "1"), true,
                "a truthy switch alone selects shared-host");
        requirePolicy(Map.of(SHARED_HOST_VARIABLE, "1", CONTINUOUS_INTEGRATION_VARIABLE, "true"), false,
                "a CI runner refuses the shared-host switch");

        Path tree = null;
        try {
            tree = Files.createTempDirectory(scratchRoot, "real-home-non-vacuity-control-");
            Files.writeString(tree.resolve("credentials"), "token=probe\n", StandardCharsets.UTF_8);

            RealHomeFingerprint strict = new RealHomeFingerprint(tree, false);
            RealHomeFingerprint shared = new RealHomeFingerprint(tree, true);
            String strictBase = strict.value();
            String sharedBase = shared.value();

            Files.writeString(tree.resolve("activation-ledger.json"), "{}\n", StandardCharsets.UTF_8);
            requireChanged(strict, strictBase, "root-level write, strict scope");
            requireChanged(shared, sharedBase, "root-level write, shared-host scope");
            Files.delete(tree.resolve("activation-ledger.json"));
            requireUnchanged(shared, sharedBase, "root-level write removed again, shared-host scope");

            Path prompt = tree.resolve(PROMPT_NAMESPACE_DIRECTORY)
                    .resolve("0123456789abcdef")
                    .resolve("spec-kitty-next-control.md");
            Files.createDirectories(prompt.getParent());
            Files.writeString(prompt, "prompt\n", StandardCharsets.UTF_8);
            String strictAfterPrompt = strict.value();
            requireChanged(strict, strictBase, "prompt-namespace write, strict scope");
            requireUnchanged(shared, sharedBase, "prompt-namespace write, shared-host scope");

            Files.writeString(prompt, "more\n", StandardCharsets.UTF_8, StandardOpenOption.APPEND);
            requireChanged(strict, strictAfterPrompt, "prompt-namespace edit, strict scope");
            requireUnchanged(shared, sharedBase, "prompt-namespace edit, shared-host scope");

            Path excusedOnly = Files.createTempDirectory(scratchRoot, "real-home-excused-only-");
            try {
                Path onlyPrompt = excusedOnly.resolve(PROMPT_NAMESPACE_DIRECTORY).resolve("feedface");
                Files.createDirectories(onlyPrompt);
                Files.writeString(onlyPrompt.resolve("spec-kitty-review-control.md"), "prompt\n",
                        StandardCharsets.UTF_8);
                String missingRoot = new RealHomeFingerprint(excusedOnly.resolve("absent"), true).value();
                requireUnchanged(new RealHomeFingerprint(excusedOnly, true), missingRoot,
                        "prompt-only root, shared-host scope (a fresh machine's first Mission)");
                requireChanged(new RealHomeFingerprint(excusedOnly, false), missingRoot,
                        "prompt-only root, strict scope");
            } finally {
                deleteQuietly(excusedOnly);
            }
        } catch (IOException e) {
            throw new UncheckedIOException("Could not run the real-home non-vacuity control", e);
        } finally {
            if (tree != null) {
                deleteQuietly(tree);
            }
        }
    }

    private static void requirePolicy(Map<String, String> environment, boolean expected, String what) {
        boolean actual = sharedHost(environment);
        if (actual != expected) {
            throw new IllegalStateException("Real-home scope policy is wrong: " + what
                    + " should be sharedHost=" + expected + " but was " + actual
                    + " for environment " + environment);
        }
    }

    private static void requireChanged(RealHomeFingerprint fingerprint, String before, String what) {
        String after = fingerprint.value();
        if (before.equals(after)) {
            throw new IllegalStateException("Scenario isolation guard is vacuous: the " + what
                    + " did not change the fingerprint of " + fingerprint.root + " (both " + before + ")");
        }
    }

    private static void requireUnchanged(RealHomeFingerprint fingerprint, String before, String what) {
        String after = fingerprint.value();
        if (!before.equals(after)) {
            throw new IllegalStateException("Scenario isolation guard excused too little: the " + what
                    + " is a concurrent-mission write that shared-host scope must ignore, but it changed"
                    + " the fingerprint of " + fingerprint.root + " (before: " + before + ", after: "
                    + after + ")");
        }
    }

    private static void deleteQuietly(Path path) {
        if (!Files.exists(path)) {
            return;
        }
        try (Stream<Path> tree = Files.walk(path)) {
            tree.sorted(Comparator.reverseOrder()).forEach(entry -> {
                try {
                    Files.deleteIfExists(entry);
                } catch (IOException ignored) {
                    // Best-effort cleanup; a leftover control tree is not worth failing a scenario.
                }
            });
        } catch (IOException ignored) {
            // Best-effort cleanup.
        }
    }

    private static boolean truthy(String value) {
        if (value == null) {
            return false;
        }
        return switch (value.trim().toLowerCase(java.util.Locale.ROOT)) {
            case "1", "true", "yes", "on" -> true;
            default -> false;
        };
    }
}
