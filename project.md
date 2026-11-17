# coil-rewrite-declarative

A language-first rewrite of the whole Coil compiler. Compiler semantics, language implementations, and execution plans become programs in purpose-built languages; a small Coil seed starts the bootstrap. Preserve the existing declarative native backend.

The implementation plan is [PLAN.md](PLAN.md). Status: executable seed DSLs derive schema storage, readers, concrete type judgments, scalar lowering, and unary function program compilation through the retained native backend. Full Coil compatibility and self-hosting remain unimplemented. Project notebook: `coil-rewrite-declarative`; detailed plan: `coil-rewrite-declarative-plan`.
