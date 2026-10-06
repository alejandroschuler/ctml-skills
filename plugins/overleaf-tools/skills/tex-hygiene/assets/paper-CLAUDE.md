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
- Every section lives in `sections/<slug>.tex`, which starts with its heading,
  and the root file inputs it. Keep each file of text under about 200 lines.
  Split a longer file at a subsection, or between paragraphs where the topic
  turns. Leave it when it is only a few paragraphs over and nothing splits it
  well. An `\input` path starts from the root file's folder. Notes are not
  split.
- Put each sentence of prose on its own line. When you edit a paragraph in
  another style, re-break that paragraph and no other.
- `deferproofs.sty` holds the proof-at-the-end setup. Build with
  `latexmk -pdf main.tex`. The build writes `main-pratenddefaultcategory.tex`;
  never edit or commit it.
- Run the skill's checker on this folder before each push.

## Overleaf

Coauthors edit this paper on Overleaf. Pull before you read or edit it, with
`git pull --rebase --autostash`, or with `make pull-paper` from the code repo
when this is the `paper/` clone of a reproducible-paper-artefacts project.
