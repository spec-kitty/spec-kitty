package org.speckitty.missionstatus.application.query.detail;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.adapter.out.filesystem.YamlFrontmatterDecoder;
import org.speckitty.missionstatus.application.query.port.out.dto.FileRef;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.application.query.port.out.dto.ReadScope;
import org.speckitty.missionstatus.application.query.port.out.dto.RelativePath;
import org.speckitty.missionstatus.application.query.port.out.exceptions.TextFault;
import org.speckitty.missionstatus.domain.model.Actor;
import org.speckitty.missionstatus.domain.model.HistoryRow;
import org.speckitty.missionstatus.domain.readmodel.detail.ReviewCycleEntry;
import org.speckitty.missionstatus.domain.readmodel.detail.ReviewView.Verdict;
import org.speckitty.missionstatus.domain.redaction.Projector;
import org.speckitty.missionstatus.testsupport.InMemoryTextSource;
import org.speckitty.missionstatus.testsupport.LeakPatternsFile;

/**
 * {@link ReviewCycleReader} over the in-memory port, with the history rows built by hand: the scope of every call is asserted through
 * {@code readScopes()} (the in-memory port registers entries under every scope), the order is numeric, the verdict is the last matching row's, and
 * what the port cannot say becomes an entry with null members or a thrown fault, as the oracle's {@code except} clauses decide.
 */
class ReviewCycleReaderTest {

  private static final MissionRef MISSION = new MissionRef("alpha");
  private static final String POINTER = "review-cycle://alpha/WP01-one/review-cycle-";

  private static FileRef file(String path) {
    return new FileRef.MissionFile(MISSION, RelativePath.of(path));
  }

  private static byte[] cycle(int number) {
    return DetailRoute.cycleFile(number, "reviewer-renata", "2026-09-21T09:15:00+00:00").getBytes(StandardCharsets.UTF_8);
  }

  private static InMemoryTextSource withCycles(int... numbers) {
    String[] names = new String[numbers.length];
    InMemoryTextSource source = new InMemoryTextSource().dir(file("tasks"), "WP01-one", "WP01-one.md").dir(file("tasks/WP01-one"));
    List<String> listed = new ArrayList<>();
    for (int i = 0; i < numbers.length; i++) {
      names[i] = "review-cycle-" + numbers[i] + ".md";
      listed.add(names[i]);
      source.file(file("tasks/WP01-one/" + names[i]), cycle(numbers[i]));
    }
    return source.dir(file("tasks/WP01-one"), listed.toArray(String[]::new));
  }

  private static ReviewCycleReader reader(InMemoryTextSource source) {
    return new ReviewCycleReader(source, new YamlFrontmatterDecoder());
  }

  private static List<ReviewCycleEntry> read(InMemoryTextSource source, List<HistoryRow> history) {
    return reader(source).read(MISSION, "alpha", "WP01-one.md", history, new Projector(LeakPatternsFile.load()));
  }

  private static HistoryRow row(String reference, String verdict) {
    return new HistoryRow("WP01", "E", "2026-09-01T10:00:00Z", "planned", "planned", Actor.NONE, false, null, verdict, reference);
  }

  @Test
  void theEntriesAreInNumericOrderWithTheirPointersAndEveryCallIsUnderTheAuthoredScope() {
    InMemoryTextSource source = withCycles(10, 2, 1, 9);

    List<ReviewCycleEntry> served = read(source, List.of());

    assertThat(served).extracting(ReviewCycleEntry::cycleNumber).containsExactly(1, 2, 9, 10);
    assertThat(served).extracting(ReviewCycleEntry::feedbackReference).containsExactly(POINTER + "1.md", POINTER + "2.md", POINTER + "9.md", POINTER + "10.md");
    assertThat(source.readScopes()).isNotEmpty().containsOnly(ReadScope.AUTHORED);
  }

  @Test
  void theVerdictOfTheLastRowThatNamesTheCycleDecides() {
    InMemoryTextSource source = withCycles(1, 2, 3);
    List<HistoryRow> history =
        List.of(
            row(POINTER + "1.md", "changes_requested"),
            row(" " + POINTER + "1.md\n", "approved"),
            row(POINTER + "2.md", "approved"),
            row(POINTER + "2.md", "something else"),
            row(null, "approved"),
            row("elsewhere", "approved"));

    assertThat(read(source, history)).extracting(ReviewCycleEntry::verdict).containsExactly(Verdict.APPROVED, null, null);
  }

  @Test
  void theLedgerLineNumberDecidesWhichRowIsLastWhateverOrderTheHistoryIsGivenIn() {
    InMemoryTextSource source = withCycles(1);
    HistoryRow later = new HistoryRow("WP01", "E", "2026-09-01T10:05:00Z", "planned", "planned", Actor.NONE, false, null, "approved", POINTER + "1.md", 2L);
    HistoryRow earlier = new HistoryRow("WP01", "E", "2026-09-01T10:02:00Z", "planned", "planned", Actor.NONE, false, null, "changes_requested", POINTER + "1.md", 3L);

    assertThat(read(source, List.of(later, earlier))).extracting(ReviewCycleEntry::verdict).containsExactly(Verdict.CHANGES_REQUESTED);
    assertThat(read(source, List.of(earlier, later))).extracting(ReviewCycleEntry::verdict).containsExactly(Verdict.CHANGES_REQUESTED);
  }

  @Test
  void aPromptFileNameGivesNoCyclesWhenThereIsNoPromptFile() {
    InMemoryTextSource source = withCycles(1);

    assertThat(reader(source).read(MISSION, "alpha", null, List.of(), new Projector(LeakPatternsFile.load()))).isEmpty();
    assertThat(source.readRefs()).isEmpty();
  }

  @Test
  void aLinkOrAFileInPlaceOfTheDirectoriesGivesNoCycles() {
    InMemoryTextSource linkedTasks = new InMemoryTextSource().link(file("tasks"));
    InMemoryTextSource linkedDirectory = new InMemoryTextSource().dir(file("tasks"), "WP01-one").link(file("tasks/WP01-one"));
    InMemoryTextSource fileForDirectory = new InMemoryTextSource().dir(file("tasks"), "WP01-one").file(file("tasks/WP01-one"), new byte[] {'x'});
    InMemoryTextSource absent = new InMemoryTextSource();

    for (InMemoryTextSource source : List.of(linkedTasks, linkedDirectory, fileForDirectory, absent)) {
      assertThat(read(source, List.of())).isEmpty();
    }
  }

  @Test
  void aDirectoryTooLargeToListIsRefused() {
    String[] names = new String[100_001];
    for (int i = 0; i < names.length; i++) {
      names[i] = "n" + i;
    }
    InMemoryTextSource source = new InMemoryTextSource().dir(file("tasks"), "WP01-one").dir(file("tasks/WP01-one"), names);

    assertThatThrownBy(() -> read(source, List.of())).isInstanceOf(ReadRefused.class);
  }

  @Test
  void aFaultOfAStatOrOfTheListingIsThrown() {
    for (TextFault.Kind kind : TextFault.Kind.values()) {
      InMemoryTextSource statFault = withCycles(1).fault(file("tasks/WP01-one/review-cycle-1.md"), kind);
      assertThatThrownBy(() -> read(statFault, List.of())).isInstanceOf(TextFault.class);
    }
    InMemoryTextSource listing = new InMemoryTextSource().dir(file("tasks"), "WP01-one").fault(file("tasks/WP01-one"), TextFault.Kind.DIR_UNREADABLE);
    assertThat(listing).isNotNull();
    assertThatThrownBy(() -> read(listing, List.of())).isInstanceOf(TextFault.class);
  }

  @Test
  void aCycleFileOverTheCapOrNotRegularIsAnEntryWithNullMembers() {
    InMemoryTextSource over = withCycles(1).file(file("tasks/WP01-one/review-cycle-1.md"), new byte[ReviewCycleReader.FILE_CAP_BYTES + 1]);
    InMemoryTextSource directory = withCycles(1).dir(file("tasks/WP01-one/review-cycle-1.md"), "x");
    InMemoryTextSource link = withCycles(1).link(file("tasks/WP01-one/review-cycle-1.md"));

    for (InMemoryTextSource source : List.of(over, directory, link)) {
      ReviewCycleEntry entry = read(source, List.of()).get(0);
      assertThat(entry.reviewer()).isNull();
      assertThat(entry.reviewedAt()).isNull();
      assertThat(entry.cycleNumber()).isEqualTo(1);
    }
    assertThat(read(over, List.of()).get(0).artifactPath()).isEqualTo("tasks/WP01-one/review-cycle-1.md");
    assertThat(read(directory, List.of()).get(0).artifactPath()).isNull();
    assertThat(read(link, List.of()).get(0).artifactPath()).isNull();
    assertThat(ReviewCycleReader.FILE_CAP_BYTES).isEqualTo(262_144);
  }

  @Test
  void aPromptFileWhoseNameIsNoPathSegmentGivesNoCycles() {
    InMemoryTextSource source = withCycles(1);

    assertThat(reader(source).read(MISSION, "alpha", "WP01-a\\b.md", List.of(), new Projector(LeakPatternsFile.load()))).isEmpty();
  }
}
