# git-pulse

[![PyPI](https://img.shields.io/pypi/v/gitpulse-ai?logo=pypi&logoColor=white)](https://pypi.org/project/gitpulse-ai/)
[![Python](https://img.shields.io/pypi/pyversions/gitpulse-ai?logo=python&logoColor=white)](https://pypi.org/project/gitpulse-ai/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

[![Downloads](https://img.shields.io/pepy/dt/gitpulse-ai?label=total%20downloads&color=blue)](https://pepy.tech/project/gitpulse-ai)
[![Downloads/month](https://img.shields.io/pypi/dm/gitpulse-ai?label=downloads%2Fmonth&color=blue)](https://pypistats.org/packages/gitpulse-ai)
[![Release](https://img.shields.io/github/v/tag/srikanth1003/git-pulse?label=release&sort=semver)](https://github.com/srikanth1003/git-pulse/tags)
[![Last commit](https://img.shields.io/github/last-commit/srikanth1003/git-pulse)](https://github.com/srikanth1003/git-pulse/commits/main)

**Analyze git repository history for development hotspots and get LLM-powered insights to optimize your workflow.**

> Installed from PyPI as [`gitpulse-ai`](https://pypi.org/project/gitpulse-ai/); the command is `git-pulse`.

git-pulse examines your commit history to find rework patterns, codebase health issues, and — when coding agents are detected — specific prompt engineering guidance to reduce wasted iterations. It works on any git repo, with any LLM provider.

## What It Does

git-pulse reads your git history and produces actionable insights across five categories:

| Category | What It Finds |
|----------|--------------|
| **Rework Reduction** | Files rewritten multiple times — what went wrong and how to get it right faster |
| **Codebase Health** | Chronic hotspots, architectural issues causing repeated churn |
| **Prompt Guidance** | Specific before/after prompt examples when coding agents are detected (Co-Authored-By, aider tags, etc.) |
| **Agent Effectiveness** | How well agents are being utilized — where they struggle or excel |
| **Workflow Optimization** | Session patterns, productivity signals, process improvements |

### Agent-Aware Analysis

git-pulse auto-detects coding agent attribution from commit metadata — `Co-Authored-By: Claude`, `[copilot]`, `aider:` tags, and more. When agent commits are found, it provides **prompt guidance** with realistic bad/better prompt examples showing exactly what to change in how you talk to your agent.

Every signal carries a weight, and a commit's score is the highest weight it matched — so a classification is always traceable to the line of metadata that caused it.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/srikanth1003/git-pulse/main/docs/images/attribution-dark.png">
  <img alt="43.9% of 376 commits carry a coding-agent signature: 165 agent commits adding 2,574 lines against 211 human commits adding 4,707" src="https://raw.githubusercontent.com/srikanth1003/git-pulse/main/docs/images/attribution-light.png" width="840">
</picture>

<details>
<summary>Same figure as text</summary>

```
Agent-authored share — 43.9% of 376 commits carry a coding-agent signature

  agent    165 commits    2,574 lines added
  human    211 commits    4,707 lines added

  signal            weight   matches   provider
  coauthor_trailer    0.95        48   Claude Code
  bot_identity        0.90        96   GitHub Copilot
  aider_prefix        0.90        34   aider
  bracket_tag         0.85        35   Cursor
```

`matches` counts signal instances, not commits — `bot_identity` fires on both the
author and the committer field, so 96 matches is 48 commits.

</details>

### Churn, ranked

Insertions plus deletions per file. Churn on its own is not a defect signal, but it
tells you which files the next question is about.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/srikanth1003/git-pulse/main/docs/images/churn-dark.png">
  <img alt="orders.py churns most at 1,735 lines, ahead of routes.py at 1,467 and pricing.py at 1,406" src="https://raw.githubusercontent.com/srikanth1003/git-pulse/main/docs/images/churn-light.png" width="840">
</picture>

<details>
<summary>Same figure as text</summary>

```
Top files by churn (insertions + deletions, 120 days)

  src/shipyard/core/orders.py       1,735
  src/shipyard/api/routes.py        1,467
  src/shipyard/core/pricing.py      1,406
  src/shipyard/api/auth.py          1,167
  src/shipyard/core/scheduling.py   1,042
  src/shipyard/db/models.py           953
  tests/test_orders.py                886
  tests/test_pricing.py               803
```

Agent share of that churn runs 30–47% per file, so no single file is agent-only.

</details>

### Velocity over time

Commits per day across the window, with the peak and the last day labelled — enough
to see whether the work is steady or arrives in bursts.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/srikanth1003/git-pulse/main/docs/images/velocity-dark.png">
  <img alt="Commits per day across 92 active days of 120, averaging 3.13 and peaking at 12 on 2026-04-12" src="https://raw.githubusercontent.com/srikanth1003/git-pulse/main/docs/images/velocity-light.png" width="840">
</picture>

<details>
<summary>Same figure as text</summary>

```
Commit velocity — 376 commits over 120 days

  active days        92 of 120
  commits per day    3.13
  files per commit   1.62
  peak               12 commits on 2026-04-12
  last day            3 commits on 2026-05-05
```

</details>

### Spatiotemporal hotspots

A hotspot is a cluster of edits close together in *both* line position and time. The
classification says who touched the region and in what order, which is the part that
tells you whether an agent is being reworked or is doing the reworking.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/srikanth1003/git-pulse/main/docs/images/hotspots-dark.png">
  <img alt="Seven highest-scoring hotspots of 229: six are agent-reworked and one is human-fixing-agent, each 4 to 6 edits inside a 1 to 4 hour window" src="https://raw.githubusercontent.com/srikanth1003/git-pulse/main/docs/images/hotspots-light.png" width="840">
</picture>

<details>
<summary>Same figure as text</summary>

```
Spatiotemporal hotspots — 229 detected, seven highest-scoring shown

  location                              edits  span  agent/human  score  pattern
  src/shipyard/core/pricing.py:51-75        6  3.9h        3 / 3    7.4  agent-reworked
  src/shipyard/core/scheduling.py:55-71     4  1.2h        2 / 2    7.3  human-fixing-agent
  src/shipyard/core/pricing.py:151-160      5  2.5h        3 / 2    7.1  agent-reworked
  src/shipyard/db/models.py:26-50           6  4.1h        3 / 3    7.0  agent-reworked
  src/shipyard/db/models.py:51-75           6  4.1h        3 / 3    7.0  agent-reworked
  src/shipyard/core/orders.py:82-100        5  2.7h        3 / 2    6.7  agent-reworked
  tests/test_pricing.py:10-25               5  3.0h        3 / 2    6.3  agent-reworked
```

Score is `edits² ÷ (1 + hours)`. `human-fixing-agent` means a human touched the
region last; `agent-reworked` means an agent did.

</details>

> **About the numbers in these figures.** git-pulse's own history is entirely
> human-authored, so it cannot demonstrate agent attribution. Every figure above is a
> real `git-pulse analyze` run against a synthetic repository built with a fixed
> seed, so the numbers are reproducible rather than illustrative.

## Install

```bash
pip install gitpulse-ai
```

Requires Python 3.11+. The installed command is `git-pulse`.

## Quick Start

```bash
# Analyze current repo (last 30 days)
git-pulse analyze .

# Analyze a specific repo, last 14 days
git-pulse analyze /path/to/repo --days 14

# Last 50 commits only
git-pulse analyze . --commits 50

# JSON output
git-pulse analyze . --json

# Save report to file
git-pulse analyze . --output report.json

# Use a specific model
git-pulse analyze . --model openai/gpt-4o

# Show raw collector metrics alongside LLM insights
git-pulse analyze . --verbose
```

## Example Output

`git-pulse analyze` prints attribution, authors, churn, velocity, sessions, and
hotspots. No API key is involved in any of it — this is git metadata, counted.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/srikanth1003/git-pulse/main/docs/images/report-dark.png">
  <img alt="Terminal output: a header with repository, branch, date range and 376 commits, an attribution table showing 165 agent commits and four detected providers, and an authors table classifying each of six authors as agent or human" src="https://raw.githubusercontent.com/srikanth1003/git-pulse/main/docs/images/report-light.png" width="840">
</picture>

<details>
<summary>Same output as text</summary>

```
$ git-pulse analyze ~/src/shipyard --days 120
╭───────────────── git-pulse ─────────────────╮
│ git-pulse-demo  ·  branch main  ·  55b89860 │
│ 2026-01-06 → 2026-05-05  ·  376 commits     │
╰───── v0.1.1.dev24+g86dac6cf1.d20260823 ─────╯
Attribution
┏━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Metric            ┃                                                          Value ┃
┡━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Agent commits     │                                                      165 (44%) │
│ Mixed commits     │                                                              0 │
│ Human commits     │                                                            211 │
│ Agent lines added │                                                     2574 (35%) │
│ Providers         │ Claude Code (48), Cursor (35), GitHub Copilot (48), aider (34) │
└───────────────────┴────────────────────────────────────────────────────────────────┘
Authors
┏━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━┓
┃ Author                 ┃ Class ┃ Commits ┃         +/- ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━┩
│ Dana Whitfield         │ agent │      89 │  +2581/-955 │
│ Ravi Menon             │ agent │      83 │ +1386/-1046 │
│ Lena Osei              │ agent │      73 │  +1319/-943 │
│ copilot-swe-agent[bot] │ agent │      48 │   +702/-528 │
│ Tomas Brandt           │ human │      42 │   +662/-493 │
│ Priya Raman            │ human │      41 │   +631/-451 │
└────────────────────────┴───────┴─────────┴─────────────┘
```

Churn, velocity, session, and hotspot tables follow; they are shown as figures above.

</details>

## LLM Provider Setup

git-pulse uses [LiteLLM](https://docs.litellm.ai/) under the hood, so it works with 100+ LLM providers out of the box. Set the appropriate environment variable for your provider:

```bash
# Anthropic (default model: claude-sonnet-4-20250514)
export ANTHROPIC_API_KEY=sk-ant-...

# OpenAI
export OPENAI_API_KEY=sk-...
git-pulse analyze . --model openai/gpt-4o

# AWS Bedrock
export AWS_PROFILE=my-profile
git-pulse analyze . --model bedrock/us.anthropic.claude-sonnet-4-20250514-v1:0

# Any LiteLLM-supported provider
git-pulse analyze . --model <provider>/<model-id>
```

## Configuration

git-pulse looks for TOML config files in this order:

1. `--config` flag (explicit path)
2. `.gitpulse.toml` in the repo root
3. `~/.config/gitpulse/config.toml`
4. Built-in defaults

Example `.gitpulse.toml`:

```toml
[llm]
model = "anthropic/claude-sonnet-4-20250514"

[analysis]
default_days = 30
max_hotspots = 20
exclude = ["*.lock", "package-lock.json", "*.generated.*"]
```

## CLI Options

```
git-pulse analyze [PATH] [OPTIONS]

Arguments:
  PATH                  Path to a git repository [default: .]

Options:
  --days INTEGER        Analyze last N days of history
  --commits INTEGER     Analyze last N commits
  --branch TEXT         Branch to analyze (default: current)
  --include TEXT        Only analyze files matching glob (repeatable)
  --exclude TEXT        Skip files matching glob (repeatable)
  --max-hotspots INT    Max hotspots to send to LLM
  --model TEXT          LiteLLM model string
  --json                Output JSON instead of rich terminal
  --output TEXT         Write report to file
  --verbose             Show raw collector metrics
  --config TEXT         Path to config file
```

## How It Works

git-pulse has a two-layer architecture:

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/srikanth1003/git-pulse/main/docs/images/architecture-dark.png">
  <img alt="Layer diagram: cli imports report, report imports analysis, analysis imports gitlayer, gitlayer shells out to git; attribution, models, render, and the optional LLM analyst are shared by every layer above" src="https://raw.githubusercontent.com/srikanth1003/git-pulse/main/docs/images/architecture-light.png" width="840">
</picture>

<details>
<summary>Same diagram as text</summary>

```
cli         analyze · cache · config · version
 ↓
report      builds one immutable Report value
 ↓
analysis    churn · velocity · sessions · hotspots
 ↓
gitlayer    git plumbing · history cache
 ↓
git         log · numstat · notes

shared by every layer above:
  attribution   signals · providers
  models        typed history & report
  render        terminal · JSON v1
  analyst       optional LLM narrative  ← the only part that needs an API key
```

</details>

**Collector Layer** (deterministic, no LLM):
- Walks git history, extracts diffs, detects agent attribution
- Clusters modifications by file + spatial/temporal proximity into hotspots
- Computes metrics: file churn, change velocity, rework rate, session analysis

**Analyst Layer** (LLM-powered):
- Receives the structured collector report
- Produces categorized insights with evidence and recommendations
- Generates specific prompt guidance when agent attribution is detected

## Releases & Downloads

Latest release: [![Release](https://img.shields.io/github/v/tag/srikanth1003/git-pulse?label=&sort=semver&color=brightgreen)](https://github.com/srikanth1003/git-pulse/tags) on GitHub, [![PyPI](https://img.shields.io/pypi/v/gitpulse-ai?label=&color=brightgreen)](https://pypi.org/project/gitpulse-ai/) on PyPI.

| | |
|---|---|
| **PyPI package** | [pypi.org/project/gitpulse-ai](https://pypi.org/project/gitpulse-ai/) |
| **Release history** | [All versions on PyPI](https://pypi.org/project/gitpulse-ai/#history) · [Git tags](https://github.com/srikanth1003/git-pulse/tags) |
| **Download stats** | [pepy.tech](https://pepy.tech/project/gitpulse-ai) (totals, by version) · [pypistats.org](https://pypistats.org/packages/gitpulse-ai) (daily, by Python version) |

Versioning follows [Semantic Versioning](https://semver.org/). While the project is pre-1.0, minor versions may include breaking changes to the CLI and output schemas; pin an exact version if you depend on either.

## Development

```bash
# Clone and install in dev mode
git clone https://github.com/srikanth1003/git-pulse.git
cd git-pulse
pip install -e ".[dev]"

# Run tests
pytest

# Run on any repo
git-pulse analyze /path/to/any/repo --days 14
```

### Cutting a release

The version is derived from the git tag by [hatch-vcs](https://github.com/ofek/hatch-vcs) — there is no version string to edit. Tag, then build and upload:

```bash
git tag -a v0.2.0 -m "git-pulse 0.2.0"
git push origin v0.2.0
python -m build && twine upload dist/*
```

Builds from an untagged or dirty tree produce a local dev version (e.g. `0.1.1.dev0+g1b73c1f`), which PyPI rejects by design — release only from a clean tagged commit.

## License

MIT
