---
name: writing-math
description: "Rules for writing mathematics in a LaTeX (.tex) document: how to define, scope, reuse and gloss symbols, and how to write derivations that a reader can follow and check. Load it before you write or edit mathematics in any .tex file, in the main conversation or in a subagent. The readable-math review checks new text against these same rules."
---

# Writing math

These rules apply to every `.tex` document that you write or edit. After you edit, the `readable-math` review checks the new text against them. Text that follows them from the start comes back with fewer findings.

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

Derivations should be prolix. The user can always shorten them once the logic is clear.

- **One move per step.** Between two consecutive displays, make at most one elementary algebraic move, such as a substitution, a factoring, an add-and-subtract trick or a simplification, unless a sentence names each move. For example, a derivation fails this rule when the prose says "Subtract $\mu_0(1)$ from $E[(Y^*)^2]$" but the displays show only the result, which silently uses an add-and-subtract trick to expose the variance.
- **Justify each "trust me" phrase.** Words such as *clearly*, *obviously*, *it follows*, *after some algebra*, *we obtain*, *X to isolate Y* (when the isolating is not shown), *achieved at*, *binds at* and *gives* often hide steps. Use one only when the text around it justifies the claim.
- **Show optimizations and bounds in full.** When a derivation maximizes, minimizes or bounds something, such as a variance or a minimum detectable effect, write all of these: the objective as a function of the free variables; the feasible region of those variables; the reason for the direction of monotonicity, such as the sign of a partial derivative; the location of the optimum, derived and not asserted; and each case of any case split, such as $\min(1, \mu/h)$ resolving to $\mu/h$ or to one.
- **Write for a reader who does not know the answer.** A reader who does not know where a derivation is heading should never have to guess which move happened at a step.

## Correctness

- Check each algebraic step before you write it down. When a step is not obvious, verify it with `sympy` or with a numerical check in `python3`.
- When you cite a result, check that its conditions hold where you use it.
- State the conditions and quantifiers of every claim: the values for which it holds, and the sense in which it holds, for example exactly, asymptotically or with high probability.
