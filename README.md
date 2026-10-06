# ctml-skills

Agent skills for statistical methods research, packaged as a Claude Code plugin marketplace. They cover designing and reporting simulation studies, setting up and tuning supervised learners, writing and reviewing the mathematics of LaTeX papers, keeping a paper's figures and numbers in step with the code that made them, reading the comments that coauthors leave on Overleaf, and keeping each theorem, each TikZ figure and each section of a paper in a file of its own, with one sentence on each line.

## What is here

| Plugin | Skills | Use it for |
|---|---|---|
| `stats-research` | `design-and-report-simulations`, `supervised-learning`, `writing-math`, `readable-math` | Planning a simulation study backwards from its claims, building the code so any piece can rerun alone and expensive fits are cached, choosing and tuning learners (including the check that each tuning grid is wide enough), and writing and reviewing the mathematics of a LaTeX document, so that every symbol is defined and scoped and every proof is correct and can be followed. |
| `paper-pipeline` | `reproducible-paper-artefacts` | Keeping a code repo and its Overleaf manuscript in step, so every figure, table and inline number is built by the pipeline and stamped with the commit that made it. |
| `overleaf-tools` | `overleaf-comments`, `tex-hygiene` | Reading the review comments and tracked changes on an Overleaf project, which the git bridge does not carry. Keeping each theorem with its proof in `theory/<slug>.tex`, with the proof printed in the appendix by itself, and each TikZ figure in `tikz/<slug>.tex`. Keeping each section in a numbered file such as `sections/20-setup.tex`, so that the folder reads as the table of contents, splitting a file of text into a folder of numbered parts when it grows past about 200 lines, and putting each sentence on its own line, so that agents can work on a paper in parallel and merge cleanly. Stopping Claude from reading or editing a clone that is behind Overleaf. |
| `claude-code-utils` | `move-claude-project` | Keeping a Claude Code project's session history when its folder is moved or renamed. |

The skills in `stats-research` refer to each other. The simulation skill sends learner setup to `supervised-learning` and finished LaTeX prose to `readable-math`, so install that plugin whole.

`stats-research` also installs two hooks. Before the first edit to a `.tex` file in a conversation or a subagent, one hook makes Claude load `writing-math`. After each edit to a `.tex` file, the other reminds Claude to run `readable-math` before the task is done. The hooks need `python3` on your `PATH`. If you had a readable-math reminder hook of your own in `~/.claude/settings.json`, remove it, or you will get each reminder two times.

## Install in Claude Code

In a Claude Code session:

```
/plugin marketplace add alejandroschuler/ctml-skills
/plugin install stats-research@ctml-skills
```

Install `paper-pipeline@ctml-skills`, `overleaf-tools@ctml-skills` or `claude-code-utils@ctml-skills` the same way. From a terminal, the equivalent commands are `claude plugin marketplace add alejandroschuler/ctml-skills` and `claude plugin install stats-research@ctml-skills`.

Installed skills carry their plugin's name as a prefix, for example `stats-research:supervised-learning`.

## Keep the plugins up to date

Claude Code does not update plugins from this marketplace by itself, because auto-update is off by default for third-party marketplaces like this one. You turn it on in `~/.claude/settings.json`. The `marketplace add` command already wrote a `ctml-skills` entry there. Add `"autoUpdate": true` next to its `source`.

If you use the Claude desktop app, also add `FORCE_AUTOUPDATE_PLUGINS` to the `env` block. The desktop app starts Claude Code with `DISABLE_AUTOUPDATER=1`, and that variable stops automatic plugin updates unless `FORCE_AUTOUPDATE_PLUGINS` is also set. Merge both keys into the settings that you have, and keep the rest of the file:

```json
{
  "extraKnownMarketplaces": {
    "ctml-skills": {
      "source": { "source": "github", "repo": "alejandroschuler/ctml-skills" },
      "autoUpdate": true
    }
  },
  "env": {
    "FORCE_AUTOUPDATE_PLUGINS": "1"
  }
}
```

In a terminal session without that variable, the `/plugin` menu can add `autoUpdate` for you. Open its **Marketplaces** tab, select `ctml-skills`, then select **Enable auto-update**.

With auto-update on, Claude Code checks the marketplace within ten minutes after your first message in a session. It puts new versions on disk, and your next session loads them. A plugin updates only when the `version` in its `.claude-plugin/plugin.json` goes up. If you change a plugin in this repo, raise that version.

To update by hand, run these in a terminal and then restart Claude Code:

```bash
claude plugin marketplace update ctml-skills
claude plugin update stats-research@ctml-skills
```

Update each other plugin that you use with the same command.

## Use without the plugin system

Each skill is a plain folder with a `SKILL.md` at its top. You can copy `plugins/<plugin>/skills/<skill>/` into `~/.claude/skills/`, or zip a skill folder and upload it to claude.ai as a custom skill.


## License

MIT. See [LICENSE](LICENSE).
