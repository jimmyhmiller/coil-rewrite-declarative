# Building the replacement Coil compiler

## Where to write a change

Put every decision about the behavior of Coil in `src/`, expressed in a custom language. This includes the executable entry point, command behavior, package loading, reader dispatch, scope, macro expansion, type checking, specialization, diagnostics, lowering, backend selection and phase order. A contributor reading the source here should be able to explain why the compiler accepts, rejects, or emits something.

Put language definitions and their compilers in `dsls/`. Bootstrap them with Coil metaprograms. Give a DSL the operations its domain needs, then use those operations in `src/` to describe Coil. As patterns emerge in the language compilers, express those compilers in a language for defining languages, with a small Coil bootstrap.

For example, a judgment language can compile premises, carry a typing environment, and specialize rule dispatch. The rule that introduces a Coil function signature, the names and types it binds, and the rule that checks its body against its declared result all belong in `src/`. A reader that emits a hardcoded Coil function checker violates this boundary even if a DSL form invokes it. If a rule cannot be expressed, extend the language and write the rule in it.

## How a build works

Register custom file readers and map source modules in the Coil package manifest. An ordinary `coil build` must consume the authored DSL modules through Coil's import and reader system. Use Coil metaprogramming for compilation. No Python, separate generator, generated source checkout, or handwritten Coil replacement compiler. Run `coil guide` before writing Coil.

Reuse the established Stogir declarative backend. Consult the upstream source and its tests before choosing the integration boundary. The compiler's lowering rules and use of the backend belong in `src/`. Preserve upstream provenance when bringing in backend material.

## How to evaluate work

Exercise each new compiler rule through the integrated executable using real Coil input. Check accepted behavior and rejected input against the reference compiler, including source locations when relevant. Where practical, change a rule in `src/` and show its effect with identical DSL compiler code.

Count all authored production code, including language compilers, the bootstrap and the retained backend. Measure generated output separately. Keep implementation status, compatibility evidence and performance measurements distinct. The end goal includes building real projects, rebuilding the compiler with itself, and a substantial measured reduction in total authored code with good performance.

Read [DESIGN.md](DESIGN.md) before choosing the first language. The previous prototype has been removed. Start from the documents and upstream references.
