# Changelog

All notable changes to Burl are recorded here. This file *is* the evidence
behind the compatibility covenant in SPEC.md: from 1.0 onward, nothing may
appear in the "Changed" or "Removed" sections that breaks a correct program
without a two-major-version deprecation.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.3.0] - 2026-11-24

### Added

- **The static checker** (SPEC.md 12, ROADMAP v0.3 "Iron"): `burl check
  program.burl [more.burl ...]` reads the optional type hints of SPEC.md 8
  and reports every problem provable from the source, with `file:line`
  prefixes and multi-error output. Advisory, never load-bearing: no false
  positives, the interpreter is unchanged.
  - Catches: unknown names, duplicate definitions, redefining builtins at
    the top level, arity errors, calls of non-callables, builtin argument
    types, hint mismatches (initializers, assignments, arguments, returns),
    operators given operands they reject, misplaced
    `break`/`continue`/`return`; warns on unused `let` bindings.
  - `tests/bad/`: a corpus of 12 planted-bug programs, each naming the
    diagnostics it must earn.
  - CI now runs the checker over all of `examples/` on every push.

## [0.2.0] - 2026-11-24

### Added

- `examples/adventure.burl` — "Vinland", a small text adventure exercising
  maps, closures, interpolation, and `input` (added between 0.1.0 and this
  release, covered by tests).
- **Modules** (SPEC.md 11): `import(path)` loads another Burl file and
  returns a map of its `fn` and `const` declarations. Relative paths resolve
  against the main program's directory. Modules run once; repeated imports
  return the same map; circular imports are loud errors naming the chain;
  plain `let` bindings stay private to the module.
- String tools: `slice(s, start, end)`, `find(s, sub[, start])` (returns -1
  when absent), `contains(s, sub)`, `replace(s, old, new)`, `trim(s)`.
- New example `examples/riddle.burl` (with the shared module
  `examples/lib/saga.burl`) exercising imports, `input`, string tools.

### Changed

- `input()` now returns `nil` at end of input (previously, programs reading a
  closed stdin looped forever on empty strings). Callers that never reach end
  of input are unaffected.
- Map literals may span lines (previously only map literals fully contained
  on one line parsed).

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
