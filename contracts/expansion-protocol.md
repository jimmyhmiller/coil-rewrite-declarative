# Expansion protocols to preserve

This trace inspects Coil revision `3eb10b3aeea76182f6305eef80dd2a8b57dd76ca`, with a clean reference worktree. It refines the earlier backend-pinned trace; it does not update the vendored backend. Symbol names below locate the implementation without treating file line numbers as stable contracts.

`evidence/expansion-reference.json` records selected executed reference cases, input hashes, compiler identity, exit statuses, assertions and raw-output hashes. These cases currently run only on the installed reference compiler. The rewrite does not yet implement the protocols described here.

## Distinct execution policies

| Protocol | Input and model | Advancement | Completion and next consumer |
|---|---|---|---|
| Reader providers | Source plus reader context; providers bootstrap through the default reader and execute for the host | Returned forms enter loading; imported guest modules can invoke configured readers | Reader output and necessary semantic context survive until their consumers finish |
| Before-expand transforms | Authored module forms; no current-compilation checked model, though a live session can expose the already accepted parent program | Run registered transforms in order; split stage declarations; compile/install cumulative stage definitions; expand marked requests; resume transforms on returned guest forms | Stable transformed forms proceed through declaration rebuilding and ordinary expansion |
| Macro tower | Reachable compile-time definitions and pending macro calls | Compile available definitions, expand requests, discover newly available definitions/imports and restart when needed | No unresolved expansion work; later checks are authoritative |
| After-expand transforms | Expanded program | One pass through registered transforms; rebuild transformed declarations | Output does not re-enter macro expansion; ordinary resolution/checking validates it |
| Default semantic transforms | Expanded forms plus a provisional semantic model | Run once-only registrations once, then repeat ordinary semantic transforms with refreshed provisional models | Stable forms proceed to authoritative strict resolution, semantic maps, affine validation and drop elaboration |

Source anchors: `frontend/expander.coil` functions `run-before-expand`, `run-after-expand`, `expand-stage3-except-mode`, `run-transform-fixpoint`, `install-transform-model!`, `try-resolve-check`, `run-transformers`, and `run-transforms-and-check`; `pipeline.coil` functions `run-prepared-reader` and `source-readers-build-native!`.

The rewrite's finite phase DAG cannot encode these policies by adding a back edge: its cycle rejection is correct for single-assignment artifacts. Expansion needs explicit repeated generations, retained capabilities and dependency discovery. A single generic “repeat every pass until unchanged” policy would rerun one-shot transforms, offer the wrong semantic model, and expand output that the reference deliberately leaves for strict checking.

## Cumulative stage declarations and resumption

`run-before-expand` uses `split-stage-declarations!` to separate runtime forms from stage declarations. It retains cumulative stage forms and definition names, rejects a definition introduced more than once, compiles the cumulative phase program for the host, installs new signatures, and expands marked requests against that phase context. Later increments can call earlier helpers. Stage definitions stay outside the runtime program.

The `staged_chain` fixture proves a concrete dependency:

1. A before-expand dialect sees `(chain-a E)`, introduces an entry and helper, and requests that entry.
2. Native compile-time execution returns `(chain-b E)`, still guest syntax.
3. The resumed dialect introduces another entry that calls the earlier helper.
4. Its request yields the runtime result `42`.

The reference runner builds and executes the fixture. It also inspects the successful artifact with `nm` and `strings`, first requiring a real `_main` symbol, then checking that `chain-a-entry`, `chain-b-entry` and `chain-second` are absent. Failed compilation or failed inventory commands cannot establish absence.

`docs/design/STAGED_METACOMPILATION.md` documents compilation-scoped marker routing and outermost-first request expansion. Those additional requirements are source/design evidence here; the selected runner does not yet independently cover cross-module marker routing, duplicate stage definitions or every request-order interaction.

Stage compilation currently uses durable storage because engine images share mono/interpreter structures with checked graphs. A replacement may improve ownership, but cannot free a stage's dependencies merely because its own invocation ended. Current successful cumulative behavior is the compatibility requirement; copying the allocation strategy is not.

## Declarations and imports remain authoritative

A before-expand transform returns the authoritative module-form list and can add/remove imports and exports. `rebuild-transformed-declarations!` and `rebuild-top-level!` rebuild loader bookkeeping, including imports/exports nested in top-level `do` bundles. Source loading can be memoized while importer-specific aliases, `:use` and re-export relationships are rebuilt.

`transforms_test.coil` exercises a transform that emits a definition and an import needed by the program, alongside an identity transform. Its expected runtime exit is `42`. `early_macro.coil` proves another ordering constraint: an early macro introduces functions that a later macro needs before it can compile. Its stdout is `9` both with and without library-state reuse.

The current rewrite's declaration sequence maps introduce functions in a single normalization pass. That does not satisfy either dynamic dependency case above.

## Model availability and strict validation

`run-before-expand` clears the current semantic model. In a stateful compilation it may expose the already accepted parent program; it must not claim the in-progress compilation is checked.

`install-transform-model!` attempts ordinary resolution/type synthesis. It clears unavailable models and marks available partial models with diagnostics. `try-resolve-check` deliberately does not perform final affine validation/drop elaboration: ownership transforms may need to rewrite a program containing repeated affine uses first. `run-transforms-and-check` eventually invokes `strict-resolve-check` on the final forms.

After-expand and semantic transform outputs do not re-enter macro expansion. `semantic-transform-output-diag` diagnoses non-core top-level forms for semantic transforms and explains the before-expand alternative. These are source-observed boundaries; the new reference runner does not yet exercise model partiality, affine elaboration or post-expansion diagnostic cases.

## Equality, limits and diagnostics

`forms-equal` compares tagged forms through `sexp-eq`; `meta/metastate.coil` compares syntax tags and values recursively, treating a list view as its represented list. This comparison does not inspect hygiene module/scope fields. Separately, `source-syntax-equal?` checks hygiene identity when deciding whether previously normalized source can be reused. These predicates serve different purposes and must not be replaced with one unexamined equality operation.

The implementation's guard conditions are part of the trace, not newly proposed limits:

- Default semantic transforms test equality before the `iters >= 16` nonconvergence guard.
- Before-expand tests equality first, then applies `iters >= 16` when that round made no stage progress, and the wider `iters >= 64` guard for continued staging.
- The macro-tower helper `stage3-max-rounds` uses `min(64 + number-of-subforms, 4096)`.

Do not infer an invocation count merely from the diagnostic's phrase “16 rounds”: counters start at zero and the equality test precedes the guard. None of these bounds permits successful truncation. Boundary-count and nonconvergence fixtures remain to be captured before implementing equivalent policies.

## Reader lifetime and target separation

The project reader fixture imports `.json`, `.guest` and `.kv` modules and exits `48`. With tracing, it reports `reader.unit.released 1`: its non-reflecting provider compilation is released after producing the reader engine. The same project checks for `wasm32-unknown-unknown`, establishing that host-executed readers can serve a non-host target.

The reflecting reader fixture inspects a provider-side struct and combines its field count with guest source; it exits `7` and reports `reader.unit.kept 1`. `source-readers-build-native!` saves the checked program, resolution state and semantic maps for such readers. This is a retained semantic capability, not merely a code address.

Prepared readers return forms with source and definition-module context. The rewrite must define ownership of returned forms and retained reflection state before reusing or releasing a provider. The runner checks both retention branches through existing trace events, not with a new independent allocator audit. Provider-artifact isolation and generated-unit ownership remain separate required cases.

## Next implementation slice

Build the expansion vocabulary around observable transitions: an authored generation, introduced stage declarations, installed phase entries, pending requests, returned syntax and a resumed generation. Keep stage-only declarations separate from runtime declarations. Name introduction must retain Coil's intended semantics; do not insert automatic alpha-renaming as a substitute for its Code/hygiene protocol.

The first executable slice must introduce a helper, execute an entry that returns guest syntax, resume the language, then execute a later entry using the earlier helper. Its runtime result and absence of stage helpers should match the captured staged-chain contract. Retained Code operations and semantic context must have explicit ownership. Unsupported compiler introspection must be rejected rather than answered by a reduced or fabricated model.

Full reader/transform APIs, imports, negative diagnostics, phase limits, semantic-model invalidation, effects, persistent artifacts and session behavior remain outside this initial slice. These are outstanding compatibility requirements, not optional features.

Reproduce the selected reference evidence on the Mac:

```sh
python3 tools/capture-expansion-reference.py --reference ../coil --compiler coil
```

Raw outputs are retained under `build/expansion-reference/`; the committed JSON stores excerpts and hashes. Elapsed times are observations of one run, not a benchmark or a rewrite performance comparison. The installed compiler and checked-out reference inputs are identified separately; matching revision labels alone do not prove a hermetic bootstrap.


An owned reader-syntax representation now exists in `languages/code.schema` / `rewrite.code`. It preserves raw scalar kinds and floating-point bits, container structure, source origins and opaque hygiene/context metadata independently of the temporary reader arena. It does not yet provide the full Code operations, scoped identity registry, native handle transport or invocation context needed by the staged slice above. Those boundaries must be implemented explicitly before phase entries can exchange syntax values.
