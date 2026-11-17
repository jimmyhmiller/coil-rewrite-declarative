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


## Declaration sequence checkpoint

Sequence-result maps now omit, introduce and splice declarations while retaining order, sharing and source origins. The native fixture turns one source declaration into an alias and its implementation, calls the alias successfully, and rejects a colliding introduced name using normal duplicate-function checking. An independent fixture checks nominal sequence types, cardinality, shared results, input teardown and capacity errors. Shared-segment storage avoids repeated descendant copying at each splice.

This is a context-free normalization capability, not Coil macro/reader compatibility. Dynamic declaration discovery across expansion rounds, binding-aware transforms, host compile-time capabilities and dependency invalidation remain missing.


## Schema collection checkpoint

Sequence-valued node fields and final list/vector rest captures now support arbitrary declaration collections. The native fixture parses a module and nested groups into source sequence fields, maps them into a core module's function field, then compiles normally. An independent vector-record client checks constructor/surface parsing, malformed input diagnostics, compact shared-sequence mapping and text lifetime after source teardown. Segment traversal uses an explicit stack and retries correctly after element failures.

Only node-reference sequences are supported. Binding rules over collections, type-checking sequences, import/module semantics, dynamic expansion rounds and language-toolchain self-description remain incomplete.


## Shared lexical binding checkpoint

Reference fields and child-local name visibility now come from one binding declaration consumed by typing and lowering. Existing unary let and installed-Coil surface comparisons remain covered. A separate parallel-binding language exercises multiple names, outer-scope initializer evaluation, shadowing, sibling isolation and mixed payload types. A declaration-only name-order change is checked against both inferred type and native output.

This covers lexical topology, not full Coil binding compatibility. Names still resolve by Text in each consumer; canonical IDs, namespaces/imports, recursive groups, capture rules and binding-aware transforms remain missing.


## Schema parser self-description checkpoint

The seed now parses schema declarations through code generated from `languages/schema.schema`; its handwritten shape parser has been removed. The schema/syntax compilers regenerate that parser, and an isolated seed rebuild using the regenerated copy emits identical bytes. Input hashes and host compiler identity are recorded in `evidence/schema-bootstrap.json`.

At revision `f408c38`, a comparison with revision `62b83dd` covers 95 seed-language cases, including 72 seeded schemas: acceptance agrees throughout and the 77 accepted cases emit identical Coil. Six rejected cases change message wording or span specificity; both versions are recorded in `evidence/schema-parser-differential.json`. Semantic schema validation and model adaptation remain handwritten. Full Coil self-hosting, all-language self-description and bootstrap trust/distribution gates remain incomplete.

## Common keys and schema semantic indexing checkpoint

Record keys now support incremental insertion as well as batch construction. Sum keys require the same keyed field names and scalar types on every variant; physical positions may differ. Generated extraction dispatches by variant, while API and diagnostic field numbers follow the first variant. Failed duplicate/invalid-ID insertion preserves the existing map. Multiple keys remain independent indexes.

The schema grammar declares field, variant and declaration names as keys. The semantic adapter uses those generated indexes for uniqueness and forward type-name membership, replacing repeated linear name scans. Scope selection, diagnostic translation and remaining schema constraints still live in Coil; canonical binding resolution is not implemented.

The seed suite covers 10,000 mixed-variant rows, reordered fields, independent keys, duplicate provenance, insertion failure preservation, invalid common-key declarations, and schemas with 2,000 forward references and 2,000 keyed variants. Seed and native suites pass in debug/debug-checks/release, including isolated schema-parser regeneration. Generated index code and sum-key acceptance intentionally differ from the historical parser differential baseline. No full-toolchain performance improvement or parity claim follows from these checks.

## Occurrence-aware resolution checkpoint

The binding DSL now derives direct resolvers over schema records, variants and sequence children. Result-local declaration IDs distinguish repeated binder occurrences and connect references to the appropriate declaration under shadowing. A shared row can resolve differently at different lexical occurrences. Multiple scoped children can share one declaration, and scope order controls shadowing independently of field order. Globals are supplied explicitly; invalid names, row/sequence handles, cycles and duplicate globals are rejected.

The dedicated fixture covers these cases and table growth to 30,001 occurrences and 10,001 declarations in debug/debug-checks/release. Results borrow names; identity stability across resolutions or Store lifetimes is not promised. Existing type checking and lowering still use name contexts, and context-free maps have no capture-avoidance guarantee. Full Coil resolution, macro hygiene, imports, recursive groups, identity transport and client integration remain incomplete.

## Identity-directed alpha-copy checkpoint

Binding declarations now derive alpha copying over complete resolved roots. Local declarations get distinct names avoiding supplied globals, and reference names follow declaration IDs. Constructor shape and scalar values are preserved; shared input rows are copied per occurrence. The returned mapping connects source occurrences to target rows. Owned Text, origins and source documents survive input teardown.

Dedicated tests compare source and target reference targets and declaration owner/field identities, preserve global names despite generated-prefix collisions, and poison/free the input before resolving the target again. Failure tests cover aliased Stores, unresolved references, missing origins, conflicting source documents and overlapping binder/reference roles. The native suite also runs 40 seeded expression cases through alpha copying before checking, lowering and execution against their existing oracle.

This is a standalone shape-preserving operation, not general map hygiene. Freshness is scoped to one result plus its supplied globals. A field serving both binder and reference roles is explicitly rejected by alpha copying, while resolution still supports it. Failure can leave target-owned partial data; host-stack recursion and per-occurrence expansion remain limitations. Full macroexpansion, binding transport through arbitrary rewrites and semantic-client integration remain incomplete.


## Expansion reference contracts

`tools/capture-expansion-reference.py` captures existing staged-chain, early-macro, transform-introduced import/definition, guest-module reader, cross-target reader and reflective-reader behavior. The report identifies reference revision, compiler binary and input hashes, and stores exit/output assertions plus raw-output hashes. These checks currently execute only the reference compiler. They establish concrete targets for staged expansion and reader lifetime work; they are not passing rewrite parity entries. Source-observed phase policies and untested boundaries are distinguished in `contracts/expansion-protocol.md`.

## Explicit host-function linkage checkpoint

Program declarations can name unary Int-to-Int host functions. Their signatures participate in normal global checking, direct calls and explicit function pointers. Names cannot collide with program definitions. Runtime bindings use typed unary C callbacks; the checked loader rejects missing, duplicate, unknown, null and already-defined imports before executable mapping. Tests cover native calls and independent bindings in two simultaneously live images, plus invalid source declarations and callback types, in three configurations.

This adds a runtime call boundary for later compile-time operations, not the staged protocol itself. Code values/ownership, context-carrying callbacks, cumulative stage declarations and guest-language resumption are still unimplemented. Symbol validation does not verify arbitrary machine-code images. General FFI and additional ABIs remain incomplete.

## Owned reader-syntax checkpoint

The schema/syntax languages now generate an owned reader-syntax representation for integer/float-bit/symbol/keyword/string/C-string/list/vector values. A Coil adapter retains per-node origins, hygiene scope numbers, definition-module text and diagnostic-context numbers. Temporary reader storage is released before returning root sequences; diagnostic messages and registered documents remain owned. Tests cover exact negative-zero/NaN bits, container distinctions, metadata teardown, failed reads/imports and growth in three configurations.

The generated syntax-value parser also participates in isolated regeneration checks. This is not full Code compatibility: opaque metadata is preserved without implementing scope semantics; runtime views/joins, native handles, builders, invocation contexts and staged execution remain outstanding. Failure can retain unreferenced rows; identities remain store/session-local.

## Explicit callback-context checkpoint

Native host callbacks may now carry a typed borrowed context. The loader validates linkage first and emits CIR wrappers that adapt a program's unary call to a C callback taking context plus argument. A `ContextImage` tracks both executable mappings for ordered release. Two live images can carry distinct mutable contexts, including nested calls from one callback into the other image, without a global current-context variable.

The native suite checks callback types, reordered imports, missing/null callbacks, independent contexts and nested re-entry in three configurations on this Mac. Code-handle validation, invocation-owned syntax, arbitrary multi-argument signatures, semantic capabilities and cumulative staging remain incomplete. Allocator storage, callback code and context lifetimes remain caller-managed.

## Invocation handle checkpoint

Native syntax operations now validate positive opaque handles in an explicit invocation-owned store. Foreign and closed handles are rejected; canonical handles survive store growth and identities are never recycled within one loaded runtime instance. Entry calls distinguish syntax results from scalar results, reject null entry pointers and same-context re-entry, and propagate the first callback failure without treating sentinel zero as a valid handle. Closing an active invocation and reading new source while it executes are rejected.

The checked API currently offers first/last container selection and integer projection. This does not establish the complete Code API, hygiene operations, syntax promotion, semantic-query capabilities, cumulative phase declarations or language resumption. Context storage and executable-entry lifetimes remain caller-managed. Validation is local to this Mac; no cross-target or full compiler performance claim follows.

Validation: `python3 tools/check-seed.py` and `python3 tools/check-lowering.py` passed, including debug/debug-checks/release invocation fixtures. The handle-growth fixture was also rerun in all three configurations after extending it to 2,000 reads. The isolated grammar bootstrap records the current installed host compiler in `evidence/schema-bootstrap.json`.

## Syntax result promotion checkpoint

A declared `Syntax -> Syntax` transformation now derives structural promotion into independent storage. A metadata adapter transports opaque scope/context identities and owns module-name text. Shared rows remain shared in the destination. The invocation API validates a returned handle and promotes its root before teardown. This covers owned syntax graphs, not runtime Code views/joins, scope-domain remapping or arbitrary metaprogram builders.

The promotion fixture covers all scalar kinds, exact negative-zero bits, lists/vectors, shared child identity, aliased-store rejection, source-document conflicts and use after source text poisoning/release. A native fixture promotes its selected result, unloads its image and closes its invocation before using the result. The implementation still allocates source-sized memo tables, scans them to transport metadata, and uses recursive generated row transforms; no full-compiler memory or compile-time improvement is claimed.

Validation: seed and native suites passed in debug/debug-checks/release, including isolated grammar regeneration. The extended promotion fixture additionally verifies missing metadata, successful retry after failure and cycle rejection; it passed separately in all three configurations.

## Cumulative native phase mechanism checkpoint

The program language's optional `(cumulative)` policy derives append-only checked declaration history. Later native entries can call earlier helpers through a freshly compiled cumulative image. Duplicate/invalid additions do not change the accepted declaration prefix. Linking remains separate from history acceptance; no live-code replacement is introduced.

A two-increment fixture executes phase A, promotes its returned `chain-b` guest syntax, recognizes that form, adds phase B calling the earlier helper, and executes it through a fresh invocation. Its final syntax is parsed by the runtime grammar and compiled to a separately loaded image returning 42. The runtime image has exactly one named/defined entry; no stage helper names are present. This is in-memory image evidence, not a serialized binary `nm`/`strings` check. The fixture selects nested authored syntax, and the driver remains test code. Full expansion-policy and reference-source compatibility remain incomplete.

Syntax import and promotion now retain reader origin markers, transport flags and positive reader-node identity alongside hygiene/module/context fields. These fields were previously dropped. The temporary reader projection preserves those values and sharing, checks graph errors and borrows text only while the owning syntax remains live. General Code views/joins, scope-domain remapping, syntax construction, semantic capabilities and imported-reader artifacts are still missing.

Validation: `tools/check-seed.py` and the final `tools/check-lowering.py` run passed, including isolated grammar regeneration and debug/debug-checks/release fixtures. Source inventories and bootstrap hashes are refreshed. These checks do not establish full toolchain compatibility or self-hosting.

## Declared protocol control checkpoint

A generic protocol language now compiles named effect states, typed outcomes, completion and finite budgets into a direct driver. Its grammar and key indexes are themselves generated from a schema specification. Duplicate/unresolved definitions, unreachable states and cycles without a spending edge are rejected before code emission. Typed handlers return either a declared event or a caller-defined error; an outcome illegal in the current state and an exhausted budget are explicit failures.

The request-count protocol remains covered by standalone tests. The cumulative native fixture has moved to the owned before-expand adapter described below, using actual whole-form equality and shared 16/64 accounting. Guest discovery and compiler/JIT adapters remain test code. Full request/declaration semantics, source marker routing, constructors, semantic capabilities and reader imports remain incomplete.

Protocol tests cover zero, exact and exceeded budgets; independent retry/poll budgets; acyclic protocols without budgets; fresh repeated runs; handler failures; unexpected outcomes; invalid graph/name/shape contracts; and rejected callback signatures. A fuel check occurs after its source handler returns and before its target handler runs; no rollback of source effects is promised. The graph proof assumes handlers return and does not bound their own execution.

Validation: the complete seed and final native suites passed. Isolated seed regeneration now compares all four language artifacts, including the protocol grammar and staged protocol driver. The independent protocol client and boundary/error tests passed in debug/debug-checks/release. No whole-compiler performance, complete expansion compatibility or self-hosting claim follows.

## Reference boundary and shared-counter checkpoint

Thirteen installed-reference probes now establish before-expand, semantic and after-expand call counts and outcomes. Successful artifacts are executed to verify their rewritten global value. Mixed staged/plain rounds establish one counter with conditional 16/64 guards and equality precedence. A separate trace records the distinction between module-projection equality and whole-form equality in an initially unchanged fixture.

The protocol language's `spend-within` transition applies a stricter ceiling to an existing budget counter, with no reset or independent count. Its generated before-expand guard model replays eight reference changing-round traces in debug/debug-checks/release. The evidence is scoped to accounting: it does not establish rewritten source compatibility, initial normalization, production request handling, Code construction, semantic model availability or strict final checking. Full self-hosting and toolchain replacement gates remain unmet.

Validation: all 13 reference probes and the additional comparison trace passed. The full seed and native suites passed; isolated regeneration covers five language artifacts. The final accounting replay passed in all three configurations and its evidence hash points to the final reference capture. This remains a partial compiler rewrite, with no global installation.

Schema-derived syntax equality is implemented as a prerequisite for expansion: raw-bit float values, tags, scalar values and ordered children determine structural equality; source reuse additionally checks scope and definition module recursively. Pair memoization preserves equality across differing DAG sharing, detects active pair cycles and avoids recursive traversal. Tests include 25,000 levels and independent record-schema generation. This does not establish whole-form fixpoint parity: production normalization, ordered generation roots, stage-progress effects and round publication remain incomplete. Sequence comparison currently materializes logical elements.

Owned whole-form round adaptation now uses a schema-derived ordered root sequence and the declared before-expand policy. It preserves current forms on equality, publishes changed candidates after acceptance, derives stage progress from newly introduced batches, and retains candidates on errors/limits. Actual syntax tests cover later-root/arity changes and mixed 16/64 accounting. The native cumulative helper fixture now exercises two accepted generations and one equality round. Full multi-module tagging/normalization and production stage/request discovery remain absent; fixture routing still recognizes authored chain templates. External stage effects occur before guard failure and are not rolled back.

Stage datum isolation now has a declared per-constructor context policy matching inspected `stage-datum-sexp`: symbols lose scope/module, get origin 5 and fresh identity; lists/vectors refresh identity; other metadata/leaf identities survive. Occurrence-sensitive generated copying distinguishes shared occurrences and preserves independent storage, with cycle/retry tests. Identity allocation still uses the bootstrap reader's same-session supply. This is not complete stage splitting: module-tag retention, marker collection, stage grammar validation and request execution routing remain unimplemented in production.

Stage splitting is now implemented over module-tagged owned roots. Its generated declaration view commits malformed `stage` heads to an error, while unrelated roots stay runtime forms. It retains body module tags, deduplicates cumulative markers across modules, treats empty stages as marker declarations without stage forms, and isolates each stage occurrence. Nested/quoted/vector stage-shaped data is not split. The native fixture now compiles these isolated bodies; request recognition, entry qualification, imports and full marker execution remain outstanding.

Request inspection/discovery now uses declared request shapes and walk boundaries. It implements compilation-wide marker membership, quote precedence, declaration/convention prefix exclusion, module-qualified lookup and symbol/string entries. The first discovered call is outermost and left-to-right, with raw arguments. Native fixture entry addresses are selected by the inspected name. General execution/replacement, returned-request resumption, variadic/typed Code arguments and the 100,000-invocation guard remain incomplete. Reader-projection and caller-arena lifetime constraints still apply.

Request execution/replacement is now implemented with a declared per-original-root 100,000-call guard. Returned requests re-enter selection under the original tagged module; arguments remain raw until the selected callback handles them. Enclosing list/vector metadata survives rebuilding. Three configurations cover exact limits, unavailable-entry precedence at the ceiling, repeat runs, callback/projection failures and output promoted beyond session lifetime. The native cumulative fixture uses this runner and still returns runtime 42. Top-level result splicing, declaration bookkeeping, full Code argument typing/arity, import handling and whole-frontend integration remain outstanding. Successful fixture callbacks use one Code-handle argument; this does not establish general stage signature compatibility.

Top-level request results now normalize through a declared leaf walk: nested list-headed `do` bundles splice recursively, empty bundles disappear, and ordinary forms remain whole. A production batch adapter retains original module tags, uses fresh per-original-root fuel and owns output beyond session/input lifetime; the native fixture uses it. Generated walker and owned/batch fixtures pass three configurations, including later-root failure/retry and source-conflict cleanup. Generated declaration/derive admission, form identity/revision/cache tracking, full Code signatures and source-compatible stage compilation remain missing. Reference revision equality's origin/flags comparison is recorded but not yet implemented by a reuse predicate.

Revision reuse now has a declared recursive metadata predicate including origin/flags. A compilation-local kernel tracks singleton changes, stable cache reuse, splits, deletion and fresh identities. A typed per-root admission callback runs before the next original request, and batch tests use it for tracking and verify retained effects on failure/retry. Counter exhaustion is explicit; maximum-integer behavior and numeric identity sequences are not claimed identical to the reference. Actual derive/declaration registration, tracked-state propagation through the full compiler and semantic-cache use remain absent. The default native fixture still uses structural no-op admission.

Schema-derived import refer indexes now reproduce captured `use-refers`, `use-local-of` and `use-drops?` helper behavior: rename/exclude/selection precedence, source-order collisions, self-renames and explicit-drop distinction. The captured oracle has 43 policies/387 queries; two layouts match in three configurations. Owned lifetime, 2,000-name growth, invalid graph handling and late-error cleanup are tested. The oracle compiles extracted helpers, not the complete reference resolver; source import parsing, namespace route selection, exports/reexports, ambient provider overrides, hygienic lookup and derive admission remain incomplete.

Export lookup now has a production snapshot adapter driven by `languages/exports.search`. It checks visibility before one-hop declaration aliases/direct membership, follows renamed reexport edges in order, and observes the reference's inspected 64-depth guard. Tests distinguish direct precedence, hidden direct declarations, missing module records, renamed candidates, and cyclic queries requiring name/depth-sensitive memo keys. Independent policy tests verify that declaration order changes results and that callback failures release pending arrays. Reference differential export capture remains outstanding; no full resolver parity is claimed. Source normalization, alias/dotted/bare routes, namespace-specific ambiguity, core-provider ownership, hygiene and admission remain incomplete.

Export differential evidence is now available: `evidence/export-reference.json` records exact extracted helper execution over 25 graphs/2,688 queries in three configurations, and `evidence/export-replay.json` binds matching production rewrite answers to the implementation hashes. The oracle includes one-hop aliases that override same-spelled direct names, cyclic depth boundaries, visibility and generated import/reexport cases. Its fixture membership and table adapters are explicit. This advances export-helper compatibility only; source parsing, duplicate-table normalization, checker membership, surrounding name routes, route recording and hygiene remain outside this evidence.

The use-import tier now applies declared candidate selection to the production export query. Macros stop at the first successful candidate. Nominal lookup rejects a later candidate only when both its import owner and canonical declaration differ from the first witness. Targeted tests cover the same-owner exception and ensure intermediate agreeing candidates do not replace that witness. The operation returns selected provenance or typed conflict records, with allocation cleanup checked. Exact reference use-tier replay, source-route recording, diagnostic rendering and surrounding routes remain pending; the existing export differential matrix does not prove those behaviors.

`evidence/use-reference.json` and `evidence/use-replay.json` now establish use-helper parity over 25 graphs, 258 use lists and 2,564 outcomes in default/checked/release. Selected canonical targets, macro candidate provenance and ambiguity-owner pairs match; replay allocation checks pass. The reference route recorder checks exact route count and identity, but the rewrite comparison covers returned provenance, not route publication. Diagnostic text/spans, source import rejection rules and surrounding resolver routes remain incomplete. The seed gate consumes this capture without recapturing it.
