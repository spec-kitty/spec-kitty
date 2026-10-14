package org.speckitty.missionstatus.testsupport;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.application.query.port.in.ArtifactQuery;
import org.speckitty.missionstatus.application.query.port.in.MissionDetailQuery;
import org.speckitty.missionstatus.application.query.port.in.WorkPackageDetailQuery;
import org.speckitty.missionstatus.application.query.port.in.WorkPackageQuery;
import org.speckitty.missionstatus.application.query.port.in.dto.ArtifactPathInput;
import org.speckitty.missionstatus.application.query.port.in.exceptions.DetailRefusal;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.domain.model.WpId;

/**
 * AC-13.3: the five operations can be called with typed arguments only and refuse with a typed exception, never a status. The ports are
 * stubs declared here; no service of a later work package is named.
 */
class PlainCallerTest {

  private static final String MISSION = "01M4S6D5ABCDEFGHJKMNPQRSTV";

  /** Records every typed call and applies the port rule for an invalid path. */
  private static final class Stubs implements MissionDetailQuery, WorkPackageQuery, WorkPackageDetailQuery, ArtifactQuery {
    final List<String> calls = new ArrayList<>();
    DetailRefusal toThrow;

    private void maybeThrow() {
      if (toThrow != null) {
        throw toThrow;
      }
    }

    @Override
    public org.speckitty.missionstatus.domain.readmodel.detail.MissionDetail mission(MissionId missionId) {
      calls.add("mission " + missionId.value());
      maybeThrow();
      return null;
    }

    @Override
    public org.speckitty.missionstatus.domain.readmodel.detail.WorkPackageView workPackage(MissionId missionId, WpId wpId, boolean includePrompt) {
      calls.add("workPackage " + missionId.value() + " " + wpId.value() + " " + includePrompt);
      maybeThrow();
      return null;
    }

    @Override
    public org.speckitty.missionstatus.domain.readmodel.detail.WorkPackageDetail workPackageDetail(MissionId missionId, WpId wpId) {
      calls.add("workPackageDetail " + missionId.value() + " " + wpId.value());
      maybeThrow();
      return null;
    }

    @Override
    public org.speckitty.missionstatus.domain.readmodel.detail.ArtifactListing list(MissionId missionId) {
      calls.add("list " + missionId.value());
      maybeThrow();
      return null;
    }

    @Override
    public org.speckitty.missionstatus.domain.readmodel.detail.ArtifactContent content(MissionId missionId, ArtifactPathInput path) {
      calls.add("content " + missionId.value() + " " + path);
      maybeThrow();
      if (!(path instanceof ArtifactPathInput.Values values) || values.values().size() != 1) {
        throw DetailRefusal.invalidArtifactPath();
      }
      return null;
    }
  }

  private final Stubs stubs = new Stubs();
  private final PlainCaller caller = new PlainCaller(stubs, stubs, stubs, stubs);

  @Test
  void validIdentifiersReachTheStubsAsTypedArguments() {
    caller.mission(MISSION);
    caller.workPackage(MISSION, "WP12", true);
    caller.workPackageDetail(MISSION, "WP03");
    caller.artifacts(MISSION);
    caller.artifact(MISSION, new ArtifactPathInput.Values(List.of("spec.md")));

    assertThat(stubs.calls)
        .containsExactly(
            "mission " + MISSION,
            "workPackage " + MISSION + " WP12 true",
            "workPackageDetail " + MISSION + " WP03",
            "list " + MISSION,
            "content " + MISSION + " Values[values=[spec.md]]");
  }

  @Test
  void aMalformedIdentifierNeverReachesAStubAndIsNotFound() {
    for (String badMission : new String[] {null, "", "mid8abcd", "my-slug", "01m4s6d5abcdefghjkmnpqrstv"}) {
      assertThatThrownBy(() -> caller.mission(badMission)).isInstanceOf(DetailRefusal.class).extracting(e -> ((DetailRefusal) e).kind()).isEqualTo(DetailRefusal.Kind.NOT_FOUND);
    }
    for (String badWp : new String[] {null, "", "wp12", "WP1", "WP12 "}) {
      assertThatThrownBy(() -> caller.workPackage(MISSION, badWp, false)).isInstanceOf(DetailRefusal.class).extracting(e -> ((DetailRefusal) e).kind()).isEqualTo(DetailRefusal.Kind.NOT_FOUND);
      assertThatThrownBy(() -> caller.workPackageDetail(MISSION, badWp)).isInstanceOf(DetailRefusal.class).extracting(e -> ((DetailRefusal) e).kind()).isEqualTo(DetailRefusal.Kind.NOT_FOUND);
    }
    assertThatThrownBy(() -> caller.artifacts("nope")).isInstanceOf(DetailRefusal.class);
    assertThatThrownBy(() -> caller.artifact("nope", new ArtifactPathInput.Values(List.of("spec.md")))).isInstanceOf(DetailRefusal.class);

    assertThat(stubs.calls).as("no malformed identifier reached a port").isEmpty();
  }

  @Test
  void aRefusalThrownByAStubSurfacesAsTheTypedExceptionNotAStatus() {
    stubs.toThrow = DetailRefusal.sourceUnreadable();

    assertThatThrownBy(() -> caller.workPackageDetail(MISSION, "WP03")).isSameAs(stubs.toThrow);
    assertThatThrownBy(() -> caller.mission(MISSION)).isSameAs(stubs.toThrow);
  }

  @Test
  void aMissingTwoValuedOrUndecodablePathIsTheTypedInvalidArtifactPathRefusal() {
    for (ArtifactPathInput input :
        List.<ArtifactPathInput>of(new ArtifactPathInput.Values(List.of()), new ArtifactPathInput.Values(List.of("a.md", "b.md")), new ArtifactPathInput.Undecodable())) {
      assertThatThrownBy(() -> caller.artifact(MISSION, input))
          .isInstanceOf(DetailRefusal.class)
          .extracting(e -> ((DetailRefusal) e).kind())
          .isEqualTo(DetailRefusal.Kind.INVALID_ARTIFACT_PATH);
    }
  }
}
