"""
cli.py — Command-line interface for git-diff.
"""
import argparse
import os
import sys


BANNER = r"""
  __ _(_) |_      __| (_)/ _|/ _|
 / _` | | __|____/ _` | | |_| |_
| (_| | | ||_____| (_| | |  _|  _|
 \__, |_|\__|     \__,_|_|_| |_|
 |___/   Beautiful git viewer in your browser
"""


def main():
    parser = argparse.ArgumentParser(
        prog="git-diff",
        description="Beautiful git diff viewer in your browser — like GitHub, but local.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  git-diff                          Open viewer for current repo
  git-diff --port 8080              Use a specific port
  git-diff --no-browser             Don't auto-open browser
  git-diff --path /my/repo          Specify repo path
  git-diff --host 0.0.0.0           Bind to all interfaces (LAN access)
  git-diff --context 5              Show 5 lines of context in diffs
  git-diff --version                Show version and exit
        """,
    )

    parser.add_argument("--port", "-p", type=int, default=None,
                        help="Port to run on (default: auto-select 7433+)")
    parser.add_argument("--host", default="127.0.0.1",
                        help="Host to bind to (default: 127.0.0.1)")
    parser.add_argument("--no-browser", action="store_true",
                        help="Don't automatically open browser")
    parser.add_argument("--path", type=str, default=None,
                        help="Path to git repository (default: current directory)")
    parser.add_argument("--context", type=int, default=3,
                        help="Lines of context in diffs (default: 3)")
    parser.add_argument("--version", "-v", action="store_true",
                        help="Show version and exit")

    args = parser.parse_args()

    if args.version:
        from git_diff import __version__
        print(f"git-diff {__version__}")
        sys.exit(0)

    print(BANNER)

    from .git_data import get_repo_root, collect_all_data
    from .server import start_server

    try:
        repo_path = args.path or os.getcwd()
        repo_root = get_repo_root(repo_path)
    except RuntimeError as e:
        print(f"  ❌  Error: {e}\n", file=sys.stderr)
        sys.exit(1)

    repo_name = os.path.basename(repo_root)
    print(f"  📂  Repository: {repo_name}  ({repo_root})\n")

    try:
        print("  🔄  Collecting repository data...")
        data = collect_all_data(repo_root)
        print(f"\n  ✅  Ready! {data['repo']['total_commits']} commits · {len(data['file_tree'])} files · {len(data['repo']['contributors'])} contributors\n")
    except Exception as e:
        print(f"  ❌  Failed to collect git data: {e}\n", file=sys.stderr)
        sys.exit(1)

    start_server(repo_root, data, port=args.port, no_browser=args.no_browser, host=args.host)


if __name__ == "__main__":
    main()
