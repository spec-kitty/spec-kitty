package kitty.acceptance.environment;

import kitty.acceptance.driver.CliResult;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.function.Function;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Builds a Mission with finalized work packages and walks a work package through its lanes, only by
 * running the CLI and plain git, as a user and their agent would.
 *
 * <p>Decision 6 of ADR 2026-10-15-1 allows one kind of file write here: the planning files an agent
 * authors during {@code specify}, {@code plan} and {@code tasks} ({@code spec.md}, {@code plan.md},
 * {@code tasks.md}, {@code tasks/WP*.md}) and the code a work package's implementer writes in its
 * lane worktree. CLI-managed state ({@code meta.json}, the status log, {@code lanes.json}, anything
 * under {@code .kittify/}) is never written from here.
 *
 * <p>Planning happens on a topic branch, {@value #TOPIC_BRANCH}: Spec Kitty refuses planning commits
 * on the protected primary branch, so that is where a user plans. Every step fails fast with the
 * command output, so a broken fixture never reads as a product failure.
 */
public final class MissionLifecycle {

    /** The topic branch planning happens on, which becomes each Mission's target branch. */
    public static final String TOPIC_BRANCH = "work";
    /** The primary branch of the harness repository (see {@code GitFixture}). */
    public static final String PRIMARY_BRANCH = "main";

    private static final Pattern MISSION_SLUG = Pattern.compile("\"mission_slug\"\\s*:\\s*\"([^\"]+)\"");
    private static final Pattern COORDINATION_BRANCH = Pattern.compile("\"coordination_branch\"\\s*:\\s*\"([^\"]+)\"");
    private static final Pattern MISSION_BRANCH = Pattern.compile("\"mission_branch\"\\s*:\\s*\"([^\"]+)\"");
    private static final Pattern LANE_WORKTREE = Pattern.compile("\\(Lane [^:]+: ([^)]+)\\)");
    private static final List<String> LANE_ORDER = List.of("planned", "in_progress", "for_review", "in_review", "approved");
    private static final String REVIEWER = "reviewer";

    private final Path workDir;
    private final MissionFixture missions;
    private final Function<List<String>, CliResult> cli;
    private final Function<String[], String> git;
    private final Map<String, String> slugs = new HashMap<>();
    private final Map<String, String> lanes = new HashMap<>();
    private final Map<String, Path> worktrees = new HashMap<>();
    private final Map<String, String> coordinationBranches = new HashMap<>();
    private final Set<String> committed = new HashSet<>();
    private final Map<String, Integer> rounds = new HashMap<>();
    private final Map<String, String> missionBranches = new HashMap<>();
    private final Set<String> singleBranch = new HashSet<>();

    public MissionLifecycle(Path workDir, MissionFixture missions, Function<List<String>, CliResult> cli,
            Function<String[], String> git) {
        this.workDir = workDir;
        this.missions = missions;
        this.cli = cli;
        this.git = git;
    }

    /**
     * Creates the Mission {@code name} on the topic branch and plans it up to finalized work packages:
     * create, a written spec, {@code setup-plan}, a written plan and tasks, {@code finalize-tasks} and
     * a recorded analysis. Returns the full Mission slug.
     */
    public String planMission(String name, List<String> workPackages) {
        String slug = specifyMission(name);
        succeed(List.of("spec-kitty", "agent", "mission", "setup-plan", "--mission", slug, "--json"));
        return finishPlanning(name, slug, workPackages);
    }

    /**
     * Plans a {@code single_branch} Mission: its work packages run one after another in the write
     * checkout, with no lane worktree. On the topic branch the checkout stays there; targeting the
     * protected primary branch, {@code mission create} mints a Mission branch and checks it out.
     */
    public String planSingleBranchMission(String name, List<String> workPackages, boolean targetPrimary) {
        missions.ensureProject();
        List<String> create = new ArrayList<>(List.of("spec-kitty", "agent", "mission", "create", name,
                "--topology", "single_branch", "--json"));
        if (targetPrimary) {
            create.addAll(List.of("--target-branch", PRIMARY_BRANCH));
        } else {
            onTopicBranch();
        }
        CliResult created = succeed(create);
        String slug = mission(created);
        Matcher minted = MISSION_BRANCH.matcher(created.stdout());
        if (minted.find()) {
            missionBranches.put(name, minted.group(1));
        }
        singleBranch.add(name);
        write(workDir.resolve("kitty-specs").resolve(slug).resolve("spec.md"), spec(name));
        write(workDir.resolve("kitty-specs").resolve(slug).resolve("plan.md"), PLAN);
        slugs.put(name, slug);
        return finishPlanning(name, slug, workPackages);
    }

    /** The branch {@code mission create} minted for a protected single_branch Mission. */
    public String missionBranch(String name) {
        String branch = missionBranches.get(name);
        if (branch == null) {
            throw new IllegalStateException("Mission '" + name + "' has no minted mission branch");
        }
        return branch;
    }

    private void onTopicBranch() {
        if (!TOPIC_BRANCH.equals(git.apply(new String[] {"rev-parse", "--abbrev-ref", "HEAD"}).trim())) {
            git.apply(new String[] {"checkout", "-b", TOPIC_BRANCH});
        }
    }

    private String finishPlanning(String name, String slug, List<String> workPackages) {
        Path folder = workDir.resolve("kitty-specs").resolve(slug);
        write(folder.resolve("plan.md"), PLAN);
        write(folder.resolve("tasks.md"), tasks(workPackages));
        for (String wp : workPackages) {
            write(folder.resolve("tasks").resolve(wp + "-" + module(wp) + ".md"), workPackage(wp));
        }
        commit("plan and tasks for " + name);
        succeed(List.of("spec-kitty", "agent", "mission", "finalize-tasks", "--mission", slug, "--json"));
        Path analysis = workDir.resolveSibling("analysis-" + name + ".md");
        write(analysis, "# Analysis Report\n\nNo issues found. Every requirement maps to a work package.\n");
        succeed(List.of("spec-kitty", "agent", "mission", "record-analysis", "--mission", slug, "--input-file",
                analysis.toString(), "--agent", "claude"));
        slugs.put(name, slug);
        for (String wp : workPackages) {
            lanes.put(key(name, wp), "planned");
        }
        return slug;
    }

    /**
     * Creates the Mission {@code name} on the topic branch and commits a written spec for it, the
     * state {@code setup-plan} starts from. Returns the full Mission slug.
     */
    public String specifyMission(String name) {
        missions.ensureProject();
        onTopicBranch();
        CliResult created = succeed(List.of("spec-kitty", "agent", "mission", "create", name, "--json"));
        String slug = mission(created);
        Matcher coordination = COORDINATION_BRANCH.matcher(created.stdout());
        if (coordination.find()) {
            coordinationBranches.put(name, coordination.group(1));
        }
        write(workDir.resolve("kitty-specs").resolve(slug).resolve("spec.md"), spec(name));
        commit("spec for " + name);
        slugs.put(name, slug);
        return slug;
    }

    /** Walks a planned work package forward, one real step at a time, until it is in {@code lane}. */
    public void advance(String name, String wp, String lane) {
        int target = LANE_ORDER.indexOf(lane);
        if (target < 0) {
            throw new IllegalArgumentException("Unsupported lane '" + lane + "'; use one of " + LANE_ORDER);
        }
        String current = lanes.get(key(name, wp));
        if (current == null) {
            throw new IllegalStateException("Work package " + wp + " of mission '" + name + "' was not planned here");
        }
        for (int step = LANE_ORDER.indexOf(current) + 1; step <= target; step++) {
            enter(name, wp, LANE_ORDER.get(step));
            lanes.put(key(name, wp), LANE_ORDER.get(step));
        }
    }

    /**
     * A reviewer rejects a work package that is in review: its feedback goes to a file outside the
     * repository, as a reviewer's notes would, and {@code move-task --to planned} records it.
     */
    public void reject(String name, String wp, String feedback) {
        if (!"in_review".equals(lanes.get(key(name, wp)))) {
            throw new IllegalStateException("Work package " + wp + " of mission '" + name + "' is not in review");
        }
        Path file = workDir.resolveSibling("feedback-" + wp + "-" + rounds.getOrDefault(key(name, wp), 0) + ".md");
        write(file, "# Review feedback\n\n" + feedback + "\n");
        succeed(List.of("spec-kitty", "agent", "tasks", "move-task", wp, "--to", "planned", "--mission", slug(name),
                "--review-feedback-file", file.toString(), "--agent", REVIEWER));
        lanes.put(key(name, wp), "planned");
        committed.remove(key(name, wp));
    }


    /** The full slug the CLI gave the Mission {@code name}. */
    public String slug(String name) {
        String slug = slugs.get(name);
        if (slug == null) {
            throw new IllegalStateException("No mission '" + name + "' was planned in this scenario");
        }
        return slug;
    }

    /** The coordination branch {@code mission create} reported for the Mission, if it made one. */
    public String coordinationBranch(String name) {
        String branch = coordinationBranches.get(name);
        if (branch == null) {
            throw new IllegalStateException("Mission '" + name + "' has no coordination branch");
        }
        return branch;
    }

    /**
     * The implementer's work: writes the work package's module in its lane worktree, commits it there
     * and ticks its subtask, as an agent does before asking for review. The work package must be in
     * progress.
     */
    public void commitWork(String name, String wp) {
        Path worktree = worktree(name, wp);
        int round = rounds.merge(key(name, wp), 1, Integer::sum);
        write(worktree.resolve("src").resolve(module(wp)).resolve("__init__.py"),
                "GREETING = \"hello from " + wp + ", round " + round + "\"\n");
        git.apply(new String[] {"-C", worktree.toString(), "add", "--", "src/" + module(wp)});
        git.apply(new String[] {"-C", worktree.toString(), "commit", "-m", "implement " + wp});
        succeed(List.of("spec-kitty", "agent", "tasks", "mark-status", subtask(wp), "--status", "done", "--mission", slug(name)));
        committed.add(key(name, wp));
    }

    /**
     * The operator accepts the Mission: every requirement gets a passing acceptance verdict and
     * {@code accept} records the result. Every work package must be approved first.
     */
    public void accept(String name) {
        String slug = slug(name);
        succeed(List.of("spec-kitty", "agent", "acceptance-verdict", "--mission", slug, "--criterion", "FR-001",
                "--result", "pass", "--actor", "operator", "--evidence", "acceptance harness"));
        succeed(List.of("spec-kitty", "accept", "--mission", slug, "--json", "--lenient"));
    }

    /** Ticks the work package's subtask without committing any work, as an agent may do too early. */
    public void markSubtasksDone(String name, String wp) {
        succeed(List.of("spec-kitty", "agent", "tasks", "mark-status", subtask(wp), "--status", "done", "--mission", slug(name)));
    }

    /** The lane worktree {@code implement} created for a work package. */
    public Path worktree(String name, String wp) {
        Path worktree = worktrees.get(key(name, wp));
        if (worktree == null) {
            throw new IllegalStateException("Work package " + wp + " of mission '" + name + "' has no worktree yet");
        }
        return worktree;
    }

    private void enter(String name, String wp, String lane) {
        String slug = slug(name);
        switch (lane) {
            case "in_progress" -> {
                CliResult implement = succeed(List.of("spec-kitty", "agent", "action", "implement", wp, "--mission", slug,
                        "--agent", "claude"));
                Matcher matcher = LANE_WORKTREE.matcher(implement.stdout() + implement.stderr());
                if (singleBranch.contains(name)) {
                    // single_branch: the work package runs in the write checkout itself.
                    worktrees.put(key(name, wp), workDir);
                } else if (matcher.find()) {
                    worktrees.put(key(name, wp), workDir.resolve(matcher.group(1).trim()));
                } else if (!worktrees.containsKey(key(name, wp))) {
                    // A re-implement after a rejection reuses the lane worktree without naming it again.
                    throw new IllegalStateException("No lane worktree in the output of 'implement':\n" + implement);
                }
            }
            case "for_review" -> {
                if (!committed.contains(key(name, wp))) {
                    commitWork(name, wp);
                }
                succeed(List.of("spec-kitty", "agent", "tasks", "move-task", wp, "--to", "for_review", "--mission", slug,
                        "--agent", "claude"));
            }
            case "in_review" -> succeed(List.of("spec-kitty", "agent", "action", "review", wp, "--mission", slug,
                    "--agent", REVIEWER));
            case "approved" -> succeed(List.of("spec-kitty", "agent", "tasks", "move-task", wp, "--to", "approved",
                    "--mission", slug, "--agent", REVIEWER, "--note", "reviewed by the acceptance harness"));
            default -> throw new IllegalArgumentException("Cannot enter lane '" + lane + "'");
        }
    }

    // --- authored content ------------------------------------------------------------------------

    private static final String PLAN = """
            # Implementation Plan

            ## Technical Context

            **Language/Version**: Python 3.12
            **Primary Dependencies**: none
            **Storage**: Filesystem
            """;

    private static String spec(String name) {
        return """
                # %s

                ## Functional Requirements

                | ID | Requirement | Acceptance Criteria | Status |
                | --- | --- | --- | --- |
                | FR-001 | Each work package adds a greeting module. | The module exists and is committed. | proposed |
                """.formatted(name);
    }

    private static String tasks(List<String> workPackages) {
        StringBuilder text = new StringBuilder("# Work Packages\n");
        for (String wp : workPackages) {
            text.append("""

                    ## Work Package %s: %s
                    **Dependencies**: None
                    **Requirement Refs**: FR-001

                    ### Included Subtasks
                    - [ ] %s Create the %s module
                    """.formatted(wp, module(wp), subtask(wp), module(wp)));
        }
        return text.toString();
    }

    private static String workPackage(String wp) {
        return """
                ---
                work_package_id: "%1$s"
                title: "%2$s"
                dependencies: []
                requirement_refs: [FR-001]
                subtasks:
                  - "%3$s"
                owned_files:
                  - "src/%2$s/**"
                authoritative_surface: "src/%2$s/"
                ---

                # Work Package Prompt: %1$s -- %2$s

                - [ ] %3$s Create the %2$s module
                """.formatted(wp, module(wp), subtask(wp));
    }

    /** The module a work package owns: {@code WP01} owns {@code src/wp01/}. */
    private static String module(String wp) {
        return wp.toLowerCase(Locale.ROOT);
    }

    /** The one subtask of a work package: {@code WP01} has {@code T01}. */
    private static String subtask(String wp) {
        return "T" + wp.substring(2);
    }

    // --- plumbing --------------------------------------------------------------------------------

    private static String key(String name, String wp) {
        return name + "/" + wp;
    }

    private static String mission(CliResult created) {
        Matcher matcher = MISSION_SLUG.matcher(created.stdout());
        if (!matcher.find()) {
            throw new IllegalStateException("No mission_slug in the output of 'mission create':\n" + created);
        }
        return matcher.group(1);
    }

    private void commit(String message) {
        git.apply(new String[] {"add", "-A"});
        git.apply(new String[] {"commit", "-m", message});
    }

    private CliResult succeed(List<String> args) {
        CliResult result = cli.apply(args);
        if (result.exitCode() != 0) {
            throw new IllegalStateException("Building the mission lifecycle fixture failed at " + args + ":\n" + result);
        }
        return result;
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
