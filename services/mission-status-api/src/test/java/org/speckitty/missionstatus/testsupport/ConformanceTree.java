package org.speckitty.missionstatus.testsupport;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.net.URISyntaxException;
import java.net.URL;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * The committed conformance tree of the golden work package ({@code src/test/resources/conformance}): the manifest, the fixture trees
 * and their goldens, {@code resolver-cases.json}. Read from the test classpath, which Gradle serves as a directory. Nothing here
 * writes; the fixtures are copied into scratch directories by {@link ProjectHeaderMaterialisation} before anything reads them.
 */
public final class ConformanceTree {

  public static final String MANIFEST = "manifest.json";
  public static final String RESOLVER_CASES = "resolver-cases.json";
  public static final String GOLDEN_DIR = "golden";
  public static final String MISSIONS_GOLDEN = "missions.json";
  public static final String PROJECT_GOLDEN = "project.json";
  public static final String TAG_JAVA_ONLY = "javaOnly";
  public static final String TAG_KNOWN_DIVERGENCE = "knownDivergence";
  public static final String PARITY_GOLDEN = "python-golden";
  public static final String PARITY_JAVA_ONLY = "java-only";

  /** One fixture of the manifest. {@code headText} is the exact HEAD text a project-header fixture installs (else null). */
  public record TreeFixture(String tag, String name, Path dir, String parity, List<String> tags, String readDirectoryClass, String headText) {

    public String key() {
      return tag + "/" + name;
    }

    /** The key, not the scratch path: test reports and logs must not carry a directory of the machine. */
    @Override
    public String toString() {
      return key();
    }

    public boolean javaOnly() {
      return tags.contains(TAG_JAVA_ONLY);
    }

    public boolean knownDivergence() {
      return tags.contains(TAG_KNOWN_DIVERGENCE);
    }
  }

  /** One fixture class of the manifest. */
  public record ClassEntry(String tag, String parity, String property, List<TreeFixture> fixtures) {}

  private ConformanceTree() {}

  /** The directory that holds {@code manifest.json}. */
  public static Path root() {
    URL url = ConformanceTree.class.getResource("/conformance/" + MANIFEST);
    if (url == null) {
      throw new IllegalStateException("conformance/manifest.json is not on the test classpath");
    }
    try {
      return Path.of(url.toURI()).getParent();
    } catch (URISyntaxException unusable) {
      throw new IllegalStateException("the conformance tree is not a directory on the file system", unusable);
    }
  }

  @SuppressWarnings("unchecked")
  public static Map<String, Object> manifest() {
    return (Map<String, Object>) CanonicalJson.parse(read(root().resolve(MANIFEST)));
  }

  @SuppressWarnings("unchecked")
  public static List<ClassEntry> classes() {
    Path root = root();
    List<ClassEntry> classes = new ArrayList<>();
    for (Object rawClass : (List<Object>) manifest().get("classes")) {
      Map<String, Object> entry = (Map<String, Object>) rawClass;
      String tag = (String) entry.get("tag");
      String parity = (String) entry.get("parity");
      List<TreeFixture> fixtures = new ArrayList<>();
      for (Object rawFixture : (List<Object>) entry.get("fixtures")) {
        Map<String, Object> fixture = (Map<String, Object>) rawFixture;
        String name = (String) fixture.get("name");
        List<String> tags = fixture.containsKey("tags") ? ((List<Object>) fixture.get("tags")).stream().map(Object::toString).toList() : List.of();
        fixtures.add(new TreeFixture(tag, name, root.resolve(tag).resolve(name), parity, tags, (String) fixture.get("readDirectoryClass"), (String) fixture.get("headText")));
      }
      classes.add(new ClassEntry(tag, parity, (String) entry.get("property"), List.copyOf(fixtures)));
    }
    return List.copyOf(classes);
  }

  public static List<TreeFixture> fixtures() {
    return classes().stream().flatMap(entry -> entry.fixtures().stream()).toList();
  }

  public static List<TreeFixture> fixturesOf(String tag) {
    return classes().stream().filter(entry -> entry.tag().equals(tag)).flatMap(entry -> entry.fixtures().stream()).toList();
  }

  /** The bytes of one golden file of a fixture, or null when the fixture has none. */
  public static byte[] golden(TreeFixture fixture, String file) {
    Path path = fixture.dir().resolve(GOLDEN_DIR).resolve(file);
    return Files.isRegularFile(path) ? read(path) : null;
  }

  @SuppressWarnings("unchecked")
  public static List<Map<String, Object>> resolverCases() {
    List<Map<String, Object>> rows = new ArrayList<>();
    for (Object row : (List<Object>) CanonicalJson.parse(read(root().resolve(RESOLVER_CASES)))) {
      rows.add((Map<String, Object>) row);
    }
    return List.copyOf(rows);
  }

  static byte[] read(Path file) {
    try {
      return Files.readAllBytes(file);
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    }
  }
}
