package org.speckitty.missionstatus.application.query.index;

import java.util.Objects;
import org.speckitty.missionstatus.domain.model.WpId;
import org.speckitty.missionstatus.domain.model.WpMetadata;

/**
 * One Work Package of the index: its identifier, the validated frontmatter fields and the name of the file that holds them. It never holds
 * the body of the file (D-76): a record that kept it would hold every prompt of a Mission at once. The body of one requested Work Package
 * is carried beside the index by {@link WorkPackageIndex.Result}, not inside an entry.
 *
 * <p>{@code fileName} is the name of the authored file, which may differ from {@code id} (AC-6.3: the frontmatter selects the Work
 * Package, the file name selects the prompt).
 */
public record IndexedWorkPackage(WpId id, String fileName, WpMetadata metadata) {

  public IndexedWorkPackage {
    Objects.requireNonNull(id, "id");
    Objects.requireNonNull(fileName, "fileName");
    Objects.requireNonNull(metadata, "metadata");
  }
}
