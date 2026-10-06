---
name: tex-hygiene
description: "Keeps the LaTeX source of a paper in fixed places. Every theorem, proposition, lemma and corollary lives with its proof in its own file, theory/<slug>.tex, which the body inputs where the statement belongs, and proof-at-the-end prints the proof in the appendix by itself. Every TikZ figure lives in its own file, tikz/<slug>.tex. The text is split into section files of at most about 200 lines, with each sentence on its own line, so that agents can work on the paper in parallel and merge cleanly. Use it whenever you add, move, split, restate or delete a result, a proof, a TikZ figure or a section in a .tex paper, write or re-break paragraphs of a paper, start a new paper, move proofs to the appendix, or tidy or check the layout of an existing paper, even when the user does not name the convention. It covers any LaTeX manuscript, including an Overleaf clone and the paper/ repo of a reproducible-paper-artefacts project, but not notes."
---

# TeX hygiene

A paper's source stays easy to read and to change when every result, every
figure and every section has exactly one home:

- **Results.** Each theorem, proposition, lemma and corollary lives with its
  proof in `theory/<slug>.tex`. The body inputs the file where the statement
  belongs. When the proof belongs in the appendix, the `proof-at-the-end`
  package prints it there, so a new result never needs an appendix edit.
- **Figures.** Each TikZ figure lives in `tikz/<slug>.tex`, which holds the
  whole `figure` environment. The body inputs the file where the figure
  belongs.
- **Text.** Each section lives in `sections/<slug>.tex`, and a file that
  grows past about 200 lines splits again. Each sentence is on its own line.

This pays off in four ways. A result moves as one unit: move its `\input` line
and the statement, proof, labels and appendix heading all go with it. Section
files read as prose. A coauthor on Overleaf finds a result from its label,
since `thm:nu-clt` is in `theory/nu-clt.tex`. And a figure file keeps the
notes on its geometry next to the drawing, where the next edit will see them.

`assets/template/` is a small paper laid out this way, and it builds as it is.
Copy from it rather than writing the setup from memory.

## Names

`<slug>` is the label without its prefix. `thm:nu-clt` lives in
`theory/nu-clt.tex`, and `fig:snu-decomposition` lives in
`tikz/snu-decomposition.tex`. The appendix subsection of a deferred proof is
labelled `pf:<slug>`, with the same slug. Use lowercase words joined by
hyphens. When you rename a label, rename the file and the `pf:` label with it.

A paper that already uses this layout under another folder name, such as
`theorems/`, keeps that name unless the author asks for the rename. Give the
name to the checker with `--theory-dir`.

## Result files

The shape of a result's file depends on where its statement and proof go:

| Statement | Proof | Environments in the file | Template |
|---|---|---|---|
| body | appendix | `textAtEnd`, then `propositionE` and `proofE` | `theory/mean-consistency.tex` |
| body | right after the statement | `proposition` and `proof` | `theory/chebyshev.tex` |
| appendix | right after the statement | `lemma` and `proof`, input in the appendix | `theory/chebyshev.tex` |
| anywhere | none, for a cited or standard result | `theorem` alone | `theory/chebyshev.tex` without the proof |

Use the environment for the result's kind. The deferred ones are `theoremE`,
`propositionE`, `lemmaE` and `corollaryE`. Definitions, assumptions, examples
and remarks are not results, so they stay in the prose where they are
introduced.

The deferred shape is the usual one:

```latex
\begin{textAtEnd}
\subsection{Proof of \autoref{thm:nu-clt}}
\label{pf:nu-clt}
\end{textAtEnd}
\begin{propositionE}[Limit law][text link={The proof is in \autoref{pf:nu-clt}.}]
\label{thm:nu-clt}
...statement...
\end{propositionE}

\begin{proofE}
...proof...
\end{proofE}
```

- The `textAtEnd` block gives the proof a numbered appendix subsection with
  the label `pf:<slug>`. The proof then shows in the table of contents, and
  `\autoref{pf:<slug>}` works from anywhere. The block sits in the result's
  own file, which is why a new result needs no appendix edit.
- `text link` is the pointer to the proof. `deferproofs.sty` sets it in front
  of the first word of the next paragraph. Before a heading, a list, a theorem
  or a display, it sets the pointer on a line of its own instead.
- An untitled result keeps the empty first bracket:
  `\begin{propositionE}[][text link={...}]`.
- For a sketch in the body and the full proof in the appendix, put a plain
  `\begin{proof}[Proof sketch]` after the statement and the full proof in
  `proofE`.
- Point at a proof with `\autoref{pf:<slug>}`. Never type an appendix number,
  because each new result renumbers the proofs after it.

## The appendix

```latex
\appendix
\section{Proofs}

\subsection{Supporting lemmas}
\input{theory/chebyshev}   % stated and proved here, with plain environments

\printProofs               % every deferred proof, in body order
```

`\printProofs` prints each deferred proof under its own subsection, with the
statement restated above it under its original number.

Every deferred statement has to come before `\printProofs`. The package prints
only the proofs that it has collected by that point, so a `proofE` stated
later disappears without an error. This is why a result stated in the
appendix uses the plain environments.

To group the proofs or change their order, tag results with
`category=<name>` in the options bracket, give their `textAtEnd` blocks the
same `[category=<name>]`, and add a `\printProofs[<name>]` for each group.
Keep the default when the order does not matter, so that a new result still
needs no appendix edit.

## Figure files

A figure file holds a header comment and then the whole `figure` environment,
caption and label included. `assets/template/tikz/mean-tails.tex` shows the
shape.

- The header starts with the label, `% fig:<slug>`. It says what the figure
  shows, which display or result it illustrates, and where its numbers come
  from ("hand-drawn; no generator" when nothing makes them). It names the free
  parameters, says what is derived from them and what to recheck after an
  edit, and lists the TikZ libraries that the figure needs.
- When the author decides something about a figure, such as a deletion or a
  symbol that must not appear, record the decision in the header with its
  date, so that a later edit does not undo it.
- Set the free parameters with `\pgfmathsetmacro` at the top of the picture,
  and derive every coordinate and angle from them. A change to one number
  then keeps the picture true.
- Define the figure's colors and styles in its file. Load TikZ libraries in
  the preamble, because all figures share them.
- A figure inside a proof is also a `tikz/` file, input from the proof.
- A plot that code produces is not TikZ source. It goes in `figures/`, and in
  a reproducible-paper-artefacts project it goes through the pipeline.

## The text

The section rule is for the manuscript: the root file, every file that it
inputs, and a supplement with its own root. It is not for notes. A document in
`notes/`, a document that the paper does not input, and a root file with the
mode line `% writing-math: note` are notes. Do not split a note into files.
The sentence rule is for every `.tex` document, notes too, and the
`writing-math` skill states it as well.

Both rules make merges easy. Agents that work at the same time on different
files never get a merge conflict. With one sentence on each line, edits to
different sentences of one file also merge without a conflict. Short files
help an agent in other ways too. It reads less before an edit, the text that
an edit replaces is more likely to be unique in the file, and `git log` on a
file gives the history of one part of the paper.

### Section files

Each section lives in `sections/<slug>.tex`, which starts with its `\section`
heading and label, and the root file inputs it. The root file then holds the
preamble, the title, the abstract and one `\input` line for each section, and
a section moves with its `\input` line. The slug comes from the section's
`sec:` label, or from its heading when it has no label. A new paper starts
this way. Convert an existing paper when the body of its root file grows past
the target below, or when the user asks. A paper that already keeps its
sections in another folder keeps that folder.

Keep each file under about 200 lines, counted with one sentence on each line.
That is about five pages. When a file grows past the target, split it:

- **At a heading.** Move a `\subsection` or a lower heading, with its text, to
  `sections/<section-slug>-<slug>.tex`, and input that file where the text
  was. Each piece should hold at least a few paragraphs.
- **Between paragraphs**, when no heading splits the file. Split where the
  topic turns. Do not add a heading to make a split, because a new heading
  changes the paper.
- **Not at all**, when the file is only a few paragraphs over, up to about 250
  lines, and no heading splits it into two good pieces.

The target is for files of text. A `theory/` file keeps its whole proof, and a
`tikz/` file its whole figure, however long they are. Never split a generated
file, such as a table that a reproducible-paper-artefacts pipeline writes.

- Use `\input`. `\include` starts a new page and cannot be nested, so it is
  only for the chapters of a thesis or a book.
- An `\input` path starts from the folder of the root file, also inside a file
  in `sections/`. Write `\input{sections/simulation-design}`, not
  `\input{simulation-design}`.
- A split only moves text. Compare the text of the PDF before and after the
  split with `pdftotext`. It must not change.
- Overleaf review comments and tracked changes do not move with text that
  moves to another file through git, and they can be lost. Before you split a
  file that coauthors review on Overleaf, read its open comments with the
  `overleaf-comments` skill if it is installed. Tell the user which comments
  are on text that will move.

### One sentence per line

Put each sentence of prose on its own line. Do not wrap lines at a fixed
width, and do not put a whole paragraph on one line. Inside a paragraph, LaTeX
prints a line break as a space, and only a blank line ends the paragraph, so
the PDF does not change. The user and coauthors can then point at a sentence
by its line number. A LaTeX error names the line of one sentence, and a diff
shows the sentence that changed, not its whole paragraph.

- The rule is for each sentence that LaTeX prints: in the body, in statements
  and proofs, in captions and in footnotes. It is not for comments.
- A display equation breaks its sentence. The text after the display starts
  on a new line.
- Follow the rule in each paragraph that you write. When you edit a paragraph
  that has another style, re-break all of that paragraph. Do not re-break
  paragraphs that you do not otherwise change. A coauthor may be editing them
  on Overleaf, and the re-break would conflict with their edit.
- To convert a whole paper, ask the user first, and make the conversion a
  commit with no other change. `references/migration.md` has the steps.

## Set up a paper

1. Copy `assets/template/deferproofs.sty` next to `main.tex`, and make the
   folders `theory/`, `tikz/` and `sections/`.
2. Load `\usepackage{deferproofs}` in the preamble after the theorem
   declarations, and after `hyperref` and `cleveref`. For each other result
   environment the paper declares, add an alias after it, for example
   `\newEndThm{claimE}{claim}`. If the preamble already loads
   `proof-at-the-end` itself, remove that code, since `deferproofs.sty`
   replaces it.
3. Put `\section{Proofs}` with `\printProofs` in the appendix.
4. Add `*-pratend*.tex` to the paper's `.gitignore`. The package writes
   `main-pratenddefaultcategory.tex` on every build.
5. Add the sections in `assets/paper-CLAUDE.md` to the paper repo's
   `CLAUDE.md`, so that later sessions keep the layout and pull first.

## Day-to-day edits

- **New result.** Copy the matching template to `theory/<slug>.tex` and input
  it where the statement belongs.
- **New figure.** Copy `tikz/mean-tails.tex` to `tikz/<slug>.tex`, replace the
  drawing and the header, and input it where the figure belongs.
- **New section.** Write it in `sections/<slug>.tex`, which starts with its
  heading, and input it from the root file.
- **A file of text passes about 200 lines.** Split it as in "Section files".
- **Move a result, a figure or a section.** Move its `\input` line.
- **Edit a result.** Find the file from the label and edit it there. The
  appendix prints from a generated file, so a jump from the PDF appendix to
  the source can land in `main-pratenddefaultcategory.tex`. Do not edit that
  file.
- **Delete a result or a figure.** Remove its `\input` line and its file, then
  search for `\autoref`, `\ref` and `\cref` calls to its labels.
- **A coauthor's inline result or figure.** Coauthors on Overleaf may write a
  theorem or a TikZ picture inline. Move it into its own file, as for a new
  one.

After you edit a result file, run the `readable-math` skill if it is
installed, as for any `.tex` edit. Follow the paper repo's rules for commits
and pushes. If it has none, ask before you push, because coauthors see an
Overleaf push at once and Overleaf refuses force pushes.

## Check

Run the checker after each change to the layout and before each push:

```bash
python3 <skill-dir>/scripts/check_tex_hygiene.py <paper-dir>
```

`<skill-dir>` is the directory of this skill. Add `--theory-dir theorems` when
the paper uses that folder name, and `--main <file>` when the root file is not
`main.tex`. The checker only reads. It follows the `\input` graph from the root
file in document order, skips comments, and prints each problem with its
`file:line`. Errors are layout breaks and lost text, and warnings are drift.
It exits 1 when there is an error. The list of rules is at the top of the
script, and `--json` gives the same report as JSON.

Two warnings are about the text. `long-file` marks a file past the line target
(`--max-lines`, 200 by default), and `sentence-lines` marks lines that hold
more than one sentence. A paper written in another style gets many
`sentence-lines` warnings. Fix them in the paragraphs that you edit, and leave
the rest. The `long-file` rule skips a root file whose mode line says `note`.

Then build the paper with `latexmk -pdf main.tex`, or with three `pdflatex`
passes, since the appendix references settle on the third. Read the log for
undefined or multiply defined references.

## Convert an existing paper

Read `references/migration.md` first. You pull, build a baseline and record
its numbering, and take the checker's errors as the worklist. Then you move one
result or figure at a time, then the sections, build again, and compare the
numbering and the text with the baseline.

## Traps

`references/proof-at-the-end.md` explains how the package works and what
`deferproofs.sty` changes. These traps come up most:

- The package writes each deferred proof to a file and reads it back in the
  appendix. Verbatim text cannot make that trip, and every `#` in the proof is
  doubled on the way. So a deferred proof holds no `verbatim`, no `\verb` and
  no macro definition with parameters. Define such macros in the preamble, or
  give that result the plain shape.
- A deferred result stated after `\printProofs` loses its proof silently.
- Do not `\label` the items of a list in a statement and cite them by number
  in the proof. When someone rewrites the list as prose, the citations break
  with no warning. Name the condition in words in the proof instead.
- A journal class can number the appendix in its own way. With `elsarticle`,
  `\autoref{pf:...}` prints "subsection Appendix A.1". After a change of
  class, read one pointer and adjust the `text link` wording if it reads
  badly, for example to `\ref` in place of `\autoref`.
