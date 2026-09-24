# Generated files. Please do not edit these.

Everything in this directory is produced by the analysis code in the project's
code repository. The files arrive here through a build, and the next build
overwrites them.

Editing a figure or a number here does not change the analysis. It makes the
paper disagree with the code that is supposed to support it, quietly, and the
disagreement usually surfaces much later, when someone asks where a number came
from and the answer no longer exists.

The same goes for uploading a replacement figure through the Overleaf file
menu. The tooling notices (it compares each file against the hash recorded when
it was built, and reports the mismatch as "drifted"), but noticing after the
fact is a poor substitute for the number being right.

## If something here is wrong

Tell whoever maintains the code repository, or open an issue there. A wrong
number here is a bug in the analysis, and fixing it at the source fixes it
everywhere it appears.

## What the files are

- `figures/` and `tables/` are included by the manuscript directly.
- `numbers/` holds the inline numbers, one file per computation. Each line
  defines a macro, so the text says `\resPrimaryAte` and the value lives here.
- `artefacts.tex` pulls in every numbers file. The manuscript inputs it once.
- `BUILD.json` records which commit of the analysis code produced each file,
  along with its content hash. Checking out any commit of this paper tells you
  what produced the version you are looking at.

Macros beginning `\res` are manuscript numbers and macros beginning `\wip` are
exploratory. That is a naming habit rather than a rule the tools enforce: what
decides which guarantee a number carries is the directory it was written to,
which `BUILD.json` records. Exploratory numbers live under `notes/` and the
manuscript never pulls them in.
