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
