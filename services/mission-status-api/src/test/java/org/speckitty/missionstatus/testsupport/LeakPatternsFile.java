package org.speckitty.missionstatus.testsupport;

import java.io.IOException;
import java.io.InputStream;
import java.io.UncheckedIOException;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.regex.Pattern;
import org.speckitty.missionstatus.domain.redaction.LeakClasses;

/**
 * The committed {@code leak-patterns.json} on the classpath (the file WP07's generator writes from the Python source), read the way
 * the service will read it: every pattern is compiled through {@link LeakClasses#compile(String)} and nothing else. The wiring that
 * reads this file in production is another work package's; the test factories read it here so the projection class runs on the real
 * patterns.
 */
public final class LeakPatternsFile {

  public static final String RESOURCE = "/leak-patterns.json";

  /** One entry of the file. */
  public record Entry(String id, String kind, String fieldClass, String pattern) {}

  private LeakPatternsFile() {}

  public static byte[] bytes() {
    try (InputStream in = LeakPatternsFile.class.getResourceAsStream(RESOURCE)) {
      if (in == null) {
        throw new IllegalStateException(RESOURCE + " is not on the classpath");
      }
      return in.readAllBytes();
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    }
  }

  public static String sha256() {
    return sha256(bytes());
  }

  public static String sha256(byte[] content) {
    try {
      return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(content));
    } catch (NoSuchAlgorithmException impossible) {
      throw new IllegalStateException("SHA-256 is part of every Java platform", impossible);
    }
  }

  @SuppressWarnings("unchecked")
  public static List<Entry> entries() {
    Map<String, Object> document = (Map<String, Object>) CanonicalJson.parse(bytes());
    List<Entry> entries = new ArrayList<>();
    for (Object raw : (List<Object>) document.get("patterns")) {
      Map<String, Object> entry = (Map<String, Object>) raw;
      entries.add(new Entry((String) entry.get("id"), (String) entry.get("kind"), (String) entry.get("fieldClass"), (String) entry.get("pattern")));
    }
    return List.copyOf(entries);
  }

  /** The compiled classes, in file order within each group. */
  public static LeakClasses load() {
    List<Pattern> strict = new ArrayList<>();
    List<Pattern> human = new ArrayList<>();
    List<Pattern> secrets = new ArrayList<>();
    Pattern email = null;
    Pattern emailAnchored = null;
    for (Entry entry : entries()) {
      Pattern compiled = LeakClasses.compile(entry.pattern());
      switch (entry.kind()) {
        case "host_path" -> (entry.fieldClass().equals("strict") ? strict : human).add(compiled);
        case "email" -> {
          if (entry.id().equals("email-anchored")) {
            emailAnchored = compiled;
          } else {
            email = compiled;
          }
        }
        case "secret" -> secrets.add(compiled);
        default -> throw new IllegalStateException("unknown pattern kind " + entry.kind());
      }
    }
    return new LeakClasses(strict, human, email, emailAnchored, secrets);
  }
}
