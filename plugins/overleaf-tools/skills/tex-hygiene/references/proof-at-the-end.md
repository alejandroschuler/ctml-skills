# How proof-at-the-end works here

Read this when a deferred proof misbehaves, when you change `deferproofs.sty`,
or when a paper moves to a new document class or a new TeX Live.

## Contents

- The mechanism, and four things that follow from it
- What deferproofs.sty adds, and the internal names of the package that it
  depends on
- Pointer wording
- Categories
- Editing and debugging

## The mechanism

- A deferred statement, such as `propositionE`, is typeset where it stands,
  inside the `restatable` environment of thmtools. That is what lets the
  appendix restate it later under the same number.
- The body of `proofE` is not typeset in the body. The package writes it, as
  text, to the file `<jobname>-pratend<category>.tex`, which is
  `main-pratendnu-clt.tex` for `main.tex` and `category=nu-clt`. The restated
  statement goes to the same file, before the proof. On Overleaf the jobname
  is `output`, and the file stays with the build output, outside the project.
- `\printProofs[<category>]` inputs that file. It prints what was written to
  the file before it ran.

Four things follow from this.

- A deferred proof is read back from a file, so it has to survive being
  written out as text. Verbatim text and `\verb` do not survive. Every `#` is
  doubled, so a macro with parameters defined inside the proof breaks (the
  build reports "You can't use macro parameter character #"). An `\input` in a
  proof is written as it is and read in the appendix, so a figure in a proof
  works as a `tikz/` file.
- Order matters. A deferred statement after the `\printProofs` of its
  category never reaches it. `deferproofs.sty` stops the build when that
  happens (item 6 below).
- Labels are not defined twice. thm-restate drops the labels in the restated
  copy, and equations in the copy keep the numbers they have in the body.
- The appendix references need three passes to settle. latexmk and Overleaf
  rerun by themselves.

## What deferproofs.sty adds

`deferproofs.sty` started as the inline preamble block of the dml-tmle paper.
It does six things.

1. It loads the package with `conf={end, restate}`, so every E environment
   defers its proof and restates its statement.
2. It defines `theoremE`, `propositionE`, `lemmaE`, `corollaryE` and `proofE`.
3. It sets `text proof=` to nothing. The header of each deferred proof is then
   a plain "Proof.", because the heading that the appendix file writes above
   `\printProofs` already names the result. An empty proof name prints the
   default because thmtools, which the package loads, treats it that way. With amsthm alone it would
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
6. It stops the build with an error when a deferred proof is never printed.
   The stock package drops such a proof with no error or warning. A hook at
   the end of the package's `proofEndOrig` environment, which every `proofE`
   goes through, records the category when `\ifproofend` is true, that is,
   when the proof goes to the file. `\printProofs` clears the record, and
   `\AtEndDocument` reports each category left. The error names the
   category: `defaultcategory` for a result with no `category=`, or the slug
   of a result whose `\printProofs[<slug>]` line is missing, misspelled, or
   before the statement. A result with no category gives no error while the
   paper still has a `\printProofs` with no argument, as in the middle of the
   move in `references/migration.md`; the checker reports it then. The error
   is false in a partial build with `\includeonly` that leaves out the
   appendix, and in a paper whose proofs print from a separate supplement
   root.

Items 4 to 6 depend on names inside the package: `\pratendtextlink`, the key
`/prAtEnd/text link`, `\pratendmacrocat<category>`, `\prefixPrAtEndFiles`,
the environment `proofEndOrig`, the switch `\ifproofend` and the macro
`\category`. They exist in the version of 2025/06/11. After a TeX Live
update, build the template in `assets/template/` and check that the pointer
and the proof still appear. Then delete `category=mean-consistency` from
`theory/mean-consistency.tex`, build again, and check that the build stops
with the error of item 6. If a later version renames them, the fix goes in
`deferproofs.sty` alone.

## Pointer wording

- `\autoref{pf:<slug>}` prints "subsection A.3". `\cref{pf:<slug>}` prints
  "Section A.3" for a subsection unless the paper renames it, so keep
  `\autoref` in `text link`, although the text cites with `\cref`.
- Keep `\autoref` in the heading `Proof of \autoref{thm:<slug>}` too. hyperref
  turns it into "Proof of Proposition 2" in the PDF bookmark, but with `\cref`
  the bookmark reads "Proof of thm:<slug>".
- To say "Appendix A.3" instead, write
  `text link={The proof is in Appendix~\ref{pf:<slug>}.}`.
- A class can number the appendix differently. With `elsarticle`, `\autoref`
  prints "subsection Appendix A.1" and `\ref` prints "Appendix A.1".

## Categories

`category=<slug>` goes in the options bracket, the second bracket:

```latex
\begin{lemmaE}[Tail bound][text link={The proof is in \autoref{pf:tail-bound}.}, category=tail-bound]
```

Each deferred result has a category of its own, named by its slug. The
package writes one file for each category, and the appendix file prints each
one with `\printProofs[<slug>]` at the line where the proof belongs. So the
appendix file can print the proofs in any order. A category shared by two
results prints both at one line, in the order of the body, and they can be
moved apart only by an edit to `theory/`. The checker reports a category that
is not the slug of the result's file.

The package also has `textAtEnd`, which writes text to the file of a category,
so that the text prints with its proofs. Do not use it. The text would live in
a `theory/` file or a body file but print in the appendix, so a reorder of the
appendix would need edits outside the appendix files. Write the text in the
appendix file instead.

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
