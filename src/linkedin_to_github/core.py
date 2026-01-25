from __future__ import annotations

import csv
import html
import re
import subprocess
from collections.abc import Iterable, Sequence
from pathlib import Path
from urllib.parse import quote_plus

import httpx
from loguru import logger
from pydantic import BaseModel, ConfigDict
from rich.progress import Progress, SpinnerColumn, TextColumn

# Standard LinkedIn header format as of 2024/2025
HEADER_PREFIX = "First Name,Last Name,URL,Email Address,Company,Position,Connected On"

DEFAULT_WORKLIST = "github_lookup_worklist.csv"
DEFAULT_HTML = "github_lookup_links.html"
DEFAULT_USERS_TXT = "users.txt"

# Defined columns for the enrichment worklist
WORKLIST_COLUMNS: Sequence[str] = (
    "name",
    "linkedin_url",
    "company",
    "position",
    "email",
    "connected_on",
    "github_username",
    "notes",
    "google",
    "google_company",
    "google_site_github",
    "google_site_role",
    "github_search",
)

# Silence loguru for CLI usage unless specifically debugging
logger.remove()
logger.add(lambda msg: print(msg, end=""), level="INFO", colorize=True)

class Connection(BaseModel):
    """
    Represents a single LinkedIn connection. 
    Using Pydantic here for the validation and easy CSV serialization.
    """
    model_config = ConfigDict(frozen=True)

    name: str
    linkedin_url: str
    company: str
    position: str
    email: str
    connected_on: str
    google: str = ""
    google_company: str = ""
    google_site_github: str = ""
    google_site_role: str = ""
    github_search: str = ""

def _find_header_index(lines: list[str]) -> int:
    """Find where the actual CSV data starts, skipping LinkedIn's 'Notes' lines."""
    for i, line in enumerate(lines):
        if line.startswith(HEADER_PREFIX):
            return i
    raise ValueError(f"Target header not found. Expected: {HEADER_PREFIX[:20]}...")

def _generate_search_links(name: str, company: str, position: str) -> dict[str, str]:
    """Helper to generate targeted search URLs for person discovery."""
    name = (name or "").strip()
    comp = (comp or "").strip() if (comp := company) else ""
    pos = (pos or "").strip() if (pos := position) else ""

    queries = {
        "google": f"{name} github",
        "google_company": f"{name} {comp} github",
        "google_site_github": f"site:github.com {name} {comp}",
        "google_site_role": f"site:github.com {name} {pos}",
        "github_search": f"{name} {comp}",
    }

    return {
        k: "https://www.google.com/search?q=" + quote_plus(v) if "google" in k
        else "https://github.com/search?q=" + quote_plus(v) + "&type=users"
        for k, v in queries.items()
    }

def parse_linkedin_export(csv_path: Path) -> list[Connection]:
    """Reads the raw LinkedIn Connections.csv and returns a list of Connection objects.
    
    Raises:
        ValueError: If the CSV format is invalid or header is not found.
        FileNotFoundError: If the CSV file does not exist.
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"LinkedIn export not found: {csv_path}")
    
    try:
        # LinkedIn uses utf-8-sig for their exports
        raw_text = csv_path.read_text(encoding="utf-8-sig", errors="replace")
        lines = raw_text.splitlines()
    except Exception as e:
        raise ValueError(f"Failed to read CSV file: {e}") from e
    
    start_idx = _find_header_index(lines)
    content = "\n".join(lines[start_idx:])

    reader = csv.DictReader(content.splitlines())
    items: list[Connection] = []

    for r in reader or []:
        first = (r.get("First Name") or "").strip()
        last = (r.get("Last Name") or "").strip()
        name = f"{first} {last}".strip()
        
        if not name:
            continue

        company = (r.get("Company") or "").strip()
        pos = (r.get("Position") or "").strip()
        
        links = _generate_search_links(name, company, pos)
        
        items.append(
            Connection(
                name=name,
                linkedin_url=(r.get("URL") or "").strip(),
                company=company,
                position=pos,
                email=(r.get("Email Address") or "").strip(),
                connected_on=(r.get("Connected On") or "").strip(),
                **links
            )
        )

    return items

def write_worklist(items: Iterable[Connection], out_path: Path) -> None:
    """Writes the initial worklist CSV for human enrichment."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(WORKLIST_COLUMNS))
        writer.writeheader()
        for item in items:
            row = item.model_dump()
            row.update({"github_username": "", "notes": ""})
            writer.writerow(row)

def write_dashboard(
    items: Iterable[Connection],
    out_path: Path,
    title: str = "Connections Search Dashboard",
) -> None:
    """Generates the modern HTML dashboard for reviewing connections."""
    out_path.parent.mkdir(parents=True, exist_ok=True)

    def link(url: str, label: str, css_class: str = "") -> str:
        u = html.escape(url or "", quote=True)
        label_escaped = html.escape(label or "")
        c = f' class="{html.escape(css_class)}"' if css_class else ""
        return (
            f'<a href="{u}" target="_blank" rel="noopener noreferrer"{c}>'
            f"{label_escaped}</a>"
        )

    rows = []
    for it in items:
        rows.append(
            f"""<tr class="connection-row">
                <td>
                    <div class="name-cell">{html.escape(it.name)}</div>
                    <div class="role-cell">{link(it.linkedin_url, 'LinkedIn Profile') if it.linkedin_url else 'N/A'}</div>
                </td>
                <td>
                    <div class="name-cell">{html.escape(it.company)}</div>
                    <div class="role-cell">{html.escape(it.position)}</div>
                </td>
                <td class="links-cell">
                    {link(it.google, 'Google', 'badge-link primary')}
                    {link(it.google_company, 'Company', 'badge-link')}
                    {link(it.google_site_github, 'Site Search', 'badge-link')}
                    {link(it.google_site_role, 'Role Search', 'badge-link')}
                    {link(it.github_search, 'GitHub', 'badge-link primary')}
                </td>
            </tr>"""
        )

    rows_html = "\n".join(rows)
    html_content = f"""<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>{html.escape(title)}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --primary: #0a66c2;
            --bg: #f8fafc;
            --card-bg: #ffffff;
            --text-main: #1e293b;
            --text-muted: #64748b;
            --border: #e2e8f0;
            --hover: #f1f5f9;
        }}

        @media (prefers-color-scheme: dark) {{
            :root {{
                --bg: #0f172a;
                --card-bg: #1e293b;
                --text-main: #f8fafc;
                --text-muted: #94a3b8;
                --border: #334155;
                --hover: #334155;
            }}
        }}

        body {{
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
            background-color: var(--bg);
            color: var(--text-main);
            margin: 0;
            padding: 40px 20px;
            line-height: 1.5;
        }}

        .container {{ max-width: 1200px; margin: 0 auto; }}

        header {{ margin-bottom: 40px; text-align: center; }}

        h1 {{ font-size: 2.2rem; font-weight: 700; margin: 0 0 12px 0; letter-spacing: -0.02em; }}

        .description {{ color: var(--text-muted); font-size: 1.1rem; max-width: 600px; margin: 0 auto; }}

        .search-container {{ margin-bottom: 24px; position: relative; }}

        #search-input {{
            width: 100%; padding: 14px 20px; border-radius: 12px;
            border: 1px solid var(--border); background: var(--card-bg);
            color: var(--text-main); font-size: 1rem; box-sizing: border-box;
            transition: all 0.2s; box-shadow: 0 1px 2px 0 rgb(0 0 0 / 0.05);
        }}

        #search-input:focus {{ outline: none; border-color: var(--primary); box-shadow: 0 0 0 3px rgba(10, 102, 194, 0.2); }}

        .table-wrapper {{
            background: var(--card-bg); border-radius: 16px;
            border: 1px solid var(--border); overflow: hidden;
            box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
        }}

        table {{ width: 100%; border-collapse: collapse; text-align: left; }}

        th {{
            background: var(--hover); padding: 16px 20px; font-weight: 600;
            font-size: 0.85rem; color: var(--text-muted); text-transform: uppercase;
            letter-spacing: 0.05em; border-bottom: 1px solid var(--border);
        }}

        td {{ padding: 16px 20px; font-size: 0.9rem; border-bottom: 1px solid var(--border); vertical-align: middle; }}

        .name-cell {{ font-weight: 600; }}
        .role-cell {{ color: var(--text-muted); font-size: 0.85rem; }}

        .links-cell {{ display: flex; gap: 8px; flex-wrap: wrap; }}

        .badge-link {{
            display: inline-flex; align-items: center; padding: 6px 12px;
            border-radius: 6px; font-size: 0.75rem; font-weight: 500;
            text-decoration: none; transition: all 0.2s;
            background: var(--bg); border: 1px solid var(--border); color: var(--text-main);
        }}

        .badge-link:hover {{ background: var(--primary); color: white; border-color: var(--primary); transform: translateY(-1px); }}

        .badge-link.primary {{ background: rgba(10, 102, 194, 0.1); color: var(--primary); border-color: rgba(10, 102, 194, 0.2); }}

        @media (max-width: 768px) {{ .stats {{ grid-template-columns: 1fr; }} th:nth-child(n+3), td:nth-child(n+3) {{ display: none; }} }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>{html.escape(title)}</h1>
            <p class="description">Identify your LinkedIn network on GitHub. Interactive search enabled.</p>
        </header>

        <div class="search-container">
            <input type="text" id="search-input" placeholder="Search by name, company, or role..." onkeyup="filterTable()">
        </div>

        <div class="table-wrapper">
            <table id="connections-table">
                <thead>
                    <tr>
                        <th>Professional</th>
                        <th>Role & Company</th>
                        <th>Lookup Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
        </div>
    </div>

    <script>
        function filterTable() {{
            const filter = document.getElementById('search-input').value.toLowerCase();
            const tr = document.getElementById('connections-table').getElementsByTagName('tr');
            for (let i = 1; i < tr.length; i++) {{
                tr[i].style.display = tr[i].textContent.toLowerCase().includes(filter) ? "" : "none";
            }}
        }}

        window.addEventListener('keydown', (e) => {{
            if (e.key === '/' && document.activeElement.tagName !== 'INPUT') {{
                e.preventDefault(); document.getElementById('search-input').focus();
            }}
        }});
    </script>
</body>
</html>
"""
    out_path.write_text(html_content, encoding="utf-8")

def suggest_usernames(
    items: list[Connection], token: str | None = None
) -> list[tuple[Connection, str, float]]:
    """Automatic discovery for GitHub profiles using targeted search.
    
    Uses GitHub API with optional PAT token. Falls back to local gh CLI.
    If rate limit (403) is hit, logs warning and continues with remaining items.
    
    Args:
        items: List of LinkedIn connections to search.
        token: Optional GitHub Personal Access Token.
        
    Returns:
        List of tuples: (Connection, github_username, confidence_score).
    """
    results: list[tuple[Connection, str, float]] = []
    headers = {"Accept": "application/vnd.github.v3+json"}
    
    if token:
        headers["Authorization"] = f"token {token}"
    else:
        # Fallback to local gh CLI session if available
        try:
            res = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=False)
            if res.returncode == 0 and (t := res.stdout.strip()):
                headers["Authorization"] = f"token {t}"
        except Exception:
            pass

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True
    ) as progress:
        task = progress.add_task("Searching GitHub API...", total=len(items))
        with httpx.Client(headers=headers, timeout=15) as client:
            for it in items:
                username, confidence = "", 0.0

                # Priority 1: High confidence (Name + Company)
                q = f"{it.name} {it.company}".strip()
                try:
                    resp = client.get("https://api.github.com/search/users", params={"q": q})
                    if resp.status_code == 200:
                        data = resp.json()
                        if data.get("total_count", 0) > 0:
                            username = data["items"][0]["login"]
                            confidence = 0.9 if data["total_count"] == 1 else 0.7
                            logger.info(f"Matched {it.name} -> {username}")
                    elif resp.status_code == 403:
                        logger.warning(
                            "GitHub API rate limit hit. Using PAT token is recommended. "
                            "Get one at https://github.com/settings/tokens/new"
                        )
                        # Continue with remaining items, don't break
                        results.append((it, "", 0.0))
                        continue
                except Exception as e:
                    logger.debug(f"Search failed for {it.name}: {e}")

                # Priority 2: Fallback (Name only)
                if not username:
                    try:
                        resp = client.get(
                            "https://api.github.com/search/users",
                            params={"q": it.name},
                        )
                        if (
                            resp.status_code == 200
                            and (data := resp.json()).get("total_count", 0) > 0
                        ):
                            username = data["items"][0]["login"]
                            confidence = 0.4
                    except Exception:
                        pass

                results.append((it, username, confidence))
                progress.update(task, advance=1)

    return results

def update_worklist_csv(
    out_path: Path,
    suggestions: list[tuple[Connection, str, float]],
    overwrite: bool = False,
) -> None:
    """Updates the worklist file with automation results while preserving manual notes."""
    existing = {}
    if out_path.exists() and not overwrite:
        with out_path.open("r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                existing[row["linkedin_url"]] = row

    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(WORKLIST_COLUMNS))
        writer.writeheader()
        for it, user, conf in suggestions:
            row = existing.get(it.linkedin_url, it.model_dump())
            
            # Populate automation results if empty
            if not row.get("github_username") and user:
                row["github_username"] = user
                existing_notes = row.get("notes", "")
                auto_note = f"Auto-discovery ({conf:.1f})"
                row["notes"] = (
                    f"{auto_note}; {existing_notes}"
                    if existing_notes
                    else auto_note
                )
            
            # Ensure links are present in the final row
            if "google" not in row:
                row.update(it.model_dump())
            
            writer.writerow({k: row.get(k, "") for k in WORKLIST_COLUMNS})

def read_following_list(worklist_path: Path) -> list[str]:
    """Extracts confirmed GitHub usernames from the worklist."""
    usernames = []
    seen = set()
    if not worklist_path.exists():
        return []

    with worklist_path.open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            u = (row.get("github_username") or "").strip().lstrip("@")
            # Basic validation/normalization
            u = re.sub(r"^https?://github\.com/", "", u).strip("/ ")
            if u and u not in seen:
                seen.add(u)
                usernames.append(u)
    return usernames

def follow_on_github(
    usernames: Iterable[str], dry_run: bool = True
) -> list[str]:
    """Uses the GitHub CLI to follow a list of users.
    
    Args:
        usernames: GitHub usernames to follow.
        dry_run: If True, only simulate. If False, actually follow.
        
    Returns:
        List of usernames that were attempted.
        
    Raises:
        FileNotFoundError: If 'gh' CLI is not installed.
    """
    attempted = []
    for u in usernames:
        u = u.strip().lstrip("@")
        if not u:
            continue
        attempted.append(u)
        if not dry_run:
            try:
                result = subprocess.run(
                    ["gh", "api", f"user/following/{u}", "-X", "PUT"],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode != 0:
                    logger.warning(
                        f"Failed to follow @{u}: {result.stderr.strip()}"
                    )
            except FileNotFoundError:
                raise FileNotFoundError(
                    "GitHub CLI ('gh') not found. "
                    "Install from: https://cli.github.com/"
                ) from None
            except subprocess.TimeoutExpired:
                logger.warning(f"Timeout following @{u}")
    return attempted
