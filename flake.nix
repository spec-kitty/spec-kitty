{
  description = "Spec Kitty CLI and development tools";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.uv2nix.follows = "uv2nix";
    };
  };

  outputs =
    {
      self,
      nixpkgs,
      pyproject-nix,
      uv2nix,
      pyproject-build-systems,
    }:
    let
      inherit (nixpkgs) lib;
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "aarch64-darwin"
      ];
      forAllSystems = lib.genAttrs systems;
      project = fromTOML (builtins.readFile ./pyproject.toml);
      sourceVersion = project.project.version;
      sourceLines = lib.splitString "\n" (builtins.readFile ./packs/built-in.source.yaml);
      pinValue =
        name:
        let
          prefix = "${name}: ";
          matches = builtins.filter (line: lib.hasPrefix prefix line) sourceLines;
        in
        if builtins.length matches != 1 then
          throw "Expected exactly one ${name} in packs/built-in.source.yaml"
        else
          lib.removePrefix prefix (builtins.head matches);
      builtInPackRepository = pinValue "repository";
      builtInPackRevision = pinValue "commit";
      builtInPack = fetchGit {
        url = builtInPackRepository;
        rev = builtInPackRevision;
      };
      workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };
      uvOverlay = workspace.mkPyprojectOverlay { sourcePreference = "wheel"; };
      pythonSets = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          python = pkgs.python313;
          source = pkgs.runCommand "spec-kitty-source" { } ''
            mkdir -p "$out"
            cp -R ${self}/. "$out/"
            chmod -R u+w "$out"
            mkdir -p "$out/packs"
            # The Internal pack never ships (ADR 2026-08-16-3): drop it explicitly, so
            # a path: fetch of a synced checkout cannot bring it in.
            rm -rf "$out/packs/internal"
            cp -R ${builtInPack}/packs/built-in "$out/packs/built-in"
          '';
          packageOverlay = _final: previous: {
            "spec-kitty-cli" = previous."spec-kitty-cli".overrideAttrs (_: {
              src = source;
              version = sourceVersion;
            });
          };
        in
        (pkgs.callPackage pyproject-nix.build.packages { inherit python; }).overrideScope (
          lib.composeManyExtensions [
            pyproject-build-systems.overlays.wheel
            uvOverlay
            packageOverlay
          ]
        )
      );
      runtimeTools =
        pkgs: with pkgs; [
          git
          openssh
          gh
          uv
          jdk25
        ];
      appForSystem =
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          pythonSet = pythonSets.${system};
          virtualenv = pythonSet.mkVirtualEnv "spec-kitty-cli-env" workspace.deps.default;
        in
        pkgs.stdenvNoCC.mkDerivation {
          pname = "spec-kitty-cli";
          version = sourceVersion;
          dontUnpack = true;
          nativeBuildInputs = [ pkgs.makeWrapper ];
          installPhase = ''
            mkdir -p "$out/bin"
            makeWrapper "${virtualenv}/bin/spec-kitty" "$out/bin/spec-kitty" \
              --set SPEC_KITTY_NO_UPGRADE_CHECK 1 \
              --prefix PYTHONPATH : "${pythonSet."spec-kitty-cli"}/${pythonSet.python.sitePackages}" \
              --prefix PATH : "${lib.makeBinPath (runtimeTools pkgs)}"
          '';
          meta = {
            description = "Spec Kitty governed delivery CLI";
            homepage = "https://github.com/spec-kitty/spec-kitty";
            license = lib.licenses.mit;
            mainProgram = "spec-kitty";
            platforms = systems;
          };
        };
    in
    {
      packages = forAllSystems (system: {
        default = appForSystem system;
        spec-kitty-cli = appForSystem system;
      });

      apps = forAllSystems (system: {
        default = {
          type = "app";
          program = "${appForSystem system}/bin/spec-kitty";
          meta.description = "Run the Spec Kitty CLI";
        };
      });

      devShells = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          pythonSet = pythonSets.${system};
          pythonEnv = pythonSet.mkVirtualEnv "spec-kitty-cli-dev-env" (
            workspace.deps.default // workspace.deps.groups
          );
        in
        {
          default = pkgs.mkShell {
            packages = [
              (appForSystem system)
              pythonEnv
            ]
            ++ runtimeTools pkgs;
          };
        }
      );
    };
}
