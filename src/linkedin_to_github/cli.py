from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .core import (
    DEFAULT_HTML,
    DEFAULT_USERS_TXT,
    DEFAULT_WORKLIST,
    gh_follow_users,
    parse_linkedin_connections,
    read_worklist_usernames,
    write_links_html,
    write_users_txt,
    write_worklist_csv,
)


def cmd_make(args: argparse.Namespace) -> int:
    connections = Path(args.connections)
    outdir = Path(args.outdir)
    out_csv = outdir / (args.worklist or DEFAULT_WORKLIST)
    out_html = outdir / (args.html or DEFAULT_HTML)

    items = parse_linkedin_connections(connections)
    write_worklist_csv(items, out_csv)
    write_links_html(items, out_html)

    print(f"Wrote: {out_csv}")
    print(f"Wrote: {out_html}")
    return 0


def cmd_users(args: argparse.Namespace) -> int:
    worklist = Path(args.worklist)
    out_path = Path(args.out)
    usernames = read_worklist_usernames(worklist)
    write_users_txt(usernames, out_path)
    print(f"Wrote: {out_path} ({len(usernames)} usernames)")
    return 0


def cmd_follow(args: argparse.Namespace) -> int:
    users_path = Path(args.users)
    text = users_path.read_text(encoding="utf-8-sig", errors="replace")
    usernames = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]

    dry_run = args.dry_run or not args.yes
    attempted = gh_follow_users(usernames, dry_run=dry_run)

    if dry_run:
        print("Dry run only. Would follow:")
        for u in attempted:
            print(f"  {u}")
        print("\nRun with --yes (and ensure `gh auth login`) to actually follow.")
    else:
        print(f"Attempted to follow {len(attempted)} users via `gh`.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ltg", description="LinkedIn Connections.csv → GitHub lookup worklist + links")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_make = sub.add_parser("make", help="Generate github_lookup_worklist.csv and github_lookup_links.html")
    p_make.add_argument("--connections", required=True, help="Path to LinkedIn Connections.csv")
    p_make.add_argument("--outdir", default=".", help="Output directory")
    p_make.add_argument("--worklist", default=DEFAULT_WORKLIST, help="Worklist CSV filename")
    p_make.add_argument("--html", default=DEFAULT_HTML, help="HTML links filename")
    p_make.set_defaults(func=cmd_make)

    p_users = sub.add_parser("users", help="Generate users.txt from the worklist github_username column")
    p_users.add_argument("--worklist", required=True, help="Path to github_lookup_worklist.csv")
    p_users.add_argument("--out", default=DEFAULT_USERS_TXT, help="Output users.txt path")
    p_users.set_defaults(func=cmd_users)

    p_follow = sub.add_parser("follow", help="Follow users listed in users.txt using GitHub CLI (gh)")
    p_follow.add_argument("--users", default=DEFAULT_USERS_TXT, help="Path to users.txt")
    p_follow.add_argument("--dry-run", action="store_true", help="Print actions only (default unless --yes)")
    p_follow.add_argument("--yes", action="store_true", help="Actually run `gh api ...` calls")
    p_follow.set_defaults(func=cmd_follow)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
