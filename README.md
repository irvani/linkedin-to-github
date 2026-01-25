# linkedin-to-github

Turn a LinkedIn **Connections.csv** export into:

- `github_lookup_worklist.csv` — a worklist you can review + enrich (e.g., add GitHub usernames)
- `github_lookup_links.html` — clickable lookup links (Google + GitHub user search) per connection
- `users.txt` — unique GitHub usernames (from the worklist) for optional `gh` follow

This is designed to be **human-in-the-loop** (ToS-friendly): the tool generates lookup links and a worklist; you decide what to do next.

---

## Install

### Option A: pipx (recommended for CLI tools)
```bash
pipx install .
```

### Option B: editable install (dev)
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

---

## Usage

### 1) Export your LinkedIn connections
LinkedIn → Settings & Privacy → Data privacy → Get a copy of your data → Connections.

You should end up with a file like:
- `Connections.csv` (sometimes it includes `Notes:` lines above the real CSV header — handled automatically)

### 2) Generate worklist + HTML links
```bash
ltg make --connections /path/to/Connections.csv --outdir .
```

Outputs:
- `./github_lookup_worklist.csv`
- `./github_lookup_links.html`

### 3) Fill in GitHub usernames (optional)
Open `github_lookup_worklist.csv` and populate the `github_username` column for anyone you found.

### 4) Generate users.txt
```bash
ltg users --worklist ./github_lookup_worklist.csv --out ./users.txt
```

### 5) (Optional) Follow users via GitHub CLI
Requires `gh` installed and authenticated (`gh auth login`).

Dry-run:
```bash
ltg follow --users ./users.txt --dry-run
```

Actually follow:
```bash
ltg follow --users ./users.txt --yes
```

---

## CSV format notes

The parser looks for a header line that starts with:

```
First Name,Last Name,URL,Email Address,Company,Position,Connected On
```

If LinkedIn adds extra “Notes:” lines above the header, those are ignored.

---

## Development

Run lint + tests:
```bash
ruff check .
pytest
```

---

## License
MIT — see [LICENSE](LICENSE).
