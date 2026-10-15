package kitty.acceptance.steps;

import static org.assertj.core.api.Assertions.assertThat;

import io.cucumber.java.en.Then;

import kitty.acceptance.driver.CliResult;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Stream;

/** Assert ({@code Then}): check that the post-conditions hold after the action. */
public final class AssertSteps {

    private static final Pattern MISSION_SLUG = Pattern.compile("\"mission_slug\"\\s*:\\s*\"([^\"]+)\"");
    private static final Pattern FEATURE_DIR = Pattern.compile("\"feature_dir\"\\s*:\\s*\"([^\"]+)\"");

    private final ScenarioContext context;

    public AssertSteps(ScenarioContext context) {
        this.context = context;
    }

    @Then("the command succeeds")
    public void theCommandSucceeds() {
        CliResult result = context.lastResult();
        assertThat(result.exitCode()).as("Exit code of the command:%n%s", result).isZero();
    }

    @Then("the command fails")
    public void theCommandFails() {
        CliResult result = context.lastResult();
        assertThat(result.exitCode()).as("Exit code of the command:%n%s", result).isNotZero();
    }

    @Then("the mission {string} is listed")
    public void theMissionIsListed(String handle) {
        List<String> slugs = listedMissionSlugs();
        assertThat(slugs).as("Missions listed by the status command").isNotEmpty();
        assertThat(slugs).as("Missions listed by the status command include the mission '%s'", handle)
                .anyMatch(slug -> isMission(slug, handle));
    }

    @Then("the mission {string} is not listed")
    public void theMissionIsNotListed(String handle) {
        assertThat(listedMissionSlugs()).as("Mission '%s' in the output of the status command", handle)
                .noneMatch(slug -> isMission(slug, handle));
    }

    /** The CLI appends an identifier to the slug it is given, so a mission matches its name or name-plus-suffix. */
    private static boolean isMission(String listedSlug, String handle) {
        return listedSlug.matches(Pattern.quote(handle) + "(-[0-9A-Z]{8})?");
    }

    /** Every {@code mission_slug} value in the output of the last command, in order. */
    private List<String> listedMissionSlugs() {
        Matcher matcher = MISSION_SLUG.matcher(context.lastResult().stdout());
        List<String> slugs = new ArrayList<>();
        while (matcher.find()) {
            slugs.add(matcher.group(1));
        }
        return slugs;
    }

    @Then("the command exits with code {int}")
    public void theCommandExitsWithCode(int code) {
        CliResult result = context.lastResult();
        assertThat(result.exitCode()).as("Exit code of the command:%n%s", result).isEqualTo(code);
    }

    @Then("the JSON field {string} of the output is {string}")
    public void theJsonFieldOfTheOutputIs(String field, String value) {
        Pattern pair = Pattern.compile("\"" + Pattern.quote(field) + "\"\\s*:\\s*\"([^\"]*)\"");
        Matcher matcher = pair.matcher(context.lastResult().stdout());
        assertThat(matcher.find()).as("JSON field '%s' in the output:%n%s", field, context.lastResult()).isTrue();
        assertThat(matcher.group(1)).as("JSON field '%s'", field).isEqualTo(value);
    }

    @Then("the {string} entry of the JSON field {string} of the output is {string}")
    public void theNestedJsonEntryIs(String entry, String field, String value) {
        assertThat(context.lastResult().stdout()).as("%s.%s in the output:%n%s", field, entry, context.lastResult())
                .containsPattern(nestedEntry(field, entry, "\"" + Pattern.quote(value) + "\""));
    }

    @Then("the {string} entry of the JSON field {string} of the output is null")
    public void theNestedJsonEntryIsNull(String entry, String field) {
        assertThat(context.lastResult().stdout()).as("%s.%s in the output:%n%s", field, entry, context.lastResult())
                .containsPattern(nestedEntry(field, entry, "null"));
    }

    /** {@code "field": { ... "entry": <value> ... }} inside one flat JSON object (no nested braces). */
    private static Pattern nestedEntry(String field, String entry, String valuePattern) {
        return Pattern.compile("\"" + Pattern.quote(field) + "\"\\s*:\\s*\\{[^{}]*\"" + Pattern.quote(entry)
                + "\"\\s*:\\s*" + valuePattern);
    }

    @Then("the JSON flag {string} of the output is {word}")
    public void theJsonFlagIs(String field, String literal) {
        assertThat(literal).as("A JSON literal").isIn("true", "false", "null");
        assertThat(context.lastResult().stdout()).as("JSON field '%s' in the output:%n%s", field, context.lastResult())
                .containsPattern("\"" + Pattern.quote(field) + "\"\\s*:\\s*" + literal + "\\b");
    }

    @Then("the file {string} of mission {string} is committed on the current branch")
    public void theMissionFileIsCommitted(String file, String name) {
        assertThat(committedAtHead(missionPath(name, file))).as("'%s' of mission '%s' at HEAD", file, name).isTrue();
    }

    @Then("the file {string} of mission {string} is not committed")
    public void theMissionFileIsNotCommitted(String file, String name) {
        assertThat(committedAtHead(missionPath(name, file))).as("'%s' of mission '%s' at HEAD", file, name).isFalse();
    }

    private String missionPath(String name, String file) {
        Path folder = missionFolder(name);
        return context.world().workDir().relativize(folder).toString().replace('\\', '/') + "/" + file;
    }

    private boolean committedAtHead(String path) {
        return !context.world().git("ls-tree", "--name-only", "HEAD", "--", path).trim().isEmpty();
    }

    @Then("the lanes of mission {string} are {string}")
    public void theLanesOfMissionAre(String name, String expected) {
        Path lanesFile = missionFolder(name).resolve("lanes.json");
        String json;
        try {
            json = Files.readString(lanesFile);
        } catch (IOException e) {
            throw new UncheckedIOException("Could not read " + lanesFile, e);
        }
        Matcher lane = Pattern.compile("\"lane_id\"\\s*:\\s*\"([^\"]+)\"\\s*,\\s*\"wp_ids\"\\s*:\\s*\\[([^\\]]*)\\]").matcher(json);
        List<String> lanes = new ArrayList<>();
        while (lane.find()) {
            lanes.add(lane.group(1) + ": " + String.join(", ", lane.group(2).replaceAll("[\"\\s]", "").split(",")));
        }
        assertThat(String.join("; ", lanes)).as("Lanes of mission '%s' in %s", name, lanesFile).isEqualTo(expected);
    }

    @Then("the lane worktree of the work package {string} of mission {string} still holds its committed work")
    public void theLaneWorktreeStillHoldsItsWork(String wp, String name) {
        Path worktree = context.lifecycle().worktree(name, wp);
        Path module = worktree.resolve("src").resolve(wp.toLowerCase(Locale.ROOT)).resolve("__init__.py");
        assertThat(module).as("The committed work of %s in its lane worktree", wp).isRegularFile();
        try {
            assertThat(Files.readString(module)).as("Contents of %s", module).contains("hello from " + wp);
        } catch (IOException e) {
            throw new UncheckedIOException("Could not read " + module, e);
        }
        assertThat(context.world().git("-C", worktree.toString(), "status", "--porcelain").trim())
                .as("Uncommitted changes in the lane worktree of %s", wp).isEmpty();
    }

    @Then("the output is a JSON object")
    public void theOutputIsAJsonObject() {
        String stdout = context.lastResult().stdout().trim();
        assertThat(stdout).as("stdout of the command:%n%s", context.lastResult()).startsWith("{").endsWith("}");
    }

    @Then("the file {string} exists")
    public void theFileExists(String relative) {
        assertThat(context.world().resolve(relative)).as("File '%s'", relative).isRegularFile();
    }

    @Then("the output mentions {string}")
    public void theOutputMentions(String text) {
        assertThat(flowed(output())).as("Output of the command:%n%s", context.lastResult()).contains(flowed(text));
    }

    @Then("the output does not mention {string}")
    public void theOutputDoesNotMention(String text) {
        assertThat(flowed(output())).as("Output of the command:%n%s", context.lastResult()).doesNotContain(flowed(text));
    }

    /**
     * Text with every run of whitespace turned into one space. The CLI wraps long lines at the
     * terminal width, which is presentation, not part of what it promises to say.
     */
    private static String flowed(String text) {
        return text.replaceAll("\\s+", " ").trim();
    }

    @Then("the output is a single line")
    public void theOutputIsASingleLine() {
        List<String> lines = output().lines().filter(line -> !line.isBlank()).toList();
        assertThat(lines).as("Non-empty lines of the output:%n%s", context.lastResult()).hasSize(1);
    }

    @Then("the output names the folder {string}")
    public void theOutputNamesTheFolder(String relative) {
        Path folder = context.world().resolve(relative);
        assertThat(folder).as("Folder '%s'", relative).isDirectory();
        // The CLI may print the path as given, resolved (macOS /private/var, Windows long names), or
        // with forward slashes (paths git reports on Windows), so any of those spellings counts.
        List<String> spellings = Stream.of(folder.toAbsolutePath().normalize().toString(), realPath(folder).toString())
                .flatMap(path -> Stream.of(path, path.replace('\\', '/'))).distinct().toList();
        assertThat(spellings).as("The output names folder '%s':%n%s", relative, context.lastResult())
                .anyMatch(output()::contains);
    }

    @Then("the git setting {string} is {string}")
    public void theGitSettingIs(String key, String value) {
        assertThat(context.world().gitSetting(key)).as("git config %s", key).isEqualTo(value);
    }

    @Then("a git merge is still in progress")
    public void aGitMergeIsStillInProgress() {
        assertThat(context.world().mergeInProgress()).as("A git merge is still in progress").isTrue();
    }

    @Then("the new mission's folder has a {string} file")
    public void theNewMissionsFolderHasAFile(String name) {
        assertThat(newMissionFolder().resolve(name)).as("'%s' in the new mission's folder", name).isRegularFile();
    }

    @Then("the new mission's folder has a {string} folder")
    public void theNewMissionsFolderHasAFolder(String name) {
        assertThat(newMissionFolder().resolve(name)).as("'%s' in the new mission's folder", name).isDirectory();
    }

    @Then("no work package worktree has been created")
    public void noWorkPackageWorktreeHasBeenCreated() {
        Path worktrees = context.world().resolve(".worktrees");
        if (!Files.isDirectory(worktrees)) {
            return;
        }
        try (Stream<Path> entries = Files.list(worktrees)) {
            // A coordination worktree (<mission>-coord) holds Mission status, not a work package.
            assertThat(entries.map(entry -> entry.getFileName().toString()).toList())
                    .as("Worktrees under .worktrees").allMatch(name -> name.endsWith("-coord"));
        } catch (IOException e) {
            throw new UncheckedIOException("Could not list " + worktrees, e);
        }
    }

    /** stdout and stderr of the last command: where a message lands is not part of the promise. */
    private String output() {
        CliResult result = context.lastResult();
        return result.stdout() + "\n" + result.stderr();
    }

    /** The folder named by {@code feature_dir} in the JSON output of the last command. */
    private Path newMissionFolder() {
        Matcher matcher = FEATURE_DIR.matcher(context.lastResult().stdout());
        assertThat(matcher.find()).as("feature_dir in the output:%n%s", context.lastResult()).isTrue();
        Path folder = Path.of(matcher.group(1).replace("\\\\", "\\"));
        assertThat(folder).as("The new mission's folder").isDirectory();
        return folder;
    }

    private static Path realPath(Path path) {
        try {
            return path.toRealPath();
        } catch (IOException e) {
            throw new UncheckedIOException("Could not resolve " + path, e);
        }
    }

    @Then("the repository's branches are unchanged")
    public void theRepositorysBranchesAreUnchanged() {
        assertThat(context.world().branchesUnchanged()).as("Every local branch still points where it was recorded").isTrue();
    }

    @Then("the working tree has no uncommitted changes to tracked files")
    public void theWorkingTreeHasNoUncommittedChangesToTrackedFiles() {
        assertThat(context.world().git("status", "--porcelain", "--untracked-files=no").trim())
                .as("git status --porcelain --untracked-files=no").isEmpty();
    }

    @Then("the working tree has no uncommitted changes")
    public void theWorkingTreeHasNoUncommittedChanges() {
        assertThat(context.world().uncommittedChanges()).as("git status --porcelain").isEmpty();
    }

    @Then("the file {string} mentions {string}")
    public void theFileMentions(String relative, String text) {
        Path file = context.world().resolve(relative);
        assertThat(file).as("File '%s'", relative).isRegularFile();
        try {
            assertThat(Files.readString(file)).as("Contents of '%s'", relative).contains(text);
        } catch (IOException e) {
            throw new UncheckedIOException("Could not read " + file, e);
        }
    }

    @Then("the file {string} of the mission {string} mentions {string}")
    public void theFileOfTheMissionMentions(String name, String mission, String text) {
        assertThat(missionFile(mission, name)).as("Contents of '%s' of mission '%s'", name, mission).contains(text);
    }

    @Then("the file {string} of the mission {string} does not mention {string}")
    public void theFileOfTheMissionDoesNotMention(String name, String mission, String text) {
        assertThat(missionFile(mission, name)).as("Contents of '%s' of mission '%s'", name, mission).doesNotContain(text);
    }

    private String missionFile(String mission, String name) {
        Path file = missionFolder(mission).resolve(name);
        assertThat(file).as("'%s' of mission '%s'", name, mission).isRegularFile();
        try {
            return Files.readString(file);
        } catch (IOException e) {
            throw new UncheckedIOException("Could not read " + file, e);
        }
    }

    /** The single {@code kitty-specs/<name>} or {@code kitty-specs/<name>-<MID8>} folder of a mission. */
    private Path missionFolder(String handle) {
        Path specs = context.world().resolve("kitty-specs");
        assertThat(specs).as("kitty-specs folder").isDirectory();
        try (Stream<Path> entries = Files.list(specs)) {
            List<Path> matches = entries.filter(Files::isDirectory)
                    .filter(dir -> isMission(dir.getFileName().toString(), handle)).toList();
            assertThat(matches).as("Folders of mission '%s' under kitty-specs", handle).hasSize(1);
            return matches.get(0);
        } catch (IOException e) {
            throw new UncheckedIOException("Could not list " + specs, e);
        }
    }

    @Then("the work package {string} of mission {string} is in lane {string}")
    public void theWorkPackageOfMissionIsInLane(String wp, String name, String lane) {
        CliResult status = context.run(List.of("spec-kitty", "agent", "tasks", "status", "--mission",
                context.lifecycle().slug(name), "--json"));
        assertThat(status.exitCode()).as("Reading the status of mission '%s':%n%s", name, status).isZero();
        assertThat(status.stdout()).as("Lane of %s in the status of mission '%s'", wp, name)
                .containsPattern("\"id\"\\s*:\\s*\"" + Pattern.quote(wp) + "\"[^}]*\"lane\"\\s*:\\s*\"" + Pattern.quote(lane) + "\"");
    }

    @Then("the branch {string} holds no status file of mission {string}")
    public void theBranchHoldsNoStatusFileOfMission(String branch, String name) {
        String prefix = "kitty-specs/" + context.lifecycle().slug(name) + "/status.";
        List<String> files = context.world().git("ls-tree", "-r", "--name-only", branch).lines()
                .filter(path -> path.startsWith(prefix)).toList();
        assertThat(files).as("Status files of mission '%s' on branch '%s'", name, branch).isEmpty();
    }

    @Then("the folder of mission {string} has a non-empty {string} file")
    public void theFolderOfMissionHasANonEmptyFile(String name, String file) {
        Path path = missionFolder(name).resolve(file);
        assertThat(path).as("'%s' in the folder of mission '%s'", file, name).isRegularFile();
        assertThat(missionFile(name, file)).as("Contents of '%s'", path).isNotBlank();
    }

    @Then("the status log on the coordination branch of mission {string} records a move of {string} to {string}")
    public void theCoordinationStatusLogRecordsAMove(String name, String wp, String lane) {
        String log = context.world().git("show", context.lifecycle().coordinationBranch(name) + ":kitty-specs/"
                + context.lifecycle().slug(name) + "/status.events.jsonl");
        Pattern move = Pattern.compile("\"to_lane\"\\s*:\\s*\"" + Pattern.quote(lane) + "\"[^\\n]*\"wp_id\"\\s*:\\s*\""
                + Pattern.quote(wp) + "\"|\"wp_id\"\\s*:\\s*\"" + Pattern.quote(wp) + "\"[^\\n]*\"to_lane\"\\s*:\\s*\""
                + Pattern.quote(lane) + "\"");
        assertThat(log).as("Move of %s to %s in the coordination status log of mission '%s'", wp, lane, name)
                .containsPattern(move);
    }

    @Then("the folder of mission {string} has no {string} file")
    public void theFolderOfMissionHasNoFile(String name, String file) {
        assertThat(missionFolder(name).resolve(file)).as("'%s' in the folder of mission '%s'", file, name).doesNotExist();
    }

    @Then("the status log on the coordination branch of mission {string} mentions {string}")
    public void theCoordinationStatusLogMentions(String name, String text) {
        String log = context.world().git("show", context.lifecycle().coordinationBranch(name) + ":kitty-specs/"
                + context.lifecycle().slug(name) + "/status.events.jsonl");
        assertThat(log).as("Status log on the coordination branch of mission '%s'", name).contains(text);
    }

    @Then("the history of branch {string} mentions {string}")
    public void theHistoryOfBranchMentions(String branch, String text) {
        assertThat(context.world().git("log", "--format=%s", branch)).as("Commit subjects of branch '%s'", branch)
                .containsIgnoringCase(text);
    }

    @Then("the file {string} of mission {string} on the coordination branch mentions {string}")
    public void theCoordinationFileMentions(String file, String name, String text) {
        String contents = context.coordinationFile(name, file);
        assertThat(contents).as("'%s' of mission '%s' on its coordination branch", file, name).isNotNull();
        assertThat(contents).as("Contents of '%s' on the coordination branch", file).contains(text);
    }

    @Then("the coordination branch of mission {string} has no file {string}")
    public void theCoordinationBranchHasNoFile(String name, String file) {
        assertThat(context.coordinationFile(name, file)).as("'%s' of mission '%s' on its coordination branch", file, name)
                .isNull();
    }

    @Then("the file {string} of mission {string} on the coordination branch is unchanged")
    public void theCoordinationFileIsUnchanged(String file, String name) {
        assertThat(context.coordinationFile(name, file)).as("'%s' of mission '%s' on its coordination branch", file, name)
                .isEqualTo(context.recordedCoordinationFile(name, file));
    }

    @Then("the current branch is {string}")
    public void theCurrentBranchIs(String branch) {
        assertThat(context.world().git("rev-parse", "--abbrev-ref", "HEAD").trim()).as("Checked-out branch").isEqualTo(branch);
    }

    @Then("the current branch is the mission branch of mission {string}")
    public void theCurrentBranchIsTheMissionBranch(String name) {
        theCurrentBranchIs(context.lifecycle().missionBranch(name));
    }

    @Then("the mission branch of mission {string} no longer exists")
    public void theMissionBranchNoLongerExists(String name) {
        assertThat(branchExists(context.lifecycle().missionBranch(name))).as("Mission branch of mission '%s'", name).isFalse();
    }

    @Then("the mission branch of mission {string} still exists")
    public void theMissionBranchStillExists(String name) {
        assertThat(branchExists(context.lifecycle().missionBranch(name))).as("Mission branch of mission '%s'", name).isTrue();
    }

    @Then("the old tip of the mission branch of mission {string} can be restored from its kept ref")
    public void theOldTipCanBeRestored(String name) {
        String branch = context.lifecycle().missionBranch(name);
        assertThat(context.world().git("rev-parse", "refs/spec-kitty/discarded/" + branch).trim())
                .as("Kept ref of the discarded branch '%s'", branch).isEqualTo(context.recordedMissionBranchTip(name));
        assertThat(flowed(output())).as("Output of the command").contains("git branch " + branch + " refs/spec-kitty/discarded/" + branch);
    }

    @Then("the branch {string} has no folder of mission {string}")
    public void theBranchHasNoFolderOfMission(String branch, String name) {
        String prefix = "kitty-specs/" + context.lifecycle().slug(name) + "/";
        assertThat(context.world().git("ls-tree", "-r", "--name-only", branch).lines().filter(path -> path.startsWith(prefix)).toList())
                .as("Files of mission '%s' on branch '%s'", name, branch).isEmpty();
    }

    @Then("the branch {string} has the file {string} mentioning {string}")
    public void theBranchHasTheFileMentioning(String branch, String path, String text) {
        assertThat(context.world().git("show", branch + ":" + path)).as("'%s' on branch '%s'", path, branch).contains(text);
    }

    @Then("the branch {string} tracks no file under {string}")
    public void theBranchTracksNoFileUnder(String branch, String prefix) {
        assertThat(context.world().git("ls-tree", "-r", "--name-only", branch).lines()
                .filter(path -> path.equals(prefix) || path.startsWith(prefix.endsWith("/") ? prefix : prefix + "/")).toList())
                .as("Files under '%s' on branch '%s'", prefix, branch).isEmpty();
    }

    @Then("the file {string} is not tracked by git")
    public void theFileIsNotTrackedByGit(String relative) {
        assertThat(context.world().git("ls-files", "--", relative).trim()).as("git ls-files %s", relative).isEmpty();
    }

    private boolean branchExists(String branch) {
        return context.world().git("branch", "--list", branch).trim().length() > 0;
    }

    @Then("the folder {string} exists")
    public void theFolderExists(String relative) {
        assertThat(context.world().resolve(relative)).as("Folder '%s'", relative).isDirectory();
    }

    @Then("the folder {string} is not empty")
    public void theFolderIsNotEmpty(String relative) {
        Path folder = context.world().resolve(relative);
        assertThat(folder).as("Folder '%s'", relative).isDirectory();
        try (Stream<Path> entries = Files.list(folder)) {
            assertThat(entries.findAny()).as("Contents of folder '%s'", relative).isPresent();
        } catch (IOException e) {
            throw new UncheckedIOException("Could not list " + folder, e);
        }
    }

    @Then("the folder {string} is unchanged")
    public void theFolderIsUnchanged(String relative) {
        assertUnchanged("Folder", relative);
    }

    @Then("the file {string} is unchanged")
    public void theFileIsUnchanged(String relative) {
        assertUnchanged("File", relative);
    }

    @Then("no {string} folder exists in {string}")
    public void noFolderExistsIn(String name, String parent) {
        Path parentDir = context.world().resolve(parent);
        assertThat(parentDir).as("Parent folder '%s'", parent).isDirectory();
        assertThat(parentDir.resolve(name)).as("'%s' in '%s'", name, parent).doesNotExist();
    }

    @Then("the repository HEAD is unchanged")
    public void theRepositoryHeadIsUnchanged() {
        assertThat(context.world().headUnchanged()).as("HEAD is unchanged since it was recorded").isTrue();
    }

    @Then("the repository has no new commits")
    public void theRepositoryHasNoNewCommits() {
        assertThat(context.world().commitCountUnchanged())
                .as("Commit count is unchanged since it was recorded")
                .isTrue();
    }

    private void assertUnchanged(String kind, String relative) {
        assertThat(context.world().isUnchanged(relative))
                .as("%s '%s' is unchanged since it was recorded", kind, relative)
                .isTrue();
    }
}
