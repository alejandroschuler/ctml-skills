# ctml-skills

Agent skills for statistical methods research, packaged as a Claude Code plugin marketplace. They cover designing and reporting simulation studies, setting up and tuning supervised learners, checking that mathematical writing is readable, and keeping a paper's figures and numbers in step with the code that made them.

## What is here

| Plugin | Skills | Use it for |
|---|---|---|
| `stats-research` | `design-and-report-simulations`, `supervised-learning`, `readable-math` | Planning a simulation study backwards from its claims, building the code so any piece can rerun alone and expensive fits are cached, choosing and tuning learners (including the check that each tuning grid is wide enough), and making sure every symbol in a document is defined before it is used. |
| `paper-pipeline` | `reproducible-paper-artefacts` | Keeping a code repo and its Overleaf manuscript in step, so every figure, table and inline number is built by the pipeline and stamped with the commit that made it. |
| `claude-code-utils` | `move-claude-project` | Keeping a Claude Code project's session history when its folder is moved or renamed. |

The skills in `stats-research` refer to each other. The simulation skill sends learner setup to `supervised-learning` and finished prose to `readable-math`, so install that plugin whole.

## Install in Claude Code

In a Claude Code session:

```
/plugin marketplace add alejandroschuler/ctml-skills
/plugin install stats-research@ctml-skills
```

Install `paper-pipeline@ctml-skills` or `claude-code-utils@ctml-skills` the same way. From a terminal, the equivalent commands are `claude plugin marketplace add alejandroschuler/ctml-skills` and `claude plugin install stats-research@ctml-skills`.

To get a new version, run `claude plugin marketplace update ctml-skills`, then `claude plugin update stats-research@ctml-skills`, and restart Claude Code.

Installed skills carry their plugin's name as a prefix, for example `stats-research:supervised-learning`.

## Use without the plugin system

Each skill is a plain folder with a `SKILL.md` at its top. You can copy `plugins/<plugin>/skills/<skill>/` into `~/.claude/skills/`, or zip a skill folder and upload it to claude.ai as a custom skill.

## Making the main skills load reliably

Claude loads a skill when a request matches the skill's description. If you want the two main skills to load every time they apply, add lines like these to your `~/.claude/CLAUDE.md`:

```
Any time simulation work is in play, invoke the `stats-research:design-and-report-simulations` skill first.

Any time supervised machine learning, or similar loss-based learning such as Riesz regression, is in play, invoke the `stats-research:supervised-learning` skill first.
```

## Companion skill

The simulation skill also hands finished prose to [avoid-ai-writing](https://github.com/conorbronsdon/avoid-ai-writing) by Conor Bronsdon, when it is installed. That skill is not part of this repo.

## Evals

Most skills have an `evals/evals.json` with test prompts and assertions, in the format that Anthropic's skill-creator skill runs.

## License

MIT. See [LICENSE](LICENSE).
