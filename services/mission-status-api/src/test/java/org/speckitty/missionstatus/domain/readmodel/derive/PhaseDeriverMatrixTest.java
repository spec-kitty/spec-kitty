package org.speckitty.missionstatus.domain.readmodel.derive;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.EnumSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Stream;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.MethodSource;
import org.speckitty.missionstatus.domain.model.StatusSnapshot;
import org.speckitty.missionstatus.domain.readmodel.detail.MissionPhase;
import org.speckitty.missionstatus.domain.readmodel.detail.PhaseBasis;
import org.speckitty.missionstatus.domain.readmodel.detail.PhaseName;
import org.speckitty.missionstatus.domain.readmodel.detail.PhaseStatus;
import org.speckitty.missionstatus.testsupport.CanonicalJson;
import org.speckitty.missionstatus.testsupport.ConformanceTree;
import org.speckitty.missionstatus.testsupport.ConformanceTree.TreeFixture;
import org.speckitty.missionstatus.testsupport.DetailFixture;

/**
 * AC-1.3: the phase table over the committed {@code phases-matrix} class. The inputs are read from the provisioned scratch copy of each
 * fixture (the reduction of its ledger, and a link-free {@code lstat} of the three planning files), the expected phases from its golden.
 * The four link fixtures are known divergences (V1): their golden is the oracle's (a link is followed), so their expectation is pinned in
 * this test (a link is not an artifact) and every other fixture is compared with its golden unchanged. The fixtures are iterated from the
 * manifest listing, never from a literal count.
 */
class PhaseDeriverMatrixTest {

  private static final Map<PhaseName, String> FILES = Map.of(PhaseName.SPECIFY, "spec.md", PhaseName.PLAN, "plan.md", PhaseName.TASKS, "tasks.md");

  /** The pinned Java outcome of the link fixtures: the three links are no artifacts, so the events decide (status, basis) for all three. */
  private static final Map<String, String[]> LINK_FIXTURES =
      Map.of(
          "phases-matrix/ps-link-file", new String[] {"pending", "artifact"},
          "phases-matrix/ps-link-completed", new String[] {"complete", "lifecycle_event"},
          "phases-matrix/ps-link-started", new String[] {"in_progress", "lifecycle_event"},
          "phases-matrix/ps-link-neither", new String[] {"pending", "artifact"});

  static Stream<TreeFixture> fixtures() {
    return ConformanceTree.detailFixtures().stream().filter(fixture -> fixture.tag().equals("phases-matrix"));
  }

  @Test
  void theMatrixIsIteratedFromTheManifestAndHoldsTheLinkFixturesAndTheMarkerRow() {
    List<String> names = fixtures().map(TreeFixture::name).toList();

    assertThat(names).hasSizeGreaterThanOrEqualTo(19).contains("marker-row-without-event-id");
    assertThat(names.stream().filter(name -> name.startsWith("ps-link-")).count()).isEqualTo(4);
    assertThat(fixtures().filter(TreeFixture::knownDivergence).map(TreeFixture::key)).containsExactlyInAnyOrderElementsOf(LINK_FIXTURES.keySet());
  }

  @ParameterizedTest(name = "{0}")
  @MethodSource("fixtures")
  void thePhasesOfEveryFixtureEqualTheGoldenOrThePinnedLinkOutcome(TreeFixture fixture) {
    DetailFixture detail = DetailFixture.of(fixture.dir());
    Path mission = missionDirectory(detail.root());
    StatusSnapshot snapshot = detail.reduce(mission.getFileName().toString());
    Set<PhaseName> artifacts = artifacts(mission);

    List<MissionPhase> phases = PhaseDeriver.derive(snapshot.laneCounts(), snapshot.workPackages().size(), artifacts, snapshot.lifecycleTypes());

    if (LINK_FIXTURES.containsKey(fixture.key())) {
      assertThat(artifacts).as("a link is not an artifact").isEmpty();
      String[] expected = LINK_FIXTURES.get(fixture.key());
      for (PhaseName name : EnumSet.of(PhaseName.SPECIFY, PhaseName.PLAN, PhaseName.TASKS)) {
        MissionPhase phase = phases.get(name.ordinal());
        assertThat(phase.status().wire()).as(fixture.key() + " " + name).isEqualTo(expected[0]);
        assertThat(phase.basis().wire()).as(fixture.key() + " " + name).isEqualTo(expected[1]);
      }
      return;
    }
    assertThat(wire(phases)).as(fixture.key()).isEqualTo(goldenPhases(fixture));
  }

  @Test
  void aLinkFixtureAgreesWithItsGoldenOnlyWhereTheOracleAndTheLinkRuleCoincide() {
    // the control that makes the link rule bite: with the three files taken as present, the link fixtures WOULD equal their golden
    for (String key : LINK_FIXTURES.keySet()) {
      TreeFixture fixture = fixtures().filter(candidate -> candidate.key().equals(key)).findFirst().orElseThrow();
      DetailFixture detail = DetailFixture.of(fixture.dir());
      StatusSnapshot snapshot = detail.reduce(missionDirectory(detail.root()).getFileName().toString());

      List<MissionPhase> followed = PhaseDeriver.derive(snapshot.laneCounts(), snapshot.workPackages().size(), EnumSet.of(PhaseName.SPECIFY, PhaseName.PLAN, PhaseName.TASKS), snapshot.lifecycleTypes());
      List<MissionPhase> notFollowed = PhaseDeriver.derive(snapshot.laneCounts(), snapshot.workPackages().size(), Set.of(), snapshot.lifecycleTypes());

      assertThat(wire(followed)).as(key).isEqualTo(goldenPhases(fixture));
      assertThat(notFollowed.get(0)).as(key).isNotEqualTo(followed.get(0));
    }
  }

  @Test
  void theMarkerRowWithoutAnEventIdStillFeedsTheLifecycleTypes() {
    TreeFixture marker = fixtures().filter(fixture -> fixture.name().equals("marker-row-without-event-id")).findFirst().orElseThrow();
    DetailFixture detail = DetailFixture.of(marker.dir());

    StatusSnapshot snapshot = detail.reduce(missionDirectory(detail.root()).getFileName().toString());

    assertThat(snapshot.lifecycleTypes()).contains("SpecifyCompleted");
    assertThat(PhaseDeriver.derive(snapshot.laneCounts(), 0, Set.of(), snapshot.lifecycleTypes()).get(0))
        .isEqualTo(new MissionPhase(PhaseName.SPECIFY, PhaseStatus.COMPLETE, PhaseBasis.LIFECYCLE_EVENT));
  }

  // ---- inputs and expectations ---------------------------------------------------------------------------------------------------

  private static Path missionDirectory(Path root) {
    try (Stream<Path> children = Files.list(root.resolve("kitty-specs"))) {
      List<Path> directories = children.filter(Files::isDirectory).toList();
      assertThat(directories).hasSize(1);
      return directories.get(0);
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    }
  }

  private static Set<PhaseName> artifacts(Path mission) {
    Set<PhaseName> present = EnumSet.noneOf(PhaseName.class);
    FILES.forEach(
        (name, file) -> {
          if (Files.isRegularFile(mission.resolve(file), LinkOption.NOFOLLOW_LINKS)) {
            present.add(name);
          }
        });
    return present;
  }

  @SuppressWarnings("unchecked")
  private static List<String> goldenPhases(TreeFixture fixture) {
    Map<String, Object> golden = (Map<String, Object>) CanonicalJson.parse(ConformanceTree.golden(fixture, "get-mission.json"));
    Map<String, Object> body = (Map<String, Object>) golden.get("-");
    List<String> rows = new ArrayList<>();
    for (Object phase : (List<Object>) body.get("phases")) {
      Map<String, Object> row = (Map<String, Object>) phase;
      rows.add(row.get("name") + "/" + row.get("status") + "/" + row.get("basis"));
    }
    return rows;
  }

  private static List<String> wire(List<MissionPhase> phases) {
    return phases.stream().map(phase -> phase.name().wire() + "/" + phase.status().wire() + "/" + phase.basis().wire()).toList();
  }
}
