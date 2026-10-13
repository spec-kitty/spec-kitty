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
