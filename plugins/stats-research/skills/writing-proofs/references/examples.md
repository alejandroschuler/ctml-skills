# Examples

Contents:

- A statement, before and after the statement rules
- A proof in prose, with a plan and the facts that each step uses
- The same proof in numbered steps

Both examples are about the cross-fit AIPW estimator $\hat\psi$ of a mean outcome $\psi$, with propensity score $\pi$, outcome regression $\mu$, and efficient influence function $\varphi$.

## A statement

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
Suppose that the outcome $Y$ is bounded, that the propensity score $\pi$ and its estimate $\hat\pi$ are bounded away from 0, and that the nuisance estimators $\hat\pi$ and $\hat\mu$ are consistent in $L_2(P)$.
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
- The proof uses only the lower bound on the propensity score, so the upper bound is gone.
- The remark about the bound on $Y$ moved to the paragraph after the statement.
- The "If, in addition" sentence became a corollary. Its Assume sentence also holds the regularity condition $\sigma^2 > 0$ that the coverage needs.

## A proof in prose

This proof is for the theorem above, in a paper where its three regularity conditions are labelled (Bounded outcome), (Overlap) and (Consistency) in an assumption before the theorem. \cref{lem:split} is the sample-splitting lemma, and \eqref{eq:von-mises} is the von Mises expansion.

```latex
\begin{proof}
The plan is to write $\hat\psi - \psi$ as a sample average of $\varphi$ plus two remainders, and to show that both remainders are $o_P(n^{-1/2})$.
The second remainder is where the rate condition enters, and it is the key step.
In this proof, let $\epsilon > 0$ be the bound in (Overlap).

By the definition of $\hat\psi$ and the von Mises expansion \eqref{eq:von-mises},
\[
  \hat\psi - \psi = (P_n - P)\varphi + (P_n - P)(\hat\varphi - \varphi) + R_2.
\]
By (Bounded outcome), (Overlap) and (Consistency), $\|\hat\varphi - \varphi\|_{L_2(P)} = o_P(1)$, so \cref{lem:split} gives $(P_n - P)(\hat\varphi - \varphi) = o_P(n^{-1/2})$.
By the Cauchy--Schwarz inequality and (Overlap),
\[
  |R_2| \le \epsilon^{-1} \, \|\hat\pi - \pi\|_{L_2(P)} \, \|\hat\mu - \mu\|_{L_2(P)},
\]
which is $o_P(n^{-1/2})$ by the rate condition.
Hence $\sqrt{n}(\hat\psi - \psi) = \sqrt{n}(P_n - P)\varphi + o_P(1)$.
(Bounded outcome) and (Overlap) make $\sigma^2$ finite, so the central limit theorem gives the result.
\end{proof}
```

## The same proof in numbered steps

This is the form for an appendix proof longer than about a page, or for a proof in a note. This proof is short, so here it only shows the form.

```latex
\begin{proof}
The idea is to write $\hat\psi - \psi$ as a sample average of $\varphi$ plus two remainders that are $o_P(n^{-1/2})$.
Step~\ref{step:remainder} is the key step: it is where the rate condition enters.
In this proof, let $\epsilon > 0$ be the bound in (Overlap).
\begin{enumerate}
\item \label{step:expand}
  $\hat\psi - \psi = (P_n - P)\varphi + (P_n - P)(\hat\varphi - \varphi) + R_2$.

  \emph{Proof:} the definition of $\hat\psi$ and the von Mises expansion \eqref{eq:von-mises}.
\item \label{step:ep}
  $(P_n - P)(\hat\varphi - \varphi) = o_P(n^{-1/2})$.
  \begin{enumerate}
  \item \label{step:phi}
    $\|\hat\varphi - \varphi\|_{L_2(P)} = o_P(1)$.

    \emph{Proof:} (Bounded outcome), (Overlap) and (Consistency).
  \item The claim of step~\ref{step:ep} holds.

    \emph{Proof:} step~\ref{step:phi} and \cref{lem:split}.
  \end{enumerate}
\item \label{step:remainder}
  $R_2 = o_P(n^{-1/2})$.

  \emph{Proof:} by the Cauchy--Schwarz inequality and (Overlap), $|R_2| \le \epsilon^{-1} \|\hat\pi - \pi\|_{L_2(P)} \|\hat\mu - \mu\|_{L_2(P)}$, which is $o_P(n^{-1/2})$ by the rate condition.
\item The theorem holds.

  \emph{Proof:} steps~\ref{step:expand} to~\ref{step:remainder} give $\sqrt{n}(\hat\psi - \psi) = \sqrt{n}(P_n - P)\varphi + o_P(1)$.
  (Bounded outcome) and (Overlap) make $\sigma^2$ finite, so the central limit theorem gives the result.
\end{enumerate}
\end{proof}
```

The steps are cited with a plain `\ref`, because `\cref` names a list item "item".

Read alone, the claims of steps 1 to 4 give the plan. Each proof under a step names the conditions, steps and lemmas that it uses, so a reader can check that every condition of the theorem is used.
