# Compatibility ledger

Full compatibility for every surface below remains **unimplemented**. The seed currently demonstrates constructor readers, concrete typing judgments, scalar native lowering, and unary Int-to-Int function programs; these fixtures do not establish Coil compatibility. Existing tests are intended evidence, not evidence the rewrite passes. Reference revision: b7a54594b42820c24c4b4cce0d9348f160bdd38e in ../coil. The reference harness reports failures without necessarily returning failure: inspect per-step outcomes, refusals, and coverage before accepting a gate.

| Required surface | Reference evidence | Rewrite acceptance |
|---|---|---|
| Types, traits, generics | tests/corpus/types_traits.coil; tests/diag | Accept/reject, typed elaboration, executable output |
| Sums and patterns | tests/corpus/sums_match.coil | Exhaustiveness, layout and runtime behavior |
| Ownership, memory | tests/corpus/ownership.coil, memory.coil; safety lanes | Lifetime diagnostics and runtime checks |
| Numerics and machine operations | numerics.coil, machine_code.coil; tests/simd | Width, NaN, SIMD, traps and refusal behavior per backend |
| Control and collections | control_collections.coil | Evaluation order, divergence and command arguments |
| Readers | tests/readers; scripts/tests/fast/readers.sh | Source and artifact providers, guest locations |
| Expansion and compile-time execution | comptime.coil; tests/meta; meta-interp lane | Native/interpreted behavior, hygiene and phase ordering |
| Modules and projects | tests/projects; scripts/tests/fast/projects.sh | Package/workspace lookup, profiles, prebuilt units |
| Native backend | scripts/tests/declarative.py; corpus native lanes | Regeneration, rule tests, random programs, both targets |
| LLVM | corpus llvm/opt3; pipeline-differential.py | Runtime equivalence and supported inline IR |
| Wasm | tests/wasm; comprehensive wasm/self-host | wasm32/64 and hosted compiler |
| C ABI | tests/cabi; scripts/tests/c-abi.py | Both directions, aggregate boundaries and aliases |
| JIT and REPL | tests/jit; comprehensive installed/jit; repl-growth.py | Session semantics, retirement, same-signature REPL policy |
| Artifacts and installation | installed/*, generated/modules, install-pairing | Compatible identities, SDK, prefix discovery and tools |
| Debugging and object files | fast cli/debuginfo, cli/objects; x64/host | Source breakpoints, values, relocations and symbols |
| CLI and developer tools | scripts/tests/fast/cli.sh; examples/* | Exit codes, stdout/stderr, formatting, docs, lint, tests |
| Distribution and bootstrap | comprehensive build/full, bootstrap-imports | Deterministic self-host fixpoint and clean bootstrap |
| External programs | Select and pin coil-experiments and other actual clients | Build/run contracts; selection still pending |
| Performance | New isolated repeated measurement suite, pending | Cold/warm timing, process-tree RSS, size, edit retention |

Every row requires a concrete test manifest as implementation begins. The CLI help has additional subcommands and flags; milestone 1 must enumerate them rather than treating this coarse table as exhaustive. Existing regression suites alone do not prove all compatibility.

## Baseline reproduction

Run `python3 tools/inventory.py ../coil --revision b7a54594b42820c24c4b4cce0d9348f160bdd38e --output evidence/coil-source-inventory.json`.

The inventory reads Git blobs, so local edits cannot change the measurement. Every file includes its blob ID and SHA-256. Physical lines include comments and blanks. Generated backend and guide output are separate, the partially generated manifest is marked mixed, and the remaining compiler category still needs a generated-region audit. All text under scripts/tests/docs is inventoried for traceability but is not counted as production authored code.

Next baseline work: classify production source and embedded generated regions precisely, capture installed compiler identity and dependency versions, pin representative workloads, measure serial cold/warm executions and process-tree memory, then map expansion transitions and the typed-to-CIR interface. No timing or authored-size improvement is claimed yet.

## Initial measurements

`tools/measure.py` records serial runs with executable SHA-256, source revision/status, complete output, timeout and exit status. Example: `python3 tools/measure.py --cwd ../coil --output evidence/baseline-types-check.json -- coil check tests/corpus/types_traits.coil`.

The installed compiler identifies itself as `coil 0.1.0 (commit de1f0fdeb823, 2026-11-15)` and uses `/Users/jimmyhmiller/.cargo/lib/coil/stdlib`. This differs from the pinned source-inventory revision. Current measurements are exploratory and cannot serve as the final matched-revision baseline. RSS is sampled process-group sum, not exact peak physical memory; OS caches are not flushed. A finalized baseline must also pin/hash the installed stdlib and relevant environment/settings.

The initial source trace is in contracts/phases-and-backend.md. Pending contracts there are explicit implementation prerequisites.

## Surface syntax checkpoint

Schema-driven patterns now parse unary i64 `defn`, integer/boolean literals, symbols, calls, single-binding `let`, `if`, and binary `+` directly into generated rows with original source spans. `tests/surface-program.coil.in` is executed by both the rewrite and installed Coil as an exploratory comparison. It does not establish the full language or a matched-revision baseline.

The discovered bare-function discrepancy is now a rejection regression in `tests/surface-function-value-invalid.coil.in`: both implementations reject binding a function designator as a value. Explicit `fnptr-of` and the resulting pointer call are exercised by the shared legal-source fixture. This closes that observed mismatch within the unary subset. General function-pointer signatures, calling conventions, generic functions, references, closures, and real macro/name resolution remain unimplemented.


## Independent transformation storage checkpoint

Generated readers and representation maps now own interned Text and compact source spans. Target Stores retain copied source documents and transformation traces after input teardown. The native fixture poisons and frees its source arena before core checking and execution; a separate same-schema fixture checks recursive reference copying into offset target IDs, malloc-backed teardown, and structured source errors.

This establishes the lifetime boundary for the current context-free normalization subset. It does not yet satisfy imported custom-reader compatibility, expansion ancestry, introduced declarations, effects, or statically checked phase ownership. No replacement or performance gate is claimed.
