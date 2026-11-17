# The replacement Coil compiler

This directory is the compiler's authored source, written in our custom languages.

- `frontend/types.schema`: written type grammar, elaboration, classification and canonical construction.
- `syntax/code.schema`: owned compiler syntax and its structural operations.
- `resolution/`: namespace data, lookup protocols and export search.
- `expansion/`: staging, macro-head lookup, derive registration and generated-form admission policies.

The integrated command below connects expression parsing, checking and native execution. Full declarations, specialization, module and expansion integration, and standalone executable output remain unfinished.

`../languages/` defines the languages themselves. `../seed/` contains their bootstrap implementations, generated output and runtime support. Existing compiler-specific Coil adapters there are migration debt: their semantic decisions must move into this directory's languages as the integrated compiler is built. The retained declarative backend remains under `../vendor/coil/`.

The compiler must be built by composing these language programs into a working source-to-output pipeline. Adding another isolated DSL demonstration does not establish compiler progress.

## Running the compiler

Build the command with `python3 tools/build-compiler.py`, then run:

```
build/coil-rewrite run tests/compiler/integer-functions.coil entry 41
```

The result is `84`. `frontend/core.schema` declares the current expression grammar, lexical binding, type judgments, lowering, function program and source command. The bootstrap translates those declarations into executable Coil; guest source is parsed, checked and compiled directly to native code by the resulting binary. It does not invoke the old compiler on guest input.

Current support is limited to functions with zero or more `i64` parameters and an `i64` result, integer/boolean expressions, addition/subtraction/multiplication, signed integer comparisons, `if`, single-binding `let`, unary source calls (including direct and mutual recursion), forward function references and explicit function pointers. This is an executable integration point, not full Coil compatibility. Next expand function signatures and expressions in this same path, then connect modules, types and expansion. Standalone object/executable output, full diagnostics and self-hosting remain unfinished.

The command accepts one integer per declared parameter. For example, `build/coil-rewrite run tests/compiler/integer-functions.coil weighted 1 2 3` returns `123`, and selecting `forty-two` with no arguments returns `42`.
