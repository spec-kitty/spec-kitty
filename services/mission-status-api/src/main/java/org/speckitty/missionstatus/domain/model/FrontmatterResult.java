package org.speckitty.missionstatus.domain.model;

import java.util.Objects;

/**
 * What decoding the bytes of one Work Package file gave: the validated metadata with the body, or a rejection with its class. A file
 * whose bytes are not strict UTF-8 is a rejection of the decoder ({@link RejectionClass#NOT_UTF8}): the decoder decodes the bytes itself
 * and never replaces one, so the oracle's skipped {@code UnicodeDecodeError} file and its skipped {@code FrontmatterError} or
 * {@code ValidationError} file are the same outcome to the caller: skip.
 */
public sealed interface FrontmatterResult {

  /** Why a file was rejected. The class is for tests and logs; no caller serves it. */
  enum RejectionClass {
    /** The bytes are not strict UTF-8. */
    NOT_UTF8,
    /** The text does not start with {@code ---}. */
    NO_FRONTMATTER,
    /** No later line is {@code ---} once stripped. */
    NO_CLOSING_DELIMITER,
    /** The YAML does not parse. */
    YAML_SYNTAX,
    /** A mapping holds one key twice. */
    DUPLICATE_KEY,
    /** The document is not a mapping. */
    NOT_A_MAPPING,
    /** A YAML construct the decoder refuses rather than decode differently from the oracle (anchor, tag, merge key, directive). */
    UNSUPPORTED_YAML,
    /** The mapping is not a valid {@code WPMetadata}: an unknown key, a wrong type or a failed validator. */
    VALIDATION
  }

  /** The validated metadata and the body: every line after the closing delimiter, joined by a line feed. */
  record Parsed(WpMetadata metadata, String body) implements FrontmatterResult {
    public Parsed {
      Objects.requireNonNull(metadata, "metadata");
      Objects.requireNonNull(body, "body");
    }
  }

  /** The file is not a Work Package file the oracle would read. */
  record Rejected(RejectionClass kind) implements FrontmatterResult {
    public Rejected {
      Objects.requireNonNull(kind, "kind");
    }
  }
}
