package org.speckitty.missionstatus.application.query.portlegs;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.application.query.AdmissionGate;
import org.speckitty.missionstatus.application.query.ArtifactQueryService;
import org.speckitty.missionstatus.application.query.port.in.dto.ArtifactPathInput;
import org.speckitty.missionstatus.application.query.port.in.exceptions.DetailRefusal;
import org.speckitty.missionstatus.domain.readmodel.detail.ArtifactContent;
import org.speckitty.missionstatus.domain.readmodel.detail.ArtifactKind;
import org.speckitty.missionstatus.domain.readmodel.detail.ArtifactListing;
import org.speckitty.missionstatus.domain.redaction.TextScreen;
import org.speckitty.missionstatus.testsupport.ConformanceTree;
import org.speckitty.missionstatus.testsupport.DetailFixture;
import org.speckitty.missionstatus.testsupport.LeakPatternsFile;
import org.speckitty.missionstatus.testsupport.PlainCaller;

/**
 * AC-13.3 for the artifact port: the second adapter, in plain Java and with no Spring context, calls {@code list} and {@code content} with
 * typed arguments and gets typed results or a {@link DetailRefusal} of the right kind. The legs live outside {@code conformance.port} and
 * are not listed in {@code portlevel-tests.txt}: the selector fixture of that set carries only {@code MissionStatusQuery}.
 */
class ArtifactPortLegsTest {

  private static final String ID = "00000000000000000000000001";

  private static PlainCaller caller(DetailFixture fixture) {
    ArtifactQueryService service = new ArtifactQueryService(fixture.readModel(), fixture.textSource(), new AdmissionGate(), fixture.built().handles().recorder(), new TextScreen(LeakPatternsFile.load()));
    return new PlainCaller(
        missionId -> {
          throw new UnsupportedOperationException("not part of this route");
        },
        (missionId, wpId, includePrompt) -> {
          throw new UnsupportedOperationException("not part of this route");
        },
        (missionId, wpId) -> {
          throw new UnsupportedOperationException("not part of this route");
        },
        service);
  }

  private static DetailFixture populated() {
    return DetailFixture.of(ConformanceTree.detailFixtures().stream().filter(f -> f.key().equals("artifacts-populated/artifacts-populated")).findFirst().orElseThrow().dir());
  }

  private static DetailRefusal.Kind kind(Runnable call) {
    return org.assertj.core.api.Assertions.catchThrowableOfType(DetailRefusal.class, call::run).kind();
  }

  @Test
  void listAndContentReturnTypedResultsForAPopulatedMission() {
    PlainCaller caller = caller(populated());

    ArtifactListing listing = caller.artifacts(ID);
    ArtifactContent content = caller.artifact(ID, new ArtifactPathInput.Values(List.of("spec.md")));

    assertThat(listing.missionId().value()).isEqualTo(ID);
    assertThat(listing.entries()).hasSize(14);
    assertThat(content.kind()).isEqualTo(ArtifactKind.SPEC);
    assertThat(content.content()).isNotEmpty();
  }

  @Test
  void anIdThatDoesNotParseIsNotFoundBeforeAnyPortIsCalledForBothOperations() {
    PlainCaller caller = caller(populated());

    assertThat(kind(() -> caller.artifacts("not-a-ulid"))).isEqualTo(DetailRefusal.Kind.NOT_FOUND);
    assertThat(kind(() -> caller.artifact("not-a-ulid", new ArtifactPathInput.Values(List.of("..%2fx"))))).isEqualTo(DetailRefusal.Kind.NOT_FOUND);
  }

  @Test
  void theRowsThatNeedNoPercentDecodingAreDecidedBehindThePort() {
    PlainCaller caller = caller(populated());
    List<ArtifactPathInput> invalid =
        List.of(
            new ArtifactPathInput.Values(List.of()), new ArtifactPathInput.Values(List.of("a", "b")), new ArtifactPathInput.Values(List.of("spec.md", "plan.md")),
            new ArtifactPathInput.Undecodable(), new ArtifactPathInput.Values(List.of("../x")), new ArtifactPathInput.Values(List.of("a//b")),
            new ArtifactPathInput.Values(List.of("a\\b")), new ArtifactPathInput.Values(List.of("")), new ArtifactPathInput.Values(List.of("x".repeat(513))));

    for (ArtifactPathInput input : invalid) {
      assertThat(kind(() -> caller.artifact(ID, input))).as(input.toString()).isEqualTo(DetailRefusal.Kind.INVALID_ARTIFACT_PATH);
    }
    assertThat(kind(() -> caller.artifact(ID, new ArtifactPathInput.Values(List.of("missing.md"))))).isEqualTo(DetailRefusal.Kind.NOT_FOUND);
    assertThat(caller.artifact(ID, new ArtifactPathInput.Values(List.of("spec.md"))).path()).as("control").isEqualTo("spec.md");
  }

  @Test
  void anUnknownWellFormedMissionIsNotFound() {
    PlainCaller caller = caller(populated());

    assertThat(kind(() -> caller.artifacts("00000000000000000000000009"))).isEqualTo(DetailRefusal.Kind.NOT_FOUND);
  }
}
