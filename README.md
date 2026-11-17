# Coil compiler rewrite

Build a complete, self-hosting Coil compiler whose entire authored source is written in custom languages. The repository starts with two empty implementation directories.

| Directory | What belongs here |
| --- | --- |
| [dsls/](dsls/) | Language definitions, their registered Coil readers, and the compilers for those languages |
| [src/](src/) | The replacement Coil compiler, written entirely in those languages |

Start with [AGENTS.md](AGENTS.md) for the implementation boundary and [DESIGN.md](DESIGN.md) for reference projects, a first implementation exercise, and the evidence needed to claim compatibility. This baseline contains documentation only.
