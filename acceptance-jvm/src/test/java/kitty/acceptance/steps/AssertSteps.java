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

    @Then("the output mentions {string}")
    public void theOutputMentions(String text) {
        assertThat(output()).as("Output of the command:%n%s", context.lastResult()).contains(text);
    }

    @Then("the output does not mention {string}")
    public void theOutputDoesNotMention(String text) {
        assertThat(output()).as("Output of the command:%n%s", context.lastResult()).doesNotContain(text);
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
