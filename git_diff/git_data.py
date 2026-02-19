"""
git_data.py -- Comprehensive git repository data collection for git-diff.
Collects everything: commits, diffs, branches, tags, stashes, stats, blame, log graphs.
"""
import subprocess
import os
import re
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# Core git runner
# ---------------------------------------------------------------------------

def run_git(args, cwd=None, check=False, timeout=30):
    """Run a git command and return stdout. Never raises on failure."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd or os.getcwd(),
            capture_output=True,
            text=True,
            check=check,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return result.stdout
    except subprocess.TimeoutExpired:
        return ""
    except FileNotFoundError:
        raise RuntimeError("git not found. Please install git and ensure it is in your PATH.")
    except Exception:
        return ""


def run_git_lines(args, cwd=None):
    """Run git command and return non-empty lines."""
    raw = run_git(args, cwd=cwd)
    return [l for l in raw.splitlines() if l.strip()]


# ---------------------------------------------------------------------------
# Repository discovery
# ---------------------------------------------------------------------------

def get_repo_root(path=None):
    """Get the root directory of the git repository."""
    cwd = str(path or os.getcwd())
    root = run_git(["rev-parse", "--show-toplevel"], cwd=cwd).strip()
    if not root:
        raise RuntimeError(f"Not a git repository (or any parent up to mount point): {cwd}")
    return root


def is_git_repo(path=None):
    """Check if path is inside a git repo."""
    try:
        get_repo_root(path)
        return True
    except RuntimeError:
        return False


# ---------------------------------------------------------------------------
# Repository info
# ---------------------------------------------------------------------------

def get_repo_info(repo_root):
    """Collect comprehensive repository metadata."""
    name = os.path.basename(repo_root)

    # Remote URLs
    remotes_raw = run_git(["remote", "-v"], cwd=repo_root)
    remotes = {}
    for line in remotes_raw.splitlines():
        parts = line.split()
        if len(parts) >= 2 and "(fetch)" in line:
            remotes[parts[0]] = parts[1]

    remote_url = remotes.get("origin", next(iter(remotes.values()), ""))

    # Current branch / HEAD
    branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root).strip() or "HEAD"
    head_hash = run_git(["rev-parse", "HEAD"], cwd=repo_root).strip() or ""

    # Commit counts
    total_commits_raw = run_git(["rev-list", "--count", "HEAD"], cwd=repo_root).strip()
    total_commits = int(total_commits_raw) if total_commits_raw.isdigit() else 0

    # All branches
    branches_raw = run_git(
        ["branch", "-a", "--format=%(refname:short)|%(objectname:short)|%(committerdate:short)|%(subject)"],
        cwd=repo_root,
    )
    branches = []
    for line in branches_raw.splitlines():
        parts = line.split("|", 3)
        branches.append({
            "name": parts[0].strip(),
            "hash": parts[1] if len(parts) > 1 else "",
            "date": parts[2] if len(parts) > 2 else "",
            "subject": parts[3] if len(parts) > 3 else "",
            "is_current": parts[0].strip() == branch,
            "is_remote": parts[0].strip().startswith("remotes/"),
        })

    # Tags
    tags_raw = run_git(
        ["for-each-ref",
         "--sort=-version:refname",
         "--format=%(refname:short)|%(objecttype)|%(taggerdate:short)|%(subject)|%(taggername)|%(objectname:short)",
         "refs/tags"],
        cwd=repo_root,
    )
    tags = []
    for line in tags_raw.splitlines():
        parts = line.split("|", 5)
        if parts:
            tags.append({
                "name": parts[0],
                "type": parts[1] if len(parts) > 1 else "",
                "date": parts[2] if len(parts) > 2 else "",
                "message": parts[3] if len(parts) > 3 else "",
                "tagger": parts[4] if len(parts) > 4 else "",
                "hash": parts[5] if len(parts) > 5 else "",
            })

    # Contributors
    contributors_raw = run_git(
        ["shortlog", "-sne", "--no-merges", "HEAD"], cwd=repo_root
    )
    contributors = []
    for line in contributors_raw.splitlines():
        m = re.match(r"\s*(\d+)\s+(.+?)\s+<(.+?)>", line)
        if m:
            contributors.append({
                "commits": int(m.group(1)),
                "name": m.group(2).strip(),
                "email": m.group(3).strip(),
            })

    # Latest commit
    latest = get_commit_detail("HEAD", repo_root) if head_hash else {}

    # Repo size (tracked files only)
    try:
        size_bytes = 0
        for p in Path(repo_root).rglob("*"):
            if p.is_file() and ".git" not in p.parts:
                try:
                    size_bytes += p.stat().st_size
                except OSError:
                    pass
        size_str = _format_size(size_bytes)
        size_bytes_val = size_bytes
    except Exception:
        size_str = "Unknown"
        size_bytes_val = 0

    # Git dir size
    try:
        git_dir = Path(repo_root) / ".git"
        git_size = sum(
            f.stat().st_size for f in git_dir.rglob("*") if f.is_file()
        )
        git_size_str = _format_size(git_size)
    except Exception:
        git_size_str = "Unknown"

    # First commit date
    first_commit_raw = run_git(
        ["log", "--reverse", "--format=%at", "--max-count=1"], cwd=repo_root
    ).strip()
    first_commit_date = ""
    if first_commit_raw.isdigit():
        first_commit_date = datetime.fromtimestamp(int(first_commit_raw)).strftime("%Y-%m-%d")

    return {
        "name": name,
        "path": repo_root,
        "remote_url": remote_url,
        "remotes": remotes,
        "current_branch": branch,
        "head_hash": head_hash,
        "head_short": head_hash[:7] if head_hash else "",
        "total_commits": total_commits,
        "branches": branches,
        "branch_count": len([b for b in branches if not b["is_remote"]]),
        "remote_branch_count": len([b for b in branches if b["is_remote"]]),
        "tags": tags,
        "contributors": contributors,
        "latest_commit": latest,
        "size": size_str,
        "size_bytes": size_bytes_val,
        "git_size": git_size_str,
        "first_commit_date": first_commit_date,
    }


def _format_size(size_bytes):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


# ---------------------------------------------------------------------------
# Commit detail & history
# ---------------------------------------------------------------------------

_COMMIT_FMT = "%H|%h|%an|%ae|%at|%cn|%ce|%ct|%s|%P|%D"


def get_commit_detail(ref, repo_root):
    """Get full detail of a single commit including body."""
    raw = run_git(
        ["show", "-s",
         "--format=%H%n%h%n%an%n%ae%n%at%n%cn%n%ce%n%P%n%D%n%s%n%b%n<<<END>>>",
         ref],
        cwd=repo_root,
    )
    lines = raw.split("\n")
    if len(lines) < 10:
        return {}
    body_lines = []
    i = 10
    while i < len(lines) and lines[i] != "<<<END>>>":
        body_lines.append(lines[i])
        i += 1
    ts = int(lines[4]) if lines[4].strip().isdigit() else 0
    parents = [p.strip() for p in lines[7].split() if p.strip()]
    return {
        "hash": lines[0].strip(),
        "short_hash": lines[1].strip(),
        "author_name": lines[2].strip(),
        "author_email": lines[3].strip(),
        "author_timestamp": ts,
        "date": datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S") if ts else "",
        "date_relative": _relative_time(ts),
        "committer_name": lines[5].strip(),
        "committer_email": lines[6].strip(),
        "parents": parents,
        "is_merge": len(parents) > 1,
        "refs": lines[8].strip(),
        "subject": lines[9].strip(),
        "body": "\n".join(body_lines).strip(),
    }


def get_commit_history(repo_root, limit=300, branch="HEAD", author=None, path_filter=None, search=None):
    """Get commit history with optional filters."""
    args = ["log", f"--format={_COMMIT_FMT}", f"-{limit}", branch]
    if author:
        args += [f"--author={author}"]
    if search:
        args += [f"--grep={search}", "--regexp-ignore-case"]
    if path_filter:
        args += ["--", path_filter]

    raw = run_git(args, cwd=repo_root)
    commits = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = line.split("|", 10)
        if len(parts) < 10:
            continue
        ts = int(parts[4]) if parts[4].strip().isdigit() else 0
        commits.append({
            "hash": parts[0].strip(),
            "short_hash": parts[1].strip(),
            "author_name": parts[2].strip(),
            "author_email": parts[3].strip(),
            "author_timestamp": ts,
            "date": datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S") if ts else "",
            "date_relative": _relative_time(ts),
            "committer_name": parts[5].strip(),
            "committer_email": parts[6].strip(),
            "committer_timestamp": int(parts[7]) if parts[7].strip().isdigit() else 0,
            "subject": parts[8].strip(),
            "parents": [p.strip() for p in parts[9].split() if p.strip()],
            "refs": parts[10].strip() if len(parts) > 10 else "",
        })
    return commits


def _relative_time(ts):
    if not ts:
        return ""
    now = datetime.now().timestamp()
    diff = int(now - ts)
    if diff < 60:
        return "just now"
    if diff < 3600:
        m = diff // 60
        return f"{m} minute{'s' if m != 1 else ''} ago"
    if diff < 86400:
        h = diff // 3600
        return f"{h} hour{'s' if h != 1 else ''} ago"
    if diff < 604800:
        d = diff // 86400
        return f"{d} day{'s' if d != 1 else ''} ago"
    if diff < 2592000:
        w = diff // 604800
        return f"{w} week{'s' if w != 1 else ''} ago"
    if diff < 31536000:
        mo = diff // 2592000
        return f"{mo} month{'s' if mo != 1 else ''} ago"
    y = diff // 31536000
    return f"{y} year{'s' if y != 1 else ''} ago"


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

def get_status(repo_root):
    """Get detailed working tree status."""
    raw = run_git(["status", "--porcelain=v1", "-u"], cwd=repo_root)
    files = []
    for line in raw.splitlines():
        if len(line) < 4:
            continue
        xy = line[:2]
        rest = line[3:]
        staged_char = xy[0]
        unstaged_char = xy[1]
        if " -> " in rest:
            old, new = rest.split(" -> ", 1)
        else:
            old, new = rest, rest
        files.append({
            "staged": staged_char,
            "unstaged": unstaged_char,
            "path": new.strip().strip('"'),
            "old_path": old.strip().strip('"') if old != new else None,
            "xy": xy,
        })
    return files


# ---------------------------------------------------------------------------
# Diff parsing & fetching
# ---------------------------------------------------------------------------

def parse_diff(diff_raw, stat_raw=""):
    """Parse unified diff output into structured data with inline word-level diffs."""
    files = []
    current_file = None
    current_hunks = []
    current_hunk = None
    in_hunk = False

    lines = diff_raw.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]

        if line.startswith("diff --git "):
            if current_file is not None:
                if current_hunk:
                    current_hunks.append(current_hunk)
                current_file["hunks"] = current_hunks
                _finalize_file(current_file)
                files.append(current_file)

            m = re.match(r"diff --git a/(.+) b/(.+)", line)
            old_path = m.group(1) if m else ""
            new_path = m.group(2) if m else ""
            current_file = {
                "old_path": old_path,
                "new_path": new_path,
                "status": "modified",
                "hunks": [],
                "additions": 0,
                "deletions": 0,
                "is_binary": False,
                "is_new": False,
                "is_deleted": False,
                "old_mode": None,
                "new_mode": None,
                "similarity": None,
            }
            current_hunks = []
            current_hunk = None
            in_hunk = False

        elif line.startswith("new file mode") and current_file:
            current_file["is_new"] = True
            current_file["status"] = "added"
            current_file["new_mode"] = line.split()[-1]

        elif line.startswith("deleted file mode") and current_file:
            current_file["is_deleted"] = True
            current_file["status"] = "deleted"

        elif line.startswith("old mode") and current_file:
            current_file["old_mode"] = line.split()[-1]

        elif line.startswith("new mode") and current_file:
            current_file["new_mode"] = line.split()[-1]

        elif line.startswith("Binary files") and current_file:
            current_file["is_binary"] = True

        elif line.startswith("similarity index") and current_file:
            m = re.search(r"(\d+)%", line)
            if m:
                current_file["similarity"] = int(m.group(1))

        elif line.startswith("rename from ") and current_file:
            current_file["old_path"] = line[len("rename from "):]
            current_file["status"] = "renamed"

        elif line.startswith("rename to ") and current_file:
            current_file["new_path"] = line[len("rename to "):]
            current_file["status"] = "renamed"

        elif line.startswith("copy from ") and current_file:
            current_file["status"] = "copied"

        elif line.startswith("@@") and current_file:
            if current_hunk:
                current_hunks.append(current_hunk)
            m = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)", line)
            if m:
                current_hunk = {
                    "old_start": int(m.group(1)),
                    "old_count": int(m.group(2)) if m.group(2) is not None else 1,
                    "new_start": int(m.group(3)),
                    "new_count": int(m.group(4)) if m.group(4) is not None else 1,
                    "context": m.group(5).strip(),
                    "lines": [],
                    "additions": 0,
                    "deletions": 0,
                }
            in_hunk = True

        elif in_hunk and current_hunk is not None:
            if line.startswith("---") or line.startswith("+++"):
                pass
            elif line.startswith("+"):
                current_hunk["lines"].append({"type": "add", "content": line[1:]})
                current_hunk["additions"] += 1
            elif line.startswith("-"):
                current_hunk["lines"].append({"type": "del", "content": line[1:]})
                current_hunk["deletions"] += 1
            elif line.startswith(" "):
                current_hunk["lines"].append({"type": "ctx", "content": line[1:]})
            elif line.startswith("\\"):
                current_hunk["lines"].append({"type": "noeol", "content": line[1:]})

        i += 1

    if current_file is not None:
        if current_hunk:
            current_hunks.append(current_hunk)
        current_file["hunks"] = current_hunks
        _finalize_file(current_file)
        files.append(current_file)

    total_additions = sum(f["additions"] for f in files)
    total_deletions = sum(f["deletions"] for f in files)

    return {
        "files": files,
        "total_files": len(files),
        "total_additions": total_additions,
        "total_deletions": total_deletions,
        "stat_summary": stat_raw.strip().splitlines()[-1] if stat_raw.strip() else "",
    }


def _finalize_file(f):
    f["additions"] = sum(h["additions"] for h in f["hunks"])
    f["deletions"] = sum(h["deletions"] for h in f["hunks"])


def get_diff(repo_root, base=None, compare=None, staged=False, context=3, path_filter=None):
    """Universal diff fetcher: staged, unstaged, commit, or between any two refs."""
    args = ["diff", f"-U{context}"]

    if staged:
        args.append("--cached")
    elif base and compare:
        args.append(f"{base}...{compare}")
    elif base:
        # Single ref: show that commit's diff
        args = ["show", f"-U{context}", "--format=", base]
    # else: unstaged working tree

    stat_args = list(args)
    # For stat, replace -U{n} with --stat
    stat_args = [a for a in stat_args if not a.startswith("-U")]
    if "show" in stat_args:
        stat_args_final = ["show", "--stat", "--format=", base] if base else args
    else:
        stat_args_final = stat_args + ["--stat"]

    if path_filter:
        args += ["--", path_filter]
        stat_args_final += ["--", path_filter]

    stat_raw = run_git(stat_args_final, cwd=repo_root)
    diff_raw = run_git(args, cwd=repo_root)
    return parse_diff(diff_raw, stat_raw)


def get_commit_diff(commit_hash, repo_root, context=3):
    return get_diff(repo_root, base=commit_hash, context=context)


def get_staged_diff(repo_root, context=3):
    return get_diff(repo_root, staged=True, context=context)


def get_unstaged_diff(repo_root, context=3):
    return get_diff(repo_root, context=context)


def get_range_diff(repo_root, base, compare, context=3):
    """Diff between two refs (branches, tags, SHAs)."""
    stat_raw = run_git(["diff", "--stat", f"{base}...{compare}"], cwd=repo_root)
    diff_raw = run_git(["diff", f"-U{context}", f"{base}...{compare}"], cwd=repo_root)
    return parse_diff(diff_raw, stat_raw)


# ---------------------------------------------------------------------------
# File operations
# ---------------------------------------------------------------------------

def get_file_tree(repo_root, ref="HEAD"):
    """Get all tracked files with metadata."""
    raw = run_git(["ls-tree", "-r", "--long", ref], cwd=repo_root)
    files = []
    for line in raw.splitlines():
        # format: <mode> SP <type> SP <object> SP <object size> TAB <file>
        m = re.match(r"(\d+) (\w+) ([0-9a-f]+)\s+(\d+|-)\t(.+)", line)
        if m:
            size = int(m.group(4)) if m.group(4) != "-" else 0
            files.append({
                "mode": m.group(1),
                "type": m.group(2),
                "hash": m.group(3),
                "size": size,
                "path": m.group(5),
                "name": m.group(5).split("/")[-1],
                "dir": "/".join(m.group(5).split("/")[:-1]),
            })
    return files


def get_file_content(repo_root, path, ref="HEAD"):
    """Get file content at a given ref."""
    content = run_git(["show", f"{ref}:{path}"], cwd=repo_root)
    lines = content.splitlines()
    return {"content": content, "lines": len(lines), "path": path, "ref": ref}


def get_file_log(repo_root, path, limit=50):
    """Get commit history for a specific file."""
    return get_commit_history(repo_root, limit=limit, path_filter=path)


def get_file_blame(repo_root, path, ref="HEAD"):
    """Get blame for a file."""
    raw = run_git(["blame", "-p", ref, "--", path], cwd=repo_root)
    lines = []
    current_hash = None
    meta = {}
    for line in raw.splitlines():
        if re.match(r"^[0-9a-f]{40} ", line):
            parts = line.split()
            current_hash = parts[0]
            if current_hash not in meta:
                meta[current_hash] = {"hash": current_hash, "short_hash": current_hash[:7]}
        elif line.startswith("author "):
            meta[current_hash]["author"] = line[7:].strip()
        elif line.startswith("author-time "):
            ts = int(line[12:].strip())
            meta[current_hash]["date"] = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
        elif line.startswith("summary "):
            meta[current_hash]["summary"] = line[8:].strip()
        elif line.startswith("\t"):
            lines.append({
                "content": line[1:],
                "hash": current_hash,
                "meta": meta.get(current_hash, {}),
            })
    return lines


# ---------------------------------------------------------------------------
# Stashes
# ---------------------------------------------------------------------------

def get_stashes(repo_root):
    """Get stash list with details."""
    raw = run_git(["stash", "list", "--format=%gd|%H|%s|%cr|%at"], cwd=repo_root)
    stashes = []
    for line in raw.splitlines():
        parts = line.split("|", 4)
        if len(parts) >= 3:
            stashes.append({
                "ref": parts[0],
                "hash": parts[1] if len(parts) > 1 else "",
                "message": parts[2] if len(parts) > 2 else "",
                "relative": parts[3] if len(parts) > 3 else "",
                "timestamp": int(parts[4]) if len(parts) > 4 and parts[4].strip().isdigit() else 0,
            })
    return stashes


def get_stash_diff(repo_root, ref="stash@{0}", context=3):
    """Get diff for a stash entry."""
    diff_raw = run_git(["stash", "show", "-p", f"-U{context}", ref], cwd=repo_root)
    stat_raw = run_git(["stash", "show", "--stat", ref], cwd=repo_root)
    return parse_diff(diff_raw, stat_raw)


# ---------------------------------------------------------------------------
# Graph log
# ---------------------------------------------------------------------------

def get_graph_log(repo_root, limit=100, branch="HEAD"):
    """Get commit graph log (ASCII style data for UI)."""
    raw = run_git(
        ["log", "--graph", "--format=%h|%s|%an|%ar|%D", f"-{limit}", branch, "--all"],
        cwd=repo_root,
    )
    return raw


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

def get_commit_stats_by_day(repo_root, days=90):
    """Get commit counts grouped by day for the past N days."""
    raw = run_git(
        ["log", "--format=%ad", "--date=short", f"--since={days} days ago", "HEAD"],
        cwd=repo_root,
    )
    from collections import Counter
    counts = Counter(raw.splitlines())
    return dict(sorted(counts.items()))


def get_commit_stats_by_author(repo_root):
    """Get commit counts per author."""
    raw = run_git(["shortlog", "-sn", "--no-merges", "HEAD"], cwd=repo_root)
    result = []
    for line in raw.splitlines():
        m = re.match(r"\s*(\d+)\s+(.+)", line)
        if m:
            result.append({"count": int(m.group(1)), "author": m.group(2).strip()})
    return result


def get_language_stats(repo_root):
    """Estimate language stats by file extension."""
    from collections import defaultdict
    ext_count = defaultdict(int)
    ext_size = defaultdict(int)
    try:
        for p in Path(repo_root).rglob("*"):
            if p.is_file() and ".git" not in p.parts:
                ext = p.suffix.lower() or "(none)"
                try:
                    size = p.stat().st_size
                    ext_count[ext] += 1
                    ext_size[ext] += size
                except OSError:
                    pass
    except Exception:
        pass
    total_files = sum(ext_count.values()) or 1
    return sorted(
        [{"ext": k, "count": v, "size": ext_size[k],
          "pct": round(v / total_files * 100, 1)}
         for k, v in ext_count.items()],
        key=lambda x: -x["count"],
    )[:30]


# ---------------------------------------------------------------------------
# Refs resolution
# ---------------------------------------------------------------------------

def resolve_ref(repo_root, ref):
    """Resolve a ref to a full SHA."""
    return run_git(["rev-parse", ref], cwd=repo_root).strip()


def get_all_refs(repo_root):
    """Get all refs (branches + tags + HEAD)."""
    raw = run_git(
        ["for-each-ref",
         "--format=%(refname:short)|%(objectname:short)|%(objecttype)",
         "refs/"],
        cwd=repo_root,
    )
    refs = []
    for line in raw.splitlines():
        parts = line.split("|", 2)
        if len(parts) == 3:
            refs.append({"name": parts[0], "hash": parts[1], "type": parts[2]})
    return refs


# ---------------------------------------------------------------------------
# Master data collector
# ---------------------------------------------------------------------------

def collect_all_data(repo_root):
    """Collect all repository data for initial page load."""
    print("  [1/10] Collecting repository metadata...")
    repo_info = get_repo_info(repo_root)

    print("  [2/10] Collecting commit history (up to 500)...")
    commits = get_commit_history(repo_root, limit=500)

    print("  [3/10] Collecting working tree status...")
    status = get_status(repo_root)

    print("  [4/10] Collecting staged diff...")
    staged_diff = get_staged_diff(repo_root)

    print("  [5/10] Collecting unstaged diff...")
    unstaged_diff = get_unstaged_diff(repo_root)

    print("  [6/10] Collecting file tree...")
    file_tree = get_file_tree(repo_root)

    print("  [7/10] Collecting stashes...")
    stashes = get_stashes(repo_root)

    print("  [8/10] Collecting commit stats (90 days)...")
    commit_stats = get_commit_stats_by_day(repo_root, days=90)

    print("  [9/10] Collecting language stats...")
    lang_stats = get_language_stats(repo_root)

    print("  [10/10] Collecting all refs...")
    all_refs = get_all_refs(repo_root)

    return {
        "repo": repo_info,
        "commits": commits,
        "status": status,
        "staged_diff": staged_diff,
        "unstaged_diff": unstaged_diff,
        "file_tree": file_tree,
        "stashes": stashes,
        "commit_stats": commit_stats,
        "lang_stats": lang_stats,
        "all_refs": all_refs,
    }
