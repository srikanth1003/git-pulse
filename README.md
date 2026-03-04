# git-pulse

**Analyze git repository history for development hotspots and get LLM-powered insights to optimize your workflow.**

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

## Install

```bash
pip install git-pulse
```

Requires Python 3.10+.

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

```
────────────────────────────────────────────────────────────────────────────────
 Git-Pulse Report — my-project (main)
 19 days · 100 commits · 242 files changed
────────────────────────────────────────────────────────────────────────────────

╭────────────────────────────────── Summary ───────────────────────────────────╮
│ Repository shows intensive development with 100 commits across 242 files.   │
│ High rework rate (40%) suggests agent prompts need improvement, with        │
│ multiple iterations on workflow configuration and model updates.             │
╰──────────────────────────────────────────────────────────────────────────────╯

Top Actions
  1. Create design documents before implementing GitHub Actions workflows
  2. Establish centralized model configuration to reduce scattered updates
  3. Improve agent prompts with dependency analysis before changes

───────────────────────  Rework Reduction (2 insights)  ────────────────────────

  [HIGH] GitHub Workflows Churning Through Multiple Iterations
    .github/workflows/deploy.yml modified 9 times in 2.4 hours
    Same file tweaked for permissions, triggers, and comments repeatedly
  → Plan workflow requirements upfront. Create a design doc specifying trigger
  events, permissions, and behavior before coding.

────────────────────────  Prompt Guidance (1 insight)  ────────────────────────

  [HIGH] Workflow Configuration Requires Context and Constraints
    PROBLEM: Developer asked agent to 'create GitHub workflow' without
    specifying security constraints or existing patterns.

    BAD PROMPT EXAMPLE:
  ╭──────────────────────────────────────────────────────────────────────────╮
  │  Create a GitHub workflow that runs tests automatically.                 │
  ╰──────────────────────────────────────────────────────────────────────────╯

    BETTER PROMPT EXAMPLE:
  ╭──────────────────────────────────────────────────────────────────────────╮
  │  Create a GitHub workflow for CI. Before you start, look at our         │
  │  existing .github/workflows/ to understand our patterns for             │
  │  permissions and triggers. Use contents:read permission. Follow the     │
  │  same job naming pattern as deploy.yml. If you're unsure about which    │
  │  events to use, ask me rather than guessing.                            │
  ╰──────────────────────────────────────────────────────────────────────────╯

    WHY THIS WORKS: Points to existing workflows to learn patterns, sets
    explicit security constraints, and prevents the agent from making
    permission guesses that need rework.
```

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

```
Git History ──► Collector Layer ──► Structured Report ──► Analyst (LLM) ──► Insights
                  │                                          │
                  ├─ GitHistoryCollector                      ├─ LiteLLM (any provider)
                  ├─ HotspotDetector (spatiotemporal)         └─ Categorized insights
                  └─ MetricsCalculator
```

**Collector Layer** (deterministic, no LLM):
- Walks git history, extracts diffs, detects agent attribution
- Clusters modifications by file + spatial/temporal proximity into hotspots
- Computes metrics: file churn, change velocity, rework rate, session analysis

**Analyst Layer** (LLM-powered):
- Receives the structured collector report
- Produces categorized insights with evidence and recommendations
- Generates specific prompt guidance when agent attribution is detected

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

## License

MIT
