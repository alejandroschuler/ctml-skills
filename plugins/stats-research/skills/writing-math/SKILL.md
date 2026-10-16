---
name: writing-math
description: "Sets the rules for writing mathematics in a LaTeX (.tex) document: how to define, scope, reuse and gloss symbols, and how to lay out the source with one sentence per line. Load it before writing or editing mathematics in any .tex file, in the main conversation or in a subagent, together with the writing-proofs skill, which sets how to state results, how to structure proofs and how densely to write proofs and derivations. The readable-math review checks the symbol rules and the correctness of the mathematics afterward."
---

# Writing math

These rules apply to every `.tex` document that you write or edit. After you edit, the `readable-math` review checks the symbol rules and whether the mathematics is correct.

The rules for arguments are in the `writing-proofs` skill: how to state a result, how to structure a proof, and how densely to write proofs and derivations, with the mode line that sets the density. Follow both skills.

## Symbols

### Define before use

- Define every mathematical symbol, abbreviation and domain-specific term at or before its first use.
- Prefer a formal definition: a `let X := ...` line, an explicit "X denotes ..." clause, or a row of a notation table. A contextual definition, where the reader can only infer the meaning from the prose around it, is not enough for a symbol that appears in an equation.
- When you move or delete a definition, check that every remaining use of the symbol still has a definition at or before it.

### Scope

Every symbol is global or local.

- A **global** symbol is defined without a stated scope. It keeps one meaning for the whole document. No other meaning may use its letter anywhere in the document, including inside a proof, as a summation index, or after "for all".
- A **local** symbol is defined with a stated scope, such as "In this proof, let $t$ be a constant" or "In the rest of this section, $B$ is the design matrix." A scope is a proof, an example, a section or an appendix. A local symbol must not appear outside its scope.
- Another scope may give the letter of a local symbol a new meaning, if the two scopes do not overlap. A letter scoped to a section cannot take a second meaning in a proof inside that section.
- Summation indices, integration variables, and variables after "for all" or "there exists" are local by construction, so they need no scope phrase. They still must not use a letter that has a different global meaning.
- A definition inside a proof needs a scope phrase. Without one, the reader cannot tell a local symbol from a global one.

### Search before you define

Before you introduce a symbol, search the whole document for its letter, including every file that the root file inputs. If the letter has a global meaning, choose another letter. If it has only local meanings, you can reuse it in a new scope that overlaps none of theirs, and you must state that scope.

### Parsimony

- Remove symbols that are redundant, such as a symbol that is used only once.
- Remove decorative sub- and superscripts. A decoration must tell the symbol apart from another symbol, or carry meaning. For example, `h_med` in a document with no other `h` is over-decorated, so write `h`. A subscript $n$ says that a quantity depends on the sample, so a constant must not carry one.
- Keep the notation consistent: one symbol for each object, and one object for each symbol in a given scope.

### Glosses

In prose, give every use of a content-bearing symbol after its first introduction a short noun-phrase reminder of its meaning, in the same sentence. The reader should never have to scroll back to recall what a symbol stands for. Put the gloss before the symbol, or after it and a comma. For example, "substantial nonlinearity in $\mu(x)$ introduces bias" becomes "substantial nonlinearity in the conditional mean $\mu(x)$ introduces bias".

- Content-bearing symbols need glosses. These are estimands and parameters (such as $\tau$, $\pi$ and $\theta$), nuisance functions and conditional means (such as $m_C$, $p(X)$, $\mu(x)$ and $\sigma^2(x)$), derived quantities (such as $\Delta Y$ and $\hat\phi_i$), and model-specific objects.
- Structural and index symbols ($i$, $t$, $k$, $n$, $K$), and generic letters defined once near the top of the document ($X$ for the covariates, $Y$ for the outcome), need no gloss in routine use.
- A symbol that was glossed in the sentence or clause just before needs no second gloss.
- Symbols inside display equations need no gloss. The rule is for prose.

## One sentence per line

In every `.tex` document, in paper mode and in note mode, put each sentence of prose on its own line. Do not wrap lines at a fixed width, and do not put a whole paragraph on one line. LaTeX prints a line break inside a paragraph as a space, so the output does not change. The author can then point at a sentence by its line number, and a diff shows the sentence that changed, not its whole paragraph.

- The rule is for each sentence that LaTeX prints, also in statements, proofs, captions and footnotes. It is not for comments.
- A display equation breaks its sentence. The text after the display starts on a new line.
- When you edit a paragraph that has another style, re-break all of that paragraph. Do not re-break paragraphs that you do not otherwise change, because a coauthor may be editing them.
