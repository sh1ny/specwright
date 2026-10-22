"""Reads the operations of a GraphQL document, so a `gh api graphql` call can be classified as a read or a write.

`operations(doc)` returns [(kind, top_fields), ...] for the document's query, mutation and subscription definitions, and
`named_operations(doc)` the same with each operation's name ([(kind, name or None, top_fields), ...]), or None
when the document cannot be read: unbalanced brackets, an unterminated string, or a top-level token that starts no definition.
Comments and string contents never reach the parser; fragment definitions are skipped; an alias resolves to its field.
Stdlib only, one pass, no recursion.
"""
import re

NAME = re.compile(r"[_A-Za-z][_0-9A-Za-z]*")
STRING = re.compile(r'"(?:[^"\\\n]|\\.)*"')
SKIP = re.compile(r"[ \t\r\n,﻿]+")
OPEN, CLOSE = "([{", {")": "(", "]": "[", "}": "{"}
KINDS = ("query", "mutation", "subscription")


def tokens(doc):
    """Names, punctuation and a `"` mark per string, in order; None when a string is unterminated or a character is unknown."""
    out, i, n = [], 0, len(doc)
    while i < n:
        m = SKIP.match(doc, i)
        if m:
            i = m.end()
            continue
        c = doc[i]
        if c == "#":
            j = doc.find("\n", i)
            i = n if j < 0 else j
        elif doc.startswith('"""', i):
            j = doc.find('"""', i + 3)
            while j > 0 and doc[j - 1] == "\\":  # \""" is an escaped quote triple, not the end
                j = doc.find('"""', j + 3)
            if j < 0:
                return None
            out.append("\"")
            i = j + 3
        elif c == '"':
            m = STRING.match(doc, i)
            if not m:
                return None
            out.append("\"")
            i = m.end()
        elif doc.startswith("...", i):
            out.append("...")
            i += 3
        elif NAME.match(doc, i):
            m = NAME.match(doc, i)
            out.append(m.group())
            i = m.end()
        elif c in "()[]{}:@$!=|&" or c == "-" or c == "+" or c == "." or c.isdigit():
            out.append(c)  # numbers and other punctuation only occur as argument values: one token per character is enough
            i += 1
        else:
            return None
    return out


def operations(doc):
    ops = named_operations(doc)
    return None if ops is None else [(kind, fields) for kind, _, fields in ops]


def named_operations(doc):
    toks = tokens(doc)
    if toks is None:
        return None
    ops, stack = [], []
    head = None    # the keyword of the definition whose header is being read ("fragment" or an operation kind)
    fields = None  # the depth-1 field names of the operation whose selection set is open
    name = None    # the operation's name: the name right after its keyword
    prev = prev2 = ""
    for t in toks:
        if t in OPEN:
            if not stack:
                if t == "[" or (t == "(" and head is None):
                    return None
                if t == "{":
                    if head is None:
                        head = "query"  # an anonymous { ... } is a query
                    fields = [] if head != "fragment" else None
                    kind = head
            stack.append(t)
        elif t in CLOSE:
            if not stack or stack.pop() != CLOSE[t]:
                return None
            if not stack and t == "}":
                if fields is not None:
                    ops.append((kind, name, fields))
                head = fields = name = None
        elif not stack:
            # between definitions or in a header: only a keyword, then names and directives up to the opening brace
            if head is None:
                if t not in KINDS and t != "fragment":
                    return None
                head = t
            elif t != "@" and not NAME.fullmatch(t):
                return None
            elif t != "@" and prev == head and head in KINDS and name is None:
                name = t  # `query @d { ... }` has no name
        elif stack == ["{"] and fields is not None and NAME.fullmatch(t):
            if prev == ":":
                fields[-1:] = [t]  # alias: the field is the name after the colon
            elif prev not in ("@", "...") and not (prev == "on" and prev2 == "..."):
                fields.append(t)   # not a directive name, fragment spread or inline-fragment type
        prev2, prev = prev, t
    return None if stack or head is not None else ops
