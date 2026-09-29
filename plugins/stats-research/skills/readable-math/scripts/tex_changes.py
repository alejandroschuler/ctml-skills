#!/usr/bin/env python3
"""Report the LaTeX text that changed since the last readable-math check.

Usage:

    python3 tex_changes.py report PATH... [--full] [--main FILE] [--state-dir DIR]
    python3 tex_changes.py mark   PATH... [--main FILE] [--state-dir DIR]

Each PATH is a .tex file or a paper folder. The script finds the document that
it belongs to: the root file, which has the \\documentclass, and every .tex
file that the root reads through \\input, \\include, \\subfile or \\import,
in reading order. A file that no root reads is its own document.

report compares each file with the copy saved at the last check and prints
the files to read, the regions to audit as file:first-last line ranges in the
current text, and the text that was deleted. A change inside a comment or in
the spacing within a line does not count. When no check is saved yet, the
comparison is with the last git commit, and outside git every line is new.
With --full, every line is a region, for a whole-document review. report also
saves the text that it compared, and the report itself, in the state folder.

report also lists each changed statement and labeled equation with the places
that cite it, so that a reviewer of proofs sees which other arguments depend
on it. A full check leaves this list out, and so does a report on a document
that is new in full, since every argument in it needs review anyway.

mark records the text of the last report as checked, so that the next report
starts from it. Run it as soon as the checkers have reported and before any
fix, so that the fixes show up in the next report. A report that finds no
change marks the document by itself.

The state folder is readable-math/ in the repository's git directory, so
nothing in it is ever committed or pushed. Outside git it is
~/.cache/readable-math/. The exit code is 0 on success and 2 on an error.
"""

from __future__ import annotations

import argparse
import bisect
import difflib
import hashlib
import json
import os
import posixpath
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

INCLUDE = re.compile(
    r"""
      \\(?P<inc>input|include|subfile|InputIfFileExists)\s*\{(?P<incarg>[^{}]+)\}
    | \\input(?=\s)\s*(?P<bare>[^\s{}\\%]+)
    | \\(?P<imp>import|subimport|inputfrom|subinputfrom|includefrom|subincludefrom)\*?
          \s*\{(?P<impdir>[^{}]*)\}\s*\{(?P<impfile>[^{}]+)\}
    """,
    re.X,
)
DOCUMENTCLASS = re.compile(r"^\s*\\documentclass\s*(?:\[(?P<opt>[^\]]*)\])?\s*\{(?P<cls>[^}]*)\}", re.M)
MAGIC_ROOT = re.compile(r"^\s*%\s*!\s*TEX\s+root\s*=\s*(?P<path>\S.*?)\s*$", re.M | re.I)
TEX_IF = re.compile(r"\\(if[a-zA-Z@]*|fi)(?![a-zA-Z@])")
NEWTHEOREM = re.compile(
    r"\\newtheorem\*?\s*\{(?P<env>[^{}]+)\}\s*(?:\[[^\]]*\])?\s*\{(?P<title>(?:[^{}]|\{[^{}]*\})*)\}"
)
DECLARETHEOREM = re.compile(r"\\declaretheorem\s*(?:\[(?P<opts>[^\]]*)\])?\s*\{(?P<envs>[^{}]+)\}")
THEOREM_TITLE = re.compile(r"(?<![A-Za-z])(?:name|title|heading)\s*=\s*(?P<title>[^,]*)")  # not refname=
NEWENDTHM = re.compile(r"\\newEndThm\s*(?:\[[^\]]*\])?\s*\{(?P<alias>[^{}]+)\}\s*\{(?P<env>[^{}]+)\}")
ENV_OR_LABEL = re.compile(r"\\(?P<kind>begin|end)\s*\{(?P<env>[^{}]+)\}|\\label\s*\{(?P<label>[^{}]*)\}")
CITATION = re.compile(r"\\(?:ref|eqref|autoref|cref|Cref|nameref|labelcref|vref|Vref)\*?\s*\{(?P<labels>[^{}]*)\}")
MERGE_GAP = 2  # regions this many unchanged lines apart or closer are merged
MAX_DELETED = 150  # deleted lines shown in one report
MAX_STATEMENTS = 60  # changed statements shown in one report
ANCESTORS = 3  # folders above a file searched for its root outside git
STATEMENT_WORDS = ("theorem", "lemma", "proposition", "corollary", "claim", "conjecture", "fact",
                   "observation", "property", "definition", "assumption", "condition", "hypothesis")
DISPLAY_ENVS = ("equation", "align", "gather", "multline", "flalign", "alignat", "eqnarray")


class ToolError(Exception):
    pass


# --------------------------------------------------------------------------
# Cleaning. Comments, comment environments, \iffalse blocks and the text after
# \endinput are blanked with spaces, so that line numbers stay the same.


def blank(text: str, start: int, end: int) -> str:
    return text[:start] + re.sub(r"[^\n]", " ", text[start:end]) + text[end:]


def unescaped(text: str, i: int) -> bool:
    """True when text[i] is not escaped by an odd run of backslashes."""
    n = 0
    j = i - 1
    while j >= 0 and text[j] == "\\":
        n += 1
        j -= 1
    return n % 2 == 0


def strip_comments(text: str) -> str:
    out = []
    for line in text.split("\n"):
        i = line.find("%")
        while i != -1 and not unescaped(line, i):
            i = line.find("%", i + 1)
        out.append(line if i == -1 else line[:i] + " " * (len(line) - i))
    return "\n".join(out)


def blank_iffalse(text: str) -> str:
    pos = 0
    while True:
        m = re.compile(r"\\iffalse(?![a-zA-Z@])").search(text, pos)
        if not m:
            return text
        depth = 1
        end = len(text)
        for t in TEX_IF.finditer(text, m.end()):
            depth += -1 if t.group(1) == "fi" else 1
            if depth == 0:
                end = t.end()
                break
        text = blank(text, m.start(), end)
        pos = end


def clean(raw: str) -> str:
    text = strip_comments(raw)
    for m in list(re.finditer(r"\\begin\s*\{comment\}.*?\\end\s*\{comment\}", text, re.S)):
        text = blank(text, m.start(), m.end())
    text = blank_iffalse(text)
    m = re.search(r"\\endinput(?![a-zA-Z@])", text)
    if m:
        text = blank(text, m.end(), len(text))
    return text


def normalized_lines(raw: str) -> list[str]:
    """One entry per line of raw: the line without comments, with its spacing
    collapsed. The diff runs on these, so comment and spacing edits vanish."""
    return [" ".join(line.split()) for line in clean(raw).split("\n")]


def content(raw: str) -> tuple[list[str], list[int]]:
    """The normalized lines that hold text, and their 0-based line indices.
    Blank and comment-only lines drop out before the diff."""
    lines = normalized_lines(raw)
    idx = [i for i, s in enumerate(lines) if s]
    return [lines[i] for i in idx], idx


def count_lines(text: str | None) -> int:
    return len((text or "").splitlines())


# --------------------------------------------------------------------------
# Sources of text. A path is always relative to the folder of the root file,
# in POSIX form, such as "theory/nu-clt.tex" or "../shared/macros.tex".


def norm(rel: str) -> str:
    return posixpath.normpath(rel.replace(os.sep, "/"))


class Source:
    def read(self, rel: str) -> str | None:
        raise NotImplementedError


class DiskSource(Source):
    def __init__(self, base: Path):
        self.base = base
        self.cache: dict[str, str | None] = {}

    def read(self, rel: str) -> str | None:
        if rel not in self.cache:
            p = self.base / rel
            self.cache[rel] = p.read_text(encoding="utf-8", errors="replace") if p.is_file() else None
        return self.cache[rel]


class SnapshotSource(Source):
    def __init__(self, files: dict[str, str]):
        self.files = files

    def read(self, rel: str) -> str | None:
        return self.files.get(rel)


class GitHeadSource(Source):
    """The files as they are in the last commit."""

    def __init__(self, top: Path, base: Path):
        self.top = top
        self.prefix = norm(os.path.relpath(base, top))
        out = git(top, "ls-tree", "-r", "--name-only", "-z", "HEAD")
        self.names = set(out.split("\0")) if out else set()
        self.cache: dict[str, str | None] = {}

    def read(self, rel: str) -> str | None:
        name = norm(posixpath.join(self.prefix, rel))
        if name.startswith("../") or name not in self.names:
            return None
        if name not in self.cache:
            out = subprocess.run(["git", "-C", str(self.top), "show", f"HEAD:{name}"],
                                 capture_output=True)
            self.cache[name] = out.stdout.decode("utf-8", errors="replace") if out.returncode == 0 else None
        return self.cache[name]


class EmptySource(Source):
    def read(self, rel: str) -> str | None:
        return None


def git(cwd: Path, *args: str) -> str | None:
    try:
        out = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


# --------------------------------------------------------------------------
# The document: the root file and the files it reads, in reading order.


def resolve(source: Source, current: str, kind: str, target: str, impdir: str) -> str | None:
    target = target.strip()
    if kind in ("subimport", "subinputfrom", "subincludefrom"):
        base = posixpath.join(posixpath.dirname(current), impdir.strip())
    elif kind in ("import", "inputfrom", "includefrom"):
        base = impdir.strip()
    else:
        base = ""
    p = norm(posixpath.join(base, target)) if base else norm(target)
    if kind == "include":
        tries = [p + ".tex"]
    elif p.endswith(".tex"):
        tries = [p]
    else:
        tries = [p + ".tex", p]
    for t in tries:
        if t.endswith(".tex") and source.read(t) is not None:
            return t
    return None


def reading_order(source: Source, root: str) -> list[str]:
    order: list[str] = []
    seen: set[str] = set()

    def visit(rel: str, depth: int) -> None:
        if rel in seen or depth > 50:
            return
        text = source.read(rel)
        if text is None:
            return
        seen.add(rel)
        order.append(rel)
        for m in INCLUDE.finditer(clean(text)):
            if m.group("inc"):
                kind, target, impdir = m.group("inc"), m.group("incarg"), ""
            elif m.group("bare"):
                kind, target, impdir = "input", m.group("bare"), ""
            else:
                kind, target, impdir = m.group("imp"), m.group("impfile"), m.group("impdir")
            if "#" in target or "\\" in target:
                continue  # a macro argument, not a file name
            found = resolve(source, rel, kind, target, impdir)
            if found:
                visit(found, depth + 1)

    visit(root, 0)
    return order


def documentclass(text: str) -> re.Match | None:
    return DOCUMENTCLASS.search(strip_comments(text))


def is_root(path: Path) -> bool:
    try:
        return documentclass(path.read_text(encoding="utf-8", errors="replace")) is not None
    except OSError:
        return False


def roots_in(folder: Path, all_roots: bool = False) -> list[Path]:
    """The root files in folder: main.tex alone when it is a root, else every
    .tex file with a \\documentclass. With all_roots, every root, main.tex
    first."""
    roots = [p for p in sorted(folder.glob("*.tex")) if is_root(p)]
    main = folder / "main.tex"
    if main in roots:
        return [main] + [p for p in roots if p != main] if all_roots else [main]
    return roots


def find_root(path: Path) -> tuple[Path, str | None]:
    """The root file of the document that path belongs to, and a note when
    the answer is a guess."""
    text = path.read_text(encoding="utf-8", errors="replace")
    m = documentclass(text)
    if m:
        # A subfile names its main file: \documentclass[main.tex]{subfiles}.
        if m.group("cls").strip() == "subfiles" and m.group("opt"):
            main = (path.parent / m.group("opt").strip()).resolve()
            if main.suffix != ".tex":
                main = main.with_name(main.name + ".tex")
            if main.is_file():
                return main, None
        return path, None
    magic = MAGIC_ROOT.search("\n".join(text.split("\n")[:30]))
    if magic:
        root = (path.parent / magic.group("path")).resolve()
        if root.is_file():
            return root, None
    top = git(path.parent, "rev-parse", "--show-toplevel")
    stop = Path(top).resolve() if top else None
    folder = path.parent.resolve()
    for _ in range(50):
        for cand in roots_in(folder, all_roots=True):
            base = cand.parent
            order = reading_order(DiskSource(base), cand.name)
            if norm(os.path.relpath(path.resolve(), base)) in order:
                return cand, None
        if folder == stop or folder.parent == folder:
            break
        if stop is None and len(path.parent.resolve().parts) - len(folder.parts) >= ANCESTORS:
            break
        folder = folder.parent
    return path, "no root file reads this file, so it is checked as a document of its own"


# --------------------------------------------------------------------------
# State: the checked and pending copies of a document, and its last report.


def state_folder(root: Path, override: str | None) -> Path:
    if override:
        base = Path(override).expanduser()
        key_path = str(root)
    else:
        gitdir = git(root.parent, "rev-parse", "--absolute-git-dir")
        top = git(root.parent, "rev-parse", "--show-toplevel")
        if gitdir and top:
            base = Path(gitdir) / "readable-math"
            key_path = norm(os.path.relpath(root, top))
        else:
            cache = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
            base = Path(cache) / "readable-math"
            key_path = str(root)
    key = re.sub(r"[^A-Za-z0-9._-]", "-", root.name) + "-" + hashlib.sha1(key_path.encode()).hexdigest()[:10]
    folder = base / key
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError:
        folder = Path(tempfile.gettempdir()) / "readable-math" / key
        folder.mkdir(parents=True, exist_ok=True)
    return folder


def load(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def save(path: Path, data: dict | str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(data if isinstance(data, str) else json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def snapshot(root: Path, source: DiskSource, order: list[str]) -> dict:
    return {
        "version": 1,
        "root": root.name,
        "saved": datetime.now().isoformat(timespec="seconds"),
        "files": {rel: source.read(rel) for rel in order},
    }


# --------------------------------------------------------------------------
# The comparison.


@dataclass
class Region:
    file: str
    start: int  # first line, counting from 1
    end: int  # last line
    kind: str
    deleted: list[str] = field(default_factory=list)


@dataclass
class Deletion:
    file: str
    after: int  # the deleted text sat after this line of the current text
    lines: list[str]


def compare(file: str, old: str | None, new: str) -> tuple[list[Region], list[Deletion]]:
    """The regions of new that changed since old, and the deletions that sit
    between regions. Line numbers count from 1 in the raw text of new."""
    new_lines, new_idx = content(new)
    if old is None:
        if not new_idx:
            return [], []
        return [Region(file, new_idx[0] + 1, new_idx[-1] + 1, "new file")], []
    old_raw = old.split("\n")
    old_lines, old_idx = content(old)

    # Spans in content coordinates: [j1, j2) of new, and the old lines they lost.
    spans: list[list] = []
    sm = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        gone = [old_raw[old_idx[i]].rstrip("\r") for i in range(i1, i2)]
        if spans and j1 - spans[-1][1] <= MERGE_GAP:
            spans[-1][1] = max(spans[-1][1], j2)
            spans[-1][2] += gone
            spans[-1][3] = spans[-1][3] or bool(gone)
        else:
            spans.append([j1, j2, gone, bool(gone)])

    regions: list[Region] = []
    deletions: list[Deletion] = []
    for j1, j2, gone, lost in spans:
        if j2 > j1:
            kind = "changed" if lost else "added"
            regions.append(Region(file, new_idx[j1] + 1, new_idx[j2 - 1] + 1, kind, gone))
        else:
            after = new_idx[j1 - 1] + 1 if j1 > 0 else 0
            deletions.append(Deletion(file, after, gone))
    return regions, deletions


# --------------------------------------------------------------------------
# Statements and labeled equations, and the places that cite them. This reads
# the cleaned text, so a comment never counts.


@dataclass
class Item:
    file: str
    begin: int  # first line, counting from 1
    end: int  # last line
    labels: dict[str, int] = field(default_factory=dict)  # label: offset of its \label in the text


def line_starts(text: str) -> list[int]:
    """The offset at which each line of text starts."""
    return [0] + [m.end() for m in re.finditer(r"\n", text)]


def names_statement(*texts: str) -> bool:
    """True when one of the texts holds a statement word, in any case."""
    return any(w in t.lower() for t in texts for w in STATEMENT_WORDS)


def tracked_envs(texts: list[str]) -> set[str]:
    """The environment names to track: the statement words, their E forms for
    proof at the end, and the display environments, plus the environments that
    the document declares as statements and the aliases that it makes for them.
    Declarations are read from every file, because a paper often keeps them in
    a file that the root inputs. A starred name counts as its plain name."""
    preamble = "\n".join(clean(t) for t in texts)
    names = set(STATEMENT_WORDS) | {w + "E" for w in STATEMENT_WORDS} | set(DISPLAY_ENVS)
    for m in NEWTHEOREM.finditer(preamble):
        if names_statement(m.group("env"), m.group("title")):
            names.add(m.group("env").strip())
    for m in DECLARETHEOREM.finditer(preamble):
        given = THEOREM_TITLE.search(m.group("opts") or "")
        title = given.group("title") if given else ""
        for env in m.group("envs").split(","):
            if names_statement(env, title):
                names.add(env.strip())
    for m in NEWENDTHM.finditer(preamble):
        if m.group("env").strip() in names:
            names.add(m.group("alias").strip())
    return names


def env_items(file: str, text: str, tracked: set[str]) -> list[Item]:
    """The tracked environments of text, with the labels that belong to each. A
    label belongs to the innermost tracked environment around it, so an
    equation inside a theorem is an item of its own."""
    starts = line_starts(text)
    items: list[Item] = []
    stack: list[tuple[str, int, dict[str, int]]] = []  # name, offset of \begin, labels so far
    for m in ENV_OR_LABEL.finditer(text):
        if m.group("label") is not None:
            label = m.group("label").strip()
            if label and stack:
                stack[-1][2].setdefault(label, m.start())
            continue
        name = m.group("env").strip().rstrip("*")
        if name not in tracked:
            continue
        if m.group("kind") == "begin":
            stack.append((name, m.start(), {}))
            continue
        for k in range(len(stack) - 1, -1, -1):
            if stack[k][0] == name:
                _, begin, labels = stack[k]
                del stack[k:]
                items.append(Item(file, bisect.bisect_right(starts, begin),
                                  bisect.bisect_right(starts, m.start()), labels))
                break
    return items


def citations(text: str) -> list[tuple[str, int]]:
    """The label and the line of each citation in text. A citation of a list
    of labels gives one entry for each label."""
    starts = line_starts(text)
    found: list[tuple[str, int]] = []
    for m in CITATION.finditer(text):
        line = bisect.bisect_right(starts, m.start())
        found += [(label.strip(), line) for label in m.group("labels").split(",")]
    return found


def touched(item: Item, regions: list[Region], deletions: list[Deletion]) -> bool:
    """True when a region overlaps the lines of item, or a deletion sits inside
    them or right next to them."""
    return (any(r.file == item.file and r.start <= item.end and r.end >= item.begin for r in regions)
            or any(d.file == item.file and item.begin - 1 <= d.after <= item.end for d in deletions))


def statement_lines(disk: DiskSource, root: str, order: list[str], regions: list[Region],
                    deletions: list[Deletion]) -> list[str]:
    """One line for each label of each changed statement or labeled equation,
    with the places outside it that cite the label, in the reading order of the
    labels. An item inside a changed item counts as changed too, whether or not
    the outer item has a label."""
    texts = {rel: clean(disk.read(rel) or "") for rel in order}
    tracked = tracked_envs([disk.read(rel) or "" for rel in order])
    cites: dict[str, list[tuple[str, int]]] = {}
    for rel in order:
        for label, line in citations(texts[rel]):
            cites.setdefault(label, []).append((rel, line))
    out: list[str] = []
    for rel in order:
        items = env_items(rel, texts[rel], tracked)
        changed = [it for it in items if touched(it, regions, deletions)]
        entries = [(pos, label, it) for it in items if it.labels
                   if any(o.begin <= it.begin and it.end <= o.end for o in changed)
                   for label, pos in it.labels.items()]
        for _, label, it in sorted(entries, key=lambda e: e[0]):
            where = [f"{f}:{n}" for f, n in cites.get(label, []) if not (f == rel and it.begin <= n <= it.end)]
            where = list(dict.fromkeys(where))
            span = f"{it.begin}-{it.end}" if it.end > it.begin else f"{it.begin}"
            found = "cited at " + ", ".join(where) if where else "not cited elsewhere"
            out.append(f"  {label} ({rel}:{span}): {found}")
    return out


# --------------------------------------------------------------------------
# The report.


@dataclass
class Document:
    root: Path
    note: str | None = None


def describe_baseline(checked: dict | None, head: GitHeadSource | None, full: bool) -> str:
    if full:
        return "nothing, because this is a full check. Every line is in scope."
    if checked:
        return f"the last check, saved {checked['saved'].replace('T', ' ')}."
    if head:
        sha = git(head.top, "rev-parse", "--short", "HEAD")
        return (f"the last commit ({sha}), because no check is saved for this document yet. "
                "Text committed before now counts as checked.")
    return "nothing, because no check is saved and there is no git history. Every line is new."


def report(doc: Document, state_override: str | None, full: bool) -> str:
    root = doc.root
    base = root.parent
    folder = state_folder(root, state_override)
    disk = DiskSource(base)
    order = reading_order(disk, root.name)

    checked = None if full else load(folder / "checked.json")
    head = None
    if full:
        old_source: Source = EmptySource()
    elif checked:
        old_source = SnapshotSource(checked["files"])
    else:
        top = git(base, "rev-parse", "--show-toplevel")
        if top and git(base, "rev-parse", "--verify", "--quiet", "HEAD"):
            head = GitHeadSource(Path(top), base)
            old_source = head
        else:
            old_source = EmptySource()
    old_order = reading_order(old_source, root.name)

    regions: list[Region] = []
    deletions: list[Deletion] = []
    for rel in order:
        old = old_source.read(rel) if rel in old_order else None
        r, d = compare(rel, old, disk.read(rel) or "")
        if full:
            for x in r:
                x.kind = "whole file"
        regions += r
        deletions += d
    removed = [rel for rel in old_order if rel not in order]

    total = sum(count_lines(disk.read(rel)) for rel in order)
    in_scope = sum(r.end - r.start + 1 for r in regions)
    pending = snapshot(root, disk, order)

    out: list[str] = []
    out.append(f"Change report for {root.name}")
    out.append(f"Folder: {base}")
    if doc.note:
        out.append(f"Note: {doc.note}.")
    out.append(f"Compared with: {describe_baseline(checked, head, full)}")
    out.append("")
    out.append("Read these files in full, in this order, before judging anything:")
    for i, rel in enumerate(order, 1):
        out.append(f"  {i}. {(base / rel).resolve()} ({count_lines(disk.read(rel))} lines)")
    out.append("")

    if not regions and not deletions and not removed:
        out.append("No changes since then. Nothing to audit. The document is marked as checked.")
        save(folder / "checked.json", pending)
        (folder / "pending.json").unlink(missing_ok=True)
        text = "\n".join(out) + "\n"
        save(folder / "report.txt", text)
        return text

    out.append("Regions to audit (line ranges in the current text; paths relative to the folder):")
    if regions:
        for r in regions:
            span = f"{r.start}-{r.end}" if r.end > r.start else f"{r.start}"
            out.append(f"  {r.file}:{span} ({r.kind})")
    else:
        out.append("  none, only deletions")
    out.append("")

    if not full and old_order:
        statements = statement_lines(disk, root.name, order, regions, deletions)
        if statements:
            out.append("Changed statements and equations, and the places that cite them (for the correctness review):")
            out += statements[:MAX_STATEMENTS]
            if len(statements) > MAX_STATEMENTS:
                out.append(f"  ... and {len(statements) - MAX_STATEMENTS} more. Most of the document changed;"
                           " consider a full review.")
            out.append("")

    shown = 0
    blocks: list[tuple[str, list[str]]] = []
    for r in regions:
        if r.deleted:
            span = f"{r.start}-{r.end}" if r.end > r.start else f"{r.start}"
            blocks.append((f"{r.file}:{span} replaced these lines:", r.deleted))
    for d in deletions:
        blocks.append((f"{d.file}, after line {d.after}, lost these lines:", d.lines))
    for rel in removed:
        lines = [s for s, n in zip((old_source.read(rel) or "").split("\n"),
                                   normalized_lines(old_source.read(rel) or "")) if n]
        blocks.append((f"{rel} is no longer read by the document. It held:", lines))
    if blocks:
        out.append("Deleted text (apply the ripple rules to it):")
        hidden = 0
        for head_line, lines in blocks:
            out.append(f"  {head_line}")
            for s in lines:
                if shown < MAX_DELETED:
                    out.append(f"    | {s}")
                    shown += 1
                else:
                    hidden += 1
        if hidden:
            out.append(f"  ... and {hidden} more deleted lines, not shown. This change is large;"
                       " consider a full check.")
        out.append("")

    n_deleted = sum(len(lines) for _, lines in blocks)
    pct = round(100 * in_scope / total) if total else 0
    lost = "1 line was deleted" if n_deleted == 1 else f"{n_deleted} lines were deleted"
    out.append(f"Size: {in_scope} of {total} lines are in regions ({pct}%). {lost}.")
    out.append(f"Saved report: {folder / 'report.txt'}")
    text = "\n".join(out) + "\n"
    save(folder / "pending.json", pending)
    save(folder / "report.txt", text)
    return text


def mark(doc: Document, state_override: str | None) -> str:
    folder = state_folder(doc.root, state_override)
    pending = load(folder / "pending.json")
    if not pending:
        if (folder / "checked.json").is_file():
            return (f"{doc.root.name}: nothing to mark. The last report found no changes, "
                    "or it is already marked.\n")
        raise ToolError(f"{doc.root.name}: there is no report to mark. Run report first.")
    save(folder / "checked.json", pending)
    (folder / "pending.json").unlink(missing_ok=True)
    disk = DiskSource(doc.root.parent)
    order = reading_order(disk, doc.root.name)
    later = [rel for rel in order
             if normalized_lines(disk.read(rel) or "") != normalized_lines(pending["files"].get(rel) or "")]
    msg = f"{doc.root.name}: marked as checked, with the text of the report made at {pending['saved'].replace('T', ' ')}.\n"
    if later:
        msg += (f"  {len(later)} file(s) changed after that report ({', '.join(later)}). "
                "Those changes stay unchecked and will show up in the next report.\n")
    return msg


# --------------------------------------------------------------------------


def documents(paths: list[str], main: str | None) -> list[Document]:
    docs: dict[Path, Document] = {}
    for arg in paths:
        p = Path(arg).expanduser()
        if not p.exists():
            raise ToolError(f"no such file or folder: {p}")
        if main:
            root = Path(main).expanduser()
            if not root.is_absolute():
                root = (p if p.is_dir() else p.parent) / root
            if not root.is_file():
                raise ToolError(f"no such root file: {root}")
            found = [(root.resolve(), None)]
        elif p.is_dir():
            roots = roots_in(p)
            if not roots:
                raise ToolError(f"no .tex file with a \\documentclass in {p}. Pass a file or --main.")
            found = [(r.resolve(), None) for r in roots]
        else:
            if p.suffix != ".tex":
                raise ToolError(f"not a .tex file: {p}")
            r, note = find_root(p)
            found = [(r.resolve(), note)]
        for r, note in found:
            docs.setdefault(r, Document(r, note))
    return list(docs.values())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("command", choices=["report", "mark"])
    ap.add_argument("paths", nargs="+", help=".tex files or paper folders")
    ap.add_argument("--full", action="store_true", help="report every line, for a whole-document check")
    ap.add_argument("--main", help="the root file, when it cannot be found on its own")
    ap.add_argument("--state-dir", help="keep the saved copies here instead")
    args = ap.parse_args(argv)
    try:
        docs = documents(args.paths, args.main)
        parts = []
        for doc in docs:
            if args.command == "report":
                parts.append(report(doc, args.state_dir, args.full))
            else:
                parts.append(mark(doc, args.state_dir))
    except ToolError as e:
        print(f"tex_changes: {e}", file=sys.stderr)
        return 2
    print("\n".join(parts), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
