{
  description = "Central, Dolphin's CI/CD plumbing infrastructure";

  inputs.flake-utils.url = "github:numtide/flake-utils";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.11";
  inputs.poetry2nix.url = "github:nix-community/poetry2nix";
  inputs.poetry2nix.inputs.nixpkgs.follows = "nixpkgs";

  outputs = { self, nixpkgs, flake-utils, poetry2nix }: {
    overlay = nixpkgs.lib.composeManyExtensions [
      poetry2nix.overlays.default
      (final: prev: {
        central = prev.poetry2nix.mkPoetryApplication {
          projectDir = ./.;
          overrides = prev.poetry2nix.defaultPoetryOverrides.extend (self: super: {
            pypeul = super.pypeul.overridePythonAttrs (old: { buildInputs = (old.buildInputs or []) ++ [ super.poetry-core ]; });
          });
        };
      })
    ];
  } // (flake-utils.lib.eachDefaultSystem (system:
    let
      pkgs = import nixpkgs {
        inherit system;
        overlays = [ self.overlay ];
      };
    in rec {
      packages.central = pkgs.central;
      defaultPackage = pkgs.central;

      devShells.default = with pkgs; mkShell {
        buildInputs = [ poetry ];
      };
    }
  ));
}
