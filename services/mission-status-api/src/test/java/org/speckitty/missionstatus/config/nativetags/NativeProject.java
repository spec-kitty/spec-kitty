package org.speckitty.missionstatus.config.nativetags;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import org.speckitty.missionstatus.testsupport.FilesystemFixtureFactory;
import org.speckitty.missionstatus.testsupport.FixtureSpec;
import org.speckitty.missionstatus.testsupport.PortFixtures;
import org.speckitty.missionstatus.testsupport.Rows;

/** The project directory of the native-tagged tests: one Mission with one row, built before the context starts, in plain file code. */
final class NativeProject {

  static final String SLUG = "alpha";
  static final String MISSION_ID = Rows.ALPHA_ID;
  static final String FIRST_ROW = Rows.status(Rows.id(1), "2026-09-01T10:00:00Z", "WP01", "planned", "claimed");

  private NativeProject() {}

  static Path create() {
    return FilesystemFixtureFactory.fromSpec(FixtureSpec.of(PortFixtures.mission(SLUG, MISSION_ID, PortFixtures.CREATED, FIRST_ROW))).root();
  }

  static void append(Path root, String text) {
    try {
      Files.writeString(root.resolve("kitty-specs").resolve(SLUG).resolve("status.events.jsonl"), text, StandardCharsets.UTF_8, StandardOpenOption.APPEND);
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    }
  }
}
