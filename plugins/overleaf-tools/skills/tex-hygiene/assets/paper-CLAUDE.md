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
- `deferproofs.sty` holds the proof-at-the-end setup. Build with
  `latexmk -pdf main.tex`. The build writes `main-pratenddefaultcategory.tex`;
  never edit or commit it.
- Run the skill's checker on this folder before each push.
