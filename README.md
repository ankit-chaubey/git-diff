# git-diff 🔍

> **Beautiful git viewer in your browser** like GitHub, but local and instant.  
> No tokens. No accounts. No internet. Just `git-diff` and a browser tab.

[![PyPI version](https://badge.fury.io/py/git-diff.svg)](https://pypi.org/project/git-diff/)
[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![CI](https://github.com/ankit-chaubey/git-diff/actions/workflows/ci.yml/badge.svg)](https://github.com/ankit-chaubey/git-diff/actions)
[![Zero dependencies](https://img.shields.io/badge/dependencies-zero-brightgreen.svg)]()

---

## The problem

```
$ git diff HEAD~3
diff --git a/src/api/users.py b/src/api/users.py
index 3f2a1b8..9c4d72e 100644
--- a/src/api/users.py
+++ b/src/api/users.py
@@ -142,6 +142,9 @@ class UserService:
...
```

Raw `git diff` in a terminal is painful no syntax colors that actually help, no side-by-side view, no file navigation, no history, no blame. You have to mentally parse it line by line.

**git-diff** opens a GitHub-quality interface in your browser right now, from any repo, with no setup.

---

## Install

```bash
pip install git-diff
```

That's it. No npm, no node, no extra deps.

---

## Usage

```bash
# Open viewer for the current repo
cd /path/to/your/project
git-diff

# Specify a repo path
git-diff --path /path/to/repo

# Use a custom port
git-diff --port 8080

# Bind to all interfaces (share on LAN)
git-diff --host 0.0.0.0

# Don't auto-open browser (print URL only)
git-diff --no-browser

# Show 5 lines of context in diffs
git-diff --context 5

# Print version
git-diff --version
```

A browser tab opens automatically at `http://127.0.0.1:7433`.

---

## Features

### 🔀 Diff Viewer (GitHub-style)
- Line-by-line diff with **line numbers**, color-coded `+` additions / `-` deletions
- **Hunk headers** showing function/class context (`@@ ... @@ def my_function`)
- **File status badges** Added, Modified, Deleted, Renamed (with similarity %)
- Collapsible files click any file header to expand/collapse
- Binary file detection
- Support for **thousands of changed files** in a single view

### 📊 Repository Overview
- Total commits, contributors, files, branches, tags, repo size
- **Commit activity heatmap** (last 90 days, GitHub-style calendar)
- **Language breakdown** files and percentage by extension with color chart

### 📜 Commit History
- Browse **all commits** with author, date, relative time ("3 hours ago")
- Click any commit to see its **full diff** instantly
- **Merge commit** detection
- Parent commit links (click to navigate)
- Ref decoration branch labels, HEAD pointer, tags
- Search and filter commits in the sidebar

### 🔀 Compare Any Two Refs
- Compare **any branch vs branch**, **tag vs tag**, **SHA vs SHA**, or any mix
- Shows all commits in the range + full file diff
- One-click "Diff vs current" button on every branch in the branches panel
- Keyboard shortcut: `Ctrl/Cmd + K`

### ✏️  Working Tree Changes
- **Staged** and **Unstaged** changes clearly separated
- Click any file in sidebar to jump to its specific diff
- Real-time (refresh to update)

### 📁 File Browser
- Browse all tracked files
- **View file content** with syntax-aware line numbers
- **File history** all commits that touched a file
- **Blame view** who wrote which line, with commit hash and date
- Filter by filename in sidebar

### 👥 Contributors
- Ranked leaderboard by commit count
- Visual progress bars
- Email address, commit count

### 🌿 Branches & Tags
- All local and remote branches
- Tags with dates and annotation messages
- "Diff vs current" button on every branch

### 📦 Stashes
- View all stashed changes
- Click to see full diff for any stash entry

### 🎨 3 Themes
| Theme | Description |
|-------|-------------|
| 🌙 **Dark** | GitHub dark easy on the eyes |
| ☀️ **Light** | GitHub light clean and crisp |
| ⚫ **AMOLED** | True black perfect for OLED screens |

Themes are **persisted** in `localStorage` your preference sticks across sessions.

### ⌨️  Keyboard Shortcuts
| Shortcut | Action |
|----------|--------|
| `Esc` | Return to overview |
| `Ctrl/Cmd + R` | Refresh repository data |
| `Ctrl/Cmd + K` | Open Compare view |
| `Ctrl/Cmd + \` | Toggle sidebar |

---

## How it works

`git-diff` is a single Python package with **zero runtime dependencies**. It:

1. Detects your git repository root (walks up from CWD)
2. Collects all data by running `git` subprocess commands
3. Starts a tiny HTTP server using Python's built-in `http.server`
4. Serves a single-page web app with full UI
5. Opens your browser automatically
6. Exposes a `/api/*` REST endpoint for on-demand data

Everything runs **100% locally**. No data leaves your machine.

---

## API Reference

`git-diff` exposes these endpoints (accessible at `http://127.0.0.1:7433`):

| Endpoint | Description |
|----------|-------------|
| `GET /` | The web UI |
| `GET /api/data` | Full initial data bundle (repo info, commits, diffs, etc.) |
| `GET /api/commit?hash=<sha>` | Commit diff + detail for a specific SHA |
| `GET /api/commits?branch=&limit=&offset=&search=&author=` | Paginated commit history |
| `GET /api/staged[?context=N]` | Current staged diff |
| `GET /api/unstaged[?context=N]` | Current unstaged diff |
| `GET /api/range-diff?base=<ref>&compare=<ref>` | Diff between any two refs |
| `GET /api/file?path=<path>[&ref=<ref>]` | File content at a ref |
| `GET /api/file-log?path=<path>[&limit=N]` | Commit history for a file |
| `GET /api/blame?path=<path>[&ref=<ref>]` | Blame for a file |
| `GET /api/stash?ref=<stash-ref>` | Stash diff |
| `GET /api/activity[?days=N]` | Commit activity by day |
| `GET /api/langs` | Language statistics |
| `GET /api/refresh` | Re-collect all data |
| `GET /api/git?cmd=<git-args>` | Safe read-only git passthrough |

---

## Supported git commands (internal)

`git-diff` internally uses these git operations to collect data:

```
git rev-parse          detect repo root, resolve refs
git log                commit history, activity stats, file history
git show               commit detail, file content at ref
git diff               staged, unstaged, commit diffs
git status             working tree status
git blame              line-level authorship
git stash list/show    stash entries and diffs
git branch             local and remote branches
git for-each-ref       tags with metadata
git shortlog           contributor stats
git ls-tree            tracked file listing
git remote             remote URLs
git rev-list           commit counts
```

---

## Supported Platforms

| Platform | Status |
|----------|--------|
| macOS (10.14+) | ✅ Fully supported |
| Linux (Ubuntu, Debian, Fedora, Arch…) | ✅ Fully supported |
| Windows 10/11 | ✅ Fully supported |
| Python 3.8 – 3.13 | ✅ Tested via CI |

---

## Development

```bash
# Clone the repo
git clone https://github.com/ankit-chaubey/git-diff.git
cd git-diff

# Install in editable mode
pip install -e .

# Run on itself great for testing!
git-diff
```

### Project structure

```
git-diff/
├── git_diff/
│   ├── __init__.py         Package metadata (version, author)
│   ├── __main__.py         python -m git_diff support
│   ├── cli.py              Argument parsing, startup banner
│   ├── git_data.py         All git data collection (subprocess calls)
│   ├── server.py           HTTP server + REST API endpoints
│   └── templates/
│       └── index.html      Full single-page web app (HTML + CSS + JS)
├── .github/
│   └── workflows/
│       ├── publish.yml     PyPI trusted publisher (OIDC)
│       └── ci.yml          CI: test on 3 OS × 5 Python versions
├── pyproject.toml          PEP 517 build config
├── README.md
├── CHANGELOG.md
└── LICENSE                 MIT
```

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

---

## License

MIT © 2024-Persent [Ankit Chaubey](https://github.com/ankit-chaubey)

---

## Author

**Ankit Chaubey**  
📧 [ankitchaubey.dev@gmail.com](mailto:ankitchaubey.dev@gmail.com)  
🐙 [github.com/ankit-chaubey](https://github.com/ankit-chaubey)

---

*Made with ❤️ because raw `git diff` in terminal hurts.*
