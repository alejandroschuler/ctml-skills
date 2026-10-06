---
name: writing-math
description: "Rules for writing mathematics in a LaTeX (.tex) document: how to define, scope, reuse and gloss symbols, and how densely to write proofs and derivations, in paper mode for the main text of a draft or in note mode for a note that the author works through, and how to lay out the source with one sentence per line. Load it before you write or edit mathematics in any .tex file, in the main conversation or in a subagent. The readable-math review checks the symbol rules and the correctness of the mathematics afterward. Nothing checks the density rules later, so they apply as you write."
---

# Writing math

These rules apply to every `.tex` document that you write or edit. After you edit, the `readable-math` review checks the symbol rules and whether the mathematics is correct. Text that follows the rules from the start comes back with fewer findings. No reviewer checks how densely you write a derivation, so follow the mode rules below as you write.

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

## Derivations

How many steps a proof or a derivation shows depends on the mode of the document. The symbol rules above apply in both modes.

### The mode

- **Paper** mode is for the main text of a draft, which readers in a field will read.
- **Note** mode is for a note outside the main text, in which the author develops or learns an idea, often with Claude's help. A document in a `notes/` folder, or a standalone document that the paper does not input, is usually a note.

The mode and the field go on a comment line near the top of the document's root file:

```latex
% writing-math: paper, asymptotic statistics
% writing-math: note, probability theory
```

The field tells you what the readers already know. When the root file has no such line, choose the mode and the field from the place and the content of the document, add the line, and tell the user what you chose, so that they can change it.

### Paper mode

Write with the density of a paper in the field that the mode line names, which is the density that its readers and referees expect.

- You can name a standard argument of the field in place of writing it out, when readers of that field accept the name. In a probability theory paper, "this follows from a generating class argument" is enough. In an asymptotic statistics paper, the same sentence may not be enough, and the main steps belong in the text.
- A chain of algebra needs no comment when each step only rearranges or simplifies, or when a reader can check it easily.
- A step that uses a trick, such as adding and subtracting a term, a bound that is not standard, or a change of measure, gets a phrase that names the trick.

### Note mode

Spell the mathematics out. The reader is the author, who is working the idea out.

- State briefly every theorem that the note uses, with its conditions, unless it is among the most common results of the field, such as the central limit theorem in statistics or dominated convergence in probability. Check the conditions where the note applies the theorem.
- Between two consecutive lines of a derivation, make at most two or three elementary moves. You can condense a long chain of algebra a little, but no line may jump further than that.
- Name each trick, such as an add-and-subtract step, and say what it is for. For example, a derivation fails this rule when the prose says "Subtract $\mu_0(1)$ from $E[(Y^*)^2]$" but the displays show only the result, which silently uses an add-and-subtract trick to expose the variance.
- Justify each "trust me" phrase. Words such as *clearly*, *obviously*, *it follows*, *after some algebra*, *we obtain*, *X to isolate Y* (when the isolating is not shown), *achieved at*, *binds at* and *gives* often hide steps. Use one only when the text around it shows why.
- When a derivation maximizes, minimizes or bounds something, such as a variance or a minimum detectable effect, write all of these: the objective as a function of the free variables; the feasible region of those variables; the reason for the direction of monotonicity, such as the sign of a partial derivative; the location of the optimum, derived and not asserted; and each case of any case split, such as $\min(1, \mu/h)$ resolving to $\mu/h$ or to one.
- Write for a reader who does not know where the derivation is heading. That reader should never have to guess which move happened at a step.

## Correctness

- Check each algebraic step before you write it down. When a step is not obvious, verify it with `sympy` or with a numerical check in `python3`.
- When you cite a result, check that its conditions hold where you use it.
- State the conditions and quantifiers of every claim: the values for which it holds, and the sense in which it holds, for example exactly, asymptotically or with high probability.

## One sentence per line

In every `.tex` document, in paper mode and in note mode, put each sentence of prose on its own line. Do not wrap lines at a fixed width, and do not put a whole paragraph on one line. LaTeX prints a line break inside a paragraph as a space, so the output does not change. The author can then point at a sentence by its line number, and a diff shows the sentence that changed, not its whole paragraph.

- The rule is for each sentence that LaTeX prints, also in statements, proofs, captions and footnotes. It is not for comments.
- A display equation breaks its sentence. The text after the display starts on a new line.
- When you edit a paragraph that has another style, re-break all of that paragraph. Do not re-break paragraphs that you do not otherwise change, because a coauthor may be editing them.
