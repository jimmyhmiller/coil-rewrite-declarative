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
