# ctml-skills

Agent skills for statistical methods research, packaged as a Claude Code plugin marketplace. They cover designing and reporting simulation studies, setting up and tuning supervised learners, checking that mathematical writing is readable, keeping a paper's figures and numbers in step with the code that made them, and reading the comments that coauthors leave on Overleaf.

## What is here

| Plugin | Skills | Use it for |
|---|---|---|
| `stats-research` | `design-and-report-simulations`, `supervised-learning`, `readable-math` | Planning a simulation study backwards from its claims, building the code so any piece can rerun alone and expensive fits are cached, choosing and tuning learners (including the check that each tuning grid is wide enough), and making sure every symbol in a LaTeX document is defined before it is used. |
| `paper-pipeline` | `reproducible-paper-artefacts` | Keeping a code repo and its Overleaf manuscript in step, so every figure, table and inline number is built by the pipeline and stamped with the commit that made it. |
| `overleaf-tools` | `overleaf-comments` | Reading the review comments and tracked changes on an Overleaf project, which the git bridge does not carry. |
| `claude-code-utils` | `move-claude-project` | Keeping a Claude Code project's session history when its folder is moved or renamed. |

The skills in `stats-research` refer to each other. The simulation skill sends learner setup to `supervised-learning` and finished LaTeX prose to `readable-math`, so install that plugin whole.

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

## Making the main skills load reliably

Claude loads a skill when a request matches the skill's description. If you want the two main skills to load every time they apply, add lines like these to your `~/.claude/CLAUDE.md`:

```
Any time simulation work is in play, invoke the `stats-research:design-and-report-simulations` skill first.

Any time supervised machine learning, or similar loss-based learning such as Riesz regression, is in play, invoke the `stats-research:supervised-learning` skill first.
```

## Reading Overleaf comments

`overleaf-tools:overleaf-comments` runs a Python script with `uv run`, so it needs [uv](https://docs.astral.sh/uv/). It works on any Overleaf project, and it finds the `paper/` clone of a `paper-pipeline` project by itself. The first login opens a Chrome, Chromium, Edge or Brave window with a separate profile, and you log in to Overleaf there. The session is saved in `~/.config/overleaf-comments/` and lasts while it is used at least once every five days.

The script reads through Overleaf's private web API with your own session, and it never writes. Overleaf's [Acceptable Use Policy](https://www.overleaf.com/legal) restricts scripted access to the service. Read it and decide for yourself before you use the script.

## Companion skill

The simulation skill also hands finished prose to [avoid-ai-writing](https://github.com/conorbronsdon/avoid-ai-writing) by Conor Bronsdon, when it is installed. That skill is not part of this repo.

## Evals

Most skills have an `evals/evals.json` with test prompts and assertions, in the format that Anthropic's skill-creator skill runs.

## License

MIT. See [LICENSE](LICENSE).
