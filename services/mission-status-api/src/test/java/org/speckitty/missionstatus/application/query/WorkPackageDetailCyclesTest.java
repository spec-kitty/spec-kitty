package org.speckitty.missionstatus.application.query;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.MID8;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.cycleFile;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.detail;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.fixture;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.ledger;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.review;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.secret;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.write;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.wpFile;

import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist;
import org.speckitty.missionstatus.application.query.detail.DetailRoute;
import org.speckitty.missionstatus.application.query.port.in.exceptions.MissionStatusUnavailable;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.domain.readmodel.detail.ReviewCycleEntry;
import org.speckitty.missionstatus.domain.readmodel.detail.ReviewView.Verdict;
import org.speckitty.missionstatus.testsupport.DetailFixture;

/**
 * The review cycles of the detail (AC-3.2, AC-3.3, AC-3.9, rows M11 and T15 to T17): the files of {@code tasks/<wp-slug>/} of the primary
 * directory in numeric order, the verdict of each from the ledger only, an entry for every file whatever its content, and no link ever entered.
 * {@code Annotation} equality is not used anywhere in this class (WP05 review N1): the entries are read through their accessors.
 */
class WorkPackageDetailCyclesTest {

  private static final String POINTER = "review-cycle://alpha/WP01-one/review-cycle-";

  private static String pointer(int number) {
    return "\"" + POINTER + number + ".md\"";
  }

  private static List<ReviewCycleEntry> cycles(DetailFixture fixture) {
    return detail(fixture, "WP01").reviewCycles();
  }

  private static void cycle(Path root, int number) {
    write(root, "tasks/WP01-one/review-cycle-" + number + ".md", cycleFile(number, "reviewer-renata", "2026-09-21T09:15:00+00:00"));
  }

  @Test
  void theCyclesAreInNumericOrderAndEachVerdictIsTheLedgers() {
    String ledger =
        ledger()
            + review(2, "2026-09-01T10:02:00Z", "WP01", "planned", "planned", pointer(1), "changes_requested")
            + review(3, "2026-09-01T10:03:00Z", "WP01", "planned", "planned", pointer(2), "changes_requested")
            + review(4, "2026-09-01T10:04:00Z", "WP01", "planned", "approved", pointer(9), "approved")
            + review(5, "2026-09-01T10:05:00Z", "WP01", "planned", "planned", pointer(10), "changes_requested");
    DetailFixture fixture =
        fixture(
            ledger,
            root -> {
              for (int number : new int[] {10, 2, 1, 9}) {
                cycle(root, number);
              }
            });

    List<ReviewCycleEntry> served = cycles(fixture);

    assertThat(served).extracting(ReviewCycleEntry::cycleNumber).containsExactly(1, 2, 9, 10);
    assertThat(served).extracting(ReviewCycleEntry::verdict).containsExactly(Verdict.CHANGES_REQUESTED, Verdict.CHANGES_REQUESTED, Verdict.APPROVED, Verdict.CHANGES_REQUESTED);
    assertThat(served).extracting(ReviewCycleEntry::feedbackReference).containsExactly(POINTER + "1.md", POINTER + "2.md", POINTER + "9.md", POINTER + "10.md");
    assertThat(served)
        .extracting(ReviewCycleEntry::artifactPath)
        .containsExactly("tasks/WP01-one/review-cycle-1.md", "tasks/WP01-one/review-cycle-2.md", "tasks/WP01-one/review-cycle-9.md", "tasks/WP01-one/review-cycle-10.md");
    assertThat(served).extracting(ReviewCycleEntry::reviewer).containsOnly("reviewer-renata");
    assertThat(served).extracting(ReviewCycleEntry::reviewedAt).containsOnly("2026-09-21T09:15:00+00:00");
  }

  @Test
  void aCycleWhosePointerMatchesNoEventHasNoVerdict() {
    DetailFixture fixture =
        fixture(
            ledger() + review(2, "2026-09-01T10:02:00Z", "WP01", "planned", "planned", pointer(1), "approved"),
            root -> {
              cycle(root, 1);
              cycle(root, 2);
            });

    assertThat(cycles(fixture)).extracting(ReviewCycleEntry::verdict).containsExactly(Verdict.APPROVED, null);
  }

  @Test
  void theVerdictIsNeverReadFromTheFile() {
    String filed = "---\naffected_files: []\ncycle_number: 1\nmission_slug: alpha\nreviewed_at: '2026-09-21T09:15:00+00:00'\nreviewer_agent: reviewer-renata\nverdict: approved\nwp_id: WP01\n---\n\nFeedback.\n";
    DetailFixture fixture =
        fixture(
            ledger() + review(2, "2026-09-01T10:02:00Z", "WP01", "planned", "planned", pointer(1), "changes_requested"),
            root -> write(root, "tasks/WP01-one/review-cycle-1.md", filed));
    DetailFixture none = fixture(root -> write(root, "tasks/WP01-one/review-cycle-1.md", filed));

    assertThat(cycles(fixture)).extracting(ReviewCycleEntry::verdict).containsExactly(Verdict.CHANGES_REQUESTED);
    assertThat(cycles(none)).extracting(ReviewCycleEntry::verdict).containsExactly((Verdict) null);
  }

  @Test
  void aCycleNumberTooLargeForTheServedIntegerRefusesTheRequestInsteadOfDroppingTheCycle() {
    DetailFixture fixture =
        fixture(
            root -> {
              cycle(root, 1);
              write(root, "tasks/WP01-one/review-cycle-2147483648.md", cycleFile(1, "reviewer-renata", "2026-09-21T09:15:00+00:00"));
            });

    assertThatThrownBy(() -> detail(fixture, "WP01"))
        .isInstanceOfSatisfying(MissionStatusUnavailable.class, refusal -> assertThat(refusal.code()).isEqualTo(DiagnosticCode.SOURCE_UNREADABLE));
    assertThat(fixture.diagnostics()).containsExactly(new Diagnostic(DiagnosticCode.SOURCE_UNREADABLE, MID8, null));
  }

  @Test
  void theLastRowInLedgerFileOrderDecidesEvenWhenItIsTheEarlierInTime() {
    String ledger =
        ledger()
            + review(2, "2026-09-01T10:05:00Z", "WP01", "planned", "planned", pointer(1), "approved")
            + review(3, "2026-09-01T10:02:00Z", "WP01", "planned", "planned", pointer(1), "changes_requested");
    DetailFixture fixture = fixture(ledger, root -> cycle(root, 1));

    assertThat(cycles(fixture)).extracting(ReviewCycleEntry::verdict).containsExactly(Verdict.CHANGES_REQUESTED);
  }

  @Test
  void theLastEventThatNamesTheCycleDecidesAndATrimmedReferenceMatches() {
    String ledger =
        ledger()
            + review(2, "2026-09-01T10:02:00Z", "WP01", "planned", "planned", pointer(1), "changes_requested")
            + review(3, "2026-09-01T10:03:00Z", "WP01", "planned", "planned", "\"  " + POINTER + "1.md\\n \"", "approved")
            + review(4, "2026-09-01T10:04:00Z", "WP01", "planned", "planned", pointer(2), "approved")
            + review(5, "2026-09-01T10:05:00Z", "WP01", "planned", "planned", pointer(2), "unheard-of");
    DetailFixture fixture =
        fixture(
            ledger,
            root -> {
              cycle(root, 1);
              cycle(root, 2);
            });

    assertThat(cycles(fixture)).extracting(ReviewCycleEntry::verdict).containsExactly(Verdict.APPROVED, null);
  }

  @Test
  void aReferenceOfAnotherMissionOrWorkPackageOrWhichIsNotTextMatchesNothing() {
    String ledger =
        ledger()
            + review(2, "2026-09-01T10:02:00Z", "WP01", "planned", "planned", "\"review-cycle://beta/WP01-one/review-cycle-1.md\"", "approved")
            + review(3, "2026-09-01T10:03:00Z", "WP01", "planned", "planned", "\"review-cycle://alpha/WP02-two/review-cycle-1.md\"", "approved")
            + review(4, "2026-09-01T10:04:00Z", "WP01", "planned", "planned", "7", "approved")
            + review(5, "2026-09-01T10:05:00Z", "WP02", "planned", "planned", pointer(1), "approved");
    DetailFixture fixture = fixture(ledger, root -> cycle(root, 1));

    assertThat(cycles(fixture)).extracting(ReviewCycleEntry::verdict).containsExactly((Verdict) null);
  }

  @Test
  void aFileThatDoesNotParseIsStillAnEntryWithNullMembersAndNoDiagnostic() {
    DetailFixture fixture =
        fixture(
            ledger() + review(2, "2026-09-01T10:02:00Z", "WP01", "planned", "planned", pointer(1), "approved"),
            root -> write(root, "tasks/WP01-one/review-cycle-1.md", "no frontmatter here\n"));

    ReviewCycleEntry entry = cycles(fixture).get(0);

    assertThat(entry.reviewedAt()).isNull();
    assertThat(entry.reviewer()).isNull();
    assertThat(entry.verdict()).isEqualTo(Verdict.APPROVED);
    assertThat(entry.artifactPath()).isEqualTo("tasks/WP01-one/review-cycle-1.md");
    assertThat(fixture.diagnostics()).isEmpty();
  }

  /** AC-3.9: 262144 bytes are parsed and 262145 are not; the entry stays either way and nothing is written. */
  @Test
  void aCycleFileOfExactlyTheCapIsParsedAndOneByteMoreIsAnEntryWithNullMembers() {
    String base = cycleFile(1, "reviewer-renata", "2026-09-21T09:15:00+00:00");
    String atCap = base + "x".repeat(262_144 - base.getBytes(StandardCharsets.UTF_8).length);
    String overCap = atCap + "x";
    DetailFixture at = fixture(root -> write(root, "tasks/WP01-one/review-cycle-1.md", atCap));
    DetailFixture over = fixture(root -> write(root, "tasks/WP01-one/review-cycle-1.md", overCap));

    assertThat(atCap.getBytes(StandardCharsets.UTF_8)).hasSize(262_144);
    assertThat(cycles(at).get(0).reviewer()).isEqualTo("reviewer-renata");
    ReviewCycleEntry entry = cycles(over).get(0);
    assertThat(entry.reviewer()).isNull();
    assertThat(entry.reviewedAt()).isNull();
    assertThat(entry.cycleNumber()).isEqualTo(1);
    assertThat(entry.artifactPath()).isEqualTo("tasks/WP01-one/review-cycle-1.md");
    assertThat(over.diagnostics()).isEmpty();
  }

  @Test
  void aSymbolicLinkCycleFileIsAnEntryWithNullMembersAndNoPathAndItsTargetIsNeverRead() {
    DetailFixture fixture =
        fixture(
            ledger() + review(2, "2026-09-01T10:02:00Z", "WP01", "planned", "planned", pointer(1), "approved"),
            root -> {
              write(root, "elsewhere.md", cycleFile(1, "reviewer-renata", "2026-09-21T09:15:00+00:00"));
              DetailRoute.symlink(root.resolve("kitty-specs/alpha/tasks/WP01-one/review-cycle-1.md"), root.resolve("kitty-specs/alpha/elsewhere.md"));
            });
    fixture.recorder().clear();

    ReviewCycleEntry entry = cycles(fixture).get(0);

    assertThat(entry.reviewer()).isNull();
    assertThat(entry.reviewedAt()).isNull();
    assertThat(entry.artifactPath()).isNull();
    assertThat(entry.verdict()).as("the verdict is the ledger's").isEqualTo(Verdict.APPROVED);
    assertThat(entry.feedbackReference()).isEqualTo(POINTER + "1.md");
    assertThat(fixture.recorder().accesses())
        .filteredOn(access -> access.mode() == Allowlist.OpenMode.READ)
        .noneMatch(access -> access.path().contains("elsewhere") || access.path().contains("review-cycle"));
  }

  @Test
  void aDirectoryNamedLikeACycleFileIsAnEntryWithNullMembers() {
    DetailFixture fixture = fixture(root -> DetailRoute.directory(root, "kitty-specs/alpha/tasks/WP01-one/review-cycle-1.md"));

    ReviewCycleEntry entry = cycles(fixture).get(0);

    assertThat(entry.reviewer()).isNull();
    assertThat(entry.artifactPath()).isNull();
  }

  @Test
  void aWorkPackageDirectoryThatIsALinkIsNotEnteredAndHasNoCycles() {
    DetailFixture fixture =
        fixture(
            root -> {
              write(root, "elsewhere/review-cycle-1.md", cycleFile(1, "reviewer-renata", "2026-09-21T09:15:00+00:00"));
              DetailRoute.symlink(root.resolve("kitty-specs/alpha/tasks/WP01-one"), root.resolve("kitty-specs/alpha/elsewhere"));
            });
    fixture.recorder().clear();

    assertThat(cycles(fixture)).isEmpty();
    assertThat(fixture.diagnostics()).isEmpty();
    assertThat(fixture.recorder().accesses()).noneMatch(access -> access.path().contains("elsewhere"));
  }

  @Test
  void aWorkPackageWithoutAPromptFileHasNoCycles() {
    DetailFixture fixture =
        fixture(
            root -> {
              DetailRoute.delete(root, "tasks/WP01-one.md");
              write(root, "tasks/WP01.md", wpFile("WP01", "One"));
              cycle(root, 1);
            });

    assertThat(cycles(fixture)).isEmpty();
  }

  @Test
  void onlyFilesNamedLikeCyclesAreCyclesAndTheDirectoryIsOptional() {
    DetailFixture fixture =
        fixture(
            root -> {
              cycle(root, 3);
              for (String name : new String[] {"review-cycle-0.md", "review-cycle-01.md", "review-cycle-3.txt", "notes.md", "Review-cycle-4.md"}) {
                write(root, "tasks/WP01-one/" + name, "x\n");
              }
            });
    DetailFixture none = fixture(root -> {});

    assertThat(cycles(fixture)).extracting(ReviewCycleEntry::cycleNumber).containsExactly(3);
    assertThat(cycles(none)).isEmpty();
  }

  @Test
  void theReviewerIsAHandleOrNullAndNeverATokenOrFreeText() {
    DetailFixture fixture =
        fixture(
            root -> {
              write(root, "tasks/WP01-one/review-cycle-1.md", cycleFile(1, "\"Reviewer Renata\"", "2026-09-21T09:15:00+00:00"));
              write(root, "tasks/WP01-one/review-cycle-2.md", cycleFile(2, secret(), "2026-09-21T09:15:00+00:00"));
              write(root, "tasks/WP01-one/review-cycle-3.md", cycleFile(3, "claude:opus-5.5", "2026-09-21T09:15:00+00:00"));
            });

    assertThat(cycles(fixture)).extracting(ReviewCycleEntry::reviewer).containsExactly(null, null, "claude:opus-5.5");
  }

  @Test
  void aReviewTimeThatIsNoDateTimeIsNull() {
    DetailFixture fixture =
        fixture(
            root -> {
              write(root, "tasks/WP01-one/review-cycle-1.md", cycleFile(1, "reviewer-renata", "2026-09-21"));
              write(root, "tasks/WP01-one/review-cycle-2.md", cycleFile(2, "reviewer-renata", "yesterday"));
              write(root, "tasks/WP01-one/review-cycle-3.md", cycleFile(3, "reviewer-renata", "2026-09-21T09:15:00Z"));
            });

    assertThat(cycles(fixture)).extracting(ReviewCycleEntry::reviewedAt).containsExactly(null, null, "2026-09-21T09:15:00Z");
  }

}
