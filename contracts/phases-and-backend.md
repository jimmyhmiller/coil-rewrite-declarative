# Phase and backend contracts: initial trace

Inspected reference: b7a54594b42820c24c4b4cce0d9348f160bdd38e. This records source-observed contracts; it is not yet a complete executable specification.

## Frontend

In src/compiler/pipeline.coil, run-pipeline-attempt selects initial-read, initial-read-on-library-state, or a prepared reader. The prepared reader executes with its retained session allocator and semantic-map snapshot; returned forms are copied into frontend storage. Consequently reader output cannot retain pointers into a released temporary arena.

frontend-load! and frontend-load-on-library-state! load forms and imports. Entry-file relative imports resolve against the entry's directory, not process cwd. Library reuse is conditional: library-state-must-restart? recognizes registrations that read all modules and requests a fresh compilation. Missing such a registration until expansion is a diagnostic, not permission to proceed with incomplete inputs.

frontend-expand! calls expand-stage3-except with staged exclusions. run-transforms-and-check then performs transform fixpoints, authoritative resolution and type checking. A non-retained compilation marks its semantic workspace final_strict. generated-interfaces-unchanged? forbids transforms from changing read-only generated-unit interfaces after partitioning.

Semantic checkers consume the authoritative checked program. Compile-time-only code is removed subject to root validity. monomorphize receives staged-instances, then sort-mono-program normalizes order. Retained sessions record resulting monomorphs. Source registry information survives for DWARF.

Required tests before replacing this protocol: a custom reader with imported definitions; reader-owned data surviving until checking; relative imports with a different cwd; a transform that introduces a declaration needed by a later round; whole-library transform registration; generated-unit interface mutation rejection; compile-time-only root rejection; deterministic specialization; retained-session continuation. Locate and extend existing fixtures before inventing replacements. The precise fixpoint algorithm and phase APIs still need tracing inside expander/metaengine.

## Native backend

src/compiler/declarative/adapter/cir.coil exposes the retained boundary over native.cir/Func and native.asm/Asm. work-create/work-free! scope reusable per-target compilation storage. compile! accepts a function, assembler, symbol, optimization level and work object. compile-debug! additionally receives source rows, marks, frame objects and tracked locations.

The optimized module path uses module-create, module-add!, module-count!, compile-wave!, references!, place! and module-free!. The target selector is explicit and both machines exist in the compiler. settings-key belongs in artifact identity. Calling compile! alone does not provide object emission, symbol ownership, ABI classification or debug metadata; those must be supplied by the new lowering/module layer.

src/compiler/backend/codegen_native.coil currently provides that layer together with native_module.coil. It lowers Program functions to CIR and builds Mach-O/ELF objects. Do not retain its frontend Program dependency as a permanent bridge: the new lowering must construct CIR from the new typed representation. Preserve the backend's authored sources, generated snapshot and provenance at one revision.

Before the first native slice: inspect Func construction and block/phi contracts, assembler symbol/relocation ownership, integer/bool representation, function result ABI, and object finalization. The first fixture should include a branch merge and a direct call so a constant-return program cannot conceal missing control flow or ABI work.

## Executable prototype contracts

`seed/phase.coil` now validates and schedules finite single-assignment artifact plans. `seed/program.coil` declares `Declarations -> GlobalEnvironment -> CheckedProgram -> NativeImage`; `seed/main.coil` declares the table/API generation dependencies of the language toolchain itself. The latter has independent producers joining before program generation. Both consume the same planner.

These are executable prototype boundaries, not a replacement specification for the original frontend protocol traced above. Nominal representation agreement is checked; handler implementations and ownership remain trusted. In particular, staged expansion cannot be treated as a cycle in this static graph and simply rejected: its intentional fixpoints need a distinct protocol with convergence and invalidation semantics. Reader lifetime and introduced-definition tests remain required before extending this mechanism to metaprograms.

## Typed representation maps

`seed/transform.coil` now derives context-free schema-to-schema traversals. Generated APIs have nominal source/target ID types, memoize by source ID, and attach source/rule provenance to constructed nodes. The fixture has separate surface/core expression schemas and corresponding declaration schemas, with the declaration map invoking the expression map. Core checking/lowering cannot consume source declaration IDs.

Maps now borrow distinct input and target Stores. Generated readers intern Text and store compact origins; transformations copy all references, intern target Text, and retain source documents and traces in the target. Same-schema maps are supported. Input reader/store arenas can be destroyed before checking and executing target programs, as the native fixture verifies. Source identities must name identical immutable documents; missing documents, invalid spans, and conflicting identities are structured errors. Row counts are checked, but public-array mutation is not prevented and allocator lifetimes remain caller-managed. Thus these maps establish independent target storage, not a static proof of phase ownership or transactional publication. Trace entries retain source node numbers and rule spans but do not yet preserve multi-stage ancestry or DSL rule source documents. They do not replace expansion worklists, introduced-declaration discovery, binding-aware substitution, or effect contracts.


## Declaration sequence transitions

A map target may now be `(many Schema)`. Its `items` terms construct zero or more target nodes and splice results of declared sequence maps. Single and many cardinalities are distinct checked signatures. Results are nominal handles into immutable target-owned sequence segments; joins share children, preserve multiplicity and order, and check length capacity. The program boundary materializes a function-ID list before ordinary indexing, checking and lowering. Introduced name collisions remain ordinary duplicate-definition errors.

The native fixture introduces an alias plus its implementation from one source declaration. This proves that introduced declarations reach normal program indexing and native execution in one normalization pass. It does not prove the original frontend's dynamic introduction/fixpoint protocol: no later expansion round discovers dependencies, registers transforms, or runs compile-time code yet. Binding rules for generated declarations and full provenance ancestry remain open.


Schema sequence fields now store nominal handles rather than arrays embedded in rows. Constructor vectors and final surface `rest` captures produce them. Sequence-to-sequence transformation preserves shared segments through one generic traversal, using explicit single-result versus sequence-result element maps. Mapping has its own segment memo and structured cycle/input-growth errors. The module fixture crosses source-program and core-program schemas with declaration/function sequence fields before materialization at the existing program boundary.

This makes the collection boundary executable. It does not make the program phase contract a checked ownership/effect protocol, nor does it define simultaneous bindings or a staged expansion loop.


## Shared lexical topology

Binding declarations now specify each constructor's reference field and names visible in individual children. The seed validates that model once and supplies it to judgment and lowering generation. Judgment premises provide type payloads; lowering provides evaluated value payloads. Both clients check declared scope/reference coverage and payload count. A two-name fixture proves outer-scope value evaluation, body visibility, ordered shadowing and isolation; changing only its declared name order changes both type inference and native execution.

Typing and lowering still perform their own Text lookup, and the model does not prove that arbitrary client rules assign equivalent payloads. A generated resolver now produces result-local declaration identities separately; semantic clients do not yet consume them. Namespace/import resolution, recursive groups and binding-aware transforms remain unimplemented. Program-global signature/index construction remains outside this lexical model.


## Resolution artifact

Schema edges and shared binding topology now derive occurrence-aware resolution. A result records each visited row's lexical occurrence and each reference's declaration identity. A repeated DAG row may have different targets in different occurrences; a binder field has one identity per owning occurrence, shared across its declared child scopes. Ordered scope installation preserves shadowing. Globals are explicitly supplied names; the resolver does not derive modules or signatures.

Resolution borrows names from immutable input storage, releases partial results on failure, and reports invalid references, cycles, unknown names and duplicate globals. The next binding-aware transformation boundary must explicitly transport these identities or report changes to binding relationships. Re-running name lookup after rewriting is not proof of capture avoidance. Existing context-free maps remain separate and make no such guarantee. Identity transport, fresh introduced declarations and semantic-client integration remain required.


Alpha copying is the first transformation that consumes resolution identities. It preserves occurrence shape, assigns names to declarations, and rewrites reference fields by target IDs, returning source-occurrence to target-row correspondence. It copies every occurrence into target-owned storage. Successful target re-resolution must preserve reference-to-declaration relationships and declaration owner/field coordinates; the tests check these relations explicitly. This does not establish the same guarantee for general maps or for combining independently renamed roots. Source documents and origins survive input release, but failure publication remains caller-managed and partial target allocations may remain.


The newer [expansion protocol trace](expansion-protocol.md) distinguishes before-expand staging, macro-tower progress, one-shot after-expand transforms, semantic fixpoints and reader lifetime capabilities. Its selected fixtures are executed only by the reference compiler and recorded separately from rewrite parity.


## Explicit host linkage

The initial program language now declares unary i64 host signatures. The generated compiler registers these globals before checking any body; callback addresses enter only when loading an image. `native/load-image-with` validates name bindings and symbol-table shape before executable allocation, with no process-global symbol lookup. Callback lifetimes remain the embedding caller's responsibility. Distinct live images can bind one name to different addresses. This supplies a narrow native-runtime boundary for staged operations; it does not supply syntax values, semantic-model state or phase scheduling.
