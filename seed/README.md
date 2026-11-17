# Bootstrap language implementation

`schema.coil` implements the first schema surface:

```
(node Add (left Expr) (right Expr))
(node Expr (value Int))
```

Names are symbols. `Int`, `Bool`, and `Text` are scalar types; other field types name nodes, including forward or recursive references. Node names cannot reuse scalar names. Node and field declarations must be unique in their respective scopes. Empty schemas and nodes without fields are valid. No output code is generated yet.

`parse(allocator, source-text, source-id)` produces a checked schema or a diagnostic with a byte span and source identity. The caller supplies an arena and retains both that arena and the source text for the schema's lifetime. Failed parses use the same arena lifetime. The seed uses the standalone `coil.reader` library for s-expression syntax; it imports no compiler frontend modules. This reader dependency belongs in bootstrap size and dependency accounting.

Run `coil run tests/schema.coil`, also under `--debug-checks` and `--release`. The suite covers forward references, declaration/field errors, malformed syntax and exact source spans. The hardcoded byte offsets refer to an inline string, not line numbers in a source file.

Next: derive compact typed storage and constructors, then compile judgment rules against the schema. Recursive node fields must become stable IDs rather than recursive by-value structs. Decide and validate that representation before generation. The complete compiler and self-description goals remain unimplemented.
