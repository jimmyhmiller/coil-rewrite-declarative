# Design notes for a fresh implementation

## References worth reading together

These paths assume the projects are sibling checkouts.

- Start with [Stogir's package manifest](../coil-stogir-declarative/Coil.toml). Follow a module such as `backend.nodes` from the module table to its authored source, then follow its extension to the reader. This is the build experience to reproduce. Consult the [native backend reference](../coil/docs/reference/NATIVE_BACKEND.md) for the backend already maintained with Coil.
- Read the [high-level language project](../high-level-lang/README.md), then compare its [rule syntax](../high-level-lang/src/languages/rules.syntax) with [an attribute specification](../high-level-lang/src/bundle/early.attrs). Look for decisions an author can express once and execution details the language compiler can derive. Choose languages for the actual problems in Coil.
- Use Coil's [language guide](../coil/docs/reference/LANGUAGE_GUIDE.md) and [project guide](../coil/docs/reference/PROJECTS.md) for language behavior and reader packaging. Follow [the reference pipeline](../coil/src/compiler/pipeline.coil) and [expander](../coil/src/compiler/frontend/expander.coil) when behavior depends on phase ordering.

## A first design exercise

Take a function that calls another function and returns its result. Write down what a contributor should see in the compiler source to answer four questions. How is the declaration read? When does the callee become visible? How is its signature constructed and its result checked? How does a checked call reach the retained backend?

Design just enough language vocabulary to express those answers. Build the source through registered readers and exercise a forward call, a wrong return type and a successful native call. A change to the signature rule should be a reviewable edit under `src/`. This exercise tests the architecture early. It leaves most of Coil still to implement.

## What the completed compiler must demonstrate

| Area | Evidence to collect |
| --- | --- |
| Reading and modules | Real packages and workspaces import custom-language files. Guest diagnostics point into the authored source. |
| Expansion | Reference cases cover macro-produced declarations and imports, staged execution, transform ordering and semantic-model availability. |
| Checking and specialization | Compare acceptance, rejection, checked forms and specialized output for real programs using traits, generics, sums, ownership and foreign calls. |
| Execution and tools | Exercise the existing native backend, LLVM and Wasm paths, object files, debug information, JIT sessions, CLI commands and installed artifacts against the corresponding reference suites. |
| Self-hosting | The replacement builds its readers and its own source, then that compiler repeats the build and passes the same behavioral checks. |
| Size and performance | Pin revisions and workloads. Count authored compiler, DSL machinery and backend source. Record cold and warm compilation time, peak memory and generated-program performance at comparable optimization settings. |

Use the [reference test guide](../coil/docs/reference/COMPILER_TESTS.md) to locate existing suites. Record the individual outcomes and workloads behind a result. A small native example demonstrates only the behavior it exercises.
