# Burl Roadmap

The companion to [SPEC.md](SPEC.md). The spec says what the language *is*;
this file says what it is *becoming*. Each version below has a definition of
done that CI (or you, in a terminal) can check — no vibes-based shipping.

## Governing rules for every release

1. **One theme per release.** A version either does a thing or it doesn't.
2. **Spec + tests + changelog in the same commit** as the implementation.
3. **Tests green in CI first** — 3 OSes, 2 Python versions, plus examples.
4. **Nothing ever removes or redefines existing behavior.** The covenant in
   SPEC.md 1 governs; this roadmap is intent, never license to break.
5. Bootstrapping and self-hosting work runs "build what we need, then stop."
   Features that don't serve a version's theme wait for a later version.

## The voyage

| Version | Theme | Status |
|---------|-------|--------|
| 0.1.0 | First light | ✅ released 2026-11-24 |
| 0.2 | Stone (modules) | ✅ released 2026-11-24 |
| 0.3 | Iron (the checker) | next |
| 0.4 | **Bootstrap** (Burl in Burl) | |
| 0.5 | Keel (bytecode VM) | |
| 0.6 | Dragon (native code) | |
| 0.7 | Provisions (std library) | |
| 1.0 | Landfall (the covenant) | the destination |

## v0.2 — Modules as values  ✅ shipped

*Theme: programs bigger than one file.*

- `import(path)` builtin: loads another `.burl` file, runs it in a fresh
  top scope, returns a map of its `fn`/`const` declarations. No import
  statements, no module syntax — imports are ordinary declarations,
  exactly as SPEC.md 11 promised.
- File loading errors follow the language's existing honesty: loud
  `Runtime error` with the path and line.
- String tools the lexer-writer immediately needs: `slice(s, start, end)`,
  `find(s, sub, start?)`, `contains`, `replace`, `trim`. Each is one
  honest builtin, not a micro-API.
- **Shipped as:** `examples/riddle.burl` + shared module
  `examples/lib/saga.burl` exercise the whole feature (with `hint` using
  `slice`); module caching, circular-import errors, and every string tool
  are covered in `tests/test_modules.py`.

## v0.3 — The static checker

*Theme: hints earn their keep before anything else is added.*

- `burl check program.burl`: a checker, shipped with the interpreter,
  reading the type-hint vocabulary SPEC.md 8 defined in 0.1 — no new
  annotation syntax at all.
- Level 1: annotation-vs-annotation (call sites, assignments, returns).
  Level 2: inference for locals assigned once.
- **Done when:** the checker finds every planted type bug in a corpus of
  deliberately broken programs in `tests/bad/`, and `burl check` passes on
  all of `examples/`.

## v0.4 — Bootstrap: the interpreter, rewritten in Burl

*Theme: Burl runs Burl. The language starts to carry its own weight.*

- A complete interpreter written *in Burl*: `src/lex.burl`, `src/parse.burl`,
  `src/interp.burl`, driven by the Python host's runtime
  (`python -m burl src/burl.burl program.burl`).
- Slowness is acceptable (dozens of times slower is fine for v0.4);
  correctness and language ergonomics are not.
- **Bootstrapping has happened when, reflexively, one satisfied chain runs
  the whole test suite: a host runs (Burl interpreter) which runs
  (Burl interpreter) which runs (each test program) with identical
  output.** Anything less is not bootstrap.
- Bootstrap is a discovery phase, not a feature sprint: expect post-0.2 and
  post-0.3 holes found *while writing it* — those fixes, not new features,
  define 0.4. Expect it to also produce the spec's honest omissions list
  (integer ops beyond 2^53, slicing, debugging hooks), which becomes 0.5/0.6
  material.
- **Done when:** a CI job runs the reflexive suite; Python remains only a
  bootstrap shim, never a semantic reference anymore.

## v0.5 — Bytecode VM

*Theme: speed without changing meaning.*

- A compiler (tree → bytecode) and stack VM, also written in Burl, added to
  `src/`. The tree-walker from 0.4 stays as the *definition of correct*:
  CI runs both engines and diffs their outputs on every example and test.
- **Done when:** the VM is ≥10x the tree-walker on the benchmark suite and
  output-diff CI is green (the interpreter must not outsmart the interpreter).

## v0.6 — Native executables

*Theme: Burl without the host.*

- A Burl-written compiler emitting C from the 0.5 bytecode, so any C
  compiler makes standalone binaries; `burl build program.burl`.
- **Done when:** the compiler compiles *itself* (full self-hosting) and the
  resulting binary passes the whole test suite — no Python anywhere.

## v0.7 — Provisions

*Theme: a real standard library, no language changes.*

- `io`, `json`, `args` modules in Burl (via 0.2's module system), plus the
  package-usage conventions for sharing Burl source. Zero grammar changes —
  everything is values.

## v1.0 — Landfall, via a long release-candidate

*Theme: the promise becomes law, and stays it.*

The kernel model: burst the features, then freeze and shake. Phases in order:

**1.0-rc1 — feature freeze.** The grammar and the hint vocabulary are
untouchable from here on. Entry ritual: the *full deficiency ledger* is
filed and public — every known spec ambiguity, REPL papercut, error-message
gap, and CI flake. `rc` length is defined by the ledger, never by a date;
"long" is the default.

**rc2 ... rcN — fixes and evidence only.**
- Allowed: fixes, and additions to existing contracts (new builtins,
  error-message improvements). Never grammar, never removals.
- Each rc shrinks the ledger. A blocker extends rc; a non-blocker may be
  tracked to 1.0.x (fixes and additions never break programs).
- During rc the language is *lived in*, not left still: the examples are
  exercised, real tools are written in Burl, the checker runs over the
  whole corpus. A frozen grammar no one uses is evidence of nothing.

**1.0 ships when every gate holds:**

- [ ] Zero open release blockers on the ledger.
- [ ] No spec grammar change since rc1 — the six-month stability window
      (SPEC-adjacent, see 0.1's covenant) is satisfied by the rc's own
      calendar as a side effect of living in it, not as a separate wait.
- [ ] Bootstrap chain (0.4+) and native build (0.6+) green in CI.
- [ ] Static checker clean on the whole corpus.
- [ ] Full docs: spec, stdlib reference, tutorial, style guide.

Discipline note, kept from the plan above: no promotion to 1.0 off rc3
because enthusiasm peaks. Late fixes are cheap; post-1.0 grammar fixes
cost a deprecation cycle forever.

After 1.0: additions stay cheap; changes and removals need the
deprecation cycle. A burl is the English word for a rounded knot in wood —
small, dense, and prized by carvers for holding its shape. Fitting, for a
language that plans to outlive its weavers.
