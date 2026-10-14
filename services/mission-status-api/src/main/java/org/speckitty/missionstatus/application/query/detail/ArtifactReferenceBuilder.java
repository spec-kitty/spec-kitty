package org.speckitty.missionstatus.application.query.detail;

import java.util.ArrayList;
import java.util.List;
import java.util.Objects;
import java.util.regex.Pattern;
import org.speckitty.missionstatus.application.query.artifact.Eligibility;
import org.speckitty.missionstatus.application.query.port.out.TextSource;
import org.speckitty.missionstatus.application.query.port.out.dto.DirListing;
import org.speckitty.missionstatus.application.query.port.out.dto.EntryStat;
import org.speckitty.missionstatus.application.query.port.out.dto.FileRef;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.application.query.port.out.dto.ReadScope;
import org.speckitty.missionstatus.application.query.port.out.dto.RelativePath;
import org.speckitty.missionstatus.domain.model.CodePoints;
import org.speckitty.missionstatus.domain.model.WpId;
import org.speckitty.missionstatus.domain.readmodel.detail.ArtifactKind;
import org.speckitty.missionstatus.domain.readmodel.detail.ArtifactReference;
import org.speckitty.missionstatus.domain.readmodel.detail.ArtifactReferences;

/**
 * The pointers of a Work Package detail to its prompt file and to the Mission's {@code spec.md} (the oracle's {@code artifact_references}). One
 * listing of {@code tasks/} and one {@code lstat} per candidate path: no file is opened (AC-3.6). The prompt file of a Work Package is
 * <em>name-keyed</em>: the first regular, non-link {@code tasks/WP<digits>-*.md} in byte order whose name starts with {@code <wpId>-}, whichever
 * file the frontmatter of the index selected. Its kind is {@code work_package_prompt} and the kind of {@code spec.md} is {@code spec}, as
 * the oracle writes them: they are not classified from the name (a name the artifact classifier calls {@code other}, such as {@code WP01-.md}, is still
 * the prompt here). An {@code lstat} that fails other than "absent" is a fault of the port (row M9).
 */
public final class ArtifactReferenceBuilder {

  /** The names read from {@code tasks/}: a longer directory is refused by the index already; this is the same bound. */
  private static final int LISTING_LIMIT = 100_000;

  private static final String TASKS = "tasks";
  private static final String SPEC = "spec.md";
  private static final Pattern PROMPT_NAME = Pattern.compile("WP[0-9]{2,}-[^/]*\\.md", Pattern.DOTALL);
  private static final EntryStat TASKS_DIRECTORY = new EntryStat.Present(EntryStat.EntryKind.DIRECTORY, 0, 0);

  /** The references, and the name of the prompt file (null when the Work Package has none): the review cycles are keyed on its stem. */
  public record Built(String promptFileName, ArtifactReferences references) {
    public Built {
      Objects.requireNonNull(references, "references");
    }
  }

  private final TextSource text;

  public ArtifactReferenceBuilder(TextSource text) {
    this.text = Objects.requireNonNull(text, "text");
  }

  /**
   * @throws org.speckitty.missionstatus.application.query.port.out.exceptions.TextFault when the port cannot list or stat
   */
  public Built build(MissionRef mission, WpId wpId) {
    String prompt = promptFileName(mission, wpId.value());
    ArtifactReference promptReference = prompt == null ? null : new ArtifactReference(TASKS + "/" + prompt, ArtifactKind.WORK_PACKAGE_PROMPT);
    ArtifactReference specReference = eligibleLeaf(mission, SPEC, List.of()) ? new ArtifactReference(SPEC, ArtifactKind.SPEC) : null;
    return new Built(prompt, new ArtifactReferences(promptReference, specReference));
  }

  private String promptFileName(MissionRef mission, String wpId) {
    DirListing listing = text.list(new FileRef.MissionFile(mission, RelativePath.of(TASKS)), LISTING_LIMIT, ReadScope.AUTHORED);
    if (!(listing instanceof DirListing.Names names)) {
      return null;
    }
    List<String> candidates = new ArrayList<>(names.names().stream().filter(name -> name.startsWith(wpId + "-") && PROMPT_NAME.matcher(name).matches()).toList());
    candidates.sort(CodePoints::compare);
    for (String name : candidates) {
      if (eligibleLeaf(mission, TASKS + "/" + name, List.of(TASKS_DIRECTORY))) {
        return name;
      }
    }
    return null;
  }

  /** Whether the entry at {@code path} is an eligible artifact: a path the rule accepts, whose leaf is a regular file (the ancestors are known directories). */
  private boolean eligibleLeaf(MissionRef mission, String path, List<EntryStat> ancestors) {
    if (!Eligibility.isEligiblePath(path)) {
      return false;
    }
    EntryStat leaf = text.stat(new FileRef.MissionFile(mission, RelativePath.of(path)), ReadScope.AUTHORED);
    return Eligibility.isEligible(path, leaf, ancestors);
  }
}
