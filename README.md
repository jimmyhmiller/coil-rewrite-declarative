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
coil run tests/declarations.coil
tests/cli/check.sh
```

The command pipeline in `src/main.commands` reads a file, indexes ordinary function declarations, validates signatures, and checks bodies. The rules in `src/check.judgments` cover integer and boolean literals, parameter references, and direct calls, including nested and forward calls. The CLI suite compares acceptance and rejection with the installed Coil compiler. Native code generation and self-hosting remain open.
