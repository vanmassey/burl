"""The Burl command-line interface: run files, check files, or start a REPL.

Usage:
  python -m burl program.burl
  python -m burl check program.burl [more.burl ...]
  python -m burl           (REPL)
"""

import os
import sys

from . import __version__
from .checker import check_source
from .errors import BurlError
from .interpreter import Interpreter
from .parser import parse
from .values import format_value


def _read(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()
    except OSError as exc:
        return None


def run_file(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            source = handle.read()
    except OSError as exc:
        print(f"burl: cannot open '{path}': {exc.strerror or exc}", file=sys.stderr)
        return 1
    try:
        interp = Interpreter()
        # import() resolves relative paths against the main file's directory,
        # not the current working directory (SPEC.md 11).
        interp.base_dir = os.path.dirname(os.path.abspath(path))
        interp.run(parse(source))
    except BurlError as err:
        print(f"burl: {err}", file=sys.stderr)
        return 1
    return 0


def cmd_check(paths):
    """Run the static checker (SPEC.md 12). Advisory: exits 1 on errors."""
    if not paths:
        print("usage: burl check program.burl [more.burl ...]", file=sys.stderr)
        return 2
    total_errors = total_warnings = 0
    for path in paths:
        source = _read(path)
        if source is None:
            print(f"burl: cannot open '{path}'", file=sys.stderr)
            total_errors += 1
            continue
        diagnostics = check_source(source)
        for diag in diagnostics:
            if diag.severity == "error":
                total_errors += 1
            else:
                total_warnings += 1
            print(f"{path}:{diag.line}: {diag.severity}: {diag.message}")
        if not diagnostics:
            print(f"{path}: ok")
    checked = len(paths)
    print(f"checked {checked} file(s): {total_errors} error(s), "
          f"{total_warnings} warning(s)")
    return 1 if total_errors else 0


def repl():
    print(f"Burl {__version__} -- type a statement, Ctrl+C or Ctrl+D to quit.")
    interp = Interpreter()  # globals persist across inputs
    lines = []
    while True:
        try:
            prompt = "... " if lines else "burl> "
            lines.append(input(prompt))
        except (KeyboardInterrupt, EOFError):
            print()
            return 0
        source = "\n".join(lines)
        try:
            program = parse(source)
        except BurlError as err:
            if getattr(err, "eof", False):
                continue  # incomplete input (unclosed brace, trailing operator): keep reading
            print(f"burl: {err}")
            lines = []
            continue
        lines = []
        try:
            result = interp.run_with_result(program)
        except BurlError as err:
            print(f"burl: {err}")
            continue
        if result is not None:
            print(format_value(result))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] in ("-h", "--help"):
        print("usage: python -m burl [program.burl] | check FILE... "
              "(no args: REPL)")
        return 0
    if argv and argv[0] in ("-v", "--version"):
        print(f"burl {__version__}")
        return 0
    if argv and argv[0] == "check":
        return cmd_check(argv[1:])
    if not argv:
        return repl()
    return run_file(argv[0])


if __name__ == "__main__":
    sys.exit(main())
