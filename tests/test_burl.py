"""Tests for the Burl language (run: python -m unittest discover -s tests)."""

import contextlib
import io
import os
import tempfile
import unittest
from unittest import mock

import burl


def run_burl(source, stdin_lines=None):
    """Run Burl source, returning its stdout text."""
    out = io.StringIO()
    if stdin_lines is None:
        stdin = io.StringIO("")
    else:
        stdin = io.StringIO("\n".join(stdin_lines) + "\n")
    with contextlib.redirect_stdout(out), mock.patch("sys.stdin", stdin):
        burl.run(source)
    return out.getvalue()


def run_fails(source):
    """Run Burl source expecting a Burl error; return its message."""
    try:
        run_burl(source)
    except burl.BurlError as err:
        return str(err)
    raise AssertionError(f"Expected a Burl error, but program succeeded: {source!r}")


class ArithmeticTests(unittest.TestCase):
    def test_precedence(self):
        self.assertEqual(run_burl("print(2 + 3 * 4)").strip(), "14")
        self.assertEqual(run_burl("print((2 + 3) * 4)").strip(), "20")

    def test_division_is_always_real(self):
        self.assertEqual(run_burl("print(4 / 2)").strip(), "2")
        self.assertEqual(run_burl("print(3 / 2)").strip(), "1.5")

    def test_modulo(self):
        self.assertEqual(run_burl("print(7 % 3)").strip(), "1")

    def test_unary_minus(self):
        self.assertEqual(run_burl("print(-5 + 2)").strip(), "-3")

    def test_division_by_zero_is_loud(self):
        message = run_fails("let x = 1 / 0")
        self.assertIn("Division by zero", message)

    def test_number_printing(self):
        self.assertEqual(run_burl("print(3.0)").strip(), "3")
        self.assertEqual(run_burl("print(3.5)").strip(), "3.5")


class StringTests(unittest.TestCase):
    def test_concat(self):
        self.assertEqual(run_burl('print("a" + "b")').strip(), "ab")

    def test_interpolation(self):
        out = run_burl('let name = "Ada"\nprint("Hello, {name}! Age {36 + 1}")')
        self.assertEqual(out.strip(), "Hello, Ada! Age 37")

    def test_interpolation_nests_calls(self):
        out = run_burl('fn add(a, b) { return a + b }\nprint("got {add(2, 3)}")')
        self.assertEqual(out.strip(), "got 5")

    def test_escaped_braces(self):
        out = run_burl('print("\\{not an expr\\}")')
        self.assertEqual(out.strip(), "{not an expr}")

    def test_escapes(self):
        out = run_burl('print("tab:\\ta\\nnl:\\nend")')
        self.assertEqual(out, "tab:\ta\nnl:\nend\n")

    def test_missing_key_is_loud(self):
        message = run_fails('let m = {"a": 1}\nprint(m.b)')
        self.assertIn("no key 'b'", message)


class ControlFlowTests(unittest.TestCase):
    def test_if_else_chain(self):
        out = run_burl("let n = 2\nif n == 1 { print(\"one\") } "
                       "else if n == 2 { print(\"two\") } else { print(\"many\") }")
        self.assertEqual(out.strip(), "two")

    def test_while_and_break(self):
        out = run_burl("let i = 0\nwhile true {\n  i = i + 1\n"
                       "  if i > 3 { break }\n}\nprint(i)")
        self.assertEqual(out.strip(), "4")

    def test_continue(self):
        out = run_burl("for i in range(1, 6) {\n  if i % 2 == 0 { continue }\n"
                       "  print(i)\n}")
        self.assertEqual(out.strip(), "1\n3\n5")

    def test_for_iterates_string_and_map(self):
        out = run_burl('for c in "ab" { print(c) }')
        self.assertEqual(out.strip(), "a\nb")
        out = run_burl('let m = {"x": 1, "y": 2}\nfor k in m { print(k) }')
        self.assertEqual(out.strip(), "x\ny")

    def test_missing_newline_between_statements_is_error(self):
        message = run_fails("let a = 1 let b = 2")
        self.assertIn("Expected end of statement", message)


class ScopeAndFunctionTests(unittest.TestCase):
    def test_closures(self):
        out = run_burl("fn make_counter() {\n  let n = 0\n  return fn() {\n"
                       "    n = n + 1\n    return n\n  }\n}\n"
                       "let c = make_counter()\nc()\nc()\nprint(c())")
        self.assertEqual(out.strip(), "3")

    def test_for_loop_var_is_fresh_each_iteration(self):
        out = run_burl("let fns = []\nfor i in range(3) {\n  push(fns, fn() { return i })\n}\n"
                       "print(fns[0]() + fns[1]() + fns[2]())")
        self.assertEqual(out.strip(), "3")

    def test_shadowing_in_inner_block(self):
        out = run_burl("let x = 1\n{\n  let x = 2\n  print(x)\n}\nprint(x)")
        self.assertEqual(out.strip(), "2\n1")

    def test_redeclare_is_error(self):
        message = run_fails("let x = 1\nlet x = 2")
        self.assertIn("already defined", message)

    def test_const_protection(self):
        message = run_fails("const x = 1\nx = 2")
        self.assertIn("const", message)

    def test_assignment_to_undeclared(self):
        message = run_fails("y = 2")
        self.assertIn("Undefined name 'y'", message)

    def test_recursion(self):
        out = run_burl("fn fact(n) {\n  if n <= 1 { return 1 }\n"
                       "  return n * fact(n - 1)\n}\nprint(fact(5))")
        self.assertEqual(out.strip(), "120")

    def test_functions_are_values(self):
        out = run_burl("fn twice(f, v) { return f(f(v)) }\n"
                       "fn inc(n) { return n + 1 }\nprint(twice(inc, 10))")
        self.assertEqual(out.strip(), "12")

    def test_return_outside_function(self):
        message = run_fails("return 1")
        self.assertIn("'return' used outside of a function", message)


class TypeHintTests(unittest.TestCase):
    def test_valid_hints_pass(self):
        out = run_burl("let n: number = 5\nlet s: string = \"hi\"\n"
                       "fn add(a: number, b: number): number { return a + b }\n"
                       "print(add(n, n))")
        self.assertEqual(out.strip(), "10")

    def test_missing_return_checks_nil(self):
        message = run_fails("fn f(): number {\n  return\n}\nf()")
        self.assertIn("declared as 'number'", message)

    def test_bad_hint_fails_at_runtime(self):
        message = run_fails('let x: number = "hi"')
        self.assertIn("declared as 'number'", message)

    def test_assignment_hint_check(self):
        message = run_fails('let x: number = 1\nx = "no"')
        self.assertIn("declared as 'number'", message)

    def test_argument_hint_check(self):
        message = run_fails('fn f(n: number) { return n }\nf("x")')
        self.assertIn("'n' is declared as 'number'", message)

    def test_unknown_hint_is_parse_error(self):
        message = run_fails("let x: blob = 1")
        self.assertIn("Unknown type 'blob'", message)

    def test_int_and_float_share_number(self):
        out = run_burl("let a: number = 1\na = 2.5\nprint(a)")
        self.assertEqual(out.strip(), "2.5")


class EqualityAndTruthinessTests(unittest.TestCase):
    def test_strict_equality(self):
        self.assertEqual(run_burl("print(0 == false)").strip(), "false")
        self.assertEqual(run_burl('print("" == false)').strip(), "false")

    def test_deep_equality(self):
        self.assertEqual(run_burl("print([1, 2] == [1, 2])").strip(), "true")
        self.assertEqual(run_burl('print({"a": 1} == {"a": 1})').strip(), "true")

    def test_comparison_types(self):
        self.assertEqual(run_burl("print(\"a\" < \"b\")").strip(), "true")
        message = run_fails('print(1 < "a")')
        self.assertIn("Cannot compare", message)

    def test_truthiness(self):
        for value, expected in [("0", "falsy"), ('""', "falsy"), ("[]", "falsy"),
                                ("nil", "falsy"), ("3", "truthy"), ('"x"', "truthy")]:
            out = run_burl(f"if {value} {{ print(\"truthy\") }} else {{ print(\"falsy\") }}")
            self.assertEqual(out.strip(), expected)


class StdlibTests(unittest.TestCase):
    def test_list_builtins(self):
        out = run_burl("let l = []\npush(l, 1)\npush(l, 2)\nprint(pop(l))\nprint(len(l))")
        self.assertEqual(out.strip(), "2\n1")

    def test_range_join_split(self):
        out = run_burl('print(join(range(1, 4), "-"))')
        self.assertEqual(out.strip(), "1-2-3")
        out = run_burl('print(len(split("a,b,c", ",")))')
        self.assertEqual(out.strip(), "3")

    def test_map_builtins(self):
        out = run_burl('let m = {"a": 1, "b": 2}\nprint(join(keys(m), ","))\n'
                       "print(has(m, \"a\"))\nprint(has(m, \"z\"))")
        self.assertEqual(out.strip(), "a,b\ntrue\nfalse")

    def test_num_conversions(self):
        out = run_burl('print(num("12") + 1)\nprint(num("3.5"))\nprint(num("nope") == nil)')
        self.assertEqual(out.strip(), "13\n3.5\ntrue")

    def test_int_floor_round_abs(self):
        out = run_burl("print(int(3.9))\nprint(floor(3.2))\nprint(round(2.5))\nprint(abs(-4))")
        self.assertEqual(out.strip(), "3\n3\n3\n4")

    def test_min_max(self):
        out = run_burl("print(min(3, 1, 2))\nprint(max([5, 2, 9]))")
        self.assertEqual(out.strip(), "1\n9")

    def test_read_write_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "note.txt").replace("\\", "/")
            out = run_burl(f'write("{path}", "hello")\nprint(read("{path}"))')
            self.assertEqual(out.strip(), "hello")


class ErrorReportingTests(unittest.TestCase):
    def test_errors_carry_line_numbers(self):
        message = run_fails("let a = 1\nprint(a)\nprint(b)")
        self.assertIn("line 3", message)

    def test_parse_error_nonassociative_compare(self):
        message = run_fails("print(1 < 2 < 3)")
        self.assertIn("a < b and b < c", message)


class EvergreenExampleTests(unittest.TestCase):
    """The examples are load-bearing: they run on the shipping path."""

    def _run_example(self, name, stdin_lines=None):
        path = os.path.join(os.path.dirname(__file__), "..", "examples", name)
        with open(path, encoding="utf-8") as handle:
            source = handle.read()
        return run_burl(source, stdin_lines)

    def test_adventure_win_path(self):
        out = self._run_example(
            "adventure.burl",
            ["e", "take", "w", "n", "n", "talk", "s", "w", "talk", "e", "e", "e"])
        self.assertIn("You win", out)
        self.assertIn("The Crossing", out)

    def test_adventure_gates_the_crossing(self):
        # Try the crossing without blade, letter or crew: it must refuse.
        out = self._run_example("adventure.burl", ["n", "e", "e", "quit"])
        self.assertIn("No letter, no crew, no crossing", out)

    def test_input_returns_nil_at_eof(self):
        out = run_burl("print(input() == nil)")
        self.assertIn("true", out)


if __name__ == "__main__":
    unittest.main()
