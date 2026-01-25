from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from .core import (
    DEFAULT_HTML,
    DEFAULT_WORKLIST,
    follow_on_github,
    parse_linkedin_export,
    parse_linkedin_companies,
    read_following_list,
    suggest_usernames,
    suggest_organizations,
    update_worklist_csv,
    write_worklist,
    write_dashboard,
)

app = typer.Typer(
    help="Professional networking bridge between LinkedIn and GitHub.",
    add_completion=False,
    no_args_is_help=True
)
console = Console()

@app.command()
def init(
    connections: Path = typer.Option(
        ..., "--connections", "-c", help="LinkedIn Connections.csv export"
    ),
    out: Path = typer.Option(
        ".", "--out", "-o", help="Target output directory"
    ),
    worklist: str = typer.Option(
        DEFAULT_WORKLIST, help="CSV worklist filename"
    ),
    dashboard: str = typer.Option(
        DEFAULT_HTML, help="HTML dashboard filename"
    ),
) -> None:
    """
    Initialize a new search project from a LinkedIn export.
    """
    csv_path = out / worklist
    html_path = out / dashboard

    with console.status("Parsing connections and generating lookup links..."):
        items = parse_linkedin_export(connections)
        
        # Professional Ecosystem: Mapping Company Follows
        orgs = []
        comp_file = connections.parent / "Company Follows.csv"
        if comp_file.exists():
            orgs = parse_linkedin_companies(comp_file)

        write_worklist(items, csv_path)
        write_dashboard(items, html_path, orgs=orgs)

    console.print("[bold green]✔[/] Project initialized.")
    console.print(f"  • Worklist: [cyan]{csv_path}[/]")
    console.print(f"  • Dashboard: [cyan]{html_path}[/]")

@app.command()
def search(
    connections: Path = typer.Option(
        ..., "--connections", "-c", help="LinkedIn Connections.csv export"
    ),
    out: Path = typer.Option(
        ".", "--out", "-o", help="Target output directory"
    ),
    worklist: str = typer.Option(
        DEFAULT_WORKLIST, help="CSV worklist filename"
    ),
    token: str | None = typer.Option(
        None, help="Optional GitHub Personal Access Token"
    ),
    overwrite: bool = typer.Option(
        False, help="Overwrite manual entries in worklist"
    ),
) -> None:
    """
    Automate GitHub discovery by searching the GitHub API for matches.
    """
    csv_path = out / worklist
    items = parse_linkedin_export(connections)
    
    suggestions = suggest_usernames(items, token=token)
    update_worklist_csv(csv_path, suggestions, overwrite=overwrite)

    # Professional Ecosystem: Auto-match followed companies
    orgs = []
    comp_file = connections.parent / "Company Follows.csv"
    if comp_file.exists():
        orgs = suggest_organizations(parse_linkedin_companies(comp_file), token=token)

    write_dashboard(items, out / DEFAULT_HTML, orgs=orgs)

    table = Table(title="Search Matches", border_style="blue", box=None)
    table.add_column("Connection", style="bold")
    table.add_column("Identifier", style="green")
    table.add_column("Score", justify="right", style="dim")

    found = 0
    for it, user, conf in suggestions[:15]:
        if user:
            table.add_row(it.name, f"@{user}", f"{int(conf*100)}%")
            found += 1
    
    if found > 0:
        console.print("\n", table)
    
    total = sum(1 for _, u, _ in suggestions if u)
    high_conf = sum(1 for _, u, c in suggestions if u and c >= 0.8)
    
    console.print(Panel(
        f"Discovery Complete\n"
        f"  • Total Connections: [bold]{len(items)}[/]\n"
        f"  • Matches Found: [bold green]{total}[/]\n"
        f"  • High Confidence (>80%): [bold cyan]{high_conf}[/]",
        title="Search Summary",
        border_style="green"
    ))

@app.command()
def report(
    worklist: Path = typer.Option(
        DEFAULT_WORKLIST, "--worklist", "-w", help="CSV worklist file"
    ),
) -> None:
    """
    Generate a summary report of your networking progress.
    """
    if not worklist.exists():
        console.print(f"[red]Error:[/] Worklist not found: {worklist}")
        return

    from .core import read_following_list
    import csv

    all_items = []
    with worklist.open("r", encoding="utf-8") as f:
        all_items = list(csv.DictReader(f))

    followed = read_following_list(worklist)
    total = len(all_items)
    pending = total - len(followed)

    table = Table(title="Networking Progress Report", box=None)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="bold")
    
    table.add_row("Total Connections", str(total))
    table.add_row("GitHub Found/Linked", str(len([i for i in all_items if i.get("github_username")])))
    table.add_row("Actively Followed", f"[green]{len(followed)}[/]")
    table.add_row("Remaining", f"[yellow]{pending}[/]")

    console.print("\n", table)

@app.command()
def companies(
    file: Path = typer.Option("Company Follows.csv", "--file", "-f", help="LinkedIn Company Follows CSV"),
    out: Path = typer.Option(Path("company_discovery.json"), "--out", "-o", help="Output JSON file"),
) -> None:
    """
    Beta: Discover GitHub Organizations for the companies you follow on LinkedIn.
    """
    if not file.exists():
        console.print(f"[red]Error:[/] File not found: {file}")
        return

    from .core import parse_linkedin_companies, suggest_organizations
    orgs = parse_linkedin_companies(file)
    console.print(f"[cyan]Found {len(orgs)} companies to match...[/]")
    
    enriched = suggest_organizations(orgs)
    
    import json
    out.write_text(json.dumps([o.model_dump() for o in enriched], indent=2), encoding="utf-8")
    
    # Summary Table
    table = Table(title="Company Discovery (Beta)")
    table.add_column("LinkedIn Company")
    table.add_column("GitHub Org")
    table.add_column("Confidence")
    
    for o in enriched[:15]: # Show top 15
        table.add_row(o.name, o.github_org or "[dim]Not found[/]", f"{int(o.confidence*100)}%" if o.github_org else "-")
    
    console.print("\n", table)
    console.print(f"\n[green]✔[/] Full discovery saved to: [bold]{out}[/]")

@app.command()
def export(
    worklist: Path = typer.Option(
        DEFAULT_WORKLIST, "--worklist", "-w", help="CSV worklist file"
    ),
    format: str = typer.Option("markdown", "--format", "-f", help="Export format (markdown, json)"),
    out: Path = typer.Option(Path("network_export.md"), "--out", "-o", help="Output file path"),
) -> None:
    """
    Export your discovered network to Markdown or JSON.
    """
    if not worklist.exists():
        console.print(f"[red]Error:[/] Worklist not found: {worklist}")
        return

    import csv
    with worklist.open("r", encoding="utf-8") as f:
        items = list(csv.DictReader(f))

    if format.lower() == "json":
        out.with_suffix(".json").write_text(json.dumps(items, indent=2), encoding="utf-8")
        console.print(f"[green]✔[/] Exported to JSON: [bold]{out.with_suffix('.json')}[/]")
    else:
        # Markdown
        md = ["# My Professional Network on GitHub\n"]
        for it in items:
            name = it.get("name", "Unknown")
            gh = it.get("github_username")
            link = f"https://github.com/{gh}" if gh else "Not found"
            md.append(f"- **{name}**: [{gh or 'Lookup'}]({link}) ({it.get('company', 'Independent')})")
        
        out.with_suffix(".md").write_text("\n".join(md), encoding="utf-8")
        console.print(f"[green]✔[/] Exported to Markdown: [bold]{out.with_suffix('.md')}[/]")

@app.command()
def config(
    token: str = typer.Option(..., "--token", "-t", help="GitHub Personal Access Token")
) -> None:
    """
    Store your GitHub PAT token locally for automatic usage.
    """
    from .core import save_config, load_config
    conf = load_config()
    conf["github_token"] = token
    save_config(conf)
    console.print("[green]✔[/] Configuration saved. Token will be used automatically in discovery.")

@app.command()
def token() -> None:
    """
    Help create a GitHub Personal Access Token with correct permissions.
    """
    import webbrowser
    # Prefill name and scopes (read:user is usually enough for search/following)
    url = "https://github.com/settings/tokens/new?description=LinkedIn-to-GitHub&scopes=read:user"
    console.print(f"\n[bold cyan]Opening GitHub Token Creation Page...[/]")
    console.print(f"  1. Generate the token on the page that opens.")
    console.print(f"  2. Copy the token.")
    console.print(f"  3. Run: [bold]ltg config --token YOUR_TOKEN[/]\n")
    try:
        webbrowser.open(url)
    except Exception:
        console.print(f"Please open this URL manually: [link={url}]{url}[/link]")

@app.command()
def sync(
    worklist: Path = typer.Option(
        ..., "--worklist", "-w", help="Enriched CSV worklist"
    ),
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Skip confirmation prompt"
    ),
) -> None:
    """
    Follow identified users on GitHub using the 'gh' CLI. 
    """
    if not worklist.exists():
        console.print(f"[red]Error:[/] Worklist not found: {worklist}")
        raise typer.Exit(1)

    usernames = read_following_list(worklist)

    if not yes:
        console.print(f"[yellow]Plan:[/] Follow {len(usernames)} users on GitHub.")
        for u in usernames[:5]:
            console.print(f"  - @{u}")
        if len(usernames) > 5:
            console.print(f"  ... and {len(usernames) - 5} others.")
        console.print("[cyan]Run with --yes to confirm.[/]")
    else:
        with console.status("Syncing follows..."):
            attempted = follow_on_github(usernames, dry_run=False)
        console.print(f"[green]✔[/] Followed {len(attempted)} users on GitHub.")

if __name__ == "__main__":
    app()
