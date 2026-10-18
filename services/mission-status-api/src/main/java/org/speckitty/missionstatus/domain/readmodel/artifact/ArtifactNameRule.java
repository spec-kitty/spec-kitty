package org.speckitty.missionstatus.domain.readmodel.artifact;

import java.util.Set;

/**
 * The name rule of an artifact, read from the path alone and before any file system call: the Java form of {@code is_artifact_name}
 * in the reference reader ({@code tests/contract/_mission_status_artifacts.py}). It denies by default. No segment starts with a dot
 * ({@code .env}, {@code .npmrc}, {@code .git/}), the final name has an extension of {@link #EXTENSIONS}, matched with its case (so
 * {@code id_rsa}, {@code *.pem}, {@code *.key} and {@code *.p12} are not artifacts), and a data file's case-folded name less its extension (Markdown is
 * prose and is not judged by its name) is not a credential file name ({@code credentials.json}, {@code Secrets.YAML}, {@code client_secret_1.json}).
 */
public final class ArtifactNameRule {

  /** The extensions of an artifact: the media-type table plus {@code txt}. */
  public static final Set<String> EXTENSIONS = Set.of("md", "json", "jsonl", "yaml", "yml", "csv", "txt");

  private static final Set<String> CREDENTIAL_STEMS = Set.of("credential", "credentials", "secret", "secrets", "service-account", "service_account");
  private static final String CREDENTIAL_PREFIX = "client_secret";

  private ArtifactNameRule() {}

  /** Whether {@code path} (relative to the Mission directory, already a valid artifact path) has the name of an artifact. */
  public static boolean isArtifactName(String path) {
    for (String segment : path.split("/", -1)) {
      if (segment.startsWith(".")) {
        return false;
      }
    }
    String name = path.substring(path.lastIndexOf('/') + 1);
    int dot = name.lastIndexOf('.');
    String extension = dot < 0 ? "" : name.substring(dot + 1);
    if (!EXTENSIONS.contains(extension)) {
      return false;
    }
    if (extension.equals("md")) {
      return true;
    }
    String folded = AsciiCaseFold.fold(name.substring(0, dot));
    return !CREDENTIAL_STEMS.contains(folded) && !folded.startsWith(CREDENTIAL_PREFIX);
  }
}
