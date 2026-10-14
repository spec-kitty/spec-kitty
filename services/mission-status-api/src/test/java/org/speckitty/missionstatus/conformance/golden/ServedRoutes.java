package org.speckitty.missionstatus.conformance.golden;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;
import org.speckitty.missionstatus.conformance.golden.ServedRoute.Entry;
import org.speckitty.missionstatus.testsupport.ConformanceTree;
import org.speckitty.missionstatus.testsupport.ConformanceTree.TreeFixture;

/**
 * The registry of the detail route providers, and the ownership rule that makes every golden-bearing detail fixture x golden file pair
 * the business of exactly one provider by construction.
 *
 * <p>The providers belong to later work packages and do not exist at this tip, so the registry loads them by <em>name</em>
 * ({@code Class.forName}) and treats a missing class as an empty route. A typo in a name would hide a provider, so each route work
 * package asserts through {@link #loaded()} that its own provider was found. The four names and their work packages:
 *
 * <ul>
 *   <li>{@code MissionDetailServedRoute} (WP13): {@code get-mission.json};
 *   <li>{@code WorkPackageServedRoute} (WP14): {@code get-work-package.json}, {@code get-work-package-prompt.json};
 *   <li>{@code WorkPackageDetailServedRoute} (WP15): {@code get-work-package-detail.json};
 *   <li>{@code ArtifactServedRoute} (WP16): {@code list-artifacts.json}, {@code get-artifact-content.json}.
 * </ul>
 *
 * A fixture that no provider serves is neither compared nor red here; completeness is the whole-set floor of a later work package.
 */
public final class ServedRoutes {

  /** The package the providers live in. */
  static final String PROVIDER_PACKAGE = "org.speckitty.missionstatus.conformance.golden.served.";

  /** Golden file name to the simple name of the provider that owns it. */
  public static final Map<String, String> OWNER =
      Map.of(
          "get-mission.json", "MissionDetailServedRoute",
          "get-work-package.json", "WorkPackageServedRoute",
          "get-work-package-prompt.json", "WorkPackageServedRoute",
          "get-work-package-detail.json", "WorkPackageDetailServedRoute",
          "list-artifacts.json", "ArtifactServedRoute",
          "get-artifact-content.json", "ArtifactServedRoute");

  /** The six golden file names of the detail classes. */
  public static final Set<String> GOLDEN_FILES = Set.copyOf(OWNER.keySet());

  /** The simple names of the four providers. */
  public static final Set<String> PROVIDER_NAMES = Set.copyOf(OWNER.values());

  private final List<ServedRoute> providers;

  private ServedRoutes(List<ServedRoute> providers) {
    this.providers = List.copyOf(providers);
  }

  /** A registry over these providers (the self-test injects a planted one). */
  static ServedRoutes of(List<ServedRoute> providers) {
    return new ServedRoutes(providers);
  }

  /** The default registry: every provider class that exists on the classpath. */
  public static ServedRoutes load() {
    List<ServedRoute> found = new ArrayList<>();
    for (String name : new TreeSet<>(PROVIDER_NAMES)) {
      try {
        found.add((ServedRoute) Class.forName(PROVIDER_PACKAGE + name).getDeclaredConstructor().newInstance());
      } catch (ClassNotFoundException absent) {
        // the provider belongs to a later work package: an empty route
      } catch (ReflectiveOperationException broken) {
        throw new IllegalStateException("the provider " + name + " exists but cannot be created", broken);
      }
    }
    return new ServedRoutes(found);
  }

  /** The providers of this registry. */
  public List<ServedRoute> providers() {
    return providers;
  }

  /** The simple class names of the providers of this registry. */
  public Set<String> providerNames() {
    Set<String> names = new LinkedHashSet<>();
    providers.forEach(provider -> names.add(provider.getClass().getSimpleName()));
    return names;
  }

  /** The providers the default registry actually loaded (so a route work package can assert its own was found). */
  public static List<ServedRoute> loaded() {
    return load().providers();
  }

  public static Set<String> loadedProviderNames() {
    return load().providerNames();
  }

  // ---- the ownership rule ----------------------------------------------------------------------------------------------------

  /**
   * The manifest-derived entries: for every fixture of the detail classes and every given golden file name that fixture holds, one
   * {@link Entry}. Nothing here hard-codes a fixture list.
   */
  public static Set<Entry> expectedEntries(Set<String> goldenFiles) {
    Set<Entry> entries = new LinkedHashSet<>();
    for (TreeFixture fixture : ConformanceTree.detailFixtures()) {
      for (String file : new TreeSet<>(goldenFiles)) {
        if (ConformanceTree.golden(fixture, file) != null) {
          entries.add(new Entry(fixture.key(), file));
        }
      }
    }
    return entries;
  }

  /**
   * The violations of the partition: a pair served by two providers; a provider whose golden files leave its {@link #OWNER} row, or
   * whose served pairs hold a golden file outside it; and, when the given providers own all six golden files, any pair of
   * {@code expectedEntries(all six)} that no provider serves. Empty means the partition holds.
   */
  public static List<String> ownershipProblems(List<ServedRoute> providers) {
    List<String> problems = new ArrayList<>();
    Map<Entry, String> servedBy = new LinkedHashMap<>();
    Set<String> owned = new LinkedHashSet<>();
    for (ServedRoute provider : providers) {
      String name = provider.getClass().getSimpleName();
      Set<String> row = new TreeSet<>();
      OWNER.forEach((file, owner) -> {
        if (owner.equals(name)) {
          row.add(file);
        }
      });
      if (!new TreeSet<>(provider.goldenFiles()).equals(row)) {
        problems.add(name + " owns " + new TreeSet<>(provider.goldenFiles()) + " but its row of the partition is " + row);
      }
      owned.addAll(provider.goldenFiles());
      for (Entry entry : provider.served()) {
        if (!row.contains(entry.goldenFile())) {
          problems.add(name + " serves " + entry + " whose golden file is outside its row " + row);
        }
        String previous = servedBy.putIfAbsent(entry, name);
        if (previous != null) {
          problems.add(entry + " is served by both " + previous + " and " + name);
        }
      }
    }
    if (owned.containsAll(GOLDEN_FILES)) {
      for (Entry expected : expectedEntries(GOLDEN_FILES)) {
        if (!servedBy.containsKey(expected)) {
          problems.add(expected + " is served by no provider");
        }
      }
    }
    return problems;
  }
}
