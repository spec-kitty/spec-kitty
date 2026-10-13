package org.speckitty.missionstatus.adapter.out.filesystem;

import java.nio.file.Path;
import java.nio.file.attribute.BasicFileAttributes;
import java.util.Optional;
import java.util.regex.Pattern;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault.Kind;
import org.speckitty.missionstatus.domain.model.Topology;
import tools.jackson.databind.JsonNode;

/**
 * Which directory a Mission's ledger is read from (FR-006), decided by the stored topology and by directory existence only. It reads no
 * git: the oracle consults the worktree registry to tell a registered coordination worktree from a husk, the service does not (plan
 * Q-3, interim), so a stale husk is told apart from a coordination worktree by the stored topology alone.
 *
 * <ol>
 *   <li>Stored {@code single_branch} or {@code lanes}: the Mission's own primary directory; a husk beside it is never consulted, not
 *       even stat-ed ({@code _resolve_existing_for_slug}).
 *   <li>Stored {@code coord} or {@code lanes_with_coord}: the coordination Mission directory
 *       {@code .worktrees/<slug>-<mid8>-coord/kitty-specs/<slug>-<mid8>/} when it exists and either holds a {@code meta.json} (stat-ed,
 *       never read) or {@code meta.json} names a non-blank string {@code coordination_branch} (DD-105); otherwise the primary directory, whether the
 *       worktree root is absent or exists without that directory ({@code probe_coord_state}: UNMATERIALIZED, EMPTY).
 *   <li>No stored topology (absent, unrecognised or not a string, as {@code MissionTopology.from_stored}): classified once from
 *       {@code coordination_branch} and the {@code lanes.json} signal ({@code classify_from_meta}, {@code topology_from_meta}); a
 *       corrupt or unreadable {@code lanes.json} is "no lanes". An empty or malformed {@code meta.json} leaves the topology unclassified:
 *       the resolver reports it ({@link Resolution#classified()}), the application maps it to L7.
 *   <li>{@code meta.json} and {@code lanes.json} are read from the Mission's own primary directory only. The coordination copy of
 *       {@code meta.json} is never opened.
 * </ol>
 *
 * <p>A coordination directory whose real path is outside the real project root is "outside this checkout": the primary directory is
 * read instead. A Mission's own primary directory or {@code meta.json} that is a link, or leaves the root, is a different case:
 * {@code PATH_REFUSED} (L9), thrown as a {@link SourceFault}.
 */
public final class ReadDirResolver {

  private static final String COORD_SUFFIX = "-coord";
  private static final Pattern MID8 = Pattern.compile("^[0-9A-HJKMNP-TV-Z]{8}$");
  private static final String PLANNING_LANE = "lane-planning";
  private static final int MID8_LENGTH = 8;

  /** Which directory the ledger is read from. */
  public enum ReadClass {
    /** The Mission's own primary directory. */
    OWN,
    /** The coordination Mission directory. */
    COORD
  }

  /**
   * The answer. {@code topology} is the stored one, or the one classified from {@code meta.json} and {@code lanes.json}, and
   * {@code UNKNOWN} when {@code classified} is false (an empty or malformed {@code meta.json}); {@code dir} is the directory to read.
   */
  public record Resolution(ReadClass readClass, Path dir, Topology topology, boolean classified) {}

  private final SafeFiles files;

  public ReadDirResolver(SafeFiles files) {
    this.files = files;
  }

  /** Resolves the read directory of the Mission whose primary directory is {@code kitty-specs/<name>/}. */
  public Resolution resolve(String name) {
    if (!SafeFiles.isSafeSegment(name)) {
      throw new SourceFault(Kind.PATH_REFUSED);
    }
    Path own = files.requireContainedDir(files.root().resolve(Listing.SPECS).resolve(name));
    byte[] metaBytes = files.readRegular(own.resolve(Listing.META), SafeFiles.SMALL_FILE_MAX, Kind.PATH_REFUSED, Kind.META_UNPARSEABLE).orElseThrow(() -> new SourceFault(Kind.VANISHED));
    Optional<JsonNode> meta = ReadDirResolverJson.object(metaBytes);
    if (meta.isEmpty()) {
      return new Resolution(ReadClass.OWN, own, Topology.UNKNOWN, false);
    }
    Topology topology = topologyOf(meta.get(), own);
    if (!topology.routesThroughCoordination()) {
      return new Resolution(ReadClass.OWN, own, topology, true);
    }
    Optional<Path> coordination = coordinationDir(name, meta.get());
    return coordination.map(dir -> new Resolution(ReadClass.COORD, dir, topology, true)).orElseGet(() -> new Resolution(ReadClass.OWN, own, topology, true));
  }

  // ---- rule 3 -----------------------------------------------------------------------------------------------------------------

  private Topology topologyOf(JsonNode meta, Path own) {
    JsonNode stored = meta.get("topology");
    if (stored != null && stored.isString()) {
      Topology parsed = Topology.fromStored(stored.stringValue());
      if (parsed != Topology.UNKNOWN) {
        return parsed;
      }
    }
    boolean coordination = ReadDirResolverJson.truthy(meta.get("coordination_branch"));
    boolean lanes = hasCodeLanes(own);
    if (coordination) {
      return lanes ? Topology.LANES_WITH_COORD : Topology.COORD;
    }
    // unstamped_runtime_topology: a derived single_branch never stands at runtime; it reads as lanes
    return Topology.LANES;
  }

  /** "Has lanes" means a code lane: any lane but the planning lane. Absent, corrupt, unreadable, refused or larger than 1 MiB is "no lanes". */
  private boolean hasCodeLanes(Path own) {
    Optional<byte[]> bytes;
    try {
      bytes = files.readRegular(own.resolve("lanes.json"), SafeFiles.SMALL_FILE_MAX, Kind.PATH_REFUSED, Kind.DIR_UNREADABLE);
    } catch (SourceFault degrades) {
      return false;
    }
    if (bytes.isEmpty()) {
      return false;
    }
    Optional<JsonNode> manifest = ReadDirResolverJson.object(bytes.get());
    if (manifest.isEmpty()) {
      return false;
    }
    for (String key : new String[] {"version", "mission_slug", "mission_branch", "target_branch", "lanes", "computed_at", "computed_from"}) {
      if (manifest.get().get(key) == null) {
        return false;
      }
    }
    JsonNode lanes = manifest.get().get("lanes");
    if (!lanes.isArray()) {
      return false;
    }
    boolean code = false;
    for (JsonNode lane : lanes) {
      if (!lane.isObject() || lane.get("lane_id") == null || lane.get("wp_ids") == null) {
        return false;
      }
      JsonNode id = lane.get("lane_id");
      code |= !(id.isString() && PLANNING_LANE.equals(id.stringValue()));
    }
    return code;
  }

  // ---- rule 2 -----------------------------------------------------------------------------------------------------------------

  /**
   * The coordination Mission directory, when the oracle reads it (DD-105; surface_resolver.py husk authority and the
   * {@code coordination_branch} value guard). The folder must exist. It is then read when it holds a {@code meta.json} (stat-ed through
   * the seam, never opened), whatever {@code coordination_branch} holds; otherwise only when {@code coordination_branch} is a non-blank
   * string. A non-string value counts as no branch.
   */
  private Optional<Path> coordinationDir(String name, JsonNode meta) {
    String mid8 = declaredMid8(meta, name);
    if (!SafeFiles.isSafeSegment(mid8)) {
      return Optional.empty();
    }
    String missionDir = name.endsWith("-" + mid8) ? name : name + "-" + mid8;
    if (!SafeFiles.isSafeSegment(missionDir)) {
      return Optional.empty();
    }
    Path dir = files.root().resolve(".worktrees").resolve(missionDir + COORD_SUFFIX).resolve(Listing.SPECS).resolve(missionDir);
    if (!files.isContainedDirectory(dir)) {
      return Optional.empty();
    }
    JsonNode branch = meta.get("coordination_branch");
    boolean namedBranch = branch != null && branch.isString() && !branch.stringValue().isBlank();
    return namedBranch || coordinationMetaPresent(dir) ? Optional.of(dir) : Optional.empty();
  }

  /**
   * Whether the coordination folder holds a {@code meta.json}: a stat, never a read. A regular file is present; a symbolic link is
   * present when it leads to a regular file (the oracle's {@code load_meta} follows it) and absent when it dangles; anything else
   * (a directory) is absent.
   */
  private boolean coordinationMetaPresent(Path dir) {
    Path meta = dir.resolve(Listing.META);
    Optional<BasicFileAttributes> plain = files.statNoFollow(meta);
    if (plain.isEmpty()) {
      return false;
    }
    if (plain.get().isRegularFile()) {
      return true;
    }
    return plain.get().isSymbolicLink() && files.statFollow(meta).map(BasicFileAttributes::isRegularFile).orElse(false);
  }

  /** {@code resolve_declared_mid8}: {@code meta.mid8}, then the first eight characters of {@code mission_id}, then the slug's tail. */
  private static String declaredMid8(JsonNode meta, String name) {
    JsonNode explicit = meta.get("mid8");
    if (ReadDirResolverJson.truthy(explicit)) {
      // str() of a non-string, as the oracle does: it is used as the name, never dropped from the cascade
      return explicit.isString() ? explicit.stringValue() : explicit.isBoolean() ? "True" : explicit.asString();
    }
    JsonNode id = meta.get("mission_id");
    if (ReadDirResolverJson.truthy(id)) {
      String text = id.isString() ? id.stringValue() : id.asString();
      if (text.codePointCount(0, text.length()) >= MID8_LENGTH) {
        return text.substring(0, text.offsetByCodePoints(0, MID8_LENGTH));
      }
    }
    int dash = name.lastIndexOf('-');
    if (dash >= 0) {
      String tail = name.substring(dash + 1);
      if (MID8.matcher(tail).matches()) {
        return tail;
      }
    }
    return "";
  }
}
