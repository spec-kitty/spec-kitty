package org.speckitty.missionstatus.perf;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.List;
import java.util.Random;
import org.speckitty.missionstatus.conformance.golden.served.MissionDetailServedRoute;
import org.speckitty.missionstatus.testsupport.FilesystemFixtureFactory;
import org.speckitty.missionstatus.testsupport.FixtureSpec;
import org.speckitty.missionstatus.testsupport.Rows;

/**
 * The generator of the performance fixture: {@code count} Missions with synthetic ULIDs, ledgers of mixed length (2 to about 150 rows),
 * several work packages in different lanes whose rows are interleaved, written as a temporary project tree at test time. The seed is
 * fixed, so two runs produce the same bytes. Nothing it makes is committed (the repository is public).
 */
public final class MissionCorpus {

  public static final long SEED = 20_261_012L;

  private static final String[][] STEPS = {
    {"planned", "claimed"}, {"claimed", "in_progress"}, {"in_progress", "for_review"}, {"for_review", "approved"}, {"approved", "done"}
  };

  private MissionCorpus() {}

  /** The folder name of Mission {@code index}. */
  public static String slug(int index) {
    return String.format("perf-mission-%04d", index);
  }

  /** The synthetic ULID of Mission {@code index} (26 characters of the ULID alphabet). */
  public static String missionId(int index) {
    return "01J" + String.format("%023d", index + 1);
  }

  /** The source-neutral description of {@code count} Missions. */
  public static FixtureSpec spec(int count) {
    Random random = new Random(SEED);
    List<FixtureSpec.Mission> missions = new ArrayList<>(count);
    for (int i = 0; i < count; i++) {
      String createdAt = String.format("2026-08-%02dT%02d:00:00+00:00", 1 + (i % 28), i % 24);
      missions.add(FixtureSpec.Mission.of(slug(i), Rows.meta(missionId(i), slug(i), createdAt), ledger(i, random)));
    }
    return FixtureSpec.of(missions.toArray(FixtureSpec.Mission[]::new));
  }

  /** Writes {@code count} Missions as a project tree below a fresh temporary directory and returns its root. */
  public static Path write(int count) {
    return FilesystemFixtureFactory.fromSpec(spec(count)).root();
  }

  /** One ledger: 1 to 12 work packages, each advanced a random number of steps, rows interleaved, timestamps ascending. */
  static String ledger(int mission, Random random) {
    int packages = 1 + random.nextInt(12);
    int[] progress = new int[packages];
    int[] limit = new int[packages];
    int total = 0;
    for (int p = 0; p < packages; p++) {
      limit[p] = 1 + random.nextInt(STEPS.length);
      total += limit[p];
    }
    // a small share of long ledgers, so lengths are mixed
    boolean padded = mission % 7 == 0;
    StringBuilder text = new StringBuilder();
    int written = 0;
    int serial = mission * 1000;
    while (written < total) {
      int p = random.nextInt(packages);
      if (progress[p] >= limit[p]) {
        continue;
      }
      String[] step = STEPS[progress[p]++];
      text.append(Rows.status(Rows.id(++serial), at(written), "WP" + String.format("%02d", p + 1), step[0], step[1]));
      written++;
    }
    if (padded) {
      for (int k = 0; k < 120; k++) {
        text.append(Rows.annotation(Rows.id(++serial), at(written + k), "WP01"));
      }
    }
    return text.toString();
  }

  // ---- the NFR-009 option: 10 work packages and 100 transition rows per Mission (additive; spec(int) and its callers are untouched) ----

  /** Work packages per Mission of the NFR-009 corpus. */
  public static final int NFR009_WORK_PACKAGES = 10;

  /** Transition rows per work package of the NFR-009 corpus: two claims, three rework rounds of two moves each, then submit and approve. */
  public static final int NFR009_ROWS_PER_WORK_PACKAGE = 10;

  /** The ten moves of one work package, in order: planned->claimed, claimed->in_progress, 3 x (in_progress->for_review, for_review->in_progress), in_progress->for_review, for_review->approved. */
  static final String[][] NFR009_STEPS = {
    {"planned", "claimed"},
    {"claimed", "in_progress"},
    {"in_progress", "for_review"},
    {"for_review", "in_progress"},
    {"in_progress", "for_review"},
    {"for_review", "in_progress"},
    {"in_progress", "for_review"},
    {"for_review", "in_progress"},
    {"in_progress", "for_review"},
    {"for_review", "approved"}
  };

  /** The source-neutral description of {@code missions} NFR-009 Missions (seed {@link #SEED}, synthetic ids, ascending timestamps). */
  public static FixtureSpec nfr009Spec(int missions) {
    Random random = new Random(SEED);
    List<FixtureSpec.Mission> built = new ArrayList<>(missions);
    for (int i = 0; i < missions; i++) {
      String createdAt = String.format("2026-08-%02dT%02d:00:00+00:00", 1 + (i % 28), i % 24);
      built.add(FixtureSpec.Mission.of(slug(i), Rows.meta(missionId(i), slug(i), createdAt), nfr009Ledger(i, random)));
    }
    return FixtureSpec.of(built.toArray(FixtureSpec.Mission[]::new));
  }

  /** Writes {@code missions} NFR-009 Missions as a project tree below a fresh temporary directory and returns its root. */
  public static Path writeNfr009(int missions) {
    return FilesystemFixtureFactory.fromSpec(nfr009Spec(missions)).root();
  }

  /** One NFR-009 ledger: step by step, the ten work packages in a seeded order, so rows of different packages interleave. */
  static String nfr009Ledger(int mission, Random random) {
    StringBuilder text = new StringBuilder();
    int serial = mission * 1000;
    int written = 0;
    List<Integer> order = new ArrayList<>();
    for (int step = 0; step < NFR009_ROWS_PER_WORK_PACKAGE; step++) {
      order.clear();
      for (int p = 0; p < NFR009_WORK_PACKAGES; p++) {
        order.add(p);
      }
      java.util.Collections.shuffle(order, random);
      for (int p : order) {
        String[] move = NFR009_STEPS[step];
        text.append(Rows.status(Rows.id(++serial), at(written++), "WP" + String.format("%02d", p + 1), move[0], move[1]));
      }
    }
    return text.toString();
  }

  // ---- the NFR-001 detail shape (WP18; additive: spec(int), write(int) and their callers are untouched) --------------------------------

  /** The folder name of the Mission the detail routes are timed on: it sorts before every generated Mission, so the duplicate scan reads all the others (AC-1.8 c). */
  public static final String DETAIL_SLUG = "aaa-detail-perf";

  /** The synthetic ULID of the detail Mission (26 characters of the ULID alphabet). */
  public static final String DETAIL_ID = "01J00000000000000000000DET";

  /** Work Package files of the detail Mission in the {@link DetailShape#FORTY_WORK_PACKAGES} shape. */
  public static final int DETAIL_WORK_PACKAGES = 40;

  /** Files below the detail Mission directory in the {@link DetailShape#THOUSAND_FILES} shape (the content file excluded). */
  public static final int DETAIL_FILES = 1000;

  /** The size of the content file of the {@link DetailShape#THOUSAND_FILES} shape: the cap of {@code getArtifactContent}. */
  public static final int CONTENT_BYTES = 262_144;

  /** The relative path of the content file. */
  public static final String CONTENT_PATH = "big.md";

  /** What the detail Mission holds. */
  public enum DetailShape {
    /** 40 Work Package files, a {@code tasks.md} and a {@code spec.md}: {@code getMission} and {@code getWorkPackageDetail}. */
    FORTY_WORK_PACKAGES,
    /** 1000 small files, one file of {@link #CONTENT_BYTES} bytes and a {@code spec.md}: {@code listArtifacts} and {@code getArtifactContent}. */
    THOUSAND_FILES
  }

  /** Writes {@code count} generated Missions and, sorted before them all, the detail Mission of {@code shape}; returns the project root. */
  public static Path writeDetail(int count, DetailShape shape) {
    FixtureSpec base = spec(count);
    List<FixtureSpec.Mission> missions = new ArrayList<>(base.missions());
    StringBuilder ledger = new StringBuilder();
    for (int p = 1; p <= DETAIL_WORK_PACKAGES; p++) {
      ledger.append(Rows.status(Rows.id(800_000 + p), at(p), String.format("WP%02d", p), "planned", "claimed"));
    }
    missions.add(FixtureSpec.Mission.of(DETAIL_SLUG, Rows.meta(DETAIL_ID, DETAIL_SLUG, "2026-08-01T00:00:00+00:00"), ledger.toString()));
    Path root = FilesystemFixtureFactory.fromSpec(new FixtureSpec(base.project(), missions)).root();
    Path mission = root.resolve("kitty-specs").resolve(DETAIL_SLUG);
    switch (shape) {
      case FORTY_WORK_PACKAGES -> writeWorkPackages(mission, DETAIL_WORK_PACKAGES);
      case THOUSAND_FILES -> {
        writeFiles(mission, DETAIL_FILES);
        writeText(mission.resolve(CONTENT_PATH), CONTENT_BYTES, "");
      }
    }
    writeText(mission.resolve("spec.md"), 200, "");
    return root;
  }

  /** {@code n} Work Package files {@code tasks/WPnn-perf.md} and a {@code tasks.md} that names a subtask for each. */
  public static void writeWorkPackages(Path mission, int n) {
    StringBuilder tasks = new StringBuilder();
    for (int p = 1; p <= n; p++) {
      String id = String.format("WP%02d", p);
      String subtask = String.format("T%03d", p);
      writeString(mission.resolve("tasks").resolve(id + "-perf.md"), MissionDetailServedRoute.workPackageFile(id, "Perf work package " + p, "subtasks: [" + subtask + "]") + "\nBody of " + id + ".\n");
      tasks.append("## ").append(id).append("\n- [ ] ").append(subtask).append(" Subtask of ").append(id).append("\n");
    }
    writeString(mission.resolve("tasks.md"), tasks.toString());
  }

  /** {@code n} small markdown files below {@code files/}, in directories of 100. */
  public static void writeFiles(Path mission, int n) {
    for (int i = 0; i < n; i++) {
      writeString(mission.resolve("files").resolve(String.format("d%02d", i / 100)).resolve(String.format("f%04d.md", i)), "File " + i + "\n");
    }
  }

  /**
   * A text file of exactly {@code bytes} bytes (ASCII): {@code head}, then filler lines, the last one cut to the size. The filler is a plain
   * sentence, so it is neither a credential nor a path.
   */
  public static void writeText(Path file, int bytes, String head) {
    String line = "A line of plain text that stands for the body of a long document.\n";
    StringBuilder text = new StringBuilder(head);
    while (text.length() < bytes) {
      text.append(line);
    }
    text.setLength(bytes);
    writeString(file, text.toString());
  }

  public static void writeString(Path file, String text) {
    try {
      Files.createDirectories(file.getParent());
      Files.writeString(file, text, StandardCharsets.UTF_8);
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    }
  }

  private static String at(int minute) {
    return String.format("2026-09-%02dT%02d:%02d:00Z", 1 + (minute / 1440) % 28, (minute / 60) % 24, minute % 60);
  }

  /**
   * Appends one forwarded status row to Mission {@code index}. The event id counts from {@code serial} (use a value above every id of the
   * corpus) and the timestamp is later than every generated row.
   */
  public static void appendRow(Path root, int index, int serial) {
    String row = Rows.status(Rows.id(900_000_000 + serial), "2026-12-01T10:" + String.format("%02d", serial % 60) + ":00Z", "WP01", "claimed", "in_progress");
    try {
      Files.writeString(
          root.resolve("kitty-specs").resolve(slug(index)).resolve("status.events.jsonl"), row, StandardCharsets.UTF_8, StandardOpenOption.CREATE, StandardOpenOption.APPEND);
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    }
  }
}
