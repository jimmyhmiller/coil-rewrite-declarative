# Coil compiler rewrite

The compiler is authored in the custom languages under `compiler/`. The Coil package registers readers for schema, protocol and search modules. Build and test instructions are in [README.md](README.md). The retained native backend lives under `vendor/coil/`.

The compiler currently runs integer programs with functions, lexical bindings, conditionals and native calls. Module loading, full macro expansion, full type checking and self-hosting remain incomplete. The project notebook is `coil-rewrite-declarative`.
