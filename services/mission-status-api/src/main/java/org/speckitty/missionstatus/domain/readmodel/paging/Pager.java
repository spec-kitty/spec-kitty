package org.speckitty.missionstatus.domain.readmodel.paging;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Objects;
import org.speckitty.missionstatus.domain.readmodel.cursor.InvalidPageCursor;
import org.speckitty.missionstatus.domain.readmodel.cursor.PageCursor;
import org.speckitty.missionstatus.domain.model.CodePoints;
import org.speckitty.missionstatus.domain.readmodel.overview.MissionOverview;
import org.speckitty.missionstatus.domain.readmodel.overview.MissionPage;

/** Paging over one enumeration of overviews; {@code missionCount} comes from the same list as the items. */
public final class Pager {

  /**
   * One listed Mission and the name of the directory it was read from. Two directories may carry the same {@code mission_id}; the
   * directory name is what tells their positions apart.
   */
  public record Entry(String directory, MissionOverview overview) {

    public Entry {
      Objects.requireNonNull(directory, "directory");
      Objects.requireNonNull(overview, "overview");
    }
  }

  /** The listing order made total: {@link MissionOrder}, then the directory name as text. */
  private static final Comparator<Entry> ORDER =
      Comparator.comparing(Entry::overview, MissionOrder.COMPARATOR).thenComparing(Entry::directory, CodePoints::compare);

  private Pager() {}

  /**
   * @param requestedSize the requested page size, or null
   * @param pageCursor the incoming cursor, or null for the first page (an empty string is a forged cursor)
   * @throws InvalidPageCursor when the cursor is malformed or names no position of this listing
   */
  public static MissionPage page(List<Entry> listing, Integer requestedSize, String pageCursor) {
    List<Entry> sorted = new ArrayList<>(listing);
    sorted.sort(ORDER);
    int size = PageSize.resolve(requestedSize);
    int start = pageCursor == null ? 0 : positionAfter(sorted, PageCursor.decode(pageCursor));
    int end = Math.min(start + size, sorted.size());
    List<MissionOverview> items = sorted.subList(start, end).stream().map(Entry::overview).toList();
    String next = end < sorted.size() ? PageCursor.encode(items.getLast().createdAt(), items.getLast().missionId().value(), sorted.get(end - 1).directory()) : null;
    return new MissionPage(items, next, sorted.size(), size);
  }

  private static int positionAfter(List<Entry> sorted, PageCursor cursor) {
    for (int i = 0; i < sorted.size(); i++) {
      Entry entry = sorted.get(i);
      if (entry.overview().missionId().value().equals(cursor.missionId()) && entry.directory().equals(cursor.directory())) {
        if (!entry.overview().createdAt().equals(cursor.createdAt())) {
          throw new InvalidPageCursor(InvalidPageCursor.Reason.CREATED_AT_MISMATCH);
        }
        return i + 1;
      }
    }
    throw new InvalidPageCursor(InvalidPageCursor.Reason.UNLISTED);
  }
}
