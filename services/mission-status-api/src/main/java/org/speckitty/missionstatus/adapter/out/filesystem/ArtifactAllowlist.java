package org.speckitty.missionstatus.adapter.out.filesystem;

import java.util.ArrayList;
import java.util.EnumSet;
import java.util.List;
import java.util.Optional;
import java.util.Set;
import java.util.regex.Pattern;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.OpenMode;

/**
 * The read allowlist of the artifact routes ({@link FilesystemMissionArtifactSource}), kept apart from {@link Allowlist} so that the
 * event source's own guarantee (it never opens an artifact) is unchanged. It says which paths the artifact source may touch and how:
 * it lists {@code kitty-specs/} and reads each {@code meta.json} to find a Mission, stats and lists the Mission's own primary
 * directory, and stats, lists and reads below it. The two root status records are stat-ed only (the walk sees them), never read. The
 * README's second fenced allowlist equals {@link #PATTERNS}.
 *
 * <p>Classification is lexical over the path relative to the project root, as {@link Allowlist#describe} writes it.
 */
public final class ArtifactAllowlist {

  /** A path class of the artifact allowlist and the modes that may touch it. */
  public enum PathClass {
    /** The project root itself (its real path is the containment bound). */
    PROJECT_ROOT(EnumSet.of(OpenMode.STAT, OpenMode.REALPATH)),
    /** {@code kitty-specs/}: listed for Mission directory names. */
    SPECS_DIR(EnumSet.of(OpenMode.STAT, OpenMode.LIST)),
    /** {@code kitty-specs/<mission>/}: stat-ed, resolved to prove it stays inside the root, and listed. */
    MISSION_DIR(EnumSet.of(OpenMode.STAT, OpenMode.REALPATH, OpenMode.LIST)),
    /** {@code kitty-specs/<mission>/meta.json}: read for {@code mission_id}, and as an artifact. */
    MISSION_META(EnumSet.of(OpenMode.STAT, OpenMode.READ)),
    /** {@code kitty-specs/<mission>/status.events.jsonl} and {@code status.json}: stat-ed by the walk, never read. */
    STATUS_RECORD(EnumSet.of(OpenMode.STAT)),
    /** {@code kitty-specs/<mission>/<path>}: every file and directory below the Mission directory. */
    MISSION_ENTRY(EnumSet.of(OpenMode.STAT, OpenMode.LIST, OpenMode.READ));

    private final Set<OpenMode> modes;

    PathClass(Set<OpenMode> modes) {
      this.modes = modes;
    }

    public boolean permits(OpenMode mode) {
      return mode.readOnly() && modes.contains(mode);
    }
  }

  /** One line of the allowlist as the README states it. */
  public record Entry(PathClass pathClass, String pattern, String purpose) {}

  /** One touch of the file system, relative to the project root. */
  public record Access(String path, OpenMode mode) {}

  public static final List<Entry> ENTRIES =
      List.of(
          new Entry(PathClass.SPECS_DIR, "kitty-specs/ (names only)", "the Mission directory names"),
          new Entry(PathClass.MISSION_META, "kitty-specs/<mission>/meta.json", "mission_id, to find the Mission; also served as an artifact"),
          new Entry(PathClass.MISSION_DIR, "kitty-specs/<mission>/ (stat, real path, names)", "the Mission's own primary directory"),
          new Entry(PathClass.STATUS_RECORD, "kitty-specs/<mission>/status.events.jsonl and status.json (stat only)", "seen by the walk; never read and never served"),
          new Entry(PathClass.MISSION_ENTRY, "kitty-specs/<mission>/<path> (stat, names, read)", "every file and directory below the Mission directory"));

  /** The path patterns of {@link #ENTRIES}, in order: the form the README parity test compares. */
  public static final List<String> PATTERNS = ENTRIES.stream().map(Entry::pattern).toList();

  private static final String SEGMENT = "[^/]+";
  private static final List<ClassPattern> CLASSIFIERS =
      List.of(
          new ClassPattern(PathClass.PROJECT_ROOT, Pattern.compile("")),
          new ClassPattern(PathClass.SPECS_DIR, Pattern.compile("kitty-specs")),
          new ClassPattern(PathClass.MISSION_DIR, Pattern.compile("kitty-specs/" + SEGMENT)),
          new ClassPattern(PathClass.MISSION_META, Pattern.compile("kitty-specs/" + SEGMENT + "/meta\\.json")),
          new ClassPattern(PathClass.STATUS_RECORD, Pattern.compile("kitty-specs/" + SEGMENT + "/status\\.(?:events\\.jsonl|json)", Pattern.CASE_INSENSITIVE)),
          new ClassPattern(PathClass.MISSION_ENTRY, Pattern.compile("kitty-specs/" + SEGMENT + "/.+")));

  private record ClassPattern(PathClass pathClass, Pattern pattern) {}

  private ArtifactAllowlist() {}

  /** The class of a root-relative path, or empty when the path is on no class (outside the root, or with a dot segment). */
  public static Optional<PathClass> classify(String relative) {
    if (relative.startsWith("<outside>/")) {
      return Optional.empty();
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

  /** The accesses of a recorded sequence that the artifact allowlist does not permit, in order, with the reason in words. */
  public static List<String> violations(List<Access> sequence) {
    List<String> violations = new ArrayList<>();
    for (Access access : sequence) {
      Optional<PathClass> pathClass = classify(access.path());
      if (pathClass.isEmpty()) {
        violations.add(access.mode() + " " + access.path() + ": path is on no artifact allowlist class");
      } else if (!pathClass.get().permits(access.mode())) {
        violations.add(access.mode() + " " + access.path() + ": not permitted for " + pathClass.get());
      }
    }
    return violations;
  }
}
