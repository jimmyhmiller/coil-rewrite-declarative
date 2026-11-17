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

Do not infer an invocation count merely from the diagnostic's phrase “16 rounds”: counters start at zero and the equality test precedes the guard. None of these bounds permits successful truncation. Selected before-expand, semantic and after-expand boundary probes are now captured below. Macro-tower and once-only/model-availability boundaries remain to be covered.

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

## Rewrite mechanism evidence

The rewrite now has invocation-owned native handles, structural promotion, import into fresh invocations, and a temporary projection back into its bootstrap grammar API. Syntax transport retains origin/transport flags and reader-node identity as well as scope/module/context metadata. A program's explicit `(cumulative)` policy generates checked declaration history; successful extensions compile a fresh image of the full prefix, and failed checks leave history unchanged.

`tests/staged-chain.coil.in`, run by `tools/check-lowering.py`, exercises two phase increments. The first introduces an entry/helper and selects a nested `chain-b` template. The driver observes that guest form, introduces a later entry using the earlier helper, then promotes the returned runtime definition into a separate syntax store. The runtime grammar consumes it and native execution returns 42. Each invocation is closed before its result is consumed. The runtime image's names/definitions contain only its entry; this is not a serialized-artifact absence proof.

This is rewrite mechanism evidence, not reproduction of the reference's original `staged_chain` source. Request discovery and the resumption decision remain fixture code; returned syntax is selected from authored templates rather than constructed by general Code operations. Production language-declared expansion transitions, marker routing, reference limit policies, imports, semantic capabilities and full phase/runtime artifact isolation remain required.

The first generated protocol driver replaced the staged fixture's handwritten ordering loop; the owned-generation adapter below supersedes that fixture integration. `languages/staging.protocol` declares route/install/invoke/resume transitions and a finite request budget; `languages/protocol.schema` supplies the compiler's grammar and key indexes. This is control-mechanism evidence. The fixture's request budget counts transitions into install, while the reference guards rounds after equality and distinguishes stage progress. They are different policies. Do not substitute this bound for the reference limits; capture exact boundary behavior and express that accounting explicitly in subsequent expansion rules.


## Executed round boundaries and declared guard model

`tools/capture-expansion-boundaries.py` records 13 executable reference probes in `evidence/expansion-boundaries.json`. It identifies the installed compiler by binary hash and reported revision, and reads the expander blob from that exact Git revision rather than assuming the reference checkout HEAD matches. Every successful compile executes its output and checks the rewritten global's value. Failed cases require the actual limit diagnostic and a fresh missing output artifact. Raw inputs and logs remain under `build/expansion-boundaries/`; hashes, call sequences and module-projection equality are recorded in JSON. Compiler bytes are checked again after the run.

The before-expand probes establish:

| Rewrites and progress | Transform calls | Result |
|---|---:|---|
| 16 plain changes, then equality | 17 | success |
| 17 plain changes requested | 17 | 16-round diagnostic |
| 64 changes with new stage declarations, then equality | 65 | success |
| 65 such staged changes requested | 65 | 64-round diagnostic |
| First 16 changes staged, next change plain | 17 | 16-round diagnostic |
| First 16 changes plain, change 17 staged, then equality | 18 | success |
| Same sequence followed by another plain change | 18 | 16-round diagnostic |

These cases distinguish one monotonically increasing accepted-round counter from separate plain/staged counters or a counter reset after staging. Equality wins even when the counter is at a limit. Stage progress means a nonempty batch of newly split stage declarations in that round; it is not a count of native entry calls. The semantic transform probes independently accept 16 changes plus an equality call and reject another change. The after-expand probe runs once despite returning changed forms.

Two probes with an unchanged scalar counter produce calls `[0, 0]`: an identity result and a stage-only result. In the identity case, the module projection compares equal on both calls, while `COIL_MTRACE=rounds` reports whole-form `changed=yes`, then `changed=no`. Source reconstruction groups forms by module, but the evidence establishes only the predicate distinction, not a general normalization cost. The trace's printed `round 0` is the transformer index passed by `run-transformers`, not the loop iteration count. Do not infer loop counts from that label or use module-projection equality as the guard's whole-form equality.

`languages/before_expand.protocol` now declares the accounting kernel. `Equal` completes immediately; `ChangedPlain` spends the shared `rounds` budget under a ceiling of 16; `ChangedStage` spends the same budget under its overall limit of 64. Only a successful spending edge enters the `accept` handler. The round handler computes candidate output and classifies equality/progress; the accept handler publishes that candidate. Handler errors stop the protocol.

`tools/check-expansion-policy.py` replays the eight changing-round before-expand traces through this generated driver in debug/debug-checks/release. `evidence/before-policy-replay.json` links the captured reference evidence, language/model output, fixture, scripts and compiler by hashes. This checks the accounting kernel. It does not run those source files through the rewritten frontend, reproduce initial form normalization, or implement request discovery, Code construction, semantic models and strict checking. The simpler request-count protocol remains covered by standalone mechanism tests.

Reproduce with:

```sh
python3 tools/capture-expansion-boundaries.py --reference ../coil --compiler coil
python3 tools/check-expansion-policy.py
```

## Owned generation adaptation

`rewrite.rounds` now supplies ownership and event classification for the declared before-expand guard. `FormSequence` derives whole-root comparison from the syntax schema; it preserves order and shares comparison work across roots. A typed round effect writes fresh candidate runtime forms and newly introduced stage forms. Equality retains the existing generation, as reference `run-before-expand` leaves `cur` unchanged when `forms-equal` succeeds. Changed output is published only by the guard's accepted transition.

Stage compilation and request execution are effects before equality/guard classification in the reference. The adapter therefore does not promise to roll those effects back when a round is equal or exhausted. It preserves accepted syntax and keeps rejected candidate storage available until reuse or close. Effects must validate and independently retain any stage data needed after the candidate is released.

The native chain fixture now uses this owned runner rather than the request-budget loop: two native increments, two accepted generations, one equality round, and runtime entry returning 42. Its declaration/guest adapters remain handwritten fixture logic. `tests/rounds.coil` separately exercises whole-root changes and the recorded mixed 16/64 patterns with owned syntax. The original reference source is still not compiled by the rewrite; module tags, initial normalization, production marker routing and semantic APIs remain outstanding.

## Stage datum identity and context

The inspected `stage-datum-sexp` does not clear every metadata field on every node. Symbols receive hygiene scope 0, no definition module, origin 5 and a fresh node ID. Lists and vectors recursively copy their children and refresh node ID while preserving their own context fields. Other leaves remain unchanged. Quote does not shield this structural isolation operation; quote shielding belongs to request discovery. Recursive copying refreshes each occurrence of a shared symbol/container separately.

`context-policy stage-datum` now declares those field changes in the syntax schema. `code/stage-datum!` applies generated occurrence-sensitive structure copying and metadata edits, using the bootstrap reader identity supply. The default promotion path remains sharing-preserving. Tests cover shared sequence joins, occurrence identities, unchanged fields, source independence and cycle recovery. This is source-grounded component evidence, not execution of the reference stage source through the rewrite. Stage body extraction must still preserve loader module tags and use this isolation path before compilation.

## Module-tagged stage partition

`rewrite.stage/split` now implements the partition boundary using the schema's generated `StageDeclaration` view. Matching malformed declarations return a located typed error; unrelated top-level forms remain runtime forms. Stage children inherit their enclosing declaration's optional module tag, are copied with the stage-datum context policy, and keep source documents. Marker names are deduplicated across modules in first-seen order, including declarations with empty bodies. Prior markers are borrowed during splitting and copied into the result; a failed split publishes no partial batch or registry update.

Views borrow captures rather than constructing another AST. A single projection cache serves the batch; separate generated transform states preserve runtime sharing and stage occurrence identity. The native cumulative chain fixture now compiles stage bodies emitted by this partitioner, retains marker history outside candidate lifetime and still produces runtime 42. Phase source selection and request routing remain fixture work. In particular, this does not yet implement the reference's quote shielding, declaration-prefix exclusions, entry lookup or outermost-first request execution.

## Declared request selection and discovery

`walk stage-requests` encodes quote opacity and the reference's signature-prefix policy (4 children normally, 6 with `:cc` and its value). Its prefix rule applies to list/vector containers; quote opacity applies only to lists. `StageRequest` and `StageEntry` views encode the request and symbol/string entry shapes. The production inspector gives quote shielding precedence, then declared-marker membership, then ordinary child traversal. Entry qualification uses the enclosing tagged form's module, not identifier hygiene metadata; already dotted names pass through lookup unchanged.

The explicit-worklist finder returns the first left-to-right outer request without visiting its arguments. Unit fixtures exercise unavailable nested calls behind a valid outer request, signature-shaped marker data, cross-module entry selection and rejection of C strings as entry names. The native fixture now validates a marked call and resolves its selected name to an image entry. This is request-boundary evidence, not a complete request expander: it does not yet execute/rebuild arbitrary enclosing syntax, re-enter returned results, enforce the 100,000-call budget or implement full Code argument signatures.
