# Validation of the GPS-only cleanup

Validated on the laptop on 2026-11-11:

- Rust unit/integration tests: 9 passed, including a local mock NTRIP caster.
- Python regression tests: 4 passed.
- Raspberry Pi compile check: `cargo check --locked --all-targets --target aarch64-unknown-linux-gnu` passed.
- Native executable builds; `--help` succeeds and a nonexistent GPS device returns an explicit error.
- Optional PyGPSClient 1.8.0 installs and imports successfully (no live GUI/receiver test).
- Active Python sources parse successfully; `git diff --check` passes.

Rust tests were executed with an isolated Windows GNU toolchain and LLVM linker.
The target compile check does not execute code on a Pi or produce a linked Pi binary.
No live GPS, outdoor satellite, NTRIP service, or RTK Fixed test was performed.
Build and test on the Pi using PI_TRANSFER.md, then validate with the actual receiver.

The package is source-only, excludes historical archives and generated files,
and installs beside the existing ~/MAARCO installation as ~/SSAILOR_gps.
These checks validate the GPS cleanup; consult Git history for its publication status.
