# Compiler implementation boundary

The user explicitly requires the replacement Coil compiler to be authored in custom languages in this directory.

- Put compiler semantics here: syntax, declarations, binding, expansion, type checking, specialization, lowering and orchestration.
- Do not implement the replacement frontend, checker or compiler driver as handwritten Coil and call that the compiler.
- Extend a language when a necessary compiler operation cannot yet be expressed. Keep its compiler general enough to explain the operation; do not hide a Coil compiler implementation in templates or hardcoded language handlers.
- Coil is the bootstrap implementation language for language compilers and small runtime mechanisms. Generated Coil is an output artifact, not the authored compiler source.
- Existing compiler-specific adapters outside this directory are migration debt, not an architectural precedent.
- Validate progress through the integrated compiler accepting real Coil source and producing correct output. Keep unsupported behavior explicit. Full replacement and self-hosting remain the objective.

Register compiler languages as Coil readers and import their sources through Coil.toml. Implement tooling and validation in Coil. Build the compiler with coil build from the root.
