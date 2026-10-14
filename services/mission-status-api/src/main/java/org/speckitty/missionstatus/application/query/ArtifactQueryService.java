package org.speckitty.missionstatus.application.query;

import java.util.Objects;
import java.util.function.Consumer;
import org.speckitty.missionstatus.application.query.artifact.ArtifactReader;
import org.speckitty.missionstatus.application.query.artifact.ArtifactWalk;
import org.speckitty.missionstatus.application.query.port.in.ArtifactQuery;
import org.speckitty.missionstatus.application.query.port.in.dto.ArtifactPathInput;
import org.speckitty.missionstatus.application.query.port.in.exceptions.DetailRefusal;
import org.speckitty.missionstatus.application.query.port.out.TextSource;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.domain.readmodel.derive.ArtifactPaths;
import org.speckitty.missionstatus.domain.readmodel.detail.ArtifactContent;
import org.speckitty.missionstatus.domain.readmodel.detail.ArtifactListing;
import org.speckitty.missionstatus.domain.redaction.TextScreen;

/**
 * The application service of {@code listArtifacts} and {@code getArtifactContent} (FR-004, FR-005). Both run their whole body inside the
 * admission gate (FR-022). Neither touches the ledger, the head or any coordination class: the sequence is the probe-free lookup, its
 * duplicate continuation, then the work, so the {@code meta.json} of the matched Mission is read once and every other one once.
 *
 * <p>The lookup rows are the route's own: an unknown id is {@code not_found}; a Mission directory refused as a link, with no match, is
 * {@code not_found} and writes {@code path_refused}; an unusable {@code meta.json} or a directory that cannot be read, with no match, is
 * the route's 500 ({@code artifact_listing_unreadable} for the listing, {@code artifact_unreadable} for the content) with the row's
 * diagnostic; a duplicate id serves the first in byte order and writes {@code mission_id_duplicate}; a faulted sibling is ignored.
 *
 * <p>The content read judges the {@code path} before it looks the Mission up (FR-005: 400 before 404). The typed {@code missionId} is
 * the adapter's: an ill-formed one never reaches this class (ruling OO-2).
 */
public final class ArtifactQueryService implements ArtifactQuery {

  private final MissionReadModel model;
  private final AdmissionGate gate;
  private final Consumer<Diagnostic> diagnostics;
  private final ArtifactReader reader;
  private final ArtifactWalk walk;

  public ArtifactQueryService(MissionReadModel model, TextSource source, AdmissionGate gate, Consumer<Diagnostic> diagnostics, TextScreen screen) {
    this.model = Objects.requireNonNull(model, "model");
    this.gate = Objects.requireNonNull(gate, "gate");
    this.diagnostics = Objects.requireNonNull(diagnostics, "diagnostics");
    Objects.requireNonNull(source, "source");
    Objects.requireNonNull(screen, "screen");
    this.reader = new ArtifactReader(source, screen, diagnostics);
    this.walk = new ArtifactWalk(source, reader, diagnostics);
  }

  @Override
  public ArtifactListing list(MissionId missionId) {
    return gate.run(
        () -> {
          MissionLookup.Found found = resolve(missionId, DetailRefusal.Kind.ARTIFACT_LISTING_UNREADABLE);
          ArtifactWalk.Result result = walk.walk(found.ref(), found.mid8());
          return new ArtifactListing(missionId, result.entries(), result.truncated());
        });
  }

  @Override
  public ArtifactContent content(MissionId missionId, ArtifactPathInput path) {
    return gate.run(
        () -> {
          String artifactPath = validPath(path);
          MissionLookup.Found found = resolve(missionId, DetailRefusal.Kind.ARTIFACT_UNREADABLE);
          return reader.read(found.ref(), found.mid8(), artifactPath);
        });
  }

  /** Step 1 of FR-005: exactly one decoded value, and it is an artifact path. */
  private static String validPath(ArtifactPathInput input) {
    if (input instanceof ArtifactPathInput.Values values && values.values().size() == 1 && ArtifactPaths.isValid(values.values().getFirst())) {
      return values.values().getFirst();
    }
    throw DetailRefusal.invalidArtifactPath();
  }

  /** The lookup rows C2 to C7. {@code unreadable} is the route's 500 for rows C4 and C5. */
  private MissionLookup.Found resolve(MissionId id, DetailRefusal.Kind unreadable) {
    MissionLookup.Scan scan;
    try {
      scan = model.find(id);
    } catch (SourceFault fault) {
      throw refused(DiagnosticCode.MISSION_DIR_UNREADABLE, unreadable);
    }
    MissionLookup.Found found = scan.found();
    if (found != null) {
      if (model.hasDuplicate(scan)) {
        note(DiagnosticCode.MISSION_ID_DUPLICATE, found.mid8());
      }
      return found;
    }
    SourceFault.Kind fault = scan.firstFault();
    if (fault == SourceFault.Kind.PATH_REFUSED) {
      note(DiagnosticCode.PATH_REFUSED, Diagnostic.NONE);
    } else if (fault == SourceFault.Kind.META_UNPARSEABLE) {
      throw refused(DiagnosticCode.META_UNPARSEABLE, unreadable);
    } else if (fault != null) {
      throw refused(DiagnosticCode.MISSION_DIR_UNREADABLE, unreadable);
    }
    throw DetailRefusal.notFound();
  }

  private DetailRefusal refused(DiagnosticCode code, DetailRefusal.Kind kind) {
    note(code, Diagnostic.NONE);
    return new DetailRefusal(kind);
  }

  private void note(DiagnosticCode code, String mid8) {
    diagnostics.accept(new Diagnostic(code, mid8, null));
  }
}
