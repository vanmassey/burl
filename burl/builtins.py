"""Burl's lean core standard library (SPEC.md section 9).

Every builtin is a plain value in the global scope, same as user functions.
"""

import math
import random as _py_random
import time

from .errors import BurlRuntimeError
from .values import Fn, BurlFunction, format_value, type_name


class Builtin(Fn):
    __slots__ = ("name", "fn", "min_args", "max_args")

    def __init__(self, name, fn, min_args, max_args=None):
        self.name = name
        self.fn = fn
        self.min_args = min_args
        self.max_args = max_args if max_args is not None else min_args

    def call(self, args, line):
        if not (self.min_args <= len(args) <= self.max_args):
            want = str(self.min_args) if self.min_args == self.max_args \
                else f"{self.min_args}..{self.max_args}"
            raise BurlRuntimeError(
                f"{self.name}() expects {want} argument(s), got {len(args)}", line)
        return self.fn(args, line)

    def __repr__(self):
        return f"<fn {self.name}>"


def _builtin(name, min_args, max_args=None):
    def register(fn):
        return Builtin(name, fn, min_args, max_args)
    return register


def expect(args, line, name, index, want):
    """Assert args[index] has type `want` (a type_name)."""
    value = args[index]
    if type_name(value) != want:
        raise BurlRuntimeError(
            f"{name}(): argument {index + 1} must be a {want}, got {type_name(value)}", line)
    return value


# ---- output / input ---------------------------------------------------------

@_builtin("print", 0, 99)
def bi_print(args, line):
    print(" ".join(format_value(a) for a in args))
    return None


@_builtin("input", 0, 1)
def bi_input(args, line):
    prompt = format_value(args[0]) if args else ""
    try:
        text = input(prompt)
    except EOFError:
        return None  # end of input; callers check for nil (SPEC.md 9)
    except KeyboardInterrupt:
        raise BurlRuntimeError("Interrupted", line) from None
    return text


# ---- length / type ----------------------------------------------------------

@_builtin("len", 1)
def bi_len(args, line):
    value = args[0]
    if not isinstance(value, (str, list, dict)):
        raise BurlRuntimeError(f"len() needs a string, list or map, got {type_name(value)}", line)
    return len(value)


@_builtin("type", 1)
def bi_type(args, line):
    return type_name(args[0])


# ---- lists -------------------------------------------------------------------

@_builtin("push", 2)
def bi_push(args, line):
    lst = expect(args, line, "push", 0, "list")
    lst.append(args[1])
    return lst


@_builtin("pop", 1)
def bi_pop(args, line):
    lst = expect(args, line, "pop", 0, "list")
    if not lst:
        raise BurlRuntimeError("pop() on an empty list", line)
    return lst.pop()


@_builtin("range", 1, 3)
def bi_range(args, line):
    for i, a in enumerate(args):
        if isinstance(a, bool) or not isinstance(a, (int, float)) or a != int(a):
            raise BurlRuntimeError(f"range(): argument {i + 1} must be a whole number", line)
    nums = [int(a) for a in args]
    if len(nums) == 1:
        start, stop, step = 0, nums[0], 1
    elif len(nums) == 2:
        start, stop, step = nums[0], nums[1], 1
    else:
        start, stop, step = nums
    if step <= 0:
        raise BurlRuntimeError("range(): step must be positive", line)
    return list(range(start, stop, step))


@_builtin("join", 2)
def bi_join(args, line):
    lst = expect(args, line, "join", 0, "list")
    sep = expect(args, line, "join", 1, "string")
    return sep.join(format_value(item) for item in lst)


# ---- maps ---------------------------------------------------------------------

@_builtin("keys", 1)
def bi_keys(args, line):
    return list(expect(args, line, "keys", 0, "map").keys())


@_builtin("values", 1)
def bi_values(args, line):
    return list(expect(args, line, "values", 0, "map").values())


@_builtin("has", 2)
def bi_has(args, line):
    map_ = expect(args, line, "has", 0, "map")
    key = expect(args, line, "has", 1, "string")
    return key in map_


# ---- strings -------------------------------------------------------------------

@_builtin("split", 2)
def bi_split(args, line):
    text = expect(args, line, "split", 0, "string")
    sep = expect(args, line, "split", 1, "string")
    if sep == "":
        raise BurlRuntimeError("split(): separator must not be empty", line)
    return text.split(sep)


@_builtin("upper", 1)
def bi_upper(args, line):
    return expect(args, line, "upper", 0, "string").upper()


@_builtin("lower", 1)
def bi_lower(args, line):
    return expect(args, line, "lower", 0, "string").lower()


@_builtin("slice", 3)
def bi_slice(args, line):
    text = expect(args, line, "slice", 0, "string")
    start = expect(args, line, "slice", 1, "number")
    end = expect(args, line, "slice", 2, "number")
    for bound, label in ((start, "start"), (end, "end")):
        if isinstance(bound, bool) or bound != int(bound):
            raise BurlRuntimeError(f"slice(): {label} must be a whole number", line)
        if bound < 0 or bound > len(text):
            raise BurlRuntimeError(
                f"slice(): {label} {int(bound)} out of range (length {len(text)})", line)
    if start > end:
        raise BurlRuntimeError(
            f"slice(): start {int(start)} is after end {int(end)}", line)
    return text[int(start):int(end)]


@_builtin("find", 2, 3)
def bi_find(args, line):
    text = expect(args, line, "find", 0, "string")
    sub = expect(args, line, "find", 1, "string")
    start = 0
    if len(args) == 3:
        start = expect(args, line, "find", 2, "number")
        if isinstance(start, bool) or start != int(start) or start < 0:
            raise BurlRuntimeError("find(): start must be a whole number >= 0", line)
        start = int(start)
    return text.find(sub, start)  # -1 when absent: absence is a value here


@_builtin("contains", 2)
def bi_contains(args, line):
    text = expect(args, line, "contains", 0, "string")
    sub = expect(args, line, "contains", 1, "string")
    return sub in text


@_builtin("replace", 3)
def bi_replace(args, line):
    text = expect(args, line, "replace", 0, "string")
    old = expect(args, line, "replace", 1, "string")
    new = expect(args, line, "replace", 2, "string")
    if old == "":
        raise BurlRuntimeError("replace(): search string must not be empty", line)
    return text.replace(old, new)


@_builtin("trim", 1)
def bi_trim(args, line):
    return expect(args, line, "trim", 0, "string").strip()


@_builtin("str", 1)
def bi_str(args, line):
    return format_value(args[0])


# ---- numbers --------------------------------------------------------------------

@_builtin("num", 1)
def bi_num(args, line):
    value = args[0]
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        text = value.strip()
        try:
            return int(text)
        except ValueError:
            try:
                return float(text)
            except ValueError:
                return None
    raise BurlRuntimeError(f"num() needs a string or number, got {type_name(value)}", line)


@_builtin("int", 1)
def bi_int(args, line):
    value = args[0]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BurlRuntimeError(f"int() needs a number, got {type_name(value)}", line)
    return math.trunc(value)


@_builtin("abs", 1)
def bi_abs(args, line):
    return abs(expect(args, line, "abs", 0, "number"))


def _min_max(name, args, line, chooser):
    if len(args) == 1:
        lst = expect(args, line, name, 0, "list")
        if not lst:
            raise BurlRuntimeError(f"{name}() on an empty list", line)
        args = lst
    result = args[0]
    for value in args[1:]:
        if type_name(value) != type_name(result) or \
           not (isinstance(value, (int, float)) or isinstance(value, str)):
            raise BurlRuntimeError(f"{name}(): arguments must all be numbers or all strings", line)
        result = chooser(result, value)
    return result


@_builtin("min", 1, 99)
def bi_min(args, line):
    return _min_max("min", args, line, lambda a, b: b if b < a else a)


@_builtin("max", 1, 99)
def bi_max(args, line):
    return _min_max("max", args, line, lambda a, b: b if b > a else a)


@_builtin("floor", 1)
def bi_floor(args, line):
    return float(math.floor(expect(args, line, "floor", 0, "number")))


@_builtin("round", 1, 2)
def bi_round(args, line):
    value = expect(args, line, "round", 0, "number")
    digits = 0
    if len(args) == 2:
        digits = int(expect(args, line, "round", 1, "number"))
    factor = 10 ** digits
    return math.floor(value * factor + 0.5) / factor


@_builtin("random", 0)
def bi_random(args, line):
    return _py_random.random()


@_builtin("apply", 2)
def bi_apply(args, line):
    """apply(f, args_list): call f with a list of arguments.

    Added for the 0.4 bootstrap: Burl code driving the host runtime needs a
    way to hand a list of already-evaluated arguments to a builtin. A
    general-purpose tool as well.
    """
    fn = args[0]
    arg_list = args[1]
    if not isinstance(arg_list, list):
        raise BurlRuntimeError(
            f"apply(): argument 2 must be a list, got {type_name(arg_list)}", line)
    if isinstance(fn, Builtin):
        return fn.call(arg_list, line)
    if isinstance(fn, BurlFunction):
        from .interpreter import _host_call_function
        return _host_call_function(fn, arg_list, line)
    raise BurlRuntimeError(f"apply(): argument 1 must be a fn, got {type_name(fn)}", line)


# ---- files / time ----------------------------------------------------------------

@_builtin("read", 1)
def bi_read(args, line):
    path = expect(args, line, "read", 0, "string")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()
    except OSError as exc:
        raise BurlRuntimeError(f"read(): cannot read '{path}': {exc.strerror or exc}", line) from None


@_builtin("write", 2)
def bi_write(args, line):
    path = expect(args, line, "write", 0, "string")
    text = expect(args, line, "write", 1, "string")
    try:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
    except OSError as exc:
        raise BurlRuntimeError(f"write(): cannot write '{path}': {exc.strerror or exc}", line) from None
    return None


@_builtin("clock", 0)
def bi_clock(args, line):
    return float(time.time() * 1000)


# ---- the global environment ---------------------------------------------------

def global_env():
    """The global scope preloaded with every builtin."""
    from .interpreter import Env  # local import avoids a cycle

    env = Env()
    for obj in list(globals().values()):
        if isinstance(obj, Builtin):
            env.values[obj.name] = (obj, False, None)
    return env
