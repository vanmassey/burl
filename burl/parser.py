"""The Burl parser: token list -> AST.

AST nodes are small dataclasses in this module. Every statement node carries
the line it started on for error reporting.
"""

from dataclasses import dataclass
from typing import Optional

from .errors import ParseError
from .lexer import lex, Token

# The fixed vocabulary of type hints (SPEC.md section 8).
TYPES = {"number", "string", "bool", "nil", "list", "map", "fn", "any"}

COMPARE_OPS = {"==", "!=", "<", "<=", ">", ">="}


# --------------------------------------------------------------------------
# Statements
# --------------------------------------------------------------------------

@dataclass
class Program:
    stmts: list
    line: int = 1


@dataclass
class Let:
    line: int
    name: str
    expr: object
    hint: Optional[str] = None
    const: bool = False


@dataclass
class FnDecl:
    line: int
    name: str
    params: list          # [(name, hint_or_None)]
    ret_hint: Optional[str]
    body: "Block"


@dataclass
class If:
    line: int
    cond: object
    then: list            # statement list
    els: Optional[list]   # statement list (an `else if` nests another If)


@dataclass
class While:
    line: int
    cond: object
    body: list


@dataclass
class For:
    line: int
    var: str
    iterable: object
    body: list


@dataclass
class Return:
    line: int
    expr: Optional[object]


@dataclass
class Break:
    line: int


@dataclass
class Continue:
    line: int


@dataclass
class ExprStmt:
    line: int
    expr: object


@dataclass
class Assign:
    line: int
    target: object        # Var | Index | Member
    value: object


@dataclass
class Block:
    line: int
    stmts: list


# --------------------------------------------------------------------------
# Expressions
# --------------------------------------------------------------------------

@dataclass
class Num:
    value: float
    line: int


@dataclass
class Str:
    line: int
    parts: list           # [("lit", text) | ("expr", ast_expr)]


@dataclass
class Var:
    line: int
    name: str


@dataclass
class Bool:
    value: bool
    line: int


@dataclass
class Nil:
    line: int


@dataclass
class ListLit:
    line: int
    items: list


@dataclass
class MapLit:
    line: int
    items: list           # [(key_string, expr)]


@dataclass
class Binop:
    line: int
    op: str
    left: object
    right: object


@dataclass
class Not:
    line: int
    expr: object


@dataclass
class Neg:
    line: int
    expr: object


@dataclass
class Call:
    line: int
    fn: object
    args: list


@dataclass
class Index:
    line: int
    obj: object
    index: object


@dataclass
class Member:
    line: int
    obj: object
    name: str


@dataclass
class FnExpr:
    line: int
    params: list
    ret_hint: Optional[str]
    body: Block


# --------------------------------------------------------------------------
# Parser
# --------------------------------------------------------------------------

class Parser:
    def __init__(self, tokens):
        self.toks = tokens
        self.pos = 0

    # ---- token helpers ---------------------------------------------------

    def peek(self):
        return self.toks[self.pos]

    def next(self):
        tok = self.toks[self.pos]
        self.pos += 1
        return tok

    def check(self, kind):
        return self.peek().kind == kind

    def match(self, kind):
        if self.check(kind):
            return self.next()
        return None

    def expect(self, kind, what=None):
        tok = self.peek()
        if tok.kind != kind:
            shown = "end of input" if tok.kind == "EOF" else tok.kind
            wanted = what or f"'{kind}'"
            raise ParseError(f"Expected {wanted}, got {shown}", tok.line, eof=tok.kind == "EOF")
        return self.next()

    def skip_nl(self):
        while self.check("NL"):
            self.next()

    # ---- program / statements --------------------------------------------

    def parse_program(self):
        stmts = []
        self.skip_nl()
        start_line = self.peek().line
        while not self.check("EOF"):
            stmts.append(self.statement())
            self.end_statement()
            self.skip_nl()
        return Program(stmts, start_line)

    def end_statement(self):
        """A statement must end at a newline, '}' or end of input."""
        tok = self.peek()
        if tok.kind not in ("NL", "}", "EOF"):
            shown = "end of input" if tok.kind == "EOF" else f"'{tok.kind}'"
            raise ParseError(f"Expected end of statement, got {shown}", tok.line)

    def block(self):
        brace = self.expect("{", "an opening '{'")
        stmts = []
        self.skip_nl()
        while not self.check("}"):
            if self.check("EOF"):
                raise ParseError("Expected '}' to close block, got end of input",
                                 self.peek().line, eof=True)
            stmts.append(self.statement())
            self.end_statement()
            self.skip_nl()
        self.expect("}")
        return Block(brace.line, stmts)

    def statement(self):
        tok = self.peek()
        kind = tok.kind
        if kind == "let" or kind == "const":
            return self.let_decl()
        if kind == "fn":
            return self.fn_decl()
        if kind == "if":
            return self.if_stmt()
        if kind == "while":
            return self.while_stmt()
        if kind == "for":
            return self.for_stmt()
        if kind == "return":
            return self.return_stmt()
        if kind == "break":
            self.next()
            return Break(tok.line)
        if kind == "continue":
            self.next()
            return Continue(tok.line)
        if kind == "{":
            return self.block()
        # Otherwise: expression or assignment.
        expr = self.expression()
        if self.match("="):
            if not isinstance(expr, (Var, Index, Member)):
                raise ParseError("Invalid assignment target", tok.line)
            value = self.expression()
            return Assign(tok.line, expr, value)
        return ExprStmt(tok.line, expr)

    def let_decl(self):
        tok = self.next()  # let | const
        name = self.expect("ID", "a variable name").value
        hint = self.hint() if self.match(":") else None
        self.expect("=", "'=' (a 'let' needs an initializer)")
        expr = self.expression()
        return Let(tok.line, name, expr, hint, const=(tok.kind == "const"))

    def hint(self):
        tok = self.expect("ID", "a type name")
        if tok.value not in TYPES:
            raise ParseError(f"Unknown type '{tok.value}' (known: {', '.join(sorted(TYPES))})", tok.line)
        return tok.value

    def fn_decl(self):
        tok = self.next()  # fn
        name = self.expect("ID", "a function name")
        params = self.params()
        ret = self.hint() if self.match(":") else None
        body = self.block()
        return FnDecl(tok.line, name.value, params, ret, body)

    def params(self):
        self.expect("(", "'('")
        params = []
        seen = set()
        while not self.check(")"):
            name = self.expect("ID", "a parameter name").value
            if name in seen:
                raise ParseError(f"Duplicate parameter '{name}'", self.peek().line)
            seen.add(name)
            hint = self.hint() if self.match(":") else None
            params.append((name, hint))
            if not self.match(",") and not self.check(")"):
                raise ParseError("Expected ',' or ')' in parameter list", self.peek().line)
        self.expect(")")
        return params

    def if_stmt(self):
        tok = self.next()  # if
        cond = self.expression()
        then = self.block().stmts
        els = None
        if self.match("else"):
            if self.check("if"):
                els = [self.if_stmt()]
            else:
                els = self.block().stmts
        return If(tok.line, cond, then, els)

    def while_stmt(self):
        tok = self.next()  # while
        cond = self.expression()
        body = self.block().stmts
        return While(tok.line, cond, body)

    def for_stmt(self):
        tok = self.next()  # for
        var = self.expect("ID", "a loop variable").value
        self.expect("in", "'in'")
        iterable = self.expression()
        body = self.block().stmts
        return For(tok.line, var, iterable, body)

    def return_stmt(self):
        tok = self.next()  # return
        expr = None
        if not (self.check("NL") or self.check("}") or self.check("EOF")):
            expr = self.expression()
        return Return(tok.line, expr)

    # ---- expressions (precedence climbing) -------------------------------

    def expression(self):
        return self.or_expr()

    def or_expr(self):
        left = self.and_expr()
        while self.match("or"):
            right = self.and_expr()
            left = Binop(left.line, "or", left, right)
        return left

    def and_expr(self):
        left = self.not_expr()
        while self.match("and"):
            right = self.not_expr()
            left = Binop(left.line, "and", left, right)
        return left

    def not_expr(self):
        tok = self.peek()
        if self.match("not"):
            return Not(tok.line, self.not_expr())
        return self.compare()

    def compare(self):
        left = self.add()
        tok = self.peek()
        if tok.kind in COMPARE_OPS:
            self.next()
            right = self.add()
            # Non-associative on purpose (SPEC.md 3): `a < b < c` is a mistake.
            if self.peek().kind in COMPARE_OPS:
                raise ParseError("Chained comparison; combine with 'and', e.g. a < b and b < c",
                                 self.peek().line)
            return Binop(tok.line, tok.kind, left, right)
        return left

    def add(self):
        left = self.mul()
        while self.peek().kind in ("+", "-"):
            tok = self.next()
            right = self.mul()
            left = Binop(tok.line, tok.kind, left, right)
        return left

    def mul(self):
        left = self.unary()
        while self.peek().kind in ("*", "/", "%"):
            tok = self.next()
            right = self.unary()
            left = Binop(tok.line, tok.kind, left, right)
        return left

    def unary(self):
        tok = self.peek()
        if self.match("-"):
            return Neg(tok.line, self.unary())
        return self.postfix()

    def postfix(self):
        expr = self.primary()
        while True:
            tok = self.peek()
            if tok.kind == "(":
                self.next()
                args = []
                while not self.check(")"):
                    args.append(self.expression())
                    if not self.match(","):
                        break
                self.expect(")")
                expr = Call(tok.line, expr, args)
            elif tok.kind == "[":
                self.next()
                index = self.expression()
                self.expect("]")
                expr = Index(tok.line, expr, index)
            elif tok.kind == ".":
                self.next()
                name = self.expect("ID", "a property name after '.'")
                expr = Member(tok.line, expr, name.value)
            else:
                return expr

    def primary(self):
        tok = self.next()
        kind = tok.kind
        if kind == "NUM":
            return Num(tok.value, tok.line)
        if kind == "STR":
            parts = [(p[0], p[1]) if p[0] == "lit" else ("expr", self.parse_interp(p[1], p[2]))
                     for p in tok.value]
            return Str(tok.line, parts)
        if kind == "ID":
            return Var(tok.line, tok.value)
        if kind == "true":
            return Bool(True, tok.line)
        if kind == "false":
            return Bool(False, tok.line)
        if kind == "nil":
            return Nil(tok.line)
        if kind == "(":
            expr = self.expression()
            self.expect(")")
            return expr
        if kind == "[":
            return self.list_lit(tok)
        if kind == "{":
            return self.map_lit(tok)
        if kind == "fn":
            params = self.params()
            ret = self.hint() if self.match(":") else None
            body = self.block()
            return FnExpr(tok.line, params, ret, body)
        shown = "end of input" if kind == "EOF" else f"'{kind}'"
        raise ParseError(f"Unexpected {shown}", tok.line, eof=kind == "EOF")

    def list_lit(self, tok):
        items = []
        while not self.check("]"):
            items.append(self.expression())
            if not self.match(","):
                break
            self.skip_nl()
        self.expect("]")
        return ListLit(tok.line, items)

    def map_lit(self, tok):
        items = []
        while not self.check("}"):
            key = self.expect("STR", "a string key for the map")
            if len(key.value) != 1 or key.value[0][0] != "lit":
                raise ParseError("Map keys must be plain strings (no interpolation)", key.line)
            self.expect(":", "':' after the key")
            items.append((key.value[0][1], self.expression()))
            if not self.match(","):
                break
            self.skip_nl()
        self.expect("}")
        return MapLit(tok.line, items)

    def parse_interp(self, source, line):
        """Parse one {expr} found inside a string literal."""
        parser = Parser(lex(source))
        expr = parser.expression()
        extra = parser.peek()
        if extra.kind != "EOF":
            raise ParseError("Unexpected token after expression in string interpolation", line)
        return expr


def parse(source_or_tokens):
    """Parse a token list (or raw source) into a Program."""
    tokens = source_or_tokens if isinstance(source_or_tokens, list) and source_or_tokens \
        and isinstance(source_or_tokens[0], Token) else lex(source_or_tokens)
    return Parser(tokens).parse_program()
