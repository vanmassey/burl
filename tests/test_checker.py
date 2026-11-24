"""Tests for the static checker: burl check (SPEC.md 12, ROADMAP v0.3).

Two halves:
  - inline unit cases here;
  - the tests/bad/ corpus: every file there plants a bug and states the
    diagnostics it must earn, one per line, as
        # expect: <substring>
    The done-when from the roadmap: the checker finds every planted bug.
"""

import glob
import os
import unittest

from burl.checker import check_source


def errors(source):
    return [d for d in check_source(source) if d.severity == "error"]


def warnings(source):
    return [d for d in check_source(source) if d.severity == "warning"]


class CleanProgramTests(unittest.TestCase):
    """Anything the interpreter could run stays quiet (advisory default)."""

    CASES = [
        'print("hi")',
        "fn fib(n) {\n  if n < 2 {\n    return n\n  }\n  return fib(n-1) + fib(n-2)\n}\nprint(fib(10))",
        # Closures see names defined later in the enclosing scope.
        "fn h() { return data }\nlet data = 5\nprint(h())",
        # A function may have only the loop's break available.
        "while true {\n  fn g() { break }\n  break\n}",
        # Types can widen: let without hint accepts anything.
        'let x = 5\nx = "now a string"\nprint(x)',
        # Shadowing a builtin from a nested scope is legal.
        'fn f() { let type = 1\n  return type }\nprint(f())',
        # Reassigning a function name is legal.
        "fn f() { return 1 }\nf = 5\nprint(f)",
        # Interpreter-defined import has its arity and returns a map.
        # (The file read itself isn't attempted by the checker.)
        "let m = 1\nprint(len([m]))",
    ]

    def test_cases_are_clean(self):
        for source in self.CASES:
            with self.subTest(source=source):
                self.assertEqual(errors(source), [])
                self.assertEqual(warnings(source), [])


class ErrorTests(unittest.TestCase):
    def test_undefined_name(self):
        self.assertIn("Undefined name 'nope'", errors("print(nope)")[0].message)

    def test_undefined_name_in_interpolation(self):
        self.assertIn("Undefined name 'nope'", errors('print("{nope}")')[0].message)

    def test_call_arity_user_fn(self):
        found = errors("fn f(a) { return a }\nf(1, 2)")
        self.assertEqual(len(found), 1)
        self.assertIn("expects 1 argument(s), got 2", found[0].message)

    def test_call_arity_builtin(self):
        found = errors("len()")
        self.assertIn("len() expects 1 argument(s), got 0", found[0].message)

    def test_call_non_callable(self):
        self.assertIn("Cannot call a value of type 'number'",
                      errors("let x = 5\nprint(x(1))")[0].message)

    def test_builtin_argument_type(self):
        self.assertIn("push(): argument 1 must be a list",
                      errors("push(1, 2)")[0].message)

    def test_redefining_builtin_at_top_level(self):
        self.assertIn("top level", errors("let print = 1")[0].message)

    def test_redefining_name_in_block(self):
        found = errors("let x = 1\nlet x = 2")
        self.assertIn("already defined", found[0].message)
        self.assertEqual(found[0].line, 2)

    def test_return_outside_function(self):
        self.assertIn("'return' used outside of a function",
                      errors("return 1")[0].message)

    def test_break_outside_loop(self):
        self.assertIn("'break' used outside of a loop",
                      errors("break")[0].message)

    def test_continue_outside_loop(self):
        self.assertIn("'continue' used outside of a loop",
                      errors("continue")[0].message)

    def test_plus_needs_matching_operands(self):
        self.assertIn("'+' needs two strings or two numbers",
                      errors('let x = 1 + "s"')[0].message)

    def test_comparison_types(self):
        self.assertIn("Cannot compare number and bool",
                      errors("let x = 3 > true")[0].message)

    def test_index_must_be_whole_number(self):
        self.assertIn("Index must be a whole number",
                      errors('let x = [1]["a"]')[0].message)

    def test_map_keys_must_be_strings(self):
        self.assertIn("Map keys must be strings",
                      errors("let x = {\"a\":1}[1]")[0].message)

    def test_member_needs_map(self):
        self.assertIn(".b access needs a map",
                      errors("let y = 5.b")[0].message)

    def test_for_in_needs_iterable(self):
        self.assertIn("for-in needs a list, string or map",
                      errors("for x in 5 { }")[0].message)

    def test_hint_mismatch_on_initializer(self):
        self.assertIn("declared as 'number' but the initializer has type 'string'",
                      errors('let x : number = "s"')[0].message)

    def test_hint_mismatch_on_assignment(self):
        self.assertIn("declared as 'number' but assigned a value of type 'string'",
                      errors('let x : number = 1\nx = "s"')[0].message)

    def test_hint_mismatch_on_argument(self):
        self.assertIn("wants 'number' for argument 1",
                      errors('fn f(n : number) {}\nf("s")')[0].message)

    def test_hint_mismatch_on_return(self):
        self.assertIn("declares its return as 'number' but this return has type 'string'",
                      errors('fn f() : number { return "s" }')[0].message)

    def test_parse_error_is_reported(self):
        found = errors("let x = = 2")
        self.assertEqual(len(found), 1)
        self.assertIn("parse error", found[0].message)
        self.assertEqual(found[0].line, 1)


class WarningTests(unittest.TestCase):
    def test_unused_variable_warns_once(self):
        found = warnings("let unused = 2\nprint(1)")
        self.assertEqual(len(found), 1)
        self.assertIn("Unused variable 'unused'", found[0].message)

    def test_const_binding_is_never_unused(self):
        self.assertEqual(warnings("const keep = 2\nprint(1)"), [])

    def test_parameters_are_never_unused(self):
        self.assertEqual(warnings("fn f(a) { return 1 }\nprint(f(2))"), [])

    def test_assignment_counts_as_use(self):
        self.assertEqual(warnings("let x = 1\nprint(x)\nx = 2"), [])


class BadCorpusTests(unittest.TestCase):
    """tests/bad/: planted bugs, each file naming the Checks it must earn."""

    BAD_DIR = os.path.join(os.path.dirname(__file__), "bad")

    def test_every_bad_file_is_caught(self):
        files = sorted(glob.glob(os.path.join(self.BAD_DIR, "*.burl")))
        self.assertGreater(len(files), 0, "the bad corpus is empty")
        for path in files:
            with open(path, encoding="utf-8") as handle:
                source = handle.read()
            expected = [line.split("expect:", 1)[1].strip()
                        for line in source.splitlines()
                        if line.lstrip().startswith("// expect:")]
            with self.subTest(path=path):
                self.assertGreater(len(expected), 0, f"{path} plants no bug")
                messages = [d.message for d in check_source(source)]
                for substr in expected:
                    self.assertTrue(
                        any(substr in message for message in messages),
                        f"{path}: checker did not earn '{substr}'\n"
                        f"found: {messages}")


class ExampleCorpusTests(unittest.TestCase):
    """Done-when from the roadmap: `burl check` passes on all of examples/."""

    EXAMPLE_DIR = os.path.join(os.path.dirname(__file__), "..", "examples")

    def test_examples_are_clean(self):
        for path in sorted(glob.glob(os.path.join(self.EXAMPLE_DIR, "**", "*.burl"),
                                     recursive=True)):
            with open(path, encoding="utf-8") as handle:
                source = handle.read()
            with self.subTest(path=path):
                self.assertEqual(check_source(source), [])


if __name__ == "__main__":
    unittest.main()
