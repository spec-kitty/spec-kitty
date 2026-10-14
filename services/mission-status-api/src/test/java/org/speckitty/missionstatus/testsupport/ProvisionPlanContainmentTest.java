package org.speckitty.missionstatus.testsupport;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.attribute.FileTime;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/** A plan that makes a link to the outside sibling and then names that link in a later verb must never touch what the link points at. */
class ProvisionPlanContainmentTest {

  private static final String ORIGINAL = "original";
  private static final FileTime EPOCH = FileTime.fromMillis(1_000_000_000_000L);

  @TempDir Path base;
  Path fixture;
  Path root;
  Path outsideFile;

  @BeforeEach
  void arrange() throws IOException {
    fixture = Files.createDirectories(base.resolve("fixture"));
    root = Files.createDirectories(base.resolve("scratch"));
    Path outside = Files.createDirectories(root.resolveSibling(ProvisionPlan.OUTSIDE_TREE));
    outsideFile = Files.writeString(outside.resolve("f"), ORIGINAL, StandardCharsets.UTF_8);
    Files.setLastModifiedTime(outsideFile, EPOCH);
  }

  private void apply(String... lines) throws IOException {
    Files.writeString(fixture.resolve(ProvisionPlan.FILE), String.join("\n", lines) + "\n", StandardCharsets.UTF_8);
    ProvisionPlan.apply(fixture, root, Files::createSymbolicLink, base.resolve("not-run.txt"));
  }

  private void assertOutsideUntouched() throws IOException {
    assertThat(Files.readString(outsideFile, StandardCharsets.UTF_8)).isEqualTo(ORIGINAL);
    assertThat(Files.getLastModifiedTime(outsideFile)).isEqualTo(EPOCH);
  }

  @Test
  void aWriteThroughALinkToTheOutsideIsRefused() throws IOException {
    assertThatThrownBy(() -> apply("link\tx\t@outside/f", "write\tx\tTAMPERED")).isInstanceOf(IllegalArgumentException.class);
    assertOutsideUntouched();
  }

  @Test
  void aSubstituteThroughALinkToTheOutsideIsRefused() throws IOException {
    assertThatThrownBy(() -> apply("link\tx\t@outside/f", "substitute\tx\toriginal\tTAMPERED")).isInstanceOf(IllegalArgumentException.class);
    assertOutsideUntouched();
  }

  @Test
  void anMtimeOnALinkToTheOutsideChangesTheLinkAndNeverTheTarget() throws IOException {
    apply("link\tx\t@outside/f", "mtime\tx\t1790000000");
    assertOutsideUntouched();
    assertThat(Files.isSymbolicLink(root.resolve("x"))).isTrue();
    assertThat(Files.getLastModifiedTime(root.resolve("x"), LinkOption.NOFOLLOW_LINKS).toMillis()).isEqualTo(1_790_000_000_000L);
  }
}
