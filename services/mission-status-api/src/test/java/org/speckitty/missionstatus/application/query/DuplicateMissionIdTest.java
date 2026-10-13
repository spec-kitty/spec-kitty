package org.speckitty.missionstatus.application.query;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.application.query.port.in.dto.ChangeBatch;
import org.speckitty.missionstatus.application.query.port.in.dto.PageRequest;
import org.speckitty.missionstatus.application.query.port.in.dto.StreamScope;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.domain.readmodel.overview.MissionPage;
import org.speckitty.missionstatus.testsupport.FilesystemFixtureFactory;
import org.speckitty.missionstatus.testsupport.FixtureSpec;
import org.speckitty.missionstatus.testsupport.Rows;

/**
 * Landing fold R-2: two Mission directories that carry the same {@code mission_id} (a copied or backed-up {@code kitty-specs/<dir>}) are both
 * listed, and a page walk of size 1 meets each directory exactly once and ends. The page cursor names the directory as well as the id, so the
 * position after the first duplicate is not the position after the second.
 */
class DuplicateMissionIdTest {

  private static final String CREATED = "2026-09-02T10:00:00+00:00";

  private static FixtureSpec.Mission mission(String directory, String slug, String missionId, String createdAt) {
    return FixtureSpec.Mission.of(directory, Rows.meta(missionId, slug, createdAt), Rows.status(Rows.id(1), "2026-09-01T10:00:00Z", "WP01", "planned", "claimed"));
  }

  private static FixtureSpec twoCopiesAndAnOlderMission() {
    return FixtureSpec.of(
        mission("alpha-copy", "dup-one", Rows.ALPHA_ID, CREATED),
        mission("alpha", "dup-two", Rows.ALPHA_ID, CREATED),
        mission("beta", "after", Rows.BETA_ID, "2026-09-01T10:00:00+00:00"));
  }

  private static List<String> walk(FilesystemFixtureFactory.Built built, int size) {
    List<String> slugs = new ArrayList<>();
    String cursor = null;
    int pages = 0;
    do {
      MissionPage page = built.query().missions(new PageRequest(size, cursor));
      page.items().forEach(item -> slugs.add(item.slug()));
      cursor = page.nextPageCursor();
      assertThat(++pages).as("a page walk that does not end").isLessThanOrEqualTo(6);
    } while (cursor != null);
    return slugs;
  }

  @Test
  void aWalkOfSizeOneListsEachDirectoryOnceAndEnds() {
    FilesystemFixtureFactory.Built built = FilesystemFixtureFactory.fromSpec(twoCopiesAndAnOlderMission());

    assertThat(walk(built, 1)).containsExactlyInAnyOrder("dup-one", "dup-two", "after").hasSize(3);
    assertThat(built.query().missions(new PageRequest(50, null)).missionCount()).isEqualTo(3);
  }

  @Test
  void theOrderIsTotalSoAWalkOfAnySizeAgreesWithOnePage() {
    FilesystemFixtureFactory.Built built = FilesystemFixtureFactory.fromSpec(twoCopiesAndAnOlderMission());
    List<String> whole = walk(built, 50);

    assertThat(walk(built, 1)).isEqualTo(whole);
    assertThat(walk(built, 2)).isEqualTo(whole);
    assertThat(whole.getLast()).as("the older Mission comes after both copies").isEqualTo("after");
  }

  @Test
  void theListingWritesOneDuplicateDiagnosticPerIdAndNamesNoDirectory() {
    FilesystemFixtureFactory.Built built = FilesystemFixtureFactory.fromSpec(twoCopiesAndAnOlderMission());

    walk(built, 1);

    List<Diagnostic> duplicates = built.handles().diagnostics().stream().filter(d -> d.code() == DiagnosticCode.MISSION_ID_DUPLICATE).toList();
    assertThat(duplicates).as("one per listing that meets the pair; the walk made three listings").hasSize(3);
    assertThat(duplicates).allSatisfy(d -> {
      assertThat(d.mid8()).isEqualTo(Rows.ALPHA_ID.substring(0, 8));
      assertThat(d.line()).isNull();
    });
  }

  @Test
  void aStreamConnectResolvesToAReadableCopyAndWritesTheSameDiagnostic() {
    FilesystemFixtureFactory.Built built = FilesystemFixtureFactory.fromSpec(twoCopiesAndAnOlderMission());

    ChangeBatch batch = built.query().changesSince(new StreamScope.OneMission(new MissionId(Rows.ALPHA_ID)), Optional.empty());

    assertThat(batch.changes()).isEmpty();
    assertThat(built.handles().diagnostics()).singleElement().satisfies(d -> {
      assertThat(d.code()).isEqualTo(DiagnosticCode.MISSION_ID_DUPLICATE);
      assertThat(d.mid8()).isEqualTo(Rows.ALPHA_ID.substring(0, 8));
    });
  }

  @Test
  void aUniqueIdWritesNoDuplicateDiagnostic() {
    FilesystemFixtureFactory.Built built = FilesystemFixtureFactory.fromSpec(FixtureSpec.of(mission("alpha", "one", Rows.ALPHA_ID, CREATED), mission("beta", "two", Rows.BETA_ID, CREATED)));

    walk(built, 1);
    built.query().changesSince(new StreamScope.OneMission(new MissionId(Rows.ALPHA_ID)), Optional.empty());

    assertThat(built.handles().diagnostics()).isEmpty();
  }
}
