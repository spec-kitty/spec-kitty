package org.speckitty.missionstatus.testsupport;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.function.BiFunction;

/**
 * Writes one row of {@code resolver-cases.json} as a project tree, the way {@code materialise_resolver_case} does on the Python side
 * but with no git: the Mission's own folder, an optional {@code lanes.json}, and an optional coordination root at
 * {@code .worktrees/<slug>-<mid8>-coord}. A registered worktree and a husk are the same plain tree to the service, so
 * {@code coordRootKind} is read but changes nothing.
 *
 * <p>Row keys: {@code storedTopology} ({@code absent} stores none), {@code lanesJson} ({@code absent}, {@code valid}, {@code corrupt}),
 * {@code coordRootPresent}, {@code coordMissionDirPresent}, and the optional {@code coordinationBranch} ({@code present}, {@code empty},
 * {@code absent}; a row without it stores one for a coordination-routing topology only), {@code coordMeta} ({@code present}, the default,
 * or {@code absent}: the coordination copy holds the ledger only) and {@code coordRootKind}.
 */
public final class ResolverCaseTrees {

  static final String SLUG = "resolver-case";
  static final String MISSION_ID = "01J77000000000000000000001";
  static final String MID8 = MISSION_ID.substring(0, 8);
  private static final Set<String> COORD_ROUTING = Set.of("coord", "lanes_with_coord");

  private ResolverCaseTrees() {}

  /** A fresh scratch directory. */
  public static Path scratch() {
    return ScratchDirs.create();
  }

  /** The Mission directory name of every row. */
  public static String missionName() {
    return SLUG + "-" + MID8;
  }

  /** Materialises a row into the existing empty {@code root} and returns the Mission directory name. */
  public static String materialise(Map<String, Object> row, Path root) {
    try {
      String name = missionName();
      String topology = (String) row.get("storedTopology");
      String branchState = row.containsKey("coordinationBranch") ? (String) row.get("coordinationBranch") : COORD_ROUTING.contains(topology) ? "present" : "absent";
      Map<String, Object> meta = new LinkedHashMap<>();
      meta.put("mission_id", MISSION_ID);
      meta.put("mission_slug", name);
      meta.put("slug", name);
      meta.put("friendly_name", "Resolver case");
      meta.put("mission_number", null);
      meta.put("mission_type", "software-dev");
      meta.put("target_branch", "main");
      meta.put("created_at", "2026-09-01T10:00:00+00:00");
      if (!topology.equals("absent")) {
        meta.put("topology", topology);
      }
      if (branchState.equals("present")) {
        meta.put("coordination_branch", "kitty/mission-" + name);
      } else if (branchState.equals("empty")) {
        meta.put("coordination_branch", "");
      }
      Map<String, Object> event = new LinkedHashMap<>();
      event.put("actor", "claude");
      event.put("at", "2026-09-01T10:00:00Z");
      event.put("event_id", "01J77000000000000000000009");
      event.put("evidence", null);
      event.put("execution_mode", "worktree");
      event.put("force", false);
      event.put("from_lane", "planned");
      event.put("mission_id", MISSION_ID);
      event.put("mission_slug", name);
      event.put("policy_metadata", null);
      event.put("reason", null);
      event.put("review_ref", null);
      event.put("to_lane", "claimed");
      event.put("wp_id", "WP01");
      Path mission = Files.createDirectories(root.resolve("kitty-specs").resolve(name));
      Files.write(mission.resolve("meta.json"), CanonicalJson.toBytes(meta));
      Files.write(mission.resolve("status.events.jsonl"), CanonicalJson.toBytes(event));
      String lanes = (String) row.get("lanesJson");
      if (lanes.equals("valid")) {
        Files.writeString(mission.resolve("lanes.json"), "{\"lanes\":[{\"lane_id\":\"lane-a\",\"wp_ids\":[\"WP01\"]}]}", StandardCharsets.UTF_8);
      } else if (lanes.equals("corrupt")) {
        Files.writeString(mission.resolve("lanes.json"), "{not json", StandardCharsets.UTF_8);
      }
      if (Boolean.TRUE.equals(row.get("coordRootPresent"))) {
        Path worktree = Files.createDirectories(root.resolve(".worktrees").resolve(ProjectHeaderMaterialisation.coordinationDirName(name, MID8)));
        if (Boolean.TRUE.equals(row.get("coordMissionDirPresent"))) {
          Path inWorktree = worktree.resolve("kitty-specs").resolve(name);
          ProjectHeaderMaterialisation.copyTree(mission, inWorktree);
          if ("absent".equals(row.getOrDefault("coordMeta", "present"))) {
            Files.delete(inWorktree.resolve("meta.json"));
          }
        }
      }
      return name;
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    }
  }

  /**
   * Runs every row, requires the executed ids to equal the file's ids and the manifest's {@code resolverCaseIds} (as sets, no
   * duplicates), and every row to resolve to its {@code expectedClass}. Returns the number of rows run.
   */
  public static int verifyAll(List<Map<String, Object>> rows, List<String> manifestIds, BiFunction<Path, String, String> classOf) {
    List<String> failures = new ArrayList<>();
    Set<String> executed = new LinkedHashSet<>();
    for (Map<String, Object> row : rows) {
      String id = (String) row.get("id");
      if (!executed.add(id)) {
        failures.add(id + ": duplicate row id");
        continue;
      }
      try {
        Path root = Files.createDirectories(scratch().resolve("project"));
        String name = materialise(row, root);
        String actual = classOf.apply(root, name);
        if (!actual.equals(row.get("expectedClass"))) {
          failures.add(id + ": expected " + row.get("expectedClass") + ", got " + actual);
        }
      } catch (IOException failure) {
        throw new UncheckedIOException(failure);
      }
    }
    Set<String> manifest = new LinkedHashSet<>(manifestIds);
    if (manifest.size() != manifestIds.size()) {
      failures.add("manifest resolverCaseIds holds a duplicate");
    }
    Set<String> missingFromFile = new LinkedHashSet<>(manifest);
    missingFromFile.removeAll(executed);
    Set<String> missingFromManifest = new LinkedHashSet<>(executed);
    missingFromManifest.removeAll(manifest);
    if (!missingFromFile.isEmpty()) {
      failures.add("ids in the manifest but not run: " + missingFromFile);
    }
    if (!missingFromManifest.isEmpty()) {
      failures.add("ids run but not in the manifest: " + missingFromManifest);
    }
    if (!failures.isEmpty()) {
      throw new AssertionError("resolver cases: " + String.join("; ", failures));
    }
    return executed.size();
  }
}
