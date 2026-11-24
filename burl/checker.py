"""The Burl static checker (`burl check`, SPEC.md 12, ROADMAP v0.3 'Iron').

The checker is *advisory, never load-bearing*: it reads the optional type
hints of SPEC.md 8 and reports every problem it can prove from the source,
before the program runs. It can only see what the parser sees — the
interpreter's behavior is not changed by any of it.

Static semantics mirrored from the interpreter:
  - Scopes are blocks; a name defined in a block is visible for the whole
    block — including in functions declared inside it, because closures
    capture the environment object, not a snapshot of it.
  - Top-level statements run in the builtins' own environment, so defining
    a name that a builtin has there is the interpreter's "already defined"
    error; shadowing a builtin from a nested scope is legal.
  - `for` loop variables live in a scope wrapping the loop body.

Levels (ROADMAP v0.3):
  1. annotation-vs-annotation: call sites, assignments, returns.
  2. inference for expressions whose type can be proven.
"""

from .parser import (Assign, Binop, Bool, Break, Call, Continue, ExprStmt,
                     FnDecl, FnExpr, For, If, Index, Let, ListLit, MapLit,
                     Member, Neg, Nil, Not, Num, Return, Str, Var, While,
                     parse)
from .errors import BurlError
from .builtins import Builtin
from . import builtins as _builtins_module


# ---------------------------------------------------------------------------
# Builtin signatures
# ---------------------------------------------------------------------------

# Per-builtin return type and positional argument hints we are confident
# about. Arity is read from the live Builtin objects in builtins.py so the
# two can never drift. None = unknown or too dynamic to claim.
_BUILTIN_TYPES = {
    "print":    (None, ()),
    "input":    ("string", ()),
    "len":      ("number", (("string", "list", "map"),)),
    "type":     ("string", ()),
    "push":     ("list", (("list",), None)),
    "pop":      (None, (("list",),)),
    "range":    ("list", (("number",), ("number",), ("number",))),
    "join":     ("string", (("list",), ("string",))),
    "keys":     ("list", (("map",),)),
    "values":   ("list", (("map",),)),
    "has":      ("bool", (("map",), ("string",))),
    "split":    ("list", (("string",), ("string",))),
    "upper":    ("string", (("string",),)),
    "lower":    ("string", (("string",),)),
    "slice":    ("string", (("string",), ("number",), ("number",))),
    "find":     ("number", (("string",), ("string",), ("number",))),
    "contains": ("bool", (("string",), ("string",))),
    "replace":  ("string", (("string",), ("string",), ("string",))),
    "trim":     ("string", (("string",),)),
    "str":      ("string", ()),
    "num":      (None, (("number", "string"),)),  # may also return nil
    "int":      ("number", (("number",),)),
    "abs":      ("number", (("number",),)),
    "min":      (None, ()),
    "max":      (None, ()),
    "floor":    ("number", (("number",),)),
    "round":    ("number", (("number",), ("number",))),
    "random":   ("number", ()),
    "read":     ("string", (("string",),)),
    "write":    (None, (("string",), ("string",))),
    "clock":    ("number", ()),
}


def _builtin_sigs():
    """name -> (min_args, max_args, ret_type_or_None, arg_hints).

    `import` is defined by the interpreter, not the builtins module, so it
    gets its arity here: `import(path)` with one argument (interpreter.py).
    """
    sigs = {}
    for obj in vars(_builtins_module).values():
        if isinstance(obj, Builtin):
            sigs[obj.name] = [obj.min_args, obj.max_args, None, ()]
    for name, (ret, arg_hints) in _BUILTIN_TYPES.items():
        if name not in sigs:
            mn = mx = len(arg_hints)
            sigs[name] = [mn, mx, ret, ()]
        sigs[name][2] = ret
        sigs[name][3] = arg_hints
    sigs["import"] = [1, 1, "map", (("string",),)]
    return sigs


# ---------------------------------------------------------------------------
# Diagnostics and scopes
# ---------------------------------------------------------------------------

class Diagnostic:
    __slots__ = ("severity", "line", "message")

    def __init__(self, severity, line, message):
        self.severity = severity  # "error" (would fail or is certainly wrong)
        self.line = line          # or "warning" (probably a problem)
        self.message = message

    def __repr__(self):
        return f"line {self.line}: {self.severity}: {self.message}"


class Binding:
    """What one name is known to be, statically."""

    __slots__ = ("kind", "type", "params", "ret", "hint", "sig", "line",
                 "const", "used", "placeholder")

    def __init__(self, kind, type=None, params=None, ret=None, hint=None,
                 sig=None, line=0, const=False, placeholder=False):
        self.kind = kind      # "fn" | "var" | "builtin"
        self.type = type      # static type name, or None (unknown)
        self.params = params  # [(name, hint)] — fns only
        self.ret = ret        # return hint — fns only
        self.hint = hint      # declared hint — vars only
        self.sig = sig        # (min, max, ret, arg_hints) — builtins only
        self.line = line
        self.const = const
        self.used = False
        self.placeholder = placeholder  # preregistered, not yet walked


class Scope:
    __slots__ = ("values", "parent")

    def __init__(self, parent=None):
        self.values = {}
        self.parent = parent

    def lookup(self, name):
        scope = self
        while scope is not None:
            binding = scope.values.get(name)
            if binding is not None:
                binding.used = True
                return binding
            scope = scope.parent
        return None


def _compatible(inferred_type, hint):
    if inferred_type is None or hint is None or hint == "any":
        return True
    return inferred_type == hint


# ---------------------------------------------------------------------------
# The checker
# ---------------------------------------------------------------------------

class Checker:
    def __init__(self):
        self.diags = []
        self.builtins = _builtin_sigs()
        self.fn_stack = []  # (ret_hint, display_name), innermost last

    def error(self, line, message):
        self.diags.append(Diagnostic("error", line, message))

    def warn(self, line, message):
        self.diags.append(Diagnostic("warning", line, message))

    # ---- entry --------------------------------------------------------------

    def check_program(self, source):
        try:
            program = parse(source)
        except BurlError as err:
            self.error(err.line, f"{err.kind} error: {err.message}")
            return
        root = Scope()
        for name, (mn, mx, ret, arg_hints) in self.builtins.items():
            root.values[name] = Binding("builtin", type="fn", sig=(mn, mx, ret, arg_hints))
        self.check_stmts(program.stmts, root, in_loop=False)
        self.report_unused(root)

    # ---- statements -----------------------------------------------------------

    def check_stmts(self, stmts, scope, in_loop):
        self._preregister(stmts, scope)
        for stmt in stmts:
            self.check_stmt(stmt, scope, in_loop)

    # Scopes, not moments, are what a function body's free names consult:
    # closures capture the environment object, so a name defined later in
    # an enclosing scope is visible to it at call time (adventure.burl's
    # game loop relies on this). So every scope's own let/fn declarations
    # are preregistered here before its statements are checked, and filled
    # in as the walk reaches them. A use that arrives before the fill sees
    # type unknown — the checker stays quiet instead of claiming an error
    # the interpreter might not raise (advisory, never load-bearing).
    def _preregister(self, stmts, scope):
        for stmt in stmts:
            name = getattr(stmt, "name", None)
            if name is None:
                continue
            if name in scope.values:
                continue  # first binding wins; the dup is caught at its stmt
            if isinstance(stmt, FnDecl):
                scope.values[name] = Binding("fn", params=stmt.params,
                                             ret=stmt.ret_hint, line=stmt.line,
                                             placeholder=True)
            elif isinstance(stmt, FnExpr):
                continue
            else:
                scope.values[name] = Binding("var", hint=stmt.hint,
                                             line=stmt.line, const=stmt.const,
                                             placeholder=True)

    def check_stmt(self, stmt, scope, in_loop):
        method = getattr(self, "_check_" + type(stmt).__name__.lower(), None)
        if method is not None:  # unknown node: silent, never wrong
            method(stmt, scope, in_loop)

    def _define(self, scope, line, name, fill, create):
        """Bind `name`, or error when the scope already holds a real binding.

        The preregistered placeholder (if any) is filled in place; the same
        Binding object keeps the `used` marks from earlier lookups.
        """
        existing = scope.values.get(name)
        if existing is None:
            binding = create()
            scope.values[name] = binding
            return binding
        if existing.placeholder:
            fill(existing)
            existing.placeholder = False
            return existing
        if existing.kind == "builtin":
            self.error(line,
                       f"'{name}' is a builtin; redefining it at the top "
                       f"level fails at runtime. Choose another name.")
        else:
            self.error(line,
                       f"Name '{name}' is already defined in this block "
                       f"(line {existing.line})")
        return existing

    def _check_let(self, stmt, scope, in_loop):
        inferred = self.infer(stmt.expr, scope)
        if not _compatible(inferred, stmt.hint):
            self.error(stmt.line,
                       f"'{stmt.name}' is declared as '{stmt.hint}' but the "
                       f"initializer has type '{inferred}'")
        static_type = stmt.hint if stmt.hint and stmt.hint != "any" else inferred

        def fill(b):
            b.type = static_type

        def create():
            return Binding("var", type=static_type, hint=stmt.hint,
                           line=stmt.line, const=stmt.const)

        self._define(scope, stmt.line, stmt.name, fill, create)

    def _check_fndecl(self, stmt, scope, in_loop):
        def fill(b):
            b.type = "fn"

        def create():
            return Binding("fn", type="fn", params=stmt.params,
                           ret=stmt.ret_hint, line=stmt.line)

        self._define(scope, stmt.line, stmt.name, fill, create)
        self._check_fn_body(stmt.name, stmt.params, stmt.ret_hint, stmt.body,
                            scope)

    def _check_fn_body(self, name, params, ret_hint, body, outer_scope):
        scope = Scope(outer_scope)
        for pname, phint in params:
            scope.values[pname] = Binding("var", type=phint, hint=phint)
        self.fn_stack.append((ret_hint, name))
        self.check_stmts(body.stmts, scope, in_loop=False)
        self.fn_stack.pop()
        self.report_unused(scope, exclude={pname for pname, _ in params})

    def _check_if(self, stmt, scope, in_loop):
        self.infer(stmt.cond, scope)
        self.check_stmts(stmt.then, Scope(scope), in_loop)
        if stmt.els is not None:
            self.check_stmts(stmt.els, Scope(scope), in_loop)

    def _check_while(self, stmt, scope, in_loop):
        self.infer(stmt.cond, scope)
        self.check_stmts(stmt.body, Scope(scope), in_loop=True)

    def _check_for(self, stmt, scope, in_loop):
        ity = self.infer(stmt.iterable, scope)
        if ity is not None and ity not in ("list", "string", "map"):
            self.error(stmt.line,
                       f"for-in needs a list, string or map, got '{ity}'")
        loop_scope = Scope(scope)
        loop_scope.values[stmt.var] = Binding("var")
        self.check_stmts(stmt.body, Scope(loop_scope), in_loop=True)

    def _check_return(self, stmt, scope, in_loop):
        ty = self.infer(stmt.expr, scope) if stmt.expr is not None else "nil"
        if not self.fn_stack:
            self.error(stmt.line, "'return' used outside of a function")
            return
        ret_hint, name = self.fn_stack[-1]
        if not _compatible(ty, ret_hint):
            self.error(stmt.line,
                       f"'{name}' declares its return as '{ret_hint}' but "
                       f"this return has type '{ty}'")

    def _check_break(self, stmt, scope, in_loop):
        # Inside a function the loop's fate is a runtime affair (the signal
        # travels) — only flag it with no loop in sight at all.
        if not in_loop and not self.fn_stack:
            self.error(stmt.line, "'break' used outside of a loop")

    def _check_continue(self, stmt, scope, in_loop):
        if not in_loop and not self.fn_stack:
            self.error(stmt.line, "'continue' used outside of a loop")

    def _check_exprstmt(self, stmt, scope, in_loop):
        self.infer(stmt.expr, scope)

    def _check_assign(self, stmt, scope, in_loop):
        target = stmt.target
        binding = None
        if isinstance(target, Var):
            binding = scope.lookup(target.name)
            if binding is None:
                self.error(stmt.line, f"Undefined name '{target.name}'")
        elif isinstance(target, (Index, Member)):
            self._check_location(target, scope)
        inferred = self.infer(stmt.value, scope)
        if isinstance(target, Var) and binding is not None:
            if not _compatible(inferred, binding.hint):
                self.error(stmt.line,
                           f"'{target.name}' is declared as "
                           f"'{binding.hint}' but assigned a value of type "
                           f"'{inferred}'")
            elif binding.hint is None and binding.type is not None \
                    and inferred is not None and inferred != binding.type:
                binding.type = None  # the variable's type widened; give up

    def _check_block(self, stmt, scope, in_loop):
        self.check_stmts(stmt.stmts, Scope(scope), in_loop)

    # ---- locations (Index / Member, read or write target) ----------------------

    def _check_location(self, node, scope):
        """Validate an Index/Member node; returns the object's type or None."""
        ty = self.infer(node.obj, scope)
        if ty is None:
            return
        if isinstance(node, Index):
            ity = self.infer(node.index, scope)
            if ty in ("list", "string"):
                if ity is not None and ity != "number":
                    self.error(node.line,
                               f"Index must be a whole number, got '{ity}'")
            elif ty == "map":
                if ity is not None and ity != "string":
                    self.error(node.line,
                               f"Map keys must be strings, got '{ity}'")
            else:
                self.error(node.line, f"Cannot index a value of type '{ty}'")
        else:
            if ty != "map":
                self.error(node.line,
                           f".{node.name} access needs a map, got {ty}")

    # ---- expressions. infer() returns a type name, or None when unknown ------
    # It emits diagnostics itself and walks every subexpression exactly once.

    def infer(self, expr, scope):
        if expr is None:
            return None
        if isinstance(expr, Num):
            return "number"
        if isinstance(expr, Bool):
            return "bool"
        if isinstance(expr, Nil):
            return "nil"
        if isinstance(expr, Str):
            for kind, payload in expr.parts:
                if kind == "expr":
                    self.infer(payload, scope)
            return "string"
        if isinstance(expr, ListLit):
            for item in expr.items:
                self.infer(item, scope)
            return "list"
        if isinstance(expr, MapLit):
            for _key, value in expr.items:
                self.infer(value, scope)
            return "map"
        if isinstance(expr, Var):
            binding = scope.lookup(expr.name)
            if binding is None:
                self.error(expr.line, f"Undefined name '{expr.name}'")
                return None
            return binding.type
        if isinstance(expr, FnExpr):
            scope2 = Scope(scope)
            for pname, phint in expr.params:
                scope2.values[pname] = Binding("var", type=phint, hint=phint)
            self.fn_stack.append((expr.ret_hint, "<fn>"))
            self.check_stmts(expr.body.stmts, scope2, in_loop=False)
            self.fn_stack.pop()
            return "fn"
        if isinstance(expr, Binop):
            lt = self.infer(expr.left, scope)
            rt = self.infer(expr.right, scope)
            return self._infer_binop(expr, lt, rt)
        if isinstance(expr, Not):
            self.infer(expr.expr, scope)
            return "bool"
        if isinstance(expr, Neg):
            ty = self.infer(expr.expr, scope)
            if ty is not None and ty != "number":
                self.error(expr.line, f"Unary '-' needs a number, got {ty}")
            return "number"
        if isinstance(expr, Call):
            return self._check_call(expr, scope)
        if isinstance(expr, Index):
            obj_ty = self._check_location(expr, scope)
            return "string" if obj_ty == "string" else None
        if isinstance(expr, Member):
            self._check_location(expr, scope)
            return None
        return None

    def _infer_binop(self, expr, lt, rt):
        op = expr.op
        if op in ("and", "or"):
            return None  # returns the operand value, not a bool
        if op in ("==", "!="):
            return "bool"  # cross-type == is false by design, never an error
        if op in ("<", "<=", ">", ">="):
            if lt is not None and rt is not None and not (
                    (lt == "number" and rt == "number")
                    or (lt == "string" and rt == "string")):
                self.error(expr.line,
                           f"Cannot compare {lt} and {rt} with '{op}'")
            return "bool"
        if lt is not None and rt is not None:
            if op == "+":
                if lt == "string" and rt == "string":
                    return "string"
                if lt == "number" and rt == "number":
                    return "number"
                self.error(expr.line,
                           f"Operator '+' needs two strings or two numbers, "
                           f"got {lt} and {rt}")
                return None
            if lt != "number" or rt != "number":
                self.error(expr.line,
                           f"Operator '{op}' needs numbers, got {lt} and {rt}")
                return None
        return "number" if "number" == lt == rt else None

    def _check_call(self, expr, scope):
        arg_types = [self.infer(a, scope) for a in expr.args]
        callee = expr.fn
        if isinstance(callee, Var):
            binding = scope.lookup(callee.name)
            if binding is None:
                self.error(callee.line, f"Undefined name '{callee.name}'")
                return None
        else:
            ty = self.infer(callee, scope)
            if ty is not None and ty != "fn":
                self.error(expr.line, f"Cannot call a value of type '{ty}'")
            return None  # nothing more provable about a computed callee
        display = callee.name
        if binding.kind == "var":
            if binding.type is not None and binding.type != "fn":
                self.error(expr.line,
                           f"Cannot call a value of type '{binding.type}'")
            return None
        if binding.kind == "builtin":
            min_args, max_args, ret, arg_hints = binding.sig
            n = len(arg_types)
            if not (min_args <= n <= max_args):
                want = str(min_args) if min_args == max_args else f"{min_args}..{max_args}"
                self.error(expr.line,
                           f"{display}() expects {want} argument(s), got {n}")
                return None
            for i, allowed in enumerate(arg_hints):
                if allowed is None or i >= n:
                    continue
                if arg_types[i] is not None and arg_types[i] not in allowed:
                    self.error(expr.line,
                               f"{display}(): argument {i + 1} must be a "
                               f"{' or '.join(allowed)}, got '{arg_types[i]}'")
            return ret
        # User function: exact arity, plus hint-checks we can prove.
        n = len(binding.params)
        if len(arg_types) != n:
            self.error(expr.line,
                       f"Function '{display}' expects {n} argument(s), "
                       f"got {len(arg_types)}")
            return binding.ret
        for i, (_pname, phint) in enumerate(binding.params):
            if not _compatible(arg_types[i], phint):
                self.error(expr.line,
                           f"Function '{display}' wants '{phint}' for "
                           f"argument {i + 1}, got '{arg_types[i]}'")
        return binding.ret

    # ---- unused locals (level 2 nicety) ----------------------------------------

    def report_unused(self, scope, exclude=frozenset()):
        for name, binding in scope.values.items():
            if name in exclude or binding.kind != "var":
                continue
            if binding.used or binding.const or binding.placeholder:
                continue
            self.warn(binding.line, f"Unused variable '{name}'")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def check_source(source):
    """Check Burl source; returns a list of Diagnostic sorted by line."""
    checker = Checker()
    checker.check_program(source)
    return sorted(checker.diags, key=lambda d: (d.line, d.severity != "error"))
