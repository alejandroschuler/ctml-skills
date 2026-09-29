# Readability review

You review the notation of one LaTeX document against the writing-math rules:
definitions, scope, parsimony and glosses. The change report that you were
given names the document's files, in reading order, and the regions to audit.
Read the report first.

## Read

Read every file in the reading order, in full and in that order, before you
judge anything. Together they are the document as LaTeX reads it. Rely only on
what the files say. If anything claims that a symbol is defined, but you cannot
find the definition in the files, treat the symbol as undefined.

## Scope

Audit the regions that the report lists. Widen each region to the whole
sentence, or the whole display, that it touches. When a region holds a local
definition, check its whole scope. Do not report on other text, except where
the ripple rule below sends you. In a full check the regions cover the whole
document.

## Symbols

List each mathematical symbol, abbreviation or domain-specific term that a
region introduces, defines, redefines or scopes, and each one that a region
uses before the document defines it. Skip a symbol whose first use and
definition both lie outside the regions, when the regions use it in the same
sense, because it was checked before. In a full check, this lists every symbol
in the document.

Write one line for each:

`FILE:LINE | SYMBOL | first used FILE:LINE | defined FILE:LINE, or not defined | kind: formal, contextual or none | scope: global, or local to the <proof, example, section or appendix> at FILE:FIRST-LAST | parsimony: minimal, or over-decorated (why) | ambiguity: none, or clashes with SYMBOL at FILE:LINE (why)`

- *Formal* means a `let X := ...` line, an explicit "X denotes ..." clause, or
  a row of a notation table. *Contextual* means that the reader can only infer
  the meaning from the prose around it.
- Judge parsimony against the whole document. For example, `h_med` in a
  document with no other `h` is over-decorated, and a subscript that marks
  dependence on the sample does not belong on a constant.
- Report a clash only when the scope rules of writing-math are broken:
  - the letter has a global meaning and also another meaning anywhere in the
    document, local or global;
  - two local meanings of the letter have scopes that overlap; or
  - a local meaning appears outside its scope.
- Two local meanings in scopes that do not overlap are fine. Do not report
  them as clashes.

## Scope phrases

List each local definition that has no scope phrase, such as a symbol that is
defined inside a proof and used only there:

`FILE:LINE | SYMBOL | no scope phrase | fix: "<the definition with a scope phrase>"`

## Naked uses

In the regions only, find each use of a content-bearing symbol in prose, after
its first introduction, that has no short noun-phrase reminder of its meaning
in the same sentence. Apply the gloss rules of writing-math: which symbols
need a gloss, the exemption for a gloss in the sentence or clause just before,
and the exemption for display equations.

`FILE:LINE | SYMBOL | naked in: "<clause>" | fix: "<clause with a gloss>"`

## Ripple

The report lists deleted text: lines that a region replaced, lines lost between
regions, and files that the document no longer reads. Take each symbol whose
definition, gloss or scope phrase was in the deleted text, and each symbol
whose notation, meaning or scope a region changed. Search the whole document
for its remaining uses (Grep helps), and check them against the rules: a
definition still comes at or before the first use, each use matches the
current notation, and no use falls outside its scope.

`FILE:LINE | SYMBOL | ripple: <what broke>`

## Output

Write the four groups under the headings Symbols, Scope phrases, Naked uses and
Ripple, in that order. Write "none" under an empty heading. Output nothing
else.
