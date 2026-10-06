## Source layout

This paper follows the `tex-hygiene` skill of the overleaf-tools plugin.

- Every theorem, proposition, lemma and corollary lives with its proof in
  `theory/<slug>.tex`, where `<slug>` is its label without the prefix.
  `\input` the file where the statement belongs. A proof that belongs in the
  appendix uses `propositionE` (or `theoremE`, `lemmaE`, `corollaryE`) with
  `proofE`, and the one `\printProofs` in the appendix prints it, so a new
  result needs no appendix edit.
- Every TikZ figure lives in `tikz/<slug>.tex`, which starts with a header
  comment and holds the whole `figure` environment. `\input` it where the
  figure belongs.
- Every section lives in `sections/<NN>-<slug>.tex`, which starts with its
  heading. The numbers sort in the order of the paper: 10, 20, 30 for the
  body, A1, A2 for the appendix, and a free number such as 25 for a new
  section, so that no other file gets a new name. The root file inputs every
  file in `sections/` in the order of their names, and no section file
  inputs another one.
- Keep each file of text under about 200 lines. A longer file becomes a
  folder with the same name, such as `sections/30-methods/`, with the heading
  and lead-in in `00-methods.tex` and the parts in `10-<slug>.tex`,
  `20-<slug>.tex`. Split at a subsection, or between paragraphs where the
  topic turns. Leave a file whole when it is only a few paragraphs over and
  nothing splits it well. An `\input` path starts from the root file's
  folder. Notes are not split.
- Put each sentence of prose on its own line. When you edit a paragraph in
  another style, re-break that paragraph and no other.
- Cite results, sections, figures and tables with `\cref`, or `\Cref` at the
  start of a sentence, and equations with `\eqref`. Do not type the name in
  front of `\ref`, as in `Lemma~\ref{...}`. The proof headings and pointers
  that the templates write keep `\autoref`.
- `deferproofs.sty` holds the proof-at-the-end setup. Build with
  `latexmk -pdf main.tex`. The build writes `main-pratenddefaultcategory.tex`;
  never edit or commit it.
- Run the skill's checker on this folder before each push.

## Overleaf

Coauthors edit this paper on Overleaf. Pull before you read or edit it, with
`git pull --rebase --autostash`, or with `make pull-paper` from the code repo
when this is the `paper/` clone of a reproducible-paper-artefacts project.
