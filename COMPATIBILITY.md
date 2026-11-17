# Compatibility ledger

All rewrite capabilities below are **unimplemented**. Existing tests are intended evidence, not evidence the rewrite passes. Reference revision: b7a54594b42820c24c4b4cce0d9348f160bdd38e in ../coil. The reference harness reports failures without necessarily returning failure: inspect per-step outcomes, refusals, and coverage before accepting a gate.

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
