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
  public static final String SURFACE_OVERVIEW = "overview";
  public static final String SURFACE_DETAIL = "detail";
  public static final String KNOWN_DIVERGENCES = "knownDivergences";

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

  /**
   * One fixture class of the manifest. {@code surface} is {@code overview} when the entry carries no {@code surface} key (the 14 classes of the
   * first conformance gate stay byte-identical) and {@code detail} for the detail and artifact classes; {@code goldenFiles} are the golden file
   * names a {@code python-golden} detail class holds per fixture (empty for an overview class and for a {@code java-only} class).
   */
  public record ClassEntry(String tag, String parity, String property, String surface, List<String> goldenFiles, List<TreeFixture> fixtures) {

    /** An overview class: the surface the first conformance gate and every consumer of {@link #classes()} sees. */
    public ClassEntry(String tag, String parity, String property, List<TreeFixture> fixtures) {
      this(tag, parity, property, SURFACE_OVERVIEW, List.of(), fixtures);
    }
  }

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

  /**
   * The classes of the overview surface only, in manifest order. Every consumer written before the detail classes existed
   * ({@code GoldenSuiteTest}, the route and contract tests, the fixture factory tests) sees exactly what it saw before; the detail classes are
   * reached through {@link #detailClasses()} and {@link #allClasses()}.
   */
  public static List<ClassEntry> classes() {
    return allClasses().stream().filter(entry -> entry.surface().equals(SURFACE_OVERVIEW)).toList();
  }

  /** The classes of the detail and artifact surface only, in manifest order. */
  public static List<ClassEntry> detailClasses() {
    return allClasses().stream().filter(entry -> entry.surface().equals(SURFACE_DETAIL)).toList();
  }

  /** Every class of the manifest, overview and detail, in manifest order (the census and the directory-on-disk check read this). */
  @SuppressWarnings("unchecked")
  public static List<ClassEntry> allClasses() {
    Path root = root();
    List<ClassEntry> classes = new ArrayList<>();
    for (Object rawClass : (List<Object>) manifest().get("classes")) {
      Map<String, Object> entry = (Map<String, Object>) rawClass;
      String tag = (String) entry.get("tag");
      String parity = (String) entry.get("parity");
      String surface = entry.containsKey("surface") ? (String) entry.get("surface") : SURFACE_OVERVIEW;
      List<String> goldenFiles = entry.containsKey("goldenFiles") ? ((List<Object>) entry.get("goldenFiles")).stream().map(Object::toString).toList() : List.of();
      List<TreeFixture> fixtures = new ArrayList<>();
      for (Object rawFixture : (List<Object>) entry.get("fixtures")) {
        Map<String, Object> fixture = (Map<String, Object>) rawFixture;
        String name = (String) fixture.get("name");
        List<String> tags = fixture.containsKey("tags") ? ((List<Object>) fixture.get("tags")).stream().map(Object::toString).toList() : List.of();
        fixtures.add(new TreeFixture(tag, name, root.resolve(tag).resolve(name), parity, tags, (String) fixture.get("readDirectoryClass"), (String) fixture.get("headText")));
      }
      classes.add(new ClassEntry(tag, parity, (String) entry.get("property"), surface, List.copyOf(goldenFiles), List.copyOf(fixtures)));
    }
    return List.copyOf(classes);
  }

  /** The fixtures of the overview classes only (see {@link #classes()}). */
  public static List<TreeFixture> fixtures() {
    return classes().stream().flatMap(entry -> entry.fixtures().stream()).toList();
  }

  /** The fixtures of the detail and artifact classes only. */
  public static List<TreeFixture> detailFixtures() {
    return detailClasses().stream().flatMap(entry -> entry.fixtures().stream()).toList();
  }

  /** The fixtures of one overview class; an empty list for a detail tag (use {@link #detailClasses()} for those). */
  public static List<TreeFixture> fixturesOf(String tag) {
    return classes().stream().filter(entry -> entry.tag().equals(tag)).flatMap(entry -> entry.fixtures().stream()).toList();
  }

  /** The {@code knownDivergences} entries of the manifest (V1 to V27, V19 retired): id, cause, fixture, fixtures, oracleOutcome, javaAssertion, and for V3 and V4 defaultPathOutcomes. */
  @SuppressWarnings("unchecked")
  public static List<Map<String, Object>> knownDivergences() {
    List<Map<String, Object>> entries = new ArrayList<>();
    for (Object entry : (List<Object>) manifest().get(KNOWN_DIVERGENCES)) {
      entries.add((Map<String, Object>) entry);
    }
    return List.copyOf(entries);
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
