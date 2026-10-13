package org.speckitty.missionstatus.adapter.out.filesystem;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.EnumSet;
import java.util.List;
import java.util.Optional;
import java.util.Set;
import java.util.regex.Pattern;

/**
 * The explicit read allowlist of the service (FR-010 items 1-6): the one test-visible constant that says which files are opened and
 * which directories are listed or stat-ed, plus the classification of a path into one of those classes. A path that is in no class is
 * not on the allowlist; a mode that is not read-only is on it for no class. The service reads the ledger and what it needs to find it,
 * and nothing else: never {@code tasks/*.md}, {@code spec.md}, {@code plan.md}, artifacts, WP frontmatter, {@code status.json}, the
 * coordination copy of {@code meta.json}, or the personal {@code config.toml}.
 *
 * <p>Classification looks at the path relative to the project root, lexically; the callers pass paths composed under the root and never
 * a resolved real path. A path with a {@code .} or {@code ..} segment is in no class.
 */
public final class Allowlist {

  /** What the service does to a path. Everything but the first four is a way to change it, and no class permits any of them. */
  public enum OpenMode {
    READ,
    STAT,
    REALPATH,
    LIST,
    CREATE,
    WRITE,
    APPEND,
    TRUNCATE,
    DELETE_ON_CLOSE,
    RENAME,
    DELETE;

    public boolean readOnly() {
      return this == READ || this == STAT || this == REALPATH || this == LIST;
    }
  }

  /** A path class of the allowlist: where it sits relative to the project root, and which modes may touch it. */
  public enum PathClass {
    /** The project root itself (its real path is the containment bound). */
    PROJECT_ROOT(EnumSet.of(OpenMode.STAT, OpenMode.REALPATH)),
    /** {@code kitty-specs/}: listed for Mission directory names. */
    SPECS_DIR(EnumSet.of(OpenMode.STAT, OpenMode.LIST, OpenMode.REALPATH)),
    /** {@code kitty-specs/<mission>/}: the Mission's own primary directory, stat-ed and resolved only. */
    MISSION_DIR(EnumSet.of(OpenMode.STAT, OpenMode.REALPATH)),
    /** The Mission's own primary {@code meta.json}. */
    MISSION_META(EnumSet.of(OpenMode.READ, OpenMode.STAT)),
    /** The Mission's own primary {@code lanes.json}, read only when the topology has to be classified. */
    LANES_JSON(EnumSet.of(OpenMode.READ, OpenMode.STAT)),
    /** {@code status.events.jsonl} of the resolved read directory (primary or coordination). */
    LEDGER(EnumSet.of(OpenMode.READ, OpenMode.STAT)),
    /** {@code .worktrees/}: listed for names only. */
    WORKTREES_DIR(EnumSet.of(OpenMode.STAT, OpenMode.LIST)),
    /** {@code .worktrees/<slug>-<mid8>-coord/}: stat-ed only. */
    COORD_ROOT(EnumSet.of(OpenMode.STAT)),
    /** {@code .worktrees/<slug>-<mid8>-coord/kitty-specs/<slug>-<mid8>/}: stat-ed and resolved only. */
    COORD_MISSION_DIR(EnumSet.of(OpenMode.STAT, OpenMode.REALPATH)),
    /**
     * {@code .worktrees/<slug>-<mid8>-coord/kitty-specs/<slug>-<mid8>/meta.json}: stat-ed for its existence only (DD-105: the oracle
     * reads the coordination folder when it holds a {@code meta.json}); its content is never read.
     */
    COORD_META(EnumSet.of(OpenMode.STAT)),
    /** {@code .kittify/config.yaml}: {@code project.slug}; resolved (REALPATH) to prove {@code .kittify} stays inside the project root. */
    CONFIG_YAML(EnumSet.of(OpenMode.READ, OpenMode.STAT, OpenMode.REALPATH)),
    /** {@code .kittify/metadata.yaml}: {@code spec_kitty.version} and {@code spec_kitty.schema_version}. */
    METADATA_YAML(EnumSet.of(OpenMode.READ, OpenMode.STAT, OpenMode.REALPATH)),
    /** {@code .git}: a directory, or a pointer file with a {@code gitdir:} line. */
    GIT_POINTER(EnumSet.of(OpenMode.READ, OpenMode.STAT)),
    /** {@code .git/HEAD}. */
    GIT_HEAD(EnumSet.of(OpenMode.READ, OpenMode.STAT)),
    /** The single file {@code HEAD} of the directory a {@code .git} pointer file names: outside the root only; in-root {@code .git/refs} and {@code .git/worktrees} stay off the list. */
    GITDIR_HEAD(EnumSet.of(OpenMode.READ, OpenMode.STAT, OpenMode.REALPATH));

    private final Set<OpenMode> modes;

    PathClass(Set<OpenMode> modes) {
      this.modes = modes;
    }
  }

  /** One recorded or planned touch of the file system: the class (null when the path is on no class), the root-relative path, the mode. */
  public record Access(PathClass pathClass, String path, OpenMode mode) {}

  /** An access the allowlist does not permit, with the reason in words. */
  public record Violation(Access access, String reason) {}

  /** One line of the allowlist as the README states it: the class, its path pattern, and what it is read for. */
  public record Entry(PathClass pathClass, String pattern, String purpose) {}

  /** The allowlist, in the order of FR-010 items 1-6 followed by the listings and the stat. The README's fenced list equals {@link #PATTERNS}. */
  public static final List<Entry> ENTRIES =
      List.of(
          new Entry(PathClass.LEDGER, "<read-dir>/status.events.jsonl", "the event ledger of the resolved read directory"),
          new Entry(PathClass.MISSION_META, "<primary-dir>/meta.json", "identity, dates and stored topology, from the Mission's own primary directory only"),
          new Entry(PathClass.LANES_JSON, "<primary-dir>/lanes.json", "the lanes signal, only when the topology is absent and must be classified"),
          new Entry(PathClass.CONFIG_YAML, ".kittify/config.yaml", "project.slug"),
          new Entry(PathClass.METADATA_YAML, ".kittify/metadata.yaml", "spec_kitty.version and spec_kitty.schema_version"),
          new Entry(PathClass.GIT_HEAD, ".git/HEAD", "the branch name, when .git is a directory"),
          new Entry(PathClass.GIT_POINTER, ".git (pointer file) and <gitdir>/HEAD", "the branch name, when .git is a pointer file: its gitdir line and the one file HEAD of that directory"),
          new Entry(PathClass.SPECS_DIR, "kitty-specs/ (names only)", "the Mission directory names"),
          new Entry(PathClass.WORKTREES_DIR, ".worktrees/ (names only)", "listing for the coordination worktree roots"),
          new Entry(PathClass.COORD_MISSION_DIR, ".worktrees/<slug>-<mid8>-coord/kitty-specs/<slug>-<mid8>/ (stat only)", "whether the coordination Mission directory exists"),
          new Entry(PathClass.COORD_META, ".worktrees/<slug>-<mid8>-coord/kitty-specs/<slug>-<mid8>/meta.json (stat only)", "whether the coordination Mission directory holds a meta.json (existence only; never opened)"));

  /** The path patterns of {@link #ENTRIES}, in order: the form the README parity test compares. */
  public static final List<String> PATTERNS = ENTRIES.stream().map(Entry::pattern).toList();

  private static final String SEGMENT = "[^/]+";
  private static final List<ClassPattern> CLASSIFIERS =
      List.of(
          new ClassPattern(PathClass.PROJECT_ROOT, ""),
          new ClassPattern(PathClass.SPECS_DIR, "kitty-specs"),
          new ClassPattern(PathClass.MISSION_DIR, "kitty-specs/" + SEGMENT),
          new ClassPattern(PathClass.MISSION_META, "kitty-specs/" + SEGMENT + "/meta\\.json"),
          new ClassPattern(PathClass.LANES_JSON, "kitty-specs/" + SEGMENT + "/lanes\\.json"),
          new ClassPattern(PathClass.LEDGER, "kitty-specs/" + SEGMENT + "/status\\.events\\.jsonl"),
          new ClassPattern(PathClass.WORKTREES_DIR, "\\.worktrees"),
          new ClassPattern(PathClass.COORD_ROOT, "\\.worktrees/" + SEGMENT + "-coord"),
          new ClassPattern(PathClass.COORD_MISSION_DIR, "\\.worktrees/" + SEGMENT + "-coord/kitty-specs/" + SEGMENT),
          new ClassPattern(PathClass.LEDGER, "\\.worktrees/" + SEGMENT + "-coord/kitty-specs/" + SEGMENT + "/status\\.events\\.jsonl"),
          new ClassPattern(PathClass.COORD_META, "\\.worktrees/" + SEGMENT + "-coord/kitty-specs/" + SEGMENT + "/meta\\.json"),
          new ClassPattern(PathClass.CONFIG_YAML, "\\.kittify/config\\.yaml"),
          new ClassPattern(PathClass.METADATA_YAML, "\\.kittify/metadata\\.yaml"),
          new ClassPattern(PathClass.GIT_POINTER, "\\.git"),
          new ClassPattern(PathClass.GIT_HEAD, "\\.git/HEAD"));

  private static final String OUTSIDE = "<outside>/";

  private record ClassPattern(PathClass pathClass, Pattern pattern) {
    ClassPattern(PathClass pathClass, String regex) {
      this(pathClass, Pattern.compile(regex));
    }
  }

  private Allowlist() {}

  /** The class of {@code path}, or empty when the path is on the allowlist for no class. */
  public static Optional<PathClass> classify(Path root, Path path) {
    String relative = describe(root, path);
    if (relative.startsWith(OUTSIDE)) {
      // The one place outside the project root that is read: the HEAD of the git directory a .git pointer file names.
      return relative.equals(OUTSIDE + "HEAD") ? Optional.of(PathClass.GITDIR_HEAD) : Optional.empty();
    }
    for (String segment : relative.split("/", -1)) {
      if (segment.equals(".") || segment.equals("..")) {
        return Optional.empty();
      }
    }
    for (ClassPattern classifier : CLASSIFIERS) {
      if (classifier.pattern().matcher(relative).matches()) {
        return Optional.of(classifier.pathClass());
      }
    }
    return Optional.empty();
  }

  /**
   * The path as the records show it: relative to the project root with {@code /} separators ({@code ""} for the root), or
   * {@code <outside>/<file name>} for a path outside it. Never an absolute path.
   */
  public static String describe(Path root, Path path) {
    Path base = root.toAbsolutePath().normalize();
    // The candidate is deliberately not normalized: a ".." segment must stay visible so that classify refuses it.
    Path absolute = path.toAbsolutePath();
    if (absolute.startsWith(base)) {
      List<String> names = new ArrayList<>();
      for (int i = base.getNameCount(); i < absolute.getNameCount(); i++) {
        names.add(absolute.getName(i).toString());
      }
      return String.join("/", names);
    }
    Path name = path.getFileName();
    return OUTSIDE + (name == null ? "" : name.toString());
  }

  /** Whether {@code mode} may touch a path of {@code pathClass}. */
  public static boolean permits(PathClass pathClass, OpenMode mode) {
    return mode.readOnly() && pathClass.modes.contains(mode);
  }

  /** The accesses of a recorded sequence that the allowlist does not permit, in order. */
  public static List<Violation> violations(List<Access> sequence) {
    List<Violation> violations = new ArrayList<>();
    for (Access access : sequence) {
      if (access.pathClass() == null) {
        violations.add(new Violation(access, "path is on no allowlist class"));
      } else if (!access.mode().readOnly()) {
        violations.add(new Violation(access, "mode " + access.mode() + " is not read-only"));
      } else if (!permits(access.pathClass(), access.mode())) {
        violations.add(new Violation(access, "mode " + access.mode() + " is not permitted for " + access.pathClass()));
      }
    }
    return violations;
  }
}
