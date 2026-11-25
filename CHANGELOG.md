# Changelog

All notable changes to Burl are recorded here. This file *is* the evidence
behind the compatibility covenant in SPEC.md: from 1.0 onward, nothing may
appear in the "Changed" or "Removed" sections that breaks a correct program
without a two-major-version deprecation.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased] — toward 0.5.0 "Keel"

### Changed

- **SPEC.md 5.1 amended (LEDGER L-009, the release blocker resolved):**
  the language honors the engine's existing arithmetic, and the spec now
  documents it. One number type, two forms: integer literals are exact at
  any magnitude (`+ - * %` on integers compute exactly, e.g.
  `9007199254740993 * 2` is `18014398509481986`); a double result is a
  64-bit IEEE 754 float, contagious to later arithmetic, and `/` is
  always double. No program changes behavior — the covenant-safe direction:
  the spec was brought to the engine, never the reverse. The boundary is
  pinned by `tests/test_numbers.py` and a differential snippet in the
  bootstrap corpus, so the 0.5 VM can be diffed against an agreed
  semantics. README "Known limits" updated to match.
- Whole-valued doubles print as their exact integer at any magnitude
  (`values.py`): `print(18014398509481984.0)` was
  `1.8014398509481984e+16`, now `18014398509481984`, matching the amended
  printing rule "integer-valued values of either form print without a
  decimal point". Display-only change; the underlying double is
  unchanged.

### Added

- `tests/test_numbers.py`: the SPEC.md 5.1 number contract as tests —
  integer exactness, double contagion, cross-form comparison exactness,
  `int()` truncation, and the `number` hint accepting both forms.

## [0.4.0] - 2026-11-24

### Added

- **Bootstrap** (ROADMAP v0.4 "Bootstrap"): the Burl interpreter,
  rewritten in Burl. `src/lex.burl`, `src/parse.burl`, `src/interp.burl`,
  `src/kernel.burl` (boot, run, and level-chaining machinery), and
  `src/burl.burl` (the driver). All five pass `burl check`. The engine's
  tokens, ASTs, output, and error messages are byte-identical to the
  Python host's across the whole corpus — 30 semantic snippets plus the
  example programs, errors included — verified differentially in
  `tests/test_bootstrap.py`.
- `apply(f, args)` builtin (SPEC.md 9): calls any function value with a
  list of arguments. How the Burl engine, which cannot reach the host
  builtins by name while interpreting, still calls them. Under the
  bootstrapped engine, `apply` is the engine's own wrapper — it also
  accepts Burl-defined functions, which the host builtin cannot run —
  and host functions fall through to the host builtin. Two divergences
  found while wiring the corpus are filed as LEDGER.md L-010/L-011
  (error lines of builtin-internal errors under the engine; the `type`
  of an engine-defined function), both 0.5 material.
- The Python host now runs bootstrap-scale programs on a dedicated
  large-stack thread (`burl/__main__.py`); interpreting an interpreter
  multiplies Python call depth. Python-side shim only — the language is
  unchanged.

### Changed

- New entry point: `python -m burl src/burl.burl < program.burl` runs a
  program through the reflexive chain
  host → (Burl interp) → (Burl interp) → program. The driver reads its
  program from stdin because argv is still 0.7 material; `read()` stays
  working-directory relative (SPEC.md 9), so run from the repo root.
- Depth 2 exceeds the roadmap's depth-1 definition of bootstrap. It
  re-parses the entire engine through the engine (expected: minutes per
  run), so the default test suite proves depth 1 end to end and the
  depth-2 chain plus driver run only with `BURL_SLOW_TESTS=1`.

### Performance

- Stated honestly: the Burl engine is dozens of times slower than the
  Python host, and each chained level multiplies the cost. Correctness
  and identical behavior were the 0.4 bar; speed is the bytecode VM's
  (0.5) without changing meaning.

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
