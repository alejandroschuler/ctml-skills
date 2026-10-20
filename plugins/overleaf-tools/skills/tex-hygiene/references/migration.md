# Converting an existing paper

A conversion only moves text between files. Keep content edits out of it, so
that the before and after builds can be compared line by line. Work in the
paper repo, and change one kind of thing at a time.

## Contents

1. Before you start
2. Build a baseline
3. Get the worklist
4. Set up
5. Move the results, one at a time
6. Move the figures, one at a time
7. Move the sections, and number a sections/ folder that has no numbers
8. Re-break the lines and fix the typed names, if the user agrees
9. Build and compare
10. Check and commit
11. Move the appendix text out of theory/, for a paper in the layout before
    overleaf-tools 0.9.0

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

`${CLAUDE_SKILL_DIR}` is the folder that holds `SKILL.md`. Write out its path,
as the command in "Check" in `SKILL.md` shows it.

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/check_tex_hygiene.py" .
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
   appendix takes the deferred shape, with `category=<slug>`. Its
   hand-written heading stays where it is in the appendix file, and
   `\printProofs[<slug>]` replaces the proof under it. If the old label of the
   heading is not `pf:<slug>`, rename it everywhere it is cited. If the old
   proof had no heading of its own, add `\subsection{Proof of
   \autoref{thm:<slug>}}` and `\label{pf:<slug>}` above the `\printProofs`
   line, as the template does.
4. Write `theory/<slug>.tex`. Replace the statement in its section file with
   `\input{theory/<slug>}`. In the appendix file, delete the old proof and any
   statement restated under the heading, because `\printProofs` restates it.
5. Delete sentences that the pointer now makes redundant, such as "The proof
   is deferred to the appendix." Leave all other prose as it is.

The appendix keeps its old order, because each heading stays where it was.

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
every file gets a new name. Do "1. Before you start" and "2. Build a baseline"
first. Step 5 below compares with that baseline.

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

## 8. Re-break the lines and fix the typed names, if the user agrees

Coauthors are paused for the conversion, so this is the best time to put each
sentence on its own line in the whole paper. Ask the user first, because the
change touches almost every line of text. Replace only the space between two
sentences with a line break, and leave all other text as it is. Build before
and after the change, and compare the two with `pdftotext`. The text of the
PDF must not change at all. Make the change a commit of its own.

The checker's `typed-ref` warnings can be fixed in the same way, if the user
agrees: replace each typed name and its `\ref` with `\cref`, `\Cref` or
`\eqref`, and change nothing else. The text of the PDF may change only where
a typed name was wrong, or where `\eqref` adds the parentheses around an
equation number. Make this a commit of its own too.

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
figures, the sections, the line breaks and the typed names, and messages that
say what moved.
Push by the paper repo's rules, and ask first if it has none.

## 11. Move the appendix text out of theory/

A paper set up before overleaf-tools 0.9.0 keeps the heading of each deferred
proof in a `textAtEnd` block in its `theory/` file, and prints the proofs
with one `\printProofs`, in the order of the body. The checker reports
`text-at-end` and `deferred-shape` errors for it. The move changes no text in
the PDF. Do "1. Before you start" and "2. Build a baseline" first. Read the
open Overleaf comments on the `theory/` files with the `overleaf-comments`
skill, if it is installed, because comments on moved text can be lost.

1. Copy the plugin's `deferproofs.sty` over the paper's copy. Keep each change
   that the paper's `CLAUDE.md` records for its copy, such as a pointer on a
   line of its own or another proof name.
2. Take the deferred results in the order that they print: for each
   `\printProofs`, the results of its category in the order of the body. For
   each result:
   1. Add `category=<slug>` to the options of its statement. Replace a shared
      category, such as `category=rate`, with the slug.
   2. Move the text of its `textAtEnd` block (the heading, the label and any
      sentences) to the appendix file, at the place of the `\printProofs` that
      printed it and after the blocks that you moved before it. Delete the
      `textAtEnd` block from the `theory/` file.
   3. Add `\printProofs[<slug>]` after the moved text.
3. Delete the old `\printProofs` lines and the comments that describe them.
4. Other text in a `theory/` file, outside the result and its proof, prints
   where the file is input. Move it to the file that inputs it, next to the
   `\input` line.
5. Run the checker until it reports no `text-at-end` or `deferred-shape`
   error, and no `theory-text` error other than those of step 7. Build and
   compare as in "9. Build and compare": the text of the PDF must not change
   at all.
6. Update the paper's `CLAUDE.md` from `assets/paper-CLAUDE.md`, and commit
   with no other change.
7. Text that says how a cited source gives a result is its proof, but a
   `proof` environment adds a "Proof." header to the PDF. Ask the author
   before you make that change, and make it a commit of its own.
