package org.speckitty.missionstatus.application.query;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.ID;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.MID8;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.cycleFile;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.detail;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.fixture;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.lanes;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.ledger;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.review;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.secret;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.subtasks;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.write;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.wpFile;

import java.util.List;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.application.query.detail.DetailRoute;
import org.speckitty.missionstatus.application.query.port.in.exceptions.DetailRefusal;
import org.speckitty.missionstatus.application.query.port.in.exceptions.MissionStatusUnavailable;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.domain.model.Lane;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.domain.model.WpId;
import org.speckitty.missionstatus.domain.readmodel.detail.DependencyEntry;
import org.speckitty.missionstatus.domain.readmodel.detail.OwnedFileEntry;
import org.speckitty.missionstatus.domain.readmodel.detail.SubtaskEntry;
import org.speckitty.missionstatus.domain.readmodel.detail.WorkPackageDetail;
import org.speckitty.missionstatus.testsupport.DetailFixture;

/**
 * The Work Package detail at the port: the subtasks, dependencies, owned files and the identity rules (W1, FR-006), on the real service over a
 * fixture. The review cycles, the workspace and the artifact references have their own classes ({@code WorkPackageDetailCyclesTest},
 * {@code WorkPackageDetailWorkspaceTest}, {@code WorkPackageDetailReferencesTest}); the failure rows have {@code WorkPackageDetailRowsTest}.
 */
class WorkPackageDetailQueryServiceTest {

  private static final String TASKS =
      "# Tasks\n\n## WP01 One\n\n- [ ] T001 First\n- [ ] T002 **Second one**\n\n## WP02 Two\n\n- [ ] T003 Other package\n";

  private static List<DiagnosticCode> codes(DetailFixture fixture) {
    return fixture.diagnostics().stream().map(Diagnostic::code).toList();
  }

  private static MissionStatusUnavailable refused(DetailFixture fixture, String wp) {
    Throwable thrown = org.assertj.core.api.Assertions.catchThrowable(() -> detail(fixture, wp));
    assertThat(thrown).isInstanceOf(MissionStatusUnavailable.class);
    return (MissionStatusUnavailable) thrown;
  }

  // ---- identity: W1 -----------------------------------------------------------------------------------------------------------------

  @Test
  void theDetailNamesTheMissionAndTheWorkPackageOfTheRequest() {
    DetailFixture fixture = fixture(root -> {});

    WorkPackageDetail served = detail(fixture, "WP01");

    assertThat(served.missionId()).isEqualTo(new MissionId(ID));
    assertThat(served.wpId()).isEqualTo(new WpId("WP01"));
    assertThat(served.subtasks()).isEmpty();
    assertThat(served.dependencies()).isEmpty();
    assertThat(served.reviewCycles()).isEmpty();
    assertThat(served.ownedFiles()).isEmpty();
    assertThat(codes(fixture)).isEmpty();
  }

  @Test
  void aWorkPackageNoFileHoldsIsNotFoundAlthoughTheLedgerNamesIt() {
    DetailFixture fixture = fixture(ledger() + org.speckitty.missionstatus.testsupport.Rows.status(org.speckitty.missionstatus.testsupport.Rows.id(2), "2026-09-01T10:02:00Z", "WP07", "planned", "claimed"), root -> {});

    assertThatThrownBy(() -> detail(fixture, "WP07")).isInstanceOfSatisfying(DetailRefusal.class, refusal -> assertThat(refusal.kind()).isEqualTo(DetailRefusal.Kind.NOT_FOUND));
    assertThatThrownBy(() -> detail(fixture, "WP99")).isInstanceOf(DetailRefusal.class);
    assertThat(detail(fixture, "WP01").wpId().value()).isEqualTo("WP01");
  }

  @Test
  void theFileThatHoldsTheIdInItsFrontmatterIsTheWorkPackageWhateverItIsCalled() {
    DetailFixture fixture = fixture(root -> write(root, "tasks/WP05-other.md", wpFile("WP02", "Two", "subtasks: [T003]")));

    assertThat(detail(fixture, "WP02").subtasks()).extracting(SubtaskEntry::id).containsExactly("T003");
    assertThatThrownBy(() -> detail(fixture, "WP05")).isInstanceOf(DetailRefusal.class);
  }

  // ---- subtasks ---------------------------------------------------------------------------------------------------------------------

  @Test
  void theSubtasksAreTheAuthoredRosterWithTitlesFromTasksMdAndLanesFromTheLedger() {
    DetailFixture fixture =
        fixture(
            ledger() + subtasks(2, "2026-09-01T10:02:00Z", "WP01", "{\"T001\":\"done\",\"T002\":\"in_progress\"}"),
            root -> {
              write(root, "tasks/WP01-one.md", wpFile("WP01", "One", "subtasks: [T002, T001, T003]"));
              write(root, "tasks.md", TASKS);
            });

    assertThat(detail(fixture, "WP01").subtasks())
        .containsExactly(new SubtaskEntry("T002", "Second one", Lane.IN_PROGRESS), new SubtaskEntry("T001", "First", Lane.DONE), new SubtaskEntry("T003", null, null));
    assertThat(codes(fixture)).isEmpty();
  }

  @Test
  void aSubtaskWithoutARecordedStatusHasNoLaneAndIsNeverPlanned() {
    DetailFixture fixture = fixture(root -> write(root, "tasks/WP01-one.md", wpFile("WP01", "One", "subtasks: [T001]")));

    assertThat(detail(fixture, "WP01").subtasks()).containsExactly(new SubtaskEntry("T001", null, null));
  }

  @Test
  void withoutTasksMdEverySubtaskTitleIsNull() {
    DetailFixture fixture = fixture(root -> write(root, "tasks/WP01-one.md", wpFile("WP01", "One", "subtasks: [T001]")));

    assertThat(detail(fixture, "WP01").subtasks()).extracting(SubtaskEntry::title).containsExactly((String) null);
  }

  @Test
  void aTasksMdThatIsADirectoryOrALinkGivesNoTitlesAndNoError() {
    DetailFixture directory = fixture(root -> {
      write(root, "tasks/WP01-one.md", wpFile("WP01", "One", "subtasks: [T001]"));
      DetailRoute.directory(root, "kitty-specs/alpha/tasks.md");
    });
    DetailFixture link =
        fixture(
            root -> {
              write(root, "tasks/WP01-one.md", wpFile("WP01", "One", "subtasks: [T001]"));
              write(root, "elsewhere.md", "## WP01\n- [ ] T001 Hidden\n");
              DetailRoute.symlink(root.resolve("kitty-specs/alpha/tasks.md"), root.resolve("kitty-specs/alpha/elsewhere.md"));
            });

    assertThat(detail(directory, "WP01").subtasks()).extracting(SubtaskEntry::title).containsExactly((String) null);
    assertThat(detail(link, "WP01").subtasks()).extracting(SubtaskEntry::title).containsExactly((String) null);
  }

  /** The obligation of WP05 review N3 (D-159 d): a subtask status outside the nine display lanes is refused, never null. One test per case. */
  @Test
  void aSubtaskStatusOfGenesisIsAProjectionRefusalNotANull() {
    DetailFixture fixture =
        fixture(
            ledger() + subtasks(2, "2026-09-01T10:02:00Z", "WP01", "{\"T001\":\"genesis\"}"),
            root -> write(root, "tasks/WP01-one.md", wpFile("WP01", "One", "subtasks: [T001]")));

    assertThat(refused(fixture, "WP01").code()).isEqualTo(DiagnosticCode.PROJECTION_REFUSED);
  }

  @Test
  void aSubtaskStatusOfUninitializedIsAProjectionRefusalNotANull() {
    DetailFixture fixture =
        fixture(
            ledger() + subtasks(2, "2026-09-01T10:02:00Z", "WP01", "{\"T001\":\"uninitialized\"}"),
            root -> write(root, "tasks/WP01-one.md", wpFile("WP01", "One", "subtasks: [T001]")));

    assertThat(refused(fixture, "WP01").code()).isEqualTo(DiagnosticCode.PROJECTION_REFUSED);
    assertThat(codes(fixture)).contains(DiagnosticCode.PROJECTION_REFUSED);
  }

  @Test
  void aSubtaskStatusOfEveryDisplayLaneIsServed() {
    for (Lane lane : Lane.displayLanes()) {
      DetailFixture fixture =
          fixture(
              ledger() + subtasks(2, "2026-09-01T10:02:00Z", "WP01", "{\"T001\":\"" + lane.wire() + "\"}"),
              root -> write(root, "tasks/WP01-one.md", wpFile("WP01", "One", "subtasks: [T001]")));

      assertThat(detail(fixture, "WP01").subtasks()).as(lane.wire()).extracting(SubtaskEntry::statusLane).containsExactly(lane);
    }
  }

  /** SK-353 (V20, D-97): subtasks written as mappings have a Python str() this service does not reproduce. */
  @Test
  void subtasksWrittenAsMappingsAreAProjectionRefusal() {
    DetailFixture fixture = fixture(root -> write(root, "tasks/WP01-one.md", wpFile("WP01", "One", "subtasks:", "  - id: T001", "    title: x")));

    MissionStatusUnavailable unavailable = refused(fixture, "WP01");

    assertThat(unavailable.code()).isEqualTo(DiagnosticCode.PROJECTION_REFUSED);
    assertThat(codes(fixture)).containsExactly(DiagnosticCode.PROJECTION_REFUSED);
  }

  @Test
  void aSubtaskReferenceThatCannotBeShownRefusesTheWorkPackage() {
    for (String bad : new String[] {"/home/someone/private", "~x", "\\\\x", "C:\\\\x"}) {
      DetailFixture fixture = fixture(root -> write(root, "tasks/WP01-one.md", wpFile("WP01", "One", "subtasks:", "  - \"" + bad.replace("\\", "\\\\") + "\"")));

      assertThat(refused(fixture, "WP01").code()).as(bad).isEqualTo(DiagnosticCode.PROJECTION_REFUSED);
    }
  }

  // ---- M12: titles the projection cannot show --------------------------------------------------------------------------------------

  @Test
  void aSubtaskTitleHoldingACredentialIsWithheldWithOneDiagnosticAndTheRestIsServed() {
    DetailFixture fixture =
        fixture(
            root -> {
              write(root, "tasks/WP01-one.md", wpFile("WP01", "One", "subtasks: [T001, T002]"));
              write(root, "tasks.md", "## WP01\n- [ ] T001 Rotate " + secret() + " now\n- [ ] T002 Fine\n");
            });

    List<SubtaskEntry> served = detail(fixture, "WP01").subtasks();

    assertThat(served).extracting(SubtaskEntry::title).containsExactly(null, "Fine");
    assertThat(fixture.diagnostics()).containsExactly(new Diagnostic(DiagnosticCode.PROJECTION_REFUSED, MID8, null));
  }

  @Test
  void aSubtaskTitleHoldingOnlyAHostPathIsServedWithThePathReplacedAndNoDiagnostic() {
    DetailFixture fixture =
        fixture(
            root -> {
              write(root, "tasks/WP01-one.md", wpFile("WP01", "One", "subtasks: [T001]"));
              write(root, "tasks.md", "## WP01\n- [ ] T001 Edit /home/someone/private/file.txt today\n");
            });

    assertThat(detail(fixture, "WP01").subtasks()).extracting(SubtaskEntry::title).containsExactly("Edit [path] today");
    assertThat(codes(fixture)).isEmpty();
  }

  @Test
  void aDependencyTitleHoldingACredentialIsTheIdWithOneDiagnostic() {
    DetailFixture fixture =
        fixture(
            root -> {
              write(root, "tasks/WP01-one.md", wpFile("WP01", "One", "dependencies: [WP02]"));
              write(root, "tasks/WP02-two.md", wpFile("WP02", "Rotate " + secret()));
            });

    List<DependencyEntry> served = detail(fixture, "WP01").dependencies();

    assertThat(served).extracting(entry -> entry.wpId().value(), DependencyEntry::title).containsExactly(org.assertj.core.groups.Tuple.tuple("WP02", "WP02"));
    assertThat(fixture.diagnostics()).containsExactly(new Diagnostic(DiagnosticCode.PROJECTION_REFUSED, MID8, null));
  }

  @Test
  void aSubtaskTitleWithACredentialInsideAHostPathIsWithheldBecauseTheRawTextIsCheckedFirst() {
    DetailFixture fixture =
        fixture(
            root -> {
              write(root, "tasks/WP01-one.md", wpFile("WP01", "One", "subtasks: [T001]"));
              write(root, "tasks.md", "## WP01\n- [ ] T001 Edit /home/x/" + secret() + " today\n");
            });

    assertThat(detail(fixture, "WP01").subtasks()).extracting(SubtaskEntry::title).containsExactly((String) null);
    assertThat(fixture.diagnostics()).containsExactly(new Diagnostic(DiagnosticCode.PROJECTION_REFUSED, MID8, null));
  }

  @Test
  void aDependencyTitleWithACredentialInsideAHostPathIsTheIdBecauseTheRawTextIsCheckedFirst() {
    DetailFixture fixture =
        fixture(
            root -> {
              write(root, "tasks/WP01-one.md", wpFile("WP01", "One", "dependencies: [WP02]"));
              write(root, "tasks/WP02-two.md", wpFile("WP02", "Edit /home/x/" + secret() + " today"));
            });

    assertThat(detail(fixture, "WP01").dependencies())
        .extracting(entry -> entry.wpId().value(), DependencyEntry::title)
        .containsExactly(org.assertj.core.groups.Tuple.tuple("WP02", "WP02"));
    assertThat(fixture.diagnostics()).containsExactly(new Diagnostic(DiagnosticCode.PROJECTION_REFUSED, MID8, null));
  }

  // ---- dependencies -----------------------------------------------------------------------------------------------------------------

  @Test
  void theDependenciesAreInAuthoredOrderWithTheDisplayTitleAndTheLaneOfTheStatusModel() {
    DetailFixture fixture =
        fixture(
            ledger() + org.speckitty.missionstatus.testsupport.Rows.status(org.speckitty.missionstatus.testsupport.Rows.id(2), "2026-09-01T10:02:00Z", "WP02", "planned", "done"),
            root -> {
              write(root, "tasks/WP01-one.md", wpFile("WP01", "One", "dependencies: [WP03, WP02, WP09]"));
              write(root, "tasks/WP02-two.md", wpFile("WP02", "  Padded two  "));
              write(root, "tasks/WP03-three.md", wpFile("WP03", "Three"));
            });

    List<DependencyEntry> served = detail(fixture, "WP01").dependencies();

    assertThat(served)
        .extracting(entry -> entry.wpId().value(), DependencyEntry::title, DependencyEntry::statusLane)
        .containsExactly(
            org.assertj.core.groups.Tuple.tuple("WP03", "Three", null),
            org.assertj.core.groups.Tuple.tuple("WP02", "Padded two", Lane.DONE),
            org.assertj.core.groups.Tuple.tuple("WP09", "WP09", null));
  }

  @Test
  void aDependencyWhoseTitleIsBlankOrMissingIsServedUnderItsId() {
    DetailFixture fixture =
        fixture(
            root -> {
              write(root, "tasks/WP01-one.md", wpFile("WP01", "One", "dependencies: [WP02, WP03]"));
              write(root, "tasks/WP02-two.md", wpFile("WP02", "   "));
              write(root, "tasks/WP03-three.md", "---\nwork_package_id: WP03\n---\n\nBody\n");
            });

    assertThat(detail(fixture, "WP01").dependencies()).extracting(DependencyEntry::title).containsExactly("WP02", "WP03");
  }

  @Test
  void aDependencyThatIsNotAWorkPackageIdRefusesTheWorkPackage() {
    DetailFixture fixture = fixture(root -> write(root, "tasks/WP01-one.md", wpFile("WP01", "One", "dependencies: [\"/home/someone/private\"]")));
    DetailFixture shaped = fixture(root -> write(root, "tasks/WP01-one.md", wpFile("WP01", "One", "dependencies: [WP02x]")));

    assertThat(refused(fixture, "WP01").code()).isEqualTo(DiagnosticCode.PROJECTION_REFUSED);
    assertThat(refused(shaped, "WP01").code()).isEqualTo(DiagnosticCode.PROJECTION_REFUSED);
  }

  // ---- owned files ------------------------------------------------------------------------------------------------------------------

  @Test
  void theOwnedFilesAreInAuthoredOrderWithTheirGlobFlagAndAChangeStateThatIsAlwaysUnknown() {
    DetailFixture fixture = fixture(root -> write(root, "tasks/WP01-one.md", wpFile("WP01", "One", "owned_files:", "  - src/app/**", "  - README.md", "  - docs/a?.md", "  - \"{a,b}.md\"", "  - notes/[ab].md")));

    assertThat(detail(fixture, "WP01").ownedFiles())
        .containsExactly(
            new OwnedFileEntry("src/app/**", true, OwnedFileEntry.ChangeState.UNKNOWN),
            new OwnedFileEntry("README.md", false, OwnedFileEntry.ChangeState.UNKNOWN),
            new OwnedFileEntry("docs/a?.md", true, OwnedFileEntry.ChangeState.UNKNOWN),
            new OwnedFileEntry("{a,b}.md", true, OwnedFileEntry.ChangeState.UNKNOWN),
            new OwnedFileEntry("notes/[ab].md", true, OwnedFileEntry.ChangeState.UNKNOWN));
  }

  @Test
  void anOwnedFilePatternThatCannotBeShownRefusesTheWorkPackage() {
    DetailFixture fixture = fixture(root -> write(root, "tasks/WP01-one.md", wpFile("WP01", "One", "owned_files:", "  - /home/someone/private/file.py")));

    MissionStatusUnavailable unavailable = refused(fixture, "WP01");

    assertThat(unavailable.code()).isEqualTo(DiagnosticCode.PROJECTION_REFUSED);
    assertThat(unavailable.getMessage()).doesNotContain("someone");
  }

  // ---- no change state is ever computed -----------------------------------------------------------------------------------------------

  @Test
  void noProcessIsStartedAndNeitherGitNorTheWorktreeIsOpened() {
    DetailFixture fixture =
        fixture(
            root -> {
              write(root, "lanes.json", lanes("alpha", "lane-a:WP01"));
              DetailRoute.writeAtRoot(root, ".worktrees/alpha-lane-a/.git", "gitdir: elsewhere\n");
            });
    fixture.recorder().clear();

    detail(fixture, "WP01");

    assertThat(fixture.recorder().accesses())
        .filteredOn(access -> access.path().startsWith(".worktrees/"))
        .allSatisfy(access -> assertThat(access.mode()).isEqualTo(org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.OpenMode.STAT));
    assertThat(fixture.recorder().violations()).isEmpty();
  }
}
