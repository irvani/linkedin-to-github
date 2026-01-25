from __future__ import annotations

import csv
import html
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence
from urllib.parse import quote_plus

HEADER_PREFIX = "First Name,Last Name,URL,Email Address,Company,Position,Connected On"

DEFAULT_WORKLIST = "github_lookup_worklist.csv"
DEFAULT_HTML = "github_lookup_links.html"
DEFAULT_USERS_TXT = "users.txt"

WORKLIST_COLUMNS: Sequence[str] = (
    "name",
    "linkedin_url",
    "company",
    "position",
    "email",
    "connected_on",
    # human-in-the-loop enrichment:
    "github_username",
    "notes",
    # helper links:
    "google",
    "google_company",
    "google_site_github",
    "google_site_role",
    "github_search",
)


@dataclass(frozen=True)
class WorkItem:
    name: str
    linkedin_url: str
    company: str
    position: str
    email: str
    connected_on: str
    google: str
    google_company: str
    google_site_github: str
    google_site_role: str
    github_search: str


def _find_header_index(lines: List[str]) -> int:
    for i, line in enumerate(lines):
        if line.startswith(HEADER_PREFIX):
            return i
    raise ValueError(
        "Could not find LinkedIn header line. "
        "Expected a line starting with: "
        f"{HEADER_PREFIX}"
    )


def _make_links(name: str, company: str, position: str) -> Dict[str, str]:
    name = (name or "").strip()
    company = (company or "").strip()
    position = (position or "").strip()

    q1 = f"{name} github"
    q2 = f"{name} {company} github" if company else q1
    q3 = f"site:github.com {name} {company}".strip()
    q4 = f"site:github.com {name} {position}".strip()
    ghq = f"{name} {company}".strip()

    return {
        "google": "https://www.google.com/search?q=" + quote_plus(q1),
        "google_company": "https://www.google.com/search?q=" + quote_plus(q2),
        "google_site_github": "https://www.google.com/search?q=" + quote_plus(q3),
        "google_site_role": "https://www.google.com/search?q=" + quote_plus(q4),
        "github_search": "https://github.com/search?q=" + quote_plus(ghq) + "&type=users",
    }


def parse_linkedin_connections(connections_csv: Path) -> List[WorkItem]:
    """Parse LinkedIn Connections.csv.

    LinkedIn exports sometimes contain 'Notes:' lines above the true CSV header.
    This parser finds the header line and reads from there.
    """
    raw_lines = connections_csv.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    header_idx = _find_header_index(raw_lines)
    content = "\n".join(raw_lines[header_idx:])

    reader = csv.DictReader(content.splitlines())
    items: List[WorkItem] = []

    for r in reader:
        first = (r.get("First Name") or "").strip()
        last = (r.get("Last Name") or "").strip()
        linkedin_url = (r.get("URL") or "").strip()
        email = (r.get("Email Address") or "").strip()
        company = (r.get("Company") or "").strip()
        position = (r.get("Position") or "").strip()
        connected_on = (r.get("Connected On") or "").strip()

        name = " ".join([p for p in [first, last] if p]).strip()
        if not name:
            continue

        links = _make_links(name, company, position)
        items.append(
            WorkItem(
                name=name,
                linkedin_url=linkedin_url,
                company=company,
                position=position,
                email=email,
                connected_on=connected_on,
                **links,
            )
        )

    return items


def write_worklist_csv(items: Iterable[WorkItem], out_csv: Path) -> None:
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(WORKLIST_COLUMNS))
        w.writeheader()
        for it in items:
            w.writerow(
                {
                    "name": it.name,
                    "linkedin_url": it.linkedin_url,
                    "company": it.company,
                    "position": it.position,
                    "email": it.email,
                    "connected_on": it.connected_on,
                    "github_username": "",
                    "notes": "",
                    "google": it.google,
                    "google_company": it.google_company,
                    "google_site_github": it.google_site_github,
                    "google_site_role": it.google_site_role,
                    "github_search": it.github_search,
                }
            )


def write_links_html(items: Iterable[WorkItem], out_html: Path, title: str = "LinkedIn → GitHub lookup links") -> None:
    out_html.parent.mkdir(parents=True, exist_ok=True)

    def a(url: str, label: str) -> str:
        u = html.escape(url or "", quote=True)
        l = html.escape(label or "")
        return f'<a href="{u}" target="_blank" rel="noopener noreferrer">{l}</a>'

    rows = []
    for it in items:
        rows.append(
            "\n".join(
                [
                    "<tr>",
                    f"  <td>{html.escape(it.name)}</td>",
                    f"  <td>{a(it.linkedin_url, 'LinkedIn') if it.linkedin_url else ''}</td>",
                    f"  <td>{html.escape(it.company)}</td>",
                    f"  <td>{html.escape(it.position)}</td>",
                    f"  <td>{a(it.google, 'Google name+github')}</td>",
                    f"  <td>{a(it.google_company, 'Google name+company+github')}</td>",
                    f"  <td>{a(it.google_site_github, 'Google site:github')}</td>",
                    f"  <td>{a(it.google_site_role, 'Google role site:github')}</td>",
                    f"  <td>{a(it.github_search, 'GitHub search')}</td>",
                    "</tr>",
                ]
            )
        )

    doc = f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
  <title>{html.escape(title)}</title>
  <style>
    body {{ font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; padding: 24px; }}
    h1 {{ font-size: 20px; margin: 0 0 12px 0; }}
    p {{ color: #333; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; font-size: 13px; vertical-align: top; }}
    th {{ background: #f7f7f7; text-align: left; position: sticky; top: 0; }}
    tr:nth-child(even) td {{ background: #fcfcfc; }}
  </style>
</head>
<body>
  <h1>{html.escape(title)}</h1>
  <p>Click links to look up each person. Fill <code>github_username</code> in the CSV if you find it.</p>
  <table>
    <thead>
      <tr>
        <th>Name</th>
        <th>LinkedIn</th>
        <th>Company</th>
        <th>Position</th>
        <th>Google</th>
        <th>Google + Company</th>
        <th>site:github.com</th>
        <th>Role site:github.com</th>
        <th>GitHub user search</th>
      </tr>
    </thead>
    <tbody>
      {'\n'.join(rows)}
    </tbody>
  </table>
</body>
</html>
"""

    out_html.write_text(doc, encoding="utf-8")


def read_worklist_usernames(worklist_csv: Path) -> List[str]:
    """Return unique GitHub usernames from a worklist CSV (column: github_username)."""
    content = worklist_csv.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    reader = csv.DictReader(content)
    usernames: List[str] = []
    seen = set()

    for r in reader:
        u = (r.get("github_username") or "").strip()
        if not u:
            continue
        # normalize: allow either @user or user
        u = u.lstrip("@")
        # keep it conservative: GitHub usernames are 1-39 chars alnum or hyphen, no consecutive hyphens at ends
        # We won't over-validate; just strip spaces and common URL forms.
        u = re.sub(r"^https?://github\.com/", "", u).strip("/ ")
        if not u:
            continue
        if u not in seen:
            seen.add(u)
            usernames.append(u)
    return usernames


def write_users_txt(usernames: Iterable[str], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    uniq = []
    seen = set()
    for u in usernames:
        u = (u or "").strip().lstrip("@")
        if not u or u in seen:
            continue
        seen.add(u)
        uniq.append(u)
    out_path.write_text("\n".join(uniq) + ("\n" if uniq else ""), encoding="utf-8")


def gh_follow_users(usernames: Iterable[str], dry_run: bool = True) -> List[str]:
    """Follow GitHub users using the GitHub CLI.

    Uses: gh api -X PUT user/following/{username}

    Returns a list of usernames attempted.
    """
    attempted: List[str] = []
    for u in usernames:
        u = (u or "").strip().lstrip("@")
        if not u:
            continue
        attempted.append(u)
        if dry_run:
            continue
        subprocess.run(
            ["gh", "api", f"user/following/{u}", "-X", "PUT"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    return attempted
