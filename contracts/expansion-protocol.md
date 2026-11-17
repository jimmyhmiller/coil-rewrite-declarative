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


An owned reader-syntax representation now exists in `compiler/syntax/code.schema` / `rewrite.code`. It preserves raw scalar kinds and floating-point bits, container structure, source origins and opaque hygiene/context metadata independently of the temporary reader arena. It does not yet provide the full Code operations, scoped identity registry, native handle transport or invocation context needed by the staged slice above. Those boundaries must be implemented explicitly before phase entries can exchange syntax values.

## Rewrite mechanism evidence

The rewrite now has invocation-owned native handles, structural promotion, import into fresh invocations, and a temporary projection back into its bootstrap grammar API. Syntax transport retains origin/transport flags and reader-node identity as well as scope/module/context metadata. A program's explicit `(cumulative)` policy generates checked declaration history; successful extensions compile a fresh image of the full prefix, and failed checks leave history unchanged.

`tests/staged-chain.coil.in`, run by `tools/check-lowering.py`, exercises two phase increments. The first introduces an entry/helper and selects a nested `chain-b` template. The driver observes that guest form, introduces a later entry using the earlier helper, then promotes the returned runtime definition into a separate syntax store. The runtime grammar consumes it and native execution returns 42. Each invocation is closed before its result is consumed. The runtime image's names/definitions contain only its entry; this is not a serialized-artifact absence proof.

This is rewrite mechanism evidence, not reproduction of the reference's original `staged_chain` source. Request discovery and the resumption decision remain fixture code; returned syntax is selected from authored templates rather than constructed by general Code operations. Production language-declared expansion transitions, marker routing, reference limit policies, imports, semantic capabilities and full phase/runtime artifact isolation remain required.

The first generated protocol driver replaced the staged fixture's handwritten ordering loop; the owned-generation adapter below supersedes that fixture integration. `compiler/expansion/staging.protocol` declares route/install/invoke/resume transitions and a finite request budget; `languages/protocol.schema` supplies the compiler's grammar and key indexes. This is control-mechanism evidence. The fixture's request budget counts transitions into install, while the reference guards rounds after equality and distinguishes stage progress. They are different policies. Do not substitute this bound for the reference limits; capture exact boundary behavior and express that accounting explicitly in subsequent expansion rules.


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

`compiler/expansion/before_expand.protocol` now declares the accounting kernel. `Equal` completes immediately; `ChangedPlain` spends the shared `rounds` budget under a ceiling of 16; `ChangedStage` spends the same budget under its overall limit of 64. Only a successful spending edge enters the `accept` handler. The round handler computes candidate output and classifies equality/progress; the accept handler publishes that candidate. Handler errors stop the protocol.

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

## Request execution and per-root fuel

Source inspection of `expand-staged-calls` establishes that each original tagged top-level form gets a new counter. `expand-stage-markers` resolves the entry before incrementing/checking that counter, then invokes it and recursively expands the returned syntax using the same original module and counter. `traversed-sexp` preserves all container metadata while replacing only its kind/children. These observations are source evidence; the rewrite's boundary tests do not independently execute 100,000 reference native calls.

`compiler/expansion/requests.protocol` declares walk/request/invoke/returned transitions and the 100,000-call guard. `rewrite.requestexecution/run!` implements one original-root run. Its explicit task stack preserves left-to-right outermost traversal without recursively invoking the runner for returned requests. Inspection errors precede budget exhaustion. The callback borrows the raw request and appends syntax to the runner-owned workspace, returning an owned root. Returned syntax resumes under the original module tag, regardless of definition-module metadata on that syntax. No callback runs for the 100,001st valid request.

The runner copies input before executing and rejects its own workspace as input before resetting it. Busy/closed states are explicit; closing an active run fails. It retains error storage until reuse/close, and successful output can be promoted into independent storage. Callback-defined error payloads retain the callback's own lifetime contract. Callback writes must be append-only: cached reader projections require existing rows and text to remain immutable. Inspection storage is reset between calls; syntax/projections remain until run reset or close.

Tests exercise nested returned requests, quote/signature exclusions, list/vector rebuilding, preserved container context and identity, original-module lookup, unavailable entries at the ceiling, two fresh 100,000-call runs, exhaustion before invocation, callback errors, invalid returned IDs, reuse and durable promotion. The native staged chain now invokes the production runner through an image-entry callback. Its phase source selection and one-argument Code-handle ABI remain fixture restrictions.

This implements a single-root request operation. It does not yet perform the surrounding `do-produced` top-level splicing, declaration-name bookkeeping, import resolution or complete phase function checking. Projection, initial promotion and final import still traverse schema rows recursively; an iterative request stack is not a claim of stack safety for all deep syntax. Retained intermediate syntax also needs workload measurements before any memory improvement claim.

## Top-level returned-form normalization

Inspection of `splice-do-into!` and `do-produced` establishes a separate post-request operation: recursively flatten list-headed `do` bundles, preserving order; drop empty bundles; stop at every other form. It does not flatten a vector headed by `do` or a `do` inside a retained function/quote form. All resulting forms inherit the original tagged module. The number of flattened forms is determined before registration effects.

Registration is more than flattening. A newly produced derive registration executes when it joins the program and is consumed; an unchanged singleton registration passing through uses the existing registration path. Other forms pass generated declaration validation/registration (including trait names, structs and sums), add any qualified function name, and are published as tagged forms. A singleton output with an original form keeps its form identity, increments revision iff `expansion-form-equal?` differs, and clears cached shape on change. Multiple outputs receive fresh tagged identities. That equality compares scope/module/origin/flags recursively as well as datum, excluding transport context, node identity and source location. These are inspected reference requirements, not implemented registration/revision parity.

The rewrite now declares structural normalization as `(walk produced-forms (default keep) (prefix-list "do" 1))`. Generated `leaves-produced-forms` performs iterative ordered collection; `produced/normalize!` imports selected leaves with owned documents, metadata and module strings. `stagedrequests/run!` composes request execution and normalization across original tagged roots. Each original root gets fresh request fuel; nested requests in its returned bundles finish before those bundles are flattened. Failure identifies the original root and publishes no result array; callback effects and unreferenced output allocations remain.

Tests cover recursively empty and nested bundles, left-to-right order, quote/vector/function boundaries, anonymous versus named-empty modules, preserved context and node identity, source independence, a source conflict after a prior leaf imported successfully, later-root callback failure and retry. The native cumulative chain now uses the batch operation. The independent walk fixture checks a different bundle head and 25,000-level generated traversal in three configurations. None of these establishes full reader-projection stack safety, registration order effects or source-compatible macro/stage compilation.

## Revision metadata and admission order

The rewrite now declares the two metadata equivalence relations in `code.schema`: source reuse selects scope/module; revision reuse selects scope/module/origin/flags. `code/revision-equal?` combines the declared predicate with schema-derived structural comparison at every reachable pair. Tests alter each metadata field on a nested node and distinguish datum, source and revision equality. Independent record tests exercise Int/Bool/Text projections, empty selection and declaration errors without relying on syntax's record layout.

`revision/track!` implements the normalized cardinality rule: singleton outputs can reuse the original identity/revision/cache; changed singletons retain identity, increment revision and invalidate cache; multiple outputs get distinct fresh identities; empty output allocates none. New outputs without an original are fresh. It borrows normalized syntax, checks module preservation, and returns a separately owned record array. Its identity supply belongs to one compilation; exhausted identity/revision counters fail rather than wrap. That defensive boundary is not established as identical to reference integer-overflow behavior, and numeric identity allocation sequences are not claimed equal across compilers.

Batch execution now exposes `run-with!` admission between normalization and the next original root. The admission callback can register or consume normalized forms and reports a typed failure with original-root index. `run!` remains the structural path through no-op admission. Tests connect the callback to revision tracking and prove that a later original request sees prior admission, errors stop the batch, previous effects remain, and retry does not recycle allocated identities. Full `do-produced` parity still requires implementing the actual derive-registration exception, generated declaration parsing/registration and name availability; those cannot be inferred from this mechanism test. Tracking must occur against the raw flattened count before any registration is consumed.

Admission source inspection also narrows the next implementation: `defn-name-of` collects generated `defn*` names, whereas `source-defn-name-of` additionally recognizes surface `defn`. Derive arms resolve through `resolve-macro-head` with module/import/export context; simply prefixing a module name is insufficient. The current `regd-arm` scans keyword/value pairs from position 2 and keeps the last matching symbol-valued arm. An absent arm is legal, both absent are rejected, and an unresolved selected arm produces an error. These are source observations to verify with reference fixtures before adopting a grammar; they are not evidence that a stricter new parser is compatible. Generated struct/sum registration parses and qualifies declarations, while generated trait registration adds the qualified trait name to the declared-trait namespace. The admission language therefore needs real declaration and namespace data, not only head classification or callback stubs.

## Import referring as shared policy

The reference's `use-refers`, `use-local-of` and `use-drops?` distinguish three questions. Renames override selection/exclusion, source order settles overlapping forward names, and a renamed source ceases to be referred under that spelling. Reverse lookup uses the first rename of the exported source. Deliberate dropping includes excluded and renamed source names; it is not simply failed lookup. In particular, self-renames can both refer and count as deliberately dropped.

`refer-policy` now declares these roles over schema fields and generates a checked owned-index builder. `evidence/refer-reference.json` records direct execution of exact helper definitions extracted from the installed compiler's reported revision; `evidence/refer-replay.json` links those observations to generated builders using two different record layouts. The 43 policies/387 queries match in default, checked and release configurations. This is helper-level evidence: generated source import parsing, module loading and full name-resolution routes are not exercised. The input matrix intentionally includes overlapping rename rows without asserting the source parser accepts them.

Source inspection of `resolve-in-space` establishes further requirements beyond the refer edge. Bare lookup checks own declarations, then ordered use imports, then ambient core. An own non-macro declaration blocks imported/ambient macros. Macro use lookup accepts the first successful import; trait/type lookup can report ambiguity between distinct targets. Dotted names try the current module's spelling first, then fully qualified spelling; leading-dot names stay in the bare tier. Slash lookup uses import aliases, with additional own/full imported module-name routes for non-macro spaces. Export lookup checks visibility, direct/aliased declarations, then reexport edges under their refer policies, cutting off at depth 64. Ambient core obeys its effective refer selection and provider ownership. Macro heads additionally prefer their scoped lexical key and select definition-module versus use-site context. These are inspected requirements awaiting an executed route matrix and implementation, not parity established by the refer-policy tests.

## Executed export traversal contract

`tools/capture-export-reference.py --reference ../coil` extracts `space-exported`, `use-refers`, `imports-find`, `exports-check`, `decl-alias-target`, their selected data definitions, and `set-contains` from the installed compiler's reported source revision. The harness supplies fixture declaration membership, a reexport-only import record, and an alias-table accessor. The traversal, visibility and one-hop alias algorithms are the extracted code. It uses the installed AVec and text operations. The evidence records the exact compiler binary, reported revision, source/helper hashes, generated driver hash, capture-script hash and fixture inputs/outputs.

The targeted graph distinguishes unrestricted versus explicitly empty exports, direct declarations hidden by exports, aliases taking priority over same-spelled direct declarations, one-hop alias chains, direct declarations without module import records, ordered reexports, rename/exclusion/selection behavior, same-owner queries with different names, cyclic paths, and depths 0, 62, 63 and 64. Twenty-four deterministic generated acyclic graphs add varying export sets, aliases, declaration membership, overlapping renames and edge orders. Acyclic generated graphs bound the reference's un-memoized branching work; explicit cycles are tested in the targeted graph. Duplicate table keys are deliberately excluded because the rewrite snapshot requires unique keys and source normalization is not under test. Some raw refer/alias combinations may not be accepted by source import/declaration parsers.

`evidence/export-reference.json` contains 25 graphs and 2,688 queries with identical results in default, checked and release builds. `tools/check-export.py` builds the rewrite's generated name-schema snapshots, runs the production namespace/export search, and compares every answer and result count against the capture in all three configurations. Its DebugAllocator check verifies cleanup across all graphs. `evidence/export-replay.json` binds that replay to the reference capture and the implementation files used. The complete seed runner includes the replay; it does not recapture or silently bless expected answers.

This establishes export-helper parity over the recorded matrix. It does not establish source import parsing, checker namespace membership, duplicate-definition normalization, surrounding resolver routes, source-route bookkeeping, hygiene, derive admission or the full compiler. The next route matrix must distinguish macro first-hit use lookup from non-macro ambiguity, including the reference's same-import-target exception; own non-macro declarations that block macro fallback; alias versus full-module slash lookup; own-relative versus absolute dotted names; leading-dot bare names; and ambient provider ownership with effective core refer rules. Implement those policies through language declarations while keeping storage and typed callback mechanisms explicit.

## Use candidate selection

The inspected `space-use-match` algorithm compares each successful candidate with the first success, retaining both that canonical declaration and its import target. Macro lookup returns immediately and records the selected import target, referred spelling and declaration. Non-macro lookup accepts a later candidate if either its declaration equals the first declaration or its import target equals the first target. It does not replace the first witness. Consequently, the apparent pairwise agreement relation is not transitively folded: a candidate agreeing with an intermediate candidate may still conflict with the original witness.

The rewrite declares these decisions on a `Candidate` record: `first` and `(agree-any owner target)`. `namespace/used` supplies candidates from compiled use refers and the existing export query. It returns complete candidate records or both ambiguity witnesses; formatting diagnostics and publishing source-route metadata remain caller work. Targeted tests distinguish first versus later witnesses, but an executed reference use-tier matrix is still required before claiming differential parity for this operation. Raw use lists can represent combinations that the source import parser rejects eagerly, so helper-level coverage and source-program coverage must remain separate.

## Executed use-tier contract

`tools/capture-use-reference.py --reference ../coil` now extracts the exact `space-use-match`, result helpers, export traversal and refer helpers from the installed compiler's reported revision. Its fixture adapters supply declaration membership, macro-versus-nominal mode, diagnostic transport and a route recorder. Ambiguity formatting is replaced by transport of the two import owners; diagnostic text/spans are not tested. The route recorder checks the asking module, original spelling and route kind, then retains import owner, referred spelling and canonical target. A successful macro must record exactly one route; missing, ambiguous and nominal results must record none.

The capture has 25 namespace graphs and 258 ordered use lists, with 2,564 queries across both namespace modes. Targeted lists distinguish first-hit macros, nominal ambiguity, the same-declaration and same-import-owner exceptions, original-witness retention after intermediate agreements, empty selections and exclusions. Deterministic generated lists add varying refers, aliases, export restrictions and graph paths. Results comprise 478 hits, 2,054 misses and 32 ambiguities, identical in default, checked and release builds.

`tools/check-use.py` replays the capture through `namespace/compile-uses` and `namespace/used`, comparing every selected canonical target, macro candidate's owner/referred spelling/target, and ambiguous owner pair. It constructs all input rows before constructing an immutable namespace view and checks allocation cleanup across all graphs. The seed gate runs this replay without recapturing expected answers. The capture records compiler/source/helper/driver hashes and the shared export-fixture generator hash; the replay binds results to its production implementation files.

This establishes use-helper behavior over the captured matrix. The rewrite returns provenance but does not yet publish source routes. It also does not yet render reference ambiguity diagnostics or enforce source import-parser rejection of duplicate refers. Surrounding routing remains separate: bare own/use/core priority, own-function macro shadowing, slash aliases and namespace-dependent full-module lookup, own-relative versus absolute dotted lookup, leading-dot bare names, core refer restrictions/provider ownership, and scoped macro-head context. Reuse the protocol language for finite route ordering where suitable; keep candidate selection and recursive export search in their existing declarations rather than duplicating their policies in routing handlers.

Further source inspection constrains the next core/head facts. `core-contribution-owner` scans activated providers newest first. A project-root contribution is skipped for toolchain namespaces, allowing an older provider to win; this is not a single global name-to-owner map. Provider presence is total for the selected owner: failure to find its macro does not fall through to an older provider or the prelude. Provider export lookup begins at depth 1, whereas direct prelude lookup begins at 0. A missing import record defaults to referring all core names. `macro-module-of` uses definition-module context only for a positive hygiene scope; an empty definition-module string then means no module, not the caller fallback. `resolve-macro-head` tries a distinct lexical scoped spelling first, then the raw spelling in that selected module context. These are inspected requirements for subsequent executable fixtures, not claims established by the use-tier oracle.

## Scoped head implementation boundary

The production head selector now follows `macro_head.protocol`: prepare the context/spellings, try a distinct scoped spelling, and only on a miss resolve the raw spelling. Source inspection of `lexical-name` requires a fresh `$datum<node-id>$<name>` key for each negative-scope occurrence; using the syntax row's stable identity would incorrectly reuse a lexical key. Positive scopes use `$scope<scope>@<definition-module>$<name>`, while scope zero uses the raw name. Module selection uses the definition module only for positive scopes, turning an empty module into `None`; zero and negative scopes retain the caller fallback.

The selector's outcome owns any generated lexical string because the selected route's referred spelling may borrow it. The original routing API alone could not safely return that provenance after a caller-local arena was closed. Targeted tests verify a scoped import route, two live outcomes from the same constructed symbol, missing context, nonsymbol and invalid IDs, with complete cleanup. Reference macro lookup suppresses resolver errors because its macro use tier cannot be ambiguous; the rewrite propagates internal route failures for diagnosis. Executable full-route/head comparison and source-route publication remain required before broad expansion parity claims.

## Executed combined route/head contract

`tools/capture-routing-reference.py --reference ../coil` now executes exact `resolve-in-space`, `space-core-ordered`, `core-contribution-owner`, `resolve-macro-head`, `macro-module-of`, `lexical-name`, and supporting alias/use/export helpers from the installed compiler's reported revision. Explicit adapters supply declaration membership, import tables, toolchain classification, the active prelude, the provider table and diagnostic transport. Macro memoization is bypassed. The source-route recorder verifies kind 6, at most one selected route, no routes on misses/ambiguities/nominal results, and a recorded canonical target equal to the answer. Ambiguities transport owner pairs rather than reference diagnostic wording. Source parsers and the actual toolchain manifest classifier are outside this helper fixture.

`tools/route-fixtures.py` supplies twelve graphs with 1,729 outcomes, including 45 scoped-head queries. The matrix covers alias versus full-module slash lookup, export visibility versus direct dotted access, own-relative names, leading dots, empty spellings, anonymous versus named-empty modules, own-function macro shadowing, first-hit/ambiguous uses, core referring, missing prelude import records, root-provider exclusion for toolchain modules, provider total ownership, positive/zero/negative scope and absent definition-module context. A 63-edge path succeeds as a prelude lookup beginning at depth 0 and fails as the same provider lookup beginning at depth 1. Generated graphs add combinations of declaration aliases, refer policies and namespace modes.

All three reference configurations agree: 416 hits, 1,305 misses and eight ambiguities. `tools/check-routing.py` replays every result through the production facts builder, route protocol and head selector in default, checked and release builds, with allocator cleanup. For selected routes it also compares asking module, attempted spelling, import owner, referred spelling and canonical target. Head outcomes now retain the effective module and last attempted spelling explicitly; the import candidate alone could not distinguish a scoped lookup from raw fallback for later publication. The evidence records compiler/helper/source/fixture/driver identities and replay implementation hashes. Negative-scope numeric IDs are not compared across independent compiler sessions; freshness remains covered by the repeated-occurrence test.

This establishes helper-level route/head parity over the recorded matrix. It does not publish rewrite source-route records, load real module facts, format reference diagnostics, validate source import declarations, establish memo invalidation, register generated declarations/derives, or prove source-compatible expansion. Those remain required integration work. The seed gate replays committed expectations and never recaptures them implicitly.


## Source-route publication and ownership

The recorded combined route/head matrix now replays through `observedresolution`, which publishes selected provenance into `sourceroutes/Table` before returning. Every query checks the actual stored table against captured route metadata, or verifies an empty table when no route was recorded. The pure resolver remains available without recording. This validates publication per query; it does not establish full source-analysis session parity.

Inspection of `source-route-record!`, `source-route-copy!`, `source-facts-scope!`, `source-facts-start!` and `source-facts-stop!` requires disabled/module-filter guards, comparison of all three provenance fields before replacement, no write for a missing copy source, additive module scopes and fresh unrestricted sessions on start. The rewrite implements these behaviors with table-owned interned strings, schema-generated field equivalence and explicit start/stop/release. Targeted tests cover these contracts, including records surviving the release of the scoped head outcome and input stores. Copies report whether contents changed; reference helpers return zero. The private key representation is length-framed rather than the reference printable delimiter encoding. Neither difference is exposed as source-language behavior.

Only source routes are implemented here. Occurrence sites, roles, answers, types, locals, primitive observations and the other SourceFacts tables remain outside this component. Generated-form registration and loader-driven namespace updates must integrate these mechanisms without treating helper replay as complete expansion compatibility.

## Executed derive registration and pending settlement contract

`tools/capture-derive-reference.py --reference ../coil` captures exact `is-register-derive-form`, `regd-arm`, `regd-resolve`, `register-derive-form!`, and the derive registry's reset/ready/put/duplicate/settle/finish helpers from the installed compiler's reported revision. `evidence/derive-reference.json` records 31 scenarios and 82 actions, identical in default, checked and release builds. Each action retains its resolver-call trace, diagnostic and ordered registry rows. Macro and trait resolution are explicit fixture adapters, not the production resolver. The allocation owner and registry accessor are fixture state; string ownership still copies through the adapter. This oracle establishes helper behavior, not generated-form admission or namespace/signature checking.

The observed contract constrains the language design:

- Recognition requires a list with at least two items and a symbol head `register-derive`. A malformed trait operand is diagnosed only after recognition. A one-item registration-shaped list is unrecognized by this predicate.
- Arms are scanned as pairs beginning at item two. The last matching keyword with a symbol value wins. A later nonsymbol value does not erase a prior valid arm; unknown keywords, odd trailing items and nonmatching pairs are ignored. Preserve the selected syntax occurrence for hygienic lookup.
- Struct and sum arms resolve in that order. Both are attempted even if the first misses. Failed arm resolution prevents registry insertion; no selected arms is a distinct diagnostic.
- An unresolved trait creates a pending entry retaining original spelling, owner and resolved arm names. A trait-resolution error prevents insertion. Already settled canonical trait names reject duplicates.
- Settlement visits pending entries in insertion order and checks duplicates against all settled entries, including those settled earlier in the same call. It stops at the first failure without rolling back earlier settlements. Retrying only visits still-pending entries.
- Finish first performs settlement, then diagnoses the first still-pending trait. Reset clears registrations. A named empty module is passed as `Some("")` on initial registration but retained as an empty owner and reconstructed as `None` during later settlement; this distinction is captured explicitly.

The next implementation should declare arm selection and pending-registration transitions, use the existing observed macro-head and nominal resolver for real scope/import facts, and preserve partial progress on errors. Trait availability changes need an explicit update boundary. This capture does not exercise `do-produced`'s unchanged-singleton exception, generated struct/sum parsing, trait-name registration, or their full integration with staged requests. Those remain acceptance work, and the seed gate must not silently recapture expected results.

## Declared derive-arm selection

`code.schema` now declares the reference arm scan with `pair-selection derive-arms`: offset two, keyword keys, symbol values and last valid match. The language compiler's own grammar is schema-defined. Generated selection returns the original occurrence by value, borrowing its storage and retaining node identity, hygiene scope, definition module, context, origin, flags and source span.

The reference capture now records each selected struct/sum arm explicitly before registration, including malformed trait operands for which registration itself does not resolve arms. `tools/check-pairs.py` compares generated results against those captured selections in three configurations. Independent policies exercise first-match integer values, last-match text values, arbitrary values, symbol keys, absent/non-list inputs and maximum offsets. Invalid declarations are rejected. This establishes the selected-arm part of the captured contract only; registry insertion, partial settlement and the surrounding admission path remain unimplemented.

## Production registration and registry replay

`derive_registration/register!` now uses the generated `DeriveDeclaration` syntax view and pair selection, followed by typed macro callbacks and registry insertion. The two arm callbacks execute in struct/sum order before ordinary missing-arm validation. Internal callback failures propagate as typed failures rather than being silently treated as source lookup misses. Valid reference fixtures do not exercise corrupt callback states.

The shared insertion/settlement transition is declared by `derive_registration.protocol`: resolve; on a canonical result check uniqueness; publish after either an unresolved result or a clear uniqueness check. The storage adapter copies all entry text, indexes settled traits and tracks pending IDs. It preserves original spelling/owner for later resolution. An ordered pending queue preserves reference lookup order and partial commits while avoiding repeated inspection of settled rows. If settlement fails, the failed row and all later rows remain pending, together with any earlier unresolved rows. Earlier settled rows remain indexed and are removed from that queue. Finish reports the first still-pending row after settlement.

`evidence/derive-replay.json` records exact trace agreement for all 31 scenarios/82 actions in default, checked and release configurations, including diagnostic rendering by the test adapter and registry rows after every action. Registry-owned allocations are checked. The fixture supplies macro and trait resolution; neither actual module facts nor source diagnostic spans are established by this replay. Targeted growth tests additionally verify independent text ownership, reset/index invalidation, and no callbacks for already settled entries.

Still required: connect registration callbacks to real macro and trait namespace views, establish declaration-update boundaries, register generated structs/sums/trait names, and implement the unchanged-singleton exception when joining normalized forms to the program. No complete `do-produced`, source-analysis or expansion parity follows from this registry milestone.

The inspected trait resolver is ordinary nominal `resolve-in-space` with trait-specific membership. For derive registration its reflection context is null; membership comes from declared traits, including session-parent declarations. `register-generated-decl` calls `trait-names-into!` for a generated `deftrait`, which adds its qualified trait name. It does not itself register method names. Method elaboration remains a separate compiler responsibility; earlier admission wording conflating these was corrected.

## Derive registration through production namespace views

`deriveresolution` now supplies the registration/registry callbacks from the production scoped macro-head and nominal route implementations. Its context holds separate namespace views for macros and traits, so equal spellings in those spaces remain distinct. Macro arms publish selected source-route provenance before releasing their owned lexical probe. Canonical targets borrow namespace storage until registry insertion copies them. Trait failures retain the typed routing/ambiguity error rather than becoming an unresolved pending registration.

The head protocol now shares name/scope/definition-module extraction across owned syntax rows and reader symbols. The existing owned-row API retains its invalid-row and missing-context checks. Reader nonsymbols fail during preparation. Both representations use the same module selection, lexical probe construction and route ordering. The routing replay runs all 45 captured head cases through both entry points; the reference matrix remains 1,729 cases and the rewrite performs 1,774 matching executions. Targeted checks verify fresh probes for repeated negative-scope reader symbols and nonsymbol rejection.

A constructed integration fixture registers scoped imported arms, resolves nominal aliases, rejects canonical duplicates and trait import ambiguity, and confirms that the sum arm still resolves/publishes after a missing struct arm. It then replaces the context's immutable trait snapshot between calls and settles a previously unresolved registration. Registry and source-route text remains valid after every namespace store, reader input and head outcome has been released. This proves the callback integration and explicit update boundary. It does not yet derive snapshots from generated declarations, load source imports, merge parent-session facts, or implement the unchanged-singleton admission exception.


## Generated trait availability and settlement timing

Exact reference inspection places `derive-reg-settle!` in `derive-reg-find` and in `derive-reg-finish!`; generated declaration registration does not call it. Availability is published when the trait joins the program, while duplicate/ambiguity errors from pending registrations arise at a subsequent deriver query or expansion finish. The query settles all pending registrations, not just the requested trait. Full metaprogram deriver-query wiring remains required.

`traitdeclarations/observe!` now uses the produced-form walk and a declared `DeclaredTrait` syntax view to publish trait membership. It matches the availability helper's permissive boundary: only list `do` bundles recurse; a symbol trait name counts even when its body has not yet been validated; malformed names are ignored here. `namespace/introduce!` owns new strings and uses generated declaration rows/key indexes, retaining the immutable base import/export graph. Repeated introduction is idempotent and alias precedence remains unchanged. Introductions occur between queries, whose memo tables are per invocation.

`tools/capture-trait-reference.py` executes exact qualification, head inspection, membership insertion and trait observation helpers with a fixture state accessor. Its 57 cases span anonymous, named-empty and named modules, nested bundles, duplicates, non-list forms, malformed names and dotted/slash/Unicode spellings. `tools/check-traits.py` replays membership through the generated view and production introduction layer in three configurations with allocation checks. The derive integration test publishes a trait form while a registration is pending, verifies that publication does not settle it, and then resolves it at finish. This does not validate full trait syntax, add parent-session facts or implement the complete admission driver.

## Declared normalized-form admission

`admission.protocol` now declares classification, registration reuse, registration/consumption, declaration handling and publication. `admission/run!` applies it in normalized source order. An unchanged singleton registration passes through declaration handling and publication without re-registering; metadata-relevant change, multiple outputs or absent original causes registration and consumption. Trait names publish before the mandatory declaration callback; registration does not publish an ordinary form or allocate its version. No implicit finish/settlement is inserted during this loop.

Version assignment now exposes a per-entry operation taking the raw flattened count. This preserves the singleton criterion when earlier registrations are consumed, without allocating versions for consumed entries. Structural `revision/track!` reuses this operation. The driver versions only after successful declaration handling, and retains earlier effects/spent identities if a later form fails. The returned array is withheld on failure. Identity numbers are opaque compilation-local values, not reference numeric-ID parity.

A lazily populated projection session shares memo arrays across this immutable batch and projects each root at its processing point. This keeps prior effects intact if later projection fails and avoids repeatedly initializing whole-store memo tables. Reader syntax passed to callbacks is borrowed for the callback duration. Normalized syntax and metadata must not change during admission.

Targeted tests combine the production derive resolver/registry and trait publisher with a limited declaration fixture. They verify the unchanged exception, metadata change, raw-count splitting, visibility to a subsequent declaration, delayed settlement, prior effects on failure, retry identity freshness, unsupported declaration rejection and empty batches, with allocation checks. Full struct/sum registration requires a real declaration callback, and staged-compiler integration remains outstanding; exact reference replay of the complete admission operation remains outstanding. These tests do not establish full `do-produced` parity.


## Primitive function names and declaration parser baseline

Admission now includes an explicit collect state between declaration handling and publication. Its generated `GeneratedFunction` view recognizes a list headed by symbol `defn*` with a symbol name and arbitrary remaining forms. This is deliberately shallow observation, matching `defn-name-of`, not function validation. The owned ordered collection preserves duplicates and literal spelling, including slash, dotted and Unicode names. Qualification distinguishes absent modules from a named-empty module. Collection effects, like earlier declaration effects, survive a subsequent admission failure.

`capture-function-reference.py` extracts the exact `defn-name-of`, `qualify-name`, `sx-len` and `sx-at` helpers from the installed compiler's reported revision. The 51 cases replay against the generated view and production collector in default, checked and release configurations. Reader scratch is released before inspecting collected strings; the debug allocator checks cleanup. The admission fixture additionally verifies normalization, source-level `defn` exclusion and duplicate ordering across the complete admission call.

`capture-declaration-reference.py` separately invokes the real installed `dump-ast` parser on 70 struct/sum inputs: 42 accepted and 28 rejected. These cover type parameters and bounds, layout options, field defaults and offsets, bitfields, hidden fields, annotations, variants and nested type constructors. This is one installed executable/profile. The dump omits bounds, annotations and hidden initializer payloads; eventual parser equivalence needs richer observation for these fields. No replacement struct/sum parser or replay against it is claimed. Preserve the captured permissive arities and deferred layout behavior rather than imposing an accidentally stricter grammar.

## Written type grammar before declaration elaboration

The shared syntax compiler now supports bounded suffix captures, ignored suffixes and integer minima. `type_syntax.schema` uses those mechanisms to declare all type-list heads recognized by the inspected `parse-type-list`, plus constant/name forms, convention references and extent syntax. The pointer's optional first operand is a sequence of length zero or one; only canonical elaboration may substitute i64 for an absent pointee. Fixed array length zero is accepted; fixed vector/mask width zero is rejected. Generic applications recursively parse all arguments, while recognized permissive constructors ignore their extra operands. `const` and convention-value forms retain exact arity.

`tools/capture-type-reference.py` captures 113 real `dump-ast` inputs (76 accepted) under the installed compiler's recorded identity. `tools/check-type-syntax.py` replays acceptance through the generated written grammar in default/checked/release, with allocation checks. AST shape tests verify nested function signatures, pointer capture cardinality, generic constant arguments and owned spelling after reader teardown. Views retain the original scoped reader occurrences for future semantic elaboration.

This is a written grammar, not canonical type equality. Name/pack interpretation, target-dependent primitive sizes, hygienic lexical naming, source-site side effects and exact diagnostic reproduction remain required. The struct/sum declaration callback still rejects unsupported declarations in its limited test fixture. Next derive canonical elaboration rules and declaration parsing from these written views; never reconstruct hygienic identity from owned spelling alone.


## Retained identifier context

Written type rows now retain raw spelling, signed hygiene scope and definition module through a typed `identifier` syntax capture. This is lossless for the context read by the reference's `lexical-name` helper and allows schema-to-schema elaboration to operate after reader teardown. It does not retain every reader metadata field or establish exact source-site reconstruction for identifiers nested inside a parent row. Borrowed views continue to expose the original occurrences.

Capture and lexical identity allocation remain separate. `lexical/write!` shares the existing macro-head spelling mechanism: raw at scope zero, `$scopeN@MODULE$NAME` at positive scope, and a fresh `$datumN$NAME` for each negative-scope elaboration. Reusing an owned row must not cache the latter across distinct lexical occurrences. Type elaboration must classify built-ins, pack spellings and explicitly raw struct/dynamic names before requesting lexical identity, matching the reference parser's order. The production macro-head path uses the shared helper; combined route/head replay remains the integration oracle.

Independent identifier tests verify generated field ordering, borrowed views, transformed ownership after poisoned source pools, no fresh IDs during capture, and fresh IDs during repeated negative-scope elaboration. Full canonical type conversion and declaration admission remain future work.

## Structural type elaboration

A total generated map now converts written types into structural type rows. It handles constant wrapping, masks as boolean vectors, mutable/immutable references, pointer default i64, unified extents, convention forms, function signatures and generic applications. Identifier triples are retained where the reference later needs lexical naming; explicit `struct` and `dyn` forms retain their raw names. This stage does not allocate lexical identities and therefore remains eligible for pure transformation memoization.

Bare names remain `UnclassifiedName`; primitive/pack recognition and target-specific widths must eliminate that constructor before downstream layout/checking expects canonical types. `Dynamic` also remains explicit pending nominal-name elaboration. No runtime fallback or silent old-parser invocation handles these cases. Full canonical equality, source-site records and declaration registration remain incomplete.

Pointer defaulting uses the shared `(first-or sequence-field fallback)` expression. Selection is lazy and follows only the first sequence path, with explicit invalid-handle/range and cycle errors. A selected invalid child is an error rather than a request to evaluate the fallback. Structural tests cover all written constructors and ownership across input teardown; independent selection tests cover deep joins, ignored invalid tails, deferred fallback, failure propagation and retry.

## Declared type-name classification

the type-name policy in `type_syntax.schema` now supplies a generated, ordered classifier for the written `Name` boundary. Packs take precedence; Code/CodeBuilder and primitive spellings precede nominal fallback. `usize` and `isize` use an explicit target-width parameter. Decimal integer widths are 1..65535; malformed, overflowing or out-of-range spellings fall through to nominal, matching the reference's use of `prim-type` as an optional recognition step. Leading zeroes are allowed. Source `true`/`false` are handled earlier by written syntax and are not primitive names at this boundary.

`capture-type-name-reference.py` executes the exact pack, built-in and primitive/integer helpers in their inspected order against a primitive Type subset and explicit target-width fixture. Its 100 outcomes replay through the generated policy in default, checked and release configurations. This helper capture is not a complete parser, target-driver or diagnostic oracle. The new classifier language also has independent typed policies, overlapping-rule tests and maximum-i64 numeric boundaries.

Next connect classification results to canonical type construction while preserving raw pack spelling and the distinction between explicit raw nominal names and lexical references. Classification itself consumes no fresh identity. Canonical traversal, source sites, interning and complete declaration admission remain unimplemented.

## Lexical type components and occurrence effects

The transform language requires `:occurrences` for lexical identity allocation and for every pass that calls such a pass. This applies to scalar dependencies, ordinary sequence maps, spreads and selected `first-or` branches. Declaration checking rejects a cached caller even when its current fixture would not exercise the effect. The generated pass disables completed-result reuse independently of the caller's global sharing setting, while retaining visiting markers and cleanup for cycles and retries.

Type identifier, constant-reference, extent-parameter and convention components now use these declared maps. Text belongs to the destination store; negative scope receives a fresh identity per evaluation, positive scope retains definition context and zero scope retains raw spelling. Literal constants do not spend identities. These component maps feed the classified traversal and canonical construction below. Source-site effects remain required.

## Classified type traversal

The type schema now owns both the name-classification policy and its generated consumer. Target word width is an explicit immutable transform-context argument. Identifier classification precedes lexical name construction: built-ins and packs spend no fresh identities, while nominal references do. Full traversal maps constants, extents, conventions and generic heads through occurrence-sensitive lexical rules. Explicit struct names remain raw; dynamic names become raw nominal names with `-dyn` appended. Pointer omission remains signed 64-bit even for a 32-bit target, matching the reference rule.

Classifier elimination is exhaustive and typed, with branch-local bindings and lazy selected-arm execution. Nested classifier arms preserve source fields, and occurrence requirements apply transitively regardless of which arm a fixture selects. Context values belong to one state configuration; mutating exposed context fields violates the immutable-input/memoization contract. Text context is copied to the destination.

The 76 accepted cases in the real-parser capture now replay against classified graph equality in default, checked and release modes. A test-only decoder normalizes the reference's pack application and convention spelling into the rewrite representation; no old parser participates in runtime compilation. This is scope-zero, 64-bit AST-shape evidence. Separate tests verify other scopes and target widths, but do not establish reference source-site/diagnostic parity. Exact identifier sites, full declaration parsing and staged admission integration remain required.

## Canonical identities and occurrences

`CanonicalType` and its reachable component schemas now use generated bottom-up canonical construction. Structural identity excludes all origins and trace metadata, includes canonical child IDs, and compares sequence contents independently of segmentation. Destination-owned indexes persist across transformation states. Fresh negative-scope lexical names are assigned before this operation and therefore cannot accidentally merge. Noncanonical target rows appended through raw table APIs are rejected; mutation of existing rows remains a contract violation.

Row origins represent the first construction only. Every executed transformation constructor records its own source origin in `source/Trace`, including canonical hits. These numeric source/span values and copied source documents survive input teardown. This is compact occurrence provenance, not yet exact identifier capture or reference-compatible source-site publication. Sequence storage compaction, precise identifier/extent sites and full declaration admission remain required.

## Type-site publication and first extent locations

`capture-type-sites-reference.py` captures the exact `parse-type` wrapper separately from its inner parser. Fifty fixtures supply nominal, application, other-success and two failure results, while a spy records calls to `source-site-record!`. On successful nominal/application results, the wrapper chooses a nonempty list's head or the original atom. A `dyn` list with a second element additionally records that element after the first call. This explains why `(struct T)` records `struct`, while `(dyn T)` records both `dyn` and `T`. Failures publish neither wrapper call. Diagnostic source stamping is independent of span stamping: a precise inner span/context survives even when the enclosing source fills an unset file identity. Synthetic inner results intentionally isolate this wrapper; they are not evidence that every form/result combination can arise from the real parser. The spy does not implement SourceFacts filtering.

The same capture executes exact extent-site record/alias/lookup helpers over six independent scenarios and 27 actions. Only a negative `lo` prevents recording here; source and end offsets are not validated by this table. The first accepted name wins. An alias copies its source's recorded site only if the source exists and the destination has no site; self-aliases and chains preserve first-write precedence. Empty names remain valid keys. Fixture resets isolate scenarios and are not a claim about reference lifecycle policy.

`rewrite.extentsites` now provides an allocator-owned table with explicit lifetime and the same observation semantics. Its keys are owned, aliases copy the location value, and independent tables do not share state. Replay matches every intermediate lookup in three configurations, with a 2,000-name ownership/growth check. This table is a small runtime kernel over the existing Origin representation; it is not yet called by type elaboration or name qualification.

Remaining publication work must preserve symbol occurrence metadata, not just canonical type origins: the reference's site roles include spelling, hygiene, origin module and occurrence identity, and its expression-site key includes context/node identity. SourceFacts also filters disabled/out-of-scope observations and nonsymbol sites. Exact head/identifier captures, successful-child effects before a later parse failure, and publication at the actual recursive parser boundary still require implementation and direct integration evidence. Do not infer rollback or substitute the canonical row's first origin.
