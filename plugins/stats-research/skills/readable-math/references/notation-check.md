# Notation check

You check the notation of one LaTeX document. The change report that you were
given names the document's files, in reading order, and the regions to audit.
Read the report first.

## Read

Read every file in the reading order, in full and in that order, before you
judge anything. Together they are the document as LaTeX reads it. Rely only on
what the files say. If anything claims that a symbol is defined, but you cannot
find the definition in the files, treat the symbol as undefined.

## Scope

Audit the regions that the report lists. Widen each region to the whole
sentence, or the whole display, that it touches. Do not report on text outside
the regions, except where the ripple rule below sends you. In a full check the
regions cover the whole document.

## Symbols

List each mathematical symbol, abbreviation or domain-specific term that a
region introduces, defines or redefines, and each one that a region uses before
the document defines it. Skip a symbol whose first use and definition both lie
outside the regions, when the regions use it in the same sense, because it was
checked before. In a full check, this lists every symbol in the document.

Write one line for each:

`FILE:LINE | SYMBOL | first used FILE:LINE | defined FILE:LINE, or not defined | kind: formal, contextual or none | parsimony: minimal, or over-decorated (why) | ambiguity: none, or clashes with SYMBOL at FILE:LINE`

- *Formal* means a `let X := ...` line, an explicit "X denotes ..." clause, or
  a row of a notation table. *Contextual* means that the reader can only infer
  the meaning from the prose around it.
- Judge parsimony and ambiguity against the whole document, not only the
  regions. For example, `h_med` in a document with no other `h` is
  over-decorated, because the subscript tells it apart from nothing.
- A symbol that means one thing in a region and another thing elsewhere
  clashes, even when each use is defined.

## Naked uses

In the regions only, find each inline (prose) use of a content-bearing symbol,
after its first introduction, that has no short noun-phrase reminder of its
meaning in the same sentence. The reader should never have to scroll back to
recall what a symbol stands for.

`FILE:LINE | SYMBOL | naked in: "<clause>" | fix: "<clause with a gloss>"`

- Flag content-bearing symbols: estimands and parameters (such as $\tau$,
  $\pi$, $\theta$), nuisance functions and conditional means (such as $m_C$,
  $p(X)$, $\mu(x)$, $\sigma^2(x)$), derived quantities (such as $\Delta Y$ and
  $\hat\phi_i$), and model-specific objects.
- Do not flag structural or index symbols ($i$, $t$, $k$, $n$, $K$), or
  generic letters defined once near the top of the document ($X$ for
  covariates, $Y$ for the outcome) in routine use.
- Do not flag a symbol that was glossed in the sentence or clause just before.
- Do not flag uses inside display equations. The gloss rule is for prose.

Example: "substantial nonlinearity in $\mu(x)$ introduces bias" is naked. The
fix is "substantial nonlinearity in the conditional mean $\mu(x)$ introduces
bias". The gloss comes before the symbol, or after it and a comma, in the same
sentence.

## Ripple

The report lists deleted text: lines that a region replaced, lines lost between
regions, and files that the document no longer reads. Take each symbol whose
definition or gloss was in the deleted text, and each symbol whose notation or
meaning a region changed. Search the whole document for its remaining uses
(Grep helps), and check that a definition still comes at or before the first of
them and that each use matches the current notation.

`FILE:LINE | SYMBOL | ripple: <what broke>`

## Output

Write the three groups under the headings Symbols, Naked uses and Ripple, in
that order. Write "none" under an empty heading. Output nothing else.
