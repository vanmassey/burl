# Burl

A small, compatible scripting language — simple like Linux, forward-minded
like its author, and designed to be equally pleasant for humans and AI to
write.

[Website](https://vanmassey.github.io/burl/) · [Spec](SPEC.md) ·
[Roadmap](ROADMAP.md) · [Changelog](CHANGELOG.md)

```burl
fn greet(name) {
    return "Hello, {name}!"
}

for name in ["Ada", "Grace", "Linus"] {
    print(greet(name))
}
```

## Quick start

```
python -m burl examples/fib.burl        # run a program
python -m burl check examples/fib.burl  # check it before running it
python -m burl examples/adventure.burl  # play the tiny saga "Vinland"
python -m burl                          # start the REPL
python -m unittest discover -s tests    # the behavior contract, as tests
```

No dependencies beyond Python 3.8+. Or install it as a command:

```
pip install .          # from a clone (PyPI: pip install burl-lang)
burl examples/fib.burl
burl check examples/fib.burl
```

[![CI](https://github.com/vanmassey/burl/actions/workflows/ci.yml/badge.svg)](https://github.com/vanmassey/burl/actions/workflows/ci.yml)
Every push runs 88 tests on 3 OSes × 2 Python versions, upgrades to the
installed package, and runs `burl check` over every example.

## The five commitments

1. **Compatible.** From 1.0 onward a correct program never breaks, never
   changes meaning. The [compatibility covenant](SPEC.md#the-compatibility-covenant-binding-on-all-future-versions)
   in the spec is binding on all future versions.
2. **Simple.** One spec file, one dependency-free implementation package.
   Exactly one obvious way to do everything.
3. **Forward-minded.** Optional type hints defined in 0.1 already pay off:
   the static checker (`burl check`, SPEC.md 12) reads them today. Builtins
   are plain values, so modules became values without grammar changes.
4. **For humans and AI.** Braces, newlines, one expression grammar. No
   significant whitespace, no context games. Errors name the line and the
   fix.
5. **Easy.** The whole language fits in your head: seven value types, one
   declaration form each, ~30 honest builtins.

## Language in 60 seconds

```burl
// Values: nil, bool, number (one 64-bit float), string, list, map, fn
let name = "world"           // mutable
const pi = 3.14159           // immutable
let counts: map = { "a": 1 } // optional type hints, runtime-checked

// Control flow
if n % 2 == 0 { print("even") } else if n == 1 { print("one") } else { print("odd") }
while len(items) > 0 { pop(items) }
for word in split(text, " ") { print("{word}: {len(word)} chars") }

// Functions close over their scope; they are plain values
fn make_counter() {
    let n = 0
    return fn() {
        n = n + 1
        return n
    }
}

// Strings interpolate any expression (nested quotes included)
print("Status: {ok and "ready" or "waiting"}")

// Modules are values too (SPEC.md 11)
const saga = import("lib/saga.burl")
saga.banner("RIDDLES OF THE NORTH")

// Hints are optional; `burl check` reads them, nothing else changes
fn double(n : number) : number {
    return n * 2
}
```

See [SPEC.md](SPEC.md) for the full language contract — grammar, semantics,
the standard library, and the stability rules that make upgrades safe — and
[ROADMAP.md](ROADMAP.md) for where the language is headed and what ships in
each version.

## Layout

```
burl/            the implementation (no dependencies)
  errors.py      all error types and their messages
  lexer.py       source -> tokens (with string interpolation)
  parser.py      tokens -> AST
  values.py      shared value machinery: truthiness, formatting, hints
  interpreter.py the tree-walking evaluator
  checker.py     the static checker ("burl check"; advisory, never a gate)
  builtins.py    the lean core standard library
  __main__.py    CLI + REPL
examples/        small, readable programs (all pass `burl check` in CI)
tests/           the language's behavior, as executable contract
tests/bad/       planted bugs the checker must catch
docs/            the one-page website (GitHub Pages)
```

## The voyage

Shipped: **0.1** first light · **0.2** Stone (modules) · **0.3** Iron (the
checker). Coming next, per the
[roadmap](ROADMAP.md#the-voyage):

- **0.4 Bootstrap** — the interpreter rewritten in Burl itself
- **0.5 Keel** — a bytecode VM, diffed against the tree-walker in CI
- **0.6 Dragon** — native executables, the compiler compiling itself
- **0.7 Provisions** — `io`, `json`, `args` standard modules
- **1.0 Landfall** — via a deliberate, long release-candidate: burst the
  features, then freeze and shake

## Known limits (by design, ahead of 1.0)

- Numbers are 64-bit floats; integers above 2^53 lose precision.
- String interpolation expressions cannot span lines.
- `for-in` lists/strings/maps only; no ranges-as-filters yet.
- No functions attached to maps (`m.method()`); free functions only.
- The checker proves what statics can prove; it never blocks a program.
