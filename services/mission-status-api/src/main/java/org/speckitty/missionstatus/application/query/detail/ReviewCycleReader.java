package org.speckitty.missionstatus.application.query.detail;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Objects;
import org.speckitty.missionstatus.application.query.artifact.Eligibility;
import org.speckitty.missionstatus.application.query.port.out.FrontmatterDecoder;
import org.speckitty.missionstatus.application.query.port.out.TextSource;
import org.speckitty.missionstatus.application.query.port.out.dto.BytesRead;
import org.speckitty.missionstatus.application.query.port.out.dto.DirListing;
import org.speckitty.missionstatus.application.query.port.out.dto.EntryStat;
import org.speckitty.missionstatus.application.query.port.out.dto.FileRef;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.application.query.port.out.dto.ReadScope;
import org.speckitty.missionstatus.application.query.port.out.dto.RelativePath;
import org.speckitty.missionstatus.application.query.port.out.exceptions.TextFault;
import org.speckitty.missionstatus.domain.model.Actor;
import org.speckitty.missionstatus.domain.model.HistoryRow;
import org.speckitty.missionstatus.domain.model.PyText;
import org.speckitty.missionstatus.domain.model.ReviewCycleMeta;
import org.speckitty.missionstatus.domain.readmodel.derive.CycleNames;
import org.speckitty.missionstatus.domain.readmodel.detail.ReviewCycleEntry;
import org.speckitty.missionstatus.domain.readmodel.detail.ReviewView;
import org.speckitty.missionstatus.domain.redaction.Projector;

/**
 * The review cycles of a Work Package (the oracle's {@code review_cycles}): one entry per {@code tasks/<wp-slug>/review-cycle-<N>.md} of the
 * Mission's <em>primary</em> directory, ascending by {@code N} as a number, where {@code <wp-slug>} is the stem of the Work Package's prompt
 * file (none: no cycles). {@code tasks/} and {@code tasks/<wp-slug>} must be real directories: a link is not entered. A symbolic-link cycle
 * file is an entry with null members and no path, and its target is never read. A file over 262144 bytes (read by the bytes counted, not by a
 * size read earlier), or one that cannot be read or parsed, is still an entry with null {@code reviewedAt} and {@code reviewer} and writes no
 * diagnostic (row M11): its verdict comes from the ledger, never from the file.
 */
public final class ReviewCycleReader {

  /** The most bytes of a review-cycle file the route parses (256 KiB). */
  public static final int FILE_CAP_BYTES = 262_144;

  private static final int LISTING_LIMIT = 100_000;
  private static final String TASKS = "tasks";
  private static final EntryStat TASKS_DIRECTORY = new EntryStat.Present(EntryStat.EntryKind.DIRECTORY, 0, 0);

  private final TextSource text;
  private final FrontmatterDecoder decoder;

  public ReviewCycleReader(TextSource text, FrontmatterDecoder decoder) {
    this.text = Objects.requireNonNull(text, "text");
    this.decoder = Objects.requireNonNull(decoder, "decoder");
  }

  /**
   * @param missionDirectory the name of the Mission's primary directory, which the pointer of a cycle names
   * @param promptFileName the name of the Work Package's prompt file, or null
   * @param history the transitions of the Work Package, in the order the resolved state holds them: the verdicts are read from their reviews
   * @param projector the projection of the reviewer handle
   * @throws ReadRefused when a directory is too large to list, or a cycle file's number does not fit the served integer
   * @throws TextFault when the port cannot stat or list a directory, or stat a cycle file
   */
  public List<ReviewCycleEntry> read(MissionRef mission, String missionDirectory, String promptFileName, List<HistoryRow> history, Projector projector) {
    if (promptFileName == null) {
      return List.of();
    }
    String workPackageSlug = promptFileName.substring(0, promptFileName.length() - ".md".length());
    List<String> names = cycleFileNames(mission, workPackageSlug);
    names.sort(Comparator.comparingInt(name -> CycleNames.cycleNumber(name).getAsInt()));
    List<ReviewCycleEntry> entries = new ArrayList<>();
    for (String name : names) {
      entries.add(entry(mission, missionDirectory, workPackageSlug, name, history, projector));
    }
    return entries;
  }

  private List<String> cycleFileNames(MissionRef mission, String workPackageSlug) {
    if (!isDirectory(mission, TASKS) || !isDirectory(mission, TASKS + "/" + workPackageSlug)) {
      return new ArrayList<>();
    }
    DirListing listing = text.list(new FileRef.MissionFile(mission, RelativePath.of(TASKS + "/" + workPackageSlug)), LISTING_LIMIT, ReadScope.AUTHORED);
    if (!(listing instanceof DirListing.Names names)) {
      return new ArrayList<>();
    }
    if (names.limitReached()) {
      throw new ReadRefused();
    }
    List<String> cycles = names.names().stream().filter(CycleNames::isCycleName).toList();
    if (cycles.stream().anyMatch(name -> CycleNames.cycleNumber(name).isEmpty())) {
      // a cycle file the contract's integer cannot number: never dropped silently on a fail-loud route (WP15 F3)
      throw new ReadRefused();
    }
    return new ArrayList<>(cycles);
  }

  /** Whether the path is a real directory; a name that is no path segment (a prompt file with a backslash in it) names no directory. */
  private boolean isDirectory(MissionRef mission, String path) {
    RelativePath relative;
    try {
      relative = RelativePath.of(path);
    } catch (IllegalArgumentException notASegment) {
      return false;
    }
    return text.stat(new FileRef.MissionFile(mission, relative), ReadScope.AUTHORED) instanceof EntryStat.Present present
        && present.kind() == EntryStat.EntryKind.DIRECTORY;
  }

  private ReviewCycleEntry entry(MissionRef mission, String missionDirectory, String workPackageSlug, String name, List<HistoryRow> history, Projector projector) {
    String relative = TASKS + "/" + workPackageSlug + "/" + name;
    boolean eligible =
        Eligibility.isEligiblePath(relative)
            && Eligibility.isEligible(relative, text.stat(new FileRef.MissionFile(mission, RelativePath.of(relative)), ReadScope.AUTHORED), List.of(TASKS_DIRECTORY, TASKS_DIRECTORY));
    ReviewCycleMeta meta = eligible ? parsed(mission, relative) : ReviewCycleMeta.UNPARSED;
    String pointer = CycleNames.pointer(missionDirectory, workPackageSlug, name);
    String reviewer = meta.reviewer() == null ? null : projector.strict(Actor.ofText(meta.reviewer()).tool(), "reviewCycles.reviewer", true);
    return new ReviewCycleEntry(CycleNames.cycleNumber(name).getAsInt(), meta.reviewedAt(), reviewer, verdict(history, pointer), pointer, eligible ? relative : null);
  }

  /** The members of the file; an unreadable, over-cap or unparseable file gives none, and the entry stays. */
  private ReviewCycleMeta parsed(MissionRef mission, String relative) {
    try {
      BytesRead read = text.readBytes(new FileRef.MissionFile(mission, RelativePath.of(relative)), FILE_CAP_BYTES, ReadScope.AUTHORED);
      return read instanceof BytesRead.Bytes bytes ? decoder.decodeReviewCycle(bytes.content()) : ReviewCycleMeta.UNPARSED;
    } catch (TextFault unreadable) {
      return ReviewCycleMeta.UNPARSED;
    }
  }

  /** The verdict of the last transition in ledger file order whose trimmed review reference is the pointer; null when no transition names it or its verdict is no review verdict. */
  private static ReviewView.Verdict verdict(List<HistoryRow> history, String pointer) {
    if (pointer == null) {
      return null;
    }
    ReviewView.Verdict verdict = null;
    // the oracle's cycle_verdict walks the ledger rows in FILE order; the history is in time order, so the line number restores the file order
    List<HistoryRow> inFileOrder = new ArrayList<>(history);
    inFileOrder.sort(Comparator.comparingLong(HistoryRow::lineNumber));
    for (HistoryRow row : inFileOrder) {
      if (row.reviewReference() != null && PyText.strip(row.reviewReference()).equals(pointer)) {
        verdict = verdictOf(row.reviewVerdict());
      }
    }
    return verdict;
  }

  private static ReviewView.Verdict verdictOf(String stored) {
    if ("approved".equals(stored)) {
      return ReviewView.Verdict.APPROVED;
    }
    return "changes_requested".equals(stored) ? ReviewView.Verdict.CHANGES_REQUESTED : null;
  }
}
