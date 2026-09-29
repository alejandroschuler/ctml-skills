---
name: readable-math
description: "Review the mathematics of a LaTeX document after editing it: a readability review of notation, scope and glosses, and a correctness review of the proofs and derivations, split across agents by argument. Invoke after editing any LaTeX (.tex) document, before declaring the task done. By default it reviews only the text that changed since the last review; pass full, or ask for a full check, to review the whole document. The rules that it checks are in the writing-math skill. Edits to .qmd, .md, .rmd or other files do not call for it unless the user asks."
argument-hint: "[full]"
---

# Readable math

Before declaring a LaTeX document (`.tex`) finished, run this review. It does not apply to `.qmd`, `.md`, `.rmd` or `.markdown` files unless the user asks for it.

The review checks text against the rules of the `writing-math` skill, which you loaded before your first edit. It has two parts, and they run at the same time:

- The **readability review** covers notation, scope and glosses. One `stats-research:math-readability-reviewer` agent (Sonnet, high effort) reviews each document.
- The **correctness review** covers proofs and derivations: whether each step is true, and whether a reader can follow it. One `stats-research:math-correctness-reviewer` agent (Opus, high effort) reviews each group of arguments that you choose.

The reviewers read the whole document every time, so they can find a definition, a clash or a cited result anywhere. What they review depends on the scope:

- **Changes**, the default, reviews the text that changed since the last review. After a small edit that is a few paragraphs, so the review is quick.
- **Full** reviews the whole document. Use it when this skill's arguments say `full`, or when the user asks for a full or whole-document check. It is slow on a long paper, so do not choose it on your own.

Arguments: $ARGUMENTS

## Procedure

1. **Get the change report.** Pass the `.tex` files that you edited, or the paper's root file or folder:

   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/tex_changes.py" report <files>
   ```

   Add `--full` for a full review. The script finds each document's root file and every file that the root inputs, in reading order. It compares them with the copy saved at the last review, or with the last git commit when no review is saved yet. It prints the files to read, the regions to review, the statements and equations that changed with the places that cite them, and the deleted text, and it saves the report. Changes to comments and to spacing do not count. When it prints "No changes since then", the review is done.

2. **Group the arguments for the correctness review.** An argument is a proof, or a derivation that ends in a displayed result. It is in scope when it overlaps a region, or when it cites a statement or equation that the report lists as changed. In a full review every argument is in scope. Read the regions, then put the arguments in scope into groups:

   - Give major proofs of different claims separate groups. Reasoning takes most of the time there, so separate agents finish sooner.
   - Put small arguments that are closely related into one group, such as a lemma and the one proof that uses it, or a few short derivations about the same quantity. They share context, so one agent is cheaper.
   - In a paper with the tex-hygiene layout, each `theory/<slug>.tex` file holds one result and its proof, so it is a natural unit.
   - Use at most four groups in a round, or at most eight in a full review. When you have more, merge the smallest groups that are related.

   For each group, write its assignment: each argument's `FILE:FIRST-LAST` and a short phrase for what it proves. When no argument is in scope, skip the correctness review.

3. **Dispatch every reviewer in one message**, so that they run at the same time. The report path is on the report's "Saved report" line.

   - Readability, one for each document in the report: `subagent_type` `stats-research:math-readability-reviewer`, with the prompt `Follow ${CLAUDE_SKILL_DIR}/references/readability-review.md. The rules are in ${CLAUDE_PLUGIN_ROOT}/skills/writing-math/SKILL.md. The change report is <report path>.`
   - Correctness, one for each group: `subagent_type` `stats-research:math-correctness-reviewer`, with the prompt `Follow ${CLAUDE_SKILL_DIR}/references/correctness-review.md. The rules are in ${CLAUDE_PLUGIN_ROOT}/skills/writing-math/SKILL.md. The change report is <report path>. Your arguments:` and then the group's assignment.

   If these agent types are not available, use `general-purpose` with the same prompts, pass `model: sonnet` for readability and `model: opus` for correctness, and add "Do not edit any file." to each prompt. Add nothing else to the prompts. **Do not list the symbols that should be defined, or tell the reviewers what to find in any other way.** They must find every definition in the files themselves.

4. **Mark the review** as soon as every reviewer has reported, before you fix anything:

   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/tex_changes.py" mark <same files>
   ```

   This records the text that the reviewers read. Your fixes then count as new text, so the next report holds only the passages that you fixed.

5. **Fix the correctness findings first**, then the readability findings, so that the text follows the writing-math rules. A proof that you rewrite for correctness can make its readability findings moot. When a finding shows that a claim is false as stated, do not change the claim on your own: tell the user what the reviewer found, and propose a correction. Change only the regions and the text that the findings name, unless this is a full review.

6. **Check the fixes.** Run the review again. The report now holds only your fixes, so this round is short.

   - Send an argument back to the correctness review only when its mathematics changed.
   - When every readability fix only adds words around existing notation, such as a gloss, a definition sentence or a scope phrase, skip the readability review.
   - When no reviewer is needed, run `report` and then `mark` without dispatching.

   Re-render when a round finds nothing to fix, or after you skip one this way.

## When to skip

- Files that are not `.tex`, such as `.qmd`, `.md` and `.rmd` documents, unless the user asks for the review.
- Pure code edits (no narrative changes).
- Trivial typo or whitespace fixes. They stay unreviewed until the next report, which is fine.
- `.tex` files with no mathematical prose, such as a preamble of macro definitions. This is a judgment call.

## Notes

- The saved copies and the last report live in the repository's git directory, under `readable-math/`, so nothing is committed or pushed to Overleaf. Outside git they live in `~/.cache/readable-math/`.
- Coauthors' edits pulled from Overleaf count as new text, so the next report includes them.
- A file that no root file reads, such as a standalone note, is reviewed as a document of its own.
- After a large reorganization, run a full review to start from a clean record.
- The two agent files in the plugin's `agents/` folder set each reviewer's model and effort.
