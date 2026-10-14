package org.speckitty.missionstatus.application.query;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.file.AccessDeniedException;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.OpenMode;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.PathClass;
import org.speckitty.missionstatus.application.query.ArtifactQueryServiceTest.Trees;
import org.speckitty.missionstatus.application.query.port.in.exceptions.DetailRefusal;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.domain.readmodel.detail.ArtifactEntry;
import org.speckitty.missionstatus.domain.readmodel.detail.ArtifactListing;
import org.speckitty.missionstatus.testsupport.DetailFixture;
import org.speckitty.missionstatus.testsupport.PermissionCase;
import org.speckitty.missionstatus.testsupport.PermissionCase.Leg;
import org.speckitty.missionstatus.testsupport.RealPermissionFixture;

/**
 * The permission cases of AC-4.3 and AC-4.7, both legs of each (D-101): the fault is injected through the recorder (any user, any OS),
 * and the real file system refuses a real file ({@link RealPermissionFixture}, which skips and records {@code not run} when this user
 * is not refused).
 *
 * <ul>
 *   <li>{@code AC-4.3/listing-denied}: a directory below the Mission directory cannot be listed, so the whole listing is 500
 *       {@code artifact_listing_unreadable} with one diagnostic and nothing is omitted silently;
 *   <li>{@code AC-4.7/entry-denied}: one file cannot be read, so its entry stays in the listing with {@code readable} false and exactly
 *       one {@code artifact_unreadable} diagnostic, while the content read of it is 500 {@code artifact_unreadable}.
 * </ul>
 */
class ArtifactQueryServicePermissionTest {

  private static final String TEST_ID = "ArtifactQueryServicePermissionTest";

  private static DetailFixture fixture() {
    DetailFixture fixture = Trees.fixture("artifacts-populated", "artifacts-populated");
    Trees.write(Trees.mission(fixture).resolve("locked/inner.md"), "inner\n");
    Trees.write(Trees.mission(fixture).resolve("locked.md"), "locked\n");
    return fixture;
  }

  private static void assertListingDenied(DetailFixture fixture) {
    ArtifactQueryService service = Trees.service(fixture);

    assertThat(Trees.refusal(() -> service.list(Trees.id()))).isEqualTo(DetailRefusal.Kind.ARTIFACT_LISTING_UNREADABLE);

    assertThat(fixture.diagnostics()).containsExactly(new Diagnostic(DiagnosticCode.ARTIFACT_LISTING_UNREADABLE, Trees.ID.substring(0, 8), null));
  }

  private static void assertEntryDenied(DetailFixture fixture) {
    ArtifactQueryService service = Trees.service(fixture);

    ArtifactListing listing = service.list(Trees.id());

    ArtifactEntry locked = listing.entries().stream().filter(entry -> entry.path().equals("locked.md")).findFirst().orElseThrow();
    assertThat(locked.readable()).isFalse();
    assertThat(listing.entries().stream().filter(ArtifactEntry::readable)).as("the control: the others stay readable").isNotEmpty();
    assertThat(fixture.diagnostics()).containsExactly(new Diagnostic(DiagnosticCode.ARTIFACT_UNREADABLE, Trees.ID.substring(0, 8), null));
    assertThat(Trees.refusal(() -> service.content(Trees.id(), Trees.path("locked.md")))).isEqualTo(DetailRefusal.Kind.ARTIFACT_UNREADABLE);
  }

  @Test
  @PermissionCase(value = "AC-4.3/listing-denied", leg = Leg.INJECTED)
  void aDirectoryThatCannotBeListedRefusesTheWholeListing_injected() {
    DetailFixture fixture = fixture();
    fixture.recorder().failWhen(access -> access.pathClass() == PathClass.ARTIFACT_DIR && access.mode() == OpenMode.LIST && access.path().endsWith("/locked"), () -> new AccessDeniedException("injected"));

    assertListingDenied(fixture);
  }

  @Test
  @PermissionCase(value = "AC-4.3/listing-denied", leg = Leg.REAL)
  void aDirectoryThatCannotBeListedRefusesTheWholeListing_real() {
    DetailFixture fixture = fixture();
    Path locked = Trees.mission(fixture).resolve("locked");
    try (RealPermissionFixture denied = RealPermissionFixture.refusedForThisUser(locked, TEST_ID + "#listing-denied-real")) {
      assertThat(denied.path()).isEqualTo(locked);

      assertListingDenied(fixture);
    }
  }

  @Test
  @PermissionCase(value = "AC-4.7/entry-denied", leg = Leg.INJECTED)
  void aFileThatCannotBeReadIsListedUnreadableWithOneDiagnostic_injected() {
    DetailFixture fixture = fixture();
    fixture.recorder().failWhen(access -> access.pathClass() == PathClass.ARTIFACT_FILE && access.mode() == OpenMode.READ && access.path().endsWith("/locked.md"), () -> new AccessDeniedException("injected"));

    assertEntryDenied(fixture);
  }

  @Test
  @PermissionCase(value = "AC-4.7/entry-denied", leg = Leg.REAL)
  void aFileThatCannotBeReadIsListedUnreadableWithOneDiagnostic_real() {
    DetailFixture fixture = fixture();
    Path locked = Trees.mission(fixture).resolve("locked.md");
    try (RealPermissionFixture denied = RealPermissionFixture.refusedForThisUser(locked, TEST_ID + "#entry-denied-real")) {
      assertThat(denied.path()).isEqualTo(locked);

      assertEntryDenied(fixture);
    }
  }
}
