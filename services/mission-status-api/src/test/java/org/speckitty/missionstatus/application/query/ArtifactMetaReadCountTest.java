package org.speckitty.missionstatus.application.query;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.file.Path;
import java.util.EnumSet;
import java.util.List;
import java.util.Set;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.Access;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.OpenMode;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.PathClass;
import org.speckitty.missionstatus.application.query.ArtifactQueryServiceTest.Trees;
import org.speckitty.missionstatus.testsupport.DetailFixture;
import org.speckitty.missionstatus.testsupport.MetaReadCounter;

/**
 * AC-1.8: the artifact routes read the {@code meta.json} of the matched Mission exactly once and of every other Mission once (the lookup
 * and its duplicate continuation), whether the match sorts first or last; and they never touch the ledger or a coordination class, so a
 * Mission whose ledger is unreadable is answered as a healthy one.
 */
class ArtifactMetaReadCountTest {

  private static final String FIRST_ID = "00000000000000000000000002";
  private static final String MIDDLE_ID = "00000000000000000000000003";
  private static final String LAST_ID = "00000000000000000000000004";

  /** Three Missions sorted by directory name: {@code a-first}, {@code m-middle}, {@code z-last}. */
  private static DetailFixture three() {
    DetailFixture fixture = Trees.fixture("artifacts-populated", "artifacts-populated");
    Path specs = fixture.root().resolve("kitty-specs");
    Trees.write(specs.resolve("a-first").resolve("meta.json"), Trees.meta(FIRST_ID, "a-first"));
    Trees.write(specs.resolve("a-first").resolve("spec.md"), "first\n");
    Trees.write(specs.resolve("m-middle").resolve("meta.json"), Trees.meta(MIDDLE_ID, "m-middle"));
    Trees.write(specs.resolve("z-last").resolve("meta.json"), Trees.meta(LAST_ID, "z-last"));
    Trees.write(specs.resolve("z-last").resolve("spec.md"), "last\n");
    return fixture;
  }

  private static long metaReads(DetailFixture fixture, String directory) {
    return fixture.recorder().accesses().stream().filter(access -> access.pathClass() == PathClass.MISSION_META && access.mode() == OpenMode.READ && access.path().endsWith("/" + directory + "/meta.json")).count();
  }

  private static final List<String> DIRECTORIES = List.of("a-first", "alpha-mission", "m-middle", "z-last");

  private void everyMissionOnceFor(String id, boolean listing) {
    DetailFixture fixture = three();
    ArtifactQueryService service = Trees.service(fixture);
    MetaReadCounter counter = new MetaReadCounter();
    counter.reset(fixture.recorder());

    if (listing) {
      service.list(org.speckitty.missionstatus.domain.model.MissionId.parse(id).orElseThrow());
    } else {
      service.content(org.speckitty.missionstatus.domain.model.MissionId.parse(id).orElseThrow(), Trees.path("spec.md"));
    }

    assertThat(DIRECTORIES).as("the discovered Missions: the floor of the control").hasSize(4);
    for (String directory : DIRECTORIES) {
      assertThat(metaReads(fixture, directory)).as("meta.json reads of " + directory + " for " + id).isEqualTo(1);
    }
    assertThat(counter.count(fixture.recorder())).as("all reads of a meta.json").isEqualTo(DIRECTORIES.size());
  }

  @Test
  void theFirstSortedMatchAndEveryOtherMissionAreReadOnceByTheListing() {
    everyMissionOnceFor(FIRST_ID, true);
  }

  @Test
  void theLastSortedMatchAndEveryOtherMissionAreReadOnceByTheListing() {
    everyMissionOnceFor(LAST_ID, true);
  }

  @Test
  void theFirstSortedMatchAndEveryOtherMissionAreReadOnceByTheContentRead() {
    everyMissionOnceFor(FIRST_ID, false);
  }

  @Test
  void theLastSortedMatchAndEveryOtherMissionAreReadOnceByTheContentRead() {
    everyMissionOnceFor(LAST_ID, false);
  }

  @Test
  void aMiddleMissionIsAlsoReadOnce() {
    everyMissionOnceFor(MIDDLE_ID, true);
  }

  private static final Set<PathClass> ALLOWED =
      EnumSet.of(PathClass.SPECS_DIR, PathClass.MISSION_DIR, PathClass.MISSION_META, PathClass.ARTIFACT_DIR, PathClass.ARTIFACT_FILE, PathClass.PROJECT_ROOT);

  @Test
  void anUnreadableLedgerIsAnsweredAsAHealthyMissionAndNoLedgerOrCoordinationClassIsTouched() {
    DetailFixture fixture = Trees.fixture("artifacts-populated", "artifacts-populated");
    // the M2 fixture: a ledger that cannot be parsed, and one that cannot be read at all
    Trees.write(Trees.mission(fixture).resolve("status.events.jsonl"), "{broken\n");
    ArtifactQueryService service = Trees.service(fixture);
    fixture.recorder().clear();

    var listing = service.list(Trees.id());
    var content = service.content(Trees.id(), Trees.path("spec.md"));

    assertThat(listing.entries()).isNotEmpty();
    assertThat(content.content()).isNotEmpty();
    List<Access> accesses = fixture.recorder().accesses();
    assertThat(accesses).as("the control: the routes did read").isNotEmpty();
    assertThat(accesses).noneMatch(access -> access.pathClass() == PathClass.LEDGER);
    assertThat(accesses).allMatch(access -> access.pathClass() != null && ALLOWED.contains(access.pathClass()));
    assertThat(fixture.diagnostics()).isEmpty();
  }

  @Test
  void theControlSeesALedgerReadWhenOneIsMade() {
    DetailFixture fixture = Trees.fixture("artifacts-populated", "artifacts-populated");
    fixture.recorder().clear();

    fixture.built().source().readLedger(new org.speckitty.missionstatus.application.query.port.out.dto.MissionRef("alpha-mission"), fixture.built().source().stampLedger(new org.speckitty.missionstatus.application.query.port.out.dto.MissionRef("alpha-mission")));

    assertThat(fixture.recorder().accesses()).anyMatch(access -> access.pathClass() == PathClass.LEDGER);
  }
}
