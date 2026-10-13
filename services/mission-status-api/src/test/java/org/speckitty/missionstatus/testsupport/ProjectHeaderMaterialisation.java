package org.speckitty.missionstatus.testsupport;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.FileVisitResult;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.SimpleFileVisitor;
import java.nio.file.attribute.BasicFileAttributes;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Stream;

/**
 * The shared materialisation step: it turns a committed static fixture tree into a project root, with the rules the Python side runs
 * ({@code tests/contract/_mission_status_conformance.py}, {@code provision}) and the manifest's {@code provisioning} section states:
 *
 * <ul>
 *   <li>the tree is copied without {@link #NOT_COPIED} (provisioning inputs, never copied as they are);
 *   <li>a {@code HEAD} file is installed as {@code .git/HEAD}; a {@code GITDIR_POINTER} file is installed as the regular file
 *       {@code .git} and {@code gitdir-target/} is copied beside it, so its {@code HEAD} stays where it was. No {@code git init}, no
 *       commit, no git binary;
 *   <li>{@code coord-worktree/<mission-dir>/} (a registered coordination worktree on the Python side) and
 *       {@code husk-worktree/<mission-dir>/} (a stale unregistered one) are both installed as plain directories at
 *       {@code .worktrees/<slug>-<mid8>-coord}: the service reads no git, so the two are the same tree to it;
 *   <li>a {@code SYMLINK_PLAN} is run at test time: one {@code link<TAB>target} per line, relative to the project root, the target
 *       relative to the link's own directory, or {@code @outside/<path>} for a sibling directory built from the fixture's
 *       {@code outside/} tree.
 * </ul>
 */
public final class ProjectHeaderMaterialisation {

  /** The fixture entries (at the top level of a fixture) that are provisioning inputs and are not copied into the project root. */
  public static final Set<String> NOT_COPIED = Set.of("golden", "HEAD", "GITDIR_POINTER", "gitdir-target", "coord-worktree", "husk-worktree", "SYMLINK_PLAN", "outside");

  private static final String OUTSIDE_PREFIX = "@outside/";
  private static final String PRIMARY_BRANCH = "main";

  private ProjectHeaderMaterialisation() {}

  /** Materialises {@code fixtureDir} into the existing empty directory {@code projectRoot}. */
  public static void materialise(Path fixtureDir, Path projectRoot) {
    try {
      copyPrimaryTree(fixtureDir, projectRoot);
      installHead(fixtureDir, projectRoot);
      installCoordination(fixtureDir, projectRoot);
      installSymlinks(fixtureDir, projectRoot);
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    }
  }

  /** {@code coord_dir_name}: {@code <slug>-<mid8>-coord}, with the mid8 added only when the slug does not already end with it. */
  public static String coordinationDirName(String slug, String mid8) {
    String missionDir = slug.endsWith("-" + mid8) ? slug : slug + "-" + mid8;
    return missionDir + "-coord";
  }

  private static void copyPrimaryTree(Path fixtureDir, Path projectRoot) throws IOException {
    try (Stream<Path> entries = Files.list(fixtureDir)) {
      for (Path entry : entries.sorted().toList()) {
        if (!NOT_COPIED.contains(entry.getFileName().toString())) {
          copyTree(entry, projectRoot.resolve(entry.getFileName().toString()));
        }
      }
    }
  }

  private static void installHead(Path fixtureDir, Path projectRoot) throws IOException {
    Path pointer = fixtureDir.resolve("GITDIR_POINTER");
    Path head = fixtureDir.resolve("HEAD");
    if (Files.isRegularFile(pointer)) {
      Files.copy(pointer, projectRoot.resolve(".git"));
      copyTree(fixtureDir.resolve("gitdir-target"), projectRoot.resolve("gitdir-target"));
    } else if (Files.isRegularFile(head)) {
      Files.createDirectories(projectRoot.resolve(".git"));
      Files.copy(head, projectRoot.resolve(".git").resolve("HEAD"));
    } else if (needsGit(fixtureDir)) {
      // the oracle run provisions these fixtures with `git init -b main`; that is the whole of the repository the service reads
      Files.createDirectories(projectRoot.resolve(".git"));
      Files.writeString(projectRoot.resolve(".git").resolve("HEAD"), "ref: refs/heads/" + PRIMARY_BRANCH + "\n", StandardCharsets.UTF_8);
    }
  }

  /** The Python rule {@code needs_git}: a coordination worktree, a husk, or a Mission whose {@code meta.json} declares a coordination branch. */
  @SuppressWarnings("unchecked")
  static boolean needsGit(Path fixtureDir) throws IOException {
    if (Files.isDirectory(fixtureDir.resolve("coord-worktree")) || Files.isDirectory(fixtureDir.resolve("husk-worktree"))) {
      return true;
    }
    Path specs = fixtureDir.resolve("kitty-specs");
    if (!Files.isDirectory(specs)) {
      return false;
    }
    try (Stream<Path> missions = Files.list(specs)) {
      for (Path mission : missions.filter(Files::isDirectory).toList()) {
        Path meta = mission.resolve("meta.json");
        if (!Files.isRegularFile(meta)) {
          continue;
        }
        try {
          if (CanonicalJson.parse(Files.readAllBytes(meta)) instanceof Map<?, ?> document && truthy(document.get("coordination_branch"))) {
            return true;
          }
        } catch (IllegalArgumentException unparseable) {
          // the oracle skips a meta.json it cannot read here
        }
      }
    }
    return false;
  }

  private static boolean truthy(Object value) {
    return switch (value) {
      case null -> false;
      case Boolean flag -> flag;
      case String text -> !text.isEmpty();
      case CanonicalJson.Num number -> number.text().chars().anyMatch(c -> c >= '1' && c <= '9');
      case Map<?, ?> map -> !map.isEmpty();
      case List<?> list -> !list.isEmpty();
      default -> true;
    };
  }

  @SuppressWarnings("unchecked")
  private static void installCoordination(Path fixtureDir, Path projectRoot) throws IOException {
    Path coordSource = fixtureDir.resolve("coord-worktree");
    Path huskSource = fixtureDir.resolve("husk-worktree");
    if (!Files.isDirectory(coordSource) && !Files.isDirectory(huskSource)) {
      return;
    }
    Path specs = projectRoot.resolve("kitty-specs");
    List<Path> missions = new ArrayList<>();
    try (Stream<Path> entries = Files.list(specs)) {
      entries.filter(Files::isDirectory).sorted().forEach(missions::add);
    }
    for (Path mission : missions) {
      String directory = mission.getFileName().toString();
      Path source = Files.isDirectory(coordSource.resolve(directory)) ? coordSource.resolve(directory) : huskSource.resolve(directory);
      if (!Files.isDirectory(source)) {
        continue;
      }
      Map<String, Object> meta = (Map<String, Object>) CanonicalJson.parse(Files.readAllBytes(mission.resolve("meta.json")));
      String slug = meta.get("mission_slug") instanceof String text && !text.isEmpty() ? text : directory;
      if (!(meta.get("mission_id") instanceof String id) || id.length() < 8) {
        throw new IllegalStateException("a coordination fixture needs a mission_id of at least eight characters: " + directory);
      }
      copyTree(source, projectRoot.resolve(".worktrees").resolve(coordinationDirName(slug, id.substring(0, 8))));
    }
  }

  private static void installSymlinks(Path fixtureDir, Path projectRoot) throws IOException {
    Path plan = fixtureDir.resolve("SYMLINK_PLAN");
    if (!Files.isRegularFile(plan)) {
      return;
    }
    Path outsideSource = fixtureDir.resolve("outside");
    Path outside = projectRoot.resolveSibling("outside");
    if (Files.isDirectory(outsideSource)) {
      copyTree(outsideSource, outside);
    }
    for (String line : Files.readString(plan, StandardCharsets.UTF_8).split("\n")) {
      if (line.isBlank()) {
        continue;
      }
      String[] parts = line.split("\t", 2);
      if (parts.length != 2) {
        throw new IllegalStateException("a SYMLINK_PLAN line is 'link<TAB>target': " + line);
      }
      Path link = projectRoot.resolve(parts[0]);
      Files.createDirectories(link.getParent());
      String target = parts[1];
      Path linkTarget = target.startsWith(OUTSIDE_PREFIX) ? outside.resolve(target.substring(OUTSIDE_PREFIX.length())) : Path.of(target);
      Files.createSymbolicLink(link, linkTarget);
    }
  }

  /** Copies a tree byte for byte (CRLF stays CRLF); a link in the source is recreated as a link. */
  static void copyTree(Path source, Path target) throws IOException {
    Files.walkFileTree(
        source,
        new SimpleFileVisitor<>() {
          @Override
          public FileVisitResult preVisitDirectory(Path dir, BasicFileAttributes attributes) throws IOException {
            Files.createDirectories(target.resolve(source.relativize(dir).toString()));
            return FileVisitResult.CONTINUE;
          }

          @Override
          public FileVisitResult visitFile(Path file, BasicFileAttributes attributes) throws IOException {
            Path destination = target.resolve(source.relativize(file).toString());
            if (Files.isSymbolicLink(file)) {
              Files.createSymbolicLink(destination, Files.readSymbolicLink(file));
            } else if (!Files.exists(destination, LinkOption.NOFOLLOW_LINKS)) {
              Files.copy(file, destination);
            } else {
              Files.copy(file, destination, java.nio.file.StandardCopyOption.REPLACE_EXISTING);
            }
            return FileVisitResult.CONTINUE;
          }
        });
  }
}
