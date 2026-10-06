#!/usr/bin/env python3
"""Check that a LaTeX paper keeps each result in theory/ and each TikZ figure in tikz/,
keeps its text in short numbered files in sections/, puts each sentence on its own line,
and lets cleveref name its cross-references.

Read-only: it never changes a file. Usage:

    python3 check_tex_hygiene.py [PAPER_DIR] [--main FILE] [--theory-dir DIR]
                                 [--tikz-dir DIR] [--sections-dir DIR]
                                 [--result-env NAME] [--max-lines N] [--json]

PAPER_DIR defaults to the current directory. The root file is --main, else
main.tex, else the one top-level .tex file that has a \\documentclass.

The check follows the \\input graph from the root file in document order, so it
sees what LaTeX reads. It skips comments, comment environments, verbatim text
and \\iffalse blocks. Its rules:

  inline-result   a theorem, proposition, lemma or corollary is written in a
                  file outside theory/
  stray-proof     a proof is written in a file outside theory/
  inline-tikz     a tikzpicture in the document body is outside tikz/
  one-per-file    a theory/ file holds more than one result, or a tikz/ file
                  more than one figure
  slug            a file name does not match its label: thm:<slug> belongs in
                  theory/<slug>.tex, and fig:<slug> in tikz/<slug>.tex
  deferred-shape  a deferred result lacks its proofE, its textAtEnd block with
                  \\label{pf:<slug>}, or its text link
  after-print     a deferred result comes after the \\printProofs that prints
                  it, so LaTeX drops its proof without an error
  no-print        there are deferred results but no \\printProofs
  unused-print    a \\printProofs has no deferred result before it
  header          a tikz/ file does not start with a header comment
  verbatim        verbatim material inside a deferred result or its proofE
  hash            a macro parameter # inside proofE, which proof-at-the-end
                  doubles when it writes the proof out
  twice           a theory/, tikz/ or sections/ file is read more than once,
                  which defines its labels twice
  orphan          a file in theory/, tikz/ or sections/ that nothing reads
  missing         an \\input target that does not exist
  old-pointer     preamble code for the run-in proof pointer that puts the
                  pointer into a heading or loses it at a list
  generated       <jobname>-pratend*.tex is tracked by git, or not ignored
  long-file       a file of text is past the line target (--max-lines, 200 by
                  default, counted at one sentence per line) and a heading
                  splits it, or it is more than a quarter past the target. The
                  root file counts from \\begin{document}. Files in theory/,
                  tikz/ and artefacts/ are exempt.
  sentence-lines  a line of prose holds more than one sentence
  typed-ref       a name typed in front of \\ref, as in Lemma~\\ref{lem:x}, where
                  \\cref, \\Cref or \\eqref would print the name. When the .aux
                  file of a build has cleveref's data, the labels of list items
                  are skipped, and a typed name that does not match the kind of
                  its label gets a warning of its own.
  section-name    a file or folder in sections/ does not start with a number
                  such as 10- or A1-, or shares its number with another one
                  in the same folder. When no file there has a number, the
                  paper keeps an older layout, and one warning says so.
  section-order   a sections/ file is input from a file other than the root,
                  or the root inputs the sections/ files in an order other
                  than the order of their names. Skipped when no file in
                  sections/ has a number.

The long-file rule is for the manuscript only. When the root file has the mode
line % writing-math: note, the document is a note, and that rule is skipped.

An error loses text, breaks the build or breaks a layout rule. A warning is
drift worth fixing. The exit code is 1 when there is an error, 0 when there is
none, and 2 when the paper cannot be read.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Environment names that hold a result. The paper's own \newtheorem and
# \declaretheorem lines add to these when their name or title matches.
RESULT_NAMES = {
    "theorem", "thm", "proposition", "prop", "lemma", "lem", "corollary",
    "cor", "claim", "conjecture", "conj", "fact", "observation", "property",
}
RESULT_TITLE_WORDS = {
    "theorem", "proposition", "lemma", "corollary", "claim", "conjecture",
    "fact", "observation", "property",
}
# Deferred versions from deferproofs.sty and from the createShortEnv option of
# proof-at-the-end. The paper's own \newEndThm lines add to these.
DEFERRED_DEFAULTS = {
    "theoremE", "propositionE", "lemmaE", "corollaryE", "thmE", "propertyE",
    "factE",
}
PROOF_PLAIN = {"proof"}
PROOF_DEFERRED_DEFAULTS = {"proofE", "proofEnd"}
VERBATIM_ENVS = {
    "verbatim", "verbatim*", "Verbatim", "BVerbatim", "LVerbatim",
    "lstlisting", "minted",
}
FIGURE_ENVS = {"figure", "figure*"}
# TeX conditionals that end with \fi. Used only to find the end of an
# \iffalse block, so an unlisted conditional can at worst end a block early.
TEX_IFS = {
    "if", "ifx", "ifnum", "ifdim", "ifodd", "ifvmode", "ifhmode", "ifmmode",
    "ifinner", "ifvoid", "ifhbox", "ifvbox", "ifeof", "iftrue", "iffalse",
    "ifcase", "ifdefined", "ifcsname", "iffontchar", "ifincsname",
}

TOKEN = re.compile(
    r"""
      \\(?P<be>begin|end)\s*\{(?P<env>[^{}\s]+)\}
    | \\label\s*\{(?P<label>[^{}]+)\}
    | \\(?P<inc>input|include|subfile|InputIfFileExists)\s*\{(?P<incarg>[^{}]+)\}
    | \\input(?=\s)\s*(?P<bare>[^\s{}\\%]+)
    | \\(?P<imp>import|subimport|inputfrom|subinputfrom|includefrom|subincludefrom)\*?
          \s*\{(?P<impdir>[^{}]*)\}\s*\{(?P<impfile>[^{}]+)\}
    | \\(?P<print>printProofs)(?![A-Za-z@])
    | (?P<hash>\#)
    """,
    re.X,
)

# Environments that hold no prose. The sentence rule skips them.
NONPROSE_ENVS = {
    "equation", "align", "gather", "multline", "flalign", "alignat", "eqnarray",
    "displaymath", "math", "tikzpicture", "tabular", "tabularx", "longtable",
    "array", "algorithm", "algorithmic", "thebibliography",
}
# Words that end with a period inside a sentence. A word with a dot inside it,
# such as e.g. or i.i.d., and a single letter, such as an initial, count too.
ABBREVIATIONS = {
    "al", "cf", "vs", "etc", "viz", "resp", "approx", "ca", "fig", "figs", "eq",
    "eqs", "sec", "secs", "ch", "chap", "app", "thm", "prop", "lem", "cor",
    "def", "assump", "no", "nos", "vol", "pp", "ed", "eds", "dr", "mr", "mrs",
    "ms", "prof", "st", "jr", "sr", "inc", "ltd", "co",
}
# Commands that can follow the end of a sentence on its line without starting
# a new sentence. A textual citation such as \citet does start one.
NOT_A_START = {
    "label", "begin", "end", "item", "ref", "eqref", "pageref", "citep",
    "citealp", "parencite", "autocite", "footcite", "citeyearpar", "footnote",
    "footnotemark", "nonumber", "notag", "qedhere", "hfill", "vspace", "hspace",
    "smallskip", "medskip", "bigskip", "par", "newline", "linebreak",
    "pagebreak", "newpage", "clearpage", "index", "unskip", "ignorespaces",
}
# Folders of generated files, which no one splits or edits by hand.
GENERATED_DIRS = {"artefacts"}
# The name of a file or folder in sections/: two digits, or A and a digit for
# the appendix, then a hyphen and the slug.
SECTION_NAME = re.compile(r"^(\d{2}|A\d)-(.+)$")
SENTENCE_END = re.compile(r"[.?!]+['\")}]*[ \t]+(?=[A-Z]|\\([A-Za-z]+))")
HEADING = re.compile(r"\\(section|subsection|subsubsection|paragraph)\*?\s*[\[{]")
NOTE_MODE = re.compile(r"^\s*%\s*writing-math:\s*note\b", re.M | re.I)
# Words typed in front of \ref that \cref or \eqref would print, each with the
# kind of label that it names. Appendix, condition, step and item are left
# out: \cref calls an appendix section "Section", and the others often mark
# list items, where \cref prints "Item".
TYPED_NAMES = {
    "theorem": "theorem", "thm": "theorem",
    "proposition": "proposition", "prop": "proposition",
    "lemma": "lemma", "lemmata": "lemma", "lem": "lemma",
    "corollary": "corollary", "corollaries": "corollary", "cor": "corollary",
    "claim": "claim", "conjecture": "conjecture", "conj": "conjecture",
    "definition": "definition", "def": "definition", "defn": "definition",
    "assumption": "assumption", "assump": "assumption",
    "remark": "remark", "rem": "remark", "example": "example", "ex": "example",
    "section": "section", "sec": "section", "subsection": "subsection",
    "chapter": "chapter", "figure": "figure", "fig": "figure",
    "table": "table", "tab": "table", "algorithm": "algorithm", "alg": "algorithm",
    "equation": "equation", "eq": "equation", "eqn": "equation",
}
# Kinds that a typed name must match exactly. A section and a subsection are
# both called sections, so they are not compared.
MATCHED_KINDS = {
    "theorem", "proposition", "lemma", "corollary", "claim", "conjecture",
    "definition", "assumption", "remark", "example", "figure", "table",
    "algorithm", "equation",
}
TYPED_REF = re.compile(
    r"(?<![A-Za-z@\\])(?P<name>" + "|".join(sorted(TYPED_NAMES, key=len, reverse=True))
    + r")(?:s|es)?\.?(?:~|\\ |\s+)(?P<paren>\()?\\ref\*?\s*\{(?P<label>[^{}]+)\}",
    re.I,
)
CREF_TYPE = re.compile(r"\\newlabel\{(?P<label>.+?)@cref\}\{\{\[(?P<kind>[^\]]*)\]")
CLEVEREF = re.compile(r"\\(?:usepackage|RequirePackage)\s*(?:\[[^\]]*\])?\s*\{[^}]*\bcleveref\b")


@dataclass
class Finding:
    rule: str
    severity: str  # "error" or "warning"
    file: str
    line: int | None
    message: str


@dataclass
class Result:
    file: Path
    line: int
    env: str
    deferred: bool
    seq: int
    category: str = "defaultcategory"
    has_text_link: bool = False
    label: str | None = None
    nested: bool = False


@dataclass
class Figure:
    file: Path
    line: int
    label: str | None = None


@dataclass
class TikzPicture:
    file: Path
    line: int
    figure: Figure | None


@dataclass
class TextAtEnd:
    file: Path
    category: str = "defaultcategory"


@dataclass
class FileInfo:
    path: Path
    reads: int = 0
    results: list[Result] = field(default_factory=list)
    figures: list[Figure] = field(default_factory=list)
    deferred_proofs: int = 0
    pf_labels: list[str] = field(default_factory=list)
    textatend_categories: list[str] = field(default_factory=list)
    body: bool = False  # read inside the document body, not from the preamble


# --------------------------------------------------------------------------
# Cleaning the source: blank out what LaTeX does not read, keeping every
# character position so line numbers still match the file.


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


def in_comment(text: str, i: int) -> bool:
    start = text.rfind("\n", 0, i) + 1
    for k in range(start, i):
        if text[k] == "%" and unescaped(text, k):
            return True
    return False


def blank_verbatim(text: str) -> str:
    """Blank the bodies of verbatim environments and of \\verb, before comments
    are stripped, because a % inside them is not a comment. The \\begin and
    \\end lines of each environment stay, so the verbatim rule can see them."""
    for name in VERBATIM_ENVS:
        pat = re.compile(
            r"\\begin\s*\{" + re.escape(name) + r"\}(.*?)\\end\s*\{" + re.escape(name) + r"\}",
            re.S,
        )
        pos = 0
        while True:
            m = pat.search(text, pos)
            if not m:
                break
            if in_comment(text, m.start()):
                pos = m.start() + 1
                continue
            text = blank(text, m.start(1), m.end(1))
            pos = m.end()
    for m in list(re.finditer(r"\\verb\*?([^A-Za-z\s*])(.*?)\1", text)):
        if not in_comment(text, m.start()):
            text = blank(text, m.start(2), m.end(2))
    return text


def strip_comments(text: str) -> str:
    out = []
    for line in text.split("\n"):
        cut = None
        i = line.find("%")
        while i != -1:
            if unescaped(line, i):
                cut = i
                break
            i = line.find("%", i + 1)
        out.append(line if cut is None else line[:cut] + " " * (len(line) - cut))
    return "\n".join(out)


def blank_iffalse(text: str) -> str:
    token = re.compile(r"\\(if[a-zA-Z@]*|fi|else)(?![a-zA-Z@])")
    pos = 0
    while True:
        m = re.search(r"\\iffalse(?![a-zA-Z@])", text[pos:])
        if not m:
            return text
        start = pos + m.start()
        depth = 1
        end = None
        for t in token.finditer(text, start + len("\\iffalse")):
            word = t.group(1)
            if word == "fi":
                depth -= 1
            elif word == "else" and depth == 1:
                end = t.start()
                break
            elif word in TEX_IFS or word.startswith("if@"):
                depth += 1
            if depth == 0:
                end = t.start()
                break
        if end is None:
            end = len(text)
        text = blank(text, start, end)
        pos = end


def clean(raw: str) -> str:
    text = blank_verbatim(raw)
    text = strip_comments(text)
    for m in list(re.finditer(r"\\begin\s*\{comment\}.*?\\end\s*\{comment\}", text, re.S)):
        text = blank(text, m.start(), m.end())
    text = blank_iffalse(text)
    m = re.search(r"\\endinput(?![a-zA-Z@])", text)
    if m:
        text = blank(text, m.end(), len(text))
    return text


def read_group(text: str, pos: int, opener: str) -> tuple[str | None, int]:
    """Read a balanced [..] or {..} group that starts at pos, after spaces.
    Returns the inside and the position after the group, or (None, pos)."""
    closer = "]" if opener == "[" else "}"
    i = pos
    while i < len(text) and text[i] in " \t\n":
        i += 1
    if i >= len(text) or text[i] != opener:
        return None, pos
    depth = 0
    braces = 0
    j = i
    while j < len(text):
        c = text[j]
        if c == "\\":
            j += 2
            continue
        if opener == "[":
            if c == "{":
                braces += 1
            elif c == "}":
                braces -= 1
            elif braces == 0 and c == "[":
                depth += 1
            elif braces == 0 and c == "]":
                depth -= 1
                if depth == 0:
                    return text[i + 1 : j], j + 1
        else:
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return text[i + 1 : j], j + 1
        j += 1
    return None, pos


def line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def category_of(opts: str) -> str:
    c = re.search(r"category\s*=\s*\{?([^,}\]\s]+)", opts)
    return c.group(1) if c else "defaultcategory"


def slug_of(label: str | None) -> str | None:
    if not label:
        return None
    return label.split(":", 1)[1] if ":" in label else label


# --------------------------------------------------------------------------
# Reading the paper


def find_root(paper: Path, main: str | None) -> Path:
    if main:
        p = (paper / main) if not Path(main).is_absolute() else Path(main)
        if not p.is_file():
            raise SystemExit(f"check_tex_hygiene: no such file: {p}")
        return p
    cand = paper / "main.tex"
    if cand.is_file() and "\\documentclass" in cand.read_text(errors="replace"):
        return cand
    roots = [
        p for p in sorted(paper.glob("*.tex"))
        if re.search(r"^\s*\\documentclass", strip_comments(p.read_text(errors="replace")), re.M)
    ]
    if len(roots) == 1:
        return roots[0]
    names = ", ".join(p.name for p in roots) or "none"
    raise SystemExit(
        f"check_tex_hygiene: cannot tell which file is the root in {paper} "
        f"(files with \\documentclass: {names}). Pass --main."
    )


def declared_envs(preamble: str) -> tuple[set[str], set[str], set[str]]:
    """Result, deferred-result and deferred-proof environments declared in the
    preamble with \\newtheorem, \\declaretheorem, \\newEndThm and \\newEndProof."""
    results: set[str] = set()
    deferred: set[str] = set()
    proofs: set[str] = set()

    def is_result(name: str, title: str) -> bool:
        words = set(re.findall(r"[a-z]+", title.lower()))
        return name.lower() in RESULT_NAMES or bool(words & RESULT_TITLE_WORDS)

    for m in re.finditer(r"\\newtheorem\*?", preamble):
        name, p = read_group(preamble, m.end(), "{")
        if name is None:
            continue
        _, p = read_group(preamble, p, "[")
        title, _ = read_group(preamble, p, "{")
        if is_result(name.strip(), title or ""):
            results.add(name.strip())
    for m in re.finditer(r"\\declaretheorem\b", preamble):
        opts, p = read_group(preamble, m.end(), "[")
        name, p = read_group(preamble, p, "{")
        if name is None:
            continue
        more, _ = read_group(preamble, p, "[")
        allopts = (opts or "") + "," + (more or "")
        t = re.search(r"(?:name|title)\s*=\s*\{?([^,}\]]+)", allopts)
        if is_result(name.strip(), t.group(1) if t else name):
            results.add(name.strip())
    for m in re.finditer(r"\\newEndThm\b", preamble):
        _, p = read_group(preamble, m.end(), "[")
        new, p = read_group(preamble, p, "{")
        base, _ = read_group(preamble, p, "{")
        if new and base:
            deferred.add(new.strip())
            results.add(base.strip())
    for m in re.finditer(r"\\newEndProof\b", preamble):
        _, p = read_group(preamble, m.end(), "[")
        new, _ = read_group(preamble, p, "{")
        if new:
            proofs.add(new.strip())
    return results, deferred, proofs


class Walker:
    def __init__(self, paper: Path, theory: Path, tikz: Path, sections: Path,
                 extra_results: set[str]):
        self.paper = paper
        self.theory = theory
        self.tikz = tikz
        self.sections = sections
        self.results_envs = set(RESULT_NAMES) | extra_results
        self.deferred_envs = set(DEFERRED_DEFAULTS)
        self.proof_deferred = set(PROOF_DEFERRED_DEFAULTS)
        self.findings: list[Finding] = []
        self.files: dict[Path, FileInfo] = {}
        self.results: list[Result] = []
        self.tikzpictures: list[TikzPicture] = []
        self.proofs: list[tuple[Path, int, str, str]] = []  # file, line, env, context
        self.pf_outside: list[tuple[Path, int, str]] = []  # file, line, label
        self.prints: list[tuple[int, str, Path, int]] = []  # seq, category, file, line
        self.section_reads: list[tuple[Path, Path, int]] = []  # file, reader, line
        self.stack: list[tuple[str, object]] = []
        self.seq = 0
        self.in_body = False
        self.preamble_parts: list[str] = []
        self.active: list[Path] = []
        self.kpsewhich = shutil.which("kpsewhich")

    # ---- helpers

    def rel(self, p: Path) -> str:
        try:
            return str(p.resolve().relative_to(self.paper.resolve()))
        except ValueError:
            return str(p)

    def under(self, p: Path, d: Path) -> bool:
        try:
            p.resolve().relative_to(d.resolve())
            return True
        except ValueError:
            return False

    def add(self, rule: str, severity: str, file: Path | None, line: int | None, message: str) -> None:
        f = Finding(rule, severity, self.rel(file) if file else "", line, message)
        if f not in self.findings:
            self.findings.append(f)

    def info(self, p: Path) -> FileInfo:
        key = p.resolve()
        if key not in self.files:
            self.files[key] = FileInfo(key)
        return self.files[key]

    def inside_deferred(self) -> bool:
        for env, obj in self.stack:
            if env in self.proof_deferred or (isinstance(obj, Result) and obj.deferred):
                return True
        return False

    def resolve(self, target: str, kind: str, current: Path, impdir: str = "") -> Path | None:
        target = target.strip()
        if kind in ("subimport", "subinputfrom", "subincludefrom"):
            base = current.parent / impdir
        elif kind in ("import", "inputfrom", "includefrom"):
            base = Path(impdir) if Path(impdir).is_absolute() else self.paper / impdir
        else:
            base = self.paper
        p = base / target
        tries = [p] if p.suffix == ".tex" else [p.with_name(p.name + ".tex"), p]
        if kind == "include":
            tries = [p.with_name(p.name + ".tex")]
        for t in tries:
            if t.is_file():
                return t
        return None

    def known_to_tex(self, target: str) -> bool:
        if not self.kpsewhich:
            return False
        name = target if target.endswith(".tex") or "." in Path(target).name else target + ".tex"
        try:
            out = subprocess.run([self.kpsewhich, name], capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            return False
        return out.returncode == 0 and bool(out.stdout.strip())

    # ---- the walk

    def walk(self, path: Path) -> None:
        key = path.resolve()
        fi = self.info(path)
        fi.reads += 1
        if fi.reads == 1:
            fi.body = self.in_body
        if fi.reads > 1 or key in self.active:
            return
        self.active.append(key)
        text = clean(path.read_text(encoding="utf-8", errors="replace"))

        # The root's preamble declares the environments, so read it first.
        if not self.in_body:
            doc = re.search(r"\\begin\s*\{document\}", text)
            pre = text[: doc.start()] if doc else text
            self.preamble_parts.append(pre)
            r, d, p = declared_envs(pre)
            self.results_envs |= r
            self.deferred_envs |= d
            self.proof_deferred |= p

        for m in TOKEN.finditer(text):
            line = line_of(text, m.start())
            if m.group("be"):
                if m.group("be") == "begin":
                    self.begin(m.group("env"), path, line, text, m.end())
                else:
                    self.end(m.group("env"))
            elif m.group("label"):
                self.label(m.group("label").strip(), path, line)
            elif m.group("print"):
                cat, _ = read_group(text, m.end(), "[")
                self.seq += 1
                self.prints.append((self.seq, (cat or "defaultcategory").strip(), path, line))
            elif m.group("hash"):
                if unescaped(text, m.start()) and self.inside_deferred():
                    self.add("hash", "error", path, line,
                             "a macro parameter # inside a deferred proof; proof-at-the-end "
                             "doubles it when it writes the proof out. Define the macro in "
                             "the preamble instead.")
            else:
                if m.group("inc"):
                    kind, target, impdir = m.group("inc"), m.group("incarg"), ""
                elif m.group("bare"):
                    kind, target, impdir = "input", m.group("bare"), ""
                else:
                    kind, target, impdir = m.group("imp"), m.group("impfile"), m.group("impdir")
                if "#" in target or "\\" in target:
                    continue  # a macro argument, not a file
                found = self.resolve(target, kind, path, impdir)
                if found is None:
                    if not self.known_to_tex(target):
                        self.add("missing", "warning", path, line,
                                 f"\\{kind}{{{target}}} names a file that does not exist.")
                    continue
                if self.under(found, self.sections):
                    self.section_reads.append((found, path, line))
                self.walk(found)
        self.active.pop()

    def begin(self, env: str, path: Path, line: int, text: str, pos: int) -> None:
        base = env.rstrip("*")
        obj: object = None
        if env == "document":
            self.in_body = True
        if env == "theoremEnd" or base in self.deferred_envs:
            if env == "theoremEnd":
                opts, _ = read_group(text, pos, "[")
            else:
                _, p = read_group(text, pos, "[")
                opts, _ = read_group(text, p, "[")
            obj = self.new_result(env, path, line, deferred=True, opts=opts or "")
        elif base in self.results_envs:
            obj = self.new_result(env, path, line, deferred=False)
        elif env == "restatable":
            _, p = read_group(text, pos, "[")
            inner, _ = read_group(text, p, "{")
            if inner and inner.strip().rstrip("*") in self.results_envs:
                obj = self.new_result(env, path, line, deferred=False)
        elif env in FIGURE_ENVS:
            obj = Figure(path, line)
            self.info(path).figures.append(obj)
        elif env == "textAtEnd":
            opts, _ = read_group(text, pos, "[")
            obj = TextAtEnd(path, category_of(opts or ""))
            self.info(path).textatend_categories.append(obj.category)
        elif env == "tikzpicture" and self.in_body:
            fig = next((o for _, o in reversed(self.stack) if isinstance(o, Figure)), None)
            self.tikzpictures.append(TikzPicture(path, line, fig))
        elif env in PROOF_PLAIN or env in self.proof_deferred:
            if env in self.proof_deferred:
                self.info(path).deferred_proofs += 1
            ref = re.search(r"\\(?:auto|c|C|)ref\s*\{([^}]+)\}", text[max(0, pos - 400) : pos + 200])
            self.proofs.append((path, line, env, ref.group(1) if ref else ""))
        elif env in VERBATIM_ENVS and self.inside_deferred():
            self.add("verbatim", "error", path, line,
                     f"{env} inside a deferred result or proof. proof-at-the-end cannot "
                     "carry verbatim text to the appendix; use the plain environments "
                     "for this result.")
        self.stack.append((env, obj))

    def new_result(self, env: str, path: Path, line: int, deferred: bool, opts: str = "") -> Result:
        self.seq += 1
        r = Result(path, line, env, deferred, self.seq)
        if deferred:
            r.category = category_of(opts)
            r.has_text_link = "text link" in opts
        r.nested = any(isinstance(o, Result) for _, o in self.stack)
        self.results.append(r)
        self.info(path).results.append(r)
        return r

    def end(self, env: str) -> None:
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == env:
                del self.stack[i:]
                return

    def label(self, label: str, path: Path, line: int) -> None:
        """A label belongs to the innermost open environment, so the label of an
        equation inside a statement is not taken for the statement's own."""
        if label.startswith("pf:") and not self.under(path, self.theory):
            self.pf_outside.append((path, line, label))
        if not self.stack:
            return
        _, obj = self.stack[-1]
        if isinstance(obj, (Result, Figure)) and obj.label is None:
            obj.label = label
        elif isinstance(obj, TextAtEnd):
            self.info(obj.file).pf_labels.append(label)


# --------------------------------------------------------------------------
# The rules


def check(paper: Path, root: Path, theory: Path, tikz: Path, sections: Path,
          extra: set[str], max_lines: int = 200) -> tuple[Walker, dict]:
    w = Walker(paper, theory, tikz, sections, extra)
    w.walk(root)
    tdir, fdir = w.rel(theory), w.rel(tikz)

    for r in w.results:
        if not w.under(r.file, theory):
            where = f"{tdir}/{slug_of(r.label)}.tex" if r.label else f"{tdir}/<slug>.tex"
            what = f"{r.env} {r.label}" if r.label else f"an unlabelled {r.env}"
            w.add("inline-result", "error", r.file, r.line,
                  f"{what} is written inline. Move it, with its proof, to {where} "
                  "and \\input that file here.")

    for path, line, env, ref in w.proofs:
        if not w.under(path, theory):
            hint = f" It looks like the proof of {ref}; move it into {tdir}/{slug_of(ref)}.tex." if ref else \
                   f" Move it into the {tdir}/ file of its result."
            w.add("stray-proof", "error", path, line, f"{env} is outside {tdir}/." + hint)
    for path, line, label in w.pf_outside:
        w.add("stray-proof", "warning", path, line,
              f"\\label{{{label}}} outside {tdir}/ marks a hand-written proof section. "
              f"Move the proof into {tdir}/{slug_of(label)}.tex with its statement, and "
              "let the textAtEnd block there carry the label.")

    for t in w.tikzpictures:
        if not w.under(t.file, tikz):
            lab = t.figure.label if t.figure else None
            where = f"{fdir}/{slug_of(lab)}.tex" if lab else f"{fdir}/<slug>.tex"
            what = f"the tikzpicture of {lab}" if lab else "a tikzpicture"
            w.add("inline-tikz", "error", t.file, t.line,
                  f"{what} is inline. Move the whole figure environment to {where} "
                  "and \\input that file here.")

    for fi in w.files.values():
        path = fi.path
        if fi.reads > 1 and any(w.under(path, d) for d in (theory, tikz, sections)):
            w.add("twice", "error", path, None,
                  f"read {fi.reads} times, which defines its labels {fi.reads} times. "
                  "\\input it once.")
        if w.under(path, theory):
            check_theory_file(w, fi)
        elif w.under(path, tikz):
            check_tikz_file(w, fi)

    read = {p for p, fi in w.files.items()}
    for d in (theory, tikz, sections):
        if d.is_dir():
            for p in sorted(d.rglob("*.tex")):
                if p.resolve() not in read:
                    w.add("orphan", "warning", p, None,
                          "nothing reads this file. \\input it where it belongs, or delete it "
                          "if the author agrees.")

    for r in w.results:
        if not r.deferred:
            continue
        later = [s for s, c, _, _ in w.prints if c == r.category and s > r.seq]
        earlier = [(f, ln) for s, c, f, ln in w.prints if c == r.category and s < r.seq]
        if later:
            continue
        if earlier:
            f, ln = earlier[-1]
            w.add("after-print", "error", r.file, r.line,
                  f"{r.label or r.env} is deferred but comes after the \\printProofs at "
                  f"{w.rel(f)}:{ln}, so its proof is dropped. State it before that line, "
                  "or use the plain environments.")
        else:
            cat = "" if r.category == "defaultcategory" else f"[{r.category}]"
            w.add("no-print", "error", r.file, r.line,
                  f"{r.label or r.env} is deferred but there is no \\printProofs{cat} after "
                  "it. Add one to the appendix.")
    for s, c, f, ln in w.prints:
        if not any(r.deferred and r.category == c and r.seq < s for r in w.results):
            w.add("unused-print", "warning", f, ln,
                  f"\\printProofs{'' if c == 'defaultcategory' else '[' + c + ']'} has no "
                  "deferred result before it. It prints nothing with deferproofs.sty, and "
                  "stops the build without it.")

    check_pointer(w, root)
    check_generated(w, paper, root)
    check_sections(w, root)
    check_text(w, root, max_lines)
    check_refs(w, root)

    summary = {
        "results": len(w.results),
        "results_in_theory": sum(1 for r in w.results if w.under(r.file, theory)),
        "deferred": sum(1 for r in w.results if r.deferred),
        "tikzpictures": len(w.tikzpictures),
        "tikzpictures_in_tikz": sum(1 for t in w.tikzpictures if w.under(t.file, tikz)),
    }
    return w, summary


def check_theory_file(w: Walker, fi: FileInfo) -> None:
    path = fi.path
    stem = path.stem
    tops = [r for r in fi.results if not r.nested]
    if not fi.results:
        w.add("one-per-file", "warning", path, None, "holds no result.")
        return
    if len(fi.results) > 1:
        names = ", ".join(r.label or r.env for r in fi.results)
        w.add("one-per-file", "error", path, fi.results[1].line,
              f"holds {len(fi.results)} results ({names}). Give each its own file.")
    r = tops[0] if tops else fi.results[0]
    if r.label is None:
        w.add("slug", "warning", path, r.line,
              f"the {r.env} has no \\label. Give it one whose slug is the file name, "
              f"such as thm:{stem}.")
    elif slug_of(r.label) != stem:
        w.add("slug", "warning", path, r.line,
              f"the label {r.label} does not match the file name; rename one so that "
              f"the file is {slug_of(r.label)}.tex.")
    if r.deferred:
        if fi.deferred_proofs == 0:
            w.add("deferred-shape", "error", path, r.line,
                  f"{r.env} has no proofE, so the body gets no pointer and the appendix "
                  "gets the statement without a proof. Add the proofE, or use the plain "
                  "environment.")
        if f"pf:{stem}" not in fi.pf_labels:
            w.add("deferred-shape", "warning", path, r.line,
                  f"no textAtEnd block with \\label{{pf:{stem}}}, so the proof gets no "
                  "appendix subsection of its own.")
        for c in fi.textatend_categories:
            if c != r.category:
                w.add("deferred-shape", "error", path, r.line,
                      f"the textAtEnd block is in category {c} and the result in "
                      f"{r.category}, so the proof heading and the proof print in "
                      "different places. Give both the same category.")
        if not r.has_text_link:
            w.add("deferred-shape", "warning", path, r.line,
                  f"no text link option, so the pointer is the package default, a page "
                  f"number. Add [text link={{The proof is in \\autoref{{pf:{stem}}}.}}].")
    elif fi.deferred_proofs:
        w.add("deferred-shape", "error", path, r.line,
              f"proofE follows a plain {r.env}. Use the E environment for the statement, "
              "or a plain proof.")


def check_tikz_file(w: Walker, fi: FileInfo) -> None:
    path = fi.path
    stem = path.stem
    raw = path.read_text(encoding="utf-8", errors="replace")
    first = next((ln for ln in raw.splitlines() if ln.strip()), "")
    if not first.lstrip().startswith("%"):
        w.add("header", "warning", path, 1,
              "no header comment. Say what the figure shows, which numbers are free "
              "parameters, and what to recheck after an edit.")
    if not fi.figures:
        w.add("one-per-file", "warning", path, None,
              "holds no figure environment. Keep the whole figure, with its caption and "
              "label, in this file.")
        return
    if len(fi.figures) > 1:
        w.add("one-per-file", "error", path, fi.figures[1].line,
              f"holds {len(fi.figures)} figures. Give each its own file.")
    f = fi.figures[0]
    if f.label is None:
        w.add("slug", "warning", path, f.line, f"the figure has no \\label. Label it fig:{stem}.")
    elif slug_of(f.label) != stem:
        w.add("slug", "warning", path, f.line,
              f"the label {f.label} does not match the file name; rename one so that "
              f"the file is {slug_of(f.label)}.tex.")


def fill(text: str, start: int, end: int, ch: str) -> str:
    return text[:start] + re.sub(r"[^\n]", ch, text[start:end]) + text[end:]


def mask_nonprose(text: str) -> str:
    """Blank displays and environments that hold no prose, and turn inline
    math into M's, which read as a word that starts a sentence. Every position
    is kept, so the line numbers still match the file."""
    for name in NONPROSE_ENVS:
        pat = re.compile(r"\\begin\s*\{" + re.escape(name) + r"\*?\}.*?\\end\s*\{"
                         + re.escape(name) + r"\*?\}", re.S)
        for m in list(pat.finditer(text)):
            text = blank(text, m.start(), m.end())
    for pat in (r"(?<!\\)\\\[.*?\\\]", r"(?<!\\)\$\$.*?(?<!\\)\$\$"):
        for m in list(re.finditer(pat, text, re.S)):
            text = blank(text, m.start(), m.end())
    for m in list(re.finditer(r"(?<!\\)\\\(.*?\\\)", text, re.S)):
        text = fill(text, m.start(), m.end(), "M")
    dollars = [i for i, c in enumerate(text) if c == "$" and unescaped(text, i)]
    for a, b in zip(dollars[0::2], dollars[1::2]):
        text = fill(text, a, b + 1, "M")
    return text


def sentence_breaks(text: str) -> list[int]:
    """The line of each place where a sentence ends and the next one starts on
    the same line. text has been through mask_nonprose."""
    found = []
    for m in SENTENCE_END.finditer(text):
        cmd = m.group(1)
        if cmd in NOT_A_START:
            continue
        if text[m.start()] == ".":
            start = max(text.rfind(c, 0, m.start()) for c in " \t\n") + 1
            token = text[start : m.start()].replace("\\@", "")
            word = re.search(r"[A-Za-z0-9.]*$", token).group()
            if "." in word or word.lower() in ABBREVIATIONS or (len(word) == 1 and word.isalpha()):
                continue
        found.append(line_of(text, m.start()))
    return found


def check_text(w: Walker, root: Path, max_lines: int) -> None:
    """The long-file and sentence-lines rules, for each file that the body
    reads. A note gets only the sentence-lines rule."""
    note = bool(NOTE_MODE.search(root.read_text(encoding="utf-8", errors="replace")))
    root = root.resolve()
    for fi in w.files.values():
        path = fi.path
        if not (fi.body or path == root) or path.suffix == ".bbl":
            continue
        if any(part in GENERATED_DIRS for part in Path(w.rel(path)).parts[:-1]):
            continue
        text = clean(path.read_text(encoding="utf-8", errors="replace"))
        first, last = 1, line_of(text, len(text.rstrip()))
        if path == root:
            doc = re.search(r"\\begin\s*\{document\}", text)
            if not doc:
                continue
            text = blank(text, 0, doc.start())
            first = line_of(text, doc.start())
            end = re.search(r"\\end\s*\{document\}", text)
            if end:
                last = line_of(text, end.start())
        breaks = sentence_breaks(mask_nonprose(text))

        lines = sorted(set(breaks))
        if lines:
            shown = ", ".join(map(str, lines[:8])) + (", ..." if len(lines) > 8 else "")
            many = len(lines) > 1
            w.add("sentence-lines", "warning", path, lines[0],
                  f"{len(lines)} line{'s' if many else ''} hold{'' if many else 's'} more than "
                  f"one sentence (line{'s' if many else ''} {shown}). "
                  "Put each sentence on its own line when you edit its paragraph.")

        if note or w.under(path, w.theory) or w.under(path, w.tikz):
            continue
        n = last - first + 1
        size = n + len(breaks)
        if size <= max_lines:
            continue
        counted = f"{n} lines" + (f" (about {size} at one sentence per line)" if breaks else "")
        counted += f", and the target is {max_lines}"
        heads = []
        for m in HEADING.finditer(text):
            h = line_of(text, m.start())
            before = h - first + sum(1 for b in breaks if b < h)
            if min(before, size - before) >= max_lines // 5:
                heads.append((abs(size / 2 - before), h, m.group(1)))
        sdir = w.rel(w.sections)
        if path == root:
            if any(m.group(1) == "section" for m in HEADING.finditer(text)):
                w.add("long-file", "warning", path, first,
                      f"the body has {counted}. Move each \\section to "
                      f"{sdir}/<NN>-<slug>.tex, numbered 10, 20, 30 in order, and \\input "
                      "each one here.")
            elif size > max_lines + max_lines // 4:
                w.add("long-file", "warning", path, first,
                      f"the body has {counted}. Move its text to numbered files in "
                      f"{sdir}/ and \\input them here.")
            continue
        folder, head = split_hint(w, path)
        if heads:
            _, h, kind = min(heads)
            w.add("long-file", "warning", path, h,
                  f"has {counted}. Split it at the \\{kind} on line {h}: replace this "
                  f"file with the folder {folder}/, put the text before that line in "
                  f"{head} and the rest in {folder}/10-<slug>.tex, and \\input both "
                  "from the root file.")
        elif size > max_lines + max_lines // 4:
            w.add("long-file", "warning", path, None,
                  f"has {counted}. No heading splits it, so split it between paragraphs "
                  f"where the topic turns: replace this file with the folder {folder}/, "
                  f"with the first part in {head} and the rest in {folder}/10-<slug>.tex.")


def label_kinds(root: Path) -> dict[str, str]:
    """The kind of each label, from the cleveref data in the .aux file of the
    last build. Empty when there is no build or the paper has no cleveref."""
    aux = root.with_suffix(".aux")
    if not aux.is_file():
        return {}
    text = aux.read_text(encoding="utf-8", errors="replace")
    return {m.group("label"): m.group("kind") for m in CREF_TYPE.finditer(text)}


def check_refs(w: Walker, root: Path) -> None:
    """The typed-ref rule, for each file that the body reads."""
    kinds = label_kinds(root)
    texts = list(w.preamble_parts)
    for sty in sorted(w.paper.glob("*.sty")):
        texts.append(strip_comments(sty.read_text(encoding="utf-8", errors="replace")))
    load = "" if CLEVEREF.search("\n".join(texts)) else (
        " The preamble does not load cleveref, so load "
        "\\usepackage[capitalise,noabbrev]{cleveref} after hyperref.")
    root = root.resolve()
    for fi in w.files.values():
        path = fi.path
        if not (fi.body or path == root) or path.suffix == ".bbl":
            continue
        if any(part in GENERATED_DIRS for part in Path(w.rel(path)).parts[:-1]):
            continue
        text = clean(path.read_text(encoding="utf-8", errors="replace"))
        if path == root:
            doc = re.search(r"\\begin\s*\{document\}", text)
            if not doc:
                continue
            text = blank(text, 0, doc.start())
        lines: list[int] = []
        example = ""
        for m in TYPED_REF.finditer(text):
            label = m.group("label").strip()
            kind = kinds.get(label, "")
            if kind.startswith("enum"):
                continue  # a list item, where \cref prints "Item"
            line = line_of(text, m.start())
            named = TYPED_NAMES[m.group("name").lower()]
            if named == "equation":
                fix = f"\\eqref{{{label}}}"
            else:
                start = text[text.rfind("\n", 0, m.start()) + 1 : m.start()].strip() == ""
                fix = f"\\{'C' if start else 'c'}ref{{{label}}}"
            now = TYPED_NAMES.get(kind.lower(), kind.lower())
            if named in MATCHED_KINDS and now in MATCHED_KINDS and named != now:
                w.add("typed-ref", "warning", path, line,
                      f"\"{m.group(0)}\" names a {named}, but {label} is a {kind} in the "
                      f"last build, so the PDF prints the wrong name. Write {fix}.")
                continue
            lines.append(line)
            example = example or f"{fix} for \"{m.group(0)}\""
        if not lines:
            continue
        lines = sorted(set(lines))
        shown = ", ".join(map(str, lines[:8])) + (", ..." if len(lines) > 8 else "")
        many = len(lines) > 1
        w.add("typed-ref", "warning", path, lines[0],
              f"{len(lines)} line{'s' if many else ''} type{'' if many else 's'} a name in front "
              f"of \\ref (line{'s' if many else ''} {shown}). Write {example}, so that the "
              "name follows the label. Fix them in the paragraphs that you edit." + load)


def section_parts(w: Walker, path: Path) -> tuple[str, ...]:
    """The path of a sections/ file below that folder, without .tex. Tuples of
    these sort in the same order as the file manager shows the files."""
    return path.resolve().relative_to(w.sections.resolve()).with_suffix("").parts


def check_sections(w: Walker, root: Path) -> None:
    """The section-name and section-order rules."""
    d = w.sections
    files = sorted(d.rglob("*.tex")) if d.is_dir() else []
    if not files:
        return
    sdir = w.rel(d)
    numbered = {p.resolve() for p in files
                if all(SECTION_NAME.match(s) for s in section_parts(w, p))}
    if not numbered:
        w.add("section-name", "warning", d, None,
              f"no file in {sdir}/ has a number, so the folder does not show the order of "
              "the paper. Keep the names until the user asks to number them, then follow "
              "references/migration.md.")
        return
    owners: dict[tuple[tuple[str, ...], str], Path] = {}
    for p in files:
        if p.resolve() not in numbered:
            w.add("section-name", "warning", p, None,
                  "the name does not start with a number such as 10- or A1-. Give it the "
                  "number of its place in the paper.")
            continue
        parts = section_parts(w, p)
        for i, s in enumerate(parts):
            num = SECTION_NAME.match(s).group(1)
            here = d.joinpath(*parts[: i + 1])
            other = owners.setdefault((parts[:i], num), here)
            if other != here:
                w.add("section-name", "warning", here, None,
                      f"shares the number {num} with {w.rel(other)}. Give one of them a "
                      "free number between its neighbours.")

    root = root.resolve()
    last: tuple[tuple[str, ...], Path] | None = None
    seen: set[Path] = set()
    for f, reader, line in w.section_reads:
        if reader.resolve() != root:
            w.add("section-order", "error", reader, line,
                  f"{w.rel(f)} is input here. Input every file in {sdir}/ from "
                  f"{w.rel(root)}, so that the root file lists the whole paper in order.")
        key = f.resolve()
        if key in seen or key not in numbered:
            continue
        seen.add(key)
        parts = section_parts(w, f)
        if last and parts < last[0]:
            w.add("section-order", "error", reader, line,
                  f"{w.rel(f)} is input after {w.rel(last[1])}, but its name sorts "
                  "before it, so the folder shows another order than the paper. Give the "
                  "file a number that fits its place, or move this line.")
        last = (parts, f)


def split_hint(w: Walker, path: Path) -> tuple[str, str]:
    """The folder that replaces a long file, and the name of its first part."""
    folder = path.with_suffix("")
    m = SECTION_NAME.match(folder.name)
    slug = m.group(2) if m else folder.name
    return w.rel(folder), f"{w.rel(folder)}/00-{slug}.tex"


def check_pointer(w: Walker, root: Path) -> None:
    texts = list(w.preamble_parts)
    for sty in sorted(w.paper.glob("*.sty")):
        texts.append(strip_comments(sty.read_text(encoding="utf-8", errors="replace")))
    joined = "\n".join(texts)
    if "text link/.code" in joined and "cmd/section/before" not in joined:
        w.add("old-pointer", "warning", root, None,
              "the preamble sets the proof pointer at the next paragraph without the "
              "guard for headings and lists, so a result that ends a subsection puts its "
              "pointer inside the next heading, and a list right after a result deletes "
              "it. Replace that code with \\usepackage{deferproofs}.")


def check_generated(w: Walker, paper: Path, root: Path) -> None:
    if not shutil.which("git"):
        return
    inside = subprocess.run(["git", "-C", str(paper), "rev-parse", "--is-inside-work-tree"],
                            capture_output=True, text=True)
    if inside.returncode != 0:
        return
    tracked = subprocess.run(["git", "-C", str(paper), "ls-files", "--", "*-pratend*.tex"],
                             capture_output=True, text=True).stdout.split()
    for t in tracked:
        w.add("generated", "error", paper / t, None,
              "proof-at-the-end writes this file on every build, and git tracks it. "
              f"Run `git rm --cached {t}` and ignore *-pratend*.tex.")
    if not any(r.deferred for r in w.results):
        return
    name = f"{root.stem}-pratenddefaultcategory.tex"
    ignored = subprocess.run(["git", "-C", str(paper), "check-ignore", "-q", name],
                             capture_output=True, text=True)
    if ignored.returncode == 1:
        w.add("generated", "warning", paper / ".gitignore", None,
              f"{name} is generated on every build but not ignored. Add the line "
              "*-pratend*.tex to .gitignore.")


# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("paper", nargs="?", default=".", help="the paper directory (default: .)")
    ap.add_argument("--main", help="the root .tex file, relative to the paper directory")
    ap.add_argument("--theory-dir", default="theory", help="directory of result files (default: theory)")
    ap.add_argument("--tikz-dir", default="tikz", help="directory of figure files (default: tikz)")
    ap.add_argument("--sections-dir", default="sections",
                    help="directory of section files (default: sections)")
    ap.add_argument("--result-env", action="append", default=[],
                    help="another environment that holds a result; may repeat")
    ap.add_argument("--max-lines", type=int, default=200,
                    help="the line target for a file of text (default: 200)")
    ap.add_argument("--json", action="store_true", help="print JSON")
    args = ap.parse_args(argv)

    paper = Path(args.paper).expanduser()
    if not paper.is_dir():
        print(f"check_tex_hygiene: not a directory: {paper}", file=sys.stderr)
        return 2
    try:
        root = find_root(paper, args.main)
    except SystemExit as e:
        print(e, file=sys.stderr)
        return 2
    theory = paper / args.theory_dir
    tikz = paper / args.tikz_dir
    sections = paper / args.sections_dir
    w, summary = check(paper, root, theory, tikz, sections, set(args.result_env),
                       args.max_lines)

    errors = [f for f in w.findings if f.severity == "error"]
    warnings = [f for f in w.findings if f.severity == "warning"]
    order = lambda f: (f.file, f.line or 0, f.rule)  # noqa: E731
    errors.sort(key=order)
    warnings.sort(key=order)

    if args.json:
        print(json.dumps({
            "paper": str(paper.resolve()),
            "root": w.rel(root),
            "summary": summary,
            "errors": [f.__dict__ for f in errors],
            "warnings": [f.__dict__ for f in warnings],
        }, indent=2))
    else:
        print(f"tex-hygiene check of {paper.resolve()} (root: {w.rel(root)})")
        for title, group in (("Errors", errors), ("Warnings", warnings)):
            if not group:
                continue
            print(f"\n{title} ({len(group)})")
            for f in group:
                where = f"{f.file}:{f.line}" if f.line else f.file
                print(f"  {where}  [{f.rule}] {f.message}")
        s = summary
        print(
            f"\n{s['results_in_theory']} of {s['results']} results are in {args.theory_dir}/ "
            f"({s['deferred']} deferred); {s['tikzpictures_in_tikz']} of {s['tikzpictures']} "
            f"TikZ pictures are in {args.tikz_dir}/. {len(errors)} errors, {len(warnings)} warnings."
        )
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
