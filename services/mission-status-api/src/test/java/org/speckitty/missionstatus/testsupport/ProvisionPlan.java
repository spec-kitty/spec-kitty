package org.speckitty.missionstatus.testsupport;

import org.speckitty.missionstatus.testsupport.RealPermissionFixture.NotRun;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.FileVisitResult;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.SimpleFileVisitor;
import java.nio.file.attribute.BasicFileAttributeView;
import java.nio.file.attribute.BasicFileAttributes;
import java.nio.file.attribute.FileTime;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import org.junit.jupiter.api.Assumptions;

/**
 * Applies a fixture's {@code PROVISION_PLAN} to the scratch copy the Java tests read: the Java twin of {@code apply_provision_plan} in
 * {@code tests/contract/_mission_status_conformance.py}, with the same grammar (data-model.md section 9.3). The committed trees hold no
 * {@code .git}, no symbolic link, no modification time and no host path (NFR-007, D-42, D-48); this plan is how they get them.
 *
 * <p>The plan is a file named {@code PROVISION_PLAN} at the top level of the <em>source</em> fixture directory (ruling OO-4). It is read
 * from there and never from the scratch root; a stray copy that the shared copy step left in the scratch tree is removed so that it can
 * not appear in a listing. Tab-separated, verb-first lines, applied in file order; blank lines and lines starting with {@code #} are
 * ignored:
 *
 * <ul>
 *   <li>{@code link path target}: a symbolic link at {@code path} to the root-relative {@code target} ({@code @outside/x} points into a
 *       sibling directory made from the fixture's {@code outside/} tree). A host that cannot make a link records
 *       {@code not run: link unsupported} and skips the test;
 *   <li>{@code gitentry path}: a plain file at {@code path} (a {@code .git} entry; its content is irrelevant to a stat);
 *   <li>{@code mtime path epochSeconds}: the modification time (of a link itself, never of its target);
 *   <li>{@code dir path}: a directory (the lane worktrees);
 *   <li>{@code write path text}: a file with {@code text} as its content, no newline added; a non-ASCII name is made this way and needs a
 *       UTF-8 host ({@link Utf8Host});
 *   <li>{@code substitute path marker fragment...}: the marker text of a committed file replaced by the joined fragments, so that no host
 *       path, address or credential shape is committed whole. A marker that is not in the file is an error, except on a second run, which
 *       finds the replacement already there.
 * </ul>
 *
 * <p>Every path must be relative and free of {@code ..}, and the real parent of what is written must lie inside the scratch root, even
 * when an earlier line made a link: nothing is written outside it. The one thing outside is the {@code outside} sibling directory a
 * {@code @outside/} target needs. Applying a plan twice gives the same tree.
 */
public final class ProvisionPlan {

  /** The name of the plan file, at the top level of a fixture. */
  public static final String FILE = "PROVISION_PLAN";

  static final String OUTSIDE_PREFIX = "@outside/";
  static final String OUTSIDE_TREE = "outside";

  /** One line of a plan: the verb and its tab-separated arguments. */
  public record Step(String verb, List<String> arguments) {
    public Step {
      arguments = List.copyOf(arguments);
    }
  }

  /** Creates a symbolic link; a seam so that a host without links can be simulated. */
  @FunctionalInterface
  interface LinkMaker {
    void link(Path link, Path target) throws IOException;
  }

  private ProvisionPlan() {}

  /** Applies the plan of {@code fixtureDir} (if it has one) to {@code scratchRoot} and removes any stray copy of the plan from the scratch tree. */
  public static void apply(Path fixtureDir, Path scratchRoot) {
    apply(fixtureDir, scratchRoot, Files::createSymbolicLink, NotRun.DEFAULT_FILE);
  }

  static void apply(Path fixtureDir, Path scratchRoot, LinkMaker links, Path notRunReport) {
    removeStrayPlans(scratchRoot);
    Path plan = fixtureDir.resolve(FILE);
    if (!Files.isRegularFile(plan, LinkOption.NOFOLLOW_LINKS)) {
      return;
    }
    String id = "provision:" + fixtureDir.getFileName();
    for (Step step : parse(read(plan))) {
      applyStep(step, fixtureDir, scratchRoot, links, notRunReport, id);
    }
  }

  /** The steps of a plan text; a line that is none of the six verbs with the right number of arguments is refused. */
  public static List<Step> parse(String text) {
    List<Step> steps = new ArrayList<>();
    for (String line : text.split("\r?\n", -1)) {
      if (line.isBlank() || line.startsWith("#")) {
        continue;
      }
      List<String> parts = Arrays.asList(line.split("\t", -1));
      Step step = new Step(parts.get(0), parts.subList(1, parts.size()));
      if (!wellFormed(step)) {
        throw new IllegalArgumentException(FILE + ": unusable line");
      }
      steps.add(step);
    }
    return List.copyOf(steps);
  }

  private static boolean wellFormed(Step step) {
    int arguments = step.arguments().size();
    return switch (step.verb()) {
      case "link", "mtime", "write" -> arguments == 2;
      case "gitentry", "dir" -> arguments == 1;
      case "substitute" -> arguments >= 3;
      default -> false;
    };
  }

  private static void applyStep(Step step, Path fixtureDir, Path root, LinkMaker links, Path report, String id) {
    List<String> a = step.arguments();
    try {
      switch (step.verb()) {
        case "link" -> link(fixtureDir, root, a.get(0), a.get(1), links, report);
        case "gitentry" -> write(root, a.get(0), "gitdir: fixture\n", id);
        case "mtime" -> mtime(root, a.get(0), a.get(1));
        case "dir" -> Files.createDirectories(inside(root, a.get(0), true));
        case "write" -> write(root, a.get(0), a.get(1), id);
        case "substitute" -> substitute(root, a.get(0), a.get(1), String.join("", a.subList(2, a.size())));
        default -> throw new IllegalArgumentException(FILE + ": unusable line");
      }
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    }
  }

  // ---- the verbs -------------------------------------------------------------------------------------------------------------

  private static void link(Path fixtureDir, Path root, String path, String target, LinkMaker links, Path report) throws IOException {
    Path link = inside(root, path, true);
    Files.createDirectories(link.getParent());
    Path text;
    if (target.startsWith(OUTSIDE_PREFIX)) {
      Path outside = root.resolveSibling(OUTSIDE_TREE);
      Path source = fixtureDir.resolve(OUTSIDE_TREE);
      if (Files.isDirectory(source)) {
        ProjectHeaderMaterialisation.copyTree(source, outside);
      }
      text = outside.resolve(target.substring(OUTSIDE_PREFIX.length()));
    } else {
      text = link.getParent().relativize(inside(root, target, false));
    }
    if (Files.isSymbolicLink(link) && Files.readSymbolicLink(link).equals(text)) {
      return;
    }
    Files.deleteIfExists(link);
    try {
      links.link(link, text);
    } catch (IOException | UnsupportedOperationException | SecurityException unsupported) {
      NotRun.record(report, "not run: link unsupported: " + fixtureDir.getFileName());
      Assumptions.abort("not run: link unsupported");
    }
  }

  private static void write(Path root, String path, String text, String id) throws IOException {
    if (!path.chars().allMatch(c -> c < 0x80)) {
      Utf8Host.assumeUtf8(id);
    }
    Path target = inside(root, path, true);
    Files.createDirectories(target.getParent());
    if (Files.isSymbolicLink(target)) {
      throw new IllegalArgumentException(FILE + ": a write would follow a link");
    }
    Files.writeString(target, text, StandardCharsets.UTF_8);
  }

  private static void mtime(Path root, String path, String epochSeconds) throws IOException {
    Path target = inside(root, path, true);
    FileTime time = FileTime.from(Instant.ofEpochSecond(Long.parseLong(epochSeconds)));
    // follow no link: the modification time of a link is the link's own, as the listing shows it
    Files.getFileAttributeView(target, BasicFileAttributeView.class, LinkOption.NOFOLLOW_LINKS).setTimes(time, time, null);
  }

  private static void substitute(Path root, String path, String marker, String replacement) throws IOException {
    Path target = inside(root, path, false);
    if (!realParentInside(root, target) || !realInside(root, target)) {
      throw new IllegalArgumentException(FILE + ": the file leaves the project root");
    }
    String content = Files.readString(target, StandardCharsets.UTF_8);
    if (content.contains(marker)) {
      Files.writeString(target, content.replace(marker, replacement), StandardCharsets.UTF_8);
    } else if (!content.contains(replacement) || replacement.isEmpty()) {
      throw new IllegalArgumentException(FILE + ": the marker is not in the file");
    }
  }

  // ---- containment -----------------------------------------------------------------------------------------------------------

  /** {@code relative} below {@code root}: an absolute path or one with {@code ..} is refused; for a write, so is a real parent outside the root. */
  private static Path inside(Path root, String relative, boolean forWrite) {
    Path path = Path.of(relative);
    if (relative.isEmpty() || path.isAbsolute() || hasParentSegment(path)) {
      throw new IllegalArgumentException(FILE + ": a path leaves the project root");
    }
    Path target = root.resolve(path);
    if (forWrite && !realParentInside(root, target)) {
      throw new IllegalArgumentException(FILE + ": a path leaves the project root through a link");
    }
    return target;
  }

  private static boolean hasParentSegment(Path path) {
    for (Path part : path) {
      if (part.toString().equals("..")) {
        return true;
      }
    }
    return false;
  }

  /** Whether the deepest existing ancestor of {@code target}, with every link resolved, is inside the real root. */
  private static boolean realParentInside(Path root, Path target) {
    try {
      Path ancestor = target.getParent();
      while (ancestor != null && !Files.exists(ancestor)) {
        ancestor = ancestor.getParent();
      }
      return ancestor != null && ancestor.toRealPath().startsWith(root.toRealPath());
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    }
  }

  private static boolean realInside(Path root, Path target) {
    try {
      return target.toRealPath().startsWith(root.toRealPath());
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    }
  }

  // ---- the stray copy --------------------------------------------------------------------------------------------------------

  /**
   * The shared copy step ({@code ProjectHeaderMaterialisation}) does not list {@code PROVISION_PLAN} among the entries it leaves out, so
   * the plan can land at the scratch root, and a plan sitting inside a Mission directory would land there too. A plan is never part of
   * the artifact space: every regular file of that name below the scratch root is removed (links are not followed).
   */
  static void removeStrayPlans(Path scratchRoot) {
    if (!Files.isDirectory(scratchRoot, LinkOption.NOFOLLOW_LINKS)) {
      return;
    }
    try {
      Files.walkFileTree(
          scratchRoot,
          new SimpleFileVisitor<>() {
            @Override
            public FileVisitResult visitFile(Path file, BasicFileAttributes attributes) throws IOException {
              if (attributes.isRegularFile() && file.getFileName().toString().equals(FILE)) {
                Files.delete(file);
              }
              return FileVisitResult.CONTINUE;
            }
          });
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    }
  }

  private static String read(Path plan) {
    try {
      return Files.readString(plan, StandardCharsets.UTF_8);
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    }
  }
}
