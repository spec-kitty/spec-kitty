package org.speckitty.missionstatus.domain.readmodel.derive;

import java.util.List;
import org.speckitty.missionstatus.domain.readmodel.detail.ArtifactKind;

/**
 * The ordered classifier of {@code schemas/ArtifactKind.yaml} and the extension table of {@code ArtifactContent.mediaType}. Both decide
 * from the path alone and never read the file. The first matching rule wins:
 * <ol>
 *   <li>{@code review_cycle}: {@code tasks/<directory>/review-cycle-<N>.md}, N a positive integer without a leading zero;
 *   <li>{@code work_package_prompt}: {@code tasks/WP<digits>-<name>.md} directly under {@code tasks/}, at least two digits;
 *   <li>the root files {@code spec.md}, {@code plan.md}, {@code tasks.md}, {@code data-model.md}, {@code quickstart.md},
 *       {@code analysis-report.md};
 *   <li>{@code research}: the root file {@code research.md} and everything under {@code research/};
 *   <li>{@code contract}: everything under {@code contracts/}; {@code checklist}: everything under {@code checklists/};
 *   <li>{@code other}.
 * </ol>
 */
public final class ArtifactKinds {

  private static final String CYCLE_PREFIX = "review-cycle-";
  private static final String MARKDOWN = ".md";

  private record Root(String name, ArtifactKind kind) {}

  private static final List<Root> ROOT_FILES =
      List.of(
          new Root("spec.md", ArtifactKind.SPEC),
          new Root("plan.md", ArtifactKind.PLAN),
          new Root("tasks.md", ArtifactKind.TASKS),
          new Root("data-model.md", ArtifactKind.DATA_MODEL),
          new Root("quickstart.md", ArtifactKind.QUICKSTART),
          new Root("analysis-report.md", ArtifactKind.ANALYSIS_REPORT));

  private ArtifactKinds() {}

  /** The class of the artifact at {@code path}, which must be a valid artifact path. */
  public static ArtifactKind kindOf(String path) {
    String[] segments = path.split("/", -1);
    if (segments.length == 3 && segments[0].equals("tasks") && isReviewCycleFile(segments[2])) {
      return ArtifactKind.REVIEW_CYCLE;
    }
    if (segments.length == 2 && segments[0].equals("tasks") && isWorkPackagePrompt(segments[1])) {
      return ArtifactKind.WORK_PACKAGE_PROMPT;
    }
    if (segments.length == 1) {
      for (Root root : ROOT_FILES) {
        if (root.name().equals(path)) {
          return root.kind();
        }
      }
      if (path.equals("research" + MARKDOWN)) {
        return ArtifactKind.RESEARCH;
      }
    }
    if (segments.length > 1) {
      switch (segments[0]) {
        case "research":
          return ArtifactKind.RESEARCH;
        case "contracts":
          return ArtifactKind.CONTRACT;
        case "checklists":
          return ArtifactKind.CHECKLIST;
        default:
          break;
      }
    }
    return ArtifactKind.OTHER;
  }

  /** {@code review-cycle-<N>.md}, N a positive integer written without a leading zero. */
  private static boolean isReviewCycleFile(String name) {
    if (!name.startsWith(CYCLE_PREFIX) || !name.endsWith(MARKDOWN)) {
      return false;
    }
    String number = name.substring(CYCLE_PREFIX.length(), name.length() - MARKDOWN.length());
    return !number.isEmpty() && number.charAt(0) != '0' && allAsciiDigits(number);
  }

  /** {@code WP<digits>-<name>.md} with at least two digits, then a dash and a non-empty rest. */
  private static boolean isWorkPackagePrompt(String name) {
    if (!name.startsWith("WP") || !name.endsWith(MARKDOWN)) {
      return false;
    }
    int digitsEnd = 2;
    while (digitsEnd < name.length() && name.charAt(digitsEnd) >= '0' && name.charAt(digitsEnd) <= '9') {
      digitsEnd++;
    }
    int rest = name.length() - MARKDOWN.length();
    return digitsEnd - 2 >= 2 && digitsEnd < rest && name.charAt(digitsEnd) == '-' && digitsEnd + 1 < rest;
  }

  private static boolean allAsciiDigits(String text) {
    for (int i = 0; i < text.length(); i++) {
      char c = text.charAt(i);
      if (c < '0' || c > '9') {
        return false;
      }
    }
    return true;
  }

  /** The media type from the extension of the last segment only (case-sensitive), never from the content. */
  public static String mediaTypeOf(String path) {
    String name = path.substring(path.lastIndexOf('/') + 1);
    int dot = name.lastIndexOf('.');
    String extension = dot < 0 ? "" : name.substring(dot + 1);
    return switch (extension) {
      case "md" -> "text/markdown";
      case "json" -> "application/json";
      case "yaml", "yml" -> "application/yaml";
      case "jsonl" -> "application/x-ndjson";
      case "csv" -> "text/csv";
      default -> "text/plain";
    };
  }
}
