# The Burl Language Specification — v0.1

> "Compatibility is a promise you keep every day, not a document you write once."
> — the operating principle of this spec

## 1. Design philosophy

Burl is a small, general-purpose scripting language with five commitments:

1. **Compatible.** From version 1.0 onward, a correct Burl program never breaks
   and never changes meaning on upgrade. Ever. Pre-1.0 (0.x) versions may
   still change, and every change is listed in the changelog.
2. **Simple.** The spec fits in one file, the reference interpreter in one
   package with no dependencies. There is exactly one obvious way to do
   something. Features must pay rent.
3. **Forward-minded.** Nothing in the design closes a door we will need:
   optional type hints are defined now so a static checker can arrive later
   without changing programs; every builtin is a plain value so modules become
   values later; strings interpolate so formatting never becomes another
   mini-language.
4. **For humans and AI both.** Regular, brace-delimited, newline-terminated
   syntax that survives copy-paste and diffing. No significant whitespace. No
   context-dependent parsing. Every error names its line and says what to do.
5. **Easy.** You should be able to hold the whole language in your head.

### The compatibility covenant (binding on all future versions)

- **Never remove or change the meaning of existing syntax or builtins.**
- **Never change the type of a result a program relies on.**
- **Adding is allowed at any time** (new builtins, new optional keywords,
  new hints). Additions cannot break a correct program.
- **Deprecation is a two-way street:** a deprecated feature must keep working
  for at least two major versions and print a warning first.
- The spec is the contract, not the implementation. Where they differ, the
  spec wins, and that is a bug in the interpreter.

## 2. Lexical structure

| Element   | Rule                                                             |
|-----------|------------------------------------------------------------------|
| Comments  | `//` to end of line. No block comments in v0.                     |
| Newlines  | A statement ends at a newline. Inside `(...)`, `[...]`, and interpolation, newlines are whitespace. Semicolons may separate statements on one line but are not required and not idiomatic. |
| Identifiers | `[a-zA-Z_][a-zA-Z0-9_]*`. Case-sensitive.                       |
| Keywords  | `and or not let const fn if else while for in return break continue true false nil` |
| Operators | `+ - * / % == != < <= > >= = ( ) { } [ ] , . :`                  |
| Strings   | Double-quoted, `"..."`, escapes `\n \t \r \\ \" \{` and `\}`. `{expr}` inside a string is interpolated (§7). |
| Numbers   | `[0-9]+(\.[0-9]+)?` with optional leading `-` handled as unary minus. One number type: 64-bit IEEE 754 (§5.1). |

A number's printed form is the shortest exact representation: `3` not `3.0`.

## 3. Grammar (informal, top level to statement)

```
program    := statement*
statement  := letdecl | constdecl | fndecl | if | while | for
            | "return" [expr] | "break" | "continue"
            | block | expr

letdecl    := "let" IDENT [":" type] "=" expr
constdecl  := "const" IDENT [":" type] "=" expr
fndecl     := "fn" IDENT "(" params ")" [":" type] block
if         := "if" expr block ("else" ("if" ... | block))?
while      := "while" expr block
for        := "for" IDENT "in" expr block
block      := "{" statement* "}"
type       := IDENT            // number, string, bool, nil, list, map, fn, any

params     := [IDENT [":" type] [","]* ...]
```

Expressions, loosest binding first:

```
expr     := or
or       := and ("or" and)*
and      := not ("and" not)*
not      := "not" not | compare
compare  := add (("=="|"!="|"<"|"<="|">"|">=") add)?
add      := mul (("+"|"-") mul)*
mul      := unary (("*"|"/"|"%") unary)*
unary    := "-" unary | postfix
postfix  := primary (call | index | member)*
primary  := NUM | STRING | IDENT | "true" | "false" | "nil"
          | "(" expr ")" | list | map | fnexpr
list     := "[" [expr ("," expr)*] [","] "]"
map      := "{" [STRING ":" expr ("," STRING ":" expr)*] [","] "}"
fnexpr   := "fn" "(" params ")" [":" type] block
call     := "(" [expr ("," expr)*] ")"
index    := "[" expr "]"
member   := "." IDENT
```

Note: `compare` is non-associative — `a < b < c` is a parse error, not a
silent `(a < b) < c`. `a < b and b < c` is the way, and it's clearer.

## 4. Names and scope

- `let` declares a mutable binding in the current block; redeclaring in the
  same block is an error. Inner blocks may shadow outer names.
- `const` declares an immutable binding; assignment to it is an error.
- Function parameters behave like `let`.
- Blocks create scopes. `if`/`while`/`for`/`fn` bodies are blocks.
- A `for` loop variable is fresh per iteration, so closures created in the
  body capture each value, not the last one.
- Reading a name that is declared nowhere is an error: `Undefined name 'x' (line N)`.

## 5. Values and types

### 5.1 number

One number type, 64-bit IEEE 754, like Lua and JavaScript. Integer-valued
numbers print without a decimal point. Consequences, by design:

- `3 / 2` is `1.5`. There is no surprise division.
- Counters up to 2^53 are exact — far beyond a human's patience.
- `int(n)` truncates toward zero when you truly need an integer op.

### 5.2 bool, nil

`true`, `false`, `nil` (the absent value). Truthiness: `false`, `nil`, `0`,
`""`, `[]`, `{}` are false; everything else is true. `0 == false`? **No.**
Truthiness only exists in conditions; equality is strict across types:
`0 == false` is `false`, `1 == true` is `false`.

### 5.3 string

Immutable, UTF-8, and interpolated: `"Hello, {name}!"`. `\{` produces a
literal `{`. Indexing gives 1-character strings. `len` counts characters.

### 5.4 list

Mutable, heterogeneous, passed by reference. `list[0]` indexes;
out-of-bounds indexing is an error (no silent nil — a bug should yell).
Negative indices are errors in v0; `len(list)-1` is the way.

### 5.5 map

Mutable, string-keyed, insertion-ordered. Literal and access forms:

```
let person = { "name": "Ada", "age": 36 }
print(person.name)     // dot form; error if the key is absent
print(person["name"])  // bracket form, same thing
person.city = "London" // assignment creates the key
```

### 5.6 fn

Functions are first-class values and close over their defining scope
(§6.2). Comparing two functions with `==` compares identity.

## 6. Control flow and functions

### 6.1 Conditions

Any expression is allowed; truthiness is §5.2's list. `else if` chains are
written `else if`, not `elif`, not `elsif`.

### 6.2 Functions and closures

```
fn add(a, b) {
    return a + b
}
fn make_counter() {
    let n = 0
    return fn() {
        n = n + 1
        return n
    }
}
```

- `return nil` if no return. Fallthrough returns `nil`.
- Recursion works, including mutual recursion (declared names are visible
  inside their own and later bodies in the same block).

### 6.3 for-in

`for x in v` iterates: lists by element, strings by character, maps by key.
`break` / `continue` work in `while` and `for`.

## 7. String interpolation

At lex time, `"...{expr}..."` becomes a sequence of literal and expression
parts; the expression is parsed with the full expression grammar and
evaluated with `str()` semantics. Any expression, any nesting, computed
right where you read it:

```
print("Sum of 1..100 is {sum(range(1, 101))}")
print("Person: {person.name}, age {person.age + 1}")
```

Plain `+` also concatenates two strings. Interpolation is preferred: it
reads better and formats values automatically.

## 8. Optional type hints

Hints exist so that a future static checker (and today's runtime) share one
vocabulary. In v0 they are **checked at runtime**:

- On a `let`/`const`, the initializer must satisfy the hint, and every later
  assignment is checked.
- On a parameter, each call argument is checked.
- On a return type, the returned value is checked (missing `return` checks
  `nil`, so declare `: nil` or return for non-nil results).

A value satisfies a hint when: the hint is `any`; or its type equals the
hint name; or the hint is `number` and the value is a number (int and float
are both `number`); or the hint is `list`/`map`/`fn` and the value has that
type. `number`, `string`, `bool`, `nil`, `list`, `map`, `fn`, `any` are the
recognized hints; others are a parse error — the checker's vocabulary is
fixed here, early, on purpose.

Bad: `let x: number = "hi"` fails at runtime with a clear message. That is
the contract until static checking exists; it never silently changes.

## 9. Standard library (lean core)

Builtins are plain global values (~30 of them):

| Category | Functions |
|----------|-----------|
| Output / input | `print(...)` `input([prompt])` — `input` returns the line as a string, or `nil` at end of input |
| Length / type | `len(v)` `type(v)` |
| Lists | `push(list, v)` `pop(list)` `range(a[, b[, step]])` `join(list, sep)` |
| Maps | `keys(map)` `values(map)` `has(map, key)` |
| Strings | `split(s, sep)` `upper(s)` `lower(s)` `str(v)` `slice(s, start, end)` `find(s, sub[, start])` `contains(s, sub)` `replace(s, old, new)` `trim(s)` |
| Numbers | `num(v)` `int(n)` `abs(n)` `min(...)` `max(...)` `floor(n)` `round(n)` `random()` |
| Calls | `apply(f, args)` — calls any function value with a list of arguments |
| Files / time / modules | `read(path)` `write(path, text)` `clock()` `import(path)` |

Notes: `push` returns the list (so it chains); `pop` errors on empty;
`range(a, b, step)` needs a positive step; `num("12.5")` is `12.5`,
`num("x")` is `nil` (parse failures are values, not crashes); `random()`
is in `[0, 1)`; `clock()` is milliseconds since the epoch, as a number;
`apply(len, ["hello"])` is `5`.

## 10. Errors

Every error message, including runtime errors, contains `line N` and names
the offending operation. Misuse is loud on purpose: fewer `nil`-sneaking
bugs, better messages for both humans and AI. Parse errors stop the
program before the first statement runs (no half-run).

## 11. Modules

Builtins are values; modules are, too. There is no import statement and no
module syntax — loading a module is calling a function:

```
let saga = import("lib/saga.burl")
saga.banner("RIDDLES OF THE NORTH")
```

- `import(path)` loads the file (relative paths resolve against the *main
  program's* directory, not the working directory), runs its top level in a
  fresh scope whose parent is the global scope, and returns a map.
- The map contains the module's `fn` and `const` declarations. Functions
  stay live: they close over the module scope. Plain `let` bindings stay
  private — module functions can mutate them (counters, caches); importers
  only see what was deliberately exported.
- A module's top-level code runs exactly once. `import` returns the *same*
  exported map on repeated imports of the same file.
- Circularity is a loud error naming the whole chain:
  `Circular import: a.burl -> b.burl -> a.burl`.
- Any file remains a runnable program. Modules are programs that export.

## 12. Tooling: `burl check`

The checker is part of the shipped tool, not part of the language. It reads
a program, applies the hint vocabulary of section 8, and reports every
problem it can *prove* from the source, with `file:line` prefixes:

```
burl check program.burl [more.burl ...]
```

- **Advisory, never load-bearing.** The checker is a lint, not a gate. The
  interpreter's behavior is unchanged by its existence, and a clean check
  promises nothing beyond what the language already does.
- **No false positives.** The checker is silent on any program the
  interpreter would run without error. When it cannot prove a claim, it
  says nothing: unknown types stay unknown, and a name used before its
  definition in the same file is not flagged (a closure may legitimately
  see it by call time).
- It reports, among others: unknown names, duplicate definitions, redefining
  builtins at the top level, arity errors at call sites, calls of
  non-callables, type mismatches wherever a hint meets a provable type
  (initializers, assignments, arguments, returns), operands the arithmetic
  and comparison operators reject, misplaced `break`/`continue`/`return`,
  and unused `let` bindings (as warnings).
- Exit code is 1 when errors are found, 0 otherwise; warnings never change
  the exit code.
