"""Bootstrap differential tests (0.4): Burl written in Burl must match Burl
written in Python, byte for byte.

Every corpus program runs two ways and the combined output must be
identical (stdout, then any error rendered as ``burl: {Kind} error at
line N: msg``):

  (a) host:   the Python implementation (``burl`` package)
  (b) engine: ``src/lex.burl`` + ``src/parse.burl`` + ``src/interp.burl``
              + ``src/kernel.burl``, executed by the host and driven
              through its own lex/parse/exec entry points.

Chain depth:
  depth 1  host runs (Burl interp) which runs the program      — default tests
  depth 2  host runs (Burl interp) which runs (Burl interp)
           which runs the program                              — slow

Depth 2 re-parses the whole engine (~2,800 lines) through the depth-1
interpreter, so it runs for many minutes. Those tests only execute when
``BURL_SLOW_TESTS=1`` is set in the environment.
"""

import contextlib
import io
import os
import subprocess
import sys
import unittest
from unittest import mock

import burl
from burl import Interpreter
from burl.__main__ import _with_big_stack
from burl.lexer import lex as host_lex
from burl.parser import parse as host_parse

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLES = os.path.join(REPO, "examples")
ENGINE_FILES = ["src/lex.burl", "src/parse.burl", "src/interp.burl", "src/kernel.burl"]

# The reflexive chain depth the default suite proves (host -> engine -> program).
DEPTH_1 = 1
SLOW_ENV = "BURL_SLOW_TESTS"


# ---- the corpus ---------------------------------------------------------------

# Semantic snippets: every language feature whose output a differential run
# can compare, including the error paths (same rendering on both sides).
SNIPPETS = [
    # arithmetic, precedence, unary, float formatting
    "print(1 + 2 * 3)\nprint((1 + 2) * 3)\nprint(7 / 2)\nprint(-5 + 2)\nprint(10 % 3)\nprint(2.5 + 0.5)\nprint(1 == 1.0)\n",
    # exact integers vs double contamination (SPEC.md 5.1, LEDGER L-009)
    'print(9007199254740993 * 2)\nprint(9007199254740992 + 1.0)\nprint(9007199254740993 == 9007199254740992.0)\nprint(int(9007199254740992.5))\nprint(num("9007199254740993") * 2)\n',
    # strings + interpolation
    'let n = 3\nprint("n is \\{n\\} and \\{n * 2\\}")\nprint("a" + "b")\nprint(len("hello"))\nprint(upper("abc") + lower("DEF"))\n',
    # functions, recursion, hints
    'fn fact(n: number): number {\n    if n <= 1 {\n        return 1\n    }\n    return n * fact(n - 1)\n}\nprint(fact(6))\n',
    'fn add(a, b) { return a + b }\nprint(add(2, 3))\nlet f = fn(x) { return x * x }\nprint(f(9))\n',
    # while / break / continue
    'let i = 0\nwhile true {\n    i = i + 1\n    if i > 10 { break }\n    if i % 2 == 0 { continue }\n    print(i)\n}\nprint("done", i)\n',
    # for-in over list, string, map
    'for x in [10, 20, 30] { print(x) }\nfor c in "hey" { print(c) }\nlet m = {"a": 1, "b": 2}\nfor k in m { print(k, m[k]) }\n',
    # lists / maps / index / member assign
    'let l = [1, 2, 3]\nl[1] = 42\npush(l, 4)\nprint(l, len(l), l[0], l[len(l) - 1])\nlet m = {"x": 1}\nm["x"] = 5\nm.y = 6\nprint(m, m["x"], m.y)\nprint(has(m, "x"), has(m, "nope"))\n',
    # truthiness, and/or/not short-circuit
    'print(not false, not 0, not "")\nprint(1 and 2)\nprint(nil or "fallback")\nfn boom() { return 1 / 0 }\nprint(false and boom())\nprint(true or boom())\n',
    # comparisons
    'print(1 < 2)\nprint("a" < "b")\n',
    # blocks & scoping & closures
    'let x = 1\nif true {\n    let x = 2\n    print(x)\n}\nprint(x)\nfn make() {\n    let n = 0\n    return fn() {\n        n = n + 1\n        return n\n    }\n}\nlet c = make()\nc()\nc()\nprint(c())\n',
    # builtins
    'print(join(split("a,b,c", ","), "-"))\nprint(find("hello", "ll"))\nprint(contains("hello", "ell"), contains("hello", "xyz"))\nprint(keys({"k": 1})[0])\nprint(str(12) + str(3))\nprint(num("3.5") + 1)\nprint(int(3.9))\nprint(abs(-4), min(3, 1, 2), max([1, 5, 2]), floor(2.7))\nprint(round(2.567, 2))\nprint(slice("hello", 1, 3))\nprint(trim("  x  ") + "!")\nprint(replace("aaa", "a", "b"))\n',
    # value display formats
    'print([1, "two", true, nil])\nprint({"k": [1], "nested": {"a": "s"}})\nprint(nil, true, false)\n',
    # runtime error: division by zero
    'let a = 1\nprint("before")\nprint(a / 0)\n',
    # runtime error: index out of range
    'let l = [1]\nprint(l[5])\n',
    # runtime error: type error in arithmetic
    'print(1 + "x")\n',
    # runtime error: undefined name
    'print(nope)\n',
    # runtime error: call arity
    'fn f(a) { return a }\nprint(f(1, 2))\n',
    # runtime error: cannot call non-fn
    'let n = 3\nn()\n',
    # hint violation
    'let x: number = "str"\n',
    # parse error
    'let x = = 2\n',
    # lex error
    'let s = "unterminated\n',
    # interpolation key in a map literal is rejected
    'let k = "a"\nlet m = {"\\{k\\}": 1}\nprint(m)\n',
    # empty structures, multiline lists
    'let e = []\nprint(e, len(e))\nlet big = [\n    1,\n    2,\n]\nprint(big)\nlet m2 = {\n    "a": 1,\n    "b": 2,\n}\nprint(m2)\n',
    # recursion depth
    'fn fib(n) { if n < 2 { return n } return fib(n - 1) + fib(n - 2) }\nprint(fib(10))\n',
    # string escapes
    'print("tab\\there")\nprint("nl\\nnext")\nprint("quote\\" inside")\nprint("back\\\\slash")\n',
    # chained postfix: list of maps, calls on index
    'let users = [{"name": "bo", "say": fn(self) { return "hi " + self["name"] }}]\nprint(users[0]["name"])\nprint(users[0]["say"](users[0]))\nusers[0]["name"] = "bj"\nprint(users[0].name)\n',
    # return without value; early return
    'fn noret() {\n    if true { return }\n    return 5\n}\nprint(noret())\nfn early(x) {\n    if x { return "yes" }\n    return "no"\n}\nprint(early(true), early(false))\n',
    # const
    'const K = 5\nprint(K)\n',
    # apply: the builtin the engine itself depends on
    'print(apply(len, ["hello"]))\nprint(apply(fn(a, b) { return a * b }, [6, 7]))\nfn wrap(x) { return [x] }\nprint(apply(wrap, ["ok"]))\n',
    # plain sequence
    'let a = 1\nlet b = 2\nprint(a + b)\n',
]

# Example programs, with the stdin their input() loops consume.
# riddle.burl is excluded: its closing saga.wisdom() pick is random(), which
# cannot match across two separate executions.
EXAMPLE_PROGRAMS = [
    ("fib.burl", []),
    ("fizzbuzz.burl", []),
    ("wordcount.burl", []),
    ("adventure.burl", ["look", "north", "go north", "quit? never", ""]),
]


# ---- host side ------------------------------------------------------------------

def run_host(source, base_dir=None, stdin_lines=None):
    """Run source on the Python host; return stdout + rendered error line."""
    out = io.StringIO()
    stdin = io.StringIO("\n".join(stdin_lines) + "\n" if stdin_lines else "")
    try:
        interp = Interpreter()
        if base_dir is not None:
            interp.base_dir = base_dir
        with contextlib.redirect_stdout(out), mock.patch("sys.stdin", stdin):
            interp.run(host_parse(host_lex(source)))
    except burl.BurlError as err:
        return out.getvalue() + "burl: %s\n" % err
    return out.getvalue()


def run_host_name(name, stdin_lines=None):
    """Run an example file by name from examples/ on the host."""
    with open(os.path.join(EXAMPLES, name), encoding="utf-8") as handle:
        return run_host(handle.read(), base_dir=EXAMPLES, stdin_lines=stdin_lines)


# ---- engine side ----------------------------------------------------------------

class Engine:
    """The bootstrap engine: src/*.burl loaded into one host interpreter.

    Loading is cheap (~0.1s). All engine entry points are plain Burl
    functions; errors are read from the engine's module-level error maps.
    """

    _cache = {}

    def __init__(self, cwd):
        old = os.getcwd()
        os.chdir(cwd)
        try:
            self.interp = Interpreter()
            source = "\n".join(
                open(os.path.join(REPO, f), encoding="utf-8").read()
                for f in ENGINE_FILES
            )
            self.interp.run(host_parse(host_lex(source)))
        finally:
            os.chdir(old)

    @classmethod
    def get(cls, cwd):
        if cwd not in cls._cache:
            cls._cache[cwd] = Engine(cwd)
        return cls._cache[cwd]

    def call(self, name, args, depth=0):
        fn = self.lookup(name)
        return self.interp.call_function(fn, args, depth)

    def lookup(self, name):
        env = self.interp.globals
        while env is not None:
            if name in env.values:
                return env.values[name][0]
            env = env.parent
        raise AssertionError("engine global not found: %s" % name)

    def error_state(self, name):
        return self.lookup(name)


def render_engine_error(err):
    """Render an engine error map exactly the way the host renders BurlError."""
    prefix = err["kind"].capitalize() + " error"
    if err["line"]:
        prefix += " at line " + str(int(err["line"]))
    return "burl: %s: %s\n" % (prefix, err["msg"])


def run_engine(eng, source, stdin_lines=None):
    """Run source through the engine: lex -> parse -> exec. Returns combined."""
    out = io.StringIO()
    stdin = io.StringIO("\n".join(stdin_lines) + "\n" if stdin_lines else "")
    with contextlib.redirect_stdout(out), mock.patch("sys.stdin", stdin):
        try:
            toks = eng.call("lex", [source])
            if toks is None:
                return out.getvalue() + render_engine_error(eng.error_state("_E"))
            ast = eng.call("parse", [toks, eng.lookup("lex")])
            if ast is None:
                return out.getvalue() + render_engine_error(eng.error_state("_P_E"))
            eng.call("interp_fresh", [])
            genv = eng.call("i_make_globals", [])
            eng.call("i_boot_exec", [ast, genv])
            err = eng.error_state("_I_E")
            if err["kind"] != "":
                return out.getvalue() + render_engine_error(err)
        except burl.BurlError:
            raise  # a host-side failure is a test bug, not a corpus result
    return out.getvalue()


def big_stack(fn):
    """Run on a large stack: bootstrapped interpretation multiplies depth."""
    return _with_big_stack(fn)


# ---- the tests -------------------------------------------------------------------

# kernel.k_chain's deps map: dep name -> the engine global that provides it.
_CHAIN_DEPS = {
    "lex": "lex",
    "parse": "parse",
    "make_globals": "i_make_globals",
    "exec_ast": "i_boot_exec",
    "call_fn": "i_call_fn",
    "lex_err": "lex_err",
    "parse_err": "parse_err",
    "interp_err": "interp_err",
}


def _chain_deps(eng):
    return {dep: eng.lookup(fn) for dep, fn in _CHAIN_DEPS.items()}


def _engine_sources():
    return [
        open(os.path.join(REPO, f), encoding="utf-8").read()
        for f in ENGINE_FILES
    ]


class BootstrapDepth1Tests(unittest.TestCase):
    """Depth 1: the host runs the Burl engine, which runs each program."""

    def test_semantic_snippets_match_host(self):
        def body():
            eng = Engine.get(REPO)
            for i, src in enumerate(SNIPPETS):
                host_out = run_host(src)
                with self.subTest(snippet=i):
                    self.assertEqual(run_engine(eng, src), host_out)
        big_stack(body)

    def test_example_programs_match_host(self):
        def body():
            eng = Engine.get(EXAMPLES)
            for name, stdin_lines in EXAMPLE_PROGRAMS:
                host_out = run_host_name(name, stdin_lines)
                with self.subTest(example=name):
                    with open(os.path.join(EXAMPLES, name), encoding="utf-8") as handle:
                        src = handle.read()
                    self.assertEqual(run_engine(eng, src, stdin_lines), host_out)
        big_stack(body)

    def test_chain_depth1_matches_host(self):
        """The kernel's own boot path: build the engine FROM the engine."""
        good = 'print("hi")\nlet x = 6 * 7\nprint(x)\n'
        bad = "let a = 1\nprint(a / 0)\n"
        for program in (good, bad):
            with self.subTest(program=program.strip()):
                def body():
                    eng = Engine.get(REPO)
                    out = io.StringIO()
                    with contextlib.redirect_stdout(out):
                        err = eng.call(
                            "k_chain",
                            [_chain_deps(eng), _engine_sources(), program, DEPTH_1],
                        )
                    line = render_engine_error(err) if err["kind"] != "" else ""
                    self.assertEqual(out.getvalue() + line, run_host(program))
                big_stack(body)


@unittest.skipUnless(
    os.environ.get(SLOW_ENV) == "1",
    "depth-2 chain re-parses the whole engine through the engine itself; "
    "runs for many minutes. Set %s=1 to include it." % SLOW_ENV,
)
class BootstrapDepth2Tests(unittest.TestCase):
    """Depth 2: host -> (Burl interp) -> (Burl interp) -> program.

    This is the full reflexive proof. Slow by construction: the second
    engine boot lexes and parses ~2,800 lines of Burl through Burl.
    """

    def test_chain_depth2_matches_host(self):
        program = 'print("hi")\nlet x = 6 * 7\nprint(x)\n'

        def body():
            eng = Engine.get(REPO)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                err = eng.call(
                    "k_chain",
                    [_chain_deps(eng), _engine_sources(), program, 2],
                )
            self.assertEqual(err["kind"], "")
            self.assertEqual(out.getvalue(), run_host(program))

        big_stack(body)

    def test_driver_cli_depth2(self):
        """The shipped entry point end to end:
        python -m burl src/burl.burl < program.burl
        """
        program = 'print("hi")\nlet x = 6 * 7\nprint(x)\n'
        proc = subprocess.run(
            [sys.executable, "-m", "burl", "src/burl.burl"],
            cwd=REPO, input=program, capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, run_host(program))
