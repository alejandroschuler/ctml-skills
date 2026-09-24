# Promotion and recovery

The branch and commit rules exist so that "which code produced this number"
always has an answer. The rules themselves are in the project rules, in the
project's `CLAUDE.md`. This file has the procedures that follow from them.

Every artefact carries a stamp: the commit of the code repo that it was built
from, recorded in `BUILD.json` when the file was written.

## Where work goes

Exploratory work happens on `wip/<topic>`, never on `main`. The instinct that
junk commits are bad comes from shared mainline history, and it does not apply
to a private exploration branch: forty commits in an afternoon cost nothing,
they squash away at promotion, and each one is a state you can return to.
`make notes` commits for you, so the cost is zero keystrokes.

Names like `wip/overlap-diagnostics` are a convention for legibility. The notes
tier accepts any branch except `main`. It refuses a detached HEAD, which is
where you are during a rebase or a bisect: git reports the branch there as the
literal string `HEAD`, and committing onto it would put the work somewhere that
becomes unreachable the moment anything else is checked out.

Ask before creating a branch only when the fork point is unclear, which in
practice means the new work might need an unmerged branch's code.

## Nothing is built from a dirty tree

The guard, `tools/build_guard.py`, checks the branch and the code tree before a
build. It runs from the `make build` and `make notes` targets, and again from
the Snakefile's `onstart`, so a bare `snakemake` meets it too. The emit helpers
then check the same conditions at each write. On a wip branch the guard
commits whatever is pending. On `main` it refuses, because `main` is the
branch the paper-tier invariant trusts, and a commit there needs a message
that says what changed.

Auto-commit refuses two kinds of file outright: files over the size limit in
`.artefacts.toml`, and files matching credential patterns. Both would otherwise
be swept in by `git add -A` and become permanent. Keep expensive output under
`results/`, which is gitignored.

## The two invariants

For the paper tier, `git merge-base --is-ancestor <stamp> main` holds for
every artefact. This is stronger than asking whether the tree was clean at
build time, because it also catches an artefact built from a clean tree on a
branch that was later abandoned. That artefact looks perfect and cannot be
reproduced. This is the ancestry check.

For the notes tier, the stamp resolves to a commit that some branch or tag
still contains. This is weaker on purpose. Exploration is allowed to be messy;
it is not allowed to be unrecoverable. This is the reachability check.

`make check` runs both.

## Promotion

A notes artefact becomes a paper artefact in this order:

1. On the wip branch, move the artefact from its `NOTES_` list to the matching
   paper list in the Snakefile. Change its rule's output from `{NOTES}` to
   `{ART}`, the Snakefile's names for `paper/notes/artefacts` and
   `paper/artefacts`. Rename its macros from `\wip...` to `\res...`. Renaming
   makes you reread each sentence whose claim now rests on the number.
2. Delete the old notes copy under `paper/notes/artefacts/`. It is build
   output, and the paper repo's history keeps it.
3. Squash-merge onto `main`:
   ```
   git switch main
   git merge --squash wip/<topic>
   git commit -m "<what the result is>"
   ```
4. Run `make build` on `main`. The rebuild is the point. Without it, the
   artefact keeps the wip commit as its stamp, and the ancestry check refuses
   it, which is the gate working.
5. Use the artefact in the `.tex` (see `making-artefacts.md`).
6. Run `make pdf` and `make check`.
7. Keep the wip branch, or tag it and delete it:
   `git tag archive/<topic> wip/<topic> && git branch -D wip/<topic>`.
   The squash put none of its commits on `main`, so only the branch or the tag
   keeps the stamps of the older notes artefacts reachable.

Push only when asked. `make push-paper` then sends everything.

## Recovery

### Built on the wrong branch

The ancestry check names the artefact and its stamp. Merge the branch to
`main` and rebuild, or rebuild from `main` if the work is already there. The
emit helpers refuse this write in the first place, so it takes a file that
arrived some other way.

### A stamp that ends in `-dirty`

The code tree changed while the artefact was being made, so no commit
describes the code that produced it. `make check` reports this separately from
an ancestry failure. Commit, then rebuild. Nothing is lost.

### Deleted a wip branch whose notes artefacts are in the paper

The reachability check fails, and names each artefact with its stamp. If that
commit still exists, `git tag archive/<topic> <stamp>` brings it back into
reach. If it does not, the artefacts cannot be reproduced, and the honest move
is to rebuild them from current code or delete them.

### Abandoning a wip line of inquiry

Overleaf holds one branch, so the notes artefacts from the abandoned work are
already in the paper repo's history, and deleting the code branch does not
remove them. Delete that line's notes documents and artefacts from
`paper/notes/` in a normal forward commit, and keep or tag the code branch so
the stamps in that history stay reachable.

### Paper push rejected

`make push-paper` retries both of Overleaf's usual failures: HTTP 500 gets a
larger `http.postBuffer`, and a non-fast-forward gets a rebase onto whatever
the web editor committed. There is no force push, so every repair on that side
is a new commit.

### Code pushed, paper not

`make push-paper` pushes the code first, so a failure at the Overleaf step
leaves the code repo pushed and the paper repo not. Nothing is broken: the
artefacts on disk are correct and stamped, and `make status` is accurate about
them. Run `make push-paper` again. Until it succeeds, coauthors on Overleaf see
the previous figures.

### No upstream for `main`

`make push-paper` warns and carries on. The artefacts are then stamped with
commits that exist only on this machine. Add a remote and push `main` before
the paper goes to anyone else.
