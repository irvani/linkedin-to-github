from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .core import (
    DEFAULT_HTML,
    DEFAULT_WORKLIST,
    follow_on_github,
    parse_linkedin_export,
    read_following_list,
    suggest_usernames,
    update_worklist_csv,
    write_dashboard,
    write_worklist,
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
        write_worklist(items, csv_path)
        write_dashboard(items, html_path)

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
    console.print(
        f"\n[green]Done.[/] Found [bold]{total}[/] potential matches "
        f"across [bold]{len(items)}[/] connections."
    )

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
