# Bootstrap language implementation

`schema.coil` implements the first schema surface:

```
(node Add (left Expr) (right Expr))
(node Expr (value Int))
```

Names are symbols. `Int`, `Bool`, and `Text` are scalar types; other field types name nodes, including forward or recursive references. Node names cannot reuse scalar names. Node and field declarations must be unique in their respective scopes. Empty schemas and nodes without fields are valid. `emit.coil` derives distinct reference types, row layouts, append constructors and checked lookups.

`parse(allocator, source-text, source-id)` produces a checked schema or a diagnostic with a byte span and source identity. The caller supplies an arena and retains both that arena and the source text for the schema's lifetime. Failed parses use the same arena lifetime. The seed uses the standalone `coil.reader` library for s-expression syntax; it imports no compiler frontend modules. This reader dependency belongs in bootstrap size and dependency accounting.

Run `coil run tests/schema.coil`, also under `--debug-checks` and `--release`. The suite covers forward references, declaration/field errors, malformed syntax and exact source spans. The hardcoded byte offsets refer to an inline string, not line numbers in a source file.

Build and validate generated code with `python3 tools/check-seed.py`. The seed reads a schema from stdin and writes a `rewrite.generated` Coil module to stdout; diagnostics go to stderr. Numbered names are internal and avoid collisions with source symbols and Coil keywords. Node references become distinct `N0Id`, `N1Id`, etc.; rows hold scalar values and typed IDs, and growable tables store rows. Numeric assignments depend on schema order and cannot be persisted without schema identity.

IDs survive table growth and checked lookups reject negative and out-of-range indexes. IDs are local to a table: the current API does not distinguish two tables of the same node type, prevent forged IDs, or check the references inside an appended row. Text remains borrowed. An owning store, schema-driven traversal, source-origin fields, and graph validation are still required before this is a compiler IR. Recursive layouts compile without recursive by-value storage.

The generator is ordinary Coil and uses StrBuf emission; it derives layouts and operations from checked schema fields, with no embedded user code. This is an initial substrate, not yet the high-level semantic language. Next: sums/variants and judgment compilation against these representations. The complete compiler and self-description goals remain unimplemented.

Sum declarations now describe variants of a single node identity:

```
(sum Expr
  (Literal (value Int))
  (Add (left Expr) (right Expr))
  (Choose (condition Bool) (yes Expr) (no Expr)))
```

A sum emits one nominal ID type and one Coil sum row, with constructors `N0V0`, `N0V1`, etc. Variant names are unique within the sum; field names are unique within a variant. Sums require at least one variant. References resolve against node/sum names, not constructor names. Thus both Add operands reference any Expr variant, and representation size stays finite. Tests build a recursive expression graph, grow its table, evaluate it through exhaustive generated-variant matches, and check malformed declarations. The evaluator in the test is handwritten acceptance code; judgment compilation has not been implemented.

The first judgment surface is now compiled:

```
(judgment Expr
  (Integer Int)
  (Boolean Bool)
  (Add Int (left Int) (right Int)))
```

A judgment names a declared sum, gives exactly one case per variant, and checks zero or more child premises before returning a scalar type. Premises must name fields referencing that same sum. The seed checks coverage, duplicate judgments, field existence and premise/result types before publishing output. It generates direct variant dispatch and recursive native calls; no rule interpreter runs in the generated checker.

The generated `judge-N` API returns a `Judgment` sum: `Typed` carries 1/2/3 for Int/Bool/Text, `Mismatch` identifies the child ID, field, expected/actual types and premise byte span, and `InvalidReference` and `CyclicInput` distinguish graph errors. Nested failures propagate unchanged; premises run in declaration order and the first failure wins. Recursion has a table-length depth budget, sufficient for any acyclic path through that table, rather than an arbitrary constant cutoff. Very deep valid graphs can still exhaust the native stack; iterative scheduling and memoization are future work. The result retains the failing premise but not a full ancestry trace or original expression source span. This finite kernel is not Coil's type system: contexts, type variables, unification, elaboration, bidirectional checking and richer result schemas remain to implement.

Schema parsing currently recognizes and defers judgment forms to the judgment compiler. The command publishes no generated source if judgment validation fails. The command reads the source once and shares those parsed forms between schema validation and judgment compilation.

Rule-local inference variables use a `?` prefix:

```
(Choose ?result (condition Bool) (yes ?result) (no ?result))
```

The first premise naming a variable binds it to that child's synthesized type. Later premises using the variable require equality with the binding; the rule result may return it. Distinct variables bind independently. Variables are scoped to one variant rule, and a result variable without a premise binding is rejected at its source span. Rule compilation assigns local slots by first occurrence, so variable spelling does not enter generated identifiers. Premises still execute in source order and preserve first-failure behavior.

This implements local inference over concrete scalar types, not general unification of type constructors or polymorphic type schemes. The conditional fixture exercises both Int and Bool results, disagreeing branches, and an invalid condition. A separate projection rule exercises independent variables. Contexts for variables/lets/functions and bidirectional checking remain required for the frontend slice.

Lexical contexts are expressed through lookup and premise-local extension:

```
(Variable (lookup name))
(Let ?body
  (value ?value)
  (body ?body (bind name ?value)))
```

`lookup` requires a Text field and returns the nearest binding's type, or `UnboundName` with the expression ID and name. `bind` also requires a Text field. Its type must be a scalar or a variable bound by an earlier premise; it cannot depend on the premise whose context it extends. Each extension exists only for that recursive premise. The implementation uses immutable linked stack frames, so returning from a child restores the parent's context without mutation or cleanup bookkeeping. The empty root context is a sentinel and is never followed to its null parent.

This lets the rules specify non-recursive let scope: value in the outer context, body in the extended context. Tests check unresolved names, shadowing, outer-name use in an initializer, and sibling isolation. Binding Text is borrowed from the expression table; the table and its strings must outlive a judgment call. General namespace resolution, mutually recursive bindings, function types and environment-dependent caching remain unimplemented.

Schemas also derive constructor readers and a multi-table `Store`. `parse-N(store, form)` reads a `coil.reader/Sexp` into the corresponding node table. For example:

```
(Let "x" (Integer 42) (Add (Variable "x") (Integer 1)))
```

The schema controls constructor names, arity, scalar validation and recursive dispatch, including references between different node types. The reader emits children before parents and returns a nominal ID. `store-new` initializes the tables, `store-free!` releases them. A parallel origins table keeps the original Sexp for every row created by the reader, preserving source identity and spans for later diagnostics. These are borrowed syntax values: retain their source/reader arena for the store lifetime. Manually appending directly to row tables bypasses origin tracking and must not be mixed with reader-owned store construction.

On a failed parse, previously appended child rows remain in the store; discard that store/arena if transactional behavior is required. No partially constructed parent is published. The generated reader currently recognizes explicit constructor syntax, not Coil surface syntax. Tests run source through the generated reader and judgment checker, exercising lets, shadowing, invalid names, branch disagreement, malformed fields/arity and unknown constructors in debug, debug-checks and release. The standalone reader and generated table machinery are still bootstrap dependencies to count.

`types.coil` introduces the concrete type store needed for function judgments. Scalar IDs remain Int=1, Bool=2, Text=3. `function(store, argument, result)` interns a unary function type and returns its canonical ID; argument and result can themselves be functions. `as-function` safely decomposes one. The pair index uses two checked 32-bit IDs packed into a u64, so pair equality is exact and lookup does not scan the type table. Exhaustion returns `TypeCapacity`; invalid component IDs return `InvalidType` before any mutation.

IDs belong to one type store and are meaningful only while it lives. Callers must not mutate the store's backing tables directly or compare IDs from different stores. This API currently handles concrete unary function types, not unknown metavariables, recursive types, polymorphic schemes, multi-argument signatures, or effects. Generated judgment calls now take a caller-owned type store as their first argument, so returned function IDs remain valid until that store is released. The implementation is handwritten Coil runtime machinery pending self-description, and counts toward the total authored size.

`tests/types.coil` checks canonical reuse, argument/result distinction, higher-order signatures, invalid IDs and 10,000 nested signatures across growth; `tools/check-seed.py` runs it in all three build configurations.

Judgment result terms can construct function types:

```
(LambdaInt (Fn Int ?body) (body ?body (bind name Int)))
```

`Fn` terms nest recursively, and their leaves are scalars or previously inferred rule variables. The seed validates every nested term and rejects unbound variables before generation. Generated code interns the resulting type in the caller's `rewrite.types/Types` store; construction errors propagate as `TypeConstruction`. The generated module imports that runtime, which must accompany generated output. The acceptance harness copies the exact source into its isolated consumer projects.

The public signature is now `judge-N(type-store, rows, id)`. Context bindings and type-variable equality operate on canonical IDs from that same store. Tests parse and check identity functions, let-bound functions and nested function results, then decompose the returned types before releasing the store. LambdaInt/LambdaBool are fixtures demonstrating domain-independent rule composition, not a claim to implement Coil lambda semantics or capture rules. Call typing, argument annotations, function-type pattern premises, polymorphism and elaboration remain pending.

Premises can match structured function types and bind their components:

```
(Call ?result
  (callee (Fn ?argument ?result))
  (argument ?argument))
```

Patterns recurse through `Fn`; scalar leaves require exact type identity. The first occurrence of a variable, including inside a pattern, binds it. Later occurrences require equality, even within the same pattern, so `(Fn ?same ?same)` describes functions whose argument and result types agree. Variable slots are assigned by the first occurrence's source position, independent of spelling. A non-function where `Fn` is required returns `ExpectedFunction` identifying the child and actual type; scalar/component disagreement retains `Mismatch` and premise location.

Source-driven tests cover successful calls, argument mismatch, non-callable values, nested calls, repeated pattern variables and nested function patterns. This is structural matching of already concrete types. It does not implement metavariable unification, overload search, polymorphic instantiation or Coil's complete call semantics.

Scalar native lowering is now a schema-checked language:

```
(lower Expr
  (Integer (const value))
  (Boolean (bool value))
  (Add (add left right))
  (Choose (if condition yes no)))
```

Every sum variant needs exactly one lowering case. Operators validate their field names/types. `add` evaluates children left-to-right; `if` generates true/false blocks, a join and an SSA variable, evaluating each branch within its own block. Integer and boolean values currently use CIR i64. This is a limited scalar representation, not Coil's ABI/layout implementation.

The generated internal `lower-N` function requires an acyclic, fully checked graph with rules covering all reached variants. It does not recheck types or validate graph cycles; callers must successfully run the judgment first. Invalid references indicate a violated internal precondition. The source reader constructs acyclic graphs. No machine code should be emitted for rejected source.

`python3 tools/check-lowering.py` compiles source through generated reading, checking and lowering, then executes the retained direct native backend's result. Tests include both conditional arms, nested joins inside arithmetic and rejection before lowering, in debug/debug-checks/release host builds. The harness uses the retained backend's test image loader; this is acceptance scaffolding, not the eventual production lifetime-managed linker. Direct calls, lexical values, object output, runtime source/debug locations and general lowering types remain pending. `lower` contains no raw Coil escape hatch.

Lowering now supports lexical values:

```
(Variable (name name))
(Let (let name value body))
```

`name` resolves a Text field through the lowering context. `let` lowers its initializer in the outer context, binds the resulting CIR value only for the body, and returns the body's value. Context entries contain CIR value IDs, not source expressions, so uses share the initializer's result. Shadowing and leaving scope do not mutate outer bindings. An initializer's branch merge is completed before its value is bound; body branches receive the same dominating value.

The native suite includes shadowing, outer-name lookup in initializers, branch-local shadowing without leaks, and bindings initialized by conditional merges. It also generates 40 deterministic nested programs with an independent Python value oracle and executes them through the new generated frontend/lowering and retained backend in all three host build configurations. This does not cover side effects or calls yet; those must extend the same semantics tests as implemented.

`(Call (call callee argument))` lowers a unary scalar call. Callee and argument are lowered in source order. A zero-addend CIR symbol becomes a direct call; other callee values use an indirect call. The current ABI is one i64 argument and one i64 result. General signatures, aggregate passing and closures are not implemented.

`runtime/native.coil` now owns the direct-backend image boundary instead of using `tests.direct/load-compiled`. The caller supplies allocation storage for compilation state and image metadata, keeps it live through execution, unloads executable memory, then releases its arena. The adapter currently links only symbols defined in its image and supports the scalar operations exercised here; runtime helper resolution, recoverable link diagnostics, object output and general ABI handling remain required.

The call acceptance fixture registers an `increment` function's signature and symbol explicitly, checks and lowers both function bodies from source, links them in one image, and executes a caller containing a direct call plus a branch-selected indirect call. It verifies exactly two CIR call instructions even though a let-bound result is used twice. Source-level function declaration syntax and module orchestration remain to replace the fixture's registration code. Scalar and call suites use growing ScratchArena storage and explicit unload/release order.

Program declarations now derive function registration and body orchestration:

```
(node Function (name Text :key) (parameter Text) (body Expr))
(program Expr Function name parameter body Int Int)
```

There is one program declaration per generated module; its expression schema must have both a judgment and a lowering. The declaration selects a record's two distinct Text fields and expression body field. `program-functions` converts reader-produced record IDs into declarations, rejecting invalid IDs. `compile-program` collects all global signatures and symbols, rejects duplicate names, checks every body, and only then lowers and emits functions. Forward references are available during checking; parameters shadow global names. The returned image uses declaration order for symbol IDs. Callers own the scratch arena and executable-image unload lifetime, as for the native adapter.

`tests/program.coil.in` exercises forward calls, duplicate names, an invalid later body, wrong return types, and parameter/global shadowing. The native harness runs it in debug, debug-checks, and release. DSL checks reject duplicate program declarations, missing judgment/lowering dependencies, invalid fields, and unsupported signatures before publishing generated output.

This first program form only supports unary Int-to-Int functions. Its orchestration implementation is a fixed Coil generator template, counted as authored machinery; it is not yet the planned composable phase language. Global duplicate detection uses the schema-derived unique index. Global type and symbol contexts are now shared indexes; derive orchestration from reusable phase contracts before treating this as the final language architecture. The retained image registry still scans existing names during symbol registration. Full Coil syntax, macro expansion, general signatures, modules, effects, artifacts, and self-hosting remain outstanding.

Record fields can declare unique keys, for example `(label Text :key)` or `(serial Int :key)`. For each such field the schema compiler derives `index-N-F(allocator, rows, ids)`, returning a typed HashMap from field values to nominal row IDs. The selected ID sequence defines the scope of uniqueness; unselected rows do not participate. Keys may be Text, Int, or Bool. Multiple key fields define independent indexes, not a compound key. Sum variants and reference-valued keys are rejected until their equality semantics are specified.

Index construction checks IDs and reports `DuplicateKey(node, field, first, second)` with both original row IDs, or `InvalidIndexReference(node, id)`. The first duplicate in selection order determines the diagnostic. Failed construction releases the partial map. Successful maps belong to the caller and must be freed. Text keys own copies and compare by content; IDs remain meaningful only for the original row table. An index is a snapshot: appending or editing rows does not update it, and building one does not make the mutable row table permanently unique.

Function-name fields must now declare `:key`. `compile-program` takes the selected function-record IDs directly, derives their unique-name index, converts the records, and proceeds to all-body checking. This removes the quadratic duplicate scan from the program template. The generic key mechanism is also exercised independently with 10,000 multi-key records, non-contiguous selections, duplicate provenance, repeated IDs, and invalid references. It is the first part of schema-driven indexing, not yet a complete scope, namespace, or module binding language.


Checking and lowering now share `rewrite.scope/Scope[V]`, a small handwritten runtime kernel counted with the seed. A scope is a chain of borrowed lexical frames ending at either an empty root or a borrowed immutable HashMap. `scope-bind` creates a frame without changing its parent; `scope-global` wraps a map; `scope-lookup` returns the nearest local value or the indexed global value. Frames, borrowed names, and maps must remain live through lookup. Maps are populated before body checking/lowering and are not mutated while those phases run. The current kernel has no namespace/import semantics, scope cycles, or mutation/invalidation protocol.

Generated judgments use `Scope[i64]` for canonical type IDs. Generated lowering uses `Scope[ValueBinding]`: `LocalValue` carries a CIR value, while `GlobalSymbol` carries an image symbol identity. A global lookup creates a CIR symbol at the use site. Global identities may be shared by every function; CIR values are function-local and are never stored in the shared global map. References in different branches are materialized in their respective blocks, avoiding accidental reuse of a value that does not dominate both branches.

Program compilation creates the two global maps once, borrows their roots for all bodies, and frees them after emission. It no longer builds a linked global context or emits all global symbols into every function. The native suite checks zero/used symbol counts with 2,000 globals, local/global shadowing and outer initializer lookup, and a 129-function forward-call program in all three host configurations. This establishes the removal of the repeated global setup, not a whole-compiler speedup: retained `image/symbol!` still performs a linear name scan per registration, and source-name resolution inside local scopes still walks lexical frames. Module indexing and stable binding identities remain required.

The seed also has an artifact-prerequisite language:

```
(phases
  (input declarations Declarations)
  (phase emit
    (needs (checked CheckedProgram))
    (makes (image NativeImage)))
  (phase check
    (needs (globals GlobalEnvironment))
    (makes (checked CheckedProgram)))
  (phase register
    (needs (declarations Declarations))
    (makes (globals GlobalEnvironment))))
```

A phase names required artifacts and their nominal representations, and one or more produced artifacts. Every artifact has exactly one source: an input or a phase. `rewrite.phase/schedule` resolves forward references, rejects missing or duplicate producers and representation disagreements, and derives a deterministic serial order. A dependency cycle is an error; no partial schedule is returned. Independent phases enter the ready queue in declaration order, and newly ready consumers follow their producer's edge order. All phases run; there is no output pruning. Resolving names uses hash indexes, followed by a linear traversal of the phase/edge graph.

The program compiler uses this contract to order its registration, all-body checking, and emission fragments at generation time. Its contract deliberately lists emission first; the derived output still checks every body before emission. The seed compiler itself is a second client: table definitions feed reader/index/judgment/lowering generation, and those outputs join before program generation. This replaces fixed scheduling in those two clients; their phase implementations remain Coil code or generated Coil fragments. The schema parser is still a prerequisite outside the seed-generation plan.

Representation names are checked nominal labels, not proofs that a phase implementation fulfills its contract. Stage implementations and their mapping to artifact storage remain trusted and handwritten; consumers reject unknown stage implementations. These plans describe finite single-assignment artifacts. They do not model mutation, capabilities, effects, failure recovery, dynamic discovery, expansion fixpoints, invalidation, cache identity, or typed artifact ownership. Those require further language mechanisms before this can represent Coil's full frontend protocol. Independent side effects must not be hidden in phases and assumed to be ordered merely by a ready-queue tie break.

Planner storage belongs to the supplied arena, including failed plans, and returned phase names borrow the contract text. `tests/phases.coil` checks reverse-declared dependencies, independent roots joining with multiple prerequisite edges, input-only plans, malformed contracts, absent/multiple producers, representation mismatch, duplicate phases, and self/mutual cycles. It runs in debug, debug-checks, and release as part of `tools/check-seed.py`; the native suite checks the generated program client.
