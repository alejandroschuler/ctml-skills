---
name: readable-math
description: "Verify the mathematical content of a LaTeX document is readable. This means every symbol, abbreviation, or domain-specific term is defined at or before its first use, parsimonious, and unambiguous, and every derivation step follows clearly from the previous one. Invoke after editing any LaTeX (.tex) document, before declaring the task done. By default it audits only the text that changed since its last check; pass full, or ask for a full check, to audit the whole document. Edits to .qmd, .md, .rmd or other files do not call for it unless the user asks."
argument-hint: "[full]"
---

# Readable math

Before declaring a LaTeX document (`.tex`) finished, run this check. It does not apply to `.qmd`, `.md`, `.rmd` or `.markdown` files unless the user asks for it.

The checkers read the whole document every time, so they can find a definition or a clash anywhere. What they audit depends on the scope:

- **Changes**, the default, audits the text that changed since the last check. After a small edit that is a few paragraphs, so the check is quick.
- **Full** audits the whole document. Use it when this skill's arguments say `full`, or when the user asks for a full or whole-document check. It is slow on a long paper, so do not choose it on your own.

Arguments: $ARGUMENTS

## Procedure

1. **Get the change report.** Pass the `.tex` files that you edited, or the paper's root file or folder:

   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/tex_changes.py" report <files>
   ```

   Add `--full` for a full check. The script finds each document's root file and every file that the root inputs, in reading order. It compares them with the copy saved at the last check, or with the last git commit when no check is saved yet. It prints the files to read, the regions to audit and the deleted text, and it saves the report. Changes to comments and to spacing do not count. When it prints "No changes since then", the check is done.

2. **Dispatch the two checkers in one message**, so that they run at the same time. For each document in the report, start one notation checker and one derivation checker with the Agent tool:

   - `subagent_type`: `stats-research:readable-math-checker`, which has no tool for editing files. If that type is not available, use `general-purpose` and add "Do not edit any file." to each prompt.
   - Notation prompt: `Follow ${CLAUDE_SKILL_DIR}/references/notation-check.md. The change report is <report path>.`
   - Derivation prompt: `Follow ${CLAUDE_SKILL_DIR}/references/derivation-check.md. The change report is <report path>.`

   The report path is on the report's "Saved report" line. Add nothing else to the prompts. **Do not list the symbols that should be defined, or tell the checkers what to find in any other way.** They must find every definition in the files themselves.

3. **Mark the check** as soon as both checkers have reported, before you fix anything:

   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/tex_changes.py" mark <same files>
   ```

   This records the text that the checkers read. Your fixes then count as new text, so the next report holds only the passages that you fixed.

4. **Plan the revision** from both lists. Think about:
   - changing any notation that is not internally consistent or gets redefined.
   - removing symbols that are redundant or not needed, such as a symbol used only once, and removing unnecessary sub- and superscripts.
   - removing decorative subscripts or modifiers that do not tell the symbol apart from any other symbol in the document. For example, `h_med` in a document with no other `h` is over-decorated, so use `h`.
   - upgrading contextual definitions to formal ones (a `let X := ...` line, an explicit "X denotes ..." clause, or a row of a notation table), especially for symbols used in equations.
   - fixing each use before definition by adding a definition at the first use.
   - wrapping each naked use in a noun-phrase gloss in the same sentence, so that the reader never has to scroll back to recall what a symbol stands for. For example, "the bias in $\mu(x)$" becomes "the bias in the conditional mean $\mu(x)$".
   - fixing each ripple finding, where a deleted definition or a changed notation broke text elsewhere.
   - writing out the missing derivation steps. Derivations should be prolix, because the user can always edit them down once they understand the logic.

5. **Implement the plan.** Change only the regions and the text that the ripple findings name. In a full check, the whole document is open to change.

6. **Check the fixes.** Run the procedure again. The report now holds only your fixes, so this round is short. When every fix only adds words around notation that is already there, such as a gloss or a definition sentence, you can skip the checkers: run `report` and then `mark`. Re-render when a round finds nothing to fix, or after you skip one this way.

## When to skip

- Files that are not `.tex`, such as `.qmd`, `.md` and `.rmd` documents, unless the user asks for the check.
- Pure code edits (no narrative changes).
- Trivial typo or whitespace fixes. They stay unchecked until the next report, which is fine.
- `.tex` files with no mathematical prose, such as a preamble of macro definitions. This is a judgment call.

## Notes

- The saved copies and the last report live in the repository's git directory, under `readable-math/`, so nothing is committed or pushed to Overleaf. Outside git they live in `~/.cache/readable-math/`.
- Coauthors' edits pulled from Overleaf count as new text, so the next report includes them.
- A file that no root file reads, such as a standalone note, is checked as a document of its own.
- After a large reorganization, run a full check to start from a clean record.
