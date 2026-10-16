---
name: writing-proofs
description: "Sets the rules for stating a mathematical result (a theorem, proposition, lemma or corollary): the Let, Suppose that, If, Then order; how to tell the regularity conditions from the substantive assumptions that the result is about; when to split off a corollary; what to display; what stays out of the statement; and what goes in the paragraph after it. Use whenever Claude writes, edits or restates the statement of a result, in a LaTeX paper, a Quarto or Markdown note, or a chat reply, including a result quoted from another paper. The rules for symbols and for how densely to write a proof are in the writing-math skill."
---

# Writing proofs

These rules are for the statement of a result: a theorem, proposition, lemma or corollary. They apply in every format: a `.tex` paper, a `.qmd` or `.md` note, and a chat reply. For symbols, and for how densely to write a proof or a derivation, follow the `writing-math` skill.

## The form of a statement

Write a statement in four parts, in this order. Leave out a part that has nothing in it.

1. **Let.** Name the objects of the result and give their type. Define here what the document does not define elsewhere. Restate a definition from elsewhere only if it is central to the result. Do not restate definitions that the document uses many times or that are part of the background. Give a symbol that is defined elsewhere a short gloss, and a reference to its definition when that definition is far back, for example "Let $\hat\psi$ be the cross-fit AIPW estimator of \cref{eq:aipw}."
2. **Suppose that.** State the regularity conditions. If each condition takes a full sentence, put each one on its own line, with a label.
3. **If.** State the substantive assumptions.
4. **Then.** State the conclusion.

The Let part names objects and does not impose conditions. "Let $f$ be a Lipschitz function" puts a condition where the reader does not look for one. Write "Let $f \colon \mathbb{R} \to \mathbb{R}$ be a function", and put "$f$ is Lipschitz" in the Suppose part or the If part.

## Regularity conditions and substantive assumptions

A regularity condition is a condition that we are happy to assume and that we expect to hold quite generally. Different proofs of one result often use different regularity conditions. Two tests help:

- **Swap.** If another, similar condition could replace it with no change to the meaning or the use of the result in practice, it is probably a regularity condition. For example, a Donsker condition and sample splitting with consistent nuisance estimators do the same job in many proofs.
- **Remove.** A regularity condition often comes from the proof technique. Without it, the conclusion is usually still true but needs a different proof. Without a substantive assumption, the conclusion fails in cases that the reader cares about.

The substantive assumptions are the conditions on the core objects of the result that the proof really needs. They are the conditions that the document wants the reader to notice and think about.

The split depends on the document. Overlap is a regularity condition in a paper about rate conditions on nuisance estimators, and the substantive assumption in a paper about limited overlap. When the document does not make the split clear, ask the author.

## Shared and grouped conditions

- When two or more results use the same conditions, state the conditions once, as a named assumption before the first of those results. Then write "Suppose that \cref{asm:regularity} holds."
- When several conditions together describe one property, define a name for the property before the result, and use the name in the statement. For example, define a *regular* function before the result, and write "If $f$ is regular, then ...".
- Give conditions descriptive labels, such as (Overlap) or (Bounded outcome), not (A1) to (A7). A reader then knows what a reference to a condition means without looking it up.

## Corollaries and split results

- Do not write "If, in addition, ..., then ...". Write a corollary: "Assume the conditions of \cref{thm:main} hold. If ..., then ...".
- When a result has more than one conclusion, check whether each conclusion needs all the conditions. If not, split the result. If yes, list the conclusions as (a), (b), ... in the Then part.
- Use the kind of result to show its weight: a theorem for a main result of the document, a proposition for a result of less weight, a lemma for a step in a proof, and a corollary for a direct consequence of another result.
- Give each main result a short title, such as `\begin{theorem}[Double robustness]`.

## Display equations

- Display the conclusion, and display a substantive assumption that is a formula. A display draws the reader's eye to what matters.
- Write regularity conditions inline. Display one only when it would otherwise be a very long and complex inline formula.

## What stays out of the statement

- Keep a statement short: fewer than ten lines, and five is better. This limit is flexible. A longer statement is fine when a shorter one would be less clear.
- Put no commentary in a statement: no "without loss of generality", no examples, and no remarks such as "(this holds, for example, when ...)". They go in the paragraph after the statement.
- Put no symbol in a statement that only the proof uses. Define it at the start of the proof.
- A formal statement does not say "under regularity conditions" or "under mild conditions". State the conditions, or refer to the named assumption that holds them.

## Quantifiers and dependence

Say exactly what the result claims:

- what is fixed, and what can change with the sample size $n$;
- the type of convergence: almost surely, in probability or in distribution;
- whether the result holds for each distribution in the model or uniformly over the model;
- what each constant depends on, for example "a constant $C$ that depends only on $\epsilon$ and $M$".

## After the statement

Put a short paragraph directly after the statement. It says what the result means in words, why the substantive assumptions matter, and when the regularity conditions hold or how they could be weakened.

## The statement and the proof agree

When you write or edit a result or its proof, check two things:

- The proof uses every condition in the statement. Remove a condition that it does not use.
- The proof uses no condition that is outside both the statement and the global setup of the document. Add any such condition to the statement.

## Example

Before:

```latex
\begin{theorem}
Let $\hat\psi$ be the AIPW estimator, with $\hat\mu$ and $\hat\pi$ cross-fit and consistent.
Suppose that $\|\hat\pi - \pi\| \, \|\hat\mu - \mu\| = o_P(n^{-1/2})$, that $|Y| \le M$, and that $\epsilon \le \pi, \hat\pi \le 1 - \epsilon$ for some $\epsilon > 0$.
Then $\sqrt{n}(\hat\psi - \psi) \rightsquigarrow N(0, \sigma^2)$ (the bound on $Y$ can be weakened to a moment condition).
If, in addition, $\hat\sigma^2$ is consistent, the Wald interval has asymptotic coverage $1 - \alpha$.
\end{theorem}
```

After:

```latex
\begin{theorem}[Asymptotic normality of AIPW]
\label{thm:aipw-normal}
Let $\hat\psi$ be the cross-fit AIPW estimator of \cref{eq:aipw}, and let $\sigma^2$ be the variance of the efficient influence function of \cref{eq:eif}.
Suppose that the outcome $Y$ is bounded, that the propensity score $\pi$ and its estimate $\hat\pi$ are bounded away from 0 and 1, and that the nuisance estimators $\hat\pi$ and $\hat\mu$ are consistent in $L_2(P)$.
If
\[
  \|\hat\pi - \pi\|_{L_2(P)} \, \|\hat\mu - \mu\|_{L_2(P)} = o_P(n^{-1/2}),
\]
then
\[
  \sqrt{n}\,(\hat\psi - \psi) \rightsquigarrow N(0, \sigma^2).
\]
\end{theorem}

The product-rate condition is the one that matters: it holds when each nuisance estimator converges faster than $n^{-1/4}$, or when one converges fast enough to make up for the other.
The bound on the outcome can be weakened to a moment condition.

\begin{corollary}
Assume the conditions of \cref{thm:aipw-normal} hold and that $\sigma^2 > 0$.
If $\hat\sigma^2 \to \sigma^2$ in probability, then the Wald interval $\hat\psi \pm z_{1-\alpha/2} \, \hat\sigma / \sqrt{n}$ covers $\psi$ with a probability that tends to $1 - \alpha$.
\end{corollary}
```

What changed:

- The consistency of the nuisance estimators moved from the Let part to the Suppose part.
- The product-rate condition is the substantive assumption, so it moved to the If part, as a display. The bound on the outcome, overlap and consistency are regularity conditions, so they stay inline.
- The conclusion is a display.
- $M$ and $\epsilon$ were each used once, so words replace them.
- The remark about the bound on $Y$ moved to the paragraph after the statement.
- The "If, in addition" sentence became a corollary. Its Assume sentence also holds the regularity condition $\sigma^2 > 0$ that the coverage needs.
