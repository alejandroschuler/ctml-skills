---
name: writing-proofs
description: "Sets the rules for writing mathematical arguments: how to state a theorem, proposition, lemma or corollary (the Let, Suppose that, If, Then order, with the regularity conditions apart from the substantive assumptions); how densely to write proofs and derivations, measured against the reference texts on the document's mode line, in paper mode or note mode; when to cite a result and when to restate it in the document's notation; and how to structure a proof, with a plan, the facts that each step uses, lemmas, and numbered steps for long proofs. Use whenever Claude writes, edits or restates a result, a proof or a derivation, in a LaTeX paper, a Quarto or Markdown note, or a chat reply. Load it with the writing-math skill, which has the rules for symbols, before any edit to a .tex file. Nothing checks density later, so the mode rules apply during writing."
---

# Writing proofs

These rules are for mathematical arguments: the statement of a result (a theorem, proposition, lemma or corollary), its proof, and any derivation. They apply in every format: a `.tex` paper, a `.qmd` or `.md` note, and a chat reply. The rules for symbols, and for the layout of `.tex` source, are in the `writing-math` skill. After an edit to a `.tex` file, the `readable-math` review checks the symbols and whether the mathematics is correct. No reviewer checks how densely an argument is written, so follow the mode rules as you write.

## The mode line

Each document has a mode, a field and a list of reference texts. They go on one comment line near the top of the document's root file, the mode line:

```latex
% writing-math: paper, nonparametric statistics; refs: Wainwright 2019, van der Vaart and Wellner 1996
% writing-math: note, probability theory; refs: Durrett 2019
```

In a Quarto or Markdown note, put the same text in an HTML comment at the top of the file, such as `<!-- writing-math: note, causal inference; refs: Hernán and Robins 2020 -->`. The line keeps the name `writing-math` so that older documents still work.

- **Paper** mode is for the main text of a draft, which readers in the field will read.
- **Note** mode is for a note outside the main text, in which the author develops or learns an idea, often with Claude's help. A document in a `notes/` folder, a standalone document that the paper does not input, and a Quarto or Markdown note are usually notes.
- The **reference texts** are two to four books that the readers know well. They set the level of every argument in the document. In note mode, list texts that the author knows well. They are often at a lower level than the texts for a paper in the same field.

When the document has no mode line, or its line names no reference texts, choose them from the place and the content of the document, add the line, and tell the user what you chose, so that they can change it. In a chat reply, use the mode line of the document under discussion, or note mode with the standard graduate texts of the field.

## The level of an argument

Write each step so that a reader who knows the reference texts can check it at sight, as a small problem with clear limits. Every step should be about equally easy to check. Steps need not be equally long: a new or difficult step needs more words than a routine one. The common failures are a basic fact derived in detail and a hard step passed over in a phrase.

- Do not prove a result that is in a reference text. Cite it by name and number, for example "by Bernstein's inequality (Boucheron, Lugosi and Massart, 2013, Theorem 2.10)", and check its conditions where you use it.
- Restate a result that is not in a reference text, such as a result from a paper or from a less standard book. State it as a lemma in the notation and the setting of the document, with its conditions written for the document's objects, and cite the exact theorem in the source. When the source is more general than the document needs, state the special case, and say in a sentence how the source's result gives it. Check the restatement against the source, because conditions are easy to lose when the notation changes. If you do not have the source, ask the user for it.
- A step that the reference texts treat as routine gets a name and not a derivation, for example "by a union bound and Bernstein's inequality". A step that goes beyond them is written out, or becomes a lemma.
- A step that uses a trick, such as adding and subtracting a term, a bound that is not standard, or a change of measure, gets a phrase that names the trick.
- When you leave out part of an argument, say what kind of part it is and how long it is, for example "a routine induction on $k$ gives" or "two applications of the Cauchy–Schwarz inequality give".

## Paper mode

Write with the density of a paper in the field, which is the density that its readers and referees expect.

- You can name a standard argument of the field in place of writing it out, when readers of the reference texts accept the name. In a probability theory paper, "this follows from a generating class argument" is enough. In an asymptotic statistics paper, the same sentence may not be enough, and the main steps belong in the text.
- A chain of algebra needs no comment when each step only rearranges or simplifies, or when a reader can check it easily.
- Write proofs in prose, except an appendix proof longer than about a page, which uses numbered steps.

## Note mode

Spell the mathematics out. The reader is the author, who is working the idea out.

- Between two consecutive lines of a derivation, make at most two or three elementary moves. You can condense a long chain of algebra a little, but no line may jump further than that.
- Name each trick, and say what it is for. For example, a derivation fails this rule when the prose says "Subtract $\mu_0(1)$ from $E[(Y^*)^2]$" but the displays show only the result, which silently uses an add-and-subtract trick to expose the variance.
- Justify each "trust me" phrase. Words such as *clearly*, *obviously*, *it follows*, *after some algebra*, *we obtain*, *X to isolate Y* (when the isolating is not shown), *achieved at*, *binds at* and *gives* often hide steps. Use one only when the text around it shows why.
- When a derivation maximizes, minimizes or bounds something, such as a variance or a minimum detectable effect, write all of these: the objective as a function of the free variables; the feasible region of those variables; the reason for the direction of monotonicity, such as the sign of a partial derivative; the location of the optimum, derived and not asserted; and each case of any case split, such as $\min(1, \mu/h)$ resolving to $\mu/h$ or to one.
- Write each proof as numbered steps. A derivation that is one chain of displays needs no numbers.
- Write for a reader who does not know where the derivation is heading. That reader should never have to guess which move happened at a step.

## Statements

### The form of a statement

Write a statement in four parts, in this order. Leave out a part that has nothing in it.

1. **Let.** Name the objects of the result and give their type. Define here what the document does not define elsewhere. Restate a definition from elsewhere only if it is central to the result. Do not restate definitions that the document uses many times or that are part of the background. Give a symbol that is defined elsewhere a short gloss, and a reference to its definition when that definition is far back, for example "Let $\hat\psi$ be the cross-fit AIPW estimator of \cref{eq:aipw}."
2. **Suppose that.** State the regularity conditions. If each condition takes a full sentence, put each one on its own line, with a label.
3. **If.** State the substantive assumptions.
4. **Then.** State the conclusion.

The Let part names objects and does not impose conditions. "Let $f$ be a Lipschitz function" puts a condition where the reader does not look for one. Write "Let $f \colon \mathbb{R} \to \mathbb{R}$ be a function", and put "$f$ is Lipschitz" in the Suppose part or the If part.

### Regularity conditions and substantive assumptions

A regularity condition is a condition that we are happy to assume and that we expect to hold quite generally. Different proofs of one result often use different regularity conditions. Two tests help:

- **Swap.** If another, similar condition could replace it with no change to the meaning or the use of the result in practice, it is probably a regularity condition. For example, a Donsker condition and sample splitting with consistent nuisance estimators do the same job in many proofs.
- **Remove.** A regularity condition often comes from the proof technique. Without it, the conclusion is usually still true but needs a different proof. Without a substantive assumption, the conclusion fails in cases that the reader cares about.

The substantive assumptions are the conditions on the core objects of the result that the proof really needs. They are the conditions that the document wants the reader to notice and think about.

The split depends on the document. Overlap is a regularity condition in a paper about rate conditions on nuisance estimators, and the substantive assumption in a paper about limited overlap. When the document does not make the split clear, ask the author.

### Shared and grouped conditions

- When two or more results use the same conditions, state the conditions once, as a named assumption before the first of those results. Then write "Suppose that \cref{asm:regularity} holds."
- When several conditions together describe one property, define a name for the property before the result, and use the name in the statement. For example, define a *regular* function before the result, and write "If $f$ is regular, then ...".
- Give conditions descriptive labels, such as (Overlap) or (Bounded outcome), not (A1) to (A7). A reader then knows what a reference to a condition means without looking it up.

### Corollaries and split results

- Do not write "If, in addition, ..., then ...". Write a corollary: "Assume the conditions of \cref{thm:main} hold. If ..., then ...".
- When a result has more than one conclusion, check whether each conclusion needs all the conditions. If not, split the result. If yes, list the conclusions as (a), (b), ... in the Then part.
- Use the kind of result to show its weight: a theorem for a main result of the document, a proposition for a result of less weight, a lemma for a step in a proof, and a corollary for a direct consequence of another result. When you are not sure, call the result a lemma.
- Give each main result a short title, such as `\begin{theorem}[Double robustness]`.

### Display equations

- Display the conclusion, and display a substantive assumption that is a formula. A display draws the reader's eye to what matters.
- Write regularity conditions inline. Display one only when it would otherwise be a very long and complex inline formula.

### What stays out of the statement

- Keep a statement short: fewer than ten lines, and five is better. This limit is flexible. A longer statement is fine when a shorter one would be less clear.
- Put no commentary in a statement: no "without loss of generality", no examples, and no remarks such as "(this holds, for example, when ...)". They go in the paragraph after the statement.
- Put no symbol in a statement that only the proof uses. Define it at the start of the proof.
- A formal statement does not say "under regularity conditions" or "under mild conditions". State the conditions, or refer to the named assumption that holds them.

### Quantifiers and dependence

Say exactly what the result claims:

- what is fixed, and what can change with the sample size $n$;
- the type of convergence: almost surely, in probability or in distribution;
- whether the result holds for each distribution in the model or uniformly over the model;
- what each constant depends on, for example "a constant $C$ that depends only on $\epsilon$ and $M$".

### After the statement

Put a short paragraph directly after the statement. It says what the result means in words, why the substantive assumptions matter, and when the regularity conditions hold or how they could be weakened.

[references/examples.md](references/examples.md) has a statement before and after these rules. Read it the first time you state a result in a session.

## Proofs

- **Plan.** Start a proof that is longer than a few steps with a short plan: its main steps, and the step that holds the main idea.
- **The key step.** The step where the claims become much stronger usually holds the main idea, and errors often occur there. Give it the most detail.
- **Name what each step uses.** Each step names the conditions, earlier steps, lemmas and cited results that it uses: "by (Overlap) and \cref{lem:split}", not "by assumption". Cite a well-known result by its name, such as "by the triangle inequality", and not by a number alone.
- **Status of each claim.** The reader always knows whether a claim is proved here, proved later, cited or assumed. Announce a claim before you prove it ("Next we show that $G$ is abelian"), and do not state it first with "To see this, ..." after it. When a proof defers a claim, say where its proof is.
- **Lemmas.** Make a fact a lemma when a later step uses it, or when its proof needs notation that the rest of the argument does not. Keep that notation inside the lemma's proof. Merge two technical lemmas that are only useful together. When two proofs repeat the same steps, make the common part a lemma. State a lemma for use: its hypotheses should be easy to check where it is applied.
- **The form of the argument.** Announce it: "Seeking a contradiction, suppose that ...", "We consider two cases", "We argue by induction on $k$".
- **Contradiction.** Check each proof by contradiction. If it never uses the assumption that it negates, rewrite it as a direct proof. To prove a contrapositive, prove it directly and say so.
- **The statement and the proof agree.** The proof uses every condition in the statement: remove a condition that it does not use. The proof uses no condition that is outside both the statement and the global setup of the document: add any such condition to the statement.

### Numbered steps

Write a proof as numbered steps in note mode, and in paper mode when it is an appendix proof longer than about a page. Write other proofs in prose, with a plan and with the facts that each step uses.

- Each step is a claim, numbered 1, 2, 3, ..., with a short proof under it that names the facts that it uses.
- A step whose proof needs more detail gets sub-steps 2.1, 2.2, ....
- The last step is the conclusion of the result. Its proof says how the earlier steps give it.
- Read alone, the claims of the top-level steps give the plan of the proof. A sentence or two before the steps can say the idea.
- In LaTeX, use an `enumerate` list, nested for sub-steps, and label each step that another step cites.

[references/examples.md](references/examples.md) has a proof in prose and in numbered steps.

## Correctness

- Check each algebraic step before you write it down. When a step is not obvious, verify it with `sympy` or with a numerical check in `python3`.
- When you cite a result, check that its conditions hold where you use it.
- State the conditions and quantifiers of every claim: the values for which it holds, and the sense in which it holds, for example exactly, asymptotically or with high probability.
