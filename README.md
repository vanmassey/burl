# Burl

A small, compatible scripting language — simple like Linux, forward-minded
like its author, and designed to be equally pleasant for humans and AI to
write.

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
python -m burl examples/fib.burl   # run a program
python -m burl                     # start the REPL
python -m unittest discover -s tests
```

No dependencies beyond Python 3.8+. Or install it as a command:

```
pip install burl-lang    # when published to PyPI (or: pip install . from a clone)
burl examples/fib.burl
```

[![CI](https://github.com/vanmassey/burl/actions/workflows/ci.yml/badge.svg)](https://github.com/vanmassey/burl/actions/workflows/ci.yml)

## The five commitments

1. **Compatible.** From 1.0 onward a correct program never breaks, never
   changes meaning. The [compatibility covenant](SPEC.md#the-compatibility-covenant-binding-on-all-future-versions)
   in the spec is binding on all future versions.
2. **Simple.** One spec file, one dependency-free implementation package.
   Exactly one obvious way to do everything.
3. **Forward-minded.** Optional type hints defined today, static checker
   compatible tomorrow. Builtins are plain values, so modules become values
   without grammar changes.
4. **For humans and AI.** Braces, newlines, one expression grammar. No
   significant whitespace, no context games. Errors name the line and the
   fix.
5. **Easy.** The whole language fits in your head: seven value types,
   one declaration form each, ~24 builtins.

## Language in 60 seconds

```burl
// Values: nil, bool, number (one 64-bit float), string, list, map, fn
let name = "world"          // mutable
const pi = 3.14159          // immutable
let counts: map = { "a": 1 } // optional type hints, runtime-checked

// Control flow
if n % 2 == 0 { print("even") } else if n == 1 { print("one") } else { print("odd") }
while len(items) > 0 { pop(items) }
for word in split(text, " ") { print("{word}: {len(word)} chars") }

// Functions close over their scope; they are plain values
fn make_counter() {
    let n = 0
    return fn() { n = n + 1; return n }
}

// Strings interpolate any expression
print("Status: {ok and "ready" or "waiting"}")
```

See [SPEC.md](SPEC.md) for the full language contract — grammar, semantics,
the standard library, and the stability rules that make upgrades safe.

## Layout

```
burl/            the implementation (no dependencies)
  errors.py      all error types and their messages
  lexer.py       source -> tokens (with string interpolation)
  parser.py      tokens -> AST
  values.py      shared value machinery: truthiness, formatting, hints
  interpreter.py the tree-walking evaluator
  builtins.py    the lean core standard library
  __main__.py    CLI + REPL
examples/        small, readable programs
tests/           the language's behavior, as executable contract
```

## Roadmap

- **0.x** — can change, changes are always recorded.
- **1.0** — the compatibility covenant takes over: programs never break.
- Later (all without breaking 1.0 programs): modules-as-values, a static
  type checker over the existing hint vocabulary, a bytecode VM.

## Known limits of 0.1 (by design, ahead of 1.0)

- Numbers are 64-bit floats; integers above 2^53 lose precision.
- String interpolation expressions cannot span lines.
- `for-in` lists/strings/maps only; no ranges-as-filters yet.
- No functions attached to maps (`m.method()`); free functions only.
