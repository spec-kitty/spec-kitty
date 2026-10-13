package org.speckitty.missionstatus.domain.readmodel.paging;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.domain.readmodel.cursor.InvalidPageCursor;
import org.speckitty.missionstatus.domain.readmodel.cursor.PageCursor;
import org.speckitty.missionstatus.domain.readmodel.overview.Fixtures;
import org.speckitty.missionstatus.domain.readmodel.overview.MissionOverview;
import org.speckitty.missionstatus.domain.readmodel.overview.MissionPage;

class PagerTest {

  private static final String OLD = "2026-09-01T10:00:00Z";
  private static final String MID = "2026-09-02T10:00:00+00:00";
  private static final String NEW = "2026-09-03T10:00:00Z";

  private static List<Pager.Entry> entries(List<MissionOverview> listing) {
    return listing.stream().map(o -> new Pager.Entry(directory(o.missionId().value()), o)).toList();
  }

  private static String directory(String missionId) {
    return "dir-" + missionId;
  }

  private static List<String> ids(MissionPage page) {
    return page.items().stream().map(o -> o.missionId().value()).toList();
  }

  @Test
  void theOrderIsCreatedAtDescendingThenMissionIdAscending() {
    // 1: OLD, 2: NEW, 3: MID, 4: NEW (ties with 2), 5: MID (ties with 3).
    List<MissionOverview> listing = Fixtures.overviews(OLD, NEW, MID, NEW, MID);
    List<MissionOverview> shuffled = new ArrayList<>(listing);
    Collections.reverse(shuffled);
    MissionPage page = Pager.page(entries(shuffled), 50, null);
    assertThat(ids(page)).containsExactly(Fixtures.ulid(2), Fixtures.ulid(4), Fixtures.ulid(3), Fixtures.ulid(5), Fixtures.ulid(1));
    assertThat(page.nextPageCursor()).isNull();
    assertThat(page.missionCount()).isEqualTo(5);
    assertThat(page.pageSize()).isEqualTo(50);
  }

  @Test
  void createdAtIsOrderedAsAnInstantNotAsText() {
    // As text "…T10:30:00+02:00" > "…T09:00:00Z"; as an instant it is earlier, so it sorts last when descending.
    List<MissionOverview> listing = Fixtures.overviews("2026-09-01T10:30:00+02:00", "2026-09-01T09:00:00Z");
    assertThat(ids(Pager.page(entries(listing), 50, null))).containsExactly(Fixtures.ulid(2), Fixtures.ulid(1));
  }

  @Test
  void pagingWithPageSizeOneYieldsEveryMissionExactlyOnceInOrder() {
    List<MissionOverview> listing = Fixtures.overviews(OLD, NEW, MID, NEW, MID);
    List<String> seen = new ArrayList<>();
    String cursor = null;
    int pages = 0;
    do {
      MissionPage page = Pager.page(entries(listing), 1, cursor);
      seen.addAll(ids(page));
      assertThat(page.missionCount()).isEqualTo(5);
      cursor = page.nextPageCursor();
      pages++;
    } while (cursor != null);
    assertThat(pages).isEqualTo(5);
    assertThat(seen).containsExactly(Fixtures.ulid(2), Fixtures.ulid(4), Fixtures.ulid(3), Fixtures.ulid(5), Fixtures.ulid(1));
  }

  @Test
  void aNextCursorIsOnlyOfferedWhenMoreItemsRemain() {
    List<MissionOverview> listing = Fixtures.overviews(OLD, NEW, MID);
    MissionPage first = Pager.page(entries(listing), 2, null);
    assertThat(ids(first)).containsExactly(Fixtures.ulid(2), Fixtures.ulid(3));
    assertThat(first.nextPageCursor()).isEqualTo(PageCursor.encode(MID, Fixtures.ulid(3), directory(Fixtures.ulid(3))));
    MissionPage last = Pager.page(entries(listing), 2, first.nextPageCursor());
    assertThat(ids(last)).containsExactly(Fixtures.ulid(1));
    assertThat(last.nextPageCursor()).isNull();
    MissionPage exact = Pager.page(entries(listing), 3, null);
    assertThat(exact.nextPageCursor()).isNull();
  }

  @Test
  void anEmptyListingIsAnEmptyPage() {
    MissionPage page = Pager.page(entries(List.of()), null, null);
    assertThat(page.items()).isEmpty();
    assertThat(page.nextPageCursor()).isNull();
    assertThat(page.missionCount()).isZero();
    assertThat(page.pageSize()).isEqualTo(50);
  }

  @Test
  void aCursorNamingAnUnlistedMissionIsRefused() {
    List<MissionOverview> listing = Fixtures.overviews(OLD, NEW);
    String forged = PageCursor.encode(NEW, Fixtures.ulid(9), directory(Fixtures.ulid(9)));
    assertThatThrownBy(() -> Pager.page(entries(listing), 50, forged)).isInstanceOfSatisfying(InvalidPageCursor.class, e -> assertThat(e.reason()).isEqualTo(InvalidPageCursor.Reason.UNLISTED));
  }

  @Test
  void aCursorNamingAListedMissionWithADifferentCreatedAtIsRefused() {
    List<MissionOverview> listing = Fixtures.overviews(OLD, NEW);
    String forged = PageCursor.encode(OLD, Fixtures.ulid(2), directory(Fixtures.ulid(2))); // mission 2 was created NEW
    assertThatThrownBy(() -> Pager.page(entries(listing), 50, forged)).isInstanceOfSatisfying(InvalidPageCursor.class, e -> assertThat(e.reason()).isEqualTo(InvalidPageCursor.Reason.CREATED_AT_MISMATCH));
    // The same instant written with another offset is a different createdAt text, so it is refused as well.
    String otherText = PageCursor.encode("2026-09-03T12:00:00+02:00", Fixtures.ulid(2), directory(Fixtures.ulid(2)));
    assertThatThrownBy(() -> Pager.page(entries(listing), 50, otherText)).isInstanceOf(InvalidPageCursor.class);
  }

  @Test
  void anEmptyCursorIsRefusedWhileAbsentMeansFirstPage() {
    List<MissionOverview> listing = Fixtures.overviews(OLD);
    assertThatThrownBy(() -> Pager.page(entries(listing), 50, "")).isInstanceOf(InvalidPageCursor.class);
    assertThat(Pager.page(entries(listing), 50, null).items()).hasSize(1);
  }

  @Test
  void pageSizeIsBoundedByTheContract() {
    assertThat(PageSize.resolve(null)).isEqualTo(50);
    assertThat(PageSize.resolve(1)).isEqualTo(1);
    assertThat(PageSize.resolve(200)).isEqualTo(200);
    assertThat(PageSize.resolve(201)).isEqualTo(200);
    assertThat(PageSize.resolve(0)).isEqualTo(1);
    assertThat(PageSize.resolve(-5)).isEqualTo(1);
    assertThat(PageSize.DEFAULT).isEqualTo(50);
    assertThat(PageSize.MIN).isEqualTo(1);
    assertThat(PageSize.MAX).isEqualTo(200);
  }

  @Test
  void theSameInputsGiveEqualResults() {
    List<MissionOverview> listing = Fixtures.overviews(OLD, NEW, MID);
    assertThat(Pager.page(entries(listing), 2, null)).isEqualTo(Pager.page(entries(listing), 2, null));
  }

  // ---- landing fold R-2: two directories, one mission_id ---------------------------------------------------------------------

  @Test
  void twoDirectoriesWithOneMissionIdAreBothListedAndAWalkOfSizeOneMeetsEachOnce() {
    MissionOverview copy = Fixtures.overviews(MID).getFirst();
    MissionOverview after = Fixtures.overviews(OLD, OLD).get(1);
    List<Pager.Entry> listing = List.of(new Pager.Entry("b-copy", copy), new Pager.Entry("a-original", copy), new Pager.Entry("c-after", after));
    List<String> seen = new ArrayList<>();
    String cursor = null;
    int pages = 0;
    do {
      MissionPage page = Pager.page(listing, 1, cursor);
      assertThat(page.missionCount()).isEqualTo(3);
      seen.add(page.items().getFirst().missionId().value());
      String next = page.nextPageCursor();
      if (next != null) {
        assertThat(PageCursor.decode(next).directory()).as("the cursor names the directory").isIn("a-original", "b-copy");
      }
      cursor = next;
      assertThat(++pages).as("a walk that does not end").isLessThanOrEqualTo(3);
    } while (cursor != null);
    assertThat(seen).containsExactly(copy.missionId().value(), copy.missionId().value(), after.missionId().value());
    assertThat(PageCursor.decode(Pager.page(listing, 1, null).nextPageCursor()).directory()).isEqualTo("a-original");
  }

  @Test
  void aCursorNamingTheIdOfADuplicateWithAnUnlistedDirectoryIsRefused() {
    MissionOverview copy = Fixtures.overviews(MID).getFirst();
    List<Pager.Entry> listing = List.of(new Pager.Entry("a", copy), new Pager.Entry("b", copy));
    String forged = PageCursor.encode(MID, copy.missionId().value(), "c");
    assertThatThrownBy(() -> Pager.page(listing, 50, forged)).isInstanceOfSatisfying(InvalidPageCursor.class, e -> assertThat(e.reason()).isEqualTo(InvalidPageCursor.Reason.UNLISTED));
  }
}
