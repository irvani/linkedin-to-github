from __future__ import annotations

import csv
import html
import json
import os
import re
import subprocess
from collections.abc import Iterable, Sequence
from pathlib import Path
from urllib.parse import quote_plus

import httpx
from loguru import logger
from pydantic import BaseModel, ConfigDict
from rich.progress import Progress, SpinnerColumn, TextColumn
from rapidfuzz import fuzz

# Standard LinkedIn header format as of 2024/2025
HEADER_PREFIX = "First Name,Last Name,URL,Email Address,Company,Position,Connected On"

DEFAULT_WORKLIST = Path("github_lookup_worklist.csv")
DEFAULT_HTML = Path("github_lookup_links.html")
DEFAULT_USERS_TXT = Path("users.txt")
CONFIG_PATH = Path.home() / ".ltg_config.json"

# Noise reduction for production
logger.remove()
logger.add(lambda msg: print(msg, end=""), level="WARNING", colorize=True)

def load_config() -> dict:
    """Loads local configuration."""
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_config(config: dict) -> None:
    """Saves local configuration."""
    CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")

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
    google_site_role: str = ""
    github_search: str = ""

class Organization(BaseModel):
    """Represents a followed LinkedIn company."""
    name: str
    followed_on: str
    github_org: str = ""
    github_url: str = ""
    confidence: float = 0.0

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

def parse_linkedin_companies(csv_path: Path) -> list[Organization]:
    """Parses LinkedIn 'Company Follows.csv' export."""
    if not csv_path.exists():
        raise FileNotFoundError(f"File not found: {csv_path}")
    
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [Organization(name=row["Organization"], followed_on=row["Followed On"]) for row in reader]

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
    title: str = "LinkedIn-to-GitHub Explorer",
    orgs: list[Organization] | None = None,
) -> None:
    """Generates a premium Glassmorphism HTML dashboard with Network and Company insights."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    orgs = orgs or []
    
    # Analytics for Connections
    conn_list = [it.model_dump() for it in items]
    analytics = get_analytics_data(conn_list)
    
    # Analytics for Orgs
    org_data = [o.model_dump() for o in orgs]
    
    def link(url: str, label: str, css_class: str = "") -> str:
        u = html.escape(url or "", quote=True)
        label_escaped = html.escape(label or "")
        c = f' class="{html.escape(css_class)}"' if css_class else ""
        return (
            f'<a href="{u}" target="_blank" rel="noopener noreferrer"{c}>'
            f"{label_escaped}</a>"
        )

    # Network Cards
    cards = []
    for it in items:
        # Check if already following (heuristic for demo)
        is_following = False 
        
        cards.append(
            f"""<div class="glass-card connection-row" data-name="{html.escape(it.name.lower())}" data-company="{html.escape(it.company.lower())}">
                <div class="card-header">
                    <div class="avatar-circle">{html.escape(it.name[0]) if it.name else '?'}</div>
                    <div class="header-info">
                        <h3 class="name-text">{html.escape(it.name)}</h3>
                        <div class="role-text">{html.escape(it.position)}</div>
                    </div>
                </div>
                <div class="card-body">
                    <div class="company-badge">🏢 {html.escape(it.company or "Independent")}</div>
                    <div class="social-tags">
                        <span class="status-tag tag-pending">Discovery Pending</span>
                    </div>
                </div>
                <div class="card-footer">
                    <div class="lookup-grid">
                        {link(it.google, 'Google', 'btn btn-ghost')}
                        {link(it.github_search, 'GitHub', 'btn btn-primary')}
                        {link(it.linkedin_url, 'Profile', 'btn btn-ghost')}
                    </div>
                </div>
            </div>"""
        )
    cards_html = "\n".join(cards)

    # Org Cards (Beta)
    org_cards = []
    for o in orgs:
        org_cards.append(
            f"""<div class="glass-card org-card" data-name="{html.escape(o.name.lower())}">
                <div class="card-header">
                    <div class="avatar-circle">🏢</div>
                    <div class="header-info">
                        <h3 class="name-text">{html.escape(o.name)}</h3>
                        <div class="role-text">Followed on LinkedIn</div>
                    </div>
                </div>
                <div class="card-body">
                    <div class="social-tags">
                        <span class="status-tag {'tag-following' if o.github_org else 'tag-pending'}">
                            {html.escape(o.github_org or 'Discovery Pending')}
                        </span>
                    </div>
                </div>
                <div class="card-footer">
                    <div class="lookup-grid">
                        {link(o.github_url, 'View Org', 'btn btn-primary') if o.github_url else ''}
                        {link(f"https://github.com/search?q={quote_plus(o.name)}+type:org", 'Search', 'btn btn-ghost')}
                    </div>
                </div>
            </div>"""
        )
    orgs_html = "\n".join(org_cards)

    analytics_js = json.dumps(analytics)
    
    html_content = f"""<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>{html.escape(title)}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;600&family=Fira+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {{
            --primary: #22c55e;
            --secondary: #1e293b;
            --bg: #020617;
            --card-bg: rgba(30, 41, 59, 0.4);
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --border: rgba(255, 255, 255, 0.1);
            --hover: rgba(51, 65, 85, 0.6);
            --glass-blur: 16px;
        }}

        body {{ font-family: 'Fira Sans', sans-serif; background-color: var(--bg); background-image: radial-gradient(at 0% 0%, rgba(34, 197, 94, 0.1) 0px, transparent 50%), radial-gradient(at 100% 0%, rgba(14, 165, 233, 0.1) 0px, transparent 50%); color: var(--text-main); margin: 0; padding: 2rem; min-height: 100vh; }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        header {{ margin-bottom: 2rem; text-align: center; }}
        h1 {{ font-family: 'Fira Code', monospace; font-size: 2.5rem; background: linear-gradient(to right, #22c55e, #10b981); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin: 0 0 0.5rem 0; }}
        .description {{ color: var(--text-muted); }}

        .nav-tabs {{ display: flex; justify-content: center; gap: 1rem; margin-bottom: 3rem; background: rgba(255, 255, 255, 0.03); padding: 0.5rem; border-radius: 1rem; width: fit-content; margin-inline: auto; }}
        .tab-btn {{ padding: 0.75rem 1.5rem; border: none; background: transparent; color: var(--text-muted); font-weight: 600; cursor: pointer; border-radius: 0.75rem; transition: 0.3s; }}
        .tab-btn.active {{ background: var(--primary); color: #000; }}
        
        .tab-content {{ display: none; animation: fadeIn 0.4s; }}
        .tab-content.active {{ display: block; }}
        @keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(10px); }} to {{ opacity: 1; transform: translateY(0); }} }}

        .insights-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 2rem; margin-bottom: 3rem; }}
        .chart-container {{ background: var(--card-bg); backdrop-filter: blur(var(--glass-blur)); border: 1px solid var(--border); border-radius: 1.25rem; padding: 2rem; }}
        .chart-title {{ font-size: 1.25rem; color: var(--primary); margin-bottom: 1.5rem; text-align: center; font-weight: 600; }}

        .search-container {{ margin-bottom: 2rem; position: sticky; top: 1rem; z-index: 100; }}
        .search-input {{ width: 100%; padding: 1.25rem; border-radius: 1rem; border: 1px solid var(--border); background: rgba(15, 23, 42, 0.9); color: #fff; box-sizing: border-box; font-size: 1.1rem; }}

        .grid-layout {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 1.5rem; }}
        .glass-card {{ background: var(--card-bg); backdrop-filter: blur(var(--glass-blur)); border: 1px solid var(--border); border-radius: 1rem; padding: 1.5rem; transition: 0.3s; display: flex; flex-direction: column; justify-content: space-between; }}
        .glass-card:hover {{ transform: translateY(-5px); background: var(--hover); }}

        .card-header {{ display: flex; gap: 1rem; align-items: center; margin-bottom: 1rem; }}
        .avatar-circle {{ width: 44px; height: 44px; border-radius: 50%; background: #1e293b; display: flex; align-items: center; justify-content: center; color: var(--primary); font-weight: 700; border: 1px solid var(--border); }}
        .name-text {{ margin: 0; font-size: 1.1rem; color: #fff; }}
        .role-text {{ font-size: 0.8rem; color: var(--text-muted); }}
        .company-badge {{ background: rgba(255,255,255,0.05); padding: 0.4rem 0.8rem; border-radius: 2rem; font-size: 0.85rem; color: var(--primary); display: inline-block; margin-bottom: 1rem; }}
        
        .social-tags {{ margin-bottom: 1rem; }}
        .status-tag {{ font-size: 0.7rem; padding: 0.2rem 0.6rem; border-radius: 0.4rem; font-weight: 700; }}
        .tag-pending {{ background: rgba(255,255,255,0.1); color: var(--text-muted); }}
        .tag-following {{ background: rgba(34,197,94,0.2); color: var(--primary); }}

        .card-footer {{ border-top: 1px solid var(--border); padding-top: 1rem; display: flex; justify-content: flex-start; align-items: center; }}
        .lookup-grid {{ display: flex; gap: 0.5rem; }}
        .btn {{ padding: 0.5rem 0.8rem; border-radius: 0.5rem; font-size: 0.75rem; text-decoration: none; font-weight: 600; display: inline-flex; align-items: center; }}
        .btn-primary {{ background: var(--primary); color: #000; }}
        .btn-ghost {{ background: rgba(255,255,255,0.05); color: #fff; border: 1px solid var(--border); }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>LinkedIn-to-GitHub Explorer</h1>
            <p class="description">Discovery Insights & Professional Ecosystem</p>
        </header>

        <nav class="nav-tabs">
            <button class="tab-btn active" onclick="switchTab('explorer')">Network Explorer</button>
            <button class="tab-btn" onclick="switchTab('ecosystem')">Company Ecosystem (Beta)</button>
            <button class="tab-btn" onclick="switchTab('insights')">Insights</button>
        </nav>

        <div id="explorer" class="tab-content active">
            <div class="search-container">
                <input type="text" id="search-input" class="search-input" placeholder="Search people or companies..." onkeyup="filterCards('connection-row', 'search-input')">
            </div>
            <div class="grid-layout">{cards_html}</div>
        </div>

        <div id="ecosystem" class="tab-content">
            <div class="search-container">
                <input type="text" id="org-search" class="search-input" placeholder="Search followed companies..." onkeyup="filterCards('org-card', 'org-search')">
            </div>
            <div class="grid-layout">{orgs_html}</div>
        </div>

        <div id="insights" class="tab-content">
            <div class="insights-grid">
                <div class="chart-container">
                    <div class="chart-title">Connection Demographics</div>
                    <canvas id="companyChart"></canvas>
                </div>
                <div class="chart-container">
                    <div class="chart-title">Discovery Confidence</div>
                    <canvas id="confidenceChart"></canvas>
                </div>
            </div>
        </div>
    </div>

    <script>
        const analyticsData = {analytics_js};

        function switchTab(id) {{
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.getElementById(id).classList.add('active');
            event.currentTarget.classList.add('active');
            if (id === 'insights') initCharts();
        }}

        function initCharts() {{
            const ctx1 = document.getElementById('companyChart').getContext('2d');
            new Chart(ctx1, {{
                type: 'bar',
                data: {{
                    labels: Object.keys(analyticsData.companies),
                    datasets: [{{ label: 'Connections', data: Object.values(analyticsData.companies), backgroundColor: '#22c55e', borderRadius: 8 }}]
                }},
                options: {{ plugins: {{ legend: {{ display: false }} }}, scales: {{ y: {{ beginAtZero: true, grid: {{ color: 'rgba(255,255,255,0.05)' }} }} }} }}
            }});

            const ctx2 = document.getElementById('confidenceChart').getContext('2d');
            new Chart(ctx2, {{
                type: 'doughnut',
                data: {{
                    labels: Object.keys(analyticsData.confidences),
                    datasets: [{{ data: Object.values(analyticsData.confidences), backgroundColor: ['#22c55e', '#eab308', '#ef4444', '#475569'], borderWidth: 0 }}]
                }},
                options: {{ plugins: {{ legend: {{ position: 'bottom', labels: {{ color: '#f8fafc' }} }} }} }}
            }});
        }}

        function filterCards(className, inputId) {{
            const query = document.getElementById(inputId).value.toLowerCase();
            document.querySelectorAll('.' + className).forEach(card => {{
                card.style.display = card.dataset.name.includes(query) ? "flex" : "none";
            }});
        }}
    </script>
</body>
</html>
"""
    out_path.write_text(html_content, encoding="utf-8")

def suggest_usernames(
    items: list[Connection], token: str | None = None
) -> list[tuple[Connection, str, float]]:
    """Automatic discovery for GitHub profiles using targeted search."""
    if not token:
        config = load_config()
        token = config.get("github_token")

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
                            for hit in data["items"][:3]:  # Check top 3 hits
                                user_login = hit["login"]
                                # Get more details for fuzzy matching
                                user_resp = client.get(f"https://api.github.com/users/{user_login}")
                                if user_resp.status_code == 200:
                                    u_data = user_resp.json()
                                    gh_name = u_data.get("name") or ""
                                    gh_bio = u_data.get("bio") or ""
                                    gh_company = u_data.get("company") or ""
                                    
                                    # Fuzzy scores
                                    name_score = fuzz.token_sort_ratio(it.name.lower(), gh_name.lower())
                                    bio_score = fuzz.partial_ratio(it.company.lower(), gh_bio.lower())
                                    comp_score = fuzz.token_sort_ratio(it.company.lower(), gh_company.lower())
                                    
                                    # Heuristic match
                                    if name_score > 85 or (name_score > 70 and (bio_score > 80 or comp_score > 80)):
                                        username = user_login
                                        confidence = max(name_score, bio_score, comp_score) / 100.0
                                        logger.info(f"Fuzzy Match: {it.name} -> {username} ({int(confidence*100)}%)")
                                        break
                                    
                            if not username:
                                username = data["items"][0]["login"]
                                confidence = 0.7 if data["total_count"] == 1 else 0.5
                    elif resp.status_code == 403:
                        logger.warning(
                            "GitHub API rate limit hit. Using PAT token is recommended."
                        )
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

def suggest_organizations(
    orgs: list[Organization], token: str | None = None
) -> list[Organization]:
    """Beta: Automatically discover GitHub Organizations for followed LinkedIn companies."""
    if not token:
        config = load_config()
        token = config.get("github_token")

    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"

    with Progress(SpinnerColumn(), TextColumn("[bold blue]Discovery:[/] {task.description}"), transient=True) as progress:
        task = progress.add_task("Matching Company Orgs...", total=len(orgs))
        with httpx.Client(headers=headers, timeout=10) as client:
            for org in orgs:
                try:
                    # Search specifically for Orgs
                    resp = client.get("https://api.github.com/search/users", params={"q": f"{org.name} type:org"})
                    if resp.status_code == 200:
                        data = resp.json()
                        if data.get("total_count", 0) > 0:
                            hit = data["items"][0]
                            org.github_org = hit["login"]
                            org.github_url = hit["html_url"]
                            org.confidence = 0.9 if fuzz.token_sort_ratio(org.name.lower(), hit["login"].lower()) > 90 else 0.7
                except Exception:
                    pass
                progress.update(task, advance=1)
    return orgs

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

def check_following_status(usernames: list[str], token: str | None = None) -> dict[str, bool]:
    """Checks if the current authenticated user is following the given targets.
    
    Returns a mapping of username -> is_following.
    """
    is_following = {}
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    else:
        try:
            res = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=False)
            if res.returncode == 0 and (t := res.stdout.strip()):
                headers["Authorization"] = f"token {t}"
        except Exception:
            pass

    with httpx.Client(headers=headers, timeout=10) as client:
        # Check current user login first
        try:
            me_resp = client.get("https://api.github.com/user")
            if me_resp.status_code != 200:
                return {u: False for u in usernames if u}
        except Exception:
            return {u: False for u in usernames if u}

        for u in usernames:
            if not u:
                continue
            try:
                # GitHub returns 204 if following, 404 if not
                resp = client.get(f"https://api.github.com/user/following/{u}")
                is_following[u] = (resp.status_code == 204)
            except Exception:
                is_following[u] = False
    
    return is_following

def get_analytics_data(items: list[dict]) -> dict:
    """Aggregates networking data for visualization."""
    companies = {}
    positions = {}
    confidences = {"High (>80%)": 0, "Medium (50-80%)": 0, "Low (<50%)": 0, "None": 0}
    
    for it in items:
        # Company distribution
        c = it.get("company", "Independent") or "Independent"
        companies[c] = companies.get(c, 0) + 1
        
        # Position distribution
        p = it.get("position", "Other") or "Other"
        positions[p] = positions.get(p, 0) + 1
        
        # Confidence distribution
        notes = it.get("notes", "")
        if "Auto-discovery" in notes:
            try:
                # Extract score from "(40%)" or similar
                match = re.search(r"\((\d+)%\)", notes)
                if match:
                    score = int(match.group(1)) / 100.0
                    if score >= 0.8: confidences["High (>80%)"] += 1
                    elif score >= 0.5: confidences["Medium (50-80%)"] += 1
                    else: confidences["Low (<50%)"] += 1
                else:
                    confidences["None"] += 1
            except Exception:
                confidences["None"] += 1
        else:
            confidences["None"] += 1

    # Sort and limit top 5
    top_companies = dict(sorted(companies.items(), key=lambda x: x[1], reverse=True)[:5])
    top_positions = dict(sorted(positions.items(), key=lambda x: x[1], reverse=True)[:5])
    
    return {
        "companies": top_companies,
        "positions": top_positions,
        "confidences": confidences
    }
