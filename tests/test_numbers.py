"""The number contract of SPEC.md 5.1 (LEDGER L-009 resolution, Roadmap 0.5).

One number type, two forms: an integer literal is exact at any magnitude;
a double arithmetic result is a 64-bit IEEE 754 float. This file pins the
boundary so the 0.5 VM can be diffed against it.
"""

import unittest

from tests.test_burl import run_burl


def prints(source):
    return run_burl(source).strip()


class IntegerExactnessTests(unittest.TestCase):
    def test_big_int_literals_stay_exact(self):
        # The exact pair L-009 was filed with.
        self.assertEqual(prints("print(9007199254740993)"),
                         "9007199254740993")
        self.assertEqual(prints("print(9007199254740993 * 2)"),
                         "18014398509481986")

    def test_int_ops_chain_exactly(self):
        self.assertEqual(
            prints("print(9007199254740992 * 2 + 1)"),
            "18014398509481985")

    def test_int_modulo_stays_int(self):
        out = prints("let big = 10000000000000000001\nprint(big % 10)")
        self.assertEqual(out, "1")

    def test_num_of_bare_int_text_is_exact(self):
        self.assertEqual(prints('print(num("9007199254740993") * 2)'),
                         "18014398509481986")

    def test_int_values_survive_variables_and_hints(self):
        src = ("fn fact(n: number): number {\n"
               "    if n <= 1 { return 1 }\n"
               "    return n * fact(n - 1)\n"
               "}\n"
               "print(fact(25))")
        self.assertEqual(prints(src), "15511210043330985984000000")


class DoubleContagionTests(unittest.TestCase):
    def test_division_is_always_double(self):
        self.assertEqual(prints("print(4 / 2)"), "2")  # int-valued: prints bare
        self.assertEqual(prints("print(3 / 2)"), "1.5")

    def test_double_operand_makes_double_result(self):
        # The L-009 evidence rows, now documented instead of disputed.
        self.assertEqual(prints("print(9007199254740992 + 1.0)"),
                         "9007199254740992")
        self.assertEqual(prints("print(9007199254740992 * 2 + 1.0)"),
                         "18014398509481984")

    def test_rounded_result_then_exact_ops_stay_rounded(self):
        # Once double, always double: exactness does not come back.
        self.assertEqual(prints("let x = 9007199254740992.0 * 2\n"
                                "print(x + 1)"),
                         "18014398509481984")


class CrossFormSemanticsTests(unittest.TestCase):
    def test_cross_form_comparison_is_exact(self):
        self.assertEqual(prints("print(1 == 1.0)"), "true")
        self.assertEqual(prints("print(9007199254740993 == 9007199254740992.0)"),
                         "false")
        self.assertEqual(prints("print(9007199254740993 < 9007199254740992.0)"),
                         "false")

    def test_int_truncates_toward_zero(self):
        self.assertEqual(prints("print(int(3.9))"), "3")
        self.assertEqual(prints("print(int(-3.9))"), "-3")
        self.assertEqual(prints("print(int(9007199254740992.5))"),
                         "9007199254740992")

    def test_number_hint_accepts_both_forms(self):
        out = run_burl('let a: number = 3\n'
                       'let b: number = 3.5\n'
                       'print(a + b)').strip()
        self.assertEqual(out, "6.5")


if __name__ == "__main__":
    unittest.main()
