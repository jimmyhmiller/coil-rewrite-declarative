# Building Coil out of languages

Design proposal, 2026-11-16. The first deliverable is a complete vertical slice that establishes whether this approach actually reduces total implementation cost. Language names below are provisional, not implemented APIs.

## What success means

Produce a compatible, self-hosting Coil toolchain whose authored implementation is substantially smaller and whose compile time and memory use improve. Count the DSL compilers, seed, runtime, adapters, and retained backend alongside the compiler specifications. Generated Coil is measured separately; moving complexity into a generator does not make it disappear.

Provisional budget: 45,000 authored physical lines for the whole production toolchain, including retained backend and language machinery, with a 30,000-line stretch target. These are design constraints to validate, not estimates already supported by an implementation. Report code-only lines, physical lines and bytes separately; tests and vendored dependencies get their own totals. Never shorten names or compress formatting to meet the budget.

Compatibility includes readers, metaprograms, compile-time evaluation, generics, modules, diagnostics, artifacts, native/LLVM/wasm output, debug information, C interoperation, JIT mechanisms, and CLI tooling. Track each explicitly. A native-only prototype is a milestone, not completion of the rewrite.

## Evidence from the existing projects

Inspected Coil at b7a54594b42820c24c4b4cce0d9348f160bdd38e and high-level-lang at 1e488d3f4580ebe064da449d2b1d6d5a6a68c4c1. Relevant sources: Coil's docs/reference/NATIVE_BACKEND.md, src/compiler/pipeline.coil, high-level-lang/README.md, src/languages/rules.syntax and src/bundle/early.attrs; Stogir's project.md, handoff.md and design/review notebook cells.

The current src/compiler tree contains 219,746 physical lines of .coil, including generated code. Frontend is 81,525; meta 26,104; backend 27,086; declarative 22,185; CLI 28,357. This is an inventory, not the authored baseline needed for a reduction claim. Establish the generated/authored split before comparing.

High-level-lang demonstrates grammar-defined languages, attribute equations fused into traversals, indexed relations, typed rules, structural sharing, and execution policies separated from semantics. Its README reports roughly 12,200 code lines of language compilers plus 2,100 runtime lines: the machinery has a real cost. Reuse proven concepts and selectively port mechanisms after inspecting their contracts; do not import JavaScript-specific assumptions.

The Stogir backend now lives in Coil's src/declarative. Keep that source and its tests as the authoritative backend, pinned by revision when imported here. Its latest notebook review exposes a crucial failure mode: assignment renamed scatter and loops renamed sweep still describe an imperative implementation. Another size audit counted 2,337 declaration lines plus 2,095 machinery lines against 2,992 original lines. These existing findings are constraints on this design, not newly discovered bugs.

A new language earns its place by removing a repeated semantic decision, checking an invariant, or deriving an execution strategy. A string template around one old loop is insufficient. An independent client must exercise different shapes of the domain, not just rename the original entities.

## The language architecture

Use one shared typed core for language implementations, with specialized frontends. Sharing types, patterns, source locations, effects, collections and code generation prevents each DSL from growing a private compiler. Preserve domain distinctions rather than forcing all work through a universal rule engine.

| Domain | Author writes | Language compiler derives |
|---|---|---|
| Syntax and representations | Grammars, node schemas, field roles, invariants | Readers, typed constructors, visitors, printers, verifiers and canonical dumps |
| Binding | Scope introduction, visibility, namespaces, import and export rules | Symbol indexing, lookup, duplicate checks and binding explanations |
| Typing | Ordered synthesis/checking judgments, constraints, elaboration and blame | Specialized dispatch, constraint scheduling, typed IR and diagnostics |
| Expansion | Phase transitions, transform contracts, introduced declarations, dependencies | Expansion worklists, invalidation, provenance and checked phase boundaries |
| Structural transformations | Typed patterns, context equations, replacement expressions | Fused traversals, sharing and exhaustive handling checks |
| Relations and analyses | Relations, finite lattices, transfer rules, joins | Indexes, semi-naive worklists, SCC scheduling and optional explanations |
| Specialization | Instance keys, reachability, substitution and layout requirements | Deduplicated monomorphization queues and termination diagnostics |
| Lowering | Typed source/target rules, evaluation order, layout and effect requirements | Verified lowering to CIR and adapters to other output paths |
| Artifacts and sessions | Wire schemas, identity inputs, legal state transitions | Encoding, compatibility validation and session protocol checks |
| Build and commands | Queries, dependencies, effects, command schemas and plans | Caching, scheduling, CLI dispatch and reproducible manifests |

Start with schemas, typed transformations, judgments, and a minimal execution-plan vocabulary. Add a separate surface only when real compiler cases establish its value. Attributes and relations may be constructs within these languages rather than independent file types.

### Types are judgments with an operational meaning

Distinguish synthesis from checking against an expected type. Rules return elaborated expressions plus constraints and source origins. Make priority, ambiguity, contextual literal typing and failure selection explicit. Do not use unordered Datalog for unification with mutable substitutions.

A conceptual conditional rule checks its condition as Bool, checks both branches against the expected result, and returns a typed conditional. Synthesis instead obtains branch types and applies Coil's actual compatibility rule. Divergence, numeric conversions, overloaded operations and generic instantiation must be captured from current behavior, not guessed from this sketch.

Use an explicit constraint kernel: interned types, union-find where appropriate, occurs checks, substitutions, and bounded diagnostic evidence. Recursive declarations are checked by SCC with declared signatures available before bodies. No silent fallback to the old checker. Unknown behavior fails as unsupported in the prototype.

### Expansion is a staged protocol

Model reading, declaration discovery, binding, expansion, compile-time execution and checking as explicit states with typed inputs and outputs. The existing compiler intertwines them; first map legal transitions and dependencies using actual reader and metaprogram fixtures. Do not assume a single parse-expand-resolve-check pass is semantically sufficient.

Each transform records its input identities, phase, outputs, introduced names and origins. Preserve Coil's existing name-introduction behavior; hygiene changes would be a separate language change. Effectful compile-time code executes with declared host capabilities. Cache only when dependencies and effects justify reuse. Cycles and repeated expansion report a trace; resource limits are diagnostics, not arbitrary successful truncation.

Keep original source, reader locations and expansion ancestry available through checking and lowering. Generated-code errors must point to the DSL rule and originating user form.

### Performance is part of the languages

Schemas choose compact IDs, interned names/types and arena lifetimes. Semantic specifications use entities and fields; physical plans select dense columns, indexes and storage ownership. The compiler verifies the plan against access/effect requirements. Avoid a boxed universal AST for every phase.

Relations require finite domains or an explicit convergence argument; reject negative recursion unless stratified. Attribute dependencies must have an acyclic schedule or an explicitly declared fixed-point interpretation. Rewrites declare traversal and termination policy. Rule compilation produces native dispatch and loops, not a generic interpreter in production hot paths.

Queries own their results and record all inputs, including target, compiler version, macro code and files read. Start with deterministic serial execution and correct lifetime release. Add parallelism only after effects and ownership permit it; compare results across schedules. Caching is an optimization, and cold recomputation is its oracle.

## Making the language compilers languages too

1. Write a deliberately small seed in Coil: reader for the initial schema/rule notation, typed core validator, and emitter of ordinary Coil. Use Coil's current compiler to build it. Keep its supported subset frozen and explicit.
2. Write the full grammar, transformation and judgment compilers in that initial notation. Their parsing, binding, checking and lowering become the second client of the same facilities used for Coil.
3. Generate those language compilers with the seed. Use the resulting compiler to regenerate itself. Compare canonical generated programs, then deterministic objects where reproducible, and run semantic tests at every stage.
4. Build the rewritten Coil compiler with the regenerated language toolchain. Use rewritten Coil to rebuild both the language toolchain and Coil. Reach a stable stage2/stage3 result and run compatibility gates on the final stage.
5. Retain an auditable seed and reproducible generated bootstrap distribution. The dependency graph must never require the new compiler to exist before anything can build it.

Some platform primitives remain Coil/FFI: allocation, files, threads, executable memory and OS calls. Keep these small and domain-independent. Record every escape from a DSL with its reason and size; migrate it when a useful abstraction emerges. Do not pretend a bootstrap with no trusted base is possible.

## Backend and whole-toolchain boundary

Import the current backend's authored DSLs, language implementations, runtime and tests with provenance. Initially use generated Coil from the same revision to keep the bootstrap independent of backend readers. Regeneration must reproduce that snapshot. Adapt the new typed/lowered representation to CIR and run CIR verification before code generation.

Inventory layouts, evaluation order, calling conventions, debug locations, relocations, traps and runtime symbols at this boundary. Initially preserve behavior; subsequent layout changes require cross-backend and C ABI evidence.

LLVM and wasm lowering remain explicit workstreams after the native slice; share typed lowering and layout semantics where supported rather than reimplementing language semantics in each backend. Reader artifacts, units, installation, formatter, documentation, lint, project handling and debugger behavior belong in the parity ledger.

JIT compilation accepts new definitions and exposes dependencies, addresses, Var cells and retirement. Replacement remains metaprogram policy. Preserve coil.repl's same-signature replacement boundary; do not add changed-signature replacement or migration to the compiler or JIT.

## Delivery sequence and gates

1. **Baseline and contracts.** Classify authored/generated source; pin revisions and corpus; record cold/warm time, peak process-tree RSS, output size and self-build time on this Mac. Build a parity ledger mapping every CLI family and semantic area to existing tests. Map expansion phases and CIR contracts. Deliver reproducible measurement commands before performance claims.
2. **Prove the language approach.** Implement schema, transformation and judgment seed support. Compile literals, lexical lets, functions, calls and conditionals through typed IR to the retained backend. Include wrong-type and unresolved-name diagnostics. Use a small second language with different binding behavior and at least one language-toolchain component as independent clients. Count all supporting machinery.
3. **Front-end depth.** Add modules, recursive declarations, generics, aggregates, pattern matching, effects and specialization in dependency order. Differentially compare normalized checked/mono dumps and executable behavior. Each addition extends area-level tests instead of creating a test file per bug.
4. **Metaprogramming early.** Before declaring the frontend complete, run a custom reader, a transform introducing definitions, and compile-time execution through the new phase protocol. Then migrate the full compile-time APIs and artifact handling. This is a high-risk architectural gate, not end-stage integration.
5. **Self-description.** Move language compilers into the new languages and prove regeneration. Reject designs that require growing a second general-purpose compiler for every surface.
6. **Full toolchain.** Complete LLVM/wasm, JIT/session mechanisms, artifacts, diagnostics, tools, installation and all parity-ledger entries. Run native/LLVM/C ABI comparisons and debug checks. Linux-specific validation uses computer.jimmyhmiller.com; normal development stays on macOS.
7. **Self-host and replace.** Bootstrap the entire tower, reach fixpoint, run Coil FAST and COMPREHENSIVE equivalents, and validate real external Coil projects. Publish authored-size and end-to-end performance results before replacing the installed compiler.

Every milestone produces runnable artifacts, a compatibility delta, total authored-size accounting and measurements. If a language merely relocates procedural code, revise the abstraction before broad migration.

## Acceptance and risk management

Correctness: exact acceptance/rejection where specified; normalized IR comparison when representations permit; executable output/exit/trap comparisons otherwise. Diagnostic changes require reviewed expectations. Preserve source origins even when message wording improves. Existing compiler behavior is evidence, not an excuse to reproduce a confirmed bug; record discrepancies in the appropriate bugs pad.

Performance proposal: no more than 5% median cold compile-time or peak-memory regression on representative workloads, with repeated isolated runs and raw results retained; aim for at least 2x frontend speed and half frontend peak memory. Measure tiny files, many modules, generic-heavy code, metaprograms, backend-heavy programs and self-compilation separately. Generated program speed must also remain within measured noise for the same backend/options. These are proposed gates, not observed results.

Largest risks: phase semantics hidden in current control flow; a generic rule engine introducing allocation/search costs; language proliferation; duplicated bootstrap implementations; source reductions overwhelmed by machinery; caches retaining whole compiler generations. Address them with the vertical slice, explicit execution plans, source accounting, regeneration checks and repeated-edit memory tests.

The immediate implementation task is milestone 1 followed by the smallest end-to-end typing slice. Do not begin by copying all 81,525 frontend lines into a new notation. The architectural question to answer first is whether a handful of semantic rules can generate correct, fast checking and lowering while also serving the language compilers themselves.

## Implementation checkpoint: schema keys

The seed now derives row storage, constructor readers, concrete type judgments, scalar CIR lowering, and unary function program compilation. Record fields annotated `:key` derive typed unique indexes with duplicate provenance. Function registration consumes this shared mechanism; a separate multi-key record client checks growth and identity behavior. This establishes part of binding/index generation, not module semantics.

Milestone 2 remains incomplete: Coil surface syntax, the independent language with different binding semantics, a language-toolchain component expressed in the DSLs, and early metaprogramming are still required. Program phase implementations still live in Coil fragments, but their schedule now comes from artifact-prerequisite contracts also used by the seed language compiler. Local lexical bindings end at shared global indexes, and global CIR symbols are created at use sites. Schema-checked source patterns now parse a unary Coil-shaped surface directly into rows. The first reference comparison exposed a function-designator/value-category mismatch, retained as an explicit fixture and open gap. Next, make expression categories part of the judgment language, replace opaque phase representation labels with typed owned artifacts, and extend transform support toward the required reader and introduced-definition experiments. Finite DAG scheduling alone cannot express staged expansion fixpoints. Do not broaden the phase implementations into another handwritten frontend.

`python3 tools/count-rewrite.py` records hashed working-tree inventories for seed/runtime, retained authored backend, generated backend, tests, and tools. Physical lines and bytes are reported separately. This inventory does not yet establish the code-only count, total bootstrap dependency size, or matched-workload performance improvement required by the final gates.
