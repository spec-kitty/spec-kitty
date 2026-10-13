package org.speckitty.missionstatus.testsupport;

import java.util.Map;
import org.speckitty.missionstatus.application.query.port.in.MissionStatusQuery;
import org.speckitty.missionstatus.application.query.port.in.exceptions.MissionStatusUnavailable;
import org.speckitty.missionstatus.application.query.port.in.dto.PageRequest;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.testsupport.ConformanceTree.TreeFixture;

/**
 * Runs one fixture's two reads through an inbound port and compares each with its committed golden: a served document by RAW bytes
 * ({@link CanonicalJson#assertBodyEqualsGolden}), a refusal by the code its Python exception class implies. The golden suite (over the
 * real filesystem adapter) and the AC-2a hook (over whichever source the selector holds) share it, so the two cannot disagree.
 */
public final class GoldenComparison {

  /** The page size the goldens record (the first page, the default size of the oracle run). */
  public static final int GOLDEN_PAGE_SIZE = 50;

  /**
   * A documented difference between the Java answer and the golden that is NOT a bug of the Java side, for one document of one fixture,
   * keyed {@code <class>/<fixture>#<file>}. Exactly one of {@code refusal} and the text pair is set: the service must refuse with
   * the code, or its body must equal the golden with {@code goldenText} replaced by {@code javaText}. Nothing else may differ.
   */
  public record Divergence(String reason, DiagnosticCode refusal, String goldenText, String javaText) {}

  /**
   * The divergences of the golden suite that are not tagged {@code knownDivergence} in the manifest (that tag is WP07's and covers
   * only the L4b fixture). Each one is a design decision of the spec or the decision record, asserted exactly rather than skipped.
   */
  public static final Map<String, Divergence> REPORTED_DIVERGENCES =
      Map.of(
          "projection/strict-field-refused#project.json",
          new Divergence("spec FR-004 row `projection`: the Java answer to a non-nullable strict field holding a token-shaped value is the 500 of rows L3a and L3b on both reads, where the oracle's project builder serves", DiagnosticCode.PROJECTION_REFUSED, null, null),
          "project-header/git-pointer-file#project.json",
          new Divergence("DD-101: HEAD is read through a gitdir pointer only when the gitdir lies outside the project root; the oracle follows an in-root one", null, "\"currentBranch\":\"main\"", "\"currentBranch\":null"));

  /** How much a verification covered. */
  public record Report(int documents, int bodiesEqual, int refusalsMatched, int divergencesHandled) {}

  private GoldenComparison() {}

  /** The {@code Project} body the service gives, as canonical bytes. */
  public static byte[] projectBody(MissionStatusQuery query) {
    return CanonicalJson.toBytes(GoldenDocuments.project(query.project()));
  }

  /** The first {@code MissionOverviewPage} body the service gives, as canonical bytes. */
  public static byte[] missionsBody(MissionStatusQuery query) {
    return CanonicalJson.toBytes(GoldenDocuments.page(query.missions(new PageRequest(GOLDEN_PAGE_SIZE, null))));
  }

  /** The Python exception class a refusal golden records, or null when the golden is a served document. */
  @SuppressWarnings("unchecked")
  public static String refusalException(byte[] golden) {
    Object tree = CanonicalJson.parse(golden);
    if (tree instanceof Map<?, ?> map && map.size() == 1 && map.get("refusal") instanceof Map<?, ?> refusal) {
      return (String) ((Map<String, Object>) refusal).get("exception");
    }
    return null;
  }

  /** The 1-based line a refusal golden records, or null. */
  public static Integer refusalLine(byte[] golden) {
    Object tree = CanonicalJson.parse(golden);
    if (tree instanceof Map<?, ?> map && map.get("refusal") instanceof Map<?, ?> refusal && refusal.get("line") instanceof CanonicalJson.Num number) {
      return Integer.valueOf(number.text());
    }
    return null;
  }

  /** The diagnostic code the Java side must refuse with where Python raised {@code exception}, for one document of one fixture. */
  static DiagnosticCode expectedCode(TreeFixture fixture, String exception) {
    if (fixture.key().equals("torn-final-line/unparseable-final-line")) {
      return DiagnosticCode.LEDGER_TORN_TAIL; // L4: the unparseable unterminated tail has its own row
    }
    return switch (exception) {
      case "StoreError", "DiaryError", "JSONDecodeError", "UnicodeDecodeError" -> DiagnosticCode.LEDGER_UNPARSEABLE;
      case "ValueError", "MissionMetaReadError" -> DiagnosticCode.META_UNPARSEABLE;
      case "ProjectionError" -> DiagnosticCode.PROJECTION_REFUSED;
      default -> throw new AssertionError(fixture.key() + ": no code is mapped to the Python exception class " + exception);
    };
  }

  /** Verifies both documents of a fixture. A difference is an {@link AssertionError} that names the fixture, the document and the member. */
  public static Report verify(TreeFixture fixture, MissionStatusQuery query) {
    int equal = 0;
    int refusals = 0;
    int divergences = 0;
    for (String file : new String[] {ConformanceTree.PROJECT_GOLDEN, ConformanceTree.MISSIONS_GOLDEN}) {
      byte[] golden = ConformanceTree.golden(fixture, file);
      if (golden == null) {
        throw new AssertionError(fixture.key() + ": the golden " + file + " is missing");
      }
      String exception = refusalException(golden);
      Divergence divergence = REPORTED_DIVERGENCES.get(fixture.key() + "#" + file);
      try {
        byte[] body = file.equals(ConformanceTree.PROJECT_GOLDEN) ? projectBody(query) : missionsBody(query);
        if (exception != null) {
          throw new AssertionError(fixture.key() + " " + file + ": Python raised " + exception + " but the service served a document");
        }
        byte[] expected = golden;
        if (divergence != null) {
          if (divergence.refusal() != null) {
            throw new AssertionError(fixture.key() + " " + file + ": the service served a document where " + divergence.reason() + " requires the refusal " + divergence.refusal().wire());
          }
          String goldenText = new String(golden, java.nio.charset.StandardCharsets.UTF_8);
          if (!goldenText.contains(divergence.goldenText())) {
            throw new AssertionError(fixture.key() + " " + file + ": the golden no longer holds " + divergence.goldenText());
          }
          expected = goldenText.replace(divergence.goldenText(), divergence.javaText()).getBytes(java.nio.charset.StandardCharsets.UTF_8);
        }
        try {
          CanonicalJson.assertBodyEqualsGolden(body, expected);
        } catch (AssertionError mismatch) {
          throw new AssertionError(fixture.key() + " " + file + ": " + mismatch.getMessage(), mismatch);
        }
        if (divergence != null) {
          divergences++;
        } else {
          equal++;
        }
      } catch (MissionStatusUnavailable refusal) {
        if (divergence != null && divergence.refusal() == refusal.code() && exception == null) {
          divergences++;
          continue;
        }
        if (exception == null) {
          throw new AssertionError(fixture.key() + " " + file + ": the service refused with " + refusal.code().wire() + " where the golden holds a document", refusal);
        }
        DiagnosticCode expected = expectedCode(fixture, exception);
        if (refusal.code() != expected) {
          throw new AssertionError(fixture.key() + " " + file + ": Python raised " + exception + ", so the service must refuse with " + expected.wire() + ", not " + refusal.code().wire(), refusal);
        }
        refusals++;
      }
    }
    return new Report(equal + refusals + divergences, equal, refusals, divergences);
  }
}
