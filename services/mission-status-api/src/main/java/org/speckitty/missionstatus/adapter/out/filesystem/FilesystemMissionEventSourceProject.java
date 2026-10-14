package org.speckitty.missionstatus.adapter.out.filesystem;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.math.BigDecimal;
import java.math.BigInteger;
import java.nio.ByteBuffer;
import java.nio.channels.SeekableByteChannel;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.nio.file.InvalidPathException;
import java.nio.file.Path;
import java.nio.file.attribute.BasicFileAttributes;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import org.speckitty.missionstatus.application.query.port.out.dto.ProjectInputs;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault.Kind;
import org.speckitty.missionstatus.domain.model.PyText;
import org.yaml.snakeyaml.LoaderOptions;
import org.yaml.snakeyaml.Yaml;
import org.yaml.snakeyaml.constructor.SafeConstructor;

/**
 * The project-header inputs: {@code project.slug} of {@code .kittify/config.yaml}, {@code spec_kitty.version} and
 * {@code spec_kitty.schema_version} of {@code .kittify/metadata.yaml}, and the branch {@code HEAD} names. It reads those keys and
 * nothing else (in particular no drain key), starts no process, and mirrors the reference builder
 * {@code tests/contract/_mission_status_project.py}: {@code read_project_name}, {@code project_version} (through
 * {@code ProjectMetadata.load}), {@code schema_version_of} (through {@code get_project_schema_version}), {@code head_file} and
 * {@code read_head}. The branch-name pattern, the length bound, the version pattern and the host-path test are the domain's; this class
 * hands over the raw name.
 *
 * <p>Differences kept on purpose: a configuration that is missing, unreadable or without a usable slug is a {@code DIR_UNREADABLE}
 * fault (the oracle raises a projection error); a {@code schema_version} beyond 31 bits reads as absent (the service carries the field as a 32-bit integer by decision, FR-004 of 2026-10-12); only the structural parts of
 * {@code ProjectMetadata.load} that make it fail are reproduced (a {@code spec_kitty}, {@code environment} or {@code migrations} that
 * is not a mapping, or a migration entry that is not a mapping); a {@code .git} that is a symbolic link is not followed.
 */
final class FilesystemMissionEventSourceProject {

  private static final int YAML_MAX_BYTES = SafeFiles.SMALL_FILE_MAX;
  private static final int HEAD_MAX_BYTES = 64 * 1024;
  private static final String GITDIR_PREFIX = "gitdir:";
  private static final String REF_PREFIX = "ref:";
  private static final String HEADS_PREFIX = "refs/heads/";
  private static final char BYTE_ORDER_MARK = (char) 0xFEFF;
  private static final String UNKNOWN_VERSION = "unknown";

  private final Path root;
  private final SafeFiles files;
  private final AllowlistAccess access;

  FilesystemMissionEventSourceProject(SafeFiles files, AllowlistAccess access) {
    this.files = files;
    this.access = access;
    this.root = files.root();
  }

  ProjectInputs read() {
    String name = slug();
    Map<?, ?> metadata = metadata();
    return new ProjectInputs(name, metadata == null ? null : version(metadata), metadata == null ? null : schemaVersion(metadata), branch());
  }

  // ---- .kittify/config.yaml ---------------------------------------------------------------------------------------------------

  private String slug() {
    Object document = tryReadKittify(root.resolve(".kittify").resolve("config.yaml")).flatMap(FilesystemMissionEventSourceProject::yaml).orElse(null);
    if (document instanceof Map<?, ?> config && config.get("project") instanceof Map<?, ?> project && project.get("slug") instanceof String slug && !slug.isEmpty()) {
      return slug;
    }
    throw new SourceFault(Kind.DIR_UNREADABLE);
  }

  // ---- .kittify/metadata.yaml -------------------------------------------------------------------------------------------------

  /** The parsed document when it is a mapping; null when the file is absent, unreadable, not UTF-8, not YAML or not a mapping. */
  private Map<?, ?> metadata() {
    Object document = tryReadKittify(root.resolve(".kittify").resolve("metadata.yaml")).flatMap(FilesystemMissionEventSourceProject::yaml).orElse(null);
    return document instanceof Map<?, ?> map ? map : null;
  }

  /** {@code ProjectMetadata.load}: null when it fails; the version when it is a string other than the product's {@code unknown}. */
  private static String version(Map<?, ?> data) {
    if (data.isEmpty() || !loadSucceeds(data)) {
      return null;
    }
    Object recorded = ((Map<?, ?>) orEmpty(data, "spec_kitty")).get("version");
    return recorded instanceof String text && !text.equals(UNKNOWN_VERSION) ? text : null;
  }

  /** The structural parts of {@code ProjectMetadata.load} that raise: every one of them is read as "no version". */
  private static boolean loadSucceeds(Map<?, ?> data) {
    if (!(orEmpty(data, "spec_kitty") instanceof Map<?, ?> section) || !(orEmpty(data, "environment") instanceof Map<?, ?>)) {
      return false;
    }
    // parse_iso(x) if x else now: a truthy non-string raises TypeError, which project_version reads as "no version"
    if (truthy(section.get("initialized_at")) && !(section.get("initialized_at") instanceof String)
        || truthy(section.get("last_upgraded_at")) && !(section.get("last_upgraded_at") instanceof String)) {
      return false;
    }
    if (!(orEmpty(data, "migrations") instanceof Map<?, ?> migrations)) {
      return false;
    }
    Object applied = migrations.containsKey("applied") ? migrations.get("applied") : List.of();
    if (applied instanceof Map<?, ?> keys) {
      return keys.isEmpty();
    }
    if (applied instanceof String text) {
      return text.isEmpty();
    }
    if (!(applied instanceof List<?> entries)) {
      return false;
    }
    return entries.stream().allMatch(FilesystemMissionEventSourceProject::migrationEntryLoads);
  }

  /**
   * One {@code migrations.applied} entry: it must be a mapping, and when it holds both {@code id} and {@code applied_at} the latter must
   * be a string (the oracle's {@code parse_iso} raises TypeError for any other value, a null included, and only ValueError and KeyError
   * skip the entry).
   */
  private static boolean migrationEntryLoads(Object entry) {
    if (!(entry instanceof Map<?, ?> record)) {
      return false;
    }
    return !(record.containsKey("id") && record.containsKey("applied_at")) || record.get("applied_at") instanceof String;
  }

  /** Python truthiness of a parsed YAML value. */
  private static boolean truthy(Object value) {
    if (value == null) {
      return false;
    }
    if (value instanceof Boolean flag) {
      return flag;
    }
    if (value instanceof Number number) {
      return number.doubleValue() != 0.0 || (number instanceof BigInteger big && big.signum() != 0);
    }
    if (value instanceof CharSequence text) {
      return text.length() > 0;
    }
    if (value instanceof Map<?, ?> map) {
      return !map.isEmpty();
    }
    return !(value instanceof java.util.Collection<?> collection) || !collection.isEmpty();
  }

  /** {@code data.get(key, {})}: the value as stored (null stays null), or an empty mapping when the key is absent. */
  private static Object orEmpty(Map<?, ?> data, String key) {
    return data.containsKey(key) ? data.get(key) : Map.of();
  }

  /** {@code get_project_schema_version}: {@code int(raw)} of {@code spec_kitty.schema_version}, null when it is absent or not coercible. */
  private static Integer schemaVersion(Map<?, ?> data) {
    if (!(orEmpty(data, "spec_kitty") instanceof Map<?, ?> section)) {
      return null;
    }
    Object raw = section.get("schema_version");
    if (raw instanceof Boolean flag) {
      return flag ? 1 : 0;
    }
    if (raw instanceof Integer number) {
      return number;
    }
    if (raw instanceof Long || raw instanceof BigInteger) {
      return toInt(new BigInteger(raw.toString()));
    }
    if (raw instanceof Double real) {
      return real.isNaN() || real.isInfinite() ? null : toInt(BigDecimal.valueOf(real).toBigInteger());
    }
    return raw instanceof String text ? pyInt(text) : null;
  }

  private static Integer toInt(BigInteger value) {
    return value.bitLength() > 31 ? null : value.intValue();
  }

  /** Python's {@code int(text)} for a string: surrounding whitespace, an optional sign, digits with single underscores between them. */
  static Integer pyInt(String text) {
    String stripped = PyText.strip(text);
    int index = 0;
    boolean negative = false;
    if (!stripped.isEmpty() && (stripped.charAt(0) == '+' || stripped.charAt(0) == '-')) {
      negative = stripped.charAt(0) == '-';
      index = 1;
    }
    StringBuilder digits = new StringBuilder();
    boolean previousUnderscore = true;
    for (; index < stripped.length(); ) {
      int codePoint = stripped.codePointAt(index);
      index += Character.charCount(codePoint);
      if (codePoint == '_') {
        if (previousUnderscore) {
          return null;
        }
        previousUnderscore = true;
      } else if (Character.isDigit(codePoint)) {
        digits.append(Character.digit(codePoint, 10));
        previousUnderscore = false;
      } else {
        return null;
      }
    }
    if (digits.isEmpty() || previousUnderscore) {
      return null;
    }
    BigInteger value = new BigInteger(digits.toString());
    return toInt(negative ? value.negate() : value);
  }

  // ---- HEAD -------------------------------------------------------------------------------------------------------------------------

  /** {@code read_head}: the branch name HEAD points at, null for a detached, missing, unreadable or unparseable HEAD. */
  private String branch() {
    Optional<Path> head = headFile();
    if (head.isEmpty()) {
      return null;
    }
    Optional<String> text = tryRead(head.get(), HEAD_MAX_BYTES).flatMap(FilesystemMissionEventSourceProject::utf8).map(PyText::strip);
    if (text.isEmpty() || !text.get().startsWith(REF_PREFIX)) {
      return null;
    }
    String target = PyText.strip(text.get().substring(REF_PREFIX.length()));
    return target.startsWith(HEADS_PREFIX) ? target.substring(HEADS_PREFIX.length()) : null;
  }

  /**
   * {@code head_file}: {@code .git/HEAD} when {@code .git} is a directory; when it is a pointer file, the single {@code HEAD} of the
   * directory its {@code gitdir:} line names. A named directory inside the project root is refused (an in-root {@code HEAD} other than
   * {@code .git/HEAD} is not on the allowlist), and so is a {@code .git} that is a symbolic link.
   */
  private Optional<Path> headFile() {
    Path dotGit = root.resolve(".git");
    Optional<BasicFileAttributes> attributes;
    try {
      attributes = files.statNoFollow(dotGit);
    } catch (SourceFault unreadable) {
      return Optional.empty();
    }
    if (attributes.isEmpty() || SafeFiles.isLinkLike(attributes.get())) {
      return Optional.empty();
    }
    if (attributes.get().isDirectory()) {
      return Optional.of(dotGit.resolve("HEAD"));
    }
    if (!attributes.get().isRegularFile()) {
      return Optional.empty();
    }
    Optional<String> pointer = tryRead(dotGit, HEAD_MAX_BYTES).flatMap(FilesystemMissionEventSourceProject::utf8).map(PyText::strip);
    if (pointer.isEmpty() || !pointer.get().startsWith(GITDIR_PREFIX)) {
      return Optional.empty();
    }
    String named = PyText.strip(pointer.get().substring(GITDIR_PREFIX.length()));
    Path base = root.toAbsolutePath().normalize();
    Path gitDir;
    try {
      gitDir = base.resolve(named).normalize();
    } catch (InvalidPathException notAPath) {
      return Optional.empty();
    }
    if (gitDir.startsWith(base)) {
      return Optional.empty();
    }
    Path head = gitDir.resolve("HEAD");
    return containedByRealPath(head) ? Optional.empty() : Optional.of(head);
  }

  /**
   * Whether the real path of {@code head} lies inside the real project root: a pointer that reaches an in-root directory through a
   * symbolic link is refused as an in-root pointer is. A {@code HEAD} that cannot be resolved is not contained (there is nothing to
   * read, and the read finds that out).
   */
  private boolean containedByRealPath(Path head) {
    try {
      return access.realPath(head).startsWith(access.realPath(root));
    } catch (IOException unresolved) {
      return false;
    }
  }

  // ---- reading ----------------------------------------------------------------------------------------------------------------------

  /**
   * A file of {@code .kittify}: read only when its real path is inside the real project root, so a {@code .kittify} that is a link to a
   * directory elsewhere is unusable project configuration (the {@code /project} 500 {@code mission_dir_unreadable}), not a second root.
   * A deliberate divergence from the oracle, which follows the link (pre-merge fold J4, ruling 3 of 2026-10-13).
   */
  private Optional<byte[]> tryReadKittify(Path file) {
    try {
      if (!files.isContainedPath(file)) {
        return Optional.empty();
      }
    } catch (SourceFault degrades) {
      return Optional.empty();
    }
    return tryRead(file, YAML_MAX_BYTES);
  }

  /** The bytes of a regular file of at most {@code max} bytes; empty when it is absent, a link, unreadable or larger. */
  private Optional<byte[]> tryRead(Path file, int max) {
    try {
      return files.readRegular(file, max, Kind.PATH_REFUSED, Kind.DIR_UNREADABLE);
    } catch (SourceFault degrades) {
      return Optional.empty();
    }
  }

  /** Strict UTF-8, as {@code read_text(encoding="utf-8")}: a byte order mark stays in the text. */
  private static Optional<String> utf8(byte[] bytes) {
    try {
      return Optional.of(StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT).onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(bytes)).toString());
    } catch (CharacterCodingException notUtf8) {
      return Optional.empty();
    }
  }

  /** The metadata and configuration are read as {@code utf-8-sig}: a leading byte order mark is skipped, for YAML reads only. */
  private static Optional<String> utf8Sig(byte[] bytes) {
    return utf8(bytes).map(text -> !text.isEmpty() && text.charAt(0) == BYTE_ORDER_MARK ? text.substring(1) : text);
  }

  /** {@code yaml.safe_load}: the document (null for an empty one); empty when the bytes are not UTF-8 or not YAML. */
  private static Optional<Object> yaml(byte[] bytes) {
    Optional<String> text = utf8Sig(bytes);
    if (text.isEmpty()) {
      return Optional.empty();
    }
    try {
      LoaderOptions options = new LoaderOptions();
      options.setAllowDuplicateKeys(true);
      options.setMaxAliasesForCollections(50);
      options.setNestingDepthLimit(50);
      return Optional.ofNullable(new Yaml(new SafeConstructor(options)).load(text.get()));
    } catch (RuntimeException notYaml) {
      return Optional.empty();
    }
  }
}
