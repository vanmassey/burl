"""Burl — a small scripting language. See SPEC.md for the language contract."""

__version__ = "0.4.0"

from .errors import BurlError, BurlRuntimeError, LexError, ParseError
from .interpreter import Interpreter
from .lexer import lex
from .parser import parse


def run(source):
    """Lex, parse and execute Burl source. Returns the Interpreter."""
    interpreter = Interpreter()
    interpreter.run(parse(source))
    return interpreter
