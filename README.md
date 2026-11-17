# Coil compiler rewrite

Build from the repository root with the installed Coil toolchain.

```sh
coil build -o coil-rewrite
./coil-rewrite check tests/compiler/integer-functions.coil
./coil-rewrite run tests/compiler/integer-functions.coil composed 1
coil run tests/reader-build.coil --debug-checks
```

The example returns 551. Coil imports the compiler's source from `compiler/frontend/core.schema` using the reader registered in `Coil.toml`. The same reader compiles the resolution and expansion languages on import. The package entry forwards command-line arguments to the compiler module.

The executable supports integer functions, lexical binding, conditionals, direct calls and function pointers. Full Coil compatibility and self-hosting are in progress. The Coil regression fixtures live under `tests/`. The historical Python validation drivers were removed with the separate generation workflow. Their complete test coverage has yet to be ported to Coil.
