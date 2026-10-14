package org.speckitty.missionstatus.adapter.in.http.flow;

import java.util.Map;
import org.speckitty.missionstatus.adapter.out.filesystem.JsonLanesDecoder;
import org.speckitty.missionstatus.adapter.out.filesystem.YamlFrontmatterDecoder;
import org.speckitty.missionstatus.application.query.AdmissionGate;
import org.speckitty.missionstatus.application.query.ArtifactQueryService;
import org.speckitty.missionstatus.application.query.MissionDetailQueryService;
import org.speckitty.missionstatus.application.query.WorkPackageDetailQueryService;
import org.speckitty.missionstatus.application.query.WorkPackageQueryService;
import org.speckitty.missionstatus.application.query.MissionReadModel;
import org.speckitty.missionstatus.application.query.index.WorkPackageIndex;
import org.speckitty.missionstatus.application.query.port.in.ArtifactQuery;
import org.speckitty.missionstatus.application.query.port.in.MissionDetailQuery;
import org.speckitty.missionstatus.application.query.port.in.WorkPackageDetailQuery;
import org.speckitty.missionstatus.application.query.port.in.WorkPackageQuery;
import org.speckitty.missionstatus.application.query.port.out.TextSource;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.redaction.TextScreen;
import org.speckitty.missionstatus.testsupport.DetailFixture;
import org.speckitty.missionstatus.testsupport.LeakPatternsFile;

/**
 * The four detail services built over one {@link DetailFixture} (WP18): one text source and one admission gate shared by all four, as the
 * production wiring shares them, with the fixture's recording seam in the path. The flow tests install them through
 * {@code HttpHarness#startWith}; the port-level admission test calls them directly. Test support only.
 */
public record DetailServices(MissionDetailQuery mission, WorkPackageQuery workPackage, WorkPackageDetailQuery workPackageDetail, ArtifactQuery artifact, AdmissionGate gate) {

  /** The services over the fixture's own text source and a new gate. */
  public static DetailServices over(DetailFixture fixture) {
    return over(fixture, fixture.textSource(), new AdmissionGate());
  }

  /** The services over another text source (for example one that blocks) and another gate. */
  public static DetailServices over(DetailFixture fixture, TextSource text, AdmissionGate gate) {
    return over(fixture.readModel(), text, fixture.built().handles().recorder(), gate);
  }

  /** The services over a read model and a text source, writing diagnostics to {@code diagnostics} (a perf scenario has no fixture bundle). */
  public static DetailServices over(MissionReadModel model, TextSource text, java.util.function.Consumer<Diagnostic> diagnostics, AdmissionGate gate) {
    YamlFrontmatterDecoder frontmatter = new YamlFrontmatterDecoder();
    WorkPackageIndex index = new WorkPackageIndex(text, frontmatter);
    return new DetailServices(
        new MissionDetailQueryService(model, index, text, diagnostics, LeakPatternsFile.load()),
        new WorkPackageQueryService(model, index, diagnostics, LeakPatternsFile.load(), gate),
        new WorkPackageDetailQueryService(model, index, text, frontmatter, new JsonLanesDecoder(), gate, diagnostics, LeakPatternsFile.load()),
        new ArtifactQueryService(model, text, gate, diagnostics, new TextScreen(LeakPatternsFile.load())),
        gate);
  }

  /** The four ports under their interfaces, as {@code HttpHarness#startWith} takes them. */
  public Map<Class<?>, Object> ports() {
    return Map.of(MissionDetailQuery.class, mission, WorkPackageQuery.class, workPackage, WorkPackageDetailQuery.class, workPackageDetail, ArtifactQuery.class, artifact);
  }
}
