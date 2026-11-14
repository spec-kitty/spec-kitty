{
  description = "Spec Kitty CLI and development tools";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    built-in-pack = {
      url = "github:spec-kitty/spec-kitty-open-packs/a79c36318b7a506ca2ab26d74705c5e3e406004f";
      flake = false;
    };
  };

  outputs =
    {
      self,
      nixpkgs,
      built-in-pack,
    }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "aarch64-darwin"
      ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
    in
    {
      packages = forAllSystems (
        system:
        let
          pkgs = import nixpkgs { inherit system; };
          python = pkgs.python313;
          py = python.pkgs;
          lockedWheel =
            {
              pname,
              version,
              url,
              hash,
              propagatedBuildInputs ? [ ],
            }:
            py.buildPythonPackage {
              inherit pname version propagatedBuildInputs;
              format = "wheel";
              src = pkgs.fetchurl { inherit url hash; };
              doCheck = false;
            };
          # Nixpkgs either lacks these distributions or has versions outside this project's constraints.
          lockedTyper = lockedWheel {
            pname = "typer";
            version = "0.27.3";
            url = "https://files.pythonhosted.org/packages/07/ea/2e31b67051e91a133189e9c000c222502ddc6969856416de0d095de4c0b0/typer-0.27.3-py3-none-any.whl";
            hash = "sha256-5QAi8ouCqGMT5UUBMXodtkv4+NA2/4z+XKfkdnVFSv8=";
            propagatedBuildInputs = with py; [
              annotated-doc
              rich
              shellingham
            ];
          };
          lockedPackaging = lockedWheel {
            pname = "packaging";
            version = "26.2";
            url = "https://files.pythonhosted.org/packages/df/b2/87e62e8c3e2f4b32e5fe99e0b86d576da1312593b39f47d8ceef365e95ed/packaging-26.2-py3-none-any.whl";
            hash = "sha256-X8RSNrlEYQf/JBXOd8gHzuKGLLb6wiuKc4JtBpOwmA4=";
          };
          lockedHatchling = py.hatchling.overridePythonAttrs (_: {
            dependencies = with py; [
              editables
              lockedPackaging
              pathspec
              pluggy
              trove-classifiers
            ];
          });
          lockedPydanticCore = py.pydantic-core.overridePythonAttrs (
            old:
            let
              version = "2.46.3";
              src = pkgs.fetchFromGitHub {
                owner = "pydantic";
                repo = "pydantic";
                tag = "core-v${version}";
                hash = "sha256-RCPTWXaDsHxi8z+TSddMu3T2A6pWnj1U4XAQCanMdIQ=";
              };
              sourceRoot = "${src.name}/pydantic-core";
            in
            {
              inherit version src sourceRoot;
              cargoDeps = pkgs.rustPlatform.fetchCargoVendor {
                inherit (old) pname;
                inherit version src sourceRoot;
                hash = "sha256-mEnlxTUyyMgDBEfLMBrXPVPpR6YopO7qEPbZmiY1aec=";
              };
            }
          );
          lockedPydantic = lockedWheel {
            pname = "pydantic";
            version = "2.13.3";
            url = "https://files.pythonhosted.org/packages/f3/0a/fd7d723f8f8153418fb40cf9c940e82004fce7e987026b08a68a36dd3fe7/pydantic-2.13.3-py3-none-any.whl";
            hash = "sha256-bbFKyN/JoeV/h+osDeZwwlEkD0PLDDClEw6XINxhKSc=";
            propagatedBuildInputs = with py; [
              annotated-types
              lockedPydanticCore
              typing-extensions
              typing-inspection
            ];
          };
          lockedPydanticSettings = py.pydantic-settings.overridePythonAttrs (_: {
            dependencies = [
              lockedPydantic
              py.python-dotenv
            ];
          });
          lockedEvents = lockedWheel {
            pname = "spec-kitty-events";
            version = "11.3.0";
            url = "https://files.pythonhosted.org/packages/a3/25/66d2e90850b932e58604bef7ecd542de5ba8818fc942571f779fa855d520/spec_kitty_events-11.3.0-py3-none-any.whl";
            hash = "sha256-kucs7IvesyBiHLdUu8Rqn5FdmlF5+dxvjGBGYj7tHSU=";
            propagatedBuildInputs = [
              lockedPydantic
              py.python-ulid
            ];
          };
          lockedTracker = lockedWheel {
            pname = "spec-kitty-tracker";
            version = "0.5.2";
            url = "https://files.pythonhosted.org/packages/5b/ac/69f37ae99cacb50cb4a6e76386fb83704cc3657f2a949630bf626a96dd1d/spec_kitty_tracker-0.5.2-py3-none-any.whl";
            hash = "sha256-9hSWfCFMwptWZFcte7vuRHBs7/IrgQbPpGLzu4T8w58=";
            propagatedBuildInputs = [ py.httpx ];
          };
          lockedMcp = lockedWheel {
            pname = "mcp";
            version = "1.29.0";
            url = "https://files.pythonhosted.org/packages/01/c8/248b201f6d753d69fd5d6506011abbb35a946d9142b2ae311a948fd0be3d/mcp-1.29.0-py3-none-any.whl";
            hash = "sha256-9aB1u2EfI9b00IDGoWmfpidy7rxWK6nmazBt3eHHVfc=";
            propagatedBuildInputs = with py; [
              anyio
              httpx
              httpx-sse
              jsonschema
              lockedPydantic
              lockedPydanticSettings
              pyjwt
              python-multipart
              sse-starlette
              starlette
              typing-extensions
              typing-inspection
              uvicorn
            ];
          };
          source = pkgs.runCommand "spec-kitty-source" { } ''
            mkdir -p "$out"
            cp -R ${self}/. "$out/"
            chmod -R u+w "$out"
            mkdir -p "$out/packs"
            cp -R ${built-in-pack}/packs/built-in "$out/packs/built-in"
            substituteInPlace "$out/src/specify_cli/__init__.py" \
              --replace-fail '\n\nSet SPEC_KITTY_NO_UPGRADE_CHECK=1 to disable the upgrade-check notice.' ""
          '';
          runtimeDependencies =
            (with py; [
              charset-normalizer
              click
              cryptography
              google-re2
              httpx
              jsonschema
              platformdirs
              psutil
              pygments
              python-ulid
              pyyaml
              readchar
              requests
              rich
              ruamel-yaml
              toml
              tomli-w
            ])
            ++ [
              lockedPackaging
              lockedPydantic
              lockedPydanticSettings
              lockedTyper
              lockedEvents
              lockedTracker
              lockedMcp
            ];
          runtimeTools = [
            python
            pkgs.git
            pkgs.openssh
            pkgs.gh
            pkgs.uv
            pkgs.jdk25
            py.ruff
            py.mypy
          ];
          app = py.buildPythonApplication {
            pname = "spec-kitty-cli";
            version = "4.0.0rc8";
            src = source;
            format = "pyproject";
            build-system = [
              lockedHatchling
              lockedPackaging
              lockedPydantic
              py.python-ulid
              py.ruamel-yaml
            ];
            nativeBuildInputs = [ pkgs.makeWrapper ];
            dependencies = runtimeDependencies;
            dontUsePypaBuild = true;
            # Use the declared Hatchling backend directly with the pinned build-system environment.
            buildPhase = ''
              runHook preBuild
              hatchling build -t wheel
              runHook postBuild
            '';
            makeWrapperArgs = [
              "--argv0"
              "spec-kitty"
              "--set"
              "SPEC_KITTY_NO_UPGRADE_CHECK"
              "1"
              "--prefix"
              "PATH"
              ":"
              (pkgs.lib.makeBinPath runtimeTools)
            ];
            pythonImportsCheck = [
              "specify_cli"
              "kernel"
              "charter"
              "runtime"
            ];
            doCheck = false;
            meta = {
              description = "Spec Kitty governed delivery CLI";
              homepage = "https://github.com/spec-kitty/spec-kitty";
              license = pkgs.lib.licenses.mit;
              mainProgram = "spec-kitty";
              platforms = systems;
            };
          };
        in
        {
          default = app;
          spec-kitty-cli = app;
        }
      );

      apps = forAllSystems (system: {
        default = {
          type = "app";
          program = "${self.packages.${system}.default}/bin/spec-kitty";
          meta.description = "Run the Spec Kitty CLI";
        };
      });

      devShells = forAllSystems (
        system:
        let
          pkgs = import nixpkgs { inherit system; };
          py = pkgs.python313Packages;
        in
        {
          default = pkgs.mkShell {
            packages = [
              self.packages.${system}.default
            ]
            ++ [
              pkgs.python313
              pkgs.git
              pkgs.openssh
              pkgs.gh
              pkgs.uv
              pkgs.jdk25
              py.ruff
              py.mypy
            ];
          };
        }
      );
    };
}
