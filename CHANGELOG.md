# Changelog

All notable changes to Burl are recorded here. This file *is* the evidence
behind the compatibility covenant in SPEC.md: from 1.0 onward, nothing may
appear in the "Changed" or "Removed" sections that breaks a correct program
without a two-major-version deprecation.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.0] - 2026-11-24

First public release. Everything below is "Added" by definition.

### Added

- Core values: `nil`, `bool`, `number` (64-bit IEEE 754), `string`,
  `list`, `map`, `fn`.
- Statements: `let`/`const` declarations, `fn`, `if`/`else if`/`else`,
  `while`, `for-in`, `return`, `break`, `continue`, blocks.
- First-class functions with closures; fresh loop variables per iteration.
- String interpolation: `"total: {a + b}"` with full expression grammar,
  escapes `\n \t \r \\ \" \{ \}`, and `+` string concatenation.
- Optional runtime-checked type hints across the fixed vocabulary
  `number string bool nil list map fn any` (SPEC.md sec. 8).
- Lean standard library: `print input len type push pop range join keys
  values has split upper lower str num int abs min max floor round random
  read write clock`.
- Truthiness rules and strict equality (`0 == false` is `false`).
- Loud error behavior: line-numbered errors, non-associative comparisons,
  out-of-bounds indexing fails, division by zero fails.
- REPL with multiline input and auto-print; CLI: `python -m burl
  [program.burl]`.
- MIT license; test suite in `tests/`; examples in `examples/`.

### Compatibility

- 0.x versions may still change; all changes will be in this file.
- The compatibility covenant begins at 1.0.
