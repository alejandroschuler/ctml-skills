# Converting an existing paper

A conversion only moves text between files. Keep content edits out of it, so
that the before and after builds can be compared line by line. Work in the
paper repo, and change one kind of thing at a time.

## 1. Before you start

- Pull first, with `git pull` in a plain Overleaf clone or `make pull-paper`
  in a reproducible-paper-artefacts project, and start from a clean tree.
- The conversion moves text that coauthors may be editing on Overleaf, and
  such conflicts are hard to merge. Tell the user before you start, so that
  they can ask coauthors to pause, and push soon after you finish.

## 2. Build a baseline

Keep the baseline files outside the paper repo, for example in the session's
scratch folder, so that they are never pushed. Here `$B` is that folder.

```bash
latexmk -pdf -interaction=nonstopmode main.tex
pdftotext main.pdf "$B/before.txt"
grep -o '\\newlabel{[^}]*}{{[^}]*}' main.aux | grep -v prAtEnd | sort > "$B/labels-before.txt"
grep -c 'undefined' main.log
```

The labels file maps each label to its printed number. After the conversion,
every result, equation and figure must keep its number.

## 3. Get the worklist

```bash
python3 <skill-dir>/scripts/check_tex_hygiene.py .
```

The errors are the worklist, chiefly `inline-result`, `stray-proof` and
`inline-tikz`. A `long-file` warning on the root file adds its sections to the
worklist. Treat the other warnings as questions. For an orphan file, ask the
author whether to delete it or input it; do not decide alone.

## 4. Set up

Follow "Set up a paper" in `SKILL.md`. If the preamble already has its own
`proof-at-the-end` block, as the dml-tmle paper does, replace the block with
`\usepackage{deferproofs}`, and keep any aliases the block defined that
`deferproofs.sty` does not.

## 5. Move the results, one at a time

For each inline result:

1. Take the slug from its label. A result without a label gets one now.
2. Find its proof. It may follow the statement, or sit in the appendix under a
   hand-written subsection, often titled "Proof of Theorem N" and labelled
   `pf:<something>`. The checker's `stray-proof` lines point at these.
3. Choose the shape from the table in `SKILL.md`. A proof that lived in the
   appendix takes the deferred shape, and the `textAtEnd` block replaces the
   hand-written subsection. If the old label is not `pf:<slug>`, rename it
   everywhere it is cited.
4. Write `theory/<slug>.tex`. Replace the statement in its section file with
   `\input{theory/<slug>}`, and delete the old appendix subsection with its
   proof.
5. Delete sentences that the pointer now makes redundant, such as "The proof
   is deferred to the appendix." Leave all other prose as it is.

`\printProofs` orders the proofs by the body. If the old appendix used another
order and the author wants to keep it, use categories (see
`references/proof-at-the-end.md`).

A hand-written proof whose statement is gone, which prints as "Proof of ??",
is a question for the author: delete it, or restore its statement.

## 6. Move the figures, one at a time

For each inline `tikzpicture`:

1. Move the whole `figure` environment, from `\begin{figure}` to
   `\end{figure}`, to `tikz/<slug>.tex`, where the slug comes from its `fig:`
   label.
2. Write the header comment. Take what you can from the surrounding text and
   from notes in the repo, since a project skill or `CLAUDE.md` often records
   decisions about a figure. Do not state a fact about the geometry that you
   have not checked.
3. Replace the figure in the section file with `\input{tikz/<slug>}`.

Leave the drawing code as it is. Turning hardcoded coordinates into
parameters is a separate change, best made the next time the figure is edited,
unless the author asks for it now.

## 7. Move the sections

When the checker gives a `long-file` warning for the root file, move each
section to `sections/<NN>-<slug>.tex`, with its heading and label at the top,
and replace it with `\input{sections/<NN>-<slug>}`. Number the body sections
10, 20, 30 in order, and the appendix sections A1, A2, A3. Then split each
section file that is still past the target, as in "Section files" in
`SKILL.md`. Do not change any words on the way.

### Number a sections/ folder that has no numbers

A paper set up before the numbering rule keeps its sections in
`sections/<slug>.tex`, and a long section can input its parts from
`sections/<section-slug>-<slug>.tex`. The checker gives one `section-name`
warning for such a paper. Number its files only when the user asks, because
every file gets a new name.

1. Read the open Overleaf comments on the section files with the
   `overleaf-comments` skill, if it is installed. A file that gets a new name
   can lose its comments, so tell the user which files have open comments
   before you start.
2. Give each section file its number with `git mv`, in the order of the root
   file: 10, 20, 30 for the body, and A1, A2, A3 for the appendix.
3. A section that inputs its parts becomes a folder. Move the section file to
   `<NN>-<slug>/00-<slug>.tex`. Move each part to `10-<slug>.tex`,
   `20-<slug>.tex` and so on in that folder, in the order that the section
   inputs them, and drop the section's slug from the front of the part's
   name. Move each part's `\input` line from the section file to the root
   file, after the line of the section.
4. Change the `\input` lines in the root file to the new paths. Run the
   checker again until it reports no `section-name` or `section-order`
   problem.
5. Build and compare as in step 9. Commit the renames with no other change,
   so that git records them as renames.
6. After the push, tell the user to delete any empty old folder in the
   Overleaf file tree.

## 8. Re-break the lines, if the user agrees

Coauthors are paused for the conversion, so this is the best time to put each
sentence on its own line in the whole paper. Ask the user first, because the
change touches almost every line of text. Replace only the space between two
sentences with a line break, and leave all other text as it is. Build before
and after the change, and compare the two with `pdftotext`. The text of the
PDF must not change at all. Make the change a commit of its own.

## 9. Build and compare

```bash
latexmk -pdf -interaction=nonstopmode main.tex
pdftotext main.pdf "$B/after.txt"
grep -o '\\newlabel{[^}]*}{{[^}]*}' main.aux | grep -v prAtEnd | sort > "$B/labels-after.txt"
diff "$B/labels-before.txt" "$B/labels-after.txt"
diff "$B/before.txt" "$B/after.txt"
grep -c 'undefined' main.log
```

These differences are expected: the new `pf:` labels, the proof subsections,
the pointer sentences, the statements restated in the appendix, and page
numbers after the moved text. No result, equation or figure may change its
number, and the body text may not change in any other way. The count of
undefined references must not go up, and the log must show no multiply
defined labels.

## 10. Check and commit

Run the checker again. No errors may remain, and each remaining warning needs
a reason. Commit in the paper repo, with one commit each for the results, the
figures, the sections and the line breaks, and messages that say what moved.
Push by the paper repo's rules, and ask first if it has none.
