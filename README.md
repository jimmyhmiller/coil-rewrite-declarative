# Coil compiler rewrite

Build a complete, self-hosting Coil compiler whose entire authored source is written in custom languages.

| Directory | What belongs here |
| --- | --- |
| [dsls/](dsls/) | Language definitions, their registered Coil readers, and the compilers for those languages |
| [src/](src/) | The replacement Coil compiler, written entirely in those languages |

Start with [AGENTS.md](AGENTS.md) for the implementation boundary and [DESIGN.md](DESIGN.md) for reference projects, a first implementation exercise, and the evidence needed to claim compatibility.

## Build and exercise the checker

From this checkout, run:

```sh
coil build
build/debug/rewrite check program.coil
build/debug/rewrite run program.coil
build/debug/rewrite build program.coil -o program
build/debug/rewrite emit-obj program.coil -o program.o
coil run tests/declarations.coil
tests/cli/check.sh
```

The command pipeline in `src/main.commands` reads a file, indexes ordinary function declarations, validates signatures, and checks bodies. The rules in `src/check.judgments` cover integer and boolean literals, parameter references, direct calls, conditional branches, sequencing with `do`, and sequential `let` bindings. Scalar mutable locals support `set!`, `store!`, and `load`. Functions may return a scalar or `void`. Scalar ascriptions and integer casts feed the operator rules in `src/core.operators`, which cover addition, subtraction, multiplication, bitwise operations, and comparisons. The checker records each expression’s type and resolves each local reference to its binding before native lowering. The CLI suite compares acceptance and rejection with the installed Coil compiler. The native lowering rules in `src/native.lowering` build Stogir graphs for these expressions. The host target and object writer are selected in `src/host.machine`. Place the maintained Coil checkout at `../coil` for its `src/declarative` package. Its NOTICE records the backend’s provenance. The CLI tests link and execute generated objects on macOS arm64 and compare program exit statuses with the reference compiler. Native 128-bit integer lowering and self-hosting remain open.
