# Contributing to Burl

Thank you for considering work on the language itself. Burl has an unusual
governing document: [SPEC.md](SPEC.md), especially its
[compatibility covenant](SPEC.md#the-compatibility-covenant-binding-on-all-future-versions).
Read it first — most contribution questions are answered by it.

## The rules that decide every PR

1. **Correct programs never break.** If your change could alter the meaning
   of any program that is correct under the current spec, it needs a
   deprecation cycle (see the covenant) and an entry under "Changed" in
   [CHANGELOG.md](CHANGELOG.md).
2. **The spec wins.** If code and SPEC.md disagree, that's a bug in the
   interpreter. Fix the interpreter, or fix the spec *deliberately* and
   separately.
3. **New features must pay rent.** Adding is always covenant-legal, but
   "simple" is the product. A feature needs a case that existing features
   cannot handle well, and should compose with value semantics rather than
   introduce a special form.
4. **Errors say what to do.** Every user-facing message includes the line
   number and names the operation.

## How to contribute

```
git clone https://github.com/vanmassey/burl
cd burl
python -m unittest discover -s tests   # must be green before you start
```

- Language changes: propose in an issue showing example programs enabled,
  disabled, or broken — then spec change, then implementation, then tests.
- Bug fixes: failing test first, then the fix.
- The full matrix (3 OSes x 2 Python versions) runs in CI and must pass.

## Layout

See the layout table in [README.md](README.md). `values.py` is imported by
both `interpreter.py` and `builtins.py` — keep it free of imports from
either.
