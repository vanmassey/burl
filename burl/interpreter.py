"""The Burl tree-walking interpreter.

Values map to Python values directly:
  nil -> None, bool -> bool, number -> int | float, string -> str,
  list -> list, map -> dict, fn -> BurlFunction | Builtin.
"""

from .builtins import Builtin
from .errors import BurlRuntimeError
from .parser import (Assign, Binop, Block, Bool, Break, Call, Continue, ExprStmt,
                     FnDecl, FnExpr, For, If, Index, ListLit, MapLit, Member, Neg,
                     Nil, Not, Num, Program, Return, Str, Var, While, Let)
from .values import (NUMERIC, BurlFunction, check_hint, format_value, is_equal,
                     satisfies, truthy, type_name)


# --------------------------------------------------------------------------
# Error flow: break/continue/return travel as control-flow exceptions.
# --------------------------------------------------------------------------

class _BreakSignal(Exception):
    pass


class _ContinueSignal(Exception):
    pass


class _ReturnSignal(Exception):
    def __init__(self, value):
        self.value = value


# --------------------------------------------------------------------------
# Scopes
# --------------------------------------------------------------------------

class Env:
    """A block scope: name -> (value, const, hint)."""

    def __init__(self, parent=None):
        self.values = {}
        self.parent = parent

    def _find(self, name):
        env = self
        while env is not None:
            if name in env.values:
                return env
            env = env.parent
        return None

    def define(self, name, value, line, const=False, hint=None):
        if name in self.values:
            raise BurlRuntimeError(f"Name '{name}' is already defined in this block", line)
        check_hint(value, hint, name, line)
        self.values[name] = (value, const, hint)

    def get(self, name, line):
        env = self._find(name)
        if env is None:
            raise BurlRuntimeError(f"Undefined name '{name}'", line)
        return env.values[name][0]

    def assign(self, name, value, line):
        env = self._find(name)
        if env is None:
            raise BurlRuntimeError(f"Undefined name '{name}'", line)
        value_, const, hint = env.values[name]
        if const:
            raise BurlRuntimeError(f"Cannot assign to const '{name}'", line)
        check_hint(value, hint, name, line)
        env.values[name] = (value, const, hint)


# --------------------------------------------------------------------------
# Type hints (SPEC.md section 8)
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# The interpreter
# --------------------------------------------------------------------------

class Interpreter:
    def __init__(self, builtins_env=None):
        from .builtins import global_env  # local import avoids a cycle
        self.globals = builtins_env if builtins_env is not None else global_env()
        self._exec_map = {
            Let: self.exec_let, FnDecl: self.exec_fn_decl, If: self.exec_if,
            While: self.exec_while, For: self.exec_for, Return: self.exec_return,
            Break: self.exec_break, Continue: self.exec_continue,
            ExprStmt: self.exec_expr_stmt, Assign: self.exec_assign,
            Block: self.exec_block_stmt,
        }
        self._eval_map = {
            Num: lambda n, env: n.value,
            Str: self.eval_str, Var: self.eval_var, Bool: lambda n, env: n.value,
            Nil: lambda n, env: None, ListLit: self.eval_list, MapLit: self.eval_map,
            Binop: self.eval_binop, Not: self.eval_not, Neg: self.eval_neg,
            Call: self.eval_call, Index: self.eval_index, Member: self.eval_member,
            FnExpr: self.eval_fn_expr,
        }

    # ---- entry points ------------------------------------------------------

    def run(self, program):
        """Execute a Program's top-level statements."""
        try:
            self.exec_stmts(program.stmts, self.globals)
        except _ReturnSignal:
            raise BurlRuntimeError("'return' used outside of a function", program.line) from None
        except _BreakSignal:
            raise BurlRuntimeError("'break' used outside of a loop", program.line) from None
        except _ContinueSignal:
            raise BurlRuntimeError("'continue' used outside of a loop", program.line) from None

    def run_with_result(self, program):
        """Execute, returning the value of a trailing expression statement.

        Used by the REPL so typing `1 + 2` prints `3`.
        """
        stmts = program.stmts
        try:
            if stmts and isinstance(stmts[-1], ExprStmt):
                self.exec_stmts(stmts[:-1], self.globals)
                return self.eval(stmts[-1].expr, self.globals)
            self.exec_stmts(stmts, self.globals)
            return None
        except _ReturnSignal:
            raise BurlRuntimeError("'return' used outside of a function", program.line) from None
        except _BreakSignal:
            raise BurlRuntimeError("'break' used outside of a loop", program.line) from None
        except _ContinueSignal:
            raise BurlRuntimeError("'continue' used outside of a loop", program.line) from None

    # ---- statements ---------------------------------------------------------

    def exec_stmts(self, stmts, env):
        for stmt in stmts:
            self.exec_stmt(stmt, env)

    def exec_stmt(self, stmt, env):
        self._exec_map[type(stmt)](stmt, env)

    def exec_block_stmt(self, stmt, env):
        self.exec_stmts(stmt.stmts, Env(env))

    def exec_let(self, stmt, env):
        env.define(stmt.name, self.eval(stmt.expr, env), stmt.line,
                   const=stmt.const, hint=stmt.hint)

    def exec_fn_decl(self, stmt, env):
        fn = BurlFunction(stmt.name, stmt.params, stmt.ret_hint, stmt.body, env, stmt.line)
        env.define(stmt.name, fn, stmt.line)

    def exec_if(self, stmt, env):
        if truthy(self.eval(stmt.cond, env)):
            self.exec_stmts(stmt.then, Env(env))
        elif stmt.els is not None:
            self.exec_stmts(stmt.els, Env(env))

    def exec_while(self, stmt, env):
        while truthy(self.eval(stmt.cond, env)):
            try:
                self.exec_stmts(stmt.body, Env(env))
            except _BreakSignal:
                break
            except _ContinueSignal:
                continue

    def exec_for(self, stmt, env):
        iterable = self.eval(stmt.iterable, env)
        if isinstance(iterable, list):
            items = iterable
        elif isinstance(iterable, str):
            items = list(iterable)
        elif isinstance(iterable, dict):
            items = list(iterable.keys())
        else:
            raise BurlRuntimeError(
                f"for-in needs a list, string or map, got {type_name(iterable)}", stmt.line)
        for item in items:
            loop_env = Env(env)
            loop_env.define(stmt.var, item, stmt.line)
            try:
                self.exec_stmts(stmt.body, Env(loop_env))
            except _BreakSignal:
                break
            except _ContinueSignal:
                continue

    def exec_return(self, stmt, env):
        value = self.eval(stmt.expr, env) if stmt.expr is not None else None
        raise _ReturnSignal(value)

    def exec_break(self, stmt, env):
        raise _BreakSignal()

    def exec_continue(self, stmt, env):
        raise _ContinueSignal()

    def exec_expr_stmt(self, stmt, env):
        self.eval(stmt.expr, env)

    def exec_assign(self, stmt, env):
        target = stmt.target
        if isinstance(target, Var):
            env.assign(target.name, self.eval(stmt.value, env), stmt.line)
            return
        # Index / Member targets: evaluate the container, then mutate it.
        container = self.eval(target.obj, env)
        value = self.eval(stmt.value, env)
        if isinstance(target, Index):
            index = self.eval(target.index, env)
            if isinstance(container, list):
                i = self.check_int_index(container, index, stmt.line)
                container[i] = value
            elif isinstance(container, dict):
                if not isinstance(index, str):
                    raise BurlRuntimeError(
                        f"Map keys must be strings, got {type_name(index)}", stmt.line)
                container[index] = value
            else:
                raise BurlRuntimeError(
                    f"Cannot index-assign into {type_name(container)}", stmt.line)
        else:  # Member
            if not isinstance(container, dict):
                raise BurlRuntimeError(
                    f".{target.name} access needs a map, got {type_name(container)}", stmt.line)
            container[target.name] = value

    # ---- expressions ---------------------------------------------------------

    def eval(self, expr, env):
        return self._eval_map[type(expr)](expr, env)

    def eval_var(self, expr, env):
        return env.get(expr.name, expr.line)

    def eval_str(self, expr, env):
        out = []
        for kind, payload in expr.parts:
            if kind == "lit":
                out.append(payload)
            else:
                out.append(format_value(self.eval(payload, env)))
        return "".join(out)

    def eval_list(self, expr, env):
        return [self.eval(item, env) for item in expr.items]

    def eval_map(self, expr, env):
        return {key: self.eval(value, env) for key, value in expr.items}

    def eval_not(self, expr, env):
        return not truthy(self.eval(expr.expr, env))

    def eval_neg(self, expr, env):
        value = self.eval(expr.expr, env)
        if not isinstance(value, NUMERIC) or isinstance(value, bool):
            raise BurlRuntimeError(f"Unary '-' needs a number, got {type_name(value)}", expr.line)
        return -value

    def eval_binop(self, expr, env):
        op = expr.op
        if op == "and":
            left = self.eval(expr.left, env)
            return self.eval(expr.right, env) if truthy(left) else left
        if op == "or":
            left = self.eval(expr.left, env)
            return left if truthy(left) else self.eval(expr.right, env)
        left = self.eval(expr.left, env)
        right = self.eval(expr.right, env)
        line = expr.line
        if op == "+":
            if isinstance(left, str) and isinstance(right, str):
                return left + right
            return self.numbers(op, left, right, line,
                                lambda a, b: a + b)
        if op == "-":
            return self.numbers(op, left, right, line, lambda a, b: a - b)
        if op == "*":
            return self.numbers(op, left, right, line, lambda a, b: a * b)
        if op == "/":
            def divide(a, b):
                if b == 0:
                    raise BurlRuntimeError("Division by zero", line)
                return a / b
            return self.numbers(op, left, right, line, divide)
        if op == "%":
            def mod(a, b):
                if b == 0:
                    raise BurlRuntimeError("Modulo by zero", line)
                return a % b
            return self.numbers(op, left, right, line, mod)
        if op == "==":
            return is_equal(left, right)
        if op == "!=":
            return not is_equal(left, right)
        if op in ("<", "<=", ">", ">="):
            return self.compare(op, left, right, line)
        raise BurlRuntimeError(f"Unknown operator '{op}'", line)

    def numbers(self, op, a, b, line, fn):
        ok_a = isinstance(a, NUMERIC) and not isinstance(a, bool)
        ok_b = isinstance(b, NUMERIC) and not isinstance(b, bool)
        if not (ok_a and ok_b):
            raise BurlRuntimeError(
                f"Operator '{op}' needs numbers, got {type_name(a)} and {type_name(b)}", line)
        return fn(a, b)

    def compare(self, op, a, b, line):
        ok = (isinstance(a, NUMERIC) and isinstance(b, NUMERIC)
              and not isinstance(a, bool) and not isinstance(b, bool)) \
            or (isinstance(a, str) and isinstance(b, str))
        if not ok:
            raise BurlRuntimeError(
                f"Cannot compare {type_name(a)} and {type_name(b)} with '{op}'", line)
        if op == "<":
            return a < b
        if op == "<=":
            return a <= b
        if op == ">":
            return a > b
        return a >= b

    def check_int_index(self, container, index, line, for_read_len=None):
        """Validate a list/string index and return it as a Python int."""
        if isinstance(index, bool) or not isinstance(index, (int, float)) or index != int(index):
            got = format_value(index)
            raise BurlRuntimeError(f"Index must be a whole number, got {got}", line)
        i = int(index)
        if for_read_len is not None:
            if i < 0 or i >= for_read_len:
                raise BurlRuntimeError(
                    f"Index {i} out of range (length {for_read_len})", line)
        else:
            if i < 0 or i >= len(container):
                raise BurlRuntimeError(
                    f"Index {i} out of range (length {len(container)})", line)
        return i

    def eval_index(self, expr, env):
        obj = self.eval(expr.obj, env)
        index = self.eval(expr.index, env)
        if isinstance(obj, list):
            return obj[self.check_int_index(obj, index, expr.line, for_read_len=len(obj))]
        if isinstance(obj, str):
            i = self.check_int_index(obj, index, expr.line, for_read_len=len(obj))
            return obj[i]
        if isinstance(obj, dict):
            if not isinstance(index, str):
                raise BurlRuntimeError(
                    f"Map keys must be strings, got {type_name(index)}", expr.line)
            return self.map_get(obj, index, expr.line, "index")
        raise BurlRuntimeError(f"Cannot index {type_name(obj)}", expr.line)

    def eval_member(self, expr, env):
        obj = self.eval(expr.obj, env)
        if isinstance(obj, dict):
            return self.map_get(obj, expr.name, expr.line, f".{expr.name}")
        raise BurlRuntimeError(
            f".{expr.name} access needs a map, got {type_name(obj)}", expr.line)

    @staticmethod
    def map_get(map_, key, line, via):
        if key not in map_:
            raise BurlRuntimeError(f"Map has no key '{key}' (via {via})", line)
        return map_[key]

    def eval_call(self, expr, env):
        fn = self.eval(expr.fn, env)
        args = [self.eval(a, env) for a in expr.args]
        if isinstance(fn, Builtin):
            try:
                return fn.call(args, expr.line)
            except BurlRuntimeError as err:
                if err.line is None:
                    raise BurlRuntimeError(err.message, expr.line) from None
                raise
        if isinstance(fn, BurlFunction):
            return self.call_function(fn, args, expr.line)
        raise BurlRuntimeError(f"Cannot call {type_name(fn)}", expr.line)

    def call_function(self, fn, args, line):
        if len(args) != len(fn.params):
            raise BurlRuntimeError(
                f"Function '{fn.name}' expects {len(fn.params)} argument(s), got {len(args)}",
                line)
        call_env = Env(fn.env)
        for (name, hint), value in zip(fn.params, args):
            call_env.define(name, value, line, hint=hint)
        try:
            self.exec_stmts(fn.body.stmts, Env(call_env))
        except _ReturnSignal as ret:
            check_hint(ret.value, fn.ret_hint, f"return of '{fn.name}'", line)
            return ret.value
        check_hint(None, fn.ret_hint, f"return of '{fn.name}'", line)
        return None

    def eval_fn_expr(self, expr, env):
        return BurlFunction("<anonymous>", expr.params, expr.ret_hint, expr.body, env, expr.line)
