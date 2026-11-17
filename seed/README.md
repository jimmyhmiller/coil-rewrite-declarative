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
