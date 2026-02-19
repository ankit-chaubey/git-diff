# Changelog

All notable changes to `git-diff` are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
This project uses [Semantic Versioning](https://semver.org/).

---

## [0.1.0] — 2024-01-01

### 🎉 Initial release

#### Added
- **GitHub-style diff viewer** with line numbers, `+`/`-` highlights, hunk headers
- **3 themes**: Dark (GitHub dark), Light (GitHub light), AMOLED (true black)
- **Repository overview** with stats cards (commits, contributors, branches, tags, size)
- **Commit activity heatmap** (GitHub-calendar style, last 90 days)
- **Language breakdown** with color bar chart by file extension
- **Commit history** — browse up to 500 commits, click any for full diff
- **Compare any two refs** — branch vs branch, SHA vs SHA, tag vs tag, any mix
- **Working tree changes** — staged and unstaged diffs clearly separated
- **File browser** — browse all tracked files with syntax-highlighted view
- **File history** — commits that touched a specific file
- **Blame view** — line-level authorship with commit hash and date
- **Contributors panel** — ranked by commits with visual progress bars
- **Branches & tags panel** — local/remote branches, annotated tags
- **Stash viewer** — list and diff all stash entries
- **Keyboard shortcuts** — `Esc`, `Ctrl+R`, `Ctrl+K`, `Ctrl+\`
- **REST API** — all data accessible via `/api/*` endpoints
- **Zero runtime dependencies** — pure Python stdlib only
- **Cross-platform** — macOS, Linux, Windows
- **Python 3.8–3.13** support
- **PyPI Trusted Publisher** (OIDC) workflow — no API token needed
- **CI** — tests on 3 OS × 5 Python versions
