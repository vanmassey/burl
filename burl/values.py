"""Shared Burl value machinery: callables, truthiness, formatting, hints.

Kept free of imports from interpreter.py / builtins.py — both depend on this
module, never the other way around.
"""

import json

from .errors import BurlRuntimeError

NUMERIC = (int, float)


class Fn:
    """Base class for every callable Burl value."""
    name = "?"


class BurlFunction(Fn):
    __slots__ = ("name", "params", "ret_hint", "body", "env", "line")

    def __init__(self, name, params, ret_hint, body, env, line):
        self.name = name
        self.params = params
        self.ret_hint = ret_hint
        self.body = body
        self.env = env
        self.line = line

    def __repr__(self):
        return f"<fn {self.name}>"


# ---- Type names and hints (SPEC.md sections 5, 8) -------------------------

def type_name(value):
    if value is None:
        return "nil"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, NUMERIC):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "map"
    if isinstance(value, Fn):
        return "fn"
    return type(value).__name__


def satisfies(value, hint):
    if hint == "any":
        return True
    if hint == "number":
        return isinstance(value, NUMERIC) and not isinstance(value, bool)
    return type_name(value) == hint


def check_hint(value, hint, name, line):
    if hint is None or hint == "any":
        return
    if not satisfies(value, hint):
        raise BurlRuntimeError(
            f"'{name}' is declared as '{hint}' but got {format_value(value)} "
            f"of type '{type_name(value)}'", line)


# ---- Truthiness, formatting, equality --------------------------------------

def truthy(value):
    if value is None or value is False:
        return False
    if value is True:
        return True
    if isinstance(value, NUMERIC):
        return value != 0
    if isinstance(value, (str, list, dict)):
        return len(value) > 0
    return True  # functions


def format_number(value):
    if isinstance(value, int):
        return str(value)
    if value != value:  # NaN
        return "nan"
    if value in (float("inf"), float("-inf")):
        return "inf" if value > 0 else "-inf"
    if value.is_integer() and abs(value) < 1e16:
        return str(int(value))
    return repr(value)


def format_value(value, quoted=False):
    """The single canonical way Burl turns a value into display text (SPEC 5)."""
    if value is None:
        return "nil"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, NUMERIC):
        return format_number(value)
    if isinstance(value, str):
        return json.dumps(value) if quoted else value
    if isinstance(value, list):
        return "[" + ", ".join(format_value(item, quoted=True) for item in value) + "]"
    if isinstance(value, dict):
        inner = ", ".join(
            format_value(key, quoted=True) + ": " + format_value(item, quoted=True)
            for key, item in value.items())
        return "{" + inner + "}"
    if isinstance(value, Fn):
        return f"<fn {getattr(value, 'name', '?')}>"
    return str(value)


def is_equal(a, b):
    if type_name(a) != type_name(b):
        return False
    if isinstance(a, list):
        return len(a) == len(b) and all(is_equal(x, y) for x, y in zip(a, b))
    if isinstance(a, dict):
        if a.keys() != b.keys():
            return False
        return all(is_equal(v, b[k]) for k, v in a.items())
    return a == b
