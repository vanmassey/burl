"""Tests for Burl 0.2: modules and the string tools."""

import contextlib
import io
import os
import tempfile
import unittest

import burl
from burl import Interpreter, parse
from tests.test_burl import run_burl, run_fails


def run_main_file(path):
    """Run a .burl file as the main program; import() resolves from its dir."""
    interp = Interpreter()
    interp.base_dir = os.path.dirname(path)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        interp.run(parse(open(path, encoding="utf-8").read()))
    return buf.getvalue()


class ModuleTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, name, source):
        path = os.path.join(self.dir, name)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(source)
        return path

    def test_import_exposes_fn_and_const(self):
        self.write("mod.burl",
                   "const answer = 42\nfn twice(n) { return n * 2 }\n"
                   "let secret = 1  // private\n")
        main = self.write("main.burl",
                          'let m = import("mod.burl")\n'
                          'print(m.twice(m.answer))\n'
                          'print(has(m, "secret"))\n')
        # `secret` is a private let: it must be invisible to the importer.
        self.assertEqual(run_main_file(main).strip(), "84\nfalse")

    def test_module_runs_once_and_functions_stay_live(self):
        self.write("counter_mod.burl",
                   'print("MODULE LOADS")\n'
                   "let count = 0\n"
                   "fn bump() {\n  count = count + 1\n  return count\n}\n")
        main = self.write("main.burl",
                          'let a = import("counter_mod.burl")\n'
                          'let b = import("counter_mod.burl")\n'
                          'a.bump()\na.bump()\n'
                          'print(b.bump())\n')
        lines = run_main_file(main).strip().split("\n")
        # The module body ran exactly once; both imports share one module map,
        # whose bump() closes over the same private count.
        self.assertEqual(lines[0], "MODULE LOADS")
        self.assertEqual(lines[-1], "3")

    def test_circular_import_is_loud(self):
        self.write("a.burl", 'let b = import("b.burl")\n')
        self.write("b.burl", 'let a = import("a.burl")\n')
        main = self.write("main.burl", 'let a = import("a.burl")\n')
        with self.assertRaises(burl.BurlError) as caught:
            run_main_file(main)
        self.assertIn("Circular import", str(caught.exception))
        self.assertIn("a.burl -> b.burl -> a.burl", str(caught.exception))

    def test_missing_module_names_the_path(self):
        main = self.write("main.burl", 'let m = import("nope.burl")\n')
        with self.assertRaises(burl.BurlError) as caught:
            run_main_file(main)
        self.assertIn("nope.burl", str(caught.exception))
        self.assertIn("cannot read", str(caught.exception))

    def test_module_parse_error_reports_line(self):
        self.write("broken.burl", "let ok = 1\nprint(\n")
        main = self.write("main.burl", 'import("broken.burl")\n')
        with self.assertRaises(burl.BurlError) as caught:
            run_main_file(main)
        self.assertIn("broken.burl", str(caught.exception))
        self.assertIn("line 3", str(caught.exception))


class StringToolTests(unittest.TestCase):
    def test_slice(self):
        self.assertEqual(run_burl('print(slice("drakkar", 0, 3))').strip(), "dra")
        self.assertEqual(run_burl('print(slice("drakkar", 4, 7))').strip(), "kar")
        message = run_fails('slice("ab", 0, 5)')
        self.assertIn("out of range", message)
        message = run_fails('slice("ab", 2, 1)')
        self.assertIn("start 2 is after end 1", message)

    def test_find(self):
        self.assertEqual(run_burl('print(find("longship sea", "ship"))').strip(), "4")
        self.assertEqual(run_burl('print(find("longship", "zzz") < 0)').strip(), "true")
        self.assertEqual(run_burl('print(find("a-b-a", "a", 1))').strip(), "4")

    def test_contains(self):
        self.assertEqual(run_burl('print(contains("vinland", "land"))').strip(), "true")
        self.assertEqual(run_burl('print(contains("vinland", "sea"))').strip(), "false")

    def test_replace(self):
        self.assertEqual(
            run_burl('print(replace("row, row, row", "row", "sail"))').strip(),
            "sail, sail, sail")
        message = run_fails('replace("abc", "", "x")')
        self.assertIn("must not be empty", message)

    def test_trim(self):
        self.assertEqual(run_burl('print("[" + trim("  skal  ") + "]")').strip(), "[skal]")


if __name__ == "__main__":
    unittest.main()
