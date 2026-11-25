# The Burl deficiency ledger

ROADMAP v1.0-rc1 requires an entry ritual: *the full deficiency ledger is
filed and public — every known spec ambiguity, REPL papercut, error-message
gap, and CI flake.* This is that ledger, started early so nothing gets
forgotten between now and the freeze. rc length is defined by this file,
never by a date: **a blocker extends rc; zero open release blockers opens
1.0.**

An entry is not a complaint; it is a commitment to resolve. Everything here
is knowable without reading the implementation — a repro or a spec quote
must be enough for a stranger to hit each item. Seed the ledger the moment
you notice a papercut; pruning it (fixing, or consciously tracking to
1.0.x) is what release candidates are for.

Fields: **ID** (never reused) · **Found** (version) · **Category** (spec ·
stdlib · tooling · errors · CI) · **Status** (`open` blocks 1.0 unless a
blocker says otherwise; `→ 1.0.x` is consciously deferred with reasons;
`fixed in N` with the release) · **Evidence** (repro or where it bites).

## Open

| ID | Found | Category | Status | Description | Evidence |
|----|-------|----------|--------|-------------|----------|
| L-001 | 0.1 | spec | open | Integers in float arithmetic lose precision beyond 2^53 (one 64-bit float, by design). 0.4's bootstrap is expected to surface the honest omissions list; integer ops beyond 2^53 head it. | SPEC.md 5.1; `9007199254740992 + 1.0` → `9007199254740992` |
| L-002 | 0.1 | spec | open | String interpolation expressions cannot span lines, so multi-line message building needs `join` or concatenation. | SPEC.md 7 (stated limit) |
| L-003 | 0.1 | spec | open | `for-in` iterates lists, strings, and maps; `range()` materializes eagerly and there are no ranges-as-filters (lazy `range.upto`, stepping, numeric loops over huge bounds). | README "Known limits" |
| L-004 | 0.1 | spec | open | No calls attached to maps (`m.method()`); method-style code needs free functions taking the map. Deliberate in v0 — recorded so the cost is lived in while the language is small. | README "Known limits" |
| L-005 | 0.3 | errors | open | Deep Burl recursion dies with a raw Python `RecursionError` traceback instead of a Burl error naming the line and offering the fix. A tree-walker on Python's stack has a real depth ceiling; the fix is shaping that failure, not removing the ceiling. | `fn spin(n) { return spin(n + 1) }` then `spin(1)` → traceback from `burl/interpreter.py` |
| L-006 | 0.3 | tooling | open | The REPL discards the whole buffered block on a runtime error: type three lines of an `if` block, make an error on the third, and all three lines are lost. | REPL in `burl/__main__.py` — `lines` resets before the error path |
| L-007 | 0.2 | stdlib | open | List concatenation is a hand-rolled loop (`fn concat(a, b, c)` in `benchmarks/sort.burl` is the canonical workaround). 0.7's provisions are the natural home for a decision — and a decision *not* to add anything is also a resolution. | No list→list concat builtin in SPEC.md 9 |
| L-008 | 0.3 | CI | open | The Python 3.8 legs are pinned to `ubuntu-22.04` because `ubuntu-latest` no longer builds 3.8. That runner image will eventually go unsupported; the pin needs a plan before it breaks a green main. | `.github/workflows/ci.yml` matrix comment |
| L-009 | 0.3 | spec | fixed in 0.5 | RESOLVED in favor of the engine: SPEC.md 5.1 now documents the two-form number type — integer literals are exact at any magnitude (`+ - * %` exact), doubles are 64-bit IEEE 754 and contagious to the result, `/` is always double. The engine's behavior was kept and the spec was brought to it; pinned by `tests/test_numbers.py` and a differential snippet in the bootstrap corpus. | SPEC.md 5.1; tests/test_numbers.py |
| L-010 | 0.4 | errors | open | Under the bootstrapped engine, a *builtin-internal* runtime error (e.g. `pop(3)`, `upper(3)`, a bad `apply`) carries the wrong line — the engine source's own `apply` call site, not the user program's — and escapes the engine's error channel as a host exception (the bootstrap driver then prints a Python traceback) instead of `burl: Runtime error at line N`. The engine pre-raises its own errors (arithmetic, indexing, arity, hints) correctly; only errors raised *inside* host builtins leak. The 0.5 VM, which owns dispatch, is the natural fix: pre-validate builtin arguments or capture the call line at the boundary. | host: `print(pop(3))` → `Runtime error at line 1`; depth-1 chain → line 1744 of `src/interp.burl` |
| L-011 | 0.4 | errors | open | `type()` of a Burl-defined function value disagrees across engines: host → `fn`; bootstrapped engine → `map` (engine functions are maps tagged `burlfn`; the exposed `type` is the host builtin, which only knows host functions). The engine's internal `i_type` already normalizes both to `fn`; the language-level builtin needs the same wrapper (or the VM's function representation). | `let f = fn(x) { return x }` `print(type(f))` → `fn` on the host, `map` via the depth-1 chain |

## → 1.0.x (consciously deferred)

*(none yet — entries move here with a reason, never by being deleted)*

## Fixed

| ID | Found | Category | Status | Description | Evidence |
|----|-------|----------|--------|-------------|----------|

*(none yet — the ledger is young. When an entry is fixed, it moves here with
the release that closed it, and the ID stays retired.)*
