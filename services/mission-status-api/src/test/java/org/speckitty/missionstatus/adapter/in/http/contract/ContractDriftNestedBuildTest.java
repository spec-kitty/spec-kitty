package org.speckitty.missionstatus.adapter.in.http.contract;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.regex.Pattern;
import java.util.stream.Stream;
import org.gradle.testkit.runner.BuildResult;
import org.gradle.testkit.runner.GradleRunner;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;
import org.junit.jupiter.api.io.TempDir;

/**
 * AC-11c, generated mode (WP10 T056 step 2; DD-63, DD-66, DD-67): a nested build of a COPY of the service sources and a COPY of the
 * contract compiles when the copy is unmutated, and FAILS with a missing-symbol error when one property of MissionOverview is renamed
 * or one required property of Project is removed in the contract copy. The hand-written {@code ContractDriftProbe} holds one compile
 * time reference per mutation target. Runs in the kit source set (name ends in NestedBuildTest) through {@code ./gradlew kitTest}.
 */
class ContractDriftNestedBuildTest {

  private static final String CANNOT_FIND = "cannot find symbol";

  @Test
  @Timeout(1800)
  void theBuildIsInGeneratedModeAndTheProbeLivesInTheHttpPackage() throws IOException {
    Path project = Path.of(requiredProperty("kit.projectDir"));
    String script = Files.readString(project.resolve("build.gradle.kts"), StandardCharsets.UTF_8);
    assertThat(script).as("generated mode").contains("generatorName.set(\"spring\")").contains("org.speckitty.missionstatus.adapter.in.http.api").contains("org.speckitty.missionstatus.adapter.in.http.model");
    Path probe = project.resolve("src/main/java/org/speckitty/missionstatus/adapter/in/http/ContractDriftProbe.java");
    assertThat(probe).as("the probe was moved, not dropped").isRegularFile();
    String text = Files.readString(probe, StandardCharsets.UTF_8);
    assertThat(text).contains("new MissionOverview().blockedCount(1)").contains("new Project().currentBranch(\"main\")");
  }

  @Test
  @Timeout(1800)
  void renamingAMissionOverviewPropertyOrRemovingARequiredProjectPropertyBreaksTheNestedBuild(@TempDir Path workDir) throws IOException {
    Path original = Path.of(requiredProperty("kit.projectDir"));
    Path copy = workDir.resolve("service");
    copyService(original, copy);

    // positive control: the unmutated copy of the contract compiles
    Path control = workDir.resolve("contract-control");
    copyTree(Path.of(requiredProperty("kit.contractRoot")), control);
    BuildResult built = runner(copy, control).build();
    assertThat(built.getOutput()).doesNotContain(CANNOT_FIND);

    // mutation 1: rename blockedCount (property and required entry) in the MissionOverview source schema
    Path renamed = workDir.resolve("contract-rename");
    copyTree(Path.of(requiredProperty("kit.contractRoot")), renamed);
    Path head = renamed.resolve("mission-status/schemas/MissionHead.yaml");
    String before = Files.readString(head, StandardCharsets.UTF_8);
    String after = before.replace("blockedCount", "blockedTotal");
    assertThat(after).as("the mutation changed the schema").isNotEqualTo(before);
    Files.writeString(head, after, StandardCharsets.UTF_8);
    BuildResult renamedResult = runner(copy, renamed).buildAndFail();
    assertThat(renamedResult.getOutput()).contains(CANNOT_FIND).contains("blockedCount");

    // mutation 2: remove the required property currentBranch from Project
    Path removed = workDir.resolve("contract-remove");
    copyTree(Path.of(requiredProperty("kit.contractRoot")), removed);
    Path projectSchema = removed.resolve("mission-status/schemas/Project.yaml");
    String projectBefore = Files.readString(projectSchema, StandardCharsets.UTF_8);
    String projectAfter = dropCurrentBranch(projectBefore);
    assertThat(projectAfter).as("the mutation changed the schema").isNotEqualTo(projectBefore).doesNotContain("currentBranch:");
    Files.writeString(projectSchema, projectAfter, StandardCharsets.UTF_8);
    BuildResult removedResult = runner(copy, removed).buildAndFail();
    assertThat(removedResult.getOutput()).contains(CANNOT_FIND).contains("currentBranch");
  }

  /** One mutation target: the schema file, the member renamed in it, and the probe expression that must stop compiling. */
  private record Target(String schema, String member, String probeExpression) {}

  /** WP06 (P2, FR-015, AC-15.3): one target per model of the five detail operations; the expression text is the probe's own. */
  static final List<Target> DETAIL_TARGETS =
      List.of(
          new Target("Actor", "tool", "new Actor().tool(\"claude\")"),
          new Target("ArtifactContent", "sizeBytes", "new ArtifactContent().sizeBytes(1L)"),
          new Target("ArtifactEntry", "modifiedAt", "new ArtifactEntry().modifiedAt("),
          new Target("ArtifactListing", "truncated", "new ArtifactListing().truncated(false)"),
          new Target("ArtifactReference", "kind", "new ArtifactReference().kind(null)"),
          new Target("ArtifactReferences", "spec", "new ArtifactReferences().spec(null)"),
          new Target("ArtifactRefusal", "code", "new ArtifactRefusal().code(ArtifactRefusal.CodeEnum.NOT_FOUND)"),
          new Target("Assignment", "agentProfileVersion", "new Assignment().agentProfileVersion("),
          new Target("Authored", "agentProfile", "new Authored().agentProfile("),
          new Target("Cancellation", "reasonSource", "new Cancellation().reasonSource(null)"),
          new Target("DependencyRef", "wpId", "new DependencyRef().wpId("),
          new Target("HistoryEntry", "reviewVerdict", "new HistoryEntry().reviewVerdict(null)"),
          new Target("MissionDetail", "workPackages", "new MissionDetail().addWorkPackagesItem(null)"),
          new Target("MissionPhase", "basis", "new MissionPhase().basis(null)"),
          new Target("MissionProgress", "doneCount", "new MissionProgress().doneCount(1)"),
          new Target("StatusLaneCounts", "planned", "new StatusLaneCounts().planned(1)"),
          new Target("StreamCursor", "invariant", "new StreamCursor().invariant(\"x\")"),
          new Target("OwnedFile", "isGlob", "new OwnedFile().isGlob(false)"),
          new Target("Readiness", "satisfied", "new Readiness().satisfied(true)"),
          new Target("Review", "latestResult", "new Review().latestResult(null)"),
          new Target("ReviewCycle", "artifactPath", "new ReviewCycle().artifactPath("),
          new Target("ReviewOverride", "complete", "new ReviewOverride().complete(true)"),
          new Target("ReviewResult", "reference", "new ReviewResult().reference("),
          new Target("Staleness", "minutesSinceCommit", "new Staleness().minutesSinceCommit("),
          new Target("Subtask", "id", "new Subtask().id("),
          new Target("SubtaskProgress", "total", "new SubtaskProgress().total(1)"),
          // the generated twin of the hand record dto.WorkPackage: its drift sensor (research.md, Plan defects found, item 1)
          new Target("WorkPackage", "forceCount", "new WorkPackage().forceCount(1)"),
          new Target("WorkPackageDetail", "artifactReferences", "new WorkPackageDetail().artifactReferences(null)"),
          new Target("WorkPackageDetailRefusal", "code", "new WorkPackageDetailRefusal().code(WorkPackageDetailRefusal.CodeEnum.NOT_FOUND)"),
          new Target("WorkPackageSummary", "lastTransitionAt", "new WorkPackageSummary().lastTransitionAt("),
          new Target("Workspace", "worktreePresent", "new Workspace().worktreePresent(true)"));

  @Test
  @Timeout(1800)
  void everyDetailModelHasAProbeReferenceThatThePinnedExpressionsQuote() throws IOException {
    Path project = Path.of(requiredProperty("kit.projectDir"));
    String probe = Files.readString(project.resolve("src/main/java/org/speckitty/missionstatus/adapter/in/http/ContractDriftProbe.java"), StandardCharsets.UTF_8);
    assertThat(DETAIL_TARGETS).hasSizeGreaterThanOrEqualTo(31);
    for (Target target : DETAIL_TARGETS) {
      assertThat(probe).as("the probe holds the reference of %s", target.schema()).contains(target.probeExpression());
    }
    assertThat(probe).as("the hand record is read next to its twin").contains("handWorkPackageForceCount");
  }

  @Test
  @Timeout(1800)
  void renamingOneMemberOfEveryDetailModelBreaksTheNestedBuildAtItsProbeReference(@TempDir Path workDir) throws IOException {
    Path original = Path.of(requiredProperty("kit.projectDir"));
    Path copy = workDir.resolve("service");
    copyService(original, copy);

    // positive control: the unmutated contract compiles with the larger model set and the larger probe
    Path control = workDir.resolve("contract-control");
    copyTree(Path.of(requiredProperty("kit.contractRoot")), control);
    assertThat(runner(copy, control).build().getOutput()).doesNotContain(CANNOT_FIND);

    // every target renamed in ONE contract copy: javac reports every missing symbol of the probe in one run, and each report quotes
    // the probe line, so one build shows that each reference is red on its own member
    Path mutated = workDir.resolve("contract-rename-all");
    copyTree(Path.of(requiredProperty("kit.contractRoot")), mutated);
    for (Target target : DETAIL_TARGETS) {
      Path schema = mutated.resolve("mission-status/schemas/" + target.schema() + ".yaml");
      String before = Files.readString(schema, StandardCharsets.UTF_8);
      String after = renameMember(before, target.member());
      assertThat(after).as("the mutation of %s.%s changed the schema", target.schema(), target.member()).isNotEqualTo(before);
      Files.writeString(schema, after, StandardCharsets.UTF_8);
    }
    String output = runner(copy, mutated).buildAndFail().getOutput();
    assertThat(output).contains(CANNOT_FIND);
    for (Target target : DETAIL_TARGETS) {
      assertThat(output).as("the probe reference of %s stops compiling when %s is renamed", target.schema(), target.member()).contains(target.probeExpression());
    }
  }

  /** Renames every whole-word occurrence of {@code member} (the property key and its required entry) by appending {@code Drift}. */
  static String renameMember(String yaml, String member) {
    return Pattern.compile("(?<![A-Za-z0-9_])" + Pattern.quote(member) + "(?![A-Za-z0-9_])").matcher(yaml).replaceAll(member + "Drift");
  }

  /** Removes currentBranch from the required list and deletes its property block. */
  static String dropCurrentBranch(String yaml) {
    String withoutRequired = yaml.replace("currentBranch, ", "");
    StringBuilder out = new StringBuilder();
    boolean skipping = false;
    for (String line : withoutRequired.split("\n", -1)) {
      if (line.startsWith("  currentBranch:")) {
        skipping = true;
        continue;
      }
      if (skipping && (line.startsWith("    ") || line.isBlank())) {
        continue;
      }
      skipping = false;
      out.append(line).append('\n');
    }
    return out.substring(0, out.length() - 1);
  }

  private static GradleRunner runner(Path copy, Path contractRoot) {
    return GradleRunner.create()
        .withProjectDir(copy.toFile())
        .withTestKitDir(Path.of(requiredProperty("kit.gradleUserHome")).toFile())
        .withArguments(List.of("--offline", "-PcontractRoot=" + contractRoot, "compileJava"));
  }

  private static void copyService(Path original, Path copy) throws IOException {
    Files.createDirectories(copy);
    for (String name : List.of("build.gradle.kts", "settings.gradle.kts", "gradle.properties", "gradlew", "gradlew.bat")) {
      Files.copy(original.resolve(name), copy.resolve(name));
    }
    copyTree(original.resolve("gradle"), copy.resolve("gradle"));
    copyTree(original.resolve("src/main/java"), copy.resolve("src/main/java"));
  }

  private static void copyTree(Path from, Path to) throws IOException {
    try (Stream<Path> paths = Files.walk(from)) {
      for (Path path : (Iterable<Path>) paths::iterator) {
        Path target = to.resolve(from.relativize(path).toString());
        if (Files.isDirectory(path)) {
          Files.createDirectories(target);
        } else {
          Files.copy(path, target);
        }
      }
    } catch (UncheckedIOException e) {
      throw e.getCause();
    }
  }

  private static String requiredProperty(String name) {
    String value = System.getProperty(name);
    assertThat(value).as("system property %s (set by the kitTest task)", name).isNotBlank();
    return value;
  }
}
