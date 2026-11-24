"""Error types shared by every stage of the Burl interpreter."""

class BurlError(Exception):
    """Base class for all Burl errors. `kind` is 'lex', 'parse' or 'runtime'."""

    kind = "error"

    def __init__(self, message, line=None):
        super().__init__(message)
        self.message = message
        self.line = line

    def __str__(self):
        prefix = self.kind.capitalize() + " error"
        if self.line is not None:
            prefix += f" at line {self.line}"
        return f"{prefix}: {self.message}"


class LexError(BurlError):
    kind = "lex"


class ParseError(BurlError):
    kind = "parse"

    def __init__(self, message, line=None, eof=False):
        super().__init__(message, line)
        # True when the input ended unexpectedly; the REPL uses this to
        # decide whether to keep reading lines.
        self.eof = eof


class BurlRuntimeError(BurlError):
    kind = "runtime"
