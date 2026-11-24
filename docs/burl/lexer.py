"""The Burl lexer.

Token kinds:
  NUM, STR, ID, NL, EOF  -- and every keyword / operator is its own kind
  ("let", "fn", "+", "==", ...), so the parser can match on tok.kind directly.

A STR token's value is a list of interpolation parts, each a tuple:
  ("lit", text, line)    literal text
  ("expr", source, line) a Burl expression to parse and evaluate
See SPEC.md section 7.
"""

from .errors import LexError

KEYWORDS = {
    "and", "or", "not", "let", "const", "fn", "if", "else", "while",
    "for", "in", "return", "break", "continue", "true", "false", "nil",
}

SINGLE_OPS = set("+-*/%=<>()[{}],.:")

TWO_CHAR_OPS = {"==", "!=", "<=", ">=" }

ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", '"': '"', "{": "{", "}": "}"}


class Token:
    __slots__ = ("kind", "value", "line")

    def __init__(self, kind, value, line):
        self.kind = kind
        self.value = value
        self.line = line

    def __repr__(self):
        return f"Token({self.kind!r}, {self.value!r}, line={self.line})"


class Lexer:
    def __init__(self, source):
        self.src = source
        self.pos = 0
        self.line = 1
        self.depth = 0  # () [] nesting: newlines are suppressed above depth 0

    def error(self, message, line=None):
        raise LexError(message, self.line if line is None else line)

    def at_end(self):
        return self.pos >= len(self.src)

    def peek(self):
        return self.src[self.pos] if self.pos < len(self.src) else ""

    def peek2(self):
        i = self.pos + 1
        return self.src[i] if i < len(self.src) else ""

    def advance(self):
        ch = self.src[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line += 1
        return ch

    def tokens(self):
        out = []
        while not self.at_end():
            ch = self.peek()
            if ch == "\n":
                self.advance()
                if self.depth == 0 and out and out[-1].kind not in ("NL",):
                    out.append(Token("NL", None, self.line))
            elif ch in " \t\r":
                self.advance()
            elif ch == "/" and self.peek2() == "/":
                while not self.at_end() and self.peek() != "\n":
                    self.advance()
            elif ch == '"':
                out.append(self.string())
            elif ch.isdigit():
                out.append(self.number())
            elif ch.isalpha() or ch == "_":
                out.append(self.ident())
            else:
                out.append(self.operator())
        out.append(Token("EOF", None, self.line))
        return out

    def operator(self):
        line = self.line
        two = self.peek() + self.peek2()
        if two in TWO_CHAR_OPS:
            self.advance(); self.advance()
            return Token(two, None, line)
        ch = self.peek()
        if ch in SINGLE_OPS:
            self.advance()
            if ch == "(" or ch == "[":
                self.depth += 1
            elif ch == ")" or ch == "]":
                self.depth = max(0, self.depth - 1)
            return Token(ch, None, line)
        self.error(f"Unexpected character {ch!r}")

    def number(self):
        line = self.line
        start = self.pos
        while self.peek().isdigit():
            self.advance()
        is_float = False
        if self.peek() == "." and self.peek2().isdigit():
            is_float = True
            self.advance()  # '.'
            while self.peek().isdigit():
                self.advance()
        text = self.src[start:self.pos]
        if text.endswith("."):  # e.g. "1." - let the parser reject via rule below
            self.error(f"Malformed number {text!r} (expected digits after '.')", line)
        return Token("NUM", float(text) if is_float else int(text), line)

    def ident(self):
        line = self.line
        start = self.pos
        while self.peek().isalnum() or self.peek() == "_":
            self.advance()
        word = self.src[start:self.pos]
        kind = word if word in KEYWORDS else "ID"
        return Token(kind, word, line)

    def string(self):
        line = self.line
        self.advance()  # opening quote
        parts = []      # list of ("lit", text, line) / ("expr", src, line)
        buf = []

        def flush():
            if buf:
                parts.append(("lit", "".join(buf), line))
                buf.clear()

        while True:
            if self.at_end():
                self.error("Unterminated string (missing closing '\"')", line)
            ch = self.peek()
            if ch == '"':
                self.advance()
                flush()
                return Token("STR", parts, line)
            if ch == "\n":
                self.error("Unterminated string (newline before closing '\"')", line)
            if ch == "\\":
                self.advance()
                esc = self.peek()
                if esc not in ESCAPES:
                    self.error(f"Unknown escape '\\{esc}' (valid: {sorted(ESCAPES)})")
                self.advance()
                buf.append(ESCAPES[esc])
            elif ch == "{":
                self.advance()
                flush()
                parts.append(self.interpolation(line))
            elif ch == "}":
                self.error("Unmatched '}' in string (escape it as '\\}')")
            else:
                self.advance()
                buf.append(ch)

    def interpolation(self, start_line):
        """Scan a {...} expression inside a string, returning its source.

        Braces are balanced; quoted strings inside are skipped so their
        braces and backslashes do not interfere.
        """
        depth = 1
        start = self.pos
        while True:
            if self.at_end():
                raise LexError("Unterminated '{' in string interpolation", start_line)
            ch = self.peek()
            if ch == '"':
                self.skip_quoted_in_expr()
            elif ch == "{":
                depth += 1
                self.advance()
            elif ch == "}":
                depth -= 1
                self.advance()
                if depth == 0:
                    return ("expr", self.src[start:self.pos - 1].strip(), start_line)
            else:
                self.advance()

    def skip_quoted_in_expr(self):
        self.advance()  # opening quote
        while True:
            if self.at_end():
                self.error("Unterminated '\"' inside string interpolation")
            ch = self.peek()
            if ch == "\\":
                self.advance(); self.advance()
            elif ch == '"':
                self.advance()
                return
            else:
                self.advance()


def lex(source):
    """Lex source text into a token list, ending with an EOF token."""
    return Lexer(source).tokens()
