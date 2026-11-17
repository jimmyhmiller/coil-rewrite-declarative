# Coil compiler rewrite

Build a complete, self-hosting Coil compiler whose entire authored source is written in custom languages.

| Directory | What belongs here |
| --- | --- |
| [dsls/](dsls/) | Language definitions, their registered Coil readers, and the compilers for those languages |
| [src/](src/) | The replacement Coil compiler, written entirely in those languages |

Start with [AGENTS.md](AGENTS.md) for the implementation boundary and [DESIGN.md](DESIGN.md) for reference projects, a first implementation exercise, and the evidence needed to claim compatibility.

The first reader compiles structural patterns over Coil syntax. The declaration rules in `src/declarations.patterns` recognize ordinary function forms, typed parameters and nullary calls. Run `coil run tests/declarations.coil` to exercise these rules against parsed source. The executable compiler and self-hosting pipeline are still outstanding.
