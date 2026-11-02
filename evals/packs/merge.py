"""The install prompt's Step 5 pack merge, as test code (README Step 5, design D5).

`update.sh` never writes config.yaml: the prompt's agent does. The evals need the same result without an agent, so this
module writes it for the restricted YAML shape the evals use (a top-level `context: |` block scalar, `rules:` and
`operations:` mappings whose lists hold one entry per `- ` line). Group 8's end-to-end test reuses it.

merge_config(existing, template, packs, previous) -> (text, unmanaged)
  existing   the project's config.yaml text, or None (then the template is the start, as in Step 5)
  template   the download's templates/openspec/config.yaml text
  packs      the enabled packs in install order: [(name, manifest dict)]
  previous   the pack names of `packs_previous`
  unmanaged  the `[pack:` lines kept because their pack is neither enabled nor previous (Step 5 reports them)

Step 5: remove each line starting `[pack:<name>] ` from context, every rules.<artifact> list and every
operations.<op>.guidance list for a <name> enabled now or in previous; keep every other `[pack:` line; append each enabled
pack's lines prefixed `[pack:<name>] ` in pack order then manifest order; list entries are double-quoted YAML scalars.
"""
import json
import re

PREFIX = "[pack:"


def quoted(text):
    """A double-quoted YAML scalar: `"` and backslash escaped (json.dumps writes exactly that for printable text)."""
    return json.dumps(text, ensure_ascii=False)


def unquoted(entry):
    """The text of one list entry (`"..."`, `'...'` or plain)."""
    entry = entry.strip()
    if entry.startswith('"'):
        try:
            return json.loads(entry)
        except ValueError:
            return entry[1:-1]
    if entry.startswith("'") and entry.endswith("'") and len(entry) >= 2:
        return entry[1:-1].replace("''", "'")
    return entry


def parse(text):
    """Split config.yaml into [(key, header, body lines)] by top-level key; lines before the first key go under key None."""
    sections, cur = [], [None, None, []]
    for ln in text.splitlines():
        m = re.match(r"^([A-Za-z_][\w-]*):(.*)$", ln)
        if m:
            sections.append(cur)
            cur = [m.group(1), ln, []]
        else:
            cur[2].append(ln)
    sections.append(cur)
    return [s for s in sections if s[0] is not None or s[2]]


def parse_lists(body):
    """A mapping body (`  <name>:` then `    - entry` lines) as ordered {name: [entry texts]}."""
    lists, name = {}, None
    for ln in body:
        m = re.match(r"^  ([\w-]+):\s*$", ln)
        if m:
            name = m.group(1)
            lists.setdefault(name, [])
        elif name is not None and re.match(r"^    - ", ln):
            lists[name].append(unquoted(ln[6:]))
    return lists


def strip_managed(lines, managed, unmanaged):
    """The lines without those of a managed pack; every other `[pack:` line is kept and recorded."""
    kept = []
    for ln in lines:
        m = re.match(r"^\[pack:([^\]]*)\] ", ln)
        if m and m.group(1) in managed:
            continue
        if m or ln.startswith(PREFIX):
            unmanaged.append(ln)
        kept.append(ln)
    return kept


def merge_config(existing, template, packs, previous=()):
    unmanaged = []
    managed = {n for n, _ in packs} | set(previous)
    sections = parse(existing if existing is not None else template)
    by_key = {s[0]: s for s in sections}
    names = [n for n, _ in packs]
    assert len(set(names)) == len(names), "a pack is enabled once"

    def own(kind, key):
        """The enabled packs' lines for one target, in pack order then manifest order."""
        out = []
        for n, m in packs:
            if kind == "context":
                src = m.get("context", [])
            elif kind == "rules":
                src = m.get("rules", {}).get(key, [])
            else:
                src = m.get("operations", {}).get(key, {}).get("guidance", [])
            out.extend(f"{PREFIX}{n}] {t}" for t in src)
        return out

    # context: a block scalar, one two-space-indented line per entry
    if "context" not in by_key:
        sections.append(["context", "context: |", []])
        by_key["context"] = sections[-1]
    ctx = by_key["context"]
    cl = [ln[2:] if ln.startswith("  ") else ln for ln in ctx[2] if ln.strip()]
    cl = strip_managed(cl, managed, unmanaged) + own("context", None)
    ctx[2] = ["  " + ln for ln in cl]

    for kind, top in (("rules", "rules"), ("operations", "operations")):
        if top not in by_key:
            sections.append([top, f"{top}:", []])
            by_key[top] = sections[-1]
        sec = by_key[top]
        lists = parse_lists(sec[2])
        if kind == "operations":
            # operations.<op>.guidance: one more level; the evals' shape is `  apply:` / `    guidance:` / `      - entry`
            ops, op = {}, None
            for ln in sec[2]:
                m = re.match(r"^  ([\w-]+):\s*$", ln)
                if m:
                    op = m.group(1)
                    ops.setdefault(op, [])
                elif op is not None and re.match(r"^      - ", ln):
                    ops[op].append(unquoted(ln[8:]))
            targets = ops
        else:
            targets = lists
        wanted = {k for n, m in packs for k in (m.get("rules", {}) if kind == "rules" else m.get("operations", {}))}
        for key in sorted(wanted - set(targets)):
            targets[key] = []
        body = []
        for key, entries in targets.items():
            entries = strip_managed(entries, managed, unmanaged) + own(kind, key)
            if not entries:
                continue
            if kind == "rules":
                body.append(f"  {key}:")
                body.extend(f"    - {quoted(e)}" for e in entries)
            else:
                body.extend([f"  {key}:", "    guidance:"])
                body.extend(f"      - {quoted(e)}" for e in entries)
        sec[2] = body
        if not body:
            sections[:] = [x for x in sections if x is not sec]

    out = []
    for key, header, body in sections:
        if header is not None:
            out.append(header)
        out.extend(body)
    return "\n".join(out) + "\n", unmanaged
