# Methodology

How git-pulse computes each metric, what assumptions it makes, and where those
assumptions break down. Every number this tool reports is derived from git
metadata alone — no source-code analysis, no network calls, no AI inference
(unless `--llm` is passed explicitly).

## Attribution

Each commit is scored as **human**, **mixed**, or **agent** based on the
highest-weight signal found in its metadata.

| Signal | Weight | What it matches |
|---|---|---|
| `coauthor_trailer` | 0.95 | `Co-Authored-By:` trailer naming a known agent |
| `bot_identity` | 0.90 | Author or committer email/name matching a bot pattern |
| `generated_by_trailer` | 0.90 | `Generated-by:` trailer |
| `aider_prefix` | 0.90 | Subject line starting with `aider:` |
| `generated_with_marker` | 0.90 | `Generated-with:` trailer |
| `git_note` | 0.90 | A git note referencing a known agent |
| `bracket_tag` | 0.85 | `[cursor]`, `[copilot]`, etc. in the subject |
| `cadence` | 0.20 | Unusually fast commit cadence (configurable) |

**Thresholds:** agent >= 0.70, mixed 0.30–0.70, human < 0.30.

**Limitation:** The mixed band is currently unreachable — no signal weight falls
in 0.30–0.70. It exists as a reserved slot for future per-hunk fractional
attribution. Until then, `mixed_commits` is always 0.

**Limitation:** Attribution is based on metadata conventions. A commit made by an
agent but lacking any recognized signal will be classified as human. There is no
diff-content-based heuristic — this is deliberate, as diff-based attribution
would require a model and would not be reproducible.

## Churn

Per-file insertions and deletions, aggregated across the analyzed history window.
Rename tracking is enabled (`-M`), so a renamed file's history collapses onto
its current path.

## File-level rework

The share of total churn that landed in files touched by more than one commit.
This is an **upper bound** on actual rework: it counts all lines in a
multi-touch file, even lines nobody revisited. It exists for backward
compatibility with 0.1.0.

## Per-line rework

A surviving line is "reworked" if its introducing commit is not the earliest
commit to touch that file. The first commit to a file creates it — those lines
replaced nothing. Every subsequent commit that writes surviving lines is by
definition overwriting or extending prior content.

**Assumption:** This treats all post-creation lines as rework. A commit that
appends 50 new lines to a file counts as rework even though no existing lines
were overwritten. A more precise measurement would require tracking individual
line identities across edits, which the line-lifetime index does not yet
support at that granularity.

## Ownership and bus factor

Per-file and repo-wide ownership are computed from `git blame --porcelain` on
the current HEAD. Each surviving line is attributed to the commit that
introduced it, and ownership is the share of lines per author.

**Bus factor** is the minimum number of authors whose combined line ownership
exceeds 50% of the file (or repository). A bus factor of 1 means one person
wrote more than half the surviving code.

**Limitation:** Blame attributes a line to the last commit that touched it,
which may be a reformatting or rename commit rather than the commit that wrote
the logic. There is no "ignore whitespace" mode in the blame pass currently.

## Temporal coupling

File pairs that change together across commits. The coupling ratio is:

```
coupling_ratio = shared_commits / min(commits_a, commits_b)
```

A ratio of 1.0 means the less-frequently-changed file always appears alongside
the other. Only pairs with at least `min_shared` co-occurrences (default: 3)
are reported.

**Limitation:** Coupling is purely commit-based. Two files that always change
in the same PR but are split across separate commits will not register as
coupled.

## Velocity

Commits per calendar day, active days, and files per commit over the analyzed
span. `span_days` is calendar days from first to last commit inclusive, so
quiet days reduce the rate.

## Sessions

Work clustered per author by commit-timestamp gap. A gap exceeding
`gap_minutes` (default: 90) starts a new session. Clustering is per-author, so
concurrent work by different people is not merged.

## Hotspots

Edits to the same file region within a time window, scored by:

```
score = modification_count² / (1 + time_span_hours)
```

Edits are binned into fixed-width line regions (default: 25 lines) rather than
merged by proximity. Binning prevents a large initial commit from bridging
every later edit into one meaningless cluster.

**Classification:** `repeated-agent` if only agents touched the region,
`human-iteration` if only humans, `human-fixing-agent` if a human touched it
last, `agent-reworked` if an agent touched it last.

## Revert and fix detection

Commits are classified from message patterns:

- **Revert:** subject starts with "Revert " (git default) or "revert:" /
  "revert(" (conventional commit)
- **Fix:** subject starts with "fix:", "bugfix:", "hotfix:", or body contains
  "fixes #N", "closes #N", "resolves #N"

**Limitation:** This is heuristic. A commit that fixes a bug without using any
of these patterns will not be detected. Conversely, a commit with "fix:" in
the subject that is actually a feature will be misclassified.

## Kaplan-Meier line survival

Statistical survival analysis for code lines. Each line's lifetime is measured
from its introducing commit to the commit that deleted or replaced it. Lines
still alive at the analysis boundary are **right-censored** — they contribute
to the survival estimate without being counted as dead.

The survival function is estimated using the Kaplan-Meier product-limit
estimator. Median survival time is the point where the survival function
crosses 0.50 (if it does).

Agent-written and human-written lines are estimated separately, so you can
compare their survival curves.

**Assumption:** A line is "dead" when any hunk in a later commit touches the
range it occupied. This overcounts deaths when a hunk reformats but does not
change semantics.

## SZZ bug-introduction attribution

Given a set of fix commits (from revert/fix detection), SZZ traces back via
`git blame` to find the commit that introduced the lines being fixed. That
introducing commit is labeled as a **bug-introducing commit**.

**Limitation:** Classic SZZ has known false positives: if a fix touches a line
that was last modified by a formatting commit, the formatting commit is blamed
rather than the commit that introduced the actual defect. This implementation
does not yet filter out cosmetic changes.

## Risk quadrants

Each file is placed in a 2x2 risk matrix based on:

- **Churn** (high vs. low, split at the median)
- **Bus factor** (risky: bus factor = 1, safe: bus factor >= 2)

The four quadrants are:

| | Low churn | High churn |
|---|---|---|
| **Safe (bus >= 2)** | Stable | Active |
| **Risky (bus = 1)** | Quiet risk | Hot risk |

Files in the "hot risk" quadrant are changing frequently and owned by a single
author — the highest-priority candidates for review.

## Indentation-based complexity

A proxy for code complexity that requires no language-specific parser. For each
file, the indentation depth of every non-blank line is measured (in units of
the detected indent width, defaulting to 4 spaces).

Reported metrics per file:
- **avg_depth**: mean indentation depth
- **max_depth**: deepest line
- **deep_line_share**: fraction of lines at depth >= 4

**Limitation:** Indentation is a weak proxy. A deeply nested Python function
and a deeply nested YAML config have the same depth profile but very different
complexity implications. The metric is most useful for comparing files within
the same language.
