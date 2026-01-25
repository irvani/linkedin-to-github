# linkedin-to-github

![Python Version](https://img.shields.edu/badge/python-3.10%2B-blue?style=flat-square&logo=python)
![License](https://img.shields.edu/github/license/irvani/linkedin-to-github?style=flat-square)
![Stars](https://img.shields.edu/github/stars/irvani/linkedin-to-github?style=flat-square)
![Issues](https://img.shields.edu/github/issues/irvani/linkedin-to-github?style=flat-square)

A utility to bridge the gap between your LinkedIn professional network and your GitHub community. 

I built this to automate the tedious process of finding and following professional connections on GitHub. It parses a LinkedIn connections export, generates targeted lookup links, and can optionally use the GitHub Search API to suggest matches based on name and company.

## Features

- **Pydantic-powered parsing**: Robust handling of LinkedIn's CSV export format.
- **Automated Discovery**: Heuristic-based search using the GitHub API (via `httpx`).
- **Interactive Dashboard**: A modern, dark-mode-ready HTML interface for manual review and enrichment.
- **CLI Sync**: Direct integration with the GitHub CLI (`gh`) for mass-following.

## Tech Stack

Selected for performance and developer experience:
- [Typer](https://typer.tiangolo.com/) (CLI)
- [Pydantic V2](https://docs.pydantic.dev/) (Data Modeling)
- [HTTPX](https://www.python-httpx.org/) (Networking)
- [Rich](https://github.com/Textualize/rich) (Terminal UI)

## Installation

```bash
git clone https://github.com/irvani/linkedin-to-github.git
cd linkedin-to-github
make dev
```

## Workflow

### 1. Initialize Project
Export your connections from LinkedIn and run:
```bash
ltg init --connections Connections.csv
```
This creates `github_lookup_worklist.csv` and an interactive `github_lookup_links.html`.

### 2. Automated Search (Optional)
To speed things up, let the tool try to find users for you:
```bash
ltg search --connections Connections.csv
```

### 3. Review & Sync
Open the dashboard, verify the GitHub usernames in the CSV, and then:
```bash
ltg sync --worklist github_lookup_worklist.csv --yes
```

## Development

Check the [Makefile](./Makefile) for common tasks:
- `make test`: Run pytest suite.
- `make lint`: Run ruff checks.
- `make clean`: Cleanup build artifacts.

---
License: MIT
