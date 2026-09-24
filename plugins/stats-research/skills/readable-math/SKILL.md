---
name: readable-math
description: Verify the mathematical content of a human-facing document is readable — every symbol, abbreviation, or domain-specific term is defined at or before its first use, parsimonious, and unambiguous; every derivation step follows clearly from the previous. Invoke after editing any qmd, LaTeX, or human-facing markdown document, before declaring the task done.
---

# Readable math

Before declaring any human-facing doc (`.qmd`, `.tex`, `.md`, `.rmd`, `.markdown` — anything a human reads top-to-bottom) finished, run this check.

## Procedure

### Notation Check

1. Identify the file(s) edited in this turn that are human-facing docs.
2. For each, dispatch an Explore subagent with this prompt. **Do not enumerate the Notation table, list expected symbols, or otherwise pre-tell the subagent what should be defined** — the subagent must discover all definitions by reading the file itself.

   > Read this document top-to-bottom: `<absolute path>`. List every mathematical symbol, abbreviation, or domain-specific term and the line where it is *first used*. For each, say whether it has been defined at or before that line, classify *how* it is defined, and judge whether the chosen notation is useful, parsimonious, and unambiguous. Be terse — output one line per symbol, in the form `LINE: SYMBOL — first used on line X, defined on line Y (kind: formal | contextual | not defined), parsimony: minimal | over-decorated (e.g. could drop subscript Z — no other Z in doc), ambiguous: conflicts with previous symbol XXX`. *Formal* = a `let X := ...` line, an explicit "X denotes ..." clause, or a Notation-table row. *Contextual* = meaning only inferable from surrounding prose. Do not trust any priming in this dispatch about what *should* be defined — rely only on what *is* defined in the file; if a definition is asserted but you cannot locate it, treat the symbol as undefined.
   >
   > **Naked-symbol check.** Additionally, scan every inline (non-display, prose) use of a content-bearing symbol *after* its first introduction, and flag any use that is "naked" — referenced without a brief noun-phrase reminder of what it means in the same sentence. The reader should never have to scroll back to recall what a symbol stands for. Output one line per offending use, in the form `LINE: SYMBOL — naked use in: "<offending clause>"; suggested fix: "<gloss + symbol rewrite>"`.
   >
   > Scoping rules for the naked-symbol check:
   >
   > - **Flag** content-bearing symbols: estimands and parameters (e.g. $\tau$, $\pi$, $\theta$), nuisance functions and conditional means (e.g. $m_C$, $p(X)$, $\mu(x)$, $\sigma^2(x)$), derived/defined quantities ($\Delta Y$, $\hat\phi_i$), model-specific objects.
   > - **Do not flag** structural/index symbols ($i$, $t$, $k$, $n$, $K$) or generic universal letters defined once near the top of the document ($X$ for covariates, $Y$ for outcome) when used in routine ways.
   > - **Do not flag** if the symbol was glossed in the immediately preceding sentence or clause (recency exemption).
   > - **Do not flag** symbol uses *inside* display equations or fenced math blocks. The gloss requirement is for inline prose only.
   >
   > Example: "substantial nonlinearity in $\mu(x)$ introduces bias" is naked. Fix: "substantial nonlinearity in the conditional mean $\mu(x)$ introduces bias." The pattern is gloss-then-symbol (or symbol-then-comma-then-gloss), in the same sentence as the symbol use.

3. Review the list line by line and make a plan to revise the document. Think about:
   - changing any notation that is not internally consistent or gets redefined.
   - entirely removing symbols that are redundant or not entirely necessary (eg get used only once) Remove any unecessary sub or superscripts. 
   - removing decorative subscripts or modifiers that don't disambiguate from any other symbol in the document. Example: `h_med` in a doc with no other `h` is over-decorated — just use `h`.
   - upgrading contextual definitions to formal ones (a `let X := ...` line, an explicit "X denotes ..." clause, or a Notation-table row), especially for symbols used in equations.
   - Fix any use-before-definition violations by adding a definition inline at first use.
   - Wrapping every flagged naked-symbol use in a noun-phrase gloss in the same sentence (pattern: "the [meaning] $\text{symbol}$ ..."). The point is that the reader should not have to scroll back to recall what a symbol stands for. Example fix: "the bias in $\mu(x)$" → "the bias in the conditional mean $\mu(x)$".
4. Implement the plan and revise the document accordingly.
5. Re-render only after the check passes: all symbols must be deemed useful, unambiguous, and well-defined at or before their first use.

### Derivation Check

1. For each mathematical derivation in the edited file(s), dispatch an Explore subagent with this prompt:

   > Read this document top-to-bottom: `<absolute path>`. For each mathematical derivation, verify that every step follows from the previous one. Apply these specific checks:
   >
   > **(a) Step-density.** Flag any pair of consecutive display equations where more than one elementary algebraic move (substitution, factoring, add-and-subtract trick, simplification, etc.) occurs between them without a sentence bridging the moves. Example failure: the prose says "Subtract $\mu_0(1)$ from $E[(Y^*)^2]$" but the displayed equations only show the post-subtraction result, silently using an add-and-subtract trick to expose the variance.
   >
   > **(b) "Trust me" markers.** Flag uses of phrases that commonly hide steps: *clearly*, *obviously*, *it follows*, *after some algebra*, *we obtain*, *X to isolate Y* (without the isolating actually shown), *achieved at*, *binds at*, *gives*. These are not banned — they are prompts to verify that the surrounding text actually justifies the claim.
   >
   > **(c) Optimization-and-bound template.** When a derivation maximises, minimises, or bounds something (a variance, a minimum detectable effect, etc.), explicitly check that the text contains: (i) the objective written as a function of the free variables, (ii) the feasibility region of those variables, (iii) reasoning for the monotonicity direction (e.g. sign of a partial derivative or an analogous argument), (iv) the location of the optimum *derived* rather than asserted, and (v) any case-split (e.g. $\min(1, \mu/h)$ resolving to $\mu/h$ vs $1$) spelled out for each branch.
   >
   > **(d) Reader-simulation.** Try to follow each derivation step-by-step assuming no prior knowledge of where it is heading. At each step, if you have to guess which algebraic move happened, flag the gap — even if the move is "obvious" once the answer is known. This is a semantic check, complementary to the lexical heuristics in (a) and (b).
   >
   > If any step is not immediately clear, write out the missing steps or justify the leap in logic. Output a structured list of your comments. Each should include the specific line number, which check flagged it (a / b / c / d / general), your judgement on whether it is clear, and if not, the additional steps or justification needed.
   
2. Reivew this list and correct the derivations. Derivations should be prolix: the user can always edit them down later once they understand the logic.

## When to skip

- Pure code edits (no narrative changes).
- Trivial typo or whitespace fixes.
- Files that are not human-facing (READMEs in non-research projects, internal config, etc.) — judgment call.
