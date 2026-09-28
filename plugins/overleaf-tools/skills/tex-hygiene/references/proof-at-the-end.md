# How proof-at-the-end works here

Read this when a deferred proof misbehaves, when you change `deferproofs.sty`,
or when a paper moves to a new document class or a new TeX Live.

## The mechanism

- A deferred statement, such as `propositionE`, is typeset where it stands,
  inside the `restatable` environment of thmtools. That is what lets the
  appendix restate it later under the same number.
- The body of `proofE` is not typeset in the body. The package writes it, as
  text, to the file `<jobname>-pratend<category>.tex`, which is
  `main-pratenddefaultcategory.tex` for `main.tex`. The restated statement and
  the text of each `textAtEnd` block go to the same file, in the order they
  appear. On Overleaf the jobname is `output`, and the file stays with the
  build output, outside the project.
- `\printProofs` inputs that file. It prints what was written to the file
  before it ran.

Four things follow from this.

- A deferred proof is read back from a file, so it has to survive being
  written out as text. Verbatim text and `\verb` do not survive. Every `#` is
  doubled, so a macro with parameters defined inside the proof breaks (the
  build reports "You can't use macro parameter character #"). An `\input` in a
  proof is written as it is and read in the appendix, so a figure in a proof
  works as a `tikz/` file.
- Order matters. A deferred statement after `\printProofs` never reaches it.
- Labels are not defined twice. thm-restate drops the labels in the restated
  copy, and equations in the copy keep the numbers they have in the body.
- The appendix references need three passes to settle. latexmk and Overleaf
  rerun by themselves.

## What deferproofs.sty adds

`deferproofs.sty` started as the inline preamble block of the dml-tmle paper.
It does five things.

1. It loads the package with `conf={end, restate}`, so every E environment
   defers its proof and restates its statement.
2. It defines `theoremE`, `propositionE`, `lemmaE`, `corollaryE` and `proofE`.
3. It sets `text proof=` to nothing. The header of each deferred proof is then
   a plain "Proof.", because the subsection heading from `textAtEnd` already
   names the result. An empty proof name prints the default because thmtools,
   which the package loads, treats it that way. With amsthm alone it would
   print a lone period.
4. It sets the pointer (`text link`) in front of the first word of the next
   paragraph, through `\everypar`, where the package would give it a line of
   its own. The dml-tmle version did only this, and a test showed two
   failures. Before a `\subsection`, the pointer went into the heading line.
   Before a list, the list code deleted the pointer. So a pending pointer is
   now set as a paragraph of its own before any sectioning command (through
   LaTeX's `cmd/<name>/before` hooks) and before any list, theorem or proof
   (by patching `\list` and `\trivlist`). Inside a box, such as a float,
   nothing happens, and the pointer waits for the next paragraph of body
   text. This was tested with the classes article, amsart, scrartcl,
   elsarticle, report and revtex4-2, and with article plus titlesec.
5. It makes `\printProofs` read the proof file only when this build wrote to
   it. The stock command stops the build with a missing-file error when no
   deferred result exists yet. When the last deferred result has been
   removed, it prints the stale proofs of an earlier build.

Items 4 and 5 depend on names inside the package: `\pratendtextlink`, the key
`/prAtEnd/text link`, `\pratendmacrocat<category>` and `\prefixPrAtEndFiles`.
They exist in the version of 2025/06/11. After a TeX Live update, build the
template in `assets/template/` and check that the pointer and the proof still
appear. If a later version renames them, the fix goes in `deferproofs.sty`
alone.

## Pointer wording

- `\autoref{pf:<slug>}` prints "subsection A.3". `\cref{pf:<slug>}` prints
  "section A.3" for a subsection unless the paper renames it, so keep
  `\autoref` in `text link`.
- To say "Appendix A.3" instead, write
  `text link={The proof is in Appendix~\ref{pf:<slug>}.}`.
- A class can number the appendix differently. With `elsarticle`, `\autoref`
  prints "subsection Appendix A.1" and `\ref` prints "Appendix A.1".

## Categories

`category=<name>` goes in the options bracket, the second bracket:

```latex
\begin{textAtEnd}[category=technical]
\subsection{Proof of \autoref{thm:tail-bound}}
\label{pf:tail-bound}
\end{textAtEnd}
\begin{lemmaE}[Tail bound][text link={The proof is in \autoref{pf:tail-bound}.}, category=technical]
```

The `textAtEnd` block needs the same category. Without it, the subsection
heading goes to the default group while the proof goes to the other one.
Each category needs its own `\printProofs[<name>]`, placed after the last
result of that category.

## Editing and debugging

- A jump from the PDF appendix to the source (SyncTeX) lands in the
  generated file, because that is the file the appendix reads. Edit the result
  in its `theory/` file. Changes to the generated file are overwritten on the
  next build.
- `\pratendEnableDebugSynctex` in the preamble typesets every proof in place,
  for one debugging build. That build drops the result titles and the
  pointers. Remove the line afterwards.
- A result stated inside a deferred proof would be deferred a second time,
  while the appendix is being printed. Give a result inside a proof the plain
  environments.
