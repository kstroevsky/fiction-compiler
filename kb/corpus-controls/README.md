# Literature controls

This directory holds rights-cleared literary controls used to test the framework against work that was
not generated for the compiler. A control is a stress test, not a gold label for universal quality.

Each control must have a title-specific `fiction-corpus` source entry whose structured `rights` record
allows full-text use in EU/DE. The control manifest binds exact source bytes and analyst-created scene
segments by SHA-256, records whether segmentation comes from the author or from analysis, and keeps
manual story-format limitations separate from deterministic linter output.

Critic evidence is never inferred from the reputation of the work. If no live critic was run, the
manifest and report say so explicitly.
