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

  /** The text of the valid Work Package file of {@link #createWithWorkPackages()}: owned files, subtasks and a prompt body. */
  static final String VALID_WORK_PACKAGE =
      "---\nwork_package_id: WP01\ntitle: Foundation\nagent_profile: python-pedro\nexecution_mode: code_change\nmodel: sonnet\nrole: implementer\n"
          + "owned_files:\n- src/app/**\n- README.md\nsubtasks:\n- T001\n- T002\n---\n\n# Body of WP01\n";

  /** A Work Package file the decoder rejects: a member no Work Package file may hold. */
  static final String REJECTED_WORK_PACKAGE = "---\nwork_package_id: WP02\ntitle: Unknown member\nmystery_key: 1\n---\n\nbody\n";

  /**
   * The project of {@link #create()} with the Work Package files, one review cycle and the planning files the detail routes read: WP01 is
   * valid, WP02 has a ledger row and a file the decoder rejects, {@code secret.txt} holds a credential assembled here from fragments
   * (no credential shape is committed whole) and {@code notes.md} holds plain text.
   */
  static Path createWithWorkPackages() {
    Path root =
        FilesystemFixtureFactory.fromSpec(
                FixtureSpec.of(PortFixtures.mission(SLUG, MISSION_ID, PortFixtures.CREATED, FIRST_ROW + Rows.status(Rows.id(2), "2026-09-01T10:00:30Z", "WP02", "planned", "claimed"))))
            .root();
    Path mission = root.resolve("kitty-specs").resolve(SLUG);
    write(mission.resolve("tasks").resolve("WP01-foundation.md"), VALID_WORK_PACKAGE);
    write(mission.resolve("tasks").resolve("WP02-unknown-member.md"), REJECTED_WORK_PACKAGE);
    write(mission.resolve("tasks").resolve("WP01-foundation").resolve("review-cycle-1.md"), "---\nverdict: rejected\n---\n\nFix the foundation.\n");
    write(mission.resolve("spec.md"), "# Spec\n\nPlain text.\n");
    write(mission.resolve("secret.txt"), "token = " + "gh" + "p_" + "a".repeat(36) + "\n");
    return root;
  }

  /** One GET against the service on {@code port}; the body as the service sent it. */
  static java.net.http.HttpResponse<byte[]> get(int port, String path) throws Exception {
    return java.net.http.HttpClient.newHttpClient()
        .send(java.net.http.HttpRequest.newBuilder(java.net.URI.create("http://127.0.0.1:" + port + path)).GET().build(), java.net.http.HttpResponse.BodyHandlers.ofByteArray());
  }

  private static void write(Path file, String text) {
    try {
      Files.createDirectories(file.getParent());
      Files.writeString(file, text, StandardCharsets.UTF_8);
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    }
  }

  static void append(Path root, String text) {
    try {
      Files.writeString(root.resolve("kitty-specs").resolve(SLUG).resolve("status.events.jsonl"), text, StandardCharsets.UTF_8, StandardOpenOption.APPEND);
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    }
  }
}
